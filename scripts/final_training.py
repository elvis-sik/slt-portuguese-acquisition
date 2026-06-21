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
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.scientific_pilot import (
    collate_batch,
    evaluate_all,
    git_commit,
    git_status_short,
    grammar_sanity_checks,
    load_grammar_pairs,
    normalize_text,
    package_versions,
    path_size_bytes,
    save_checkpoint,
    sha256_file,
    stable_json_hash,
    utc_now,
    write_json,
    write_jsonl,
)


FINAL_CONDITIONS = (
    "structured_pt_seed_a",
    "shuffled_pt",
    "matched_en",
    "structured_pt_seed_b",
)

CONDITION_SEED_OFFSETS = {
    "structured_pt_seed_a": 101,
    "shuffled_pt": 202,
    "matched_en": 303,
    "structured_pt_seed_b": 404,
}


@dataclass(frozen=True)
class FinalConfig:
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
    hard_cap_usd: float
    starting_cumulative_cost_usd: float
    split_manifest: Path
    grammar_csv: Path
    local_files_only: bool
    validation_source: str
    validation_config: str
    validation_size: int
    sampler_reference_size: int
    validation_skip: int
    train_corpus_pt: str
    train_corpus_pt_config: str
    train_corpus_en: str
    train_corpus_en_config: str
    max_docs_pt: int
    max_docs_en: int
    fixed_llc_checkpoint_tokens: tuple[int, ...]
    adaptive_metric: str

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
            "hard_cap_usd": self.hard_cap_usd,
            "starting_cumulative_cost_usd": self.starting_cumulative_cost_usd,
            "split_manifest": str(self.split_manifest),
            "grammar_csv": str(self.grammar_csv),
            "local_files_only": self.local_files_only,
            "validation_source": self.validation_source,
            "validation_config": self.validation_config,
            "validation_size": self.validation_size,
            "sampler_reference_size": self.sampler_reference_size,
            "validation_skip": self.validation_skip,
            "train_corpus_pt": self.train_corpus_pt,
            "train_corpus_pt_config": self.train_corpus_pt_config,
            "train_corpus_en": self.train_corpus_en,
            "train_corpus_en_config": self.train_corpus_en_config,
            "max_docs_pt": self.max_docs_pt,
            "max_docs_en": self.max_docs_en,
            "conditions_priority_order": list(FINAL_CONDITIONS),
            "llc_selection_rule": {
                "fixed_llc_checkpoint_tokens": list(self.fixed_llc_checkpoint_tokens),
                "adaptive_metric": self.adaptive_metric,
                "adaptive_rule": (
                    "After all behavior trajectories are written and before any final LLC inspection, "
                    "select the adjacent structured_pt_seed_a checkpoint pair with the largest positive "
                    "change in the configured behavior metric per log-token interval; if no positive "
                    "increase exists, use the largest absolute BPB decrease. Add at most those two "
                    "bracketing checkpoints to the fixed set."
                ),
            },
        }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def read_config(path: Path) -> FinalConfig:
    raw = load_json(path)
    training = raw["training"]
    data = raw["data"]
    cost = raw.get("cost", {})
    llc = raw["llc_checkpoint_selection"]
    return FinalConfig(
        model=raw["model"]["id"],
        sequence_length=int(training["sequence_length"]),
        batch_size=int(training["global_batch_size"]),
        target_tokens=int(training["target_tokens"]),
        checkpoint_tokens=tuple(int(x) for x in training["checkpoint_tokens"]),
        learning_rate=float(training["learning_rate"]),
        warmup_fraction=float(training.get("warmup_fraction", 0.0)),
        lr_schedule=str(training.get("lr_schedule", "constant")),
        grad_clip=float(training.get("grad_clip", 0.0)),
        weight_decay=float(training.get("weight_decay", 0.0)),
        seed=int(training["seed"]),
        device=str(training["device"]),
        hourly_rate_usd=float(cost.get("hourly_rate_usd", 1.0)),
        hard_cap_usd=float(cost.get("hard_cap_usd", 50.0)),
        starting_cumulative_cost_usd=float(cost.get("starting_cumulative_cost_usd", 0.0)),
        split_manifest=Path(data.get("split_manifest", "")),
        grammar_csv=Path(raw["evaluation"]["grammar_pairs"]),
        local_files_only=bool(raw["model"].get("local_files_only", True)),
        validation_source=str(data.get("validation_source", "Helsinki-NLP/opus-100")),
        validation_config=str(data.get("validation_config", "en-pt")),
        validation_size=int(data.get("validation_size", 512)),
        sampler_reference_size=int(data.get("sampler_reference_size", 128)),
        validation_skip=int(data.get("validation_skip", 512)),
        train_corpus_pt=str(data.get("train_corpus_pt", data.get("train_corpus", "wikimedia/wikipedia"))),
        train_corpus_pt_config=str(data.get("train_corpus_pt_config", data.get("train_corpus_config", "20231101.pt"))),
        train_corpus_en=str(data.get("train_corpus_en", "wikimedia/wikipedia")),
        train_corpus_en_config=str(data.get("train_corpus_en_config", "20231101.en")),
        max_docs_pt=int(data.get("max_docs_pt", data.get("max_docs", 16384))),
        max_docs_en=int(data.get("max_docs_en", data.get("max_docs", 16384))),
        fixed_llc_checkpoint_tokens=tuple(int(x) for x in llc["fixed_checkpoint_tokens"]),
        adaptive_metric=str(llc.get("adaptive_metric", "grammar_mean_margin")),
    )


def checkpoint_plan(cfg: FinalConfig) -> list[dict[str, int]]:
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


