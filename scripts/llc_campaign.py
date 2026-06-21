from __future__ import annotations

import argparse
import csv
import inspect
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.final_training import checkpoint_name
from scripts.scientific_pilot import (
    git_commit,
    git_status_short,
    package_versions,
    path_size_bytes,
    sha256_file,
    tokenize_texts,
    utc_now,
    write_json,
    write_jsonl,
)


PRIMARY_CONDITION = "structured_pt_seed_a"
PHASE = "03_llc_campaign"
OBSERVABLE_NAME = "fixed_portuguese_sampler_reference"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def numeric_summary(values: Iterable[float]) -> dict[str, Any]:
    nums = [float(v) for v in values]
    finite = [v for v in nums if math.isfinite(v)]
    return {
        "count": len(nums),
        "finite_count": len(finite),
        "min": min(finite) if finite else None,
        "max": max(finite) if finite else None,
        "mean": statistics.mean(finite) if finite else None,
        "first": finite[0] if finite else None,
        "last": finite[-1] if finite else None,
    }


def validate_frozen_selection(
    *,
    selection: dict[str, Any],
    condition_summary: dict[str, Any],
    checkpoint_root: Path,
    expected_tokens: list[int] | None,
) -> list[dict[str, Any]]:
    if not selection.get("no_final_llc_inspected"):
        raise ValueError("Frozen selection must have no_final_llc_inspected=true")
    if selection.get("primary_condition") != PRIMARY_CONDITION:
        raise ValueError(f"Frozen selection primary condition must be {PRIMARY_CONDITION}")

    selected = [int(x) for x in selection["selected_checkpoint_tokens"]]
    if expected_tokens is not None and selected != expected_tokens:
        raise ValueError(f"Frozen selected tokens changed: got {selected}, expected {expected_tokens}")

    available = [int(item["target_tokens"]) for item in condition_summary["checkpoint_plan"]]
    statuses: list[dict[str, Any]] = []
    for token in available:
        name = checkpoint_name(token)
        ckpt_dir = checkpoint_root / name
        selected_for_llc = token in selected
        missing_files = [
            rel for rel in ("config.json", "model.safetensors") if not (ckpt_dir / rel).exists()
        ]
        if selected_for_llc and missing_files:
            status = "invalid_rejected"
            reason = "selected checkpoint is missing required model files"
        elif selected_for_llc:
            status = "selected_valid"
            reason = "in frozen behavior-only LLC subset"
        else:
            status = "not_selected_rejected"
            reason = "outside frozen behavior-only LLC subset"
        statuses.append(
            {
                "target_tokens": token,
                "checkpoint": name,
                "selected_for_llc": selected_for_llc,
                "status": status,
                "reason": reason,
                "checkpoint_dir": str(ckpt_dir),
                "missing_files": missing_files,
            }
        )

    missing_selected = sorted(set(selected) - set(available))
    for token in missing_selected:
        statuses.append(
            {
                "target_tokens": token,
                "checkpoint": checkpoint_name(token),
                "selected_for_llc": True,
                "status": "invalid_rejected",
                "reason": "selected token is absent from final behavior checkpoint plan",
                "checkpoint_dir": str(checkpoint_root / checkpoint_name(token)),
                "missing_files": ["checkpoint_dir"],
            }
        )
    return sorted(statuses, key=lambda row: row["target_tokens"])


def extract_scalar(value: Any) -> float | None:
    try:
        return float(value.values)
    except Exception:
        try:
            return float(value)
        except Exception:
            return None


