#!/usr/bin/env python3
"""Overnight autonomous orchestrator for the SLT Portuguese experiment.

Three layers (see codex/prompts/planner.md and the plan):

    deterministic harness (this file)  -- owns the inviolable backstops
      |- planner agent  (codex exec + plan_directive schema)  -- proposes the next step
      |- executor agent (codex exec + run_decision schema)    -- does the work

The agents are smart and propose; the harness is thin and enforces the hard limits:
the wall-clock deadline, the hard $ cap, and the operator stop-file. None of these can be
overridden by an agent. Per-step time budgets from the planner are clamped to the time
remaining, and any step whose projected spend would cross the hard cap is refused.

Run unattended on the VM:
    nohup setsid python3 codex/orchestrate.py >> results/_orchestrator/harness.log 2>&1 &

Dry-run locally (no GPU, no API), to exercise the loop / backstops / retry / completion:
    python3 codex/orchestrate.py --dry-run --scenario complete
    python3 codex/orchestrate.py --dry-run --scenario deadline
    python3 codex/orchestrate.py --dry-run --scenario budget
    python3 codex/orchestrate.py --dry-run --scenario retry
    python3 codex/orchestrate.py --dry-run --scenario stop
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# ORCH_REPO_ROOT lets dry-run tests point at a hermetic temp copy instead of the live repo.
REPO_ROOT = Path(os.environ.get("ORCH_REPO_ROOT", Path(__file__).resolve().parent.parent))
ORCH_DIR = REPO_ROOT / "results" / "_orchestrator"
STATE_PATH = ORCH_DIR / "state.json"
STOP_FILE = REPO_ROOT / "results" / "_control" / "_orchestrator" / "stop"
REGISTRY = REPO_ROOT / "state" / "experiment_registry.csv"
DECISION_LOG = REPO_ROOT / "state" / "decision_log.md"
CURRENT_STATUS = REPO_ROOT / "state" / "current_status.json"
CODEX_DIR = REPO_ROOT / "results" / "_codex"

PLANNER_PROMPT = REPO_ROOT / "codex" / "prompts" / "planner.md"
PLAN_SCHEMA = REPO_ROOT / "codex" / "schemas" / "plan_directive.schema.json"
RUN_SCHEMA = REPO_ROOT / "codex" / "schemas" / "run_decision.schema.json"
CODEX_ENV = Path.home() / ".config" / "slt-portuguese" / "codex.env"


def utcnow_iso(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


class Clock:
    """Real wall clock; the dry-run subclass advances a counter instead."""

    def now(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class FakeClock(Clock):
    def __init__(self, start: float, tick_advance_s: float) -> None:
        self._t = start
        self._advance = tick_advance_s

    def now(self) -> float:
        return self._t

    def sleep(self, seconds: float) -> None:
        # In dry-run, "sleeping" just advances simulated time so deadlines are reachable fast.
        self._t += self._advance


@dataclass
class Config:
    deadline_hours: float = 8.0
    soft_cap_usd: float = 35.0
    hard_cap_usd: float = 50.0
    hourly_rate_usd: float = 1.0
    min_step_hours: float = 0.05
    max_consecutive_failures: int = 4
    tick_pause_s: float = 30.0
    sandbox: str = "workspace-write"  # planner: read/edit only, never needs the GPU
    # The executor must reach the GPU; Codex's workspace-write sandbox hides /dev/nvidia* compute
    # nodes, so GPU work needs full host access. Operator-authorized on this disposable worker.
    exec_sandbox: str = "danger-full-access"
    auto_stop_on_complete: bool = True
    planner_model: str = "gpt-5.5"
    planner_effort: str = "xhigh"
    exec_model: str = "gpt-5.5"
    exec_effort: str = "high"
    dry_run: bool = False
    scenario: str = "complete"


@dataclass
class State:
    started_at: float
    deadline_at: float
    config: Config
    tick: int = 0
    stage: str = "infrastructure_gate"
    status: str = "running"  # running|awaiting_retry|complete|halted_*|escalate
    launch_id: str = ""  # unique per launch so relaunches don't overwrite earlier codex logs
    cumulative_cost_usd: float = 0.0
    consecutive_failures: int = 0
    soft_cap_logged: bool = False
    request_shutdown: bool = False
    last_plan_directive: dict[str, Any] | None = None
    last_executor_decision: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- IO helpers

def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def cumulative_cost_from_registry() -> float:
    """Ground-truth GPU/compute spend: sum of estimated_cost_usd across registry rows.

    This is what the $35 soft / $50 hard caps in AGENTS.md refer to.
    """
    if not REGISTRY.exists():
        return 0.0
    total = 0.0
    with REGISTRY.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                total += float(row.get("estimated_cost_usd") or 0.0)
            except ValueError:
                continue
    return total


def registry_summary() -> dict[str, int]:
    summary: dict[str, int] = {}
    if not REGISTRY.exists():
        return summary
    with REGISTRY.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = f"{row.get('phase', '?')}/{row.get('status', '?')}"
            summary[key] = summary.get(key, 0) + 1
    return summary


def append_decision_log(text: str) -> None:
    DECISION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DECISION_LOG.open("a", encoding="utf-8") as fh:
        fh.write(text if text.endswith("\n") else text + "\n")


def write_state(state: State, clock: Clock) -> None:
    ORCH_DIR.mkdir(parents=True, exist_ok=True)
    now = clock.now()
    elapsed = now - state.started_at
    remaining = state.deadline_at - now
    payload = {
        "started_at": utcnow_iso(state.started_at),
        "deadline_at": utcnow_iso(state.deadline_at),
        "now": utcnow_iso(now),
        "launch_id": state.launch_id,
        "tick": state.tick,
        "stage": state.stage,
        "status": state.status,
        "elapsed_s": round(elapsed, 1),
        "remaining_s": round(remaining, 1),
        "elapsed_hours": round(elapsed / 3600.0, 3),
        "remaining_hours": round(remaining / 3600.0, 3),
        "cumulative_cost_usd": round(state.cumulative_cost_usd, 4),
        "soft_cap_usd": state.config.soft_cap_usd,
        "hard_cap_usd": state.config.hard_cap_usd,
        "consecutive_failures": state.consecutive_failures,
        "request_shutdown": state.request_shutdown,
        "auto_stop_on_complete": state.config.auto_stop_on_complete,
        "models": {
            "planner": f"{state.config.planner_model}/{state.config.planner_effort}",
            "executor": f"{state.config.exec_model}/{state.config.exec_effort}",
        },
        "sandbox": {"planner": state.config.sandbox, "executor": state.config.exec_sandbox},
        "dry_run": state.config.dry_run,
        "last_plan_directive": state.last_plan_directive,
        "last_executor_decision": state.last_executor_decision,
        "history": state.history[-60:],
        "notes": state.notes[-20:],
        "updated_at": utcnow_iso(now),
    }
    tmp = STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATE_PATH)


# --------------------------------------------------------------------------- agent calls

def codex_exec(prompt_text: str, schema_path: Path, out_dir: Path, sandbox: str,
               timeout_s: float | None, model: str = "", effort: str = "") -> dict[str, Any] | None:
    """Mirror codex/run_phase.sh: source the API key, run `codex exec` with a forced schema.

    model/effort are passed through to `codex exec` (--model and -c model_reasoning_effort=...).
    Effort is sent verbatim so newer levels (e.g. xhigh) work without a code change.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "prompt.md").write_text(prompt_text, encoding="utf-8")
    final_json = out_dir / "final_decision.json"
    events = out_dir / "events.jsonl"
    inner = (
        'set -a; [ -f "$CODEX_ENV" ] && . "$CODEX_ENV"; set +a; '
        'set -- --sandbox "$SANDBOX" --json --output-schema "$SCHEMA" -o "$OUT"; '
        '[ -n "$MODEL" ] && set -- "$@" --model "$MODEL"; '
        '[ -n "$EFFORT_CFG" ] && set -- "$@" -c "$EFFORT_CFG"; '
        'exec codex exec "$@" "$PROMPT"'
    )
    env = {
        **os.environ,
        "CODEX_ENV": str(CODEX_ENV),
        "SANDBOX": sandbox,
        "SCHEMA": str(schema_path),
        "OUT": str(final_json),
        "PROMPT": prompt_text,
        "MODEL": model,
        # Quote the value so codex parses it as a TOML string; empty => skipped in bash.
        "EFFORT_CFG": f'model_reasoning_effort="{effort}"' if effort else "",
    }
    try:
        with events.open("w", encoding="utf-8") as log:
            subprocess.run(
                ["bash", "-c", inner],
                cwd=str(REPO_ROOT),
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout_s,
                check=False,
            )
    except subprocess.TimeoutExpired:
        events.open("a", encoding="utf-8").write("\n[harness] codex exec timed out\n")
    return read_json(final_json)


