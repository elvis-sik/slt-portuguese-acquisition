from __future__ import annotations

import argparse
import csv
import json
import math
import random
import shutil
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.final_training import load_jsonl
from scripts.scientific_pilot import (
    collate_batch,
    evaluate_all,
    git_commit,
    git_status_short,
    hash_tree,
    load_grammar_pairs,
    package_versions,
    path_size_bytes,
    save_checkpoint,
    sha256_file,
    stable_json_hash,
    utc_now,
    write_json,
    write_jsonl,
)


CONDITIONS = ("structured_pt", "shuffled_pt")
CONDITION_SEED_OFFSETS = {"structured_pt": 101, "shuffled_pt": 202}
DEFAULT_VALIDATION = Path("results/01_scientific_pilot/scientific_pilot_20260620T053047Z/data_splits/validation.jsonl")
DEFAULT_GRAMMAR = Path("data/eval/grammar_minimal_pairs.example.csv")


@dataclass(frozen=True)
class RecipeConfig:
    model: str
    sequence_length: int
    batch_size: int
    target_tokens: int
    checkpoint_tokens: tuple[int, ...]
    learning_rate: float
    warmup_fraction: float
    lr_schedule: str
    grad_clip: float
    weight_decay: float
    seed: int
    device: str
    hourly_rate_usd: float
    validation_jsonl: Path
    grammar_csv: Path
    local_files_only: bool
    train_corpus: str
    train_corpus_config: str
    max_docs: int

    @property
    def tokens_per_step(self) -> int:
        return self.sequence_length * self.batch_size

    @property
    def target_steps(self) -> int:
        return math.ceil(self.target_tokens / self.tokens_per_step)

    @property
    def actual_target_tokens(self) -> int:
        return self.target_steps * self.tokens_per_step

    @property
    def train_chunks_needed(self) -> int:
        return self.target_steps * self.batch_size

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "sequence_length": self.sequence_length,
            "batch_size": self.batch_size,
            "tokens_per_step": self.tokens_per_step,
            "target_tokens": self.target_tokens,
            "target_steps": self.target_steps,
            "actual_target_tokens": self.actual_target_tokens,
            "train_chunks_needed": self.train_chunks_needed,
            "checkpoint_tokens": list(self.checkpoint_tokens),
            "learning_rate": self.learning_rate,
            "warmup_fraction": self.warmup_fraction,
            "lr_schedule": self.lr_schedule,
            "grad_clip": self.grad_clip,
            "weight_decay": self.weight_decay,
            "optimizer": "AdamW",
            "training_precision": "fp32",
            "seed": self.seed,
            "device": self.device,
            "hourly_rate_usd": self.hourly_rate_usd,
            "validation_jsonl": str(self.validation_jsonl),
            "grammar_csv": str(self.grammar_csv),
            "local_files_only": self.local_files_only,
            "train_corpus": self.train_corpus,
            "train_corpus_config": self.train_corpus_config,
            "max_docs": self.max_docs,
            "conditions": list(CONDITIONS),
        }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def checkpoint_plan(cfg: RecipeConfig) -> list[dict[str, int]]:
    tokens = sorted({0, *cfg.checkpoint_tokens, cfg.target_tokens})
    plan = []
    for target in tokens:
        step = 0 if target == 0 else min(cfg.target_steps, math.ceil(target / cfg.tokens_per_step))
        plan.append(
            {
                "target_tokens": int(target),
                "optimizer_step": int(step),
                "actual_cumulative_tokens": int(step * cfg.tokens_per_step),
            }
        )
    return plan


def checkpoint_name(target_tokens: int) -> str:
    return f"tokens_{target_tokens:09d}"


def normalize_text(text: str) -> str:
    return " ".join(str(text).replace("\u00a0", " ").split())


def stream_portuguese_documents(cfg: RecipeConfig) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from datasets import load_dataset

    stream = load_dataset(cfg.train_corpus, cfg.train_corpus_config, split="train", streaming=True)
    docs: list[dict[str, Any]] = []
    counts = {"seen": 0, "accepted": 0, "too_short": 0, "empty": 0}
    for ex in stream:
        counts["seen"] += 1
        text = normalize_text(str(ex.get("text", "")))
        if not text:
            counts["empty"] += 1
            continue
        if len(text) < 200:
            counts["too_short"] += 1
            continue
        docs.append(
            {
                "id": str(ex.get("id", f"doc_{counts['seen']:09d}")),
                "title": str(ex.get("title", "")),
                "url": str(ex.get("url", "")),
                "text": text,
                "text_sha256": stable_json_hash(text),
            }
        )
        counts["accepted"] += 1
        if len(docs) >= cfg.max_docs:
            break
    metadata = {
        "source": cfg.train_corpus,
        "config": cfg.train_corpus_config,
        "split": "train",
        "streaming": True,
        "counts": counts,
    }
    return docs, metadata


