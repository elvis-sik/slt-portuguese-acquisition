from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SYNTHETIC_GATE_TEXTS = [
    "Lia found a blue cup beside the garden gate.",
    "The small train stopped, and every child waved.",
    "Marta counted three shells before the rain began.",
    "A quiet dog slept while the moon crossed the window.",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_tree(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            hashes[str(path.relative_to(root))] = sha256_file(path)
    return hashes


def make_repeated_texts(texts: Iterable[str], target_count: int) -> list[str]:
    base = list(texts)
    if not base:
        raise ValueError("texts must not be empty")
    return [base[i % len(base)] for i in range(target_count)]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Infrastructure-gate train/save/reload/evaluate/generate loop for TinyStories-3M"
    )
    parser.add_argument("--model", default="roneneldan/TinyStories-3M")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sequence-length", type=int, default=64)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--train-steps", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--seed", type=int, default=20260620)
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    parser.add_argument("--prompt", default="Once upon a time")
    parser.add_argument("--max-new-tokens", type=int, default=24)
    args = parser.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = args.output_dir / "checkpoint"
    torch.manual_seed(args.seed)

    device = torch.device(args.device)
    started = time.perf_counter()
    start_utc = datetime.now(timezone.utc).isoformat()

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(args.model).to(device).train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.0)

    train_texts = make_repeated_texts(SYNTHETIC_GATE_TEXTS, args.batch_size)
    eval_texts = make_repeated_texts(reversed(SYNTHETIC_GATE_TEXTS), args.batch_size)
    train_batch = tokenizer(
        train_texts,
        return_tensors="pt",
        padding="max_length",
        truncation=True,
        max_length=args.sequence_length,
    ).to(device)
    eval_batch = tokenizer(
        eval_texts,
        return_tensors="pt",
        padding="max_length",
        truncation=True,
        max_length=args.sequence_length,
    ).to(device)

    losses: list[float] = []
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    for _ in range(args.train_steps):
        optimizer.zero_grad(set_to_none=True)
        out = model(**train_batch, labels=train_batch["input_ids"])
        out.loss.backward()
        optimizer.step()
        losses.append(float(out.loss.detach().cpu()))

    model.save_pretrained(checkpoint_dir, safe_serialization=True)
    tokenizer.save_pretrained(checkpoint_dir)

    del model
    if device.type == "cuda":
        torch.cuda.empty_cache()

    reloaded = AutoModelForCausalLM.from_pretrained(checkpoint_dir).to(device).eval()
    with torch.no_grad():
        eval_loss = float(reloaded(**eval_batch, labels=eval_batch["input_ids"]).loss.detach().cpu())
        prompt = tokenizer(args.prompt, return_tensors="pt").to(device)
        generated = reloaded.generate(
            **prompt,
            do_sample=False,
            max_new_tokens=args.max_new_tokens,
            pad_token_id=tokenizer.eos_token_id,
        )
    generated_text = tokenizer.decode(generated[0], skip_special_tokens=True)
    (args.output_dir / "generated_sample.txt").write_text(generated_text + "\n", encoding="utf-8")

    peak_memory = None
    total_memory = None
    headroom_fraction = None
    if device.type == "cuda":
        peak_memory = int(torch.cuda.max_memory_allocated())
        total_memory = int(torch.cuda.get_device_properties(0).total_memory)
        headroom_fraction = 1.0 - (peak_memory / total_memory)

    report = {
        "run_kind": "tinystories_3m_train_save_reload_evaluate_sample_loop",
        "scientific_validity": "infrastructure smoke only; synthetic fixed text, not an empirical result",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "start_utc": start_utc,
        "wall_seconds": time.perf_counter() - started,
        "model": args.model,
        "seed": args.seed,
        "device": str(device),
        "parameter_count": sum(p.numel() for p in reloaded.parameters()),
        "trainable_parameter_count": sum(p.numel() for p in reloaded.parameters() if p.requires_grad),
        "sequence_length": args.sequence_length,
        "batch_size": args.batch_size,
        "train_steps": args.train_steps,
        "learning_rate": args.learning_rate,
        "train_losses": losses,
        "eval_loss_after_reload": eval_loss,
        "checkpoint_dir": str(checkpoint_dir),
        "checkpoint_hashes_sha256": hash_tree(checkpoint_dir),
        "generated_sample_path": str(args.output_dir / "generated_sample.txt"),
        "generated_sample_chars": len(generated_text),
        "peak_memory_bytes": peak_memory,
        "cuda_total_memory_bytes": total_memory,
        "vram_headroom_fraction": headroom_fraction,
    }
    metrics_path = args.output_dir / "loop_metrics.json"
    metrics_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
