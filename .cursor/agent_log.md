# RAN Sharing Project — Agent Development Log

## Project Timeline

### Session 1: Initial Implementation

**Task**: Generate `ran_sharing.py` based on cursor rules describing a cooperative game for RAN sharing.

**What was built**:
- Single-file implementation with all functions: `OperatorParams`, `single_operator_utility`, `allocate_uniform_until_saturation`, `coalition_utility`, `coalition_value_star`, `shapley_values`, `payoff_rule1/2/3`, `simulate_one_hour`.
- 3 operators, constant traffic (T1=40, T2=30, T3=20 for all t).

**Bug found**: Python `list[int] | None` syntax failed on the user's Python version (pre-3.10). Fixed by importing `Optional` from `typing`.

---

### Session 2: Add 4th Operator + Time-Varying Traffic

**Task**: Add a 4th operator and make traffic change over time.

**What was built**:
- Operator4: ε=70, c=0.95, β=0.28, K=-11.0
- Time-varying traffic using sinusoidal/bell/counter-cyclical/growth patterns.

**Problem found**: Guardian selection was always `[0, 2]` for all 60 time steps. User asked: "shouldn't it re-decide every minute?"

**Root cause**: The traffic range (100-122) was too narrow. All time steps fell into the same regime where `[0, 2]` (capacity 160) was always optimal. No bug in the code — the decision logic was correct, just the data didn't create enough variation.

**Fix**: Redesigned traffic profiles with much wider range (138-209) to cross multiple capacity thresholds. Result: guardian selection now varies across `[0,2]`, `[0,3]`, `[0,1]`, `[0,2,3]` depending on traffic level.

---

### Session 3: Code Modularization

The user manually refactored the single file into a modular structure:
```
src/
├── generate_data.py   (OperatorParams, example data)
├── utility.py         (single_operator_utility)
├── allocate.py        (allocate_uniform_until_saturation)
├── optimiser.py       (coalition_utility, coalition_value_star)
├── profit.py          (shapley_values, payoff_rule1/2/3)
└── main.py            (simulate_one_hour, __main__)
```
Cursor rules updated to reflect new structure.

---

### Session 4: Oracle vs Online Simulation Modes

**Task**: Add a realistic "online" mode where decisions at time t use only history 0..t-1.

