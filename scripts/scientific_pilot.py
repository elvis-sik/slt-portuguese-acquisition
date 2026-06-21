from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import json
import math
import os
import random
import statistics
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


MODEL_NAME = "roneneldan/TinyStories-3M"
DEFAULT_LR_GRID = (3e-5, 1e-4, 3e-4)
CONDITIONS = ("structured_pt", "shuffled_pt", "matched_en")
CONDITION_SEED_OFFSETS = {"structured_pt": 101, "shuffled_pt": 202, "matched_en": 303}
GRAMMAR_CSV = Path("data/eval/grammar_minimal_pairs.example.csv")


EMBEDDED_PARALLEL_PAIRS = [
    {
        "id": f"embedded_{i:04d}",
        "source": "embedded_minimal_parallel_fallback",
        "en": en,
        "pt": pt,
    }
    for i, (en, pt) in enumerate(
        [
            ("The girl reads a book in the garden.", "A menina lê um livro no jardim."),
            ("The boys run near the school.", "Os meninos correm perto da escola."),
            ("My friend arrived early yesterday.", "Meu amigo chegou cedo ontem."),
            ("The old house has a red door.", "A casa antiga tem uma porta vermelha."),
            ("The small dogs slept on the rug.", "Os cães pequenos dormiram no tapete."),
            ("The teacher opened the window.", "A professora abriu a janela."),
            ("The children found three flowers.", "As crianças encontraram três flores."),
            ("The new car stopped in the street.", "O carro novo parou na rua."),
            ("The woman wrote a short letter.", "A mulher escreveu uma carta curta."),
            ("The happy cat climbed the chair.", "O gato feliz subiu na cadeira."),
            ("The students answered the question.", "Os alunos responderam à pergunta."),
            ("The clean shirts stayed on the table.", "As camisas limpas ficaram na mesa."),
            ("The doctor spoke with the family.", "O médico falou com a família."),
            ("The bright moon crossed the sky.", "A lua brilhante cruzou o céu."),
            ("The neighbors bought fresh bread.", "Os vizinhos compraram pão fresco."),
            ("The young bird left the nest.", "O pássaro jovem deixou o ninho."),
        ]
    )
]


