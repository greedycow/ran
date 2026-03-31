"""
Research-quality visualisation suite for the RAN Sharing Cooperative Game.

Generates publication-ready static figures and an animated GIF that shows
the simulation evolving over time.

Usage:
    cd src && python visualisation.py          # generates all figures
    cd src && python visualisation.py --gif    # also generates the animated GIF
"""

from __future__ import annotations

import os
import sys
import math
from typing import Any

import numpy as np
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for file output
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from matplotlib.animation import FuncAnimation, PillowWriter

from generate_data import OperatorParams, get_example_operators, get_example_traffic
from utility import single_operator_utility
from main import (
    simulate_one_hour_oracle,
    simulate_one_hour_online,
    compare_oracle_vs_online,
)

# ── Global style ─────────────────────────────────────────────────────────────

PALETTE = ["#2563eb", "#dc2626", "#16a34a", "#f59e0b"]   # blue, red, green, amber
ORACLE_COLOR = "#2563eb"
ONLINE_COLOR = "#dc2626"
STANDALONE_COLOR = "#6b7280"
BG_LIGHT = "#f8fafc"
GRID_COLOR = "#e2e8f0"

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor":   BG_LIGHT,
    "axes.grid":        True,
    "grid.color":       GRID_COLOR,
    "grid.linewidth":   0.6,
    "axes.spines.top":  False,
    "axes.spines.right": False,
    "font.size":        10,
    "axes.titlesize":   12,
    "axes.titleweight": "bold",
    "axes.labelsize":   10,
    "legend.fontsize":  8.5,
    "legend.framealpha": 0.9,
    "figure.dpi":       150,
    "savefig.dpi":      200,
    "savefig.bbox":     "tight",
    "savefig.pad_inches": 0.15,
})

OP_LABELS: list[str] = []  # filled at runtime


# ── Helper: run both simulations and compute standalone ──────────────────────

def _run_simulations(safety_margin: float = 0.15):
    ops = get_example_operators()
    traffic = get_example_traffic()
    coalition = list(range(len(ops)))
    num_steps = len(traffic[0])

    global OP_LABELS
    OP_LABELS = [op.name for op in ops]

    oracle = simulate_one_hour_oracle(ops, traffic, coalition)
    online = simulate_one_hour_online(ops, traffic, coalition,
                                      window_size=5,
                                      safety_margin=safety_margin)
    comparison = compare_oracle_vs_online(oracle, online)

    # standalone utility per operator per time step
    standalone_ts: dict[int, list[float]] = {}
    for i in coalition:
        standalone_ts[i] = []
        for t in range(num_steps):
            T_i = traffic[i][t]
            rho_i = min(1.0, T_i / ops[i].capacity_epsilon)
            standalone_ts[i].append(
                single_operator_utility(ops[i].c, T_i, ops[i].beta, rho_i, ops[i].K)
            )

    return ops, traffic, coalition, oracle, online, comparison, standalone_ts


# ── Figure 1: Traffic Profiles ───────────────────────────────────────────────

def fig_traffic_profiles(ops, traffic, coalition, out_dir):
    """Per-operator traffic and aggregate, with capacity references."""
    num_steps = len(traffic[0])
    t = np.arange(num_steps)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.2))

    # Left: individual traffic
    for i in coalition:
        ax1.plot(t, traffic[i], color=PALETTE[i], lw=1.8, label=OP_LABELS[i])
        ax1.axhline(ops[i].capacity_epsilon, color=PALETTE[i], ls="--", lw=0.8, alpha=0.5)
    ax1.set_xlabel("Time (min)")
    ax1.set_ylabel("Traffic  $T_i(t)$")
    ax1.set_title("(a) Per-Operator Traffic Profiles")
    ax1.legend(loc="upper left")

    # Right: aggregate traffic vs capacity combos
    agg = [sum(traffic[i][tt] for i in coalition) for tt in range(num_steps)]
    ax2.fill_between(t, agg, alpha=0.15, color="#475569")
    ax2.plot(t, agg, color="#475569", lw=2, label="Total traffic")

    cap_combos = {
        "Op1+Op3 (160)": ops[0].capacity_epsilon + ops[2].capacity_epsilon,
        "Op1+Op2 (180)": ops[0].capacity_epsilon + ops[1].capacity_epsilon,
        "Op1+Op3+Op4 (230)": ops[0].capacity_epsilon + ops[2].capacity_epsilon + ops[3].capacity_epsilon,
    }
    dash_styles = [(4, 2), (6, 2, 2, 2), (2, 2)]
    for idx, (lab, cap) in enumerate(cap_combos.items()):
        ax2.axhline(cap, ls="--", dashes=dash_styles[idx], lw=1, alpha=0.7,
                     color=PALETTE[idx], label=lab)

    ax2.set_xlabel("Time (min)")
    ax2.set_ylabel("Traffic")
    ax2.set_title("(b) Aggregate Traffic vs Guardian Capacities")
    ax2.legend(loc="upper left", fontsize=7.5)

    fig.tight_layout(w_pad=3)
    fig.savefig(os.path.join(out_dir, "fig1_traffic_profiles.png"))
    plt.close(fig)