def make_chunks(tokenizer: Any, docs: list[dict[str, Any]], cfg: RecipeConfig) -> tuple[list[list[int]], list[dict[str, Any]]]:
    chunks: list[list[int]] = []
    records: list[dict[str, Any]] = []
    eos = tokenizer.eos_token_id
    if eos is None:
        eos = tokenizer.pad_token_id
    for doc in docs:
        ids = tokenizer(doc["text"], add_special_tokens=False)["input_ids"]
        if eos is not None:
            ids.append(int(eos))
        start_chunks = len(chunks)
        for start in range(0, len(ids) - cfg.sequence_length + 1, cfg.sequence_length):
            chunk = [int(x) for x in ids[start : start + cfg.sequence_length]]
            if len(chunk) == cfg.sequence_length:
                chunks.append(chunk)
                records.append(
                    {
                        "chunk_id": f"chunk_{len(chunks) - 1:09d}",
                        "doc_id": doc["id"],
                        "doc_title": doc["title"],
                        "token_start": start,
                        "token_count": len(chunk),
                        "input_ids_sha256": stable_json_hash(chunk),
                    }
                )
            if len(chunks) >= cfg.train_chunks_needed:
                return chunks, records
        doc["chunks_used"] = len(chunks) - start_chunks
    return chunks, records


def shuffled_chunks(chunks: list[list[int]], seed: int) -> list[list[int]]:
    rng = random.Random(seed)
    out: list[list[int]] = []
    for chunk in chunks:
        local = list(chunk)
        rng.shuffle(local)
        out.append(local)
    return out


def write_chunk_jsonl(path: Path, chunks: list[list[int]], records: list[dict[str, Any]]) -> None:
    rows = []
    for chunk, record in zip(chunks, records):
        rows.append({**record, "input_ids": chunk})
    write_jsonl(path, rows)


def prepare_data(output_dir: Path, tokenizer: Any, cfg: RecipeConfig) -> dict[str, Any]:
    split_dir = output_dir / "data_splits"
    split_dir.mkdir(parents=True, exist_ok=True)
    validation_rows = load_jsonl(cfg.validation_jsonl)
    write_jsonl(split_dir / "validation.jsonl", validation_rows)
    docs, corpus_metadata = stream_portuguese_documents(cfg)
    chunks, records = make_chunks(tokenizer, docs, cfg)
    if len(chunks) < cfg.train_chunks_needed:
        raise RuntimeError(
            f"Corpus produced {len(chunks)} chunks, need {cfg.train_chunks_needed}; increase max docs or change corpus."
        )
    chunks = chunks[: cfg.train_chunks_needed]
    records = records[: cfg.train_chunks_needed]
    shuffled = shuffled_chunks(chunks, cfg.seed + CONDITION_SEED_OFFSETS["shuffled_pt"])
    write_chunk_jsonl(split_dir / "train_structured_pt_token_ids.jsonl", chunks, records)
    write_chunk_jsonl(split_dir / "train_shuffled_pt_token_ids.jsonl", shuffled, records)
    doc_records = [
        {k: v for k, v in doc.items() if k != "text"}
        for doc in docs
    ]
    write_jsonl(split_dir / "train_documents_manifest.jsonl", doc_records)
    split_hashes = {
        "validation.jsonl": sha256_file(split_dir / "validation.jsonl"),
        "train_structured_pt_token_ids.jsonl": sha256_file(split_dir / "train_structured_pt_token_ids.jsonl"),
        "train_shuffled_pt_token_ids.jsonl": sha256_file(split_dir / "train_shuffled_pt_token_ids.jsonl"),
        "train_documents_manifest.jsonl": sha256_file(split_dir / "train_documents_manifest.jsonl"),
    }
    manifest = {
        "created_utc": utc_now(),
        "immutability_note": "Recipe-search data artifacts are per-attempt, content-addressed, and must not be overwritten.",
        "fixed_validation_source": str(cfg.validation_jsonl),
        "fixed_validation_source_sha256": sha256_file(cfg.validation_jsonl),
        "grammar_csv": str(cfg.grammar_csv),
        "grammar_csv_sha256": sha256_file(cfg.grammar_csv),
        "training_corpus": corpus_metadata,
        "split_sizes": {
            "validation": len(validation_rows),
            "train_chunks": len(chunks),
            "train_tokens": len(chunks) * cfg.sequence_length,
            "documents_used": len(docs),
        },
        "split_hashes_sha256": split_hashes,
        "tokenizer_vocab_sha256": stable_json_hash(tokenizer.get_vocab()),
    }
    write_json(split_dir / "split_manifest.json", manifest)
    return {
        "manifest": manifest,
        "splits": {"validation": validation_rows},
        "structured_chunks": chunks,
        "shuffled_chunks": shuffled,
    }


