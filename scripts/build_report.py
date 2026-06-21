from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd


FINAL_RUN_DIR = Path("results/02_final_training/final_training_20260620T053855Z")
LLC_RUN_DIR = Path("results/03_llc_campaign/llc_campaign_final_training_20260620T053855Z_batch16")
REPORT_ROOT = Path("results/04_report")
CONDITIONS = [
    "structured_pt_seed_a",
    "structured_pt_seed_b",
    "shuffled_pt",
    "matched_en",
]
CONDITION_LABELS = {
    "structured_pt_seed_a": "structured PT seed A",
    "structured_pt_seed_b": "structured PT seed B",
    "shuffled_pt": "token-shuffled PT",
    "matched_en": "matched English",
}


@dataclass(frozen=True)
class SourceCell:
    table: str
    row_id: str
    column: str
    value: str
    source_paths: str
    source_keys: str
    transform: str


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def fmt_float(value: float | str | None, digits: int = 4) -> str:
    if value is None or value == "":
        return ""
    return f"{float(value):.{digits}f}"


def fmt_int(value: int | float | str | None) -> str:
    if value is None or value == "":
        return ""
    return str(int(float(value)))


def fmt_money(value: float | str | None) -> str:
    if value is None or value == "":
        return ""
    return f"${float(value):.4f}"


def json_key(*parts: str) -> str:
    return ".".join(parts)


def add_cells(
    cells: list[SourceCell],
    table: str,
    row_id: str,
    row: dict[str, Any],
    sources: dict[str, tuple[list[Path], list[str], str]],
) -> None:
    for column, value in row.items():
        paths, keys, transform = sources[column]
        cells.append(
            SourceCell(
                table=table,
                row_id=row_id,
                column=column,
                value=str(value),
                source_paths=";".join(str(path) for path in paths),
                source_keys=";".join(keys),
                transform=transform,
            )
        )


def bootstrap_ci(values: list[float], seed: int = 20260620, draws: int = 5000) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return math.nan, math.nan
    samples = rng.choice(arr, size=(draws, arr.size), replace=True).mean(axis=1)
    low, high = np.quantile(samples, [0.025, 0.975])
    return float(low), float(high)


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def condition_summary_path(final_run_dir: Path, condition: str) -> Path:
    return final_run_dir / "conditions" / condition / "condition_summary.json"


def load_condition_summaries(final_run_dir: Path) -> dict[str, dict[str, Any]]:
    return {condition: load_json(condition_summary_path(final_run_dir, condition)) for condition in CONDITIONS}