# ── Figure 2: Guardian Timeline ──────────────────────────────────────────────

def fig_guardian_timeline(ops, coalition, oracle, online, out_dir):
    """Heatmap-style timeline showing which operators serve as guardians."""
    num_steps = oracle["time_steps"]
    n = len(coalition)

    def _build_matrix(result):
        mat = np.zeros((n, num_steps))
        for tt in range(num_steps):
            for g in result["guardians"][tt]:
                mat[g, tt] = 1.0
        return mat

    oracle_mat = _build_matrix(oracle)
    online_mat = _build_matrix(online)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 3.6), sharex=True)

    for ax, mat, title in [
        (ax1, oracle_mat, "Oracle Mode"),
        (ax2, online_mat, f"Online Mode (margin={online['safety_margin']:.0%})"),
    ]:
        im = ax.imshow(mat, aspect="auto", cmap="Blues", vmin=0, vmax=1,
                        interpolation="nearest", extent=[-0.5, num_steps - 0.5, n - 0.5, -0.5])
        ax.set_yticks(range(n))
        ax.set_yticklabels(OP_LABELS[:n], fontsize=9)
        ax.set_title(title, fontsize=11)
        for spine in ax.spines.values():
            spine.set_visible(False)

    ax2.set_xlabel("Time (min)")

    # Shared legend
    legend_elements = [
        mpatches.Patch(facecolor="#2563eb", alpha=0.8, label="Guardian (ON)"),
        mpatches.Patch(facecolor=BG_LIGHT, edgecolor="#94a3b8", label="Sleeping (OFF)"),
    ]
    fig.legend(handles=legend_elements, loc="upper right", fontsize=8,
               bbox_to_anchor=(0.98, 0.98))

    fig.tight_layout(h_pad=1.2)
    fig.savefig(os.path.join(out_dir, "fig2_guardian_timeline.png"))
    plt.close(fig)


# ── Figure 3: Coalition Value v*(s) ─────────────────────────────────────────

def fig_coalition_value(oracle, online, standalone_ts, coalition, out_dir):
    """v* over time: oracle vs online vs sum-of-standalone."""
    num_steps = oracle["time_steps"]
    t = np.arange(num_steps)

    standalone_agg = [sum(standalone_ts[i][tt] for i in coalition) for tt in range(num_steps)]

    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.fill_between(t, oracle["v_star"], online["v_star"], alpha=0.12, color=ORACLE_COLOR)
    ax.plot(t, oracle["v_star"], color=ORACLE_COLOR, lw=2, label="Oracle $v^*(s)$")
    ax.plot(t, online["v_star"], color=ONLINE_COLOR, lw=2, ls="--",
            label=f"Online $v^*(s)$ (margin={online['safety_margin']:.0%})")
    ax.plot(t, standalone_agg, color=STANDALONE_COLOR, lw=1.5, ls=":",
            label=r"$\sum_i\, v(A_i)$  (non-cooperative)")

    # Mark capacity failures
    failures = online.get("capacity_failures", [])
    if failures:
        fail_t = [f["t"] for f in failures]
        fail_v = [online["v_star"][f["t"]] for f in failures]
        ax.scatter(fail_t, fail_v, marker="x", s=50, color=ONLINE_COLOR, zorder=5,
                   label="Capacity failure")

    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Coalition value")
    ax.set_title("Coalition Value $v^*(s)$: Oracle vs Online vs Non-Cooperative")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "fig3_coalition_value.png"))
    plt.close(fig)