def running_llc_records(
    loss_trace: Any,
    *,
    init_loss: float,
    n_beta: float,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    values = loss_trace.values
    for chain_index, chain_values in enumerate(values):
        cumulative = 0.0
        for step_index, loss in enumerate(chain_values):
            loss_float = float(loss)
            cumulative += loss_float
            running_mean = cumulative / (step_index + 1)
            records.append(
                {
                    "chain": chain_index,
                    "step": step_index,
                    "loss_trace": loss_float,
                    "running_loss_mean": running_mean,
                    "running_llc": n_beta * (running_mean - init_loss),
                }
            )
    return records


def displacement_records(samples: Any) -> list[dict[str, Any]]:
    ds = samples.dataset
    if "metrics_distance" not in ds:
        return []
    arr = ds["metrics_distance"].values
    records: list[dict[str, Any]] = []
    for chain_index, chain_values in enumerate(arr):
        for step_index, distance in enumerate(chain_values):
            records.append(
                {"chain": chain_index, "step": step_index, "parameter_distance": float(distance)}
            )
    return records


def classify_checkpoint(result: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    finite = result["finite_result"]
    if not finite:
        reasons.append("nonfinite_llc_or_trace")

    loss_diag = result["loss_diagnostics"]
    if (
        loss_diag["late_mean"] < loss_diag["init_loss"] - 0.05
        and loss_diag["late_minus_early_mean"] < -0.05
    ):
        reasons.append("persistent_downhill_movement_below_center")

    chain = result["chain_diagnostics"]
    if chain["llc_std"] is not None and chain["llc_abs_mean"] is not None:
        if chain["llc_abs_mean"] > 1e-9 and chain["llc_std"] / chain["llc_abs_mean"] > 0.5:
            reasons.append("high_between_chain_dispersion")

    if result["trace_output_size_bytes"] <= 0:
        reasons.append("missing_raw_trace")
    if not result["displacement_recorded"]:
        reasons.append("missing_parameter_displacement_trace")

    return ("reportable_with_diagnostics" if not reasons else "rejected", reasons)


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if hasattr(value, "to_dict"):
        try:
            return jsonable(value.to_dict())
        except Exception:
            pass
    return repr(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name) for name in fieldnames})


