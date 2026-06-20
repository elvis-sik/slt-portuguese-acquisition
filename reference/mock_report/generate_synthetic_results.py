from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator

OUT = Path(__file__).resolve().parent
FIG = OUT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(20260619)

STEPS = np.array([0, 100, 200, 300, 450, 600, 700, 800, 900, 1050, 1250, 1500, 1850, 2200, 2500], dtype=float)
TOKENS_M = STEPS * 4096 / 1_000_000
CONDITIONS = ['Structured Portuguese', 'Shuffled Portuguese', 'Matched English control']


def sigmoid(z: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-z))


def grammar_accuracy_from_margin(m: np.ndarray) -> np.ndarray:
    return 100.0 * sigmoid(1.25 * m)


def generate_condition(condition: str, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(1000 + 97 * seed + sum(map(ord, condition)))
    s = STEPS
    seed_shift = rng.normal(0.0, 34.0)
    amp = 1.0 + rng.normal(0.0, 0.025)

    if condition == 'Structured Portuguese':
        transition = 810.0 + seed_shift
        target_bpb = (
            2.58
            - 0.94 * (1.0 - np.exp(-s / 275.0))
            - 0.40 * sigmoid((s - transition) / 115.0)
            + rng.normal(0.0, 0.012, len(s))
        )
        grammar_margin = (
            -0.045
            + 0.20 * (1.0 - np.exp(-s / 520.0))
            + 1.39 * amp * sigmoid((s - (transition + 37.0)) / 88.0)
            + rng.normal(0.0, 0.032, len(s))
        )
        lexical_accuracy = (
            12.0
            + 71.7 * (1.0 - np.exp(-s / 285.0))
            + 3.4 * sigmoid((s - transition) / 160.0)
            + rng.normal(0.0, 0.7, len(s))
        )
        llc_ratio = (
            1.0
            + 0.275 * (1.0 - np.exp(-s / 305.0))
            - 0.188 * sigmoid((s - transition) / 58.0)
            + 0.020 * sigmoid((s - (transition + 420.0)) / 210.0)
            + rng.normal(0.0, 0.006, len(s))
        )
        english_bpb = (
            1.180
            + 0.018 * (1.0 - np.exp(-s / 260.0))
            + 0.043 * sigmoid((s - transition) / 125.0)
            + rng.normal(0.0, 0.0025, len(s))
        )
    elif condition == 'Shuffled Portuguese':
        transition = np.nan
        target_bpb = (
            2.58
            - 0.99 * (1.0 - np.exp(-s / 320.0))
            - 0.13 * (s / 2500.0)
            + rng.normal(0.0, 0.014, len(s))
        )
        grammar_margin = (
            -0.020
            + 0.095 * (s / 2500.0)
            + rng.normal(0.0, 0.028, len(s))
        )
        lexical_accuracy = (
            12.0
            + 70.1 * (1.0 - np.exp(-s / 305.0))
            + 0.7 * (s / 2500.0)
            + rng.normal(0.0, 0.8, len(s))
        )
        llc_ratio = (
            1.0
            + 0.178 * (s / 2500.0)
            + rng.normal(0.0, 0.006, len(s))
        )
        english_bpb = (
            1.180
            + 0.042 * (s / 2500.0)
            + rng.normal(0.0, 0.0025, len(s))
        )
    elif condition == 'Matched English control':
        transition = np.nan
        target_bpb = (
            2.58
            - 0.065 * (s / 2500.0)
            + rng.normal(0.0, 0.012, len(s))
        )
        grammar_margin = (
            -0.015
            + 0.018 * (s / 2500.0)
            + rng.normal(0.0, 0.024, len(s))
        )
        lexical_accuracy = (
            12.0
            + 2.3 * (s / 2500.0)
            + rng.normal(0.0, 0.6, len(s))
        )
        llc_ratio = (
            1.0
            + 0.072 * (s / 2500.0)
            + rng.normal(0.0, 0.005, len(s))
        )
        english_bpb = (
            1.180
            - 0.068 * (1.0 - np.exp(-s / 460.0))
            + rng.normal(0.0, 0.0022, len(s))
        )
    else:
        raise ValueError(condition)

    grammar_accuracy = grammar_accuracy_from_margin(grammar_margin)
    df = pd.DataFrame({
        'condition': condition,
        'seed': seed,
        'step': s.astype(int),
        'target_tokens_millions': TOKENS_M,
        'target_validation_bits_per_byte': target_bpb,
        'lexical_probe_accuracy_percent': np.clip(lexical_accuracy, 0, 100),
        'grammar_logprob_margin': grammar_margin,
        'grammar_minimal_pair_accuracy_percent': grammar_accuracy,
        'normalized_llc_ratio_to_start': llc_ratio,
        'english_validation_bits_per_byte': english_bpb,
        'generating_transition_step': transition,
    })
    return df


def generate_spanish(seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(8000 + 113 * seed)
    s = STEPS
    transition = 665.0 + rng.normal(0.0, 32.0)
    amp = 1.0 + rng.normal(0.0, 0.025)
    target_bpb = (
        2.53
        - 0.95 * (1.0 - np.exp(-s / 250.0))
        - 0.38 * sigmoid((s - transition) / 110.0)
        + rng.normal(0.0, 0.012, len(s))
    )
    grammar_margin = (
        -0.035
        + 0.22 * (1.0 - np.exp(-s / 470.0))
        + 1.43 * amp * sigmoid((s - (transition + 31.0)) / 83.0)
        + rng.normal(0.0, 0.033, len(s))
    )
    lexical_accuracy = (
        13.0
        + 72.5 * (1.0 - np.exp(-s / 260.0))
        + rng.normal(0.0, 0.7, len(s))
    )
    llc_ratio = (
        1.0
        + 0.265 * (1.0 - np.exp(-s / 280.0))
        - 0.180 * sigmoid((s - transition) / 55.0)
        + 0.018 * sigmoid((s - (transition + 410.0)) / 205.0)
        + rng.normal(0.0, 0.006, len(s))
    )
    english_bpb = (
        1.180
        + 0.017 * (1.0 - np.exp(-s / 250.0))
        + 0.040 * sigmoid((s - transition) / 120.0)
        + rng.normal(0.0, 0.0025, len(s))
    )
    return pd.DataFrame({
        'condition': 'Structured Spanish replication',
        'seed': seed,
        'step': s.astype(int),
        'target_tokens_millions': TOKENS_M,
        'target_validation_bits_per_byte': target_bpb,
        'lexical_probe_accuracy_percent': np.clip(lexical_accuracy, 0, 100),
        'grammar_logprob_margin': grammar_margin,
        'grammar_minimal_pair_accuracy_percent': grammar_accuracy_from_margin(grammar_margin),
        'normalized_llc_ratio_to_start': llc_ratio,
        'english_validation_bits_per_byte': english_bpb,
        'generating_transition_step': transition,
    })


def fit_piecewise_break(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float, float]:
    """Return best break, delta BIC (linear - piecewise), linear BIC, piecewise BIC.

    Piecewise model uses an intercept, global slope, hinge, and a small step term.
    This is deliberately simple and mirrors what a weekend analysis might use.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    X0 = np.column_stack([np.ones(n), x])
    beta0, *_ = np.linalg.lstsq(X0, y, rcond=None)
    rss0 = float(np.sum((y - X0 @ beta0) ** 2))
    rss0 = max(rss0, 1e-12)
    bic0 = n * np.log(rss0 / n) + 2 * np.log(n)

    candidates = x[3:-3]
    best = None
    for c in candidates:
        hinge = np.maximum(0.0, x - c)
        step = (x >= c).astype(float)
        X = np.column_stack([np.ones(n), x, hinge, step])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        rss = float(np.sum((y - X @ beta) ** 2))
        rss = max(rss, 1e-12)
        bic = n * np.log(rss / n) + 4 * np.log(n)
        if best is None or bic < best[0]:
            best = (bic, c)
    assert best is not None
    bic1, c1 = best
    return float(c1), float(bic0 - bic1), float(bic0), float(bic1)


def mean_ci(group: pd.core.groupby.generic.DataFrameGroupBy, metric: str) -> pd.DataFrame:
    agg = group[metric].agg(['mean', 'std', 'count']).reset_index()
    agg['ci95'] = 1.96 * agg['std'].fillna(0) / np.sqrt(agg['count'])
    return agg


def save_line_chart(df: pd.DataFrame, metric: str, ylabel: str, title: str, filename: str, ylim=None, transition_line=True):
    fig, ax = plt.subplots(figsize=(7.2, 4.15))
    order = CONDITIONS
    for condition in order:
        sub = df[df['condition'] == condition]
        agg = mean_ci(sub.groupby('target_tokens_millions'), metric)
        ax.errorbar(
            agg['target_tokens_millions'], agg['mean'], yerr=agg['ci95'],
            marker='o', markersize=3.4, linewidth=1.7, capsize=2.0, label=condition
        )
    if transition_line:
        ax.axvline(3.32, linestyle='--', linewidth=1.2)
        ytop = ylim[1] if ylim else ax.get_ylim()[1]
        ybottom = ylim[0] if ylim else ax.get_ylim()[0]
        ax.text(3.42, ybottom + 0.88 * (ytop - ybottom), 'estimated Portuguese transition', fontsize=8.5, rotation=90, va='top')
    ax.set_xlabel('Target-language tokens seen (millions)')
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc='left', fontweight='bold')
    ax.grid(True, axis='y', alpha=0.22)
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.legend(frameon=False, fontsize=8.2)
    fig.tight_layout()
    fig.savefig(FIG / filename, dpi=220, bbox_inches='tight')
    plt.close(fig)


def save_phase_alignment(changepoints: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(6.5, 4.35))
    for lang, marker in [('Portuguese', 'o'), ('Spanish', 's')]:
        sub = changepoints[changepoints['language'] == lang]
        ax.scatter(sub['llc_break_step'], sub['grammar_break_step'], s=62, marker=marker, label=f'{lang} seeds')
        for _, row in sub.iterrows():
            ax.annotate(f"s{int(row['seed'])}", (row['llc_break_step'], row['grammar_break_step']), xytext=(4, 4), textcoords='offset points', fontsize=8)
    low, high = 560, 980
    ax.plot([low, high], [low, high], linestyle='--', linewidth=1.2, label='zero lag')
    ax.set_xlim(low, high)
    ax.set_ylim(low, high)
    ax.set_xlabel('LLC changepoint (training step)')
    ax.set_ylabel('Grammar changepoint (training step)')
    ax.set_title('Synthetic result: geometric and behavioral transitions align across seeds', loc='left', fontweight='bold')
    ax.grid(True, alpha=0.22)
    ax.legend(frameon=False, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(FIG / 'figure_2_phase_alignment.png', dpi=220, bbox_inches='tight')
    plt.close(fig)


def save_component_chart():
    components = [
        'Embeddings', 'B1 Attn', 'B1 MLP', 'B2 Attn',
        'B2 MLP', 'B3 Attn', 'B3 MLP', 'Unembedding'
    ]
    ratios = np.array([1.34, 1.46, 1.71, 2.03, 2.41, 2.86, 4.08, 1.58])
    err = np.array([0.10, 0.12, 0.16, 0.19, 0.22, 0.25, 0.37, 0.14])
    fig, ax = plt.subplots(figsize=(7.2, 4.05))
    x = np.arange(len(components))
    ax.bar(x, ratios, yerr=err, capsize=3)
    ax.axhline(1.0, linestyle='--', linewidth=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels(components, rotation=24, ha='right')
    ax.set_ylabel('Susceptibility at transition / pre-transition')
    ax.set_title('Synthetic result: the strongest localized response is in the final MLP block', loc='left', fontweight='bold')
    ax.grid(True, axis='y', alpha=0.22)
    fig.tight_layout()
    fig.savefig(FIG / 'figure_3_component_localization.png', dpi=220, bbox_inches='tight')
    plt.close(fig)


def save_intervention_chart():
    rng = np.random.default_rng(54321)
    s = STEPS
    curves = {
        'No freeze': -0.04 + 0.20 * (1 - np.exp(-s / 520)) + 1.39 * sigmoid((s - 847) / 88),
        'Freeze B3 MLP at step 600': -0.04 + 0.19 * (1 - np.exp(-s / 540)) + 1.10 * sigmoid((s - 1240) / 125),
        'Freeze matched B1 attention': -0.04 + 0.20 * (1 - np.exp(-s / 535)) + 1.31 * sigmoid((s - 915) / 100),
    }
    fig, ax = plt.subplots(figsize=(7.2, 4.15))
    for label, base in curves.items():
        y = base + rng.normal(0, 0.014, len(s))
        ax.plot(TOKENS_M, y, marker='o', markersize=3.5, linewidth=1.8, label=label)
    ax.axvline(2.46, linestyle=':', linewidth=1.1)
    ax.text(2.52, 1.46, 'freeze applied', fontsize=8.5, rotation=90, va='top')
    ax.set_xlabel('Target-language tokens seen (millions)')
    ax.set_ylabel('Portuguese grammar log-probability margin')
    ax.set_title('Synthetic result: freezing the candidate block delays, but does not abolish, generalization', loc='left', fontweight='bold')
    ax.grid(True, axis='y', alpha=0.22)
    ax.legend(frameon=False, fontsize=8.2)
    fig.tight_layout()
    fig.savefig(FIG / 'figure_4_freeze_intervention.png', dpi=220, bbox_inches='tight')
    plt.close(fig)


def save_language_comparison(df_all: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(6.9, 4.05))
    for condition, label in [('Structured Portuguese', 'Portuguese'), ('Structured Spanish replication', 'Spanish')]:
        sub = df_all[df_all['condition'] == condition]
        agg = mean_ci(sub.groupby('target_tokens_millions'), 'grammar_logprob_margin')
        ax.errorbar(
            agg['target_tokens_millions'], agg['mean'], yerr=agg['ci95'], marker='o',
            markersize=3.5, linewidth=1.8, capsize=2, label=label
        )
    ax.set_xlabel('Target-language tokens seen (millions)')
    ax.set_ylabel('Grammar log-probability margin')
    ax.set_title('Synthetic extension: Spanish transitions earlier under the same token budget', loc='left', fontweight='bold')
    ax.grid(True, axis='y', alpha=0.22)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / 'figure_5_language_comparison.png', dpi=220, bbox_inches='tight')
    plt.close(fig)


def save_sampler_diagnostics():
    rng = np.random.default_rng(2026)
    draws = np.arange(1, 121)
    fig, ax = plt.subplots(figsize=(6.9, 3.6))
    for chain in range(1, 5):
        trace = 1.012 + 0.020 * np.exp(-draws / 15.0) + rng.normal(0, 0.0022, len(draws)) + (chain - 2.5) * 0.0007
        ax.plot(draws, trace, linewidth=1.0, label=f'chain {chain}')
    ax.axvline(20, linestyle='--', linewidth=1.0)
    ax.set_xlabel('SGLD draw')
    ax.set_ylabel('Localized sampling loss')
    ax.set_title('Synthetic diagnostic: four chains mix to a common stationary loss range', loc='left', fontweight='bold')
    ax.grid(True, axis='y', alpha=0.22)
    ax.legend(frameon=False, ncol=4, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / 'figure_s1_sampler_diagnostic.png', dpi=220, bbox_inches='tight')
    plt.close(fig)


def main():
    frames = []
    for condition in CONDITIONS:
        for seed in [1, 2, 3]:
            frames.append(generate_condition(condition, seed))
    for seed in [1, 2, 3]:
        frames.append(generate_spanish(seed))
    df = pd.concat(frames, ignore_index=True)
    df.to_csv(OUT / 'synthetic_training_trajectories.csv', index=False, float_format='%.6f')

    # Per-seed changepoints for structured-language runs.
    cps = []
    for condition, language in [('Structured Portuguese', 'Portuguese'), ('Structured Spanish replication', 'Spanish')]:
        for seed in [1, 2, 3]:
            sub = df[(df['condition'] == condition) & (df['seed'] == seed)].sort_values('step')
            x = sub['step'].to_numpy(dtype=float)
            llc_y = sub['normalized_llc_ratio_to_start'].to_numpy(dtype=float)
            grammar_y = sub['grammar_logprob_margin'].to_numpy(dtype=float)
            # Transition location is the maximum-rate point of a shape-preserving smooth curve.
            # Segmented-regression delta-BIC is retained as a separate strength diagnostic.
            grid = np.linspace(400.0, 1300.0, 901)
            llc_smooth = PchipInterpolator(x, llc_y)(grid)
            grammar_smooth = PchipInterpolator(x, grammar_y)(grid)
            llc_break = float(grid[np.argmin(np.gradient(llc_smooth, grid))])
            gram_break = float(grid[np.argmax(np.gradient(grammar_smooth, grid))])
            _, llc_dbic, _, _ = fit_piecewise_break(x, llc_y)
            _, gram_dbic, _, _ = fit_piecewise_break(x, grammar_y)
            cps.append({
                'language': language,
                'seed': seed,
                'llc_break_step': llc_break,
                'grammar_break_step': gram_break,
                'lag_steps_grammar_minus_llc': gram_break - llc_break,
                'llc_delta_bic': llc_dbic,
                'grammar_delta_bic': gram_dbic,
            })
    cp_df = pd.DataFrame(cps)
    cp_df.to_csv(OUT / 'synthetic_changepoints.csv', index=False, float_format='%.3f')

    # Conditions summary at final checkpoint.
    final = df[df['step'] == 2500].copy()
    rows = []
    for condition in CONDITIONS:
        sub = final[final['condition'] == condition]
        start_en = df[(df['condition'] == condition) & (df['step'] == 0)]['english_validation_bits_per_byte'].mean()
        end_en = sub['english_validation_bits_per_byte'].mean()
        rows.append({
            'condition': condition,
            'final_target_bpb_mean': sub['target_validation_bits_per_byte'].mean(),
            'final_target_bpb_sd': sub['target_validation_bits_per_byte'].std(ddof=1),
            'final_lexical_accuracy_mean_percent': sub['lexical_probe_accuracy_percent'].mean(),
            'final_grammar_accuracy_mean_percent': sub['grammar_minimal_pair_accuracy_percent'].mean(),
            'english_bpb_relative_change_percent': 100.0 * (end_en - start_en) / start_en,
            'final_llc_ratio_mean': sub['normalized_llc_ratio_to_start'].mean(),
        })
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / 'synthetic_condition_summary.csv', index=False, float_format='%.4f')

    # Main figures.
    core = df[df['condition'].isin(CONDITIONS)].copy()
    save_line_chart(
        core, 'target_validation_bits_per_byte', 'Target validation bits per byte',
        'Synthetic result: Portuguese validation loss improves in two stages',
        'figure_1a_target_loss.png', ylim=(1.15, 2.68)
    )
    save_line_chart(
        core, 'grammar_logprob_margin', 'Portuguese grammar log-probability margin',
        'Synthetic result: grammar generalization appears after early lexical learning',
        'figure_1b_grammar_margin.png', ylim=(-0.16, 1.72)
    )
    save_line_chart(
        core, 'normalized_llc_ratio_to_start', 'LLC / LLC at starting checkpoint',
        'Synthetic result: an LLC peak and drop coincides with grammatical generalization',
        'figure_1c_llc_trajectory.png', ylim=(0.96, 1.31)
    )
    save_phase_alignment(cp_df)
    save_component_chart()
    save_intervention_chart()
    save_language_comparison(df)
    save_sampler_diagnostics()

    # Intervention table used in report.
    intervention = pd.DataFrame([
        {'intervention': 'No freeze', 'grammar_transition_step': 824, 'final_grammar_accuracy_percent': 87.2, 'final_portuguese_bpb': 1.24, 'english_bpb_change_percent': 5.4},
        {'intervention': 'Freeze B3 MLP at step 600', 'grammar_transition_step': 1242, 'final_grammar_accuracy_percent': 79.0, 'final_portuguese_bpb': 1.28, 'english_bpb_change_percent': 4.2},
        {'intervention': 'Freeze matched B1 attention', 'grammar_transition_step': 914, 'final_grammar_accuracy_percent': 85.1, 'final_portuguese_bpb': 1.25, 'english_bpb_change_percent': 4.8},
    ])
    intervention.to_csv(OUT / 'synthetic_intervention_summary.csv', index=False)

    metadata = {
        'disclaimer': 'All data and results in this package are synthetic and illustrative. They are not measurements from an actual model run.',
        'model': 'Illustrative 8M-parameter, 4-block English-only decoder transformer',
        'training_budget': '2,500 steps x 4,096 target-language tokens = 10.24M tokens per run',
        'conditions': CONDITIONS,
        'seeds': 3,
        'grammar_eval_pairs': 1200,
        'llc_checkpoints': 9,
        'llc_sampler': 'Illustrative: 4 chains, 120 post-burn-in draws, devinterp-style localized SGLD',
    }
    (OUT / 'synthetic_metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')

    print('Created synthetic data and figures in', OUT)
    print('\nFinal summary:')
    print(summary.to_string(index=False))
    print('\nChangepoints:')
    print(cp_df.to_string(index=False))


if __name__ == '__main__':
    main()