def load_prepared_data(output_dir: Path) -> dict[str, Any]:
    split_dir = output_dir / "data_splits"
    manifest = load_json(split_dir / "split_manifest.json")
    for filename, expected in manifest["split_hashes_sha256"].items():
        actual = sha256_file(split_dir / filename)
        if actual != expected:
            raise RuntimeError(f"Prepared data hash mismatch for {filename}: {actual} != {expected}")

    def read_chunks(path: Path) -> list[list[int]]:
        return [[int(x) for x in row["input_ids"]] for row in load_jsonl(path)]

    return {
        "manifest": manifest,
        "splits": {"validation": load_jsonl(split_dir / "validation.jsonl")},
        "structured_chunks": read_chunks(split_dir / "train_structured_pt_token_ids.jsonl"),
        "shuffled_chunks": read_chunks(split_dir / "train_shuffled_pt_token_ids.jsonl"),
    }


def make_model_optimizer_scheduler(cfg: RecipeConfig, total_steps: int) -> tuple[Any, Any, Any]:
    import torch
    from transformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(cfg.model, local_files_only=cfg.local_files_only)
    model = model.to(cfg.device).float().train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg.learning_rate, weight_decay=cfg.weight_decay)
    warmup_steps = int(round(total_steps * cfg.warmup_fraction))

    def lr_lambda(step: int) -> float:
        if warmup_steps > 0 and step < warmup_steps:
            return max(1e-8, float(step + 1) / float(warmup_steps))
        progress_den = max(1, total_steps - warmup_steps)
        progress = min(1.0, max(0.0, float(step - warmup_steps) / float(progress_den)))
        if cfg.lr_schedule == "constant":
            return 1.0
        if cfg.lr_schedule == "linear_decay":
            return max(0.0, 1.0 - progress)
        if cfg.lr_schedule == "cosine":
            return 0.5 * (1.0 + math.cos(math.pi * progress))
        raise ValueError(f"Unsupported LR schedule: {cfg.lr_schedule}")

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lr_lambda)
    return model, optimizer, scheduler


def batch_indices(num_items: int, batch_size: int, step: int) -> list[int]:
    start = step * batch_size
    return list(range(start, min(num_items, start + batch_size)))


def train_to_step(
    model: Any,
    optimizer: Any,
    scheduler: Any,
    tokenizer: Any,
    chunks: list[list[int]],
    cfg: RecipeConfig,
    condition: str,
    current_step: int,
    target_step: int,
    order_writer: Any,
) -> tuple[int, list[dict[str, Any]], bool]:
    import torch

    losses: list[dict[str, Any]] = []
    stable = True
    for step in range(current_step + 1, target_step + 1):
        indices = batch_indices(len(chunks), cfg.batch_size, step - 1)
        if len(indices) < cfg.batch_size:
            stable = False
            break
        batch = collate_batch([chunks[i] for i in indices], tokenizer.pad_token_id, cfg.device, cfg.sequence_length)
        optimizer.zero_grad(set_to_none=True)
        out = model(**batch)
        loss = out.loss
        if not torch.isfinite(loss):
            stable = False
            break
        loss.backward()
        grad_norm = None
        if cfg.grad_clip > 0:
            grad_norm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip).detach().cpu())
        optimizer.step()
        scheduler.step()
        row = {
            "step": step,
            "cumulative_tokens": step * cfg.tokens_per_step,
            "loss": float(loss.detach().cpu()),
            "learning_rate": float(scheduler.get_last_lr()[0]),
            "grad_norm_pre_clip": grad_norm,
        }
        losses.append(row)
        order_writer.write(
            json.dumps(
                {
                    "condition": condition,
                    "step": step,
                    "indices": indices,
                    "chunk_ids": [f"chunk_{i:09d}" for i in indices],
                },
                sort_keys=True,
            )
            + "\n"
        )
        if cfg.device == "cuda" and step % 50 == 0:
            torch.cuda.synchronize()
    return current_step + len(losses), losses, stable