# ── Figure 4: Gain-Sharing Rules Comparison ──────────────────────────────────

def fig_payoff_rules(oracle, coalition, standalone_ts, out_dir):
    """Grouped bar chart: per-operator total payoff under each rule vs standalone."""
    rules = ["payoffs_rule1", "payoffs_rule2", "payoffs_rule3"]
    rule_labels = ["Rule 1\n(Shapley + equal cost)", "Rule 2\n(Guard interpolation)", "Rule 3\n(Proportional)"]
    n = len(coalition)

    totals = {r: [sum(oracle[r][i]) for i in coalition] for r in rules}
    standalone_totals = [sum(standalone_ts[i]) for i in coalition]

    x = np.arange(n)
    width = 0.18
    fig, ax = plt.subplots(figsize=(10, 5))

    ax.bar(x - 1.5 * width, standalone_totals, width, color=STANDALONE_COLOR,
           label="Standalone", edgecolor="white", linewidth=0.5)
    colors_rules = ["#3b82f6", "#8b5cf6", "#06b6d4"]
    for idx, (r, lab) in enumerate(zip(rules, rule_labels)):
        ax.bar(x + (idx - 0.5) * width, totals[r], width, color=colors_rules[idx],
               label=lab, edgecolor="white", linewidth=0.5)

    ax.set_xticks(x)
    ax.set_xticklabels(OP_LABELS[:n])
    ax.set_ylabel("Total profit (60 min)")
    ax.set_title("Per-Operator Profit: Standalone vs Three Gain-Sharing Rules (Oracle)")
    ax.legend(loc="upper right", ncol=2, fontsize=8)

    # Add gain annotations on Rule 1 bars
    for i in range(n):
        gain = totals["payoffs_rule1"][i] - standalone_totals[i]
        bar_top = totals["payoffs_rule1"][i]
        ax.annotate(f"+{gain:.0f}", xy=(x[i] - 0.5 * width, bar_top),
                    fontsize=7, ha="center", va="bottom", color="#16a34a", fontweight="bold")

    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "fig4_payoff_rules.png"))
    plt.close(fig)


# ── Figure 5: Prediction Quality ────────────────────────────────────────────

def fig_prediction_quality(online, traffic, coalition, out_dir):
    """Predicted vs actual traffic per operator, with error ribbon."""
    num_steps = online["time_steps"]
    n = len(coalition)
    t = np.arange(num_steps)

    fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex=True)
    axes = axes.flatten()

    for idx, i in enumerate(coalition):
        ax = axes[idx]
        actual = [traffic[i][tt] for tt in range(num_steps)]
        predicted = [online["predicted_traffic"][tt][i] for tt in range(num_steps)]
        errors = online["prediction_errors"][i]

        ax.plot(t, actual, color=PALETTE[idx], lw=1.8, label="Actual")
        ax.plot(t, predicted, color=PALETTE[idx], lw=1.2, ls="--", alpha=0.7, label="Predicted")
        ax.fill_between(t, actual, predicted, alpha=0.15, color=PALETTE[idx])

        rmse = math.sqrt(sum(e ** 2 for e in errors) / len(errors))
        ax.set_title(f"{OP_LABELS[idx]}  (RMSE = {rmse:.2f})", fontsize=10)
        if idx >= 2:
            ax.set_xlabel("Time (min)")
        ax.set_ylabel("Traffic")
        ax.legend(loc="upper left", fontsize=7)

    fig.suptitle("Traffic Prediction Quality per Operator", fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "fig5_prediction_quality.png"))
    plt.close(fig)


# ── Figure 6: Oracle vs Online Payoff Streams ───────────────────────────────