def append_phase_state(
    *,
    output_dir: Path,
    run_id: str,
    manifest: dict[str, Any],
    summary: dict[str, Any],
    gate_decision: str,
    next_action: str,
) -> None:
    status = {
        "phase": PHASE,
        "gate": gate_decision,
        "last_updated": utc_now(),
        "latest_run_id": run_id,
        "latest_run_dir": str(output_dir),
        "final_training_run_id": Path(manifest["source_final_run_dir"]).name,
        "source_final_run_dir": manifest["source_final_run_dir"],
        "git_commit": manifest["git_commit"],
        "primary_condition": PRIMARY_CONDITION,
        "selected_checkpoint_tokens": manifest["selected_checkpoint_tokens"],
        "sampler_config": manifest["sampler_config"],
        "reportable_checkpoint_count": summary["reportable_checkpoint_count"],
        "rejected_checkpoint_count": summary["rejected_checkpoint_count"],
        "requires_human_approval": False,
        "approval_reason": "Standing unattended orchestrator pre-authorization recorded in state/decision_log.md.",
        "estimated_cost_usd": manifest["estimated_gpu_hours"],
        "projected_total_cost_usd": manifest["projected_total_cost_usd"],
        "hard_cap_usd": manifest["hard_cap_usd"],
        "evidence_paths": {
            "phase_report": str(output_dir / "phase_report.md"),
            "manifest": str(output_dir / "manifest.json"),
            "campaign_summary": str(output_dir / "llc_campaign_summary.json"),
            "checkpoint_validation": str(output_dir / "checkpoint_validation.json"),
            "report_source_tables": str(output_dir / "report_source_tables"),
            "bounded_job_dir": str(output_dir / "jobs" / "final_llc"),
        },
        "next_action": next_action,
    }
    write_json(Path("state/current_status.json"), status)

    decision = f"""
## {manifest['end_utc']} — final LLC campaign completed

Decision: {gate_decision}. The final LLC campaign used the frozen behavior-only checkpoint subset for `{PRIMARY_CONDITION}` without changing `results/02_final_training/final_training_20260620T053855Z/llc_checkpoint_selection.json`.

Evidence: `{output_dir / 'manifest.json'}`, `{output_dir / 'llc_campaign_summary.json'}`, `{output_dir / 'checkpoint_validation.json'}`, raw zarr traces under `{output_dir / 'raw_traces'}`, running estimates under `{output_dir / 'running_estimates'}`, displacement traces under `{output_dir / 'displacement'}`, failures under `{output_dir / 'failures'}`, and real report-source tables under `{output_dir / 'report_source_tables'}`.

Sampler controls: one global FP32 full-parameter sampler configuration was used at every selected checkpoint: lr `{manifest['sampler_config']['lr']}`, n_beta `{manifest['sampler_config']['n_beta']}`, localization `{manifest['sampler_config']['localization']}`, chains `{manifest['sampler_config']['num_chains']}`, burn-in `{manifest['sampler_config']['num_burnin_steps']}`, draws `{manifest['sampler_config']['num_draws']}`, steps-between-draws `{manifest['sampler_config']['num_steps_bw_draws']}`. No per-checkpoint retuning was performed.

Runtime/cost: observed wall time `{manifest['wall_seconds']:.2f}` seconds, estimated GPU-hours `{manifest['estimated_gpu_hours']:.4f}`, estimated incremental cost `${manifest['estimated_gpu_hours']:.4f}` at the $1/h planning rate. Projected total cost `${manifest['projected_total_cost_usd']:.4f}` remains below hard cap `${manifest['hard_cap_usd']:.2f}`.

Uncertainty and failure modes: diagnostics are local-posterior checks, not proof of a formal SLT phase transition. Rejected checkpoints must not be reported as scalar LLC estimates. Smooth or null trajectories remain acceptable. The reference set, loss, sequence length, normalization, and sampler settings were fixed across the trajectory.

Gate decision: {gate_decision}. Next bounded action: {next_action}
"""
    with Path("state/decision_log.md").open("a", encoding="utf-8") as handle:
        handle.write(decision)

    with Path("state/experiment_registry.csv").open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                run_id,
                PHASE,
                "passed" if gate_decision == "llc_complete_reportable_diagnostics" else "partial",
                PRIMARY_CONDITION,
                manifest["model"],
                manifest["seed"],
                manifest["git_commit"],
                str(output_dir / "sampler_config.json"),
                manifest["start_utc"],
                manifest["end_utc"],
                f"{manifest['estimated_gpu_hours']:.4f}",
                f"{manifest['estimated_gpu_hours']:.4f}",
                str(output_dir),
                (
                    "Frozen behavior-only checkpoint subset sampled with one global sampler config; "
                    f"reportable={summary['reportable_checkpoint_count']}, rejected={summary['rejected_checkpoint_count']}."
                ),
            ]
        )