def summarize_losses(losses: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(row["loss"]) for row in losses if math.isfinite(float(row["loss"]))]
    if not values:
        return {"count": len(losses), "finite_count": 0}
    return {
        "count": len(losses),
        "finite_count": len(values),
        "first": values[0],
        "last": values[-1],
        "mean": statistics.mean(values),
        "min": min(values),
        "max": max(values),
    }


def run_condition(
    output_dir: Path,
    condition: str,
    tokenizer: Any,
    chunks: list[list[int]],
    splits: dict[str, list[dict[str, Any]]],
    grammar_pairs: list[dict[str, str]],
    cfg: RecipeConfig,
) -> dict[str, Any]:
    import torch

    condition_dir = output_dir / "conditions" / condition
    condition_dir.mkdir(parents=True, exist_ok=True)
    eval_dir = condition_dir / "evaluations"
    eval_dir.mkdir(exist_ok=True)
    order_dir = condition_dir / "data_order"
    order_dir.mkdir(exist_ok=True)
    checkpoint_root = condition_dir / "checkpoints"
    train_loss_path = condition_dir / "train_losses.jsonl"
    torch.manual_seed(cfg.seed + CONDITION_SEED_OFFSETS[condition])
    model, optimizer, scheduler = make_model_optimizer_scheduler(cfg, cfg.target_steps)
    all_losses: list[dict[str, Any]] = []
    evaluations: dict[str, Any] = {}
    checkpoint_hashes: dict[str, dict[str, str]] = {}
    current_step = 0
    stable = True
    peak_memory = 0
    start = time.perf_counter()

    with (order_dir / "batch_order.jsonl").open("w", encoding="utf-8") as order_writer, train_loss_path.open(
        "w", encoding="utf-8"
    ) as loss_writer:
        for item in checkpoint_plan(cfg):
            target_step = int(item["optimizer_step"])
            if target_step > current_step and stable:
                current_step, losses, stable = train_to_step(
                    model,
                    optimizer,
                    scheduler,
                    tokenizer,
                    chunks,
                    cfg,
                    condition,
                    current_step,
                    target_step,
                    order_writer,
                )
                for loss in losses:
                    all_losses.append(loss)
                    loss_writer.write(json.dumps(loss, sort_keys=True) + "\n")
                loss_writer.flush()
                order_writer.flush()
            name = checkpoint_name(int(item["target_tokens"]))
            evaluation = evaluate_all(model, tokenizer, splits, grammar_pairs, cfg)
            evaluations[name] = {
                "condition": condition,
                "checkpoint": name,
                "target_tokens": int(item["target_tokens"]),
                "optimizer_step": current_step,
                "actual_cumulative_tokens": current_step * cfg.tokens_per_step,
                **evaluation,
            }
            write_json(eval_dir / f"{name}.json", evaluations[name])
            if target_step == cfg.target_steps or not stable:
                checkpoint_dir = checkpoint_root / name
                checkpoint_hashes[name] = save_checkpoint(
                    model,
                    tokenizer,
                    optimizer,
                    checkpoint_dir,
                    {
                        "condition": condition,
                        "learning_rate": cfg.learning_rate,
                        "warmup_fraction": cfg.warmup_fraction,
                        "lr_schedule": cfg.lr_schedule,
                        "grad_clip": cfg.grad_clip,
                        "weight_decay": cfg.weight_decay,
                        "target_tokens": int(item["target_tokens"]),
                        "optimizer_step": current_step,
                        "actual_cumulative_tokens": current_step * cfg.tokens_per_step,
                        "tokens_per_step": cfg.tokens_per_step,
                        "precision": "fp32",
                        "full_parameter_training": True,
                    },
                )
            if cfg.device == "cuda":
                peak_memory = max(peak_memory, int(torch.cuda.max_memory_allocated()))

    wall_seconds = time.perf_counter() - start
    summary = {
        "condition": condition,
        "model": cfg.model,
        "recipe": cfg.as_dict(),
        "stable": stable,
        "checkpoint_plan": checkpoint_plan(cfg),
        "target_tokens": cfg.target_tokens,
        "actual_target_tokens": cfg.actual_target_tokens,
        "wall_seconds": wall_seconds,
        "estimated_gpu_hours": wall_seconds / 3600.0,
        "estimated_cost_usd": wall_seconds / 3600.0 * cfg.hourly_rate_usd,
        "train_loss_summary": summarize_losses(all_losses),
        "train_loss_path": str(train_loss_path),
        "data_order_path": str(order_dir / "batch_order.jsonl"),
        "data_order_sha256": sha256_file(order_dir / "batch_order.jsonl"),
        "evaluations": evaluations,
        "checkpoint_hashes_sha256": checkpoint_hashes,
        "checkpoint_root": str(checkpoint_root),
        "evaluation_dir": str(eval_dir),
        "peak_memory_bytes": peak_memory if cfg.device == "cuda" else None,
    }
    write_json(condition_dir / "condition_summary.json", summary)
    del model, optimizer, scheduler
    if cfg.device == "cuda":
        torch.cuda.empty_cache()
    return summary