def fig_payoff_streams(oracle, online, standalone_ts, coalition, out_dir):
    """Stacked area of per-operator payoff (Rule 1) for oracle, online, standalone."""
    num_steps = oracle["time_steps"]
    t = np.arange(num_steps)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=True)

    datasets = [
        ("Non-Cooperative", standalone_ts),
        ("Oracle (Rule 1)", oracle["payoffs_rule1"]),
        (f"Online (Rule 1, margin={online['safety_margin']:.0%})", online["payoffs_rule1"]),
    ]

    for ax, (title, data) in zip(axes, datasets):
        arrays = [np.array(data[i]) for i in coalition]
        ax.stackplot(t, *arrays, colors=PALETTE[:len(coalition)], alpha=0.75)
        ax.set_xlabel("Time (min)")
        ax.set_title(title, fontsize=10)

    axes[0].set_ylabel("Instantaneous payoff")

    # Shared legend
    handles = [mpatches.Patch(color=PALETTE[i], alpha=0.75, label=OP_LABELS[i])
               for i in coalition]
    fig.legend(handles=handles, loc="upper center", ncol=len(coalition),
               bbox_to_anchor=(0.5, 1.05), fontsize=9)

    fig.suptitle("Payoff Streams Over Time", fontsize=13, fontweight="bold", y=1.10)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "fig6_payoff_streams.png"))
    plt.close(fig)


# ── Figure 7: Safety Margin Sensitivity ──────────────────────────────────────

def fig_safety_margin_sweep(ops, traffic, coalition, out_dir):
    """Sweep safety_margin from 0% to 50%, plot value loss and capacity failures."""
    margins = np.arange(0, 0.52, 0.02)
    losses = []
    failures = []
    agreements = []

    oracle = simulate_one_hour_oracle(ops, traffic, coalition)
    oracle_total = sum(oracle["v_star"])

    for m in margins:
        online = simulate_one_hour_online(ops, traffic, coalition,
                                          window_size=5, safety_margin=float(m))
        comp = compare_oracle_vs_online(oracle, online)
        losses.append(comp["value_loss_percent"])
        failures.append(comp["capacity_failure_count"])
        agreements.append(comp["guardian_agreement"] * 100)

    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax2 = ax1.twinx()

    l1, = ax1.plot(margins * 100, losses, color=ORACLE_COLOR, lw=2, marker="o", ms=4,
                   label="Value loss (%)")
    l2, = ax2.plot(margins * 100, failures, color=ONLINE_COLOR, lw=2, marker="s", ms=4,
                   label="Capacity failures")
    l3, = ax1.plot(margins * 100, agreements, color="#16a34a", lw=1.5, ls="--",
                   label="Guardian agreement (%)")

    ax1.set_xlabel("Safety margin (%)")
    ax1.set_ylabel("Value loss / Agreement (%)", color="#1e293b")
    ax2.set_ylabel("Capacity failures (count)", color=ONLINE_COLOR)
    ax2.tick_params(axis="y", labelcolor=ONLINE_COLOR)

    ax1.axvline(15, color="#94a3b8", ls=":", lw=1, alpha=0.7)
    ax1.annotate("Default 15%", xy=(15, max(losses) * 0.9), fontsize=8,
                 ha="left", color="#64748b")

    lines = [l1, l2, l3]
    ax1.legend(lines, [l.get_label() for l in lines], loc="center right", fontsize=8)

    ax1.set_title("Safety Margin Sensitivity Analysis")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "fig7_safety_margin_sweep.png"))
    plt.close(fig)


# ── Figure 8: Summary Dashboard ─────────────────────────────────────────────