def stream_parallel_rows(cfg: FinalConfig) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    from datasets import load_dataset

    needed = cfg.validation_size + cfg.sampler_reference_size
    stream = load_dataset(cfg.validation_source, cfg.validation_config, split="train", streaming=True)
    rows: list[dict[str, str]] = []
    counts = {
        "seen": 0,
        "accepted": 0,
        "skipped_after_filter": 0,
        "missing": 0,
        "markup_heavy": 0,
        "length_rejected": 0,
        "duplicate_pairs": 0,
    }
    seen: set[tuple[str, str]] = set()
    for ex in stream:
        counts["seen"] += 1
        translation = ex.get("translation", {})
        en = normalize_text(translation.get("en", ""))
        pt = normalize_text(translation.get("pt", ""))
        if not en or not pt:
            counts["missing"] += 1
            continue
        if any(mark in en or mark in pt for mark in ("<", ">", "{", "}")):
            counts["markup_heavy"] += 1
            continue
        ratio = max(len(en), len(pt)) / max(1, min(len(en), len(pt)))
        if len(en) < 12 or len(pt) < 12 or len(en) > 260 or len(pt) > 260 or ratio > 2.8:
            counts["length_rejected"] += 1
            continue
        key = (en.casefold(), pt.casefold())
        if key in seen:
            counts["duplicate_pairs"] += 1
            continue
        seen.add(key)
        if counts["skipped_after_filter"] < cfg.validation_skip:
            counts["skipped_after_filter"] += 1
            continue
        rows.append(
            {
                "id": f"opus100_final_{len(rows):06d}",
                "source": f"{cfg.validation_source}/{cfg.validation_config}/train",
                "en": en,
                "pt": pt,
            }
        )
        counts["accepted"] += 1
        if len(rows) >= needed:
            break
    if len(rows) < needed:
        raise RuntimeError(f"Validation stream produced {len(rows)} rows after skip; need {needed}")
    metadata = {
        "source": cfg.validation_source,
        "config": cfg.validation_config,
        "split": "train",
        "streaming": True,
        "validation_skip_after_filter": cfg.validation_skip,
        "counts": counts,
    }
    return rows[: cfg.validation_size], rows[cfg.validation_size :], metadata


def shuffled_chunks(chunks: list[list[int]], seed: int) -> list[list[int]]:
    rng = random.Random(seed)
    out: list[list[int]] = []
    for chunk in chunks:
        local = list(chunk)
        rng.shuffle(local)
        out.append(local)
    return out


def write_chunk_jsonl(path: Path, chunks: list[list[int]], records: list[dict[str, Any]]) -> None:
    write_jsonl(path, ({**record, "input_ids": chunk} for chunk, record in zip(chunks, records)))