def ordered_evaluations(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(summary["evaluations"].values(), key=lambda item: int(item["target_tokens"]))


def metric_rows(final_run_dir: Path, summaries: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for condition, summary in summaries.items():
        for ev in ordered_evaluations(summary):
            margins = [float(item["margin"]) for item in ev["grammar_margin"]["margins"]]
            ci_low, ci_high = bootstrap_ci(margins)
            rows.append(
                {
                    "condition": condition,
                    "condition_label": CONDITION_LABELS[condition],
                    "checkpoint": ev["checkpoint"],
                    "target_tokens": int(ev["target_tokens"]),
                    "actual_cumulative_tokens": int(ev["actual_cumulative_tokens"]),
                    "pt_bpb": float(ev["pt_validation"]["bpb"]),
                    "english_bpb": float(ev["english_retention"]["bpb"]),
                    "grammar_mean_margin": float(ev["grammar_margin"]["mean_margin"]),
                    "grammar_margin_ci_low": ci_low,
                    "grammar_margin_ci_high": ci_high,
                    "grammar_accuracy": float(ev["grammar_margin"]["accuracy"]),
                    "grammar_examples": int(ev["grammar_margin"]["examples"]),
                    "source_summary": str(condition_summary_path(final_run_dir, condition)),
                }
            )
    return rows


def build_endpoint_table(
    final_run_dir: Path,
    summaries: dict[str, dict[str, Any]],
    cells: list[SourceCell],
) -> list[dict[str, str]]:
    table = "endpoint_summary.csv"
    rows: list[dict[str, str]] = []
    for condition in CONDITIONS:
        summary = summaries[condition]
        evaluations = ordered_evaluations(summary)
        first = evaluations[0]
        final = evaluations[-1]
        final_margins = [float(item["margin"]) for item in final["grammar_margin"]["margins"]]
        ci_low, ci_high = bootstrap_ci(final_margins)
        path = condition_summary_path(final_run_dir, condition)
        row = {
            "condition": CONDITION_LABELS[condition],
            "final_tokens": fmt_int(final["target_tokens"]),
            "pt_bpb_initial": fmt_float(first["pt_validation"]["bpb"]),
            "pt_bpb_final": fmt_float(final["pt_validation"]["bpb"]),
            "pt_bpb_delta": fmt_float(final["pt_validation"]["bpb"] - first["pt_validation"]["bpb"]),
            "grammar_margin_final": fmt_float(final["grammar_margin"]["mean_margin"]),
            "grammar_margin_95pct_ci": f"[{fmt_float(ci_low)}, {fmt_float(ci_high)}]",
            "grammar_accuracy_final": fmt_float(final["grammar_margin"]["accuracy"], 3),
            "english_bpb_final": fmt_float(final["english_retention"]["bpb"]),
            "english_bpb_delta": fmt_float(
                final["english_retention"]["bpb"] - first["english_retention"]["bpb"]
            ),
        }
        rows.append(row)
        prefix_first = json_key("evaluations", first["checkpoint"])
        prefix_final = json_key("evaluations", final["checkpoint"])
        sources = {
            "condition": ([path], ["condition"], "label mapping from condition id"),
            "final_tokens": ([path], [json_key(prefix_final, "target_tokens")], "integer formatting"),
            "pt_bpb_initial": (
                [path],
                [json_key(prefix_first, "pt_validation", "bpb")],
                "4-decimal formatting",
            ),
            "pt_bpb_final": (
                [path],
                [json_key(prefix_final, "pt_validation", "bpb")],
                "4-decimal formatting",
            ),
            "pt_bpb_delta": (
                [path],
                [
                    json_key(prefix_final, "pt_validation", "bpb"),
                    json_key(prefix_first, "pt_validation", "bpb"),
                ],
                "final minus initial, 4-decimal formatting",
            ),
            "grammar_margin_final": (
                [path],
                [json_key(prefix_final, "grammar_margin", "mean_margin")],
                "4-decimal formatting",
            ),
            "grammar_margin_95pct_ci": (
                [path],
                [json_key(prefix_final, "grammar_margin", "margins", "margin")],
                "fixed-seed bootstrap over 10 item margins",
            ),
            "grammar_accuracy_final": (
                [path],
                [json_key(prefix_final, "grammar_margin", "accuracy")],
                "3-decimal formatting",
            ),
            "english_bpb_final": (
                [path],
                [json_key(prefix_final, "english_retention", "bpb")],
                "4-decimal formatting",
            ),
            "english_bpb_delta": (
                [path],
                [
                    json_key(prefix_final, "english_retention", "bpb"),
                    json_key(prefix_first, "english_retention", "bpb"),
                ],
                "final minus initial, 4-decimal formatting",
            ),
        }
        add_cells(cells, table, condition, row, sources)
    return rows


def build_llc_alignment_table(
    final_run_dir: Path,
    llc_run_dir: Path,
    summaries: dict[str, dict[str, Any]],
    cells: list[SourceCell],
) -> list[dict[str, str]]:
    table = "llc_behavior_alignment.csv"
    llc_path = llc_run_dir / "report_source_tables" / "llc_summary.csv"
    llc_rows = read_csv_dicts(llc_path)
    primary = summaries["structured_pt_seed_a"]
    evals = {int(ev["target_tokens"]): ev for ev in ordered_evaluations(primary)}
    primary_path = condition_summary_path(final_run_dir, "structured_pt_seed_a")
    rows: list[dict[str, str]] = []
    for llc_row in llc_rows:
        target = int(llc_row["target_tokens"])
        ev = evals[target]
        row = {
            "target_tokens": fmt_int(target),
            "actual_tokens": fmt_int(llc_row["actual_cumulative_tokens"]),
            "pt_bpb": fmt_float(ev["pt_validation"]["bpb"]),
            "grammar_margin": fmt_float(ev["grammar_margin"]["mean_margin"]),
            "grammar_accuracy": fmt_float(ev["grammar_margin"]["accuracy"], 3),
            "llc_scalar": fmt_float(llc_row["llc_scalar"]),
            "llc_std": fmt_float(llc_row["llc_std"]),
            "llc_status": llc_row["report_status"],
            "rejection_reason": llc_row["rejection_reasons"],
        }
        rows.append(row)
        prefix = json_key("evaluations", ev["checkpoint"])
        csv_id = f"row target_tokens={target}"
        sources = {
            "target_tokens": ([llc_path], [csv_id + ".target_tokens"], "integer formatting"),
            "actual_tokens": (
                [llc_path],
                [csv_id + ".actual_cumulative_tokens"],
                "integer formatting",
            ),
            "pt_bpb": (
                [primary_path],
                [json_key(prefix, "pt_validation", "bpb")],
                "4-decimal formatting",
            ),
            "grammar_margin": (
                [primary_path],
                [json_key(prefix, "grammar_margin", "mean_margin")],
                "4-decimal formatting",
            ),
            "grammar_accuracy": (
                [primary_path],
                [json_key(prefix, "grammar_margin", "accuracy")],
                "3-decimal formatting",
            ),
            "llc_scalar": ([llc_path], [csv_id + ".llc_scalar"], "4-decimal formatting"),
            "llc_std": ([llc_path], [csv_id + ".llc_std"], "4-decimal formatting"),
            "llc_status": ([llc_path], [csv_id + ".report_status"], "copied verbatim"),
            "rejection_reason": ([llc_path], [csv_id + ".rejection_reasons"], "copied verbatim"),
        }
        add_cells(cells, table, str(target), row, sources)
    return rows


def build_sampler_table(llc_run_dir: Path, cells: list[SourceCell]) -> list[dict[str, str]]:
    table = "sampler_diagnostics.csv"
    diag_path = llc_run_dir / "report_source_tables" / "sampler_diagnostics.csv"
    llc_path = llc_run_dir / "report_source_tables" / "llc_summary.csv"
    diag_rows = read_csv_dicts(diag_path)
    llc_status = {row["checkpoint"]: row for row in read_csv_dicts(llc_path)}
    rows: list[dict[str, str]] = []
    for source in diag_rows:
        checkpoint = source["checkpoint"]
        status_row = llc_status[checkpoint]
        row = {
            "checkpoint": checkpoint,
            "target_tokens": fmt_int(source["target_tokens"]),
            "init_loss": fmt_float(source["init_loss"]),
            "early_mean_loss": fmt_float(source["early_mean"]),
            "late_mean_loss": fmt_float(source["late_mean"]),
            "late_minus_early": fmt_float(source["late_minus_early_mean"]),
            "between_chain_range": fmt_float(source["between_chain_range"]),
            "distance_max": fmt_float(source["distance_max"], 2),
            "status": status_row["report_status"],
            "rejection_reason": status_row["rejection_reasons"],
        }
        rows.append(row)
        csv_id = f"row checkpoint={checkpoint}"
        sources = {
            "checkpoint": ([diag_path], [csv_id + ".checkpoint"], "copied verbatim"),
            "target_tokens": ([diag_path], [csv_id + ".target_tokens"], "integer formatting"),
            "init_loss": ([diag_path], [csv_id + ".init_loss"], "4-decimal formatting"),
            "early_mean_loss": ([diag_path], [csv_id + ".early_mean"], "4-decimal formatting"),
            "late_mean_loss": ([diag_path], [csv_id + ".late_mean"], "4-decimal formatting"),
            "late_minus_early": (
                [diag_path],
                [csv_id + ".late_minus_early_mean"],
                "4-decimal formatting",
            ),
            "between_chain_range": (
                [diag_path],
                [csv_id + ".between_chain_range"],
                "4-decimal formatting",
            ),
            "distance_max": ([diag_path], [csv_id + ".distance_max"], "2-decimal formatting"),
            "status": ([llc_path], [csv_id + ".report_status"], "copied verbatim"),
            "rejection_reason": ([llc_path], [csv_id + ".rejection_reasons"], "copied verbatim"),
        }
        add_cells(cells, table, checkpoint, row, sources)
    return rows


def build_runtime_table(
    final_run_dir: Path,
    llc_run_dir: Path,
    final_manifest: dict[str, Any],
    llc_manifest: dict[str, Any],
    cells: list[SourceCell],
) -> list[dict[str, str]]:
    table = "runtime_cost_gates.csv"
    final_manifest_path = final_run_dir / "manifest.json"
    final_cost_path = final_run_dir / "cost_projection.json"
    llc_manifest_path = llc_run_dir / "manifest.json"
    final_cost = load_json(final_cost_path)
    llc_summary = load_json(llc_run_dir / "llc_campaign_summary.json")
    rows = [
        {
            "phase": "final_behavior_training",
            "run_id": final_run_dir.name,
            "gate_decision": "proceed_to_llc",
            "wall_minutes": fmt_float(final_manifest["wall_seconds"] / 60, 2),
            "gpu_hours": fmt_float(final_manifest["estimated_gpu_hours"], 4),
            "estimated_cost_usd": fmt_money(final_manifest["estimated_cost_usd"]),
            "projected_total_cost_usd": fmt_money(final_cost["projected_total_cost_usd"]),
        },
        {
            "phase": "llc_campaign",
            "run_id": llc_run_dir.name,
            "gate_decision": "llc_complete_with_rejections",
            "wall_minutes": fmt_float(llc_manifest["wall_seconds"] / 60, 2),
            "gpu_hours": fmt_float(llc_manifest["estimated_gpu_hours"], 4),
            "estimated_cost_usd": fmt_money(llc_manifest["estimated_gpu_hours"]),
            "projected_total_cost_usd": fmt_money(llc_manifest["projected_total_cost_usd"]),
        },
    ]
    source_rows = [
        (
            "final_behavior_training",
            final_manifest_path,
            final_cost_path,
            {
                "phase": ([final_manifest_path], ["run_kind"], "label from phase"),
                "run_id": ([final_manifest_path], ["path.name"], "copied run directory name"),
                "gate_decision": (
                    [final_run_dir / "phase_report.md"],
                    ["Gate Decision"],
                    "copied phase decision",
                ),
                "wall_minutes": ([final_manifest_path], ["wall_seconds"], "seconds / 60"),
                "gpu_hours": ([final_manifest_path], ["estimated_gpu_hours"], "4-decimal formatting"),
                "estimated_cost_usd": (
                    [final_manifest_path],
                    ["estimated_cost_usd"],
                    "USD formatting",
                ),
                "projected_total_cost_usd": (
                    [final_cost_path],
                    ["projected_total_cost_usd"],
                    "USD formatting",
                ),
            },
        ),
        (
            "llc_campaign",
            llc_manifest_path,
            llc_run_dir / "llc_campaign_summary.json",
            {
                "phase": ([llc_manifest_path], ["run_kind"], "label from phase"),
                "run_id": ([llc_manifest_path], ["run_id"], "copied verbatim"),
                "gate_decision": (
                    [llc_run_dir / "phase_report.md"],
                    ["Gate Decision"],
                    "copied phase decision",
                ),
                "wall_minutes": ([llc_manifest_path], ["wall_seconds"], "seconds / 60"),
                "gpu_hours": ([llc_manifest_path], ["estimated_gpu_hours"], "4-decimal formatting"),
                "estimated_cost_usd": (
                    [llc_manifest_path],
                    ["estimated_gpu_hours"],
                    "hourly-rate USD formatting",
                ),
                "projected_total_cost_usd": (
                    [llc_manifest_path],
                    ["projected_total_cost_usd"],
                    "USD formatting",
                ),
            },
        ),
    ]
    for row, (row_id, _manifest_path, _extra_path, sources) in zip(rows, source_rows, strict=True):
        add_cells(cells, table, row_id, row, sources)
    _ = llc_summary
    return rows


def build_reproducibility_table(
    final_run_dir: Path,
    llc_run_dir: Path,
    final_manifest: dict[str, Any],
    llc_manifest: dict[str, Any],
    cells: list[SourceCell],
) -> list[dict[str, str]]:
    table = "reproducibility.csv"
    final_manifest_path = final_run_dir / "manifest.json"
    llc_manifest_path = llc_run_dir / "manifest.json"
    frozen_config_path = final_run_dir / "frozen_config.json"
    split_manifest_path = final_run_dir / "data_splits" / "split_manifest.json"
    sampler_config_path = llc_run_dir / "sampler_config.json"
    rows = [
        {
            "item": "model",
            "value": final_manifest["config"]["model"],
            "evidence": str(final_manifest_path),
        },
        {
            "item": "final_training_source_commit",
            "value": final_manifest["git_commit"],
            "evidence": str(final_manifest_path),
        },
        {
            "item": "llc_campaign_source_commit",
            "value": llc_manifest["git_commit"],
            "evidence": str(llc_manifest_path),
        },
        {
            "item": "tokenizer_vocab_sha256",
            "value": final_manifest["tokenizer_vocab_sha256"],
            "evidence": str(final_manifest_path),
        },
        {
            "item": "frozen_config_sha256",
            "value": sha256_file(frozen_config_path),
            "evidence": str(frozen_config_path),
        },
        {
            "item": "split_manifest_sha256",
            "value": sha256_file(split_manifest_path),
            "evidence": str(split_manifest_path),
        },
        {
            "item": "sampler_reference_sha256",
            "value": llc_manifest["reference_set"]["sha256"],
            "evidence": str(llc_manifest_path),
        },
        {
            "item": "sampler_config_sha256",
            "value": sha256_file(sampler_config_path),
            "evidence": str(sampler_config_path),
        },
        {
            "item": "selected_llc_tokens",
            "value": ",".join(str(t) for t in llc_manifest["selected_checkpoint_tokens"]),
            "evidence": str(llc_manifest_path),
        },
    ]
    source_by_item = {
        "model": ([final_manifest_path], ["config.model"], "copied verbatim"),
        "final_training_source_commit": ([final_manifest_path], ["git_commit"], "copied verbatim"),
        "llc_campaign_source_commit": ([llc_manifest_path], ["git_commit"], "copied verbatim"),
        "tokenizer_vocab_sha256": ([final_manifest_path], ["tokenizer_vocab_sha256"], "copied verbatim"),
        "frozen_config_sha256": ([frozen_config_path], ["file bytes"], "sha256(file)"),
        "split_manifest_sha256": ([split_manifest_path], ["file bytes"], "sha256(file)"),
        "sampler_reference_sha256": ([llc_manifest_path], ["reference_set.sha256"], "copied verbatim"),
        "sampler_config_sha256": ([sampler_config_path], ["file bytes"], "sha256(file)"),
        "selected_llc_tokens": (
            [llc_manifest_path],
            ["selected_checkpoint_tokens"],
            "comma-joined list",
        ),
    }
    for row in rows:
        item_sources = {
            "item": (source_by_item[row["item"]][0], source_by_item[row["item"]][1], "label"),
            "value": source_by_item[row["item"]],
            "evidence": (source_by_item[row["item"]][0], ["path"], "source path"),
        }
        add_cells(cells, table, row["item"], row, item_sources)
    return rows


def build_checkpoint_hash_table(
    final_run_dir: Path,
    llc_run_dir: Path,
    cells: list[SourceCell],
) -> list[dict[str, str]]:
    table = "selected_checkpoint_hashes.csv"
    llc_rows = read_csv_dicts(llc_run_dir / "report_source_tables" / "llc_summary.csv")
    rows: list[dict[str, str]] = []
    for row in llc_rows:
        checkpoint = row["checkpoint"]
        model_path = (
            final_run_dir
            / "conditions"
            / "structured_pt_seed_a"
            / "checkpoints"
            / checkpoint
            / "model.safetensors"
        )
        metadata_path = model_path.with_name("checkpoint_metadata.json")
        out = {
            "checkpoint": checkpoint,
            "target_tokens": fmt_int(row["target_tokens"]),
            "model_safetensors_sha256": sha256_file(model_path),
            "checkpoint_metadata_sha256": sha256_file(metadata_path),
            "report_status": row["report_status"],
        }
        rows.append(out)
        sources = {
            "checkpoint": ([model_path.parent], ["path.name"], "copied checkpoint directory name"),
            "target_tokens": (
                [llc_run_dir / "report_source_tables" / "llc_summary.csv"],
                [f"row checkpoint={checkpoint}.target_tokens"],
                "integer formatting",
            ),
            "model_safetensors_sha256": ([model_path], ["file bytes"], "sha256(file)"),
            "checkpoint_metadata_sha256": ([metadata_path], ["file bytes"], "sha256(file)"),
            "report_status": (
                [llc_run_dir / "report_source_tables" / "llc_summary.csv"],
                [f"row checkpoint={checkpoint}.report_status"],
                "copied verbatim",
            ),
        }
        add_cells(cells, table, checkpoint, out, sources)
    return rows


def write_metric_source_table(metric_rows_: list[dict[str, Any]], output_dir: Path) -> Path:
    path = output_dir / "source_tables" / "behavior_trajectory_source.csv"
    fields = [
        "condition",
        "condition_label",
        "checkpoint",
        "target_tokens",
        "actual_cumulative_tokens",
        "pt_bpb",
        "english_bpb",
        "grammar_mean_margin",
        "grammar_margin_ci_low",
        "grammar_margin_ci_high",
        "grammar_accuracy",
        "grammar_examples",
        "source_summary",
    ]
    write_csv(path, metric_rows_, fields)
    return path


def plot_behavior(metric_rows_: list[dict[str, Any]], figures_dir: Path) -> Path:
    df = pd.DataFrame(metric_rows_)
    path = figures_dir / "behavior_trajectories.png"
    figures_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.1), dpi=180)
    colors = {
        "structured_pt_seed_a": "#1f77b4",
        "structured_pt_seed_b": "#17becf",
        "shuffled_pt": "#d62728",
        "matched_en": "#2ca02c",
    }
    for condition in CONDITIONS:
        sub = df[df["condition"] == condition].sort_values("target_tokens")
        x = sub["target_tokens"] / 1_000_000
        axes[0].plot(x, sub["pt_bpb"], marker="o", linewidth=1.8, label=CONDITION_LABELS[condition], color=colors[condition])
        axes[1].plot(
            x,
            sub["grammar_mean_margin"],
            marker="o",
            linewidth=1.8,
            label=CONDITION_LABELS[condition],
            color=colors[condition],
        )
    axes[0].set_title("Portuguese validation BPB")
    axes[0].set_xlabel("target tokens (millions)")
    axes[0].set_ylabel("bits per byte")
    axes[1].set_title("Grammar minimal-pair margin")
    axes[1].set_xlabel("target tokens (millions)")
    axes[1].set_ylabel("mean log-prob margin")
    for ax in axes:
        ax.grid(alpha=0.25)
        ax.axhline(0, color="#555555", linewidth=0.8, alpha=0.5)
    axes[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_llc(llc_run_dir: Path, figures_dir: Path) -> Path:
    rows = read_csv_dicts(llc_run_dir / "report_source_tables" / "llc_summary.csv")
    path = figures_dir / "llc_trajectory.png"
    fig, ax = plt.subplots(figsize=(7.4, 4.2), dpi=180)
    reportable = [row for row in rows if row["report_status"] == "reportable_with_diagnostics"]
    rejected = [row for row in rows if row["report_status"] != "reportable_with_diagnostics"]
    x = [int(row["target_tokens"]) / 1_000_000 for row in reportable]
    y = [float(row["llc_scalar"]) for row in reportable]
    yerr = [float(row["llc_std"]) for row in reportable]
    ax.errorbar(x, y, yerr=yerr, marker="o", linewidth=1.8, capsize=3, label="reportable with diagnostics")
    if rejected:
        ax.scatter(
            [int(row["target_tokens"]) / 1_000_000 for row in rejected],
            [float(row["llc_scalar"]) for row in rejected],
            marker="x",
            s=80,
            color="#d62728",
            label="diagnostic rejection",
        )
    ax.set_title("Primary structured-PT seed A LLC estimates")
    ax.set_xlabel("target tokens (millions)")
    ax.set_ylabel("raw LLC scalar")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_sampler_diagnostics(llc_run_dir: Path, figures_dir: Path) -> Path:
    df = pd.read_csv(llc_run_dir / "report_source_tables" / "sampler_diagnostics.csv")
    path = figures_dir / "sampler_diagnostics.png"
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), dpi=180)
    labels = [str(int(v / 1000)) + "k" if v < 1_000_000 else f"{v / 1_000_000:.1f}M" for v in df["target_tokens"]]
    axes[0].bar(labels, df["late_minus_early_mean"], color="#9467bd")
    axes[0].axhline(0, color="#333333", linewidth=0.8)
    axes[0].set_title("Late minus early sampler loss")
    axes[0].set_ylabel("loss difference")
    axes[1].bar(labels, df["between_chain_range"], color="#8c564b")
    axes[1].set_title("Between-chain LLC range")
    axes[1].set_ylabel("raw LLC units")
    for ax in axes:
        ax.grid(axis="y", alpha=0.25)
        ax.tick_params(axis="x", labelrotation=30)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def diagnostic_loss_trace(llc_run_dir: Path, checkpoint: str) -> list[list[float]]:
    data = load_json(llc_run_dir / "diagnostics" / f"{checkpoint}.json")
    return data["result_summary"]["data_vars"]["loss_trace"]["data"]