def write_phase_report(
    *,
    output_dir: Path,
    run_id: str,
    manifest: dict[str, Any],
    summary: dict[str, Any],
    gate_decision: str,
    next_action: str,
) -> None:
    lines = [
        "# LLC Campaign Phase Report",
        "",
        f"- Run ID: `{run_id}`",
        f"- Source final run: `{manifest['source_final_run_dir']}`",
        f"- Primary condition: `{PRIMARY_CONDITION}`",
        f"- Frozen selected tokens: `{manifest['selected_checkpoint_tokens']}`",
        f"- Gate decision: `{gate_decision}`",
        "",
        "## Evidence",
        "",
        f"- Manifest: `{output_dir / 'manifest.json'}`",
        f"- Campaign summary: `{output_dir / 'llc_campaign_summary.json'}`",
        f"- Checkpoint validation: `{output_dir / 'checkpoint_validation.json'}`",
        f"- Raw traces: `{output_dir / 'raw_traces'}`",
        f"- Running estimates: `{output_dir / 'running_estimates'}`",
        f"- Parameter displacement: `{output_dir / 'displacement'}`",
        f"- Failures: `{output_dir / 'failures'}`",
        f"- Report-source tables: `{output_dir / 'report_source_tables'}`",
        "",
        "## Sampler Controls",
        "",
        "- One global sampler configuration was used for every selected checkpoint.",
        f"- Sampler config: `{manifest['sampler_config']}`",
        f"- Reference set: `{manifest['reference_set']['path']}`",
        f"- Reference hash: `{manifest['reference_set']['sha256']}`",
        f"- Sequence length: `{manifest['sequence_length']}`",
        "- Loss/normalization: devinterp next-token cross-entropy with fixed sequence length; raw LLC retained.",
        "",
        "## Diagnostics",
        "",
        f"- Reportable checkpoints with diagnostics: `{summary['reportable_checkpoint_count']}`",
        f"- Rejected selected checkpoints: `{summary['rejected_checkpoint_count']}`",
        f"- Invalid/missing selected checkpoints: `{summary['invalid_selected_checkpoint_count']}`",
        "",
        "## Runtime And Cost",
        "",
        f"- Wall seconds: `{manifest['wall_seconds']:.2f}`",
        f"- Estimated GPU-hours: `{manifest['estimated_gpu_hours']:.4f}`",
        f"- Projected total cost USD: `${manifest['projected_total_cost_usd']:.4f}`",
        f"- Hard cap USD: `${manifest['hard_cap_usd']:.2f}`",
        "",
        "## Uncertainty",
        "",
        "- Chain diagnostics, running estimates, displacement, and raw zarr traces are required for interpretation.",
        "- Rejected checkpoints must not be collapsed into a headline scalar.",
        "- This report does not claim a formal SLT phase transition.",
        "",
        "## Failure Modes",
        "",
        "- Intermediate checkpoints can drift downhill under the localized sampler.",
        "- Between-chain dispersion and autocorrelation can make scalar LLC overconfident.",
        "- The result is conditional on the fixed reference set and sampler configuration.",
        "",
        "## Gate Decision",
        "",
        f"`{gate_decision}`. Next bounded action: {next_action}",
        "",
    ]
    (output_dir / "phase_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    # Set from --condition below; declared global so every PRIMARY_CONDITION reference follows.
    global PRIMARY_CONDITION
    parser = argparse.ArgumentParser(description="Run final frozen-checkpoint LLC campaign")
    parser.add_argument("--final-run-dir", type=Path, required=True)
    parser.add_argument("--selection-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-selected-tokens", default="")
    parser.add_argument("--num-chains", type=int, default=3)
    parser.add_argument("--num-burnin-steps", type=int, default=200)
    parser.add_argument("--num-draws", type=int, default=100)
    parser.add_argument("--num-steps-bw-draws", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--n-beta", type=float, default=10.0)
    parser.add_argument("--localization", type=float, default=100.0)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--init-seed", type=int, default=20260620)
    parser.add_argument("--hourly-rate-usd", type=float, default=1.0)
    parser.add_argument(
        "--condition",
        default=PRIMARY_CONDITION,
        help="Which training condition to run the LLC campaign on (default: structured_pt_seed_a). "
        "The selection-json's primary_condition must match. For a valid (condition-matched) LLC, "
        "pass a --reference-path built from THIS condition's own training data.",
    )
    parser.add_argument(
        "--reference-path",
        type=Path,
        default=None,
        help="Path to the non-padded sampler reference for this condition. Defaults to "
        "<final-run-dir>/data_splits/sampler_reference.jsonl (the structured-PT reference). For a "
        "control condition, build a matched reference from its own training chunks so lambda-hat is "
        "measured at a minimum of the loss the model actually minimised.",
    )
    args = parser.parse_args()

    # Run the campaign on the requested condition. Setting the module global means every existing
    # reference to PRIMARY_CONDITION (condition paths, validation, manifest/report fields) follows.
    PRIMARY_CONDITION = args.condition

    start = time.perf_counter()
    start_utc = utc_now()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    for rel in (
        "raw_traces",
        "diagnostics",
        "running_estimates",
        "displacement",
        "failures",
        "report_source_tables",
    ):
        (output_dir / rel).mkdir(parents=True, exist_ok=True)

    import torch
    import xarray as xr
    from datasets import Dataset
    from devinterp.slt.llc import llc
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the bounded final LLC campaign")

    final_manifest = load_json(args.final_run_dir / "manifest.json")
    final_config = load_json(args.final_run_dir / "frozen_config.json")
    condition_summary = load_json(
        args.final_run_dir / "conditions" / PRIMARY_CONDITION / "condition_summary.json"
    )
    selection_before = load_json(args.selection_json)
    selection_sha_before = sha256_file(args.selection_json)
    selected_tokens = [int(x) for x in selection_before["selected_checkpoint_tokens"]]
    expected_tokens = (
        [int(x) for x in args.expected_selected_tokens.split(",") if x.strip()]
        if args.expected_selected_tokens
        else None
    )
    checkpoint_root = args.final_run_dir / "conditions" / PRIMARY_CONDITION / "checkpoints"
    checkpoint_statuses = validate_frozen_selection(
        selection=selection_before,
        condition_summary=condition_summary,
        checkpoint_root=checkpoint_root,
        expected_tokens=expected_tokens,
    )
    write_json(output_dir / "checkpoint_validation.json", checkpoint_statuses)
    write_csv(
        output_dir / "report_source_tables" / "checkpoint_selection.csv",
        checkpoint_statuses,
        [
            "target_tokens",
            "checkpoint",
            "selected_for_llc",
            "status",
            "reason",
            "checkpoint_dir",
            "missing_files",
        ],
    )
    invalid_selected = [
        row for row in checkpoint_statuses if row["selected_for_llc"] and row["status"] != "selected_valid"
    ]
    if invalid_selected:
        write_json(output_dir / "failures" / "invalid_selected_checkpoints.json", invalid_selected)

    sequence_length = int(final_config["training"]["sequence_length"])
    reference_path = (
        args.reference_path
        if args.reference_path is not None
        else args.final_run_dir / "data_splits" / "sampler_reference.jsonl"
    )
    reference_rows = load_jsonl(reference_path)
    tokenizer = AutoTokenizer.from_pretrained(
        checkpoint_root / checkpoint_name(selected_tokens[0]),
        local_files_only=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    input_ids = tokenize_texts(tokenizer, [row["pt"] for row in reference_rows], sequence_length)
    padded = [
        row[:sequence_length] + [tokenizer.pad_token_id] * (sequence_length - len(row))
        for row in input_ids
    ]
    dataset = Dataset.from_dict({"input_ids": padded})
    dataset.set_format(type="torch", columns=["input_ids"])
    observables = {OBSERVABLE_NAME: (dataset, 1)}

    sampler_config = {
        "precision": "fp32",
        "full_parameter_sampling": True,
        "sampling_method": "sgmcmc_sgld",
        "lr": args.lr,
        "n_beta": args.n_beta,
        "localization": args.localization,
        "batch_size": args.batch_size,
        "num_chains": args.num_chains,
        "num_burnin_steps": args.num_burnin_steps,
        "num_draws": args.num_draws,
        "num_steps_bw_draws": args.num_steps_bw_draws,
        "save_metrics": True,
        "init_seed": args.init_seed,
        "match_sampling_input_ids_across_chains": True,
        "shuffle": True,
    }
    write_json(output_dir / "sampler_config.json", sampler_config)

    sig = inspect.signature(llc)
    per_checkpoint: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    for token in selected_tokens:
        name = checkpoint_name(token)
        status = next(row for row in checkpoint_statuses if row["target_tokens"] == token)
        if status["status"] != "selected_valid":
            failure = {**status, "failure_type": "invalid_checkpoint"}
            failure_rows.append(failure)
            write_json(output_dir / "failures" / f"{name}.json", failure)
            continue

        checkpoint_dir = checkpoint_root / name
        trace_path = output_dir / "raw_traces" / f"{name}.zarr"
        result_path = output_dir / "diagnostics" / f"{name}.json"
        print(f"[llc] sampling {name} from {checkpoint_dir}", flush=True)
        try:
            model = AutoModelForCausalLM.from_pretrained(checkpoint_dir, local_files_only=True)
            model = model.to("cuda").float().train()
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
            checkpoint_start = time.perf_counter()
            result = llc(
                model=model,
                dataset=dataset,
                observables=observables,
                lr=args.lr,
                n_beta=args.n_beta,
                localization=args.localization,
                batch_size=args.batch_size,
                num_chains=args.num_chains,
                num_burnin_steps=args.num_burnin_steps,
                num_draws=args.num_draws,
                num_steps_bw_draws=args.num_steps_bw_draws,
                output_path=str(trace_path),
                save_metrics=True,
                init_seed=args.init_seed,
                device="cuda",
            )
            torch.cuda.synchronize()
            wall = time.perf_counter() - checkpoint_start

            samples = xr.open_datatree(str(trace_path), engine="zarr", consolidated=False)
            running_records = running_llc_records(
                result["loss_trace"],
                init_loss=float(result["init_loss"].values),
                n_beta=args.n_beta,
            )
            distance_rows = displacement_records(samples)
            write_jsonl(output_dir / "running_estimates" / f"{name}.jsonl", running_records)
            write_jsonl(output_dir / "displacement" / f"{name}.jsonl", distance_rows)

            loss_values = [row["loss_trace"] for row in running_records]
            chain_llcs = [float(v) for v in result["llc_per_chain"].values]
            early = loss_values[: max(1, len(loss_values) // 4)]
            late = loss_values[-max(1, len(loss_values) // 4) :]
            item = {
                "condition": PRIMARY_CONDITION,
                "checkpoint": name,
                "target_tokens": token,
                "actual_cumulative_tokens": next(
                    int(row["actual_cumulative_tokens"])
                    for row in condition_summary["checkpoint_plan"]
                    if int(row["target_tokens"]) == token
                ),
                "sampler_config": sampler_config,
                "reference_set": {
                    "path": str(reference_path),
                    "sha256": sha256_file(reference_path),
                    "examples": len(dataset),
                    "split": "sampler_reference",
                },
                "devinterp_llc_signature": str(sig),
                "result_summary": jsonable(result),
                "llc_mean": extract_scalar(result["llc_mean"]),
                "llc_std": extract_scalar(result["llc_std"]),
                "llc_scalar": extract_scalar(result["llc_scalar"]),
                "llc_per_chain": chain_llcs,
                "finite_result": all(math.isfinite(v) for v in chain_llcs),
                "trace_output_path": str(trace_path),
                "trace_output_size_bytes": path_size_bytes(trace_path),
                "running_estimates_path": str(output_dir / "running_estimates" / f"{name}.jsonl"),
                "displacement_path": str(output_dir / "displacement" / f"{name}.jsonl"),
                "displacement_recorded": bool(distance_rows),
                "loss_diagnostics": {
                    "init_loss": float(result["init_loss"].values),
                    "loss_trace": numeric_summary(loss_values),
                    "min_loss": min(loss_values) if loss_values else None,
                    "early_mean": statistics.mean(early),
                    "late_mean": statistics.mean(late),
                    "late_minus_early_mean": statistics.mean(late) - statistics.mean(early),
                },
                "chain_diagnostics": {
                    "llc_abs_mean": abs(statistics.mean(chain_llcs)) if chain_llcs else None,
                    "llc_std": statistics.pstdev(chain_llcs) if len(chain_llcs) > 1 else 0.0,
                    "between_chain_range": max(chain_llcs) - min(chain_llcs)
                    if chain_llcs
                    else None,
                },
                "displacement_diagnostics": {
                    "distance": numeric_summary(row["parameter_distance"] for row in distance_rows),
                    "final_distance_by_chain": [
                        row["parameter_distance"]
                        for row in distance_rows
                        if row["step"] == max((r["step"] for r in distance_rows), default=-1)
                    ],
                },
                "timing": {
                    "wall_seconds": wall,
                    "peak_memory_bytes": int(torch.cuda.max_memory_allocated()),
                },
            }
            report_status, rejection_reasons = classify_checkpoint(item)
            item["report_status"] = report_status
            item["rejection_reasons"] = rejection_reasons
            write_json(result_path, item)
            per_checkpoint.append(item)
            if report_status == "rejected":
                failure_rows.append(
                    {
                        "checkpoint": name,
                        "target_tokens": token,
                        "failure_type": "diagnostic_rejection",
                        "rejection_reasons": rejection_reasons,
                        "diagnostics_path": str(result_path),
                    }
                )
                write_json(output_dir / "failures" / f"{name}.json", failure_rows[-1])
        except Exception as exc:
            failure = {
                "checkpoint": name,
                "target_tokens": token,
                "failure_type": type(exc).__name__,
                "message": str(exc),
                "trace_output_path": str(trace_path),
                "trace_output_size_bytes": path_size_bytes(trace_path),
            }
            failure_rows.append(failure)
            write_json(output_dir / "failures" / f"{name}.json", failure)
            print(f"[llc] failed {name}: {exc}", flush=True)
        finally:
            try:
                del model
            except Exception:
                pass
            torch.cuda.empty_cache()

    selection_sha_after = sha256_file(args.selection_json)
    if selection_sha_after != selection_sha_before:
        raise RuntimeError("Frozen checkpoint-selection file changed during LLC campaign")

    total_wall = time.perf_counter() - start
    estimated_gpu_hours = total_wall / 3600.0
    starting_cumulative = float(final_config["cost"]["starting_cumulative_cost_usd"]) + float(
        final_manifest["estimated_cost_usd"]
    )
    projected_total_cost = starting_cumulative + estimated_gpu_hours * args.hourly_rate_usd
    hard_cap = float(final_config["cost"]["hard_cap_usd"])

    reportable = [row for row in per_checkpoint if row["report_status"] == "reportable_with_diagnostics"]
    rejected = [row for row in per_checkpoint if row["report_status"] == "rejected"]
    summary = {
        "run_kind": "final_llc_campaign",
        "status": "completed",
        "source_final_run_dir": str(args.final_run_dir),
        "primary_condition": PRIMARY_CONDITION,
        "selection_frozen_confirmed": True,
        "selection_sha256_before": selection_sha_before,
        "selection_sha256_after": selection_sha_after,
        "selected_checkpoint_tokens": selected_tokens,
        "sampler_config": sampler_config,
        "reference_set": {
            "path": str(reference_path),
            "sha256": sha256_file(reference_path),
            "examples": len(dataset),
        },
        "reportable_checkpoint_count": len(reportable),
        "rejected_checkpoint_count": len(rejected),
        "failed_checkpoint_count": len(failure_rows),
        "invalid_selected_checkpoint_count": len(invalid_selected),
        "checkpoint_results": per_checkpoint,
        "failures": failure_rows,
        "claim_language_guardrail": "Do not call this a formal SLT phase transition.",
    }
    write_json(output_dir / "llc_campaign_summary.json", summary)
    if failure_rows:
        write_json(output_dir / "failures" / "failures_summary.json", failure_rows)

    summary_rows = [
        {
            "condition": row["condition"],
            "checkpoint": row["checkpoint"],
            "target_tokens": row["target_tokens"],
            "actual_cumulative_tokens": row["actual_cumulative_tokens"],
            "llc_mean": row["llc_mean"],
            "llc_std": row["llc_std"],
            "llc_scalar": row["llc_scalar"],
            "report_status": row["report_status"],
            "rejection_reasons": ";".join(row["rejection_reasons"]),
            "trace_output_path": row["trace_output_path"],
            "running_estimates_path": row["running_estimates_path"],
            "displacement_path": row["displacement_path"],
        }
        for row in per_checkpoint
    ]
    write_csv(
        output_dir / "report_source_tables" / "llc_summary.csv",
        summary_rows,
        [
            "condition",
            "checkpoint",
            "target_tokens",
            "actual_cumulative_tokens",
            "llc_mean",
            "llc_std",
            "llc_scalar",
            "report_status",
            "rejection_reasons",
            "trace_output_path",
            "running_estimates_path",
            "displacement_path",
        ],
    )
    diagnostic_rows = [
        {
            "checkpoint": row["checkpoint"],
            "target_tokens": row["target_tokens"],
            "init_loss": row["loss_diagnostics"]["init_loss"],
            "min_loss": row["loss_diagnostics"]["min_loss"],
            "early_mean": row["loss_diagnostics"]["early_mean"],
            "late_mean": row["loss_diagnostics"]["late_mean"],
            "late_minus_early_mean": row["loss_diagnostics"]["late_minus_early_mean"],
            "between_chain_range": row["chain_diagnostics"]["between_chain_range"],
            "distance_mean": row["displacement_diagnostics"]["distance"]["mean"],
            "distance_max": row["displacement_diagnostics"]["distance"]["max"],
            "wall_seconds": row["timing"]["wall_seconds"],
            "peak_memory_bytes": row["timing"]["peak_memory_bytes"],
        }
        for row in per_checkpoint
    ]
    write_csv(
        output_dir / "report_source_tables" / "sampler_diagnostics.csv",
        diagnostic_rows,
        [
            "checkpoint",
            "target_tokens",
            "init_loss",
            "min_loss",
            "early_mean",
            "late_mean",
            "late_minus_early_mean",
            "between_chain_range",
            "distance_mean",
            "distance_max",
            "wall_seconds",
            "peak_memory_bytes",
        ],
    )

    run_id = output_dir.name
    manifest = {
        "run_kind": "final_llc_campaign",
        "run_id": run_id,
        "start_utc": start_utc,
        "end_utc": utc_now(),
        "wall_seconds": total_wall,
        "estimated_gpu_hours": estimated_gpu_hours,
        "projected_total_cost_usd": projected_total_cost,
        "hard_cap_usd": hard_cap,
        "git_commit": git_commit(),
        "git_status_short_at_start": git_status_short(),
        "package_versions": package_versions(),
        "source_final_run_dir": str(args.final_run_dir),
        "source_final_manifest": str(args.final_run_dir / "manifest.json"),
        "source_final_manifest_sha256": sha256_file(args.final_run_dir / "manifest.json"),
        "model": final_config["model"]["id"],
        "seed": final_config["training"]["seed"],
        "sequence_length": sequence_length,
        "selected_checkpoint_tokens": selected_tokens,
        "sampler_config": sampler_config,
        "reference_set": summary["reference_set"],
        "selection_sha256_before": selection_sha_before,
        "selection_sha256_after": selection_sha_after,
        "reportable_checkpoint_count": len(reportable),
        "rejected_checkpoint_count": len(rejected),
        "failed_checkpoint_count": len(failure_rows),
    }
    write_json(output_dir / "manifest.json", manifest)

    gate_decision = (
        "llc_complete_reportable_diagnostics"
        if len(reportable) == len(selected_tokens)
        else "llc_complete_with_rejections"
    )
    next_action = "Build the real report from report-source tables and raw diagnostics."
    write_phase_report(
        output_dir=output_dir,
        run_id=run_id,
        manifest=manifest,
        summary=summary,
        gate_decision=gate_decision,
        next_action=next_action,
    )
    append_phase_state(
        output_dir=output_dir,
        run_id=run_id,
        manifest=manifest,
        summary=summary,
        gate_decision=gate_decision,
        next_action=next_action,
    )
    print(json.dumps({"status": "completed", "run_id": run_id, "gate": gate_decision}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