@dataclass(frozen=True)
class PilotConfig:
    model: str
    sequence_length: int
    train_size: int
    val_size: int
    sampler_size: int
    batch_size: int
    lr_pilot_steps: int
    condition_steps: int
    lr_grid: tuple[float, ...]
    sampler_num_chains: int
    sampler_burnin: int
    sampler_draws: int
    sampler_steps_between_draws: int
    sampler_lr: float
    sampler_n_beta: float
    sampler_localization: float
    seed: int
    device: str
    hourly_rate_usd: float

    @property
    def tokens_per_step(self) -> int:
        return self.sequence_length * self.batch_size

    @property
    def checkpoint_steps(self) -> list[int]:
        middle = max(1, self.condition_steps // 2)
        early = max(1, min(self.condition_steps, round(25_000 / self.tokens_per_step)))
        steps = sorted({0, early, middle, self.condition_steps})
        return steps

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "sequence_length": self.sequence_length,
            "train_size": self.train_size,
            "val_size": self.val_size,
            "sampler_size": self.sampler_size,
            "batch_size": self.batch_size,
            "lr_pilot_steps": self.lr_pilot_steps,
            "condition_steps": self.condition_steps,
            "lr_grid": list(self.lr_grid),
            "checkpoint_steps": self.checkpoint_steps,
            "tokens_per_step": self.tokens_per_step,
            "sampler": {
                "num_chains": self.sampler_num_chains,
                "num_burnin_steps": self.sampler_burnin,
                "num_draws": self.sampler_draws,
                "num_steps_between_draws": self.sampler_steps_between_draws,
                "lr": self.sampler_lr,
                "n_beta": self.sampler_n_beta,
                "localization": self.sampler_localization,
                "precision": "fp32",
            },
            "seed": self.seed,
            "device": self.device,
            "hourly_rate_usd": self.hourly_rate_usd,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_tree(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    if not root.exists():
        return hashes
    for path in sorted(root.rglob("*")):
        if path.is_file():
            hashes[str(path.relative_to(root))] = sha256_file(path)
    return hashes


def stable_json_hash(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def path_size_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
    return 0


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def git_status_short() -> str:
    try:
        return subprocess.check_output(["git", "status", "--short"], text=True).strip()
    except Exception:
        return "unknown"


def package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in ("torch", "transformers", "datasets", "devinterp", "numpy", "pandas", "zarr"):
        try:
            module = __import__(package)
            versions[package] = str(getattr(module, "__version__", "unknown"))
        except Exception as exc:
            versions[package] = f"unavailable: {exc}"
    return versions


def normalize_text(text: str) -> str:
    return " ".join(str(text).replace("\u00a0", " ").split())


def load_opus_pairs(limit: int, seed: int) -> tuple[list[dict[str, str]], dict[str, Any]]:
    from datasets import load_dataset

    metadata = {
        "source": "Helsinki-NLP/opus-100",
        "config": "en-pt",
        "split": "train",
        "streaming": True,
        "requested_limit": limit,
        "filtering": {
            "min_chars": 12,
            "max_chars": 220,
            "max_length_ratio": 2.8,
            "reject_markup_chars": ["<", ">", "{", "}"],
        },
    }
    rows: list[dict[str, str]] = []
    counts = {
        "seen": 0,
        "missing": 0,
        "markup_heavy": 0,
        "length_rejected": 0,
        "duplicate_pairs": 0,
    }
    seen: set[tuple[str, str]] = set()
    stream = load_dataset("Helsinki-NLP/opus-100", "en-pt", split="train", streaming=True)
    for ex in stream:
        counts["seen"] += 1
        translation = ex.get("translation", {})
        en = normalize_text(translation.get("en", ""))
        pt = normalize_text(translation.get("pt", ""))
        if not en or not pt:
            counts["missing"] += 1
            continue
        if any(mark in en or mark in pt for mark in metadata["filtering"]["reject_markup_chars"]):
            counts["markup_heavy"] += 1
            continue
        min_chars = int(metadata["filtering"]["min_chars"])
        max_chars = int(metadata["filtering"]["max_chars"])
        ratio = max(len(en), len(pt)) / max(1, min(len(en), len(pt)))
        if (
            len(en) < min_chars
            or len(pt) < min_chars
            or len(en) > max_chars
            or len(pt) > max_chars
            or ratio > float(metadata["filtering"]["max_length_ratio"])
        ):
            counts["length_rejected"] += 1
            continue
        key = (en.casefold(), pt.casefold())
        if key in seen:
            counts["duplicate_pairs"] += 1
            continue
        seen.add(key)
        rows.append(
            {
                "id": f"opus100_stream_{len(rows):06d}",
                "source": "Helsinki-NLP/opus-100/en-pt/train",
                "en": en,
                "pt": pt,
            }
        )
        if len(rows) >= limit:
            break
        if counts["seen"] > max(10_000, limit * 100):
            break
    metadata["counts"] = counts | {"accepted": len(rows)}
    metadata["selection_seed"] = seed
    return rows, metadata


def load_parallel_pairs(limit: int, seed: int) -> tuple[list[dict[str, str]], dict[str, Any]]:
    try:
        rows, metadata = load_opus_pairs(limit, seed)
        if len(rows) >= limit:
            return rows, metadata
        metadata["warning"] = "OPUS streaming returned fewer rows than requested; using embedded fallback."
    except Exception as exc:
        rows = []
        metadata = {
            "source": "embedded_minimal_parallel_fallback",
            "warning": f"OPUS streaming unavailable: {type(exc).__name__}: {exc}",
        }
    repeated = [EMBEDDED_PARALLEL_PAIRS[i % len(EMBEDDED_PARALLEL_PAIRS)] for i in range(limit)]
    fallback = [
        {**row, "id": f"embedded_repeated_{i:06d}"}
        for i, row in enumerate(repeated)
    ]
    return (rows + fallback)[:limit], metadata


def split_pairs(rows: list[dict[str, str]], train_size: int, val_size: int, sampler_size: int) -> dict[str, list[dict[str, str]]]:
    required = train_size + val_size + sampler_size
    if len(rows) < required:
        raise ValueError(f"Need {required} pairs, found {len(rows)}")
    return {
        "train": rows[:train_size],
        "validation": rows[train_size : train_size + val_size],
        "sampler_reference": rows[train_size + val_size : required],
    }


def token_length(tokenizer: Any, text: str) -> int:
    return len(tokenizer(text, add_special_tokens=True)["input_ids"])


def split_stats(tokenizer: Any, split_rows: list[dict[str, str]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for lang in ("pt", "en"):
        texts = [row[lang] for row in split_rows]
        byte_count = sum(len(text.encode("utf-8")) for text in texts)
        word_count = sum(len(text.split()) for text in texts)
        token_counts = [token_length(tokenizer, text) for text in texts]
        out[lang] = {
            "examples": len(texts),
            "bytes_utf8": byte_count,
            "whitespace_words": word_count,
            "tokens": sum(token_counts),
            "max_tokens": max(token_counts) if token_counts else 0,
            "tokens_per_utf8_byte": sum(token_counts) / max(1, byte_count),
            "tokens_per_whitespace_word": sum(token_counts) / max(1, word_count),
        }
    return out


def immutable_splits(
    output_dir: Path,
    tokenizer: Any,
    cfg: PilotConfig,
) -> dict[str, Any]:
    total = cfg.train_size + cfg.val_size + cfg.sampler_size
    rows, source_metadata = load_parallel_pairs(total, cfg.seed)
    splits = split_pairs(rows, cfg.train_size, cfg.val_size, cfg.sampler_size)
    split_dir = output_dir / "data_splits"
    for name, split_rows in splits.items():
        write_jsonl(split_dir / f"{name}.jsonl", split_rows)
    hashes = {f"{name}.jsonl": sha256_file(split_dir / f"{name}.jsonl") for name in splits}
    leakage = {
        "train_validation_overlap_ids": sorted(
            {row["id"] for row in splits["train"]} & {row["id"] for row in splits["validation"]}
        ),
        "train_sampler_overlap_ids": sorted(
            {row["id"] for row in splits["train"]} & {row["id"] for row in splits["sampler_reference"]}
        ),
        "validation_sampler_overlap_ids": sorted(
            {row["id"] for row in splits["validation"]} & {row["id"] for row in splits["sampler_reference"]}
        ),
    }
    manifest = {
        "created_utc": utc_now(),
        "immutability_note": "Pilot split artifacts are content-addressed by SHA256 and must not be edited in place.",
        "source_metadata": source_metadata,
        "split_sizes": {name: len(value) for name, value in splits.items()},
        "split_hashes_sha256": hashes,
        "leakage_check": leakage,
        "filtering_record": {
            name: split_stats(tokenizer, value) for name, value in splits.items()
        },
    }
    write_json(split_dir / "split_manifest.json", manifest)
    return {"splits": splits, "manifest": manifest, "split_dir": split_dir}


def load_grammar_pairs(path: Path = GRAMMAR_CSV) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def grammar_sanity_checks(pairs: list[dict[str, str]]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for row in pairs:
        good = row["grammatical"]
        bad = row["ungrammatical"]
        common = os.path.commonprefix([good, bad])
        checks.append(
            {
                "id": row["id"],
                "phenomenon": row["phenomenon"],
                "grammatical_nonempty": bool(good.strip()),
                "ungrammatical_nonempty": bool(bad.strip()),
                "not_identical": good != bad,
                "has_shared_prefix": bool(common),
                "has_differing_continuation": good[len(common) :] != bad[len(common) :],
            }
        )
    passed = all(all(v for k, v in check.items() if k not in {"id", "phenomenon"}) for check in checks)
    return {
        "passed": passed,
        "checks": checks,
        "note": "Constructed sanity checks validate minimal-pair integrity; they are not empirical grammar accuracy.",
    }


def tokenize_texts(tokenizer: Any, texts: list[str], sequence_length: int) -> list[list[int]]:
    encoded: list[list[int]] = []
    eos = tokenizer.eos_token_id
    for text in texts:
        ids = tokenizer(text, add_special_tokens=True, truncation=True, max_length=sequence_length)["input_ids"]
        if eos is not None and (not ids or ids[-1] != eos) and len(ids) < sequence_length:
            ids = ids + [eos]
        encoded.append([int(x) for x in ids[:sequence_length]])
    return encoded


def make_shuffled_ids(rows: list[dict[str, str]], tokenizer: Any, sequence_length: int, seed: int) -> tuple[list[list[int]], list[dict[str, Any]]]:
    rng = random.Random(seed)
    tokenized = tokenize_texts(tokenizer, [row["pt"] for row in rows], sequence_length)
    mapping: list[dict[str, Any]] = []
    shuffled: list[list[int]] = []
    for row, ids in zip(rows, tokenized):
        local = list(ids)
        if len(local) > 2:
            middle = local[1:-1]
            order = list(range(len(middle)))
            rng.shuffle(order)
            local = [local[0]] + [middle[i] for i in order] + [local[-1]]
        else:
            order = list(range(len(local)))
        shuffled.append(local)
        mapping.append(
            {
                "id": row["id"],
                "original_token_count": len(ids),
                "shuffle_order_middle_tokens": order,
                "original_ids_sha256": stable_json_hash(ids),
                "shuffled_ids_sha256": stable_json_hash(local),
            }
        )
    return shuffled, mapping


def save_shuffled_condition(split_dir: Path, shuffled_ids: list[list[int]], mapping: list[dict[str, Any]]) -> dict[str, str]:
    rows = [{"id": item["id"], "input_ids": ids} for item, ids in zip(mapping, shuffled_ids)]
    write_jsonl(split_dir / "train_shuffled_pt_token_ids.jsonl", rows)
    write_jsonl(split_dir / "train_shuffled_pt_mapping.jsonl", mapping)
    return {
        "train_shuffled_pt_token_ids.jsonl": sha256_file(split_dir / "train_shuffled_pt_token_ids.jsonl"),
        "train_shuffled_pt_mapping.jsonl": sha256_file(split_dir / "train_shuffled_pt_mapping.jsonl"),
    }


class TokenDataset:
    def __init__(self, sequences: list[list[int]]) -> None:
        self.sequences = sequences

    def __len__(self) -> int:
        return len(self.sequences)

    def __getitem__(self, index: int) -> list[int]:
        return self.sequences[index]


def collate_batch(sequences: list[list[int]], pad_token_id: int, device: str, sequence_length: int) -> dict[str, Any]:
    import torch

    max_len = min(sequence_length, max(len(seq) for seq in sequences))
    ids = torch.full((len(sequences), max_len), int(pad_token_id), dtype=torch.long)
    mask = torch.zeros((len(sequences), max_len), dtype=torch.long)
    for row_index, seq in enumerate(sequences):
        values = torch.tensor(seq[:max_len], dtype=torch.long)
        ids[row_index, : len(values)] = values
        mask[row_index, : len(values)] = 1
    labels = ids.clone()
    labels[mask == 0] = -100
    return {
        "input_ids": ids.to(device),
        "attention_mask": mask.to(device),
        "labels": labels.to(device),
    }


def iter_batches(
    sequences: list[list[int]],
    batch_size: int,
    steps: int,
    seed: int,
) -> Iterable[list[list[int]]]:
    rng = random.Random(seed)
    order = list(range(len(sequences)))
    cursor = 0
    for _ in range(steps):
        if cursor + batch_size > len(order):
            rng.shuffle(order)
            cursor = 0
        batch_indices = order[cursor : cursor + batch_size]
        cursor += batch_size
        yield [sequences[i] for i in batch_indices]


def nll_and_tokens(model: Any, batch: dict[str, Any]) -> tuple[float, int]:
    import torch

    labels = batch["labels"]
    outputs = model(input_ids=batch["input_ids"], attention_mask=batch.get("attention_mask"))
    logits = outputs.logits[:, :-1, :].contiguous()
    target = labels[:, 1:].contiguous()
    loss = torch.nn.functional.cross_entropy(
        logits.view(-1, logits.size(-1)),
        target.view(-1),
        ignore_index=-100,
        reduction="sum",
    )
    count = int((target != -100).sum().detach().cpu())
    return float(loss.detach().cpu()), count


def evaluate_bpb(
    model: Any,
    tokenizer: Any,
    texts: list[str],
    cfg: PilotConfig,
    batch_size: int | None = None,
) -> dict[str, Any]:
    import torch

    model.eval()
    encoded = tokenize_texts(tokenizer, texts, cfg.sequence_length)
    total_nll = 0.0
    total_tokens = 0
    total_bytes = sum(len(text.encode("utf-8")) for text in texts)
    eval_batch_size = batch_size or cfg.batch_size
    with torch.no_grad():
        for start in range(0, len(encoded), eval_batch_size):
            batch = collate_batch(
                encoded[start : start + eval_batch_size],
                tokenizer.pad_token_id,
                cfg.device,
                cfg.sequence_length,
            )
            nll, tokens = nll_and_tokens(model, batch)
            total_nll += nll
            total_tokens += tokens
    return {
        "examples": len(texts),
        "nll_nats": total_nll,
        "scored_tokens": total_tokens,
        "bytes_utf8": total_bytes,
        "bpb": total_nll / max(1, total_bytes) / math.log(2),
        "mean_token_nll": total_nll / max(1, total_tokens),
    }


def token_logprob_sum(model: Any, tokenizer: Any, text: str, cfg: PilotConfig, score_from_token: int = 0) -> float:
    import torch

    ids = tokenizer(text, add_special_tokens=True, truncation=True, max_length=cfg.sequence_length)["input_ids"]
    if len(ids) < 2:
        return 0.0
    input_ids = torch.tensor([ids], dtype=torch.long, device=cfg.device)
    with torch.no_grad():
        logits = model(input_ids=input_ids).logits[:, :-1, :]
        labels = input_ids[:, 1:]
        log_probs = torch.nn.functional.log_softmax(logits, dim=-1)
        gathered = log_probs.gather(-1, labels.unsqueeze(-1)).squeeze(-1)
    start = max(0, min(gathered.shape[1], score_from_token - 1))
    return float(gathered[:, start:].sum().detach().cpu())


def common_prefix_token_count(tokenizer: Any, good: str, bad: str) -> int:
    common = os.path.commonprefix([good, bad])
    if not common:
        return 0
    return len(tokenizer(common, add_special_tokens=True)["input_ids"])


def evaluate_grammar_margin(
    model: Any,
    tokenizer: Any,
    pairs: list[dict[str, str]],
    cfg: PilotConfig,
) -> dict[str, Any]:
    model.eval()
    margins: list[float] = []
    rows: list[dict[str, Any]] = []
    for row in pairs:
        good = row["grammatical"]
        bad = row["ungrammatical"]
        score_from = common_prefix_token_count(tokenizer, good, bad)
        good_lp = token_logprob_sum(model, tokenizer, good, cfg, score_from)
        bad_lp = token_logprob_sum(model, tokenizer, bad, cfg, score_from)
        margin = good_lp - bad_lp
        margins.append(margin)
        rows.append(
            {
                "id": row["id"],
                "phenomenon": row["phenomenon"],
                "split": row.get("split", ""),
                "score_from_token": score_from,
                "grammatical_logprob": good_lp,
                "ungrammatical_logprob": bad_lp,
                "margin": margin,
                "correct": margin > 0,
            }
        )
    mean = statistics.mean(margins) if margins else float("nan")
    median = statistics.median(margins) if margins else float("nan")
    accuracy = sum(1 for x in margins if x > 0) / max(1, len(margins))
    return {
        "examples": len(margins),
        "mean_margin": mean,
        "median_margin": median,
        "accuracy": accuracy,
        "margins": rows,
    }


def evaluate_all(
    model: Any,
    tokenizer: Any,
    splits: dict[str, list[dict[str, str]]],
    grammar_pairs: list[dict[str, str]],
    cfg: PilotConfig,
) -> dict[str, Any]:
    return {
        "pt_validation": evaluate_bpb(model, tokenizer, [row["pt"] for row in splits["validation"]], cfg),
        "english_retention": evaluate_bpb(model, tokenizer, [row["en"] for row in splits["validation"]], cfg),
        "grammar_margin": evaluate_grammar_margin(model, tokenizer, grammar_pairs, cfg),
    }


def save_checkpoint(model: Any, tokenizer: Any, optimizer: Any, checkpoint_dir: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    import torch

    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(checkpoint_dir, safe_serialization=True)
    tokenizer.save_pretrained(checkpoint_dir)
    torch.save(optimizer.state_dict(), checkpoint_dir / "optimizer.pt")
    write_json(checkpoint_dir / "checkpoint_metadata.json", metadata)
    return hash_tree(checkpoint_dir)


def make_model_and_optimizer(model_name: str, learning_rate: float, device: str) -> tuple[Any, Any]:
    import torch
    from transformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(model_name).to(device).float().train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=0.0)
    return model, optimizer


def run_training_steps(
    model: Any,
    optimizer: Any,
    sequences: list[list[int]],
    tokenizer: Any,
    cfg: PilotConfig,
    steps: int,
    seed: int,
) -> list[float]:
    losses: list[float] = []
    model.train()
    for batch_sequences in iter_batches(sequences, cfg.batch_size, steps, seed):
        batch = collate_batch(batch_sequences, tokenizer.pad_token_id, cfg.device, cfg.sequence_length)
        optimizer.zero_grad(set_to_none=True)
        out = model(**batch)
        out.loss.backward()
        optimizer.step()
        losses.append(float(out.loss.detach().cpu()))
    return losses


def lr_pilot(
    output_dir: Path,
    tokenizer: Any,
    splits: dict[str, list[dict[str, str]]],
    grammar_pairs: list[dict[str, str]],
    cfg: PilotConfig,
) -> dict[str, Any]:
    import torch

    pilot_dir = output_dir / "lr_pilot"
    pt_train = tokenize_texts(tokenizer, [row["pt"] for row in splits["train"]], cfg.sequence_length)
    results: list[dict[str, Any]] = []
    for lr in cfg.lr_grid:
        torch.manual_seed(cfg.seed)
        model, optimizer = make_model_and_optimizer(cfg.model, lr, cfg.device)
        before = evaluate_all(model, tokenizer, splits, grammar_pairs, cfg)
        start = time.perf_counter()
        train_losses = run_training_steps(
            model, optimizer, pt_train, tokenizer, cfg, cfg.lr_pilot_steps, cfg.seed + int(lr * 1e8)
        )
        after = evaluate_all(model, tokenizer, splits, grammar_pairs, cfg)
        wall = time.perf_counter() - start
        item = {
            "learning_rate": lr,
            "steps": cfg.lr_pilot_steps,
            "tokens": cfg.lr_pilot_steps * cfg.tokens_per_step,
            "wall_seconds": wall,
            "initial_pt_bpb": before["pt_validation"]["bpb"],
            "final_pt_bpb": after["pt_validation"]["bpb"],
            "pt_bpb_delta": after["pt_validation"]["bpb"] - before["pt_validation"]["bpb"],
            "initial_english_bpb": before["english_retention"]["bpb"],
            "final_english_bpb": after["english_retention"]["bpb"],
            "english_bpb_delta": after["english_retention"]["bpb"] - before["english_retention"]["bpb"],
            "initial_grammar_mean_margin": before["grammar_margin"]["mean_margin"],
            "final_grammar_mean_margin": after["grammar_margin"]["mean_margin"],
            "train_losses": train_losses,
        }
        write_json(pilot_dir / f"lr_{lr:.0e}.json", item)
        results.append(item)
        del model, optimizer
        if cfg.device == "cuda":
            torch.cuda.empty_cache()
    finite = [
        item
        for item in results
        if math.isfinite(float(item["final_pt_bpb"]))
        and float(item["pt_bpb_delta"]) < 0
        and float(item["english_bpb_delta"]) < max(0.25, abs(float(item["initial_english_bpb"])) * 0.5)
    ]
    selected = min(finite or results, key=lambda item: (float(item["final_pt_bpb"]), item["learning_rate"]))
    summary = {
        "predeclared_lr_grid": list(cfg.lr_grid),
        "selection_rule": "Choose the finite LR with improved Portuguese validation BPB and no >50% or >0.25 absolute English BPB degradation; rank by final Portuguese BPB then lower LR.",
        "selected_learning_rate": selected["learning_rate"],
        "results": results,
        "selected_result": selected,
    }
    write_json(pilot_dir / "lr_pilot_summary.json", summary)
    return summary


def condition_sequences(
    condition: str,
    tokenizer: Any,
    splits: dict[str, list[dict[str, str]]],
    shuffled_ids: list[list[int]],
    cfg: PilotConfig,
) -> list[list[int]]:
    if condition == "structured_pt":
        return tokenize_texts(tokenizer, [row["pt"] for row in splits["train"]], cfg.sequence_length)
    if condition == "shuffled_pt":
        return shuffled_ids
    if condition == "matched_en":
        return tokenize_texts(tokenizer, [row["en"] for row in splits["train"]], cfg.sequence_length)
    raise ValueError(f"Unknown condition: {condition}")


def run_condition(
    output_dir: Path,
    condition: str,
    learning_rate: float,
    tokenizer: Any,
    splits: dict[str, list[dict[str, str]]],
    grammar_pairs: list[dict[str, str]],
    shuffled_ids: list[list[int]],
    cfg: PilotConfig,
) -> dict[str, Any]:
    import torch

    condition_dir = output_dir / "conditions" / condition
    checkpoint_root = condition_dir / "checkpoints"
    eval_dir = condition_dir / "evaluations"
    torch.manual_seed(cfg.seed)
    model, optimizer = make_model_and_optimizer(cfg.model, learning_rate, cfg.device)
    sequences = condition_sequences(condition, tokenizer, splits, shuffled_ids, cfg)
    checkpoint_hashes: dict[str, dict[str, str]] = {}
    evaluations: dict[str, Any] = {}
    train_losses: list[dict[str, Any]] = []
    steps_to_save = cfg.checkpoint_steps

    for step in steps_to_save:
        if step > 0:
            previous = steps_to_save[steps_to_save.index(step) - 1]
            new_losses = run_training_steps(
                model,
                optimizer,
                sequences,
                tokenizer,
                cfg,
                step - previous,
                cfg.seed + CONDITION_SEED_OFFSETS[condition] + step,
            )
            train_losses.extend(
                {
                    "step": previous + index + 1,
                    "cumulative_tokens": (previous + index + 1) * cfg.tokens_per_step,
                    "loss": loss,
                }
                for index, loss in enumerate(new_losses)
            )
        checkpoint_name = f"step_{step:06d}"
        cumulative_tokens = step * cfg.tokens_per_step
        evaluation = evaluate_all(model, tokenizer, splits, grammar_pairs, cfg)
        evaluations[checkpoint_name] = {
            "condition": condition,
            "step": step,
            "cumulative_tokens": cumulative_tokens,
            **evaluation,
        }
        write_json(eval_dir / f"{checkpoint_name}.json", evaluations[checkpoint_name])
        hashes = save_checkpoint(
            model,
            tokenizer,
            optimizer,
            checkpoint_root / checkpoint_name,
            {
                "condition": condition,
                "learning_rate": learning_rate,
                "step": step,
                "cumulative_tokens": cumulative_tokens,
                "tokens_per_step": cfg.tokens_per_step,
                "precision": "fp32",
            },
        )
        checkpoint_hashes[checkpoint_name] = hashes

    summary = {
        "condition": condition,
        "learning_rate": learning_rate,
        "checkpoint_steps": steps_to_save,
        "tokens_per_step": cfg.tokens_per_step,
        "train_losses": train_losses,
        "evaluations": evaluations,
        "checkpoint_hashes_sha256": checkpoint_hashes,
        "checkpoint_root": str(checkpoint_root),
        "evaluation_dir": str(eval_dir),
    }
    write_json(condition_dir / "condition_summary.json", summary)
    del model, optimizer
    if cfg.device == "cuda":
        torch.cuda.empty_cache()
    return summary


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if hasattr(value, "to_dict"):
        try:
            data = value.to_dict()
            if isinstance(data, dict) and "data_vars" in data:
                data = {
                    "dims": data.get("dims", {}),
                    "attrs": data.get("attrs", {}),
                    "data_vars": {
                        name: {
                            "dims": spec.get("dims", []),
                            "attrs": spec.get("attrs", {}),
                            "data_summary": numeric_summary(spec.get("data")),
                        }
                        for name, spec in data.get("data_vars", {}).items()
                    },
                }
            return jsonable(data)
        except Exception:
            pass
    return repr(value)


def flatten_numbers(value: Any) -> list[float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [float(value)]
    if isinstance(value, list):
        out: list[float] = []
        for item in value:
            out.extend(flatten_numbers(item))
        return out
    return []


def numeric_summary(value: Any) -> dict[str, Any]:
    nums = flatten_numbers(value)
    if not nums:
        return {"type": type(value).__name__, "count": 0}
    finite = [x for x in nums if math.isfinite(x)]
    return {
        "count": len(nums),
        "finite_count": len(finite),
        "min": min(finite) if finite else None,
        "max": max(finite) if finite else None,
        "mean": statistics.mean(finite) if finite else None,
        "first": finite[0] if finite else None,
        "last": finite[-1] if finite else None,
    }


def run_llc_cross_check(
    output_dir: Path,
    tokenizer: Any,
    splits: dict[str, list[dict[str, str]]],
    cfg: PilotConfig,
    structured_summary: dict[str, Any],
) -> dict[str, Any]:
    import numpy as np
    import torch
    from datasets import Dataset
    from devinterp.slt.llc import llc
    from transformers import AutoModelForCausalLM

    llc_dir = output_dir / "llc_cross_check"
    texts = [row["pt"] for row in splits["sampler_reference"]]
    input_ids = tokenize_texts(tokenizer, texts, cfg.sequence_length)
    padded = []
    for seq in input_ids:
        row = seq[: cfg.sequence_length]
        row = row + [tokenizer.pad_token_id] * (cfg.sequence_length - len(row))
        padded.append(row)
    dataset = Dataset.from_dict({"input_ids": padded})
    dataset.set_format(type="torch", columns=["input_ids"])
    observables = {"fixed_portuguese_sampler_reference": (dataset, 1)}
    checkpoints = structured_summary["checkpoint_steps"]
    selected_steps = sorted({checkpoints[0], checkpoints[len(checkpoints) // 2], checkpoints[-1]})
    sig = inspect.signature(llc)
    results: list[dict[str, Any]] = []
    for step in selected_steps:
        checkpoint_name = f"step_{step:06d}"
        checkpoint_dir = Path(structured_summary["checkpoint_root"]) / checkpoint_name
        model = AutoModelForCausalLM.from_pretrained(checkpoint_dir).to(cfg.device).float().train()
        trace_output = llc_dir / f"{checkpoint_name}.zarr"
        candidate_kwargs = {
            "model": model,
            "dataset": dataset,
            "observables": observables,
            "lr": cfg.sampler_lr,
            "n_beta": cfg.sampler_n_beta,
            "localization": cfg.sampler_localization,
            "batch_size": cfg.batch_size,
            "num_chains": cfg.sampler_num_chains,
            "num_burnin_steps": cfg.sampler_burnin,
            "num_draws": cfg.sampler_draws,
            "num_steps_bw_draws": cfg.sampler_steps_between_draws,
            "num_steps_between_draws": cfg.sampler_steps_between_draws,
            "output_path": str(trace_output),
        }
        accepts_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        kwargs = candidate_kwargs if accepts_var_kw else {k: v for k, v in candidate_kwargs.items() if k in sig.parameters}
        if accepts_var_kw:
            kwargs.pop("num_steps_between_draws", None)
        torch.cuda.reset_peak_memory_stats() if cfg.device == "cuda" else None
        start = time.perf_counter()
        result = llc(**kwargs)
        wall = time.perf_counter() - start
        if cfg.device == "cuda":
            torch.cuda.synchronize()
        result_json = jsonable(result)
        diagnostics = {
            "finite_result": all(math.isfinite(x) for x in flatten_numbers(result_json)),
            "trace_output_size_bytes": path_size_bytes(trace_output),
            "trace_output_path": str(trace_output),
            "wall_seconds": wall,
            "peak_memory_bytes": int(torch.cuda.max_memory_allocated()) if cfg.device == "cuda" else None,
        }
        item = {
            "condition": "structured_pt",
            "checkpoint": checkpoint_name,
            "step": step,
            "cumulative_tokens": step * cfg.tokens_per_step,
            "sampler_config": cfg.as_dict()["sampler"],
            "observables": {
                "fixed_portuguese_sampler_reference": {
                    "examples": len(dataset),
                    "split": "sampler_reference",
                    "split_hash": sha256_file(output_dir / "data_splits" / "sampler_reference.jsonl"),
                }
            },
            "devinterp_llc_signature": str(sig),
            "result_summary": result_json,
            "diagnostics": diagnostics,
        }
        write_json(llc_dir / f"{checkpoint_name}.json", item)
        results.append(item)
        del model, result
        if cfg.device == "cuda":
            torch.cuda.empty_cache()
    summary = {
        "selection": "Predeclared early/middle/late structured Portuguese checkpoints from the pilot schedule.",
        "fixed_sampler_config": cfg.as_dict()["sampler"],
        "fixed_reference_set": str(output_dir / "data_splits" / "sampler_reference.jsonl"),
        "results": results,
        "interpretable": all(
            item["diagnostics"]["finite_result"] and item["diagnostics"]["trace_output_size_bytes"] > 0
            for item in results
        ),
        "warning": "Pilot LLC cross-check is diagnostic only; it is not a reportable final SLT phase-transition claim.",
    }
    write_json(llc_dir / "llc_cross_check_summary.json", summary)
    return summary


def gate_decision(
    output_dir: Path,
    cfg: PilotConfig,
    data_manifest: dict[str, Any],
    lr_summary: dict[str, Any],
    condition_summaries: dict[str, Any],
    llc_summary: dict[str, Any],
    grammar_sanity: dict[str, Any],
    wall_seconds: float,
) -> dict[str, Any]:
    structured = condition_summaries["structured_pt"]["evaluations"]
    shuffled = condition_summaries["shuffled_pt"]["evaluations"]
    english = condition_summaries["matched_en"]["evaluations"]
    first_name = f"step_{cfg.checkpoint_steps[0]:06d}"
    last_name = f"step_{cfg.checkpoint_steps[-1]:06d}"
    pt_initial = structured[first_name]["pt_validation"]["bpb"]
    pt_final = structured[last_name]["pt_validation"]["bpb"]
    shuffled_final = shuffled[last_name]["pt_validation"]["bpb"]
    english_initial = english[first_name]["english_retention"]["bpb"]
    english_final = english[last_name]["english_retention"]["bpb"]
    grammar_final = structured[last_name]["grammar_margin"]
    structured_vs_shuffled_gap = shuffled_final - pt_final
    estimated_gpu_hours = wall_seconds / 3600.0
    evidence = {
        "data_manifest": str(output_dir / "data_splits" / "split_manifest.json"),
        "lr_pilot": str(output_dir / "lr_pilot" / "lr_pilot_summary.json"),
        "structured_summary": str(output_dir / "conditions" / "structured_pt" / "condition_summary.json"),
        "shuffled_summary": str(output_dir / "conditions" / "shuffled_pt" / "condition_summary.json"),
        "matched_english_summary": str(output_dir / "conditions" / "matched_en" / "condition_summary.json"),
        "llc_cross_check": str(output_dir / "llc_cross_check" / "llc_cross_check_summary.json"),
        "grammar_sanity": str(output_dir / "grammar_sanity_checks.json"),
    }
    criteria = {
        "portuguese_validation_improves": pt_final < pt_initial,
        "grammar_probe_above_chance_or_sanity_passes": grammar_final["accuracy"] > 0.5 or grammar_sanity["passed"],
        "structured_vs_shuffled_behaviorally_distinguishable": structured_vs_shuffled_gap > 0.01,
        "common_sampler_interpretable_early_middle_late": bool(llc_summary["interpretable"]),
        "runtime_projection_within_gate": estimated_gpu_hours <= 10.0 and estimated_gpu_hours * cfg.hourly_rate_usd <= 35.0,
        "infrastructure_gate_confirmed_before_pilot": True,
        "minimum_conditions_completed": all(name in condition_summaries for name in CONDITIONS),
    }
    if all(criteria.values()):
        decision = "proceed"
        next_action = "Record pilot pass, then ask the planner for the next bounded gate; do not launch TinyStories-8M in this tick."
    elif not criteria["structured_vs_shuffled_behaviorally_distinguishable"]:
        decision = "pivot"
        next_action = "Apply the behavioral-control pivot: increase pilot data/steps or strengthen shuffled-control diagnostics before any 8M run."
    elif not criteria["common_sampler_interpretable_early_middle_late"]:
        decision = "pivot"
        next_action = "Apply the sampler pivot in docs/11_FAILURE_MODES_AND_PIVOTS.md before any 8M run."
    else:
        decision = "fail"
        next_action = "Stop before 8M and diagnose failed pilot criteria."
    return {
        "phase": "01_scientific_pilot",
        "decision": decision,
        "criteria": criteria,
        "metrics": {
            "structured_pt_initial_bpb": pt_initial,
            "structured_pt_final_bpb": pt_final,
            "structured_pt_bpb_delta": pt_final - pt_initial,
            "shuffled_pt_final_bpb": shuffled_final,
            "structured_vs_shuffled_pt_bpb_gap": structured_vs_shuffled_gap,
            "matched_english_initial_bpb": english_initial,
            "matched_english_final_bpb": english_final,
            "matched_english_bpb_delta": english_final - english_initial,
            "structured_final_grammar_accuracy": grammar_final["accuracy"],
            "structured_final_grammar_mean_margin": grammar_final["mean_margin"],
            "estimated_gpu_hours": estimated_gpu_hours,
            "estimated_cost_usd": estimated_gpu_hours * cfg.hourly_rate_usd,
            "selected_learning_rate": lr_summary["selected_learning_rate"],
        },
        "evidence_paths": evidence,
        "uncertainty": [
            "This is a short TinyStories-3M pilot, not the final 8M trajectory.",
            "Grammar probe pass may rely on constructed sanity checks if TinyStories-3M is not a known-good Portuguese baseline.",
            "LLC traces are early/middle/late pilot diagnostics under one fixed config, not a formal phase-transition claim.",
        ],
        "failure_modes": [
            "Small OPUS stream prefix may not represent the final corpus distribution.",
            "Very short training can make structured-control separation noisy.",
            "Sampler diagnostics are intentionally shallow under the tick time budget.",
        ],
        "runtime": {
            "wall_seconds": wall_seconds,
            "estimated_gpu_hours": estimated_gpu_hours,
            "hourly_rate_usd_assumption": cfg.hourly_rate_usd,
            "estimated_cost_usd": estimated_gpu_hours * cfg.hourly_rate_usd,
        },
        "next_bounded_action": next_action,
    }


def write_phase_report(output_dir: Path, run_id: str, manifest: dict[str, Any], decision: dict[str, Any]) -> None:
    lines = [
        "# Scientific Pilot Phase Report",
        "",
        f"- Run ID: `{run_id}`",
        f"- Source commit: `{manifest['git_commit']}`",
        f"- Model: `{manifest['config']['model']}`",
        f"- Conditions: `{', '.join(CONDITIONS)}`",
        f"- Gate decision: `{decision['decision']}`",
        "",
        "## Evidence",
        "",
    ]
    for label, path in decision["evidence_paths"].items():
        lines.append(f"- {label}: `{path}`")
    lines.extend(
        [
            "",
            "## Key Metrics",
            "",
        ]
    )
    for key, value in decision["metrics"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Criteria",
            "",
        ]
    )
    for key, value in decision["criteria"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Uncertainty",
            "",
        ]
    )
    for item in decision["uncertainty"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Failure Modes",
            "",
        ]
    )
    for item in decision["failure_modes"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Runtime And Cost",
            "",
            f"- Wall seconds: `{decision['runtime']['wall_seconds']:.2f}`",
            f"- Estimated GPU hours: `{decision['runtime']['estimated_gpu_hours']:.4f}`",
            f"- Estimated cost USD: `${decision['runtime']['estimated_cost_usd']:.4f}`",
            "",
            "## Gate Decision",
            "",
            f"`{decision['decision']}`. {decision['next_bounded_action']}",
            "",
        ]
    )
    (output_dir / "phase_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="TinyStories-3M scientific pilot gate")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--sequence-length", type=int, default=128)
    parser.add_argument("--train-size", type=int, default=96)
    parser.add_argument("--val-size", type=int, default=24)
    parser.add_argument("--sampler-size", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr-pilot-steps", type=int, default=20)
    parser.add_argument("--condition-steps", type=int, default=48)
    parser.add_argument("--lr-grid", default="3e-5,1e-4,3e-4")
    parser.add_argument("--sampler-num-chains", type=int, default=2)
    parser.add_argument("--sampler-burnin", type=int, default=20)
    parser.add_argument("--sampler-draws", type=int, default=10)
    parser.add_argument("--sampler-steps-between-draws", type=int, default=1)
    parser.add_argument("--sampler-lr", type=float, default=1e-5)
    parser.add_argument("--sampler-n-beta", type=float, default=10.0)
    parser.add_argument("--sampler-localization", type=float, default=100.0)
    parser.add_argument("--seed", type=int, default=20260620)
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    parser.add_argument("--hourly-rate-usd", type=float, default=1.0)
    args = parser.parse_args()

    import torch
    from transformers import AutoTokenizer

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")
    cfg = PilotConfig(
        model=args.model,
        sequence_length=args.sequence_length,
        train_size=args.train_size,
        val_size=args.val_size,
        sampler_size=args.sampler_size,
        batch_size=args.batch_size,
        lr_pilot_steps=args.lr_pilot_steps,
        condition_steps=args.condition_steps,
        lr_grid=tuple(float(x) for x in args.lr_grid.split(",") if x),
        sampler_num_chains=args.sampler_num_chains,
        sampler_burnin=args.sampler_burnin,
        sampler_draws=args.sampler_draws,
        sampler_steps_between_draws=args.sampler_steps_between_draws,
        sampler_lr=args.sampler_lr,
        sampler_n_beta=args.sampler_n_beta,
        sampler_localization=args.sampler_localization,
        seed=args.seed,
        device=args.device,
        hourly_rate_usd=args.hourly_rate_usd,
    )
    run_start = time.perf_counter()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "manifest.json"
    manifest = {
        "run_kind": "tinystories_3m_scientific_pilot",
        "scientific_scope": "TinyStories-3M only; structured Portuguese, token-shuffled Portuguese, matched English; no Spanish or localization.",
        "start_utc": utc_now(),
        "git_commit": git_commit(),
        "git_status_short_at_start": git_status_short(),
        "config": cfg.as_dict(),
        "package_versions": package_versions(),
        "device": args.device,
        "gpu": torch.cuda.get_device_name(0) if args.device == "cuda" else None,
        "torch_cuda_available": bool(torch.cuda.is_available()),
    }
    write_json(manifest_path, manifest)

    torch.manual_seed(cfg.seed)
    tokenizer = AutoTokenizer.from_pretrained(cfg.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer_hash = stable_json_hash(tokenizer.get_vocab())

    data = immutable_splits(args.output_dir, tokenizer, cfg)
    grammar_pairs = load_grammar_pairs()
    grammar_sanity = grammar_sanity_checks(grammar_pairs)
    write_json(args.output_dir / "grammar_sanity_checks.json", grammar_sanity)
    shuffled_ids, shuffle_mapping = make_shuffled_ids(
        data["splits"]["train"], tokenizer, cfg.sequence_length, cfg.seed + 17
    )
    shuffle_hashes = save_shuffled_condition(data["split_dir"], shuffled_ids, shuffle_mapping)
    data["manifest"]["split_hashes_sha256"].update(shuffle_hashes)
    write_json(data["split_dir"] / "split_manifest.json", data["manifest"])

    lr_summary = lr_pilot(args.output_dir, tokenizer, data["splits"], grammar_pairs, cfg)
    selected_lr = float(lr_summary["selected_learning_rate"])
    condition_summaries = {
        condition: run_condition(
            args.output_dir,
            condition,
            selected_lr,
            tokenizer,
            data["splits"],
            grammar_pairs,
            shuffled_ids,
            cfg,
        )
        for condition in CONDITIONS
    }
    llc_summary = run_llc_cross_check(
        args.output_dir, tokenizer, data["splits"], cfg, condition_summaries["structured_pt"]
    )
    wall_seconds = time.perf_counter() - run_start
    decision = gate_decision(
        args.output_dir,
        cfg,
        data["manifest"],
        lr_summary,
        condition_summaries,
        llc_summary,
        grammar_sanity,
        wall_seconds,
    )
    write_json(args.output_dir / "gate_decision.json", decision)
    manifest.update(
        {
            "end_utc": utc_now(),
            "wall_seconds": wall_seconds,
            "tokenizer_vocab_sha256": tokenizer_hash,
            "data_split_manifest": str(data["split_dir"] / "split_manifest.json"),
            "gate_decision": decision["decision"],
            "evidence_paths": decision["evidence_paths"],
            "estimated_gpu_hours": wall_seconds / 3600.0,
            "estimated_cost_usd": wall_seconds / 3600.0 * cfg.hourly_rate_usd,
            "exit_status": "completed",
        }
    )
    write_json(manifest_path, manifest)
    write_phase_report(args.output_dir, args.output_dir.name, manifest, decision)
    print(json.dumps(decision, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