def stream_chunks(
    tokenizer: Any,
    source: str,
    config: str,
    max_docs: int,
    cfg: FinalConfig,
) -> tuple[list[list[int]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    from datasets import load_dataset

    stream = load_dataset(source, config, split="train", streaming=True)
    chunks: list[list[int]] = []
    records: list[dict[str, Any]] = []
    doc_records: list[dict[str, Any]] = []
    counts = {"seen": 0, "accepted": 0, "too_short": 0, "empty": 0}
    eos = tokenizer.eos_token_id if tokenizer.eos_token_id is not None else tokenizer.pad_token_id
    for ex in stream:
        counts["seen"] += 1
        text = normalize_text(str(ex.get("text", "")))
        if not text:
            counts["empty"] += 1
            continue
        if len(text) < 200:
            counts["too_short"] += 1
            continue
        doc_id = str(ex.get("id", f"doc_{counts['seen']:09d}"))
        doc_title = str(ex.get("title", ""))
        ids = tokenizer(text, add_special_tokens=False)["input_ids"]
        if eos is not None:
            ids.append(int(eos))
        doc_start_chunks = len(chunks)
        for start in range(0, len(ids) - cfg.sequence_length + 1, cfg.sequence_length):
            chunk = [int(x) for x in ids[start : start + cfg.sequence_length]]
            if len(chunk) != cfg.sequence_length:
                continue
            chunks.append(chunk)
            records.append(
                {
                    "chunk_id": f"chunk_{len(chunks) - 1:09d}",
                    "doc_id": doc_id,
                    "doc_title": doc_title,
                    "token_start": start,
                    "token_count": len(chunk),
                    "input_ids_sha256": stable_json_hash(chunk),
                }
            )
            if len(chunks) >= cfg.train_chunks_needed:
                break
        counts["accepted"] += 1
        doc_records.append(
            {
                "id": doc_id,
                "title": doc_title,
                "url": str(ex.get("url", "")),
                "text_sha256": stable_json_hash(text),
                "chunks_used": len(chunks) - doc_start_chunks,
            }
        )
        if len(chunks) >= cfg.train_chunks_needed:
            break
        if counts["accepted"] >= max_docs:
            break
    metadata = {
        "source": source,
        "config": config,
        "split": "train",
        "streaming": True,
        "max_docs": max_docs,
        "counts": counts,
    }
    return chunks, records, doc_records, metadata


def prepare_data(output_dir: Path, tokenizer: Any, cfg: FinalConfig) -> dict[str, Any]:
    split_dir = output_dir / "data_splits"
    split_dir.mkdir(parents=True, exist_ok=True)
    validation_rows, sampler_rows, validation_metadata = stream_parallel_rows(cfg)
    write_jsonl(split_dir / "validation.jsonl", validation_rows)
    write_jsonl(split_dir / "sampler_reference.jsonl", sampler_rows)

    pt_chunks, pt_records, pt_doc_records, pt_metadata = stream_chunks(
        tokenizer,
        cfg.train_corpus_pt,
        cfg.train_corpus_pt_config,
        cfg.max_docs_pt,
        cfg,
    )
    if len(pt_chunks) < cfg.train_chunks_needed:
        raise RuntimeError(f"Portuguese corpus produced {len(pt_chunks)} chunks, need {cfg.train_chunks_needed}")
    pt_chunks = pt_chunks[: cfg.train_chunks_needed]
    pt_records = pt_records[: cfg.train_chunks_needed]
    shuffled = shuffled_chunks(pt_chunks, cfg.seed + CONDITION_SEED_OFFSETS["shuffled_pt"])
    write_chunk_jsonl(split_dir / "train_structured_pt_token_ids.jsonl", pt_chunks, pt_records)
    write_chunk_jsonl(split_dir / "train_shuffled_pt_token_ids.jsonl", shuffled, pt_records)
    write_jsonl(split_dir / "train_documents_manifest_pt.jsonl", pt_doc_records)

    en_chunks, en_records, en_doc_records, en_metadata = stream_chunks(
        tokenizer,
        cfg.train_corpus_en,
        cfg.train_corpus_en_config,
        cfg.max_docs_en,
        cfg,
    )
    if len(en_chunks) < cfg.train_chunks_needed:
        raise RuntimeError(f"English corpus produced {len(en_chunks)} chunks, need {cfg.train_chunks_needed}")
    en_chunks = en_chunks[: cfg.train_chunks_needed]
    en_records = en_records[: cfg.train_chunks_needed]
    write_chunk_jsonl(split_dir / "train_matched_en_token_ids.jsonl", en_chunks, en_records)
    write_jsonl(split_dir / "train_documents_manifest_en.jsonl", en_doc_records)

    split_hashes = {
        filename: sha256_file(split_dir / filename)
        for filename in (
            "validation.jsonl",
            "sampler_reference.jsonl",
            "train_structured_pt_token_ids.jsonl",
            "train_shuffled_pt_token_ids.jsonl",
            "train_matched_en_token_ids.jsonl",
            "train_documents_manifest_pt.jsonl",
            "train_documents_manifest_en.jsonl",
        )
    }
    manifest = {
        "created_utc": utc_now(),
        "immutability_note": "Final data artifacts are content-addressed by SHA256 and must not be edited in place.",
        "validation_metadata": validation_metadata,
        "training_corpus_pt": pt_metadata,
        "training_corpus_en": en_metadata,
        "split_sizes": {
            "validation": len(validation_rows),
            "sampler_reference": len(sampler_rows),
            "structured_pt_chunks": len(pt_chunks),
            "shuffled_pt_chunks": len(shuffled),
            "matched_en_chunks": len(en_chunks),
            "tokens_per_condition": cfg.actual_target_tokens,
            "documents_pt": len(pt_doc_records),
            "documents_en": len(en_doc_records),
        },
        "split_hashes_sha256": split_hashes,
        "grammar_csv": str(cfg.grammar_csv),
        "grammar_csv_sha256": sha256_file(cfg.grammar_csv),
        "shuffled_mapping_seed": cfg.seed + CONDITION_SEED_OFFSETS["shuffled_pt"],
        "tokenizer_vocab_sha256": stable_json_hash(tokenizer.get_vocab()),
    }
    write_json(split_dir / "split_manifest.json", manifest)
    return {
        "manifest": manifest,
        "split_dir": split_dir,
        "splits": {"validation": validation_rows, "sampler_reference": sampler_rows},
        "structured_chunks": pt_chunks,
        "shuffled_chunks": shuffled,
        "matched_en_chunks": en_chunks,
    }


def read_chunks(path: Path) -> list[list[int]]:
    return [[int(x) for x in row["input_ids"]] for row in load_jsonl(path)]


def load_prepared_data(output_dir: Path, cfg: FinalConfig) -> dict[str, Any]:
    split_dir = output_dir / "data_splits"
    manifest = load_json(split_dir / "split_manifest.json")
    for filename, expected_hash in manifest["split_hashes_sha256"].items():
        path = split_dir / filename
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            raise RuntimeError(f"Prepared data hash mismatch for {filename}: {actual_hash} != {expected_hash}")
    if int(manifest["split_sizes"]["validation"]) < cfg.validation_size:
        raise RuntimeError("Prepared validation split is smaller than the configured final validation size")
    return {
        "manifest": manifest,
        "split_dir": split_dir,
        "splits": {
            "validation": load_jsonl(split_dir / "validation.jsonl"),
            "sampler_reference": load_jsonl(split_dir / "sampler_reference.jsonl"),
        },
        "structured_chunks": read_chunks(split_dir / "train_structured_pt_token_ids.jsonl"),
        "shuffled_chunks": read_chunks(split_dir / "train_shuffled_pt_token_ids.jsonl"),
        "matched_en_chunks": read_chunks(split_dir / "train_matched_en_token_ids.jsonl"),
    }


def make_model_optimizer_scheduler(cfg: FinalConfig) -> tuple[Any, Any, Any]:
    import torch
    from transformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(cfg.model, local_files_only=cfg.local_files_only)
    model = model.to(cfg.device).float().train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg.learning_rate, weight_decay=cfg.weight_decay)
    warmup_steps = int(round(cfg.target_steps * cfg.warmup_fraction))

    def lr_lambda(step: int) -> float:
        if warmup_steps > 0 and step < warmup_steps:
            return max(1e-8, float(step + 1) / float(warmup_steps))
        progress_den = max(1, cfg.target_steps - warmup_steps)
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
    sequences: list[list[int]],
    cfg: FinalConfig,
    condition: str,
    current_step: int,
    target_step: int,
    order_writer: Any,
) -> tuple[int, list[dict[str, Any]], bool]:
    model.train()
    losses: list[dict[str, Any]] = []
    stable = True
    import torch

    for step in range(current_step + 1, target_step + 1):
        indices = batch_indices(len(sequences), cfg.batch_size, step - 1)
        if len(indices) < cfg.batch_size:
            stable = False
            break
        batch_sequences = [sequences[i] for i in indices]
        batch = collate_batch(batch_sequences, tokenizer.pad_token_id, cfg.device, cfg.sequence_length)
        optimizer.zero_grad(set_to_none=True)
        out = model(**batch)
        loss_tensor = out.loss
        if not torch.isfinite(loss_tensor):
            stable = False
            break
        loss_tensor.backward()
        grad_norm = None
        if cfg.grad_clip > 0:
            grad_norm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip).detach().cpu())
        optimizer.step()
        scheduler.step()
        loss = float(loss_tensor.detach().cpu())
        losses.append(
            {
                "step": step,
                "cumulative_tokens": step * cfg.tokens_per_step,
                "loss": loss,
                "learning_rate": float(scheduler.get_last_lr()[0]),
                "grad_norm_pre_clip": grad_norm,
            }
        )
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