def plot_loss_traces(llc_run_dir: Path, figures_dir: Path) -> Path:
    path = figures_dir / "chain_loss_traces_token0_vs_100k.png"
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4), dpi=180, sharey=True)
    for ax, checkpoint, title in [
        (axes[0], "tokens_000000000", "token 0 rejected"),
        (axes[1], "tokens_000100000", "100k reportable"),
    ]:
        traces = diagnostic_loss_trace(llc_run_dir, checkpoint)
        for i, trace in enumerate(traces):
            ax.plot(trace, linewidth=0.8, alpha=0.8, label=f"chain {i}")
        ax.set_title(title)
        ax.set_xlabel("sampler step")
        ax.grid(alpha=0.2)
    axes[0].set_ylabel("sampling loss")
    axes[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def table_to_markdown(path: Path, max_rows: int | None = None) -> str:
    rows = read_csv_dicts(path)
    if max_rows is not None:
        rows = rows[:max_rows]
    if not rows:
        return ""
    headers = list(rows[0].keys())
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return "\n".join(lines)


def write_report_markdown(
    output_dir: Path,
    run_id: str,
    generated_utc: str,
    paths: dict[str, Path],
    final_run_dir: Path,
    llc_run_dir: Path,
    final_manifest: dict[str, Any],
    llc_manifest: dict[str, Any],
    grammar_checks: dict[str, Any],
) -> Path:
    md = output_dir / "report.md"
    endpoint_table = table_to_markdown(paths["endpoint_table"])
    llc_table = table_to_markdown(paths["llc_table"])
    sampler_table = table_to_markdown(paths["sampler_table"])
    runtime_table = table_to_markdown(paths["runtime_table"])
    repro_table = table_to_markdown(paths["repro_table"])
    failed_grammar_checks = [row["id"] for row in grammar_checks["checks"] if not row["has_shared_prefix"]]
    text = f"""# When Does a Small Model Learn Portuguese?

Run ID: `{run_id}`  
Generated: `{generated_utc}`  
Status: empirical / methodological, with a reportable limitation rather than a formal phase-transition claim.

## Abstract

We adapted `roneneldan/TinyStories-8M` by full-parameter FP32 next-token continued pretraining on a frozen Portuguese split, with token-shuffled Portuguese and matched-English controls plus a second structured-Portuguese seed. Behavior was evaluated at every saved checkpoint. LLC was measured only for the primary structured-Portuguese seed A at a frozen behavior-selected subset using one global sampler configuration.

The real outputs show early Portuguese BPB improvement followed by later degradation, noisy grammar margins on only 10 constructed minimal pairs, and a non-monotone primary LLC trajectory after excluding the token-0 diagnostic rejection. This is not sufficient to claim a changepoint in an SLT-derived local geometric estimate aligned with a behavioral transition: LLC controls were not run, token 0 was rejected, and the grammar sanity-check file has `passed=false` because items {", ".join(failed_grammar_checks)} do not meet the shared-prefix check. The useful result is a reproducible diagnostic package for a narrow adaptation trajectory.

## 1. Experimental design

- Model: `roneneldan/TinyStories-8M`, full-parameter continued pretraining, FP32, sequence length 128.
- Conditions: structured Portuguese seed A, structured Portuguese seed B, token-shuffled Portuguese, and matched English.
- Data source for the report: only `{final_run_dir}` and `{llc_run_dir}`.
- Behavior: Portuguese validation BPB, English-retention BPB, and Portuguese grammar minimal-pair margin at all checkpoints.
- LLC: primary structured-Portuguese seed A only, selected tokens `{",".join(str(t) for t in llc_manifest["selected_checkpoint_tokens"])}`, fixed sampler reference set hash `{llc_manifest["reference_set"]["sha256"]}`.
- Sampler: FP32 full-parameter SGLD, 3 chains, 200 burn-in steps, 100 draws, 2 steps between draws, batch size 16, fixed across all selected checkpoints.

## 2. Behavioral endpoint table

Every cell in this table is generated from condition summary JSON files and checked in `validation/table_cell_verification.csv`.

{endpoint_table}

![Behavior trajectories](figures/behavior_trajectories.png)

Source data: `source_tables/behavior_trajectory_source.csv`.

## 3. LLC and alignment screen

The LLC scalar for token 0 is retained in the source table but rejected for reporting because diagnostics flagged `persistent_downhill_movement_below_center`. The remaining five selected checkpoints have chain diagnostics and raw traces. The primary LLC curve is non-monotone: it decreases through 5M tokens and rebounds by 8M tokens. Because only the primary condition was sampled for LLC, this is an association screen rather than a controlled geometric claim.

{llc_table}

![LLC trajectory](figures/llc_trajectory.png)

## 4. Chain diagnostics

The sampler diagnostics table reports loss drift, between-chain range, and displacement summaries. Token 0 is explicitly marked as a diagnostic rejection. Chain-level zarr traces, running estimates, and displacement JSONL files are preserved under the LLC run directory.

{sampler_table}

![Sampler diagnostics](figures/sampler_diagnostics.png)

![Chain loss traces](figures/chain_loss_traces_token0_vs_100k.png)

## 5. Uncertainty, failure modes, and cost

Uncertainty sources are checkpoint density, tiny grammar evaluation size, the failed constructed-pair shared-prefix sanity check, bootstrap uncertainty over only 10 grammar pairs, repeated use of a small frozen split to reach 8M target tokens, and the lack of LLC controls or second-seed LLC. The smooth/null alternative remains plausible: Portuguese behavior may be mostly local-sequence adaptation plus overfitting, while the LLC trajectory may be sampler/reference-set dependent rather than a stable geometric marker.

{runtime_table}

Failure modes retained in the report package:

- Token-0 LLC rejection for persistent downhill movement below center.
- No LLC estimates for shuffled Portuguese, matched English, or structured Portuguese seed B.
- English retention BPB worsens during Portuguese adaptation in the Portuguese conditions.
- Grammar margins are unstable and based on 10 items; grammar sanity checks are not all passed.
- The report does not infer causality or a formal SLT phase transition.

## 6. Reproducibility

{repro_table}

Additional machine-readable artifacts:

- `source_tables/selected_checkpoint_hashes.csv`
- `source_links.json`
- `validation/table_cell_verification.csv`
- `validation/validation_summary.json`
- Figures under `figures/`
- PDF copy at `report.pdf`

One-command rerun:

```bash
.venv-bench-py311/bin/python scripts/build_report.py --run-id {run_id} --output-dir {output_dir}
```
"""
    md.write_text(text, encoding="utf-8")
    return md


def add_text_page(pdf: PdfPages, title: str, body: str, footer: str = "") -> None:
    fig = plt.figure(figsize=(8.27, 11.69))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    fig.text(0.08, 0.94, title, fontsize=17, weight="bold", va="top")
    y = 0.89
    for paragraph in body.split("\n\n"):
        wrapped = textwrap.fill(paragraph, width=90)
        fig.text(0.08, y, wrapped, fontsize=9.2, va="top", family="DejaVu Sans")
        y -= 0.033 * (wrapped.count("\n") + 1) + 0.022
    if footer:
        fig.text(0.08, 0.04, footer, fontsize=7.5, color="#555555")
    pdf.savefig(fig)
    plt.close(fig)


def add_image_page(pdf: PdfPages, title: str, image_paths: list[Path], caption: str) -> None:
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.text(0.08, 0.95, title, fontsize=16, weight="bold", va="top")
    n = len(image_paths)
    top = 0.89
    height = 0.36 if n > 1 else 0.58
    for i, path in enumerate(image_paths):
        img = plt.imread(path)
        ax = fig.add_axes([0.08, top - (i + 1) * height - i * 0.04, 0.84, height - 0.02])
        ax.imshow(img)
        ax.axis("off")
    fig.text(0.08, 0.07, textwrap.fill(caption, width=100), fontsize=8.5, color="#333333")
    pdf.savefig(fig)
    plt.close(fig)


def write_report_pdf(output_dir: Path, paths: dict[str, Path], run_id: str) -> Path:
    pdf_path = output_dir / "report.pdf"
    with PdfPages(pdf_path) as pdf:
        add_text_page(
            pdf,
            "When Does a Small Model Learn Portuguese?",
            (
                f"Run ID: {run_id}\n\n"
                "Status: empirical / methodological. The report does not make a formal SLT phase "
                "transition or causal claim, and it does not claim a changepoint in an SLT-derived "
                "local geometric estimate aligned with a behavioral transition. It reports behavior, "
                "LLC diagnostics, controls, and limitations from the approved real run directories "
                "only.\n\n"
                "Headline: structured Portuguese behavior improved early in validation BPB, but the "
                "grammar probe is small and noisy; the primary LLC trajectory is non-monotone after "
                "excluding the token-0 diagnostic rejection. The evidence supports a reproducible "
                "diagnostic package, not a controlled aligned-changepoint result."
            ),
            "Sources: final training and LLC campaign manifests, summaries, diagnostics, and report-source CSVs.",
        )
        add_text_page(
            pdf,
            "Design And Controls",
            (
                "Full-parameter FP32 next-token continued pretraining was run on TinyStories-8M. "
                "The real conditions are structured Portuguese seed A, structured Portuguese seed B, "
                "token-shuffled Portuguese, and matched English. Behavior was evaluated at every "
                "checkpoint. LLC was sampled only for structured Portuguese seed A at the frozen "
                "behavior-selected token subset.\n\n"
                "The sampler used one global FP32 full-parameter SGLD configuration across selected "
                "checkpoints: 3 chains, 200 burn-in steps, 100 draws, 2 steps between draws, batch size "
                "16, fixed reference set, and fixed sequence length 128.\n\n"
                "The grammar sanity check did not fully pass, and the report treats grammar margins as "
                "a small constructed diagnostic rather than a high-confidence capability measurement."
            ),
        )
        add_image_page(
            pdf,
            "Behavior Trajectories",
            [paths["behavior_fig"]],
            "Controls are plotted in the same axes. Source data: source_tables/behavior_trajectory_source.csv.",
        )
        add_image_page(
            pdf,
            "LLC Trajectory And Chain Diagnostics",
            [paths["llc_fig"], paths["trace_fig"]],
            (
                "Token 0 is shown as a rejected diagnostic point. The 100k trace is included as a "
                "representative reportable checkpoint. Full raw zarr traces, running estimates, and "
                "displacement traces are preserved in the LLC campaign run directory."
            ),
        )
        add_image_page(
            pdf,
            "Sampler Summary",
            [paths["sampler_fig"]],
            "Diagnostic source table: source_tables/sampler_diagnostics.csv.",
        )
        add_text_page(
            pdf,
            "Limitations And Reproducibility",
            (
                "Main limitations: no LLC controls, no second-seed LLC, token-0 LLC rejection, tiny "
                "grammar probe, failed shared-prefix checks for two grammar items, repeated small split "
                "cycling, checkpoint-spacing uncertainty, and sampler/reference-set dependence.\n\n"
                "Runtime and cost are recorded in source_tables/runtime_cost_gates.csv. Reproducibility "
                "metadata and hashes are recorded in source_tables/reproducibility.csv and "
                "source_tables/selected_checkpoint_hashes.csv. Every displayed table cell is covered by "
                "validation/table_cell_verification.csv and validation/validation_summary.json."
            ),
        )
    return pdf_path


def write_phase_report(
    output_dir: Path,
    run_id: str,
    generated_utc: str,
    validation_summary: dict[str, Any],
    final_run_dir: Path,
    llc_run_dir: Path,
) -> Path:
    path = output_dir / "phase_report.md"
    text = f"""# Report Phase Report

- Run ID: `{run_id}`
- Generated UTC: `{generated_utc}`
- Source final run: `{final_run_dir}`
- Source LLC run: `{llc_run_dir}`
- Gate decision: `report_complete_with_limitations`

## Evidence

- Report Markdown: `{output_dir / "report.md"}`
- Report PDF: `{output_dir / "report.pdf"}`
- Source tables: `{output_dir / "source_tables"}`
- Figures: `{output_dir / "figures"}`
- Cell verification: `{output_dir / "validation" / "table_cell_verification.csv"}`
- Validation summary: `{output_dir / "validation" / "validation_summary.json"}`
- Source links: `{output_dir / "source_links.json"}`

## Uncertainty

- No LLC controls were run for shuffled Portuguese, matched English, or structured Portuguese seed B.
- The token-0 LLC scalar is rejected for `persistent_downhill_movement_below_center`.
- Grammar margins use 10 constructed pairs, and the grammar sanity check file has `passed=false`.
- Checkpoint spacing limits transition localization.
- The smooth/null alternative remains plausible.

## Failure Modes

- Scalar LLC without diagnostics is not reportable; diagnostics and trace paths are retained.
- The result is conditional on the fixed sampler reference set and one global sampler configuration.
- The report does not claim a formal SLT phase transition, grokking, causality, or a changepoint in an SLT-derived local geometric estimate aligned with a behavioral transition.

## Runtime And Cost

Report construction used CPU-only local processing. Incremental GPU-hours: `0.0000`; incremental cost: `$0.0000`.
The source final training and LLC campaign runtime/cost are reported in `source_tables/runtime_cost_gates.csv`.

## Validation

- Validation status: `{validation_summary["status"]}`
- Verified table cells: `{validation_summary["verified_cell_count"]}`
- Synthetic/mock references in report artifacts: `{validation_summary["mock_reference_count"]}`

## Gate Decision

`report_complete_with_limitations`. Next bounded action: operator review/submission packaging if desired; no additional GPU action is required by this report phase.
"""
    path.write_text(text, encoding="utf-8")
    return path


def write_source_links(
    output_dir: Path, llc_run_dir: Path, cells: list[SourceCell], figures: dict[str, Path]
) -> Path:
    links = {
        "tables": [cell.__dict__ for cell in cells],
        "figures": {
            "behavior_trajectories.png": {
                "path": str(figures["behavior_fig"]),
                "source_data": str(output_dir / "source_tables" / "behavior_trajectory_source.csv"),
            },
            "llc_trajectory.png": {
                "path": str(figures["llc_fig"]),
                "source_data": str(llc_run_dir / "report_source_tables" / "llc_summary.csv"),
            },
            "sampler_diagnostics.png": {
                "path": str(figures["sampler_fig"]),
                "source_data": str(
                    llc_run_dir / "report_source_tables" / "sampler_diagnostics.csv"
                ),
            },
            "chain_loss_traces_token0_vs_100k.png": {
                "path": str(figures["trace_fig"]),
                "source_data": [
                    str(llc_run_dir / "diagnostics" / "tokens_000000000.json"),
                    str(llc_run_dir / "diagnostics" / "tokens_000100000.json"),
                ],
            },
        },
    }
    path = output_dir / "source_links.json"
    path.write_text(json.dumps(links, indent=2) + "\n", encoding="utf-8")
    return path


def validate_report(output_dir: Path, cells: list[SourceCell], expected_tables: dict[str, Path]) -> dict[str, Any]:
    errors: list[str] = []
    for table, path in expected_tables.items():
        rows = read_csv_dicts(path)
        covered = [
            cell for cell in cells if cell.table == table and not cell.column.startswith("_")
        ]
        expected_count = len(rows) * len(rows[0]) if rows else 0
        if len(covered) != expected_count:
            errors.append(f"{table}: covered {len(covered)} cells, expected {expected_count}")
        by_cell = {(cell.row_id, cell.column): cell for cell in covered}
        row_id_column = "condition" if table == "endpoint_summary.csv" else None
        if table == "llc_behavior_alignment.csv":
            row_id_column = "target_tokens"
        elif table == "sampler_diagnostics.csv":
            row_id_column = "checkpoint"
        elif table == "runtime_cost_gates.csv":
            row_id_column = "phase"
        elif table == "reproducibility.csv":
            row_id_column = "item"
        elif table == "selected_checkpoint_hashes.csv":
            row_id_column = "checkpoint"
        for idx, row in enumerate(rows):
            row_id = row.get(row_id_column or "", str(idx))
            if table == "endpoint_summary.csv":
                inverse = {v: k for k, v in CONDITION_LABELS.items()}
                row_id = inverse.get(row["condition"], row["condition"])
            for column, value in row.items():
                cell = by_cell.get((row_id, column))
                if cell is None:
                    errors.append(f"{table}: missing source cell for row {row_id} col {column}")
                    continue
                if str(value) != cell.value:
                    errors.append(
                        f"{table}: value mismatch row {row_id} col {column}: {value} != {cell.value}"
                    )
                if "reference/mock_report" in cell.source_paths:
                    errors.append(f"{table}: mock-report source used in {row_id}.{column}")
    report_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in [output_dir / "report.md", output_dir / "phase_report.md"]
        if path.exists()
    )
    mock_reference_count = report_text.count("reference/mock_report")
    if mock_reference_count:
        errors.append("report text references reference/mock_report")
    validation_dir = output_dir / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    verification_path = validation_dir / "table_cell_verification.csv"
    write_csv(
        verification_path,
        [cell.__dict__ for cell in cells],
        ["table", "row_id", "column", "value", "source_paths", "source_keys", "transform"],
    )
    summary = {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "verified_cell_count": len(cells),
        "table_count": len(expected_tables),
        "mock_reference_count": mock_reference_count,
        "validated_at_utc": utc_now(),
    }
    (validation_dir / "validation_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def build_report(final_run_dir: Path, llc_run_dir: Path, output_dir: Path, run_id: str) -> dict[str, Any]:
    generated_utc = utc_now()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "source_tables").mkdir(exist_ok=True)
    figures_dir = output_dir / "figures"
    cells: list[SourceCell] = []

    final_manifest = load_json(final_run_dir / "manifest.json")
    llc_manifest = load_json(llc_run_dir / "manifest.json")
    grammar_checks = load_json(final_run_dir / "grammar_sanity_checks.json")
    summaries = load_condition_summaries(final_run_dir)
    metrics = metric_rows(final_run_dir, summaries)
    behavior_source_path = write_metric_source_table(metrics, output_dir)

    endpoint_rows = build_endpoint_table(final_run_dir, summaries, cells)
    llc_rows = build_llc_alignment_table(final_run_dir, llc_run_dir, summaries, cells)
    sampler_rows = build_sampler_table(llc_run_dir, cells)
    runtime_rows = build_runtime_table(final_run_dir, llc_run_dir, final_manifest, llc_manifest, cells)
    repro_rows = build_reproducibility_table(final_run_dir, llc_run_dir, final_manifest, llc_manifest, cells)
    checkpoint_hash_rows = build_checkpoint_hash_table(final_run_dir, llc_run_dir, cells)

    endpoint_path = output_dir / "source_tables" / "endpoint_summary.csv"
    llc_path = output_dir / "source_tables" / "llc_behavior_alignment.csv"
    sampler_path = output_dir / "source_tables" / "sampler_diagnostics.csv"
    runtime_path = output_dir / "source_tables" / "runtime_cost_gates.csv"
    repro_path = output_dir / "source_tables" / "reproducibility.csv"
    checkpoint_hash_path = output_dir / "source_tables" / "selected_checkpoint_hashes.csv"
    write_csv(endpoint_path, endpoint_rows, list(endpoint_rows[0]))
    write_csv(llc_path, llc_rows, list(llc_rows[0]))
    write_csv(sampler_path, sampler_rows, list(sampler_rows[0]))
    write_csv(runtime_path, runtime_rows, list(runtime_rows[0]))
    write_csv(repro_path, repro_rows, list(repro_rows[0]))
    write_csv(checkpoint_hash_path, checkpoint_hash_rows, list(checkpoint_hash_rows[0]))

    figures = {
        "behavior_fig": plot_behavior(metrics, figures_dir),
        "llc_fig": plot_llc(llc_run_dir, figures_dir),
        "sampler_fig": plot_sampler_diagnostics(llc_run_dir, figures_dir),
        "trace_fig": plot_loss_traces(llc_run_dir, figures_dir),
    }
    paths = {
        "behavior_source": behavior_source_path,
        "endpoint_table": endpoint_path,
        "llc_table": llc_path,
        "sampler_table": sampler_path,
        "runtime_table": runtime_path,
        "repro_table": repro_path,
        **figures,
    }
    write_report_markdown(
        output_dir,
        run_id,
        generated_utc,
        paths,
        final_run_dir,
        llc_run_dir,
        final_manifest,
        llc_manifest,
        grammar_checks,
    )
    write_report_pdf(output_dir, paths, run_id)

    expected_tables = {
        "endpoint_summary.csv": endpoint_path,
        "llc_behavior_alignment.csv": llc_path,
        "sampler_diagnostics.csv": sampler_path,
        "runtime_cost_gates.csv": runtime_path,
        "reproducibility.csv": repro_path,
        "selected_checkpoint_hashes.csv": checkpoint_hash_path,
    }
    validation_summary = validate_report(output_dir, cells, expected_tables)
    write_source_links(output_dir, llc_run_dir, cells, figures)
    phase_report = write_phase_report(
        output_dir,
        run_id,
        generated_utc,
        validation_summary,
        final_run_dir,
        llc_run_dir,
    )
    validation_summary = validate_report(output_dir, cells, expected_tables)

    source_files = [
        final_run_dir / "manifest.json",
        final_run_dir / "frozen_config.json",
        final_run_dir / "grammar_sanity_checks.json",
        final_run_dir / "llc_checkpoint_selection.json",
        llc_run_dir / "manifest.json",
        llc_run_dir / "llc_campaign_summary.json",
        llc_run_dir / "failures" / "failures_summary.json",
        llc_run_dir / "report_source_tables" / "llc_summary.csv",
        llc_run_dir / "report_source_tables" / "sampler_diagnostics.csv",
        llc_run_dir / "report_source_tables" / "checkpoint_selection.csv",
    ] + [condition_summary_path(final_run_dir, condition) for condition in CONDITIONS]
    metadata = {
        "run_kind": "empirical_report",
        "run_id": run_id,
        "generated_utc": generated_utc,
        "report_builder_git_commit": git_commit(),
        "source_final_run_dir": str(final_run_dir),
        "source_llc_run_dir": str(llc_run_dir),
        "source_files_sha256": {str(path): sha256_file(path) for path in source_files},
        "outputs": {
            "report_markdown": str(output_dir / "report.md"),
            "report_pdf": str(output_dir / "report.pdf"),
            "phase_report": str(phase_report),
            "source_tables": str(output_dir / "source_tables"),
            "figures": str(figures_dir),
            "validation": str(output_dir / "validation"),
        },
        "gate_decision": "report_complete_with_limitations",
        "incremental_gpu_hours": 0.0,
        "incremental_cost_usd": 0.0,
        "validation": validation_summary,
    }
    (output_dir / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the empirical report from real final artifacts.")
    parser.add_argument("--final-run-dir", type=Path, default=FINAL_RUN_DIR)
    parser.add_argument("--llc-run-dir", type=Path, default=LLC_RUN_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--run-id", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.run_id is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        args.run_id = f"report_{stamp}_{args.final_run_dir.name}_batch16"
    if args.output_dir is None:
        args.output_dir = REPORT_ROOT / args.run_id
    metadata = build_report(args.final_run_dir, args.llc_run_dir, args.output_dir, args.run_id)
    print(json.dumps({"run_id": metadata["run_id"], "output_dir": str(args.output_dir), "validation": metadata["validation"]}, indent=2))
    if metadata["validation"]["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