def final_key(cfg: RecipeConfig) -> str:
    return checkpoint_name(cfg.target_tokens)


def initial_key() -> str:
    return checkpoint_name(0)


def decide_attempt(cfg: RecipeConfig, summaries: dict[str, Any]) -> dict[str, Any]:
    structured = summaries["structured_pt"]
    shuffled = summaries["shuffled_pt"]
    sk0 = initial_key()
    skf = final_key(cfg)
    initial_bpb = float(structured["evaluations"][sk0]["pt_validation"]["bpb"])
    final_bpb = float(structured["evaluations"][skf]["pt_validation"]["bpb"])
    shuffled_final = float(shuffled["evaluations"][skf]["pt_validation"]["bpb"])
    delta = final_bpb - initial_bpb
    gap = shuffled_final - final_bpb
    stable = bool(structured["stable"] and shuffled["stable"])
    learned = math.isfinite(delta) and delta < -0.01
    beats_shuffled = math.isfinite(gap) and gap > 0.01
    success = stable and learned and beats_shuffled
    return {
        "status": "completed" if success else "blocked",
        "gate_decision": "proceed" if success else "pivot",
        "stable": stable,
        "structured_pt_initial_bpb": initial_bpb,
        "structured_pt_final_bpb": final_bpb,
        "structured_pt_bpb_delta": delta,
        "shuffled_pt_final_bpb": shuffled_final,
        "structured_vs_shuffled_pt_bpb_gap": gap,
        "criteria": {
            "structured_pt_bpb_decreasing": learned,
            "beats_shuffled_control": beats_shuffled,
            "stable_no_nan_or_divergence": stable,
        },
        "winning_checkpoint_path": str(
            Path("conditions")
            / "structured_pt"
            / "checkpoints"
            / final_key(cfg)
        )
        if success
        else None,
        "next_bounded_action": (
            "Stop for operator greenlight; continue this recipe from the structured checkpoint to a larger token budget."
            if success
            else "Next short attempt: lower LR further or extend fresh-token budget while preserving the fixed validation set."
        ),
    }


def write_phase_report(output_dir: Path, run_id: str, manifest: dict[str, Any], decision: dict[str, Any]) -> None:
    lines = [
        "# Recipe Search Attempt Report",
        "",
        f"- Run ID: `{run_id}`",
        f"- Source commit: `{manifest['git_commit']}`",
        f"- Model: `{manifest['config']['model']}`",
        f"- Gate decision: `{decision['gate_decision']}`",
        "",
        "## Recipe",
        "",
        f"- LR: `{manifest['config']['learning_rate']}`",
        f"- Warmup fraction: `{manifest['config']['warmup_fraction']}`",
        f"- Schedule: `{manifest['config']['lr_schedule']}`",
        f"- Grad clip: `{manifest['config']['grad_clip']}`",
        f"- Weight decay: `{manifest['config']['weight_decay']}`",
        f"- Batch size: `{manifest['config']['batch_size']}`",
        f"- Target tokens per condition: `{manifest['config']['actual_target_tokens']}`",
        "",
        "## Evidence",
        "",
        f"- Manifest: `{output_dir / 'manifest.json'}`",
        f"- Data manifest: `{output_dir / 'data_splits' / 'split_manifest.json'}`",
        f"- Structured summary: `{output_dir / 'conditions' / 'structured_pt' / 'condition_summary.json'}`",
        f"- Shuffled summary: `{output_dir / 'conditions' / 'shuffled_pt' / 'condition_summary.json'}`",
        f"- Structured checkpoint: `{output_dir / 'conditions' / 'structured_pt' / 'checkpoints' / final_key(RecipeConfig(**manifest['config_for_rehydrate']))}`",
        "",
        "## Metrics",
        "",
        f"- Structured PT BPB: `{decision['structured_pt_initial_bpb']:.6f}` -> `{decision['structured_pt_final_bpb']:.6f}` (`{decision['structured_pt_bpb_delta']:.6f}`)",
        f"- Shuffled PT final BPB: `{decision['shuffled_pt_final_bpb']:.6f}`",
        f"- Structured-vs-shuffled final gap: `{decision['structured_vs_shuffled_pt_bpb_gap']:.6f}`",
        f"- Stable: `{decision['stable']}`",
        "",
        "## Runtime And Cost",
        "",
        f"- Wall seconds: `{manifest['wall_seconds']:.2f}`",
        f"- Estimated GPU hours: `{manifest['estimated_gpu_hours']:.4f}`",
        f"- Estimated cost USD: `${manifest['estimated_cost_usd']:.4f}`",
        "",
        "## Uncertainty",
        "",
        "- This is a recipe-search attempt, not a final scientific result.",
        "- The fixed validation set is the pilot OPUS validation split; training chunks come from a fresh Portuguese Wikipedia stream slice.",
        "- A successful recipe should be continued only after operator greenlight.",
        "",
        "## Failure Modes",
        "",
        "- A short run can show early adaptation that later degrades; scale-up must continue to monitor BPB.",
        "- Shuffled-control separation can be noisy at small token budgets.",
        "",
        "## Next Action",
        "",
        decision["next_bounded_action"],
        "",
    ]
    (output_dir / "phase_report.md").write_text("\n".join(lines), encoding="utf-8")


