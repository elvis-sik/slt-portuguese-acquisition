#!/usr/bin/env python3
"""Build overnight comparison figures + data tables from LLC summary JSONs.

Deliberately produces FIGURES + factual DATA TABLES only (no interpretive prose) so an unattended run
cannot accidentally over-claim against the AGENTS.md wording rules; the analysis text is written by a
human when the PR is opened. Every figure is wrapped so one failure does not abort the rest, and the
script never raises (the caller's VM-halt must not be blocked).

Usage: overnight_report.py [summary_dir]
"""
import glob
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SUMD = sys.argv[1] if len(sys.argv) > 1 else "results/03_llc_campaign/_overnight_summary"
os.makedirs(SUMD, exist_ok=True)
BAND = (1.5e6, 2.5e6)  # behavioral grammar-acquisition window


def summarize_dir(d):
    rows = []
    for f in sorted(glob.glob(os.path.join(d, "running_estimates", "tokens_*.jsonl"))):
        toks = int(os.path.basename(f).replace("tokens_", "").replace(".jsonl", ""))
        final = {}
        for line in open(f):
            line = line.strip()
            if not line:
                continue
            j = json.loads(line)
            ch, st = j["chain"], j["step"]
            if ch not in final or st > final[ch][0]:
                final[ch] = (st, j["running_llc"])
        chains = [v[1] for k, v in sorted(final.items())]
        if chains:
            rows.append(dict(tokens=toks, llc_mean=sum(chains) / len(chains),
                             chains=[round(c, 3) for c in chains]))
    return rows


def load(name):
    p = os.path.join(SUMD, name)
    try:
        return json.load(open(p)) if os.path.exists(p) else None
    except Exception:
        return None


def newest(pat):
    g = sorted(glob.glob(pat))
    return g[-1] if g else None


def xy(rows):
    rows = sorted(rows, key=lambda r: r["tokens"])
    return [r["tokens"] for r in rows], [r["llc_mean"] for r in rows]


# --- seed-A primary (loc=100): summarize straight from its results dir ---
seedA_dir = newest("results/03_llc_campaign/seed_a_FINAL_*")
seedA = summarize_dir(seedA_dir) if seedA_dir else (load("structured_seedA_loc100_llc.json") or [])
if seedA:
    json.dump(seedA, open(os.path.join(SUMD, "structured_seedA_loc100_llc.json"), "w"), indent=2)

shuf = load("shuffled_pt_llc.json") or []
men = load("matched_en_llc.json") or []
l300 = load("seedA_loc300_llc.json") or []
l30 = load("seedA_loc30_llc.json") or []

# --- Figure 1: three-condition contrast ---
try:
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    for rows, lab, c, mk in [
        (seedA, "structured PT (seed A)", "C0", "o"),
        (shuf, "shuffled PT (control)", "C3", "s"),
        (men, "matched English (control)", "C2", "^"),
    ]:
        if rows:
            x, y = xy(rows)
            ax.plot(x, y, marker=mk, color=c, lw=2, ms=6, label=lab)
    ax.axvspan(*BAND, color="orange", alpha=0.15, lw=0, label="grammar transition (1.5-2.5M)")
    ax.set_xscale("log")
    ax.set_xlabel("training tokens (log)")
    ax.set_ylabel(r"$\hat\lambda$ (LLC)")
    ax.set_title("LLC trajectory: structured PT vs controls (loc=100, 3 chains)")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(alpha=.3)
    fig.tight_layout()
    fig.savefig(os.path.join(SUMD, "fig_three_condition_llc.png"), dpi=150)
    print("wrote fig_three_condition_llc.png")
except Exception as e:
    print("fig1 failed:", e)

# --- Figure 2: localization sensitivity ---
try:
    if l300 or l30:
        fig, ax = plt.subplots(figsize=(7.5, 4.6))
        for rows, lab, c in [
            (l30, "loc=30", "C4"),
            (seedA, "loc=100 (primary)", "C0"),
            (l300, "loc=300", "C5"),
        ]:
            if rows:
                x, y = xy(rows)
                ax.plot(x, y, marker="o", color=c, lw=2, ms=5, label=lab)
        ax.axvspan(*BAND, color="orange", alpha=0.15, lw=0)
        ax.set_xscale("log")
        ax.set_xlabel("training tokens (log)")
        ax.set_ylabel(r"$\hat\lambda$ (LLC)")
        ax.set_title("Localization sensitivity (structured PT seed A): trajectory shape")
        ax.legend(fontsize=8, loc="lower right")
        ax.grid(alpha=.3)
        fig.tight_layout()
        fig.savefig(os.path.join(SUMD, "fig_localization_sensitivity.png"), dpi=150)
        print("wrote fig_localization_sensitivity.png")
except Exception as e:
    print("fig2 failed:", e)


# --- Data-table markdown (factual only; prose added by a human in the PR) ---
def table(title, rows, compare=None):
    lines = ["### " + title, "", "| tokens | LLC (mean) | per-chain |", "|---:|---:|:--|"]
    for r in sorted(rows, key=lambda r: r["tokens"]):
        ch = " / ".join("%.1f" % c for c in r["chains"])
        lines.append("| {:,} | {:+.1f} | {} |".format(r["tokens"], r["llc_mean"], ch))
    return "\n".join(lines) + "\n"


try:
    md = ["# Overnight LLC results — data tables (auto-generated, prose pending)", "",
          "_Figures: `fig_three_condition_llc.png`, `fig_localization_sensitivity.png`._",
          "_Source summaries are the JSON files in this directory. Interpretation is written by a human "
          "in the PR; this file is factual tables only._", ""]
    md.append("## Conditions (loc=100, 3 chains, condition-matched non-padded references)\n")
    if seedA:
        md.append(table("structured PT seed A (primary)", seedA))
    if shuf:
        md.append(table("shuffled PT (control)", shuf))
    if men:
        md.append(table("matched English (control)", men))
    # contrast table at shared tokens
    if seedA and (shuf or men):
        md.append("## Contrast at shared checkpoints\n")
        md.append("| tokens | structured | shuffled | matched-EN |")
        md.append("|---:|---:|---:|---:|")
        sd = {r["tokens"]: r["llc_mean"] for r in seedA}
        hd = {r["tokens"]: r["llc_mean"] for r in shuf}
        ed = {r["tokens"]: r["llc_mean"] for r in men}
        for t in sorted(sd):
            def g(d):
                return "%+.1f" % d[t] if t in d else "-"
            md.append("| {:,} | {} | {} | {} |".format(t, g(sd), g(hd), g(ed)))
        md.append("")
    if l300 or l30:
        md.append("## Localization sensitivity (structured PT seed A)\n")
        if l30:
            md.append(table("loc=30", l30))
        if l300:
            md.append(table("loc=300", l300))
    open(os.path.join(SUMD, "OVERNIGHT_DATA.md"), "w").write("\n".join(md))
    print("wrote OVERNIGHT_DATA.md")
except Exception as e:
    print("report md failed:", e)

print("overnight_report done")