def fig_summary_dashboard(ops, traffic, coalition, oracle, online,
                          comparison, standalone_ts, out_dir):
    """A single-page dashboard summarising the whole project."""
    num_steps = oracle["time_steps"]
    n = len(coalition)
    t = np.arange(num_steps)

    fig = plt.figure(figsize=(16, 10))
    gs = gridspec.GridSpec(3, 3, hspace=0.45, wspace=0.35,
                           left=0.06, right=0.97, top=0.93, bottom=0.06)

    # ── Panel A: Traffic ────────────────────
    ax_a = fig.add_subplot(gs[0, 0])
    for i in coalition:
        ax_a.plot(t, traffic[i], color=PALETTE[i], lw=1.4, label=OP_LABELS[i])
    ax_a.set_title("(A) Traffic Profiles")
    ax_a.set_xlabel("t (min)")
    ax_a.set_ylabel("$T_i(t)$")
    ax_a.legend(fontsize=7, loc="upper left")

    # ── Panel B: Aggregate + capacity ──────
    ax_b = fig.add_subplot(gs[0, 1])
    agg = [sum(traffic[i][tt] for i in coalition) for tt in range(num_steps)]
    ax_b.fill_between(t, agg, alpha=0.2, color="#475569")
    ax_b.plot(t, agg, color="#475569", lw=1.8)
    total_cap = sum(op.capacity_epsilon for op in ops)
    ax_b.axhline(total_cap, ls="--", color="#94a3b8", lw=1, label=f"Total cap ({total_cap:.0f})")
    ax_b.set_title("(B) Aggregate Traffic")
    ax_b.set_xlabel("t (min)")
    ax_b.legend(fontsize=7)

    # ── Panel C: Guardian heatmap (oracle) ─
    ax_c = fig.add_subplot(gs[0, 2])
    mat = np.zeros((n, num_steps))
    for tt in range(num_steps):
        for g in oracle["guardians"][tt]:
            mat[g, tt] = 1.0
    ax_c.imshow(mat, aspect="auto", cmap="Blues", vmin=0, vmax=1,
                interpolation="nearest", extent=[-0.5, num_steps - 0.5, n - 0.5, -0.5])
    ax_c.set_yticks(range(n))
    ax_c.set_yticklabels([f"Op{i+1}" for i in range(n)], fontsize=8)
    ax_c.set_xlabel("t (min)")
    ax_c.set_title("(C) Guardian Schedule (Oracle)")
    for spine in ax_c.spines.values():
        spine.set_visible(False)

    # ── Panel D: v*(s) comparison ──────────
    ax_d = fig.add_subplot(gs[1, 0:2])
    standalone_agg = [sum(standalone_ts[i][tt] for i in coalition) for tt in range(num_steps)]
    ax_d.fill_between(t, oracle["v_star"], online["v_star"], alpha=0.12, color=ORACLE_COLOR)
    ax_d.plot(t, oracle["v_star"], color=ORACLE_COLOR, lw=2, label="Oracle")
    ax_d.plot(t, online["v_star"], color=ONLINE_COLOR, lw=1.5, ls="--", label="Online")
    ax_d.plot(t, standalone_agg, color=STANDALONE_COLOR, lw=1.2, ls=":", label="Standalone")
    ax_d.set_title("(D) Coalition Value $v^*(s)$ Over Time")
    ax_d.set_xlabel("t (min)")
    ax_d.set_ylabel("$v^*(s)$")
    ax_d.legend(fontsize=7, ncol=3)

    # ── Panel E: Metric cards ──────────────
    ax_e = fig.add_subplot(gs[1, 2])
    ax_e.axis("off")
    metrics = [
        ("Safety Margin", f"{online['safety_margin']:.0%}"),
        ("Guardian Agree", f"{comparison['guardian_agreement']:.1%}"),
        ("Value Loss", f"{comparison['value_loss_percent']:.2f}%"),
        ("Pred. RMSE", f"{comparison['prediction_rmse']:.2f}"),
        ("Cap. Failures", f"{comparison['capacity_failure_count']}"),
        ("Coop. Gain",
         f"+{sum(oracle['v_star']) - sum(standalone_agg):.0f} "
         f"({(sum(oracle['v_star']) - sum(standalone_agg)) / sum(standalone_agg) * 100:.1f}%)"),
    ]
    for idx, (label, value) in enumerate(metrics):
        y = 0.88 - idx * 0.155
        ax_e.text(0.05, y, label, transform=ax_e.transAxes, fontsize=9,
                  color="#64748b", va="center")
        ax_e.text(0.95, y, value, transform=ax_e.transAxes, fontsize=12,
                  fontweight="bold", color="#1e293b", va="center", ha="right")
    ax_e.set_title("(E) Key Metrics", fontsize=11, fontweight="bold")

    # ── Panel F: Per-operator profit bars ──
    ax_f = fig.add_subplot(gs[2, 0:2])
    standalone_totals = [sum(standalone_ts[i]) for i in coalition]
    oracle_totals = [sum(oracle["payoffs_rule1"][i]) for i in coalition]
    online_totals = [sum(online["payoffs_rule1"][i]) for i in coalition]

    x = np.arange(n)
    w = 0.25
    ax_f.bar(x - w, standalone_totals, w, color=STANDALONE_COLOR, label="Standalone")
    ax_f.bar(x, oracle_totals, w, color=ORACLE_COLOR, label="Oracle (Rule 1)")
    ax_f.bar(x + w, online_totals, w, color=ONLINE_COLOR, label="Online (Rule 1)")
    ax_f.set_xticks(x)
    ax_f.set_xticklabels(OP_LABELS[:n])
    ax_f.set_ylabel("Total profit")
    ax_f.set_title("(F) Per-Operator Profit Comparison")
    ax_f.legend(fontsize=7, ncol=3)

    # ── Panel G: Prediction error boxplot ──
    ax_g = fig.add_subplot(gs[2, 2])
    error_data = [online["prediction_errors"][i] for i in coalition]
    bp = ax_g.boxplot(error_data, tick_labels=[f"Op{i+1}" for i in coalition],
                      patch_artist=True, widths=0.5)
    for patch, color in zip(bp["boxes"], PALETTE[:n]):
        patch.set_facecolor(color)
        patch.set_alpha(0.4)
    ax_g.axhline(0, color="#94a3b8", ls="-", lw=0.8)
    ax_g.set_ylabel("Prediction error")
    ax_g.set_title("(G) Prediction Error Distribution")

    fig.suptitle("RAN Sharing Cooperative Game — Simulation Dashboard",
                 fontsize=15, fontweight="bold", y=0.98)
    fig.savefig(os.path.join(out_dir, "fig8_dashboard.png"))
    plt.close(fig)