**What was built**:
- `predict.py`: Simple moving average predictor with configurable `window_size`.
- Renamed `simulate_one_hour` → `simulate_one_hour_oracle` (god's eye view).
- New `simulate_one_hour_online`: predicts traffic, selects guardians based on prediction, computes actual value.
- `compare_oracle_vs_online`: computes agreement rate, value loss, RMSE.

**Initial results**: 75% guardian agreement, 0.29% value loss, RMSE 3.24.

---

### Session 5: Capacity Failure Bug

**User noticed**: At t=10, Oracle chose `[0,1]` but Online chose `[0,2]`, yet both showed v*=150.47. Different guardians should not produce identical values.

**Root cause (BUG)**: When Online's chosen guardians had insufficient capacity for actual traffic, the code fell back to `coalition_value_star(actual_traffic)` — effectively computing the oracle-optimal value. This silently masked prediction failures.

**Example**: t=10, actual total traffic = 170.54. Online chose `[0,2]` (capacity 160, insufficient!). Instead of penalizing, the code recalculated the optimal and returned the oracle value.

**Fix**: Replaced the fallback with degraded value computation:
- Revenue scaled by `served_fraction = capacity / demand`
- Guardians at full load (ρ=1.0)
- Track capacity failures with details (time, needed, available, shortfall)

**After fix**: t=10 now shows Oracle v*=150.47 vs Online v*=142.83. Total: 9 capacity failures detected, value loss increased from 0.29% to 0.45%.

---

### Session 6: Payoff Functions Bug

**User noticed**: Per-operator profits were identical between Oracle and Online modes despite different total v* values.

**Root cause (BUG)**: `payoff_rule1/2/3` internally called `coalition_value_star()` to find the optimal guardian set, ignoring the actual guardians chosen in Online mode. So payoffs were always computed as if the oracle-optimal decision was made.

**Fix**: Rewrote all three payoff functions to accept optional parameters:
- `payoff_rule1`: `actual_v_star`, `actual_guardians`, `actual_allocation`
- `payoff_rule2`: `actual_v_star`, `actual_guardians`
- `payoff_rule3`: `actual_v_star`

When provided, these override the internal `coalition_value_star` call. Oracle mode passes `None` (uses optimal), Online mode passes actual values.

**After fix**: Per-operator profits now correctly differ between modes. Oracle total = 9414.67, Online total = 9372.34.

---

### Session 7: Safety Margin

**Task**: Losing traffic is more severe than suboptimal profit. Add a 30% safety margin.

**What was built**: `safety_margin` parameter in `simulate_one_hour_online`. Predicted traffic is inflated by `(1 + safety_margin)` before guardian selection only. All other computations (v*, payoffs, errors) use real values.

**Result**: Capacity failures dropped from 9 to 0. Value loss increased from 0.45% to 5.73%. Guardian agreement dropped to 3.3% (expected — the margin causes over-provisioning).

---

### Session 8: Non-Cooperative Baseline

**Task**: Add standalone (non-cooperative) profit comparison.

**What was built**: Compute `v(A_i)` for each operator at each time step independently, sum over 60 steps. Display alongside Oracle/Online profits with a "vs Alone" gain column.

**Key result**: Cooperation gains ~10-12% over non-cooperative operation. Every operator benefits from the coalition.

---

### Session 9: Visualization Suite

**Task**: Create research-quality visualizations.

**What was built** (`visualisation.py`):
1. **fig1**: Traffic profiles (per-operator + aggregate vs capacity thresholds)
2. **fig2**: Guardian timeline heatmap (Oracle vs Online)
3. **fig3**: Coalition value v*(s) over time (Oracle vs Online vs Standalone)
4. **fig4**: Grouped bar chart of per-operator profit under 3 rules vs standalone
5. **fig5**: Prediction quality (predicted vs actual per operator, with RMSE)
6. **fig6**: Stacked area payoff streams (Standalone / Oracle / Online)
7. **fig7**: Safety margin sensitivity sweep (0-50%)
8. **fig8**: Single-page summary dashboard (7 panels)
9. **simulation.gif**: Animated 60-frame GIF of the simulation

**Minor fix**: `labels=` parameter renamed to `tick_labels=` for matplotlib 3.10 compatibility.

---

### Session 10: Op1 Always Guardian — Investigation

**User asked**: Why is Operator 1 always selected as guardian?

**Finding**: NOT a bug. Op1 has the lowest cost per unit capacity (0.103) — 33% cheaper than the next best (Op3 at 0.154). Combined with its largest capacity (100/310 = 32%), it always appears in the optimal guardian set. The set `[1,2,3]` is feasible at all traffic levels but always produces lower value than sets including Op1.

**Implication**: The example operator parameters create a scenario where one operator dominates. For more interesting guardian dynamics, parameters should be rebalanced so no single operator is universally cheapest.

---

## Known Limitations

1. **Shapley computation is O(N! * 2^N)**: Works for N=4 but won't scale. For N>6, approximate methods (sampling permutations) would be needed.

2. **Prediction is naive**: Simple moving average doesn't capture trends well during rapid traffic changes (see prediction errors at t=15 where traffic rises fast).

3. **Cold start**: At t=0, Online mode uses actual traffic as "prediction" since there's no history. This gives it a free pass on the first step.

4. **Capacity failure model is simplified**: Revenue is scaled linearly by served fraction. In reality, dropped traffic might have non-linear penalties (SLA violations, customer churn).

5. **Operator parameters are unbalanced**: Op1 dominates as guardian due to best cost-efficiency. More competitive parameters would showcase richer coalition dynamics.

6. **Single coalition assumed**: The simulation always uses the grand coalition. Sub-coalition analysis (which groups actually form?) is not implemented.

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Permutation-based Shapley | Exact values for small N; easy to verify correctness |
| Water-filling allocation | Matches the "uniform-until-saturation" rule from the paper |
| Safety margin on prediction only | Inflating for guardian selection avoids lost traffic; using real values for payoffs preserves accuracy |
| Degraded revenue model | When capacity < demand, scale revenue by served fraction (conservative estimate) |
| Separate Oracle/Online payoff paths | Payoff functions accept optional actuals to avoid silently falling back to oracle-optimal |

---

## File Inventory

```
src/
├── generate_data.py     # Data model + example operators/traffic
├── utility.py           # v(A_i) = c*T - β*ρ + K
├── allocate.py          # Water-filling allocation
├── optimiser.py         # coalition_utility, coalition_value_star
├── profit.py            # Shapley values, 3 payoff rules
├── predict.py           # Moving average predictor
├── main.py              # Oracle/Online simulation, comparison, CLI output
└── visualisation.py     # 8 figures + animated GIF

figures/
├── fig1_traffic_profiles.png
├── fig2_guardian_timeline.png
├── fig3_coalition_value.png
├── fig4_payoff_rules.png
├── fig5_prediction_quality.png
├── fig6_payoff_streams.png
├── fig7_safety_margin_sweep.png
├── fig8_dashboard.png
└── simulation.gif

.cursor/
├── rules                # Project rules / documentation
└── agent_log.md         # This file
```