def write_state_files(output_dir: Path, run_id: str, manifest: dict[str, Any], decision: dict[str, Any]) -> None:
    checkpoint_path = output_dir / "conditions" / "structured_pt" / "checkpoints" / final_key(RecipeConfig(**manifest["config_for_rehydrate"]))
    status = {
        "phase": "recipe_search",
        "gate": decision["gate_decision"],
        "last_updated": utc_now(),
        "latest_run_id": run_id,
        "latest_run_dir": str(output_dir),
        "git_commit": manifest["git_commit"],
        "model": manifest["config"]["model"],
        "recipe": manifest["config"],
        "structured_pt_initial_bpb": decision["structured_pt_initial_bpb"],
        "structured_pt_final_bpb": decision["structured_pt_final_bpb"],
        "structured_pt_bpb_delta": decision["structured_pt_bpb_delta"],
        "shuffled_pt_final_bpb": decision["shuffled_pt_final_bpb"],
        "structured_vs_shuffled_pt_bpb_gap": decision["structured_vs_shuffled_pt_bpb_gap"],
        "criteria": decision["criteria"],
        "checkpoint_path": str(checkpoint_path),
        "requires_human_approval": decision["gate_decision"] == "proceed",
        "approval_reason": (
            "Recipe found; do not start a larger token-budget continuation until operator greenlight."
            if decision["gate_decision"] == "proceed"
            else ""
        ),
        "estimated_incremental_gpu_hours": manifest["estimated_gpu_hours"],
        "estimated_incremental_cost_usd": manifest["estimated_cost_usd"],
        "evidence_paths": {
            "phase_report": str(output_dir / "phase_report.md"),
            "manifest": str(output_dir / "manifest.json"),
            "data_manifest": str(output_dir / "data_splits" / "split_manifest.json"),
            "structured_summary": str(output_dir / "conditions" / "structured_pt" / "condition_summary.json"),
            "shuffled_summary": str(output_dir / "conditions" / "shuffled_pt" / "condition_summary.json"),
            "bounded_job_dir": str(output_dir / "jobs" / "recipe_attempt"),
        },
        "next_action": decision["next_bounded_action"],
    }
    write_json(Path("state/current_status.json"), status)

    entry = f"""
## {utc_now()} — TinyStories-8M recipe-search attempt {run_id}

Decision: {decision['gate_decision']}. This is a short recipe-search attempt only, not a final scientific result.

Recipe: full-parameter FP32 AdamW on `roneneldan/TinyStories-8M`; lr `{manifest['config']['learning_rate']}`, warmup `{manifest['config']['warmup_fraction']}`, schedule `{manifest['config']['lr_schedule']}`, grad clip `{manifest['config']['grad_clip']}`, weight decay `{manifest['config']['weight_decay']}`, batch `{manifest['config']['batch_size']}`, tokens per condition `{manifest['config']['actual_target_tokens']}`.

Data: fixed pilot Portuguese validation from `{manifest['config']['validation_jsonl']}`; fresh structured/shuffled Portuguese training chunks from `{manifest['config']['train_corpus']}` `{manifest['config']['train_corpus_config']}`. Data hashes are recorded in `{output_dir / 'data_splits' / 'split_manifest.json'}`.

Evidence: `{output_dir / 'manifest.json'}`, `{output_dir / 'phase_report.md'}`, structured summary `{output_dir / 'conditions' / 'structured_pt' / 'condition_summary.json'}`, shuffled summary `{output_dir / 'conditions' / 'shuffled_pt' / 'condition_summary.json'}`, structured checkpoint `{checkpoint_path}`.

Metrics: structured PT BPB `{decision['structured_pt_initial_bpb']:.6f}` -> `{decision['structured_pt_final_bpb']:.6f}` (delta `{decision['structured_pt_bpb_delta']:.6f}`); shuffled final BPB `{decision['shuffled_pt_final_bpb']:.6f}`; structured-vs-shuffled gap `{decision['structured_vs_shuffled_pt_bpb_gap']:.6f}`; stable `{decision['stable']}`.

Runtime/cost: wall `{manifest['wall_seconds']:.2f}` seconds; estimated GPU-hours `{manifest['estimated_gpu_hours']:.4f}`; estimated incremental cost `${manifest['estimated_cost_usd']:.4f}`.

Gate decision: {decision['gate_decision']}. Next bounded action: {decision['next_bounded_action']}
"""
    with Path("state/decision_log.md").open("a", encoding="utf-8") as handle:
        handle.write(entry)

    with Path("state/experiment_registry.csv").open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                run_id,
                "recipe_search",
                decision["status"],
                "structured_pt__shuffled_pt",
                manifest["config"]["model"],
                manifest["config"]["seed"],
                manifest["git_commit"],
                str(output_dir / "manifest.json"),
                manifest["start_utc"],
                manifest["end_utc"],
                f"{manifest['estimated_gpu_hours']:.4f}",
                f"{manifest['estimated_cost_usd']:.4f}",
                str(output_dir),
                (
                    f"Recipe search attempt: structured PT BPB {decision['structured_pt_initial_bpb']:.4f}->"
                    f"{decision['structured_pt_final_bpb']:.4f}; shuffled final {decision['shuffled_pt_final_bpb']:.4f}; "
                    f"gap {decision['structured_vs_shuffled_pt_bpb_gap']:.4f}; gate {decision['gate_decision']}."
                ),
            ]
        )