# ── Animated GIF: simulation over time ───────────────────────────────────────

def animated_simulation(ops, traffic, coalition, oracle, online,
                        standalone_ts, out_dir):
    """
    Animated GIF showing the simulation evolving minute by minute.
    Four panels: traffic, guardian heatmap, v*(s), cumulative profit.
    """
    num_steps = oracle["time_steps"]
    n = len(coalition)

    fig = plt.figure(figsize=(14, 8))
    gs = gridspec.GridSpec(2, 2, hspace=0.35, wspace=0.3,
                           left=0.07, right=0.96, top=0.92, bottom=0.08)

    ax_traffic = fig.add_subplot(gs[0, 0])
    ax_guard = fig.add_subplot(gs[0, 1])
    ax_value = fig.add_subplot(gs[1, 0])
    ax_profit = fig.add_subplot(gs[1, 1])

    # Pre-compute cumulative profits
    cum_standalone = {i: np.cumsum(standalone_ts[i]) for i in coalition}
    cum_oracle = {i: np.cumsum(oracle["payoffs_rule1"][i]) for i in coalition}

    # Limits
    all_traffic = [traffic[i][t] for i in coalition for t in range(num_steps)]
    t_max = max(all_traffic) * 1.1
    v_max = max(oracle["v_star"]) * 1.15
    v_min = min(min(oracle["v_star"]), min(sum(standalone_ts[i][t] for i in coalition)
                                            for t in range(num_steps))) * 0.9
    p_max = max(cum_oracle[i][-1] for i in coalition) * 1.15

    # Guardian matrix for animation
    guard_mat = np.zeros((n, num_steps))

    time_text = fig.text(0.5, 0.96, "", ha="center", fontsize=14, fontweight="bold")

    def init():
        for ax in [ax_traffic, ax_value, ax_profit]:
            ax.clear()
        ax_guard.clear()
        return []

    def update(frame):
        t_now = frame
        t_arr = np.arange(t_now + 1)

        # ── Traffic panel ──
        ax_traffic.clear()
        for i in coalition:
            ax_traffic.plot(t_arr, [traffic[i][tt] for tt in range(t_now + 1)],
                           color=PALETTE[i], lw=1.5, label=OP_LABELS[i] if frame == 0 else "")
            # Show capacity as dashed
            if t_now == 0:
                ax_traffic.axhline(ops[i].capacity_epsilon, color=PALETTE[i],
                                   ls="--", lw=0.6, alpha=0.4)
        ax_traffic.set_xlim(0, num_steps - 1)
        ax_traffic.set_ylim(0, t_max)
        ax_traffic.set_title("Traffic $T_i(t)$")
        ax_traffic.set_xlabel("t (min)")
        if t_now == 0:
            ax_traffic.legend(fontsize=7, loc="upper left")

        # ── Guardian heatmap ──
        for g in oracle["guardians"][t_now]:
            guard_mat[g, t_now] = 1.0
        ax_guard.clear()
        ax_guard.imshow(guard_mat, aspect="auto", cmap="Blues", vmin=0, vmax=1,
                        interpolation="nearest",
                        extent=[-0.5, num_steps - 0.5, n - 0.5, -0.5])
        ax_guard.axvline(t_now, color="#ef4444", lw=1.5, alpha=0.7)
        ax_guard.set_yticks(range(n))
        ax_guard.set_yticklabels([f"Op{i+1}" for i in range(n)], fontsize=8)
        ax_guard.set_title("Guardian Schedule (Oracle)")
        ax_guard.set_xlabel("t (min)")
        for spine in ax_guard.spines.values():
            spine.set_visible(False)

        # ── v*(s) panel ──
        ax_value.clear()
        standalone_agg_so_far = [sum(standalone_ts[i][tt] for i in coalition)
                                  for tt in range(t_now + 1)]
        ax_value.plot(t_arr, oracle["v_star"][:t_now + 1],
                      color=ORACLE_COLOR, lw=2, label="Oracle")
        ax_value.plot(t_arr, online["v_star"][:t_now + 1],
                      color=ONLINE_COLOR, lw=1.5, ls="--", label="Online")
        ax_value.plot(t_arr, standalone_agg_so_far,
                      color=STANDALONE_COLOR, lw=1.2, ls=":", label="Standalone")
        ax_value.set_xlim(0, num_steps - 1)
        ax_value.set_ylim(v_min, v_max)
        ax_value.set_title("Coalition Value $v^*(s)$")
        ax_value.set_xlabel("t (min)")
        if t_now == 0:
            ax_value.legend(fontsize=7, loc="lower right")

        # ── Cumulative profit panel ──
        ax_profit.clear()
        for i in coalition:
            ax_profit.plot(t_arr, cum_standalone[i][:t_now + 1],
                          color=PALETTE[i], ls=":", lw=1, alpha=0.5)
            ax_profit.plot(t_arr, cum_oracle[i][:t_now + 1],
                          color=PALETTE[i], lw=1.8, label=OP_LABELS[i] if t_now == 0 else "")
        ax_profit.set_xlim(0, num_steps - 1)
        ax_profit.set_ylim(0, p_max)
        ax_profit.set_title("Cumulative Profit (Oracle Rule 1)")
        ax_profit.set_xlabel("t (min)")
        if t_now == 0:
            ax_profit.legend(fontsize=7, loc="upper left")

        time_text.set_text(f"RAN Sharing Simulation  —  t = {t_now} min")
        return []

    anim = FuncAnimation(fig, update, frames=num_steps, init_func=init,
                         interval=120, blit=False)
    gif_path = os.path.join(out_dir, "simulation.gif")
    anim.save(gif_path, writer=PillowWriter(fps=8))
    plt.close(fig)
    return gif_path


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    make_gif = "--gif" in sys.argv

    out_dir = os.path.join(os.path.dirname(__file__), "..", "figures")
    os.makedirs(out_dir, exist_ok=True)

    print("Running simulations...")
    ops, traffic, coalition, oracle, online, comparison, standalone_ts = _run_simulations(
        safety_margin=0.15
    )

    print("Generating Figure 1: Traffic Profiles...")
    fig_traffic_profiles(ops, traffic, coalition, out_dir)

    print("Generating Figure 2: Guardian Timeline...")
    fig_guardian_timeline(ops, coalition, oracle, online, out_dir)

    print("Generating Figure 3: Coalition Value...")
    fig_coalition_value(oracle, online, standalone_ts, coalition, out_dir)

    print("Generating Figure 4: Payoff Rules Comparison...")
    fig_payoff_rules(oracle, coalition, standalone_ts, out_dir)

    print("Generating Figure 5: Prediction Quality...")
    fig_prediction_quality(online, traffic, coalition, out_dir)

    print("Generating Figure 6: Payoff Streams...")
    fig_payoff_streams(oracle, online, standalone_ts, coalition, out_dir)

    print("Generating Figure 7: Safety Margin Sensitivity...")
    fig_safety_margin_sweep(ops, traffic, coalition, out_dir)

    print("Generating Figure 8: Summary Dashboard...")
    fig_summary_dashboard(ops, traffic, coalition, oracle, online,
                          comparison, standalone_ts, out_dir)

    if make_gif:
        print("Generating Animated GIF (this may take a minute)...")
        gif_path = animated_simulation(ops, traffic, coalition, oracle, online,
                                       standalone_ts, out_dir)
        print(f"  -> {gif_path}")

    print(f"\nAll figures saved to: {os.path.abspath(out_dir)}/")


if __name__ == "__main__":
    main()
