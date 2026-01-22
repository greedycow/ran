## Step 0 : Overview

In one sentence:
**It uses “cooperative game theory + the Shapley value” to model: when multiple operators do night-time RAN sharing (sharing base stations, turning off redundant equipment), how to decide who keeps the base station on (“guardians”), and how to split the resulting profit fairly.**

---

## Step 1: Basic definitions (Section 1)

1. **Set of operators \(A\)**

   - There is a group of operators, denoted
     \(A = (A_i)_{1 \le i \le N}\).
     Intuitively: \(N\) operators co-located at the same site/base station.

2. **Equipment capacity of each operator \(\varepsilon_i\)**

   - \(\varepsilon = (\varepsilon_i)_{1 \le i \le N}\) is the vector of capacities.
   - \(\varepsilon_i\) is operator \(A_i\)’s “available radio resource capacity” at the site (e.g., the max traffic it can carry).

3. **The idea of RAN sharing**

   - At night, traffic is low; keeping every operator’s equipment on wastes energy.
   - So: **let some operators act as “guardians (gardiens)”, keep their equipment on and serve all users; the others can switch off**.
   - This forms a “coalition” where members cooperate, save energy, and share profit.

4. **What is a coalition?**

   - A coalition \(s\) is a subset of operators, e.g. \(\{A_1, A_3\}\).
   - The paper says “k-uplet”: a coalition of size \(k\).

5. **The different cases of \(k\)**

   - \(k = 0\): only the empty coalition ⇒ effectively no operator in the area.
   - \(k = 1\): a single operator alone, no real “cooperation”.
   - \(2 \le k \le N\): there are \(\binom{N}{k}\) coalitions; within each, we may designate one or more “guardians” (cooperative setting).

6. **The set \(S\) of all possible coalitions**

   - \(S\): all possible coalitions (excluding the fully empty case) — in theory there are \(2^N\) subsets; if the empty set is not allowed, subtract 1.

> Intuition:
> **\(A\) is the full set of players, \(S\) is “all possible sub-groups of players”.**
> All subsequent game-theoretic objects define a “value \(v(s)\)” on coalitions and “how to allocate \(v(s)\)”.

---

## Step 2: Utility function of a single operator (non-cooperative case)

First consider **each operator acting alone** and define its profit.

### 2.1 Definition of \(v(A_i)\)

- The utility function is denoted \(v(\cdot)\).
- For a single operator \(A_i\):

$$
v(A_i) = \underbrace{c_i T_i}_{\text{revenue from selling traffic}} - \underbrace{\beta_i \rho_i}_{\text{energy-related cost}} + \underbrace{K_i}_{\text{various fixed costs (negative)}}
$$

The paper’s wording is essentially:

- Revenue = price × traffic (\(c_i\) is unit price, \(T_i\) is traffic)
- Costs include:
  - Equipment depreciation (invest in capacity \(\varepsilon_i\), amortized over time: a function \(u(\varepsilon_i)\))
  - Energy cost (electricity)
  - Maintenance cost (can be included in a constant \(K_i < 0\))

### 2.2 Energy model \(\rho_i\) and power consumption

- Total power draw \(x_i = x_{i,0} + \beta \rho_i\)
  - \(x_{i,0}\): “fixed” power needed just to keep the base station on
  - \(\beta\): coefficient converting “load” into extra power
  - \(\rho_i \in [0, 1]\): load ratio, depending on capacity \(\varepsilon_i\) and traffic \(T_i\):

\[
\rho_i = f(\varepsilon_i, T_i)
\]

Intuitively:

- Higher traffic \(T_i \uparrow \Rightarrow\) higher load \(\rho_i \uparrow\)
- Higher capacity \(\varepsilon_i \uparrow \Rightarrow\) for the same traffic, lower load \(\rho_i \downarrow\)

> The purpose of this step: **define a baseline profit \(v(A_i)\) for “independent operation”**, so that later we can compare whether joining a coalition is beneficial.