# --------------------------------------------------------------------------- dry-run stubs

class DryRunScenario:
    """Scripted planner/executor responses + simulated cost, for verifying the harness."""

    def __init__(self, name: str, clock: FakeClock, state: State) -> None:
        self.name = name
        self.clock = clock
        self.state = state
        self.step_cost = 6.0  # simulated $ per executor tick

    def plan(self) -> dict[str, Any]:
        t = self.state.tick
        if self.name == "complete":
            decision = "complete" if t >= 3 else "continue"
        elif self.name == "deadline":
            decision = "continue"  # never completes; the deadline backstop must fire
        elif self.name == "budget":
            decision = "continue"  # cost climbs until the hard-cap backstop fires
        elif self.name == "retry":
            # tick1 fails -> tick2 diagnose -> recover -> complete once stable.
            decision = "complete" if t >= 5 else "continue"
        elif self.name == "stop":
            decision = "continue"
        else:
            decision = "continue"
        last = self.state.last_executor_decision
        failed = bool(last and last.get("status") in ("failed", "blocked"))
        stage = "diagnose_and_fix" if (self.name == "retry" and failed) else "scientific_pilot"
        return {
            "terminal_decision": decision,
            "stage": stage,
            "executor_prompt": f"codex/prompts/{'diagnose_and_fix' if stage=='diagnose_and_fix' else '01_scientific_pilot'}.md",
            "task_instruction": f"[dry-run {self.name}] tick {t}: simulated bounded action.",
            "time_budget_hours": 0.5,
            "expected_cost_usd": self.step_cost,
            "rationale": f"dry-run scenario={self.name}",
        }

    def execute(self, directive: dict[str, Any]) -> dict[str, Any]:
        t = self.state.tick
        status = "completed"
        gate = "proceed"
        if self.name == "retry" and t in (1, 2) and directive["stage"] != "diagnose_and_fix":
            status, gate = "failed", "modify"
        # Simulate spend by appending a registry row so cumulative_cost reads it back as truth.
        self._append_registry_row(t, status, self.step_cost)
        return {
            "status": status,
            "summary": f"[dry-run {self.name}] executor tick {t} -> {status}",
            "files_changed": [],
            "commands_run": ["dry-run"],
            "gate_decision": gate,
            "requires_human_approval": False,
            "approval_reason": "",
            "estimated_incremental_gpu_hours": self.step_cost,
            "estimated_incremental_cost_usd": self.step_cost,
            "next_action": "continue",
            "evidence_paths": [],
        }

    def _append_registry_row(self, tick: int, status: str, cost: float) -> None:
        new = not REGISTRY.exists()
        REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        header = [
            "run_id", "phase", "status", "condition", "model", "seed", "git_commit",
            "config_path", "start_utc", "end_utc", "gpu_hours", "estimated_cost_usd",
            "output_dir", "notes",
        ]
        with REGISTRY.open("a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(header)
            w.writerow([
                f"dryrun-{self.name}-{tick}", "scientific_pilot", status, "structured_portuguese",
                "TinyStories-3M", "1", "dryrun", "configs/experiment.example.yaml",
                utcnow_iso(self.clock.now()), utcnow_iso(self.clock.now()), cost, cost,
                f"results/_jobs/dryrun-{self.name}-{tick}", "dry-run synthetic row",
            ])


# --------------------------------------------------------------------------- the loop

def build_planner_prompt(state: State, clock: Clock) -> str:
    now = clock.now()
    digest = {
        "tick": state.tick,
        "stage": state.stage,
        "now": utcnow_iso(now),
        "started_at": utcnow_iso(state.started_at),
        "deadline_at": utcnow_iso(state.deadline_at),
        "elapsed_hours": round((now - state.started_at) / 3600.0, 3),
        "remaining_hours": round((state.deadline_at - now) / 3600.0, 3),
        "cumulative_cost_usd": round(state.cumulative_cost_usd, 4),
        "soft_cap_usd": state.config.soft_cap_usd,
        "hard_cap_usd": state.config.hard_cap_usd,
        "consecutive_failures": state.consecutive_failures,
        "last_executor_decision": state.last_executor_decision,
        "registry_summary": registry_summary(),
        "current_status": read_json(CURRENT_STATUS),
    }
    return (
        PLANNER_PROMPT.read_text(encoding="utf-8")
        + "\n\n---\n## Live state digest (injected by the harness)\n```json\n"
        + json.dumps(digest, indent=2)
        + "\n```\n"
    )


def build_executor_prompt(directive: dict[str, Any]) -> str:
    prompt_file = REPO_ROOT / directive["executor_prompt"]
    base = prompt_file.read_text(encoding="utf-8")
    return (
        base
        + "\n\n---\n## Orchestrator directive for this tick\n"
        + f"- Time budget: {directive['time_budget_hours']:.3f} wall-clock hours "
        + "(launch bounded jobs with --max-hours within this; poll and kill as you judge best).\n"
        + f"- Task: {directive['task_instruction']}\n"
    )


def halt(state: State, status: str, clock: Clock, reason: str, shutdown: bool) -> None:
    state.status = status
    state.request_shutdown = shutdown
    state.notes.append(f"{utcnow_iso(clock.now())} {status}: {reason}")
    write_state(state, clock)
    append_decision_log(
        f"\n## {utcnow_iso(clock.now())} — orchestrator {status}\n\n{reason}\n"
        + (f"\nrequest_shutdown=true; dashboard will fetch results and stop (not delete) the VM.\n"
           if shutdown else "")
    )
    print(f"[harness] HALT {status}: {reason}", flush=True)


def run(config: Config) -> int:
    if config.dry_run:
        clock: Clock = FakeClock(start=1_750_000_000.0, tick_advance_s=config.tick_pause_s)
        # Compress the deadline for dry-run scenarios that must exercise the time backstop.
        deadline_hours = 0.05 if config.scenario == "deadline" else config.deadline_hours
    else:
        clock = Clock()
        deadline_hours = config.deadline_hours

    started = clock.now()
    state = State(started_at=started, deadline_at=started + deadline_hours * 3600.0, config=config)
    state.launch_id = time.strftime("run-%Y%m%dT%H%M%SZ", time.gmtime(started))
    state.cumulative_cost_usd = cumulative_cost_from_registry()
    scenario = DryRunScenario(config.scenario, clock, state) if config.dry_run else None

    write_state(state, clock)
    append_decision_log(
        f"\n## {utcnow_iso(started)} — orchestrator started"
        f"{' (DRY RUN)' if config.dry_run else ''}\n\n"
        f"Deadline {utcnow_iso(state.deadline_at)} ({deadline_hours:.2f}h), "
        f"soft ${config.soft_cap_usd:.0f} / hard ${config.hard_cap_usd:.0f}. "
        f"Operator pre-authorized proceed-to-cap autonomy (AGENTS.md).\n"
    )

    while True:
        state.tick += 1
        state.cumulative_cost_usd = cumulative_cost_from_registry()
        now = clock.now()

        # ---- HARD backstops, enforced before any agent runs ----
        if STOP_FILE.exists():
            halt(state, "halted_operator", clock, "operator stop-file present", shutdown=True)
            STOP_FILE.unlink(missing_ok=True)
            return 0
        if now >= state.deadline_at:
            halt(state, "halted_deadline", clock,
                 f"wall-clock deadline reached at tick {state.tick}", shutdown=True)
            return 0
        if state.cumulative_cost_usd >= config.hard_cap_usd:
            halt(state, "halted_budget", clock,
                 f"hard cap ${config.hard_cap_usd:.0f} reached "
                 f"(cumulative ${state.cumulative_cost_usd:.2f})", shutdown=True)
            return 0
        if (not state.soft_cap_logged) and state.cumulative_cost_usd >= config.soft_cap_usd:
            state.soft_cap_logged = True
            append_decision_log(
                f"\n## {utcnow_iso(now)} — soft budget review\n\n"
                f"Cumulative ${state.cumulative_cost_usd:.2f} crossed the ${config.soft_cap_usd:.0f} "
                f"soft line; continuing under pre-authorization toward the ${config.hard_cap_usd:.0f} "
                f"hard cap.\n"
            )
        if state.consecutive_failures >= config.max_consecutive_failures:
            halt(state, "escalate", clock,
                 f"{state.consecutive_failures} consecutive executor failures; needs a human",
                 shutdown=False)
            return 1

        write_state(state, clock)

        # ---- PLANNER ----
        if scenario is not None:
            directive: dict[str, Any] | None = scenario.plan()
        else:
            directive = codex_exec(
                build_planner_prompt(state, clock), PLAN_SCHEMA,
                CODEX_DIR / f"{state.launch_id}-planner-{state.tick:03d}", config.sandbox, timeout_s=900,
                model=config.planner_model, effort=config.planner_effort,
            )
        if not directive:
            state.consecutive_failures += 1
            state.notes.append(f"tick {state.tick}: planner produced no directive")
            write_state(state, clock)
            clock.sleep(config.tick_pause_s)
            continue
        state.last_plan_directive = directive
        state.stage = directive.get("stage", state.stage)
        write_state(state, clock)

        term = directive.get("terminal_decision", "continue")
        if term == "complete":
            halt(state, "complete", clock,
                 f"planner declared the goal complete: {directive.get('rationale', '')}",
                 shutdown=True)
            return 0
        if term == "escalate":
            halt(state, "escalate", clock,
                 f"planner escalated to a human: {directive.get('rationale', '')}", shutdown=False)
            return 1

        # ---- pre-flight budget/time clamp on the directive ----
        remaining_hours = (state.deadline_at - clock.now()) / 3600.0
        budget = max(config.min_step_hours, min(directive.get("time_budget_hours", 0.5), remaining_hours))
        directive["time_budget_hours"] = round(budget, 3)
        expected = float(directive.get("expected_cost_usd", 0.0) or 0.0)
        if state.cumulative_cost_usd + expected > config.hard_cap_usd:
            halt(state, "halted_budget", clock,
                 f"projected spend ${state.cumulative_cost_usd + expected:.2f} would cross the "
                 f"${config.hard_cap_usd:.0f} hard cap; refusing the step", shutdown=True)
            return 0

        # ---- EXECUTOR ----
        if scenario is not None:
            decision: dict[str, Any] | None = scenario.execute(directive)
        else:
            timeout_s = (budget + 0.25) * 3600.0  # backstop slightly beyond the granted budget
            decision = codex_exec(
                build_executor_prompt(directive), RUN_SCHEMA,
                CODEX_DIR / f"{state.launch_id}-exec-{state.stage}-{state.tick:03d}", config.exec_sandbox, timeout_s,
                model=config.exec_model, effort=config.exec_effort,
            )
        if not decision:
            state.consecutive_failures += 1
            state.notes.append(f"tick {state.tick}: executor produced no decision")
            write_state(state, clock)
            clock.sleep(config.tick_pause_s)
            continue

        state.last_executor_decision = decision
        if decision.get("status") in ("failed", "blocked"):
            state.consecutive_failures += 1
            state.status = "awaiting_retry"
        else:
            state.consecutive_failures = 0
            state.status = "running"
        state.cumulative_cost_usd = cumulative_cost_from_registry()
        state.history.append({
            "tick": state.tick,
            "at": utcnow_iso(clock.now()),
            "stage": state.stage,
            "time_budget_hours": directive.get("time_budget_hours"),
            "exec_status": decision.get("status"),
            "gate_decision": decision.get("gate_decision"),
            "cumulative_cost_usd": round(state.cumulative_cost_usd, 4),
            "summary": decision.get("summary", "")[:200],
        })
        write_state(state, clock)
        clock.sleep(config.tick_pause_s)


def parse_args(argv: list[str]) -> Config:
    p = argparse.ArgumentParser(description="SLT Portuguese overnight orchestrator")
    p.add_argument("--deadline-hours", type=float,
                   default=float(os.environ.get("ORCH_DEADLINE_HOURS", "8")))
    p.add_argument("--soft-cap", type=float, default=float(os.environ.get("ORCH_SOFT_CAP", "35")))
    p.add_argument("--hard-cap", type=float, default=float(os.environ.get("ORCH_HARD_CAP", "50")))
    p.add_argument("--hourly-rate", type=float, default=float(os.environ.get("HOURLY_RATE_USD", "1")))
    p.add_argument("--tick-pause", type=float, default=float(os.environ.get("ORCH_TICK_PAUSE", "30")))
    p.add_argument("--no-auto-stop", action="store_true",
                   help="Do not request VM shutdown on completion.")
    p.add_argument("--planner-model", default=os.environ.get("CODEX_PLANNER_MODEL", "gpt-5.5"))
    p.add_argument("--planner-effort", default=os.environ.get("CODEX_PLANNER_EFFORT", "xhigh"))
    p.add_argument("--exec-model", default=os.environ.get("CODEX_EXEC_MODEL", "gpt-5.5"))
    p.add_argument("--exec-effort", default=os.environ.get("CODEX_EXEC_EFFORT", "high"))
    p.add_argument("--exec-sandbox", default=os.environ.get("ORCH_EXEC_SANDBOX", "danger-full-access"),
                   help="Codex sandbox for the executor. danger-full-access is required for GPU access.")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--scenario", default="complete",
                   choices=["complete", "deadline", "budget", "retry", "stop"])
    a = p.parse_args(argv)
    return Config(
        deadline_hours=a.deadline_hours,
        soft_cap_usd=a.soft_cap,
        hard_cap_usd=a.hard_cap,
        hourly_rate_usd=a.hourly_rate,
        tick_pause_s=a.tick_pause,
        auto_stop_on_complete=not a.no_auto_stop,
        planner_model=a.planner_model,
        planner_effort=a.planner_effort,
        exec_model=a.exec_model,
        exec_effort=a.exec_effort,
        exec_sandbox=a.exec_sandbox,
        dry_run=a.dry_run,
        scenario=a.scenario,
    )


if __name__ == "__main__":
    sys.exit(run(parse_args(sys.argv[1:])))
