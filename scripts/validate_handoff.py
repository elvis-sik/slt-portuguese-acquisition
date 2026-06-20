from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "README.md", "START_HERE_FOR_CODEX.md", "AGENTS.md",
    "docs/01_RESEARCH_PROTOCOL.md", "docs/02_SLT_BAYESIAN_COMPLICATIONS.md",
    "docs/04_BENCHMARKS_AND_FERMI_ESTIMATES.md",
    "infra/gcp/provision_vm.sh", "infra/remote/run_bounded_job.sh",
    "scripts/benchmark_train.py", "scripts/benchmark_sampler.py",
    "reference/mock_report/slt_portuguese_synthetic_mock_submission.pdf",
    "reference/mock_report/generate_synthetic_results.py",
]

missing = [p for p in REQUIRED if not (ROOT / p).exists()]
if missing:
    print("Missing required files:")
    print("\n".join(f"- {p}" for p in missing))
    raise SystemExit(1)

pdf = ROOT / "reference/mock_report/slt_portuguese_synthetic_mock_submission.pdf"
print(f"Root: {ROOT}")
print(f"Required files: {len(REQUIRED)} present")
print(f"Mock PDF size: {pdf.stat().st_size:,} bytes")
print(f"Mock PDF SHA256: {hashlib.sha256(pdf.read_bytes()).hexdigest()}")
print("Validation passed. Synthetic artifacts remain under reference/mock_report/.")