---

## Step 3: Coalition game (cooperative case)

Now we move to **multi-operator cooperation**.

### 3.1 Coalition \(s\) and guardian set \(l_s\)

- Let \(s \subset A\) be a coalition of size \(k\).
- Within coalition \(s\), choose a subset of operators to act as guardians, denoted \(l_s \subset s\): they keep their equipment on and provide service.
- The remaining members \(s \setminus l_s\): they essentially switch off and “hand over” their customers to the guardians, paying them accordingly.

Definitions:

- Total traffic of the coalition:

\[
T(s) = \sum_{a \in s} T_a
\]

- Total capacity of the guardians:

\[
\varepsilon(l_s) = \sum_{a \in l_s} \varepsilon_a
\]

Feasibility constraint:

\[
T(s) \le \varepsilon(l_s)
\]

Meaning: guardians’ total capacity must be sufficient for the coalition’s total traffic.

### 3.2 Coalition value function \(v(s, l_s)\)

The paper gives:

$$
v(s, l_s)
= \sum_{a \in s} c_a T_a - \sum_{a \in l_s} \beta_a \tilde{\rho}_a(l_s) + \sum_{a \in l_s} K_a
$$

Explanation:

1. \(\sum_{a \in s} c_a T_a\):
   all users still pay their original operator; total revenue is unchanged, only the network is shared.

2. \(- \sum_{a \in l_s} \beta_a \tilde{\rho}_a(l_s)\):
   guardians bear the actual load \(\tilde{\rho}_a\), hence they pay electricity/variable costs.
   - For a non-guardian \(a\), \(\tilde{\rho}_a = 0\) because its equipment is off.

3. \(\sum_{a \in l_s} K_a\):
   guardians also bear their fixed costs (negative).

> Intuition:
> **Profit = coalition revenue − guardians’ costs.**
> Non-guardians mainly “pay money” (in some way compensating the guardians for the costs they do not pay themselves).

---

## Step 4: Choose the “best guardian configuration” for a coalition — obtain \(v^*(s)\)

For a given coalition \(s\), we must not only choose who belongs to the guardian set \(l_s\), but also decide how coalition traffic is split among guardians. The paper defines:

\[
v^*(s) = \max_{l_s \in L_s} v(s, l_s)
\]

Meaning: for coalition \(s\), **among all possible guardian choices + traffic allocation schemes, take the one that yields the highest profit**.

Then the paper does two things:

1. Defines two “traffic allocation rules” (how to distribute total traffic \(T(s)\) among guardians)
2. Proves that \(v^*(s)\) is “superadditive”.

---

## Step 5: Two traffic allocation rules

Let \(s\) be a coalition and \(l_s\) its guardian set.
Traffic allocation \(\tilde{T}_a\) for guardians must satisfy:

- \(\sum_{a \in l_s} \tilde{T}_a = T(s)\) (conservation of total traffic)
- \(0 \le \tilde{T}_a \le \varepsilon_a\) (each guardian’s assigned traffic does not exceed its own capacity)

### Rule 1: **Prudent rule (prudente)**

When a new operator \(i\) joins the coalition and becomes a guardian:

- The existing guardians’ allocation (for \(l_s\)) remains unchanged;
- The newcomer \(i\) **at least carries its own traffic \(T_i\)**.

Thus:

\[
\tilde{T}_a(l'_s) =
\begin{cases}
\tilde{T}_a(l_s), & a \in l_s \\
T_i,              & a = i
\end{cases}
\]

Intuition:
**simple and conservative: I join, but I first only take care of my own users.**

---

### Rule 2: **Uniform until saturation (uniforme jusqu’à saturation)**

Idea: **balance guardians’ load as much as possible**, instead of “newcomer only carries itself”.

- Find \(\lambda \ge 0\) such that

\[
\sum_{a \in l_s} \min(\varepsilon_a, \lambda) = T(s)
\]

- Then define

\[
\tilde{T}_a(l_s) = \min(\varepsilon_a, \lambda)
\]

Meaning:

- Guardians with small capacity may be “filled up” (\(\tilde{T}_a = \varepsilon_a\)).
- Guardians with large capacity each carry the same traffic \(\lambda\), until the total matches the coalition traffic.

After a new operator \(i\) joins, recompute a new \(\lambda'\) for the new guardian set so that the total equals \(T(s) + T_i\), then allocate with the same rule.

---

## Step 6: The idea of superadditivity

Target statement:

\[
\forall s \subset S,\ \forall i \notin s,\quad v^*(s \cup \{i\}) \ge v^*(s) + v(\{i\})
\]

Meaning:
**adding an independent operator \(i\) into coalition \(s\) yields a total value at least as large as “the coalition value + its standalone value”.**

The paper provides a proof sketch (using the prudent rule):

1. We know: within \(s\) there exists an optimal guardian configuration \(l_s^*\) such that

\[
v^*(s) = v(s, l_s^*)
\]

2. Add \(i\) to form \(s' = s \cup \{i\}\). Choose the new guardian set as \(l'_s = l_s^* \cup \{i\}\).

3. Use the prudent traffic rule: old guardians keep the same load; new guardian \(i\) carries its own traffic \(T_i\).

4. Under this configuration, we obtain

\[
v(s', l'_s) = v(s, l_s^*) + v(\{i\}) = v^*(s) + v(\{i\})
\]

5. Since \(v^*(s')\) is the maximum over all feasible configurations:

\[
v^*(s') \ge v(s', l'_s) = v^*(s) + v(\{i\})
\]

Hence superadditivity is proven.

> Interpretation:
> **the coalition’s “cake” can only get larger**; bringing more players in does not reduce total value.
> This is an important assumption for using Shapley value allocation later.

---

## Step 7: How to allocate profit within a coalition? (Section 3)

Given each coalition’s total value \(v^*(s)\), we now address “how to split the money”:

- For each operator \(A_i\), define a payoff allocation \(g(A_i)\).
- We want:

  1. **Efficiency (efficacité)**: the sum of allocated payoffs equals the coalition’s value
     \(\sum_{i \in s} g(A_i) = v^*(s)\)
  2. **Attractiveness**: each operator’s payoff in the coalition is at least its standalone payoff
     \(g(A_i) \ge v(A_i)\)

The paper proposes three practical schemes, starting with the classical **Shapley value**.

---

## Step 8: Shapley value (Method 0: theoretical basis)

The Shapley value is the classical “fair allocation” concept in cooperative games, based on four axioms:

1. **Efficiency**: the Shapley values sum to the total value.
2. **Symmetry**: if two players contribute the same to any coalition (same marginal contribution), they get the same Shapley value.
3. **Null player**: if a player never increases any coalition’s value, its Shapley value is 0.
4. **Additivity**: if we add two games (two value functions), Shapley values add linearly.

Shapley proved that the **unique** allocation satisfying these axioms is:

\[
\phi_i(v) = \sum_{s \subseteq S}
\frac{|s|!(N - |s| - 1)!}{N!}
\bigl[v^*(s \cup \{A_i\}) - v^*(s)\bigr]
\]

Explanation:

- Consider all possible “arrival orders” of players as uniformly random.
- For each order, when \(A_i\) arrives, compute its marginal contribution to the current coalition:
  \(v^*(s \cup \{A_i\}) - v^*(s)\).
- The Shapley value is the average marginal contribution over all orders.

> In our setting:
> **\(\phi(A_i)\)** being larger means operator \(A_i\) is more critical to the coalition (more traffic, important capacity, efficient as a guardian, etc.).

---

## Step 9: Three “practical allocation schemes” proposed in the paper

### Method 1: Split costs “AA-style”, then split profit using Shapley (partage artisanal)

**Step 1: Tricount-style cost equalization**

1. The coalition’s total “variable cost + fixed cost” borne by guardians is:

\[
\sum_{a \in l_s} \beta_a \tilde{\rho}_a(l_s) - \sum_{a \in l_s} K_a
\]

2. Split this total cost equally among all coalition members (including non-guardians):

Each member should pay:

\[
D_s =
\frac{\sum_{a \in l_s} \beta_a \tilde{\rho}_a(l_s) - \sum_{a \in l_s} K_a}{|s|}
\]

3. For a specific operator \(A_i\):

   - If it is a guardian, the cost it “would” pay is:

\[
D_i = \beta_i \tilde{\rho}_i(l_s) - K_i
\]

   - If it is a non-guardian, \(D_i = 0\) (because its equipment is off).

4. Via transfers, ensure everyone ends up paying \(D_s\):

   - Non-guardians: pay \(D_s\) into a “common pool”
   - Guardians: receive back \(D_i - D_s\) from the pool (may be negative, meaning they top up)

After this, **everyone bears the same cost**, so we stop arguing about who paid more electricity as a guardian.

**Step 2: Use Shapley to split “total revenue”**

- The coalition’s total revenue is:

\[
\sum_{a \in s} c_a T_a = v^*(s) + |s| D_s
\]

(because total revenue − total cost = net coalition profit \(v^*(s)\))

- Use Shapley values to determine each member’s share of revenue:

\[
g(A_i) = \phi(A_i) \cdot \frac{\sum_{a \in s} c_a T_a}{v^*(s)} - D_s
\]

Interpretation:

- First allocate revenue proportionally to “contribution” (\(\phi(A_i)\));
- Then subtract the common cost share \(D_s\).

This guarantees efficiency:
\(\sum_{i \in s} g(A_i) = v^*(s)\).

---

### Method 2: Distinguish “being a guardian” vs “not being a guardian” in Shapley value

The paper refines the idea:

1. Define the usual Shapley value \(\phi(A_i)\) (where \(A_i\) is allowed to be a guardian).

2. Define a modified value function \(v_i^*\) where \(A_i\) is forbidden to be a guardian:
   among all guardian configurations, enforce \(A_i \notin l_s\), then take the maximum:

\[
v_i^*(s) = \max_{l_s \in L_s,\ A_i \notin l_s} v(s, l_s)
\]

Based on this new \(v_i^*\), compute another Shapley-like value \(\psi(A_i)\).

3. Interpolate between the two using load \(\rho_i\):

\[
g(A_i) = \rho_i \phi(A_i) + (1 - \rho_i) \psi(A_i)
\]

Meaning:

- If \(\rho_i\) is large (often acts as a guardian, high load), it is closer to \(\phi(A_i)\)
- If \(\rho_i\) is small (rarely a guardian), it is closer to \(\psi(A_i)\)

4. To preserve efficiency, normalize:

\[
g(A_i) =
[\rho_i \phi(A_i) + (1 - \rho_i) \psi(A_i)] \cdot
\frac{v^*(s)}{\sum_j [\rho_j \phi(A_j) + (1 - \rho_j) \psi(A_j)]}
\]

This ensures \(\sum_i g(A_i) = v^*(s)\).

---

### Method 3: Allocate directly proportional to standalone profit \(v(A_i)\)

This is the simplest:

\[
g(A_i) = v(A_i)\, \frac{v^*(s)}{\sum_{j \in s} v(A_j)}
\]

- Each member’s payoff is proportional to how much it earns when operating alone.
- This guarantees:
  - Efficiency: the sum equals \(v^*(s)\)
  - Attractiveness: can be tuned so each \(g(A_i) \ge v(A_i)\) (in practice, needs checking)

Downside:
**this method does not explicitly distinguish “who is guardian, who has more traffic, who has more capacity”**; it depends only on “individual baseline profit”, which may be considered insufficiently granular.