def run_condition(
    output_dir: Path,
    condition: str,
    tokenizer: Any,
    sequences: list[list[int]],
    splits: dict[str, list[dict[str, Any]]],
    grammar_pairs: list[dict[str, str]],
    cfg: FinalConfig,
) -> dict[str, Any]:
    import torch

    condition_dir = output_dir / "conditions" / condition
    checkpoint_root = condition_dir / "checkpoints"
    eval_dir = condition_dir / "evaluations"
    order_dir = condition_dir / "data_order"
    train_loss_path = condition_dir / "train_losses.jsonl"
    condition_dir.mkdir(parents=True, exist_ok=True)
    eval_dir.mkdir(parents=True, exist_ok=True)
    order_dir.mkdir(parents=True, exist_ok=True)

    torch.manual_seed(cfg.seed + CONDITION_SEED_OFFSETS[condition])
    # Genuine per-seed variation. batch_indices() walks `sequences` sequentially (seed-independent), and
    # the model has no active dropout, so without this every condition produced byte-IDENTICAL weights —
    # i.e. "seed B" was a duplicate of "seed A", not a replication (see decision_log 2026-06-21). Shuffling
    # the data ORDER with the condition seed makes the optimization trajectory genuinely seed-dependent.
    order_rng = random.Random(cfg.seed + CONDITION_SEED_OFFSETS[condition])
    sequences = list(sequences)
    order_rng.shuffle(sequences)
    model, optimizer, scheduler = make_model_optimizer_scheduler(cfg)
    plan = checkpoint_plan(cfg)
    checkpoint_hashes: dict[str, dict[str, str]] = {}
    evaluations: dict[str, Any] = {}
    all_losses: list[dict[str, Any]] = []
    current_step = 0
    stable = True
    start = time.perf_counter()
    peak_memory = 0

    with (order_dir / "batch_order.jsonl").open("w", encoding="utf-8") as order_writer, train_loss_path.open(
        "w", encoding="utf-8"
    ) as loss_writer:
        for item in plan:
            target_step = int(item["optimizer_step"])
            if target_step > current_step and stable:
                current_step, losses, stable = train_to_step(
                    model,
                    optimizer,
                    scheduler,
                    tokenizer,
                    sequences,
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
            hashes = save_checkpoint(
                model,
                tokenizer,
                optimizer,
                checkpoint_root / name,
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
            checkpoint_hashes[name] = hashes
            if cfg.device == "cuda":
                peak_memory = max(peak_memory, int(torch.cuda.max_memory_allocated()))

    wall_seconds = time.perf_counter() - start
    order_hash = sha256_file(order_dir / "batch_order.jsonl")
    summary = {
        "condition": condition,
        "model": cfg.model,
        "recipe": cfg.as_dict(),
        "stable": stable,
        "learning_rate": cfg.learning_rate,
        "warmup_fraction": cfg.warmup_fraction,
        "lr_schedule": cfg.lr_schedule,
        "grad_clip": cfg.grad_clip,
        "weight_decay": cfg.weight_decay,
        "checkpoint_plan": plan,
        "tokens_per_step": cfg.tokens_per_step,
        "target_tokens": cfg.target_tokens,
        "actual_target_tokens": cfg.actual_target_tokens,
        "wall_seconds": wall_seconds,
        "estimated_gpu_hours": wall_seconds / 3600.0,
        "estimated_cost_usd": wall_seconds / 3600.0 * cfg.hourly_rate_usd,
        "train_loss_summary": summarize_losses(all_losses),
        "train_loss_path": str(train_loss_path),
        "data_order_path": str(order_dir / "batch_order.jsonl"),
        "data_order_sha256": order_hash,
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


def summarize_losses(losses: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(row["loss"]) for row in losses if math.isfinite(float(row["loss"]))]
    if not values:
        return {"count": 0, "finite_count": 0}
    return {
        "count": len(losses),
        "finite_count": len(values),
        "first": values[0],
        "last": values[-1],
        "mean": statistics.mean(values),
        "min": min(values),
        "max": max(values),
    }


def metric_value(evaluation: dict[str, Any], metric: str) -> float:
    if metric == "grammar_mean_margin":
        return float(evaluation["grammar_margin"]["mean_margin"])
    if metric == "pt_validation_bpb":
        return -float(evaluation["pt_validation"]["bpb"])
    raise ValueError(f"Unsupported adaptive metric: {metric}")


def select_llc_checkpoints(cfg: FinalConfig, structured_seed_a: dict[str, Any]) -> dict[str, Any]:
    evaluations = structured_seed_a["evaluations"]
    plan = structured_seed_a["checkpoint_plan"]
    by_name = {checkpoint_name(int(item["target_tokens"])): item for item in plan}
    ordered = [
        (by_name[name]["target_tokens"], name, evaluations[name])
        for name in sorted(evaluations, key=lambda key: by_name[key]["target_tokens"])
    ]
    best_pair: tuple[int, int] | None = None
    best_score = -float("inf")
    fallback_pair: tuple[int, int] | None = None
    fallback_score = -float("inf")
    for (left_tokens, left_name, left_eval), (right_tokens, right_name, right_eval) in zip(ordered, ordered[1:]):
        left_metric = metric_value(left_eval, cfg.adaptive_metric)
        right_metric = metric_value(right_eval, cfg.adaptive_metric)
        denom = math.log1p(right_tokens) - math.log1p(left_tokens)
        delta = right_metric - left_metric
        score = delta / max(1e-12, denom)
        if score > best_score and delta > 0:
            best_score = score
            best_pair = (left_tokens, right_tokens)
        bpb_drop = float(left_eval["pt_validation"]["bpb"]) - float(right_eval["pt_validation"]["bpb"])
        fallback = abs(bpb_drop) / max(1e-12, denom)
        if fallback > fallback_score:
            fallback_score = fallback
            fallback_pair = (left_tokens, right_tokens)
    adaptive = best_pair or fallback_pair or (ordered[0][0], ordered[-1][0])
    selected = sorted({*cfg.fixed_llc_checkpoint_tokens, *adaptive})
    return {
        "rule_frozen_at_utc": utc_now(),
        "no_final_llc_inspected": True,
        "primary_condition": "structured_pt_seed_a",
        "fixed_checkpoint_tokens": list(cfg.fixed_llc_checkpoint_tokens),
        "adaptive_metric": cfg.adaptive_metric,
        "adaptive_bracket_tokens": list(adaptive),
        "selected_checkpoint_tokens": selected,
        "selection_source": "behavioral metrics only; final LLC traces were not read or optimized",
    }


def initial_key() -> str:
    return checkpoint_name(0)


def final_key(cfg: FinalConfig) -> str:
    return checkpoint_name(cfg.target_tokens)


def bpb_delta(summary: dict[str, Any], cfg: FinalConfig, metric: str = "pt_validation") -> float:
    start = float(summary["evaluations"][initial_key()][metric]["bpb"])
    final = float(summary["evaluations"][final_key(cfg)][metric]["bpb"])
    return final - start


def decide_final_behavior(cfg: FinalConfig, condition_summaries: dict[str, Any]) -> dict[str, Any]:
    criteria: dict[str, Any] = {}
    metrics: dict[str, Any] = {}
    reasons: list[str] = []
    stable = all(bool(summary.get("stable", True)) for summary in condition_summaries.values())
    criteria["stable_no_nan_or_divergence"] = stable
    if not stable:
        reasons.append("at least one trajectory stopped early or produced non-finite loss")

    structured_a = condition_summaries.get("structured_pt_seed_a")
    if structured_a is not None:
        pt_delta = bpb_delta(structured_a, cfg, "pt_validation")
        en_delta = bpb_delta(structured_a, cfg, "english_retention")
        metrics["structured_pt_seed_a_pt_bpb_delta"] = pt_delta
        metrics["structured_pt_seed_a_english_bpb_delta"] = en_delta
        learned = math.isfinite(pt_delta) and pt_delta < -0.01
        criteria["structured_pt_seed_a_bpb_decreases"] = learned
        if not learned:
            reasons.append("structured Portuguese seed A validation BPB did not decrease")
        no_pt_gain_with_english_degrade = (not learned) and math.isfinite(en_delta) and en_delta > 0.01
        criteria["no_english_degrade_without_portuguese_gain"] = not no_pt_gain_with_english_degrade
        if no_pt_gain_with_english_degrade:
            reasons.append("English retention worsened without Portuguese validation gain")

    structured_b = condition_summaries.get("structured_pt_seed_b")
    if structured_b is not None:
        pt_delta_b = bpb_delta(structured_b, cfg, "pt_validation")
        metrics["structured_pt_seed_b_pt_bpb_delta"] = pt_delta_b
        learned_b = math.isfinite(pt_delta_b) and pt_delta_b < -0.01
        criteria["structured_pt_seed_b_bpb_decreases"] = learned_b
        if not learned_b:
            reasons.append("structured Portuguese seed B validation BPB did not decrease")

    shuffled = condition_summaries.get("shuffled_pt")
    if structured_a is not None and shuffled is not None:
        structured_final = float(structured_a["evaluations"][final_key(cfg)]["pt_validation"]["bpb"])
        shuffled_final = float(shuffled["evaluations"][final_key(cfg)]["pt_validation"]["bpb"])
        gap = shuffled_final - structured_final
        metrics["structured_pt_seed_a_final_bpb"] = structured_final
        metrics["shuffled_pt_final_bpb"] = shuffled_final
        metrics["structured_vs_shuffled_pt_bpb_gap"] = gap
        beats = math.isfinite(gap) and gap > 0.01
        criteria["structured_pt_seed_a_beats_shuffled"] = beats
        if not beats:
            reasons.append("structured Portuguese seed A did not beat shuffled Portuguese")

    ready_to_pass = set(FINAL_CONDITIONS).issubset(condition_summaries)
    failed_now = bool(reasons) and (
        "structured_pt_seed_a" in condition_summaries
        or set(FINAL_CONDITIONS).issubset(condition_summaries)
    )
    passed = ready_to_pass and not reasons
    return {
        "status": "passed" if passed else ("blocked" if failed_now else "partial"),
        "gate_decision": "proceed_to_llc" if passed else ("pivot" if failed_now else "continue"),
        "criteria": criteria,
        "metrics": metrics,
        "reasons": reasons,
        "next_bounded_action": (
            "Run the LLC campaign from the frozen selected checkpoint subset."
            if passed
            else "Route to diagnosis: learning rate/schedule, warmup, gradient clipping, token budget, model scale, tokenization, and data/evaluation."
        ),
    }


def update_cost_projection(
    output_dir: Path,
    cfg: FinalConfig,
    condition_summaries: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    completed = len(condition_summaries)
    observed_hours = sum(float(item["estimated_gpu_hours"]) for item in condition_summaries.values())
    mean_condition_hours = observed_hours / max(1, completed)
    remaining = max(0, len(FINAL_CONDITIONS) - completed)
    projected_phase_hours = observed_hours + mean_condition_hours * remaining
    projected_total_cost = cfg.starting_cumulative_cost_usd + projected_phase_hours * cfg.hourly_rate_usd
    projection = {
        "updated_utc": utc_now(),
        "status": status,
        "completed_conditions": list(condition_summaries),
        "remaining_conditions": [name for name in FINAL_CONDITIONS if name not in condition_summaries],
        "observed_phase_gpu_hours": observed_hours,
        "projected_phase_gpu_hours": projected_phase_hours,
        "hourly_rate_usd": cfg.hourly_rate_usd,
        "starting_cumulative_cost_usd": cfg.starting_cumulative_cost_usd,
        "projected_total_cost_usd": projected_total_cost,
        "hard_cap_usd": cfg.hard_cap_usd,
        "under_hard_cap": projected_total_cost <= cfg.hard_cap_usd,
    }
    write_json(output_dir / "cost_projection.json", projection)
    return projection


def write_phase_report(
    output_dir: Path,
    run_id: str,
    manifest: dict[str, Any],
    condition_summaries: dict[str, Any],
    llc_selection: dict[str, Any],
    cost_projection: dict[str, Any],
) -> None:
    lines = [
        "# Final Behavioral Training Phase Report",
        "",
        f"- Run ID: `{run_id}`",
        f"- Source commit: `{manifest['git_commit']}`",
        f"- Model: `{manifest['config']['model']}`",
        f"- Conditions: `{', '.join(condition_summaries)}`",
        "- Gate decision: `proceed_to_llc`",
        "",
        "## Evidence",
        "",
        f"- Manifest: `{output_dir / 'manifest.json'}`",
        f"- Frozen config: `{output_dir / 'frozen_config.json'}`",
        f"- Final data manifest: `{output_dir / 'data_splits' / 'split_manifest.json'}`",
        f"- Cost projection: `{output_dir / 'cost_projection.json'}`",
        f"- LLC checkpoint selection: `{output_dir / 'llc_checkpoint_selection.json'}`",
    ]
    for condition in condition_summaries:
        lines.append(f"- {condition} summary: `{output_dir / 'conditions' / condition / 'condition_summary.json'}`")
    lines.extend(["", "## Behavioral Metrics", ""])
    for condition, summary in condition_summaries.items():
        final_name = checkpoint_name(manifest["config"]["target_tokens"])
        final_eval = summary["evaluations"][final_name]
        lines.append(
            "- "
            f"{condition}: final PT BPB `{final_eval['pt_validation']['bpb']}`, "
            f"English BPB `{final_eval['english_retention']['bpb']}`, "
            f"grammar mean margin `{final_eval['grammar_margin']['mean_margin']}`"
        )
    lines.extend(
        [
            "",
            "## LLC Selection",
            "",
            f"- Fixed tokens: `{llc_selection['fixed_checkpoint_tokens']}`",
            f"- Adaptive bracket tokens: `{llc_selection['adaptive_bracket_tokens']}`",
            f"- Selected tokens: `{llc_selection['selected_checkpoint_tokens']}`",
            "- Final LLC inspected: `False`",
            "",
            "## Runtime And Cost",
            "",
            f"- Observed phase GPU-hours: `{cost_projection['observed_phase_gpu_hours']:.4f}`",
            f"- Projected phase GPU-hours: `{cost_projection['projected_phase_gpu_hours']:.4f}`",
            f"- Projected total cost USD: `${cost_projection['projected_total_cost_usd']:.4f}`",
            f"- Hard cap USD: `${cost_projection['hard_cap_usd']:.2f}`",
            "",
            "## Uncertainty",
            "",
            "- The final training data reuses the immutable pilot split artifacts and cycles them to the target-token budget.",
            "- Behavior checkpoint spacing limits transition localization to adjacent saved checkpoints.",
            "- No final LLC traces were inspected or optimized during this phase.",
            "",
            "## Failure Modes",
            "",
            "- Repeated small split examples can overfit; report train/eval split hashes and treat this as a narrow final trajectory.",
            "- Checkpoint serialization dominates wall time more than the synthetic throughput benchmark suggests.",
            "- If the next LLC campaign finds unstable localized chains, report diagnostics rather than a scalar-only estimate.",
            "",
            "## Gate Decision",
            "",
            "`proceed_to_llc`. Behavior outputs and checkpoint-selection rules are frozen.",
            "",
        ]
    )
    (output_dir / "phase_report.md").write_text("\n".join(lines), encoding="utf-8")


def write_blocked_phase_report(
    output_dir: Path,
    run_id: str,
    manifest: dict[str, Any],
    condition_summaries: dict[str, Any],
    decision: dict[str, Any],
    cost_projection: dict[str, Any],
) -> None:
    lines = [
        "# Final Behavioral Training Phase Report",
        "",
        f"- Run ID: `{run_id}`",
        f"- Source commit: `{manifest['git_commit']}`",
        f"- Model: `{manifest['config']['model']}`",
        "- Gate decision: `pivot`",
        "- Status: `blocked`",
        "",
        "## Evidence",
        "",
        f"- Manifest: `{output_dir / 'manifest.json'}`",
        f"- Frozen config: `{output_dir / 'frozen_config.json'}`",
        f"- Final data manifest: `{output_dir / 'data_splits' / 'split_manifest.json'}`",
        f"- Cost projection: `{output_dir / 'cost_projection.json'}`",
    ]
    for condition in condition_summaries:
        lines.append(f"- {condition} summary: `{output_dir / 'conditions' / condition / 'condition_summary.json'}`")
    lines.extend(
        [
            "",
            "## Scientific Validity Gate",
            "",
            f"- Criteria: `{json.dumps(decision['criteria'], sort_keys=True)}`",
            f"- Metrics: `{json.dumps(decision['metrics'], sort_keys=True)}`",
            f"- Failure reasons: `{'; '.join(decision['reasons'])}`",
            "",
            "## Runtime And Cost",
            "",
            f"- Observed phase GPU-hours: `{cost_projection['observed_phase_gpu_hours']:.4f}`",
            f"- Projected phase GPU-hours: `{cost_projection['projected_phase_gpu_hours']:.4f}`",
            f"- Projected total cost USD: `${cost_projection['projected_total_cost_usd']:.4f}`",
            f"- Hard cap USD: `${cost_projection['hard_cap_usd']:.2f}`",
            "",
            "## Next Bounded Action",
            "",
            decision["next_bounded_action"],
            "",
        ]
    )
    (output_dir / "phase_report.md").write_text("\n".join(lines), encoding="utf-8")


def write_state_files(output_dir: Path, run_id: str, manifest: dict[str, Any], cost_projection: dict[str, Any]) -> None:
    status = {
        "phase": "02_final_training",
        "gate": "behavior_complete_llc_selection_frozen",
        "last_updated": utc_now(),
        "latest_run_id": run_id,
        "latest_run_dir": str(output_dir),
        "git_commit": manifest["git_commit"],
        "prior_pilot_run_id": "scientific_pilot_20260620T053047Z",
        "structured_gate_decision": "proceed_to_llc",
        "conditions_completed": list(FINAL_CONDITIONS),
        "model": manifest["config"]["model"],
        "target_tokens": manifest["config"]["target_tokens"],
        "checkpoint_tokens": manifest["config"]["checkpoint_tokens"],
        "estimated_cost_usd": cost_projection["observed_phase_gpu_hours"] * manifest["config"]["hourly_rate_usd"],
        "projected_total_cost_usd": cost_projection["projected_total_cost_usd"],
        "hard_cap_usd": cost_projection["hard_cap_usd"],
        "requires_human_approval": False,
        "approval_reason": "Standing unattended orchestrator pre-authorization recorded in state/decision_log.md.",
        "evidence_paths": {
            "phase_report": str(output_dir / "phase_report.md"),
            "manifest": str(output_dir / "manifest.json"),
            "data_manifest": str(output_dir / "data_splits" / "split_manifest.json"),
            "cost_projection": str(output_dir / "cost_projection.json"),
            "llc_checkpoint_selection": str(output_dir / "llc_checkpoint_selection.json"),
            "bounded_job_dir": str(output_dir / "jobs" / "final_behavior"),
        },
        "next_action": "Run the LLC campaign using the frozen behavior outputs and selected checkpoint subset; do not retune per checkpoint.",
    }
    write_json(Path("state/current_status.json"), status)

    timestamp = utc_now()
    decision_entry = f"""
## {timestamp} - TinyStories-8M final behavioral trajectories complete

Decision: proceed to the LLC campaign with behavior outputs and checkpoint-selection rules frozen. No final LLC traces were inspected or optimized during final behavioral training.

Evidence: `{output_dir / 'manifest.json'}`, `{output_dir / 'data_splits' / 'split_manifest.json'}`, condition summaries under `{output_dir / 'conditions'}`, `{output_dir / 'cost_projection.json'}`, and `{output_dir / 'llc_checkpoint_selection.json'}`.

Conditions: structured Portuguese seed A, token-shuffled Portuguese, matched English, and structured Portuguese seed B completed in the predeclared priority order using full-parameter AdamW continued pretraining on `roneneldan/TinyStories-8M`.

Runtime/cost: observed phase GPU-hours `{cost_projection['observed_phase_gpu_hours']:.4f}`; projected total cost `${cost_projection['projected_total_cost_usd']:.4f}` against hard cap `${cost_projection['hard_cap_usd']:.2f}`.

Gate decision: proceed_to_llc. Next bounded action: run the LLC campaign from the frozen selected checkpoint subset.
"""
    with Path("state/decision_log.md").open("a", encoding="utf-8") as handle:
        handle.write(decision_entry)

    with Path("state/experiment_registry.csv").open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                run_id,
                "02_final_training",
                "passed",
                "__".join(FINAL_CONDITIONS),
                manifest["config"]["model"],
                manifest["config"]["seed"],
                manifest["git_commit"],
                str(output_dir / "frozen_config.json"),
                manifest["start_utc"],
                manifest["end_utc"],
                f"{cost_projection['observed_phase_gpu_hours']:.4f}",
                f"{cost_projection['observed_phase_gpu_hours'] * manifest['config']['hourly_rate_usd']:.4f}",
                str(output_dir),
                "Final behavior trajectories complete; checkpoint hashes and every-checkpoint BPB/grammar metrics recorded; LLC selection frozen without LLC inspection.",
            ]
        )


def write_blocked_state_files(
    output_dir: Path,
    run_id: str,
    manifest: dict[str, Any],
    condition_summaries: dict[str, Any],
    decision: dict[str, Any],
    cost_projection: dict[str, Any],
) -> None:
    status = {
        "phase": "02_final_training",
        "gate": "pivot",
        "status": "blocked",
        "last_updated": utc_now(),
        "latest_run_id": run_id,
        "latest_run_dir": str(output_dir),
        "git_commit": manifest["git_commit"],
        "conditions_completed": list(condition_summaries),
        "model": manifest["config"]["model"],
        "target_tokens": manifest["config"]["target_tokens"],
        "scientific_validity_gate": decision,
        "estimated_cost_usd": cost_projection["observed_phase_gpu_hours"] * manifest["config"]["hourly_rate_usd"],
        "projected_total_cost_usd": cost_projection["projected_total_cost_usd"],
        "hard_cap_usd": cost_projection["hard_cap_usd"],
        "requires_human_approval": False,
        "approval_reason": "Operator greenlight is recorded, but this run is blocked by the scientific validity gate.",
        "evidence_paths": {
            "phase_report": str(output_dir / "phase_report.md"),
            "manifest": str(output_dir / "manifest.json"),
            "data_manifest": str(output_dir / "data_splits" / "split_manifest.json"),
            "cost_projection": str(output_dir / "cost_projection.json"),
            "conditions": str(output_dir / "conditions"),
            "bounded_job_dir": str(output_dir / "jobs" / "final_behavior"),
        },
        "next_action": decision["next_bounded_action"],
    }
    write_json(Path("state/current_status.json"), status)

    entry = f"""
## {utc_now()} - TinyStories-8M final behavioral trajectories blocked

Decision: pivot. The scientific validity gate failed, so this run is a training/pipeline failure rather than a reportable null or smooth result.

Evidence: `{output_dir / 'manifest.json'}`, `{output_dir / 'phase_report.md'}`, `{output_dir / 'data_splits' / 'split_manifest.json'}`, condition summaries under `{output_dir / 'conditions'}`, and `{output_dir / 'cost_projection.json'}`.

Completed conditions: {', '.join(condition_summaries)}.

Validity gate reasons: {'; '.join(decision['reasons'])}.

Runtime/cost: observed phase GPU-hours `{cost_projection['observed_phase_gpu_hours']:.4f}`; projected total cost `${cost_projection['projected_total_cost_usd']:.4f}` against hard cap `${cost_projection['hard_cap_usd']:.2f}`.

Gate decision: pivot. Next bounded action: {decision['next_bounded_action']}
"""
    with Path("state/decision_log.md").open("a", encoding="utf-8") as handle:
        handle.write(entry)

    with Path("state/experiment_registry.csv").open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                run_id,
                "02_final_training",
                "blocked",
                "__".join(condition_summaries),
                manifest["config"]["model"],
                manifest["config"]["seed"],
                manifest["git_commit"],
                str(output_dir / "frozen_config.json"),
                manifest["start_utc"],
                manifest["end_utc"],
                f"{cost_projection['observed_phase_gpu_hours']:.4f}",
                f"{cost_projection['observed_phase_gpu_hours'] * manifest['config']['hourly_rate_usd']:.4f}",
                str(output_dir),
                "Scientific validity gate failed: " + "; ".join(decision["reasons"]),
            ]
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="TinyStories-8M final behavioral trajectories")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument(
        "--only-conditions",
        default="",
        help="Comma-separated subset of FINAL_CONDITIONS to train (e.g. structured_pt_seed_b). Reuses "
        "existing prepared data splits, writes only those conditions, and skips the full-run behavioral "
        "gate / LLC-selection finalization (and does not overwrite the original manifest.json). Use for "
        "adding a replication seed to an existing run without retraining or clobbering the other conditions.",
    )
    args = parser.parse_args()

    only_set = [c.strip() for c in args.only_conditions.split(",") if c.strip()]
    bad = [c for c in only_set if c not in FINAL_CONDITIONS]
    if bad:
        raise SystemExit(f"--only-conditions has unknown conditions {bad}; valid: {list(FINAL_CONDITIONS)}")
    targets = [c for c in FINAL_CONDITIONS if (not only_set) or c in only_set]
    subset_run = bool(only_set)

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    cfg = read_config(args.config)
    if cfg.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frozen_config_path = args.output_dir / "frozen_config.json"
    shutil.copy2(args.config, frozen_config_path)
    frozen_config_sha256 = sha256_file(frozen_config_path)
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

    prepared_manifest = args.output_dir / "data_splits" / "split_manifest.json"
    data = load_prepared_data(args.output_dir, cfg) if prepared_manifest.exists() else prepare_data(args.output_dir, tokenizer, cfg)
    grammar_pairs = load_grammar_pairs(cfg.grammar_csv)
    grammar_sanity = grammar_sanity_checks(grammar_pairs)
    write_json(args.output_dir / "grammar_sanity_checks.json", grammar_sanity)
    manifest = {
        "run_kind": "tinystories_8m_final_behavioral_training",
        "scientific_scope": "TinyStories-8M full-parameter continued pretraining; behavior only; no final LLC inspection.",
        "start_utc": start_utc,
        "git_commit": git_commit(),
        "git_status_short_at_start": git_status_short(),
        "config": cfg.as_dict(),
        "frozen_config": str(frozen_config_path),
        "frozen_config_sha256": frozen_config_sha256,
        "package_versions": package_versions(),
        "device": cfg.device,
        "gpu": torch.cuda.get_device_name(0) if cfg.device == "cuda" else None,
        "torch_cuda_available": bool(torch.cuda.is_available()),
        "parameter_count": parameter_count,
        "tokenizer_vocab_sha256": stable_json_hash(tokenizer.get_vocab()),
        "data_split_manifest": str(args.output_dir / "data_splits" / "split_manifest.json"),
        "checkpoint_plan": checkpoint_plan(cfg),
    }
    # A subset run (replication seed added to an existing run) must not clobber the original manifest.
    manifest_path = args.output_dir / (
        "manifest.json" if not subset_run else "manifest_only_" + "_".join(targets) + ".json"
    )
    write_json(manifest_path, manifest)
    update_cost_projection(args.output_dir, cfg, {}, "prepared")
    if args.prepare_only:
        manifest.update({"end_utc": utc_now(), "exit_status": "prepared_only"})
        write_json(manifest_path, manifest)
        print(json.dumps({"prepared": True, "manifest": str(args.output_dir / "manifest.json")}, indent=2))
        return 0

    condition_summaries: dict[str, Any] = {}
    for condition in targets:
        projection = update_cost_projection(args.output_dir, cfg, condition_summaries, f"before_{condition}")
        if not projection["under_hard_cap"]:
            manifest.update({"end_utc": utc_now(), "exit_status": "stopped_hard_budget_projection"})
            write_json(args.output_dir / "manifest.json", manifest)
            raise RuntimeError("Projected total cost exceeds hard cap before next trajectory")
        sequences = (
            data["structured_chunks"]
            if condition in {"structured_pt_seed_a", "structured_pt_seed_b"}
            else data["shuffled_chunks"]
            if condition == "shuffled_pt"
            else data["matched_en_chunks"]
        )
        summary = run_condition(
            args.output_dir,
            condition,
            tokenizer,
            sequences,
            data["splits"],
            grammar_pairs,
            cfg,
        )
        condition_summaries[condition] = summary
        projection = update_cost_projection(args.output_dir, cfg, condition_summaries, f"completed_{condition}")
        if not projection["under_hard_cap"]:
            manifest.update({"end_utc": utc_now(), "exit_status": "stopped_hard_budget_projection"})
            write_json(args.output_dir / "manifest.json", manifest)
            raise RuntimeError("Projected total cost exceeds hard cap after trajectory")
        if subset_run:
            continue  # subset run: skip the full-run behavioral gate (it assumes all conditions present)
        decision = decide_final_behavior(cfg, condition_summaries)
        write_json(args.output_dir / "scientific_validity_gate.json", decision)
        if decision["gate_decision"] == "pivot":
            wall_seconds = time.perf_counter() - run_start
            manifest.update(
                {
                    "end_utc": utc_now(),
                    "wall_seconds": wall_seconds,
                    "estimated_gpu_hours": wall_seconds / 3600.0,
                    "estimated_cost_usd": wall_seconds / 3600.0 * cfg.hourly_rate_usd,
                    "condition_summaries": {
                        name: str(args.output_dir / "conditions" / name / "condition_summary.json")
                        for name in condition_summaries
                    },
                    "scientific_validity_gate": decision,
                    "output_tree_size_bytes": path_size_bytes(args.output_dir),
                    "exit_status": "blocked",
                }
            )
            write_json(args.output_dir / "manifest.json", manifest)
            cost_projection = update_cost_projection(args.output_dir, cfg, condition_summaries, "blocked")
            write_blocked_phase_report(args.output_dir, args.output_dir.name, manifest, condition_summaries, decision, cost_projection)
            write_blocked_state_files(args.output_dir, args.output_dir.name, manifest, condition_summaries, decision, cost_projection)
            print(json.dumps({"status": "blocked", "gate_decision": "pivot", "decision": decision}, indent=2))
            return 2

    if subset_run:
        # Minimal finalization for a subset (e.g. replication-seed) run: the per-condition
        # condition_summary.json files (what the LLC campaign reads) are already written by run_condition.
        # We deliberately skip the full-run gate / LLC-selection that assumes all four conditions.
        wall_seconds = time.perf_counter() - run_start
        manifest.update(
            {
                "end_utc": utc_now(),
                "wall_seconds": wall_seconds,
                "estimated_gpu_hours": wall_seconds / 3600.0,
                "estimated_cost_usd": wall_seconds / 3600.0 * cfg.hourly_rate_usd,
                "only_conditions": targets,
                "condition_summaries": {
                    name: str(args.output_dir / "conditions" / name / "condition_summary.json")
                    for name in condition_summaries
                },
                "exit_status": "completed_subset",
            }
        )
        write_json(manifest_path, manifest)
        print(json.dumps({"status": "completed_subset", "conditions": list(condition_summaries),
                          "manifest": str(manifest_path)}, indent=2))
        return 0

    decision = decide_final_behavior(cfg, condition_summaries)
    write_json(args.output_dir / "scientific_validity_gate.json", decision)
    if decision["gate_decision"] != "proceed_to_llc":
        wall_seconds = time.perf_counter() - run_start
        manifest.update(
            {
                "end_utc": utc_now(),
                "wall_seconds": wall_seconds,
                "estimated_gpu_hours": wall_seconds / 3600.0,
                "estimated_cost_usd": wall_seconds / 3600.0 * cfg.hourly_rate_usd,
                "condition_summaries": {
                    name: str(args.output_dir / "conditions" / name / "condition_summary.json")
                    for name in condition_summaries
                },
                "scientific_validity_gate": decision,
                "output_tree_size_bytes": path_size_bytes(args.output_dir),
                "exit_status": "blocked",
            }
        )
        write_json(args.output_dir / "manifest.json", manifest)
        cost_projection = update_cost_projection(args.output_dir, cfg, condition_summaries, "blocked")
        write_blocked_phase_report(args.output_dir, args.output_dir.name, manifest, condition_summaries, decision, cost_projection)
        write_blocked_state_files(args.output_dir, args.output_dir.name, manifest, condition_summaries, decision, cost_projection)
        print(json.dumps({"status": "blocked", "gate_decision": "pivot", "decision": decision}, indent=2))
        return 2

    llc_selection = select_llc_checkpoints(cfg, condition_summaries["structured_pt_seed_a"])
    write_json(args.output_dir / "llc_checkpoint_selection.json", llc_selection)
    wall_seconds = time.perf_counter() - run_start
    manifest.update(
        {
            "end_utc": utc_now(),
            "wall_seconds": wall_seconds,
            "estimated_gpu_hours": wall_seconds / 3600.0,
            "estimated_cost_usd": wall_seconds / 3600.0 * cfg.hourly_rate_usd,
            "condition_summaries": {
                condition: str(args.output_dir / "conditions" / condition / "condition_summary.json")
                for condition in FINAL_CONDITIONS
            },
            "llc_checkpoint_selection": str(args.output_dir / "llc_checkpoint_selection.json"),
            "scientific_validity_gate": decision,
            "output_tree_size_bytes": path_size_bytes(args.output_dir),
            "exit_status": "completed",
        }
    )
    write_json(args.output_dir / "manifest.json", manifest)
    cost_projection = update_cost_projection(args.output_dir, cfg, condition_summaries, "completed")
    write_phase_report(args.output_dir, args.output_dir.name, manifest, condition_summaries, llc_selection, cost_projection)
    write_state_files(args.output_dir, args.output_dir.name, manifest, cost_projection)
    print(
        json.dumps(
            {
                "status": "completed",
                "run_id": args.output_dir.name,
                "cost_projection": cost_projection,
                "llc_checkpoint_selection": llc_selection,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
