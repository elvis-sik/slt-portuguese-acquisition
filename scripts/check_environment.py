from __future__ import annotations

import argparse
import importlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def version(name: str) -> str | None:
    try:
        mod = importlib.import_module(name)
        return getattr(mod, "__version__", "installed")
    except Exception as exc:
        return f"ERROR: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    report: dict[str, object] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "packages": {k: version(k) for k in ["torch", "transformers", "datasets", "devinterp", "numpy", "pandas"]},
    }
    try:
        report["nvidia_smi"] = subprocess.run(
            ["nvidia-smi"], check=True, text=True, capture_output=True, timeout=30
        ).stdout
    except Exception as exc:
        report["nvidia_smi"] = f"ERROR: {exc}"

    try:
        import torch
        report["torch_cuda_available"] = torch.cuda.is_available()
        report["torch_cuda_version"] = torch.version.cuda
        report["cuda_device_count"] = torch.cuda.device_count()
        if torch.cuda.is_available():
            report["cuda_device_name"] = torch.cuda.get_device_name(0)
            report["cuda_total_memory_bytes"] = torch.cuda.get_device_properties(0).total_memory
    except Exception as exc:
        report["torch_probe_error"] = repr(exc)

    if args.model:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            model = AutoModelForCausalLM.from_pretrained(args.model)
            tokenizer = AutoTokenizer.from_pretrained(args.model)
            report["model_id"] = args.model
            report["parameter_count"] = sum(p.numel() for p in model.parameters())
            report["trainable_parameter_count"] = sum(p.numel() for p in model.parameters() if p.requires_grad)
            report["tokenizer_vocab_size"] = len(tokenizer)
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            model.to(device).train()
            vocab = int(getattr(model.config, "vocab_size"))
            ids = torch.randint(0, vocab, (2, 32), device=device)
            out = model(input_ids=ids, labels=ids)
            out.loss.backward()
            report["forward_backward_loss"] = float(out.loss.detach().cpu())
            report["forward_backward_device"] = str(device)
        except Exception as exc:
            report["model_probe_error"] = repr(exc)

    text = json.dumps(report, indent=2, default=str)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    failures = [v for v in report.values() if isinstance(v, str) and v.startswith("ERROR:")]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