def rehydrate_config_args(cfg: RecipeConfig) -> dict[str, Any]:
    raw = cfg.as_dict()
    return {
        "model": cfg.model,
        "sequence_length": cfg.sequence_length,
        "batch_size": cfg.batch_size,
        "target_tokens": cfg.target_tokens,
        "checkpoint_tokens": cfg.checkpoint_tokens,
        "learning_rate": cfg.learning_rate,
        "warmup_fraction": cfg.warmup_fraction,
        "lr_schedule": cfg.lr_schedule,
        "grad_clip": cfg.grad_clip,
        "weight_decay": cfg.weight_decay,
        "seed": cfg.seed,
        "device": cfg.device,
        "hourly_rate_usd": cfg.hourly_rate_usd,
        "validation_jsonl": cfg.validation_jsonl,
        "grammar_csv": cfg.grammar_csv,
        "local_files_only": cfg.local_files_only,
        "train_corpus": cfg.train_corpus,
        "train_corpus_config": cfg.train_corpus_config,
        "max_docs": cfg.max_docs,
    } | {"checkpoint_tokens": tuple(raw["checkpoint_tokens"])}


def parse_checkpoint_tokens(value: str) -> tuple[int, ...]:
    return tuple(int(x) for x in value.split(",") if x.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="TinyStories-8M rapid Portuguese recipe-search attempt")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default="roneneldan/TinyStories-8M")
    parser.add_argument("--sequence-length", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--target-tokens", type=int, default=1_000_000)
    parser.add_argument("--checkpoint-tokens", default="0,100000,250000,500000,1000000")
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--warmup-fraction", type=float, default=0.03)
    parser.add_argument("--lr-schedule", choices=["constant", "cosine", "linear_decay"], default="cosine")
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=202606201)
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    parser.add_argument("--hourly-rate-usd", type=float, default=1.0)
    parser.add_argument("--validation-jsonl", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--grammar-csv", type=Path, default=DEFAULT_GRAMMAR)
    parser.add_argument("--local-files-only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--train-corpus", default="wikimedia/wikipedia")
    parser.add_argument("--train-corpus-config", default="20231101.pt")
    parser.add_argument("--max-docs", type=int, default=512)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    cfg = RecipeConfig(
        model=args.model,
        sequence_length=args.sequence_length,
        batch_size=args.batch_size,
        target_tokens=args.target_tokens,
        checkpoint_tokens=parse_checkpoint_tokens(args.checkpoint_tokens),
        learning_rate=args.learning_rate,
        warmup_fraction=args.warmup_fraction,
        lr_schedule=args.lr_schedule,
        grad_clip=args.grad_clip,
        weight_decay=args.weight_decay,
        seed=args.seed,
        device=args.device,
        hourly_rate_usd=args.hourly_rate_usd,
        validation_jsonl=args.validation_jsonl,
        grammar_csv=args.grammar_csv,
        local_files_only=args.local_files_only,
        train_corpus=args.train_corpus,
        train_corpus_config=args.train_corpus_config,
        max_docs=args.max_docs,
    )
    if cfg.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_start = time.perf_counter()
    start_utc = utc_now()
    tokenizer = AutoTokenizer.from_pretrained(cfg.model, local_files_only=cfg.local_files_only)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model_probe = AutoModelForCausalLM.from_pretrained(cfg.model, local_files_only=cfg.local_files_only)
    parameter_count = int(sum(p.numel() for p in model_probe.parameters()))
    del model_probe
    if cfg.device == "cuda":
        torch.cuda.empty_cache()

    data = load_prepared_data(args.output_dir) if (args.output_dir / "data_splits" / "split_manifest.json").exists() else prepare_data(args.output_dir, tokenizer, cfg)
    grammar_pairs = load_grammar_pairs(cfg.grammar_csv)
    manifest = {
        "run_kind": "tinystories_8m_recipe_search_attempt",
        "scientific_scope": "Short training-recipe search only; not a final result.",
        "start_utc": start_utc,
        "git_commit": git_commit(),
        "git_status_short_at_start": git_status_short(),
        "config": cfg.as_dict(),
        "config_for_rehydrate": {k: (str(v) if isinstance(v, Path) else v) for k, v in rehydrate_config_args(cfg).items()},
        "package_versions": package_versions(),
        "device": cfg.device,
        "gpu": torch.cuda.get_device_name(0) if cfg.device == "cuda" else None,
        "torch_cuda_available": bool(torch.cuda.is_available()),
        "parameter_count": parameter_count,
        "tokenizer_vocab_sha256": stable_json_hash(tokenizer.get_vocab()),
        "data_split_manifest": str(args.output_dir / "data_splits" / "split_manifest.json"),
        "checkpoint_plan": checkpoint_plan(cfg),
    }
    write_json(args.output_dir / "manifest.json", manifest)
    if args.prepare_only:
        manifest.update({"end_utc": utc_now(), "exit_status": "prepared_only"})
        write_json(args.output_dir / "manifest.json", manifest)
        print(json.dumps({"prepared": True, "manifest": str(args.output_dir / "manifest.json")}, indent=2))
        return 0

    summaries = {
        "structured_pt": run_condition(
            args.output_dir,
            "structured_pt",
            tokenizer,
            data["structured_chunks"],
            data["splits"],
            grammar_pairs,
            cfg,
        ),
        "shuffled_pt": run_condition(
            args.output_dir,
            "shuffled_pt",
            tokenizer,
            data["shuffled_chunks"],
            data["splits"],
            grammar_pairs,
            cfg,
        ),
    }
    decision = decide_attempt(cfg, summaries)
    wall_seconds = time.perf_counter() - run_start
    manifest.update(
        {
            "end_utc": utc_now(),
            "wall_seconds": wall_seconds,
            "estimated_gpu_hours": wall_seconds / 3600.0,
            "estimated_cost_usd": wall_seconds / 3600.0 * cfg.hourly_rate_usd,
            "condition_summaries": {
                condition: str(args.output_dir / "conditions" / condition / "condition_summary.json")
                for condition in CONDITIONS
            },
            "decision": decision,
            "output_tree_size_bytes": path_size_bytes(args.output_dir),
            "exit_status": decision["status"],
        }
    )
    write_json(args.output_dir / "manifest.json", manifest)
    write_phase_report(args.output_dir, args.output_dir.name, manifest, decision)
    write_state_files(args.output_dir, args.output_dir.name, manifest, decision)
    print(json.dumps({"run_id": args.output_dir.name, "decision": decision}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
