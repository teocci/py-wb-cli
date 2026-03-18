# WB CLI — Wildberries Advertising Operations Framework
> Draft v0.1 — Design Document

---

## 0. The Problem We Are Solving

Wildberries already operates the advertising auction, delivery, placements, and internal ranking logic. What sellers control through the API is not the ad engine itself, but the configuration surface around it: campaign creation, product inclusion, placements, bids, minus phrases, budgets, and statistics.

That sounds straightforward until real operations begin.

A seller trying to scale ads on WB faces four compounding problems:

1. The market is unstable. Search demand shifts by day, by season, by promotions calendar, and by competitor activity.
2. Visibility is not enough. First-page exposure only matters when it produces economically useful traffic.
3. The control surface is fragmented. Campaign state, budgets, bids, placements, search-cluster controls, and analytics signals are spread across different endpoint families.
4. Manual operations do not scale. Repeatedly checking campaigns, exporting statistics, comparing search clusters, adjusting bids, and pruning waste by hand is slow, inconsistent, and difficult to audit.

A seller or operator eventually ends up with a workflow like this:

```text
operator thinks: “I need to improve perfume campaign performance today”
→ open WB dashboard
→ inspect campaign list
→ inspect budget balance
→ inspect stats for yesterday
→ inspect search clusters
→ compare SKU performance manually
→ guess which bids to raise
→ guess which queries to suppress
→ top up budget if campaign is starved
→ repeat tomorrow from scratch
```

This is operationally expensive and structurally weak. It does not produce a reusable system. It does not create a stable interface for AI agents. It does not preserve decisions in a form that can be reviewed or replayed.

The thesis of this project is simple:

**wrap the WB API in a disciplined command-line control plane, then let operators and AI agents work through that control plane instead of improvising against raw HTTP or the web UI.**

The CLI must therefore be more than a convenience wrapper. It must become the canonical execution layer for WB ads operations.

---

## 1. Design Goals

| Goal | Metric |
|---|---|
| Operational coverage | All essential campaign operations exposed through CLI |
| Agent compatibility | Deterministic JSON I/O for every meaningful command |
| Safety | Dry-run support for every mutating workflow |
| Multi-account support | Multiple profiles and tokens handled cleanly |
| Auditability | Every write action logged locally |
| Extensibility | Promotion core with optional Analytics bridge |
| Portability | Single install, scriptable, cross-platform |
| Human usability | Commands readable enough for daily manual use |

The CLI must satisfy two different classes of users simultaneously.

The first is the human operator who wants commands like:

```bash
wb campaign list
wb stats campaign --id 12345 --from 2026-03-01 --to 2026-03-07
wb cluster set-bids --campaign 12345 --nm 998877 --file bids.json
```

The second is the AI agent that needs stable machine contracts, explicit exit codes, structured errors, and safe mutation boundaries.

If either of those user classes is neglected, the CLI will be incomplete.

---

## 2. Product Understanding — What WB Actually Handles

Wildberries handles the advertisement delivery system itself. The API does not ask the seller to manage ranking algorithms, internal inventory dispatch, or auction resolution. Those responsibilities remain on the WB side.

What the API gives us is a seller-side control surface over campaign inputs and campaign operations.

At a practical level, the WB API allows the seller to influence:

- which products are included in a campaign
- what kind of campaign is created
- what bid model is used
- whether placements such as search or recommendations are enabled where applicable
- what bids are set at the item level
- what bids are set at the search-cluster level where supported
- which minus phrases suppress irrelevant demand
- how much budget is allocated to a campaign
- when campaigns are started, paused, stopped, renamed, or deleted
- which performance statistics are retrieved for campaign analysis

That distinction is important because it defines the real scope of the CLI.

The CLI is not a custom ad engine.

It is an **advertising operations framework** for controlling WB’s ad system safely and intelligently.

---

## 3. The Core Operating Unit — Campaign + Product + Search Cluster

The most common beginner mistake is to treat a WB campaign as the only meaningful object.

That is too coarse.

The real operational unit is a three-part structure:

1. the **campaign** as the lifecycle and budget container
2. the **product card** as the selling entity receiving traffic
3. the **search cluster** as the practical approximation of query intent

This matters because performance problems usually happen at one of those three levels.

A campaign can be healthy overall while one product inside it underperforms.
A product can be strong overall while several search clusters are wasteful.
A campaign can have efficient clusters but still fail because its budget is underfunded.

Therefore the CLI and the later optimizer must be designed to reason at all three levels, not only at the campaign level.

---

## 4. Main Sales Levers Available Through WB Campaign Tooling

### 4.1 Campaign creation

WB exposes campaign creation through the Promotion API with current campaign semantics such as `bid_type` and `payment_type`. This is the foundational operation because every later control path depends on the campaign existing in a compatible mode.

This is not just a “create” action. It is a strategic choice.

A campaign created with the wrong bid mode or payment model can limit later optimization or make the economics harder to control.

### 4.2 Product selection for campaigns

WB exposes the inventory discovery path required to identify which subjects and which product cards are eligible for campaign usage.

This is one of the highest-leverage operations in the whole system.

The wrong product should not be force-amplified with bids. A weak product card with low conversion, poor reviews, bad price positioning, or low stock availability will often burn budget regardless of bidding strategy.

Therefore product inclusion must be treated as a first-class optimization lever.

### 4.3 Placement control

For campaigns where placement adjustment is supported, the seller can control whether the campaign is oriented toward search, recommendations, or both.

This is operationally important because traffic intent differs across placements.

Search often reflects stronger purchase intent.
Recommendations may support broader visibility or adjacent demand capture.

The CLI must expose this directly instead of burying it inside generic campaign update calls.

### 4.4 Item-level bid control

WB supports bid operations at the product card level.

This makes portfolio control possible inside a campaign.

A hero SKU can receive stronger support than a secondary SKU. Experimental products can be tested with lower exposure. Proven winners can be favored without rebuilding the entire campaign portfolio.

### 4.5 Search-cluster bid control

This is the closest WB primitive to keyword-level optimization.

Search clusters matter more than simplistic keyword assumptions because they reflect how WB groups or operationalizes demand internally. Real optimization must happen against cluster behavior, not fantasy spreadsheets of static keywords.

A strong CLI must therefore make search-cluster inspection, bid setting, bid deletion, and cluster statistics central features rather than optional extras.

### 4.6 Minus phrases

Minus phrases are not decorative. They are budget protection.

Without systematic exclusions, campaigns absorb irrelevant demand and pollute the performance signal. The optimizer then misreads inefficient traffic as a general campaign problem rather than a filtering problem.

Minus phrases should be easy to list, compare, replace, and version through file-based workflows.

### 4.7 Recommended and minimum bids

WB exposes recommended bids and minimum bids in relevant contexts.

These values should not be treated as automatic truth. They should be treated as platform-provided anchors.

For the CLI, that means they are useful reference inputs for planning, validation, and rule-based optimization.

### 4.8 Budget operations

Budget is part of optimization, not a separate finance concern.

A good campaign with insufficient budget becomes unstable.
A weak campaign with excessive budget becomes expensive noise.

Therefore budget retrieval and budget top-up must be part of the same operational workflow as bidding and statistics.

### 4.9 Campaign and search-cluster statistics

No optimizer is credible without measured feedback loops.

WB provides campaign statistics, search-cluster statistics, and daily search-cluster statistics. Those are the basis for all later agent reasoning.

The CLI must surface them cleanly, consistently, and in machine-readable form.

---

## 5. Why “First Page by Keywords” Is Not Enough

The intuition behind “show items on the first page based on keywords” is valid but incomplete.

It captures the visibility problem, but not the economic problem.

A campaign that wins visibility for the wrong traffic can still fail.
A campaign that reaches the first page temporarily can still become unprofitable after bid escalation.
A cluster that performed yesterday can degrade today because competitors changed strategy, inventory changed, pricing moved, reviews shifted, or WB’s own dynamics changed.

The better target is not simply:

```text
maximize first-page presence
```

The better target is:

```text
maximize profitable and sustainable search-cluster visibility
under budget and portfolio constraints
```

That requires a system with daily adaptation, not static keyword logic.

---

## 5.1 Measurement Reality — What the Current Data Can and Cannot Tell Us

One of the most important practical constraints is that the current WB data surface does not provide a perfectly clear picture of true advertising impact.

The operator may observe campaign statistics, search-cluster statistics, product-card funnel metrics, and search-query reports, but that does not automatically answer the most important business question:

```text
How many units were actually caused by advertising,
not merely observed while advertising was running?
```

That distinction matters because a product may already be selling organically. If it sells 10 units per day without advertising and 12 units per day while advertising is active, the naive interpretation is that advertising produced 12 sales. The more realistic interpretation is that the campaign may have produced only 2 incremental sales, and even that estimate is still not guaranteed unless the baseline is measured correctly.

This problem becomes even more important when ad spend is high relative to product margin. A campaign that appears “active” may still be economically negative once the estimated organic baseline is removed.

Therefore the framework must explicitly distinguish three different views of performance:

1. **Observed performance** — what the API reports while the campaign is active.
2. **Attributed performance** — performance that can reasonably be tied to the active campaign or active search clusters using campaign and analytics data.
3. **Incremental performance** — estimated lift above expected organic baseline.

WB gives enough data for the first view, partial support for the second view, and no direct causal answer for the third. That means incremental performance must be estimated empirically by our own monitoring layer.

## 5.2 Product Prioritization — Why We Cannot Work on All Products at Once

In a realistic catalog, not all products deserve equal operational attention.

If the seller has 100 products, the system should not attempt to optimize all 100 simultaneously from day one. That would dilute time, budget, and decision quality.

Instead, the framework should explicitly support a **daily working set**. For example, the operator may decide to focus on 5 products for the day. Those 5 products should be chosen systematically, not arbitrarily.

A useful selection model is to classify products into four broad states:

**State A — proven winners**

Older products with stable sales, acceptable reviews, healthy conversion, and evidence that additional visibility may still scale.

**State B — hidden potential**

Older products that appear underperforming, but may actually suffer from insufficient visibility, poor cluster fit, weak exclusions, weak content, or historical workflow limitations rather than true lack of demand.

**State C — immature new products**

New products that require time, exploration, and controlled exposure before their realistic performance can be judged.

**State D — structurally weak products**

Products whose economics, card quality, inventory, review profile, or subject fit make them poor advertising candidates at the current time.

The purpose of the prioritization model is not just to rank products. It is to decide where limited experimentation budget should be spent.

## 5.3 Product Selection Score

The CLI itself does not need to contain a full ranking engine, but the framework should define the inputs that an external scoring layer or AI agent will use.

A practical product selection score should combine:

- recent order velocity
- recent buyout quality
- product card openness and add-to-cart signal
- review and rating stability
- stock sufficiency
- price competitiveness
- estimated unit margin
- ad readiness of the product card
- historical ad efficiency if campaigns already existed
- uncertainty level, especially for new or weakly measured products

This score should not be used as a blind automation rule. It should be used to propose the daily working set.

## 5.4 Baseline and Incrementality

The system must explicitly model baseline sales.

If a product sells without advertising, campaign evaluation must estimate whether advertising produced incremental value or merely paid for sales that would likely have happened anyway.

The WB API appears to provide campaign statistics, search-cluster statistics, sales-funnel metrics, and search-query reports, but not a direct method that returns true ad incrementality or causal lift. Therefore the framework should treat incremental impact as an estimated quantity rather than a directly observed fact.

The practical implication is that the framework needs its own baseline model.

At minimum, the monitoring layer should track:

- product daily orders before any campaign
- product daily orders while campaign is active
- campaign spend for the same period
- search-cluster level engagement and order signals
- stock, price, and review changes that could distort comparisons

A first approximation can use rolling pre-campaign averages or matched historical windows. A stronger approach can later add holdout tests, on/off windows, or partial portfolio controls.

## 5.5 Economic Evaluation

The framework should evaluate campaign economics in a stricter way than raw order counts.

Consider the simplified case:

```text
organic baseline = 10 units/day
active day sales = 12 units/day
estimated incremental units = 2
profit from estimated incremental units = 200 RUB
ad spend = 1000 RUB
```

That is not a weak campaign. That is a negative campaign.

Therefore the framework must compute at least two economic views:

1. **Attributed economics** — based on campaign-reported or search-query-reported performance.
2. **Estimated incremental economics** — based on observed performance minus baseline estimate.

The second view is the one that should govern strategic decisions.

## 5.6 Why Empirical Testing Is Mandatory

At the beginning of the system, knowledge is incomplete.

We do not know with confidence which clusters WB will attach to a product campaign. We do not know how aggressively a product can absorb search traffic before efficiency collapses. We do not know whether a weak product is weak because of demand, card quality, cluster mismatch, price, or simple lack of exposure.

That means the initial system must be empirical.

The framework should explicitly adopt an exploration model:

- launch controlled tests
- observe actual cluster emergence
- prune waste quickly
- keep history
- repeat until enough evidence accumulates

This is not a side note. It is a core operating assumption.

## 6. The Optimal Workflow

The workflow should be expressed as an operational cycle rather than a collection of isolated commands.

### 6.1 Phase A — Portfolio selection

Before campaign launch, the operator or agent selects candidate SKUs using business-aware constraints:

- product is in stock
- product card quality is acceptable
- reviews and rating are not catastrophically weak
- price positioning is not obviously uncompetitive
- margin can support advertising
- product belongs to a valid subject for campaign creation

At this phase the system should also classify SKUs into roles.

A useful initial role model is:

- **Hero** — highest confidence product, primary spend target
- **Support** — proven but secondary product
- **Experimental** — new or uncertain product under observation

This role assignment becomes useful later for bid defaults and portfolio pruning.

### 6.2 Phase B — Controlled campaign launch

The system retrieves eligible subjects and product cards, chooses campaign type and payment model, creates the campaign, attaches a controlled product list, applies an initial placement strategy, sets baseline bids, allocates a conservative budget, and launches.

The important principle here is controlled launch.

The system should avoid fully aggressive first-day expansion because day-one data is not trustworthy enough to justify it.

### 6.3 Phase C — Search-cluster learning

After launch, the system begins reading the actual traffic map.

It retrieves active and inactive search-cluster lists, recommended bids, current cluster bids, and search-cluster statistics for a recent time window.

Then it classifies clusters into useful categories such as:

- efficient and scalable
- visible but weak
- expensive and non-converting
- inactive but potentially promising
- noisy and exclusion-worthy

This is the point at which the campaign stops being theoretical and becomes a real optimization object.

### 6.4 Phase D — Corrective adjustments

Once enough data exists, the operator or agent applies measured corrections.

Examples include:

- raise bids on efficient clusters with acceptable economics
- lower bids on expensive weak clusters
- delete bids from persistently wasteful clusters
- add minus phrases for irrelevant traffic
- rotate weak products out of the campaign
- add stronger products where intent fit is better
- change placements when traffic composition is distorted

### 6.5 Phase E — Budget pacing

Campaigns should not be topped up blindly.

The system should compare spend velocity against KPI quality. Strong campaigns should be protected from premature budget exhaustion. Weak campaigns should not be rewarded with additional budget simply because they are spending quickly.

Budget operations therefore belong inside the optimization engine rather than as separate manual finance tasks.

### 6.6 Phase F — Structural review

On a longer cadence, the system should review whether the campaign structure itself is still correct.

Examples of structural actions include:

- splitting mixed-intent campaigns into narrower ones
- cloning best-performing structures into new test variants
- separating branded and generic demand strategies
- retiring chronically weak campaign constructions

This phase is where tactical control becomes portfolio management.

---

## 7. System Scope — What the CLI Must Be

The CLI must operate at three levels simultaneously.

### 7.1 Human operator mode

The tool must be readable and ergonomic enough for direct use by an operator who works in the terminal daily.

That means short command groups, coherent naming, informative defaults, and tabular summaries where appropriate.

### 7.2 Script mode

The tool must be automation-friendly for shell scripts, CI jobs, and scheduled tasks.

That means reliable exit codes, quiet mode, `--json`, file-based bulk input, and predictable errors.

### 7.3 Agent mode

The tool must behave as a stable contract for AI agents.

That means deterministic JSON schemas, dry-run planning outputs, explicit mutation boundaries, machine-readable validation errors, and a design that discourages hidden state.

The third mode is the differentiator.

Many CLIs can satisfy the first two. This project must satisfy all three.

---

## 8. Command Taxonomy

The command model should be explicit and grouped by operational domain.

### 8.1 Authentication and profiles

```bash
wb auth login
wb auth logout
wb auth list
wb auth use <profile>
wb auth status
wb auth ping
```

Multiple profiles are not optional. A single operator may need separate production, test, or brand-specific accounts.

### 8.2 Campaign lifecycle

```bash
wb campaign list
wb campaign get <id>
wb campaign create
wb campaign rename <id>
wb campaign delete <id>
wb campaign start <id>
wb campaign pause <id>
wb campaign stop <id>
wb campaign clone <id>
wb campaign eligible-subjects
wb campaign eligible-items
wb campaign add-items <id>
wb campaign remove-items <id>
wb campaign set-placements <id>
```

### 8.3 Item bids

```bash
wb bid recommend --campaign <id>
wb bid minimum --campaign <id>
wb bid get-items --campaign <id>
wb bid set-item --campaign <id>
wb bid set-items --campaign <id> --file bids.json
```

### 8.4 Search clusters

```bash
wb cluster list --campaign <id> --nm <nm_id>
wb cluster active --campaign <id> --nm <nm_id>
wb cluster inactive --campaign <id> --nm <nm_id>
wb cluster bids --campaign <id> --nm <nm_id>
wb cluster set-bids --campaign <id> --nm <nm_id> --file cluster-bids.json
wb cluster delete-bids --campaign <id> --nm <nm_id>
wb cluster stats --campaign <id> --nm <nm_id> --from YYYY-MM-DD --to YYYY-MM-DD
wb cluster stats-daily --campaign <id> --nm <nm_id> --from YYYY-MM-DD --to YYYY-MM-DD
wb cluster minus list --campaign <id> --nm <nm_id>
wb cluster minus set --campaign <id> --nm <nm_id> --file minus.json
wb cluster minus clear --campaign <id> --nm <nm_id>
```

### 8.5 Budget and finance

```bash
wb budget balance
wb budget get --campaign <id>
wb budget topup --campaign <id> --sum 5000
wb budget history --campaign <id>
```

### 8.6 Statistics

```bash
wb stats campaign --id <id> --from YYYY-MM-DD --to YYYY-MM-DD
wb stats campaigns --ids ... --from YYYY-MM-DD --to YYYY-MM-DD
wb stats cluster --campaign <id> --nm <nm_id> --from YYYY-MM-DD --to YYYY-MM-DD
wb stats cluster-daily --campaign <id> --nm <nm_id> --from YYYY-MM-DD --to YYYY-MM-DD
```

### 8.7 Analytics bridge

```bash
wb analytics search-report main
wb analytics search-report groups
wb analytics sales-funnel products
wb analytics csv create
wb analytics csv list
wb analytics csv download
```

These commands should be optional because some analytics functionality depends on separate token availability and, in some cases, Jam subscription requirements.

### 8.8 Optimization workflows

```bash
wb optimize plan --campaign <id>
wb optimize run --campaign <id>
wb optimize clusters --campaign <id>
wb optimize budget --campaign <id>
wb optimize negatives --campaign <id>
wb optimize portfolio --campaign <id>
```

The optimization group should not bypass lower-level primitives. It should orchestrate them.

---

## 9. UX Rules for the CLI

A command-line tool intended for both humans and agents must be disciplined about output and safety.

### 9.1 Output modes

Every meaningful command should support:

- human-readable default rendering
- `--json`
- `--quiet`
- `--verbose`

### 9.2 Safety switches

Every mutating workflow should support:

- `--dry-run`
- `--yes`
- `--non-interactive`

The absence of dry-run support on write operations would make the tool unsafe for agent use.

### 9.3 File-based batch inputs

Bulk operations should use files rather than long flag chains.

Examples include:

- item bid sets
- cluster bid sets
- minus phrase sets
- campaign SKU lists

JSON should be the primary structured input format because it is easy for agents and scripts to generate predictably.

### 9.4 Error model

The CLI should define stable exit classes such as:

| Code | Meaning |
|---|---|
| 0 | success |
| 2 | validation error |
| 3 | authentication failure |
| 4 | authorization or missing scope |
| 5 | rate-limited or retryable API error |
| 6 | non-retryable WB API error |
| 7 | local configuration or profile error |

---

## 10. Architecture

```text
┌──────────────────────────────────────────────────────────────────┐
│                         WB CLI FRAMEWORK                         │
│                                                                  │
│  ┌────────────┐   ┌──────────────┐   ┌────────────────────────┐  │
│  │ CLI Layer  │──▶│ Service Layer │──▶│ WB Client Layer        │  │
│  │ (Typer)    │   │ use-cases     │   │ HTTP + auth + retries  │  │
│  └────────────┘   └──────────────┘   └────────────────────────┘  │
│         │                  │                      │               │
│         │                  │                      ▼               │
│         │                  │            ┌──────────────────────┐  │
│         │                  └───────────▶│ Domain Model         │  │
│         │                               │ campaigns, bids,     │  │
│         │                               │ clusters, budgets,   │  │
│         │                               │ stats, decisions     │  │
│         │                               └──────────────────────┘  │
│         │                                         │               │
│         ▼                                         ▼               │
│  ┌──────────────┐                        ┌──────────────────────┐ │
│  │ Output Layer │                        │ Local Storage        │ │
│  │ tables/json  │                        │ profiles, cache,     │ │
│  │ errors       │                        │ audit log            │ │
│  └──────────────┘                        └──────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

The architecture should be layered deliberately.

The CLI layer should handle parsing, flags, command registration, and presentation.
The service layer should implement use-cases and mutation planning.
The client layer should encapsulate HTTP behavior, retries, rate limits, and token application.
The domain layer should normalize WB concepts into coherent internal models.
The storage layer should persist local operator state such as profiles, audit logs, and optional cache snapshots.

---

## 11. Profile and Authentication Model

### 11.1 Multi-profile support

A single operator may manage multiple brands, test accounts, or seller entities. Therefore the CLI must support named profiles from the beginning.

Expected usage:

```bash
wb auth login --profile perfume-main
wb auth login --profile perfume-test
wb auth use perfume-main
```

### 11.2 Token categories

WB token categories matter. Promotion and Analytics should not be assumed to be interchangeable.

The CLI should therefore store per-profile token capabilities explicitly rather than pretending every token can access every endpoint group.

### 11.3 Secure storage

Preferred storage strategy:

1. system keychain or credential store
2. encrypted local fallback
3. plaintext only as explicit last resort

### 11.4 Login validation workflow

`wb auth login` should not merely store a token.

It should:

1. capture and store token material securely
2. associate it with a named profile
3. validate connectivity against the appropriate API surface
4. detect missing categories when possible
5. persist profile metadata for later command routing

---

## 12. Endpoint Mapping Strategy

The implementation should be phased, but the mapping should be explicit from day one.

### 12.1 Promotion endpoints — first-class scope

The first implementation wave should wrap the Promotion surface required for operational control:

- campaign listing and retrieval
- campaign creation and lifecycle control
- eligible subjects and eligible product cards
- placement changes
- item bid retrieval and mutation
- search-cluster list, bids, statistics, active/inactive views
- minus phrases
- balances and campaign budgets
- campaign statistics

### 12.2 Analytics endpoints — second-wave integration

The Analytics surface is needed for broader query discovery and product quality validation.

This should include search queries for items, sales-funnel information, and CSV report workflows where available.

The key design principle is that Promotion is the execution core and Analytics is the discovery and validation extension.

---

## 13. Rate Limits, Retries, and Reliability

A WB CLI without disciplined rate-limit handling will become unreliable under real usage.

The client layer must therefore:

- read rate-limit headers when available
- classify retryable vs non-retryable failures
- use bounded exponential backoff with jitter
- expose retry context in verbose and JSON output
- avoid aggressive parallelism by default

Parallelism should be bounded because the operational goal is reliability, not brute-force concurrency.

For mutating operations, the client should prefer read-before-write where practical so that changes can be planned and rendered as diffs under `--dry-run`.

---

## 14. Domain Model

The CLI should not pass raw WB payloads through the system without normalization.

The domain layer should define internal models such as:

- `Profile`
- `Campaign`
- `CampaignStatus`
- `CampaignMode`
- `PaymentType`
- `Placement`
- `ProductCard`
- `ItemBid`
- `SearchCluster`
- `ClusterBid`
- `MinusPhraseSet`
- `BudgetSnapshot`
- `CampaignStats`
- `ClusterStats`
- `OptimizationDecision`

Normalized models make application logic easier to test and reason about.

At the same time, raw WB payloads should still be preserved in debugging or verbose contexts for forward compatibility and troubleshooting.

---

## 14.1 Measurement and Historical Storage Layer

Although this is technically outside the narrow CLI core, the framework must define it because the CLI will be the acquisition layer for all required data.

A serious optimization system needs durable history across three levels:

### Product history

For each product, the system should retain time-series data such as:

- product-card funnel metrics
- search-query visibility and position signals where available
- ad campaign participation windows
- estimated baseline sales windows
- observed orders, buyouts, cancellations, and returns
- stock context and key price events where available

### Campaign history

For each campaign, the system should retain:

- campaign configuration snapshots
- product membership over time
- budget events and top-ups
- campaign daily statistics
- placement configuration changes
- bid changes
- lifecycle state changes

### Search-cluster history

For each `(campaign, product, cluster)` tuple, the system should retain:

- cluster bid history
- cluster daily statistics
- active/inactive transitions
- minus phrase events
- first-seen and last-seen timestamps

This history is required for three reasons.

First, it lets the system answer questions like:

```text
when did this cluster first appear for this product?
when did we increase its bid?
what happened afterward?
```

Second, it lets the system compare campaign structure over time rather than looking at one isolated API response.

Third, it creates the evidence base needed for future agents and the knowledge base you mentioned.

## 14.2 Query Model for Historical Analysis

The later monitoring and optimizer layers will need to ask questions in at least four ways.

### By product

```text
show the last 30 days of organic baseline estimate,
campaign participation, ad spend, and total orders for product X
```

This is the right view when deciding whether a product deserves more attention.

### By campaign

```text
show campaign history, product membership changes,
budget events, and daily efficiency for campaign Y
```

This is the right view when deciding whether campaign structure is correct.

### By search cluster

```text
show all appearances of cluster Z across products and campaigns,
its cost pattern, order pattern, and survivability after pruning
```

This is the right view when identifying expensive but weak demand versus expensive but scalable demand.

### By product-cluster pair

```text
show how cluster Z performed specifically for product X
across all tests and campaigns
```

This is the most useful operational view for search optimization.

## 14.3 Single-Product vs Multi-Product Campaigns

The framework should not assume a single universal answer.

A campaign may contain one product or multiple products, but the measurement implications differ.

### Single-product campaigns

These are easier to reason about.

They improve causal clarity because campaign spend and performance are associated with one product only. They are the best structure for exploration, measurement, and cluster-level learning when precision matters.

### Multi-product campaigns

These are useful when products are genuinely similar in subject, intent, pricing logic, and search behavior. They may reduce operational fragmentation, but they make analysis harder because spend and performance are pooled.

Therefore the framework should treat single-product campaigns as the default for discovery and learning, and multi-product campaigns as a scaling structure only when similarity is already validated.

This principle is especially important during the empirical phase.

## 14.4 The Two-Hour Exploration Window

Your idea of running a campaign for a short learning window and then pruning search clusters is correct and should be formalized.

The system should support a short exploration cycle for selected products:

1. create or activate a tightly controlled campaign
2. allow a short observation window, for example two hours
3. retrieve active and inactive search clusters
4. retrieve cluster statistics and recommended bids
5. mark clusters as keep, watch, suppress, or remove
6. apply pruning and bid corrections
7. continue into a second observation window

This works because WB search clusters are not fully knowable in advance. They must be discovered empirically through live campaign behavior.

The framework should therefore model search-cluster emergence as an experimental process rather than a static planning step.

## 14.5 Expensive Clusters vs Efficient Clusters

Not every expensive cluster is bad, and not every cheap cluster is good.

A strong framework must evaluate cluster quality using at least four dimensions simultaneously:

- cost
- position or visibility
- downstream order behavior
- incremental economic quality

The goal is not merely to find cheap clusters. It is to find clusters with acceptable economics relative to their role.

Some clusters may be expensive but strategically valuable because they scale profitably.
Others may be cheap but worthless because they generate low-intent traffic.

This is another reason why history matters. A single observation window can be misleading.

## 15. Optimization Engine Requirements

The optimizer should not begin as a fully autonomous mutation engine.

The first credible version should be recommendation-first.

That means the flow should be:

1. read current state
2. read relevant statistics
3. produce proposed changes
4. render a plan
5. apply only when the caller explicitly requests mutation

This is especially important for agent use, because unsafe autonomous writes destroy trust quickly.

### 15.1 Decision primitives

The optimizer should be able to recommend actions such as:

- raise item bid
- lower item bid
- raise cluster bid
- lower cluster bid
- delete cluster bid
- add minus phrase
- remove product from campaign
- add product to campaign
- top up budget
- pause campaign
- split campaign by intent class

### 15.2 Minimal KPI model

The system should reason over a compact but useful KPI set at both campaign and cluster levels:

- impressions or views
- clicks
- CTR
- add-to-cart where available
- orders
- spend
- CPC or CPM depending on mode
- conversion rate
- spend per order

### 15.3 Initial rule set

A practical V1 rule engine can start with interpretable heuristics.

Examples:

- high impressions plus low CTR suggests visibility without relevance or creative fit
- high CTR plus low orders suggests mismatch between demand and product card economics
- repeat spend with no downstream action suggests either cluster waste or product weakness
- strong conversion with constrained visibility suggests cautious bid increases
- strong efficiency with budget starvation suggests top-up consideration

These rules are intentionally explainable. The first optimizer should optimize trust before sophistication.

---

## 16. Why Promotion Alone Is Insufficient for Full Keyword Discovery

Promotion gives operational control over running campaigns and their connected search clusters.

That is powerful, but incomplete.

A complete keyword or demand-discovery system also needs broader analytics signals such as item search queries and product-level funnel data. Some of that lives in the Analytics API rather than Promotion.

Therefore the CLI should be conceptually split into two cooperating domains:

- `promotion` for execution and direct optimization
- `analytics` for discovery, validation, and reporting

This split should be visible in the command taxonomy and in the internal code structure.

---

## 17. Package and File Layout Suggestion

```text
wb/
  __main__.py
  cli/
    app.py
    auth.py
    campaign.py
    bid.py
    cluster.py
    budget.py
    stats.py
    analytics.py
    optimize.py
  core/
    config.py
    output.py
    errors.py
    retry.py
    rate_limit.py
    logging.py
  auth/
    profiles.py
    keyring.py
    token_validation.py
  client/
    http.py
    promotion.py
    analytics.py
  domain/
    models.py
    enums.py
    kpis.py
    decisions.py
  services/
    campaigns.py
    bids.py
    clusters.py
    budgets.py
    stats.py
    analytics.py
    optimizer.py
  storage/
    audit.py
    cache.py
  tests/
    unit/
    integration/
    fixtures/
```

Python is a practical initial implementation language because it supports fast CLI development, rich JSON handling, and later agent integration without friction. The CLI can still be distributed as a polished user-facing tool.

---

## 18. Testing Strategy

### 18.1 Unit tests

Unit coverage should focus on:

- argument parsing and validation
- enum normalization
- JSON schema stability
- retry and backoff behavior
- diff planning for dry-run operations
- optimizer recommendation logic

### 18.2 Integration tests

Integration coverage should include:

- auth validation and ping
- campaign listing and retrieval
- statistics retrieval
- safe write operations in test or controlled environments

### 18.3 Contract tests

Because WB evolves its API, contract tests are critical.

The system should maintain real or sanitized response fixtures to detect breaking changes in response shape or enum semantics.

### 18.4 Regression suite

Regression coverage should watch specifically for:

- campaign model changes
- field additions or removals
- statistics payload changes
- search-cluster method behavior changes
- auth category behavior shifts

---

## 19. Auditability and Local State

Every mutating command should emit a local audit record.

That record should contain at least:

- timestamp
- profile
- command invoked
- campaign ID or affected object ID
- request payload or normalized mutation intent
- response summary
- retry count
- final result

This is useful for debugging, rollback reasoning, operator review, and agent accountability.

An optional local cache of recent campaign snapshots and statistic pulls can also improve operator workflow, but the cache must never become a silent source of truth that hides stale data.

---

## 20. Development Phases

### Phase 0 — Foundation

Build the CLI scaffold, config handling, profile storage, secure token management, HTTP client, output rendering, and the common error system.

### Phase 1 — Read-only operational visibility

Implement campaign list/get, eligible subjects/items, balances, budgets, campaign stats, cluster stats, active/inactive cluster retrieval, and recommended bids.

The purpose of this phase is visibility without operational risk.

### Phase 2 — Core write controls

Implement campaign create/start/pause/stop/rename/delete, item bid changes, placement changes, add/remove items, and budget top-up.

At the end of this phase, the tool becomes genuinely operational.

### Phase 3 — Search-cluster control

Implement cluster bid listing, cluster bid mutations, minus phrase workflows, and planning diffs for cluster changes.

At the end of this phase, the tool becomes strategically useful for search optimization.

### Phase 4 — Analytics bridge

Add search-query reporting, sales-funnel access, and CSV workflows where available.

This phase deepens discovery and improves optimizer signal quality.

### Phase 5 — Optimization workflows

Implement recommendation-first optimize commands, explainable rule outputs, and guarded `--apply` execution.

### Phase 6 — Agent platform support

Stabilize JSON schemas, add SDK-level wrappers if useful, and expose deterministic machine contracts for external agents.

---

## 21. What Must Not Be Deferred

Several features are foundational and should not be postponed until “later.”

These include:

- multi-profile support
- secure token handling
- rate-limit awareness
- dry-run mode for writes
- stable JSON output
- explicit error contracts
- audit logging

Without these, the CLI may still function superficially, but it will not be safe or mature enough for agent-driven operations.

---

## 22. Recommended MVP

The best MVP is not “AI optimizer first.”

The best MVP is a reliable operational core.

That MVP should include:

- auth and profiles
- campaign list/get/create/start/pause/stop
- eligible subjects and product cards
- item bid retrieval and mutation
- budget retrieval and top-up
- campaign stats and cluster stats
- JSON output and dry-run support
- audit logging

This produces immediate value while creating the substrate for higher-level automation.

---

## 23. Decision Log — Closed Issues

| # | Issue | Decision |
|---|---|---|
| 1 | Is the CLI only a campaign wrapper? | No. It is an ads operations control plane. |
| 2 | Is first-page visibility the main KPI? | No. The main target is profitable visibility under constraints. |
| 3 | Are search clusters secondary? | No. They are central to search optimization. |
| 4 | Should analytics be separate from promotion? | Yes. Promotion is execution core; Analytics is discovery extension. |
| 5 | Should the optimizer mutate automatically in V1? | No. Recommendation-first with explicit apply. |
| 6 | Is multi-profile support optional? | No. It is foundational. |
| 7 | Should budget handling be separate from optimization? | No. Budget is part of optimization logic. |
| 8 | Is dry-run a nice-to-have? | No. It is mandatory for safe writes. |

---

## 24. Decision Log — Open Questions

| # | Question | Current Direction |
|---|---|---|
| Q1 | Should the CLI expose a local SQLite cache of snapshots? | Likely yes, but only as an explicit cache, not hidden state. |
| Q2 | Should agent adapters be subprocess-only or include a Python SDK? | Start with subprocess-safe CLI; evaluate SDK next. |
| Q3 | How should optimizer thresholds be configured? | Per-profile config with campaign-level overrides. |
| Q4 | Should campaign cloning support template files? | Likely yes in V1.5 or V2. |
| Q5 | How should scheduling and recurring optimization runs be handled? | Outside the first CLI core; integrate later via cron or task runners. |

---

## 25. Final Position

The correct way to think about this project is not:

```text
build a small Wildberries campaign CLI
```

The correct way to think about it is:

```text
build a disciplined operating layer for WB advertising,
then use that layer for humans, scripts, and AI agents.
```

That operating layer must let us:

- discover eligible products
- launch and manage campaigns
- inspect and control search clusters
- tune bids and minus phrases
- pace budget intelligently
- read campaign and cluster statistics
- expand into analytics-backed demand discovery
- generate explainable optimization plans
- apply changes safely and auditably

That is the architecture aligned with both the WB API and the business reality of dynamic, competitor-driven marketplace advertising.

---

*Draft v0.1 — rewritten as a full technical design document and intended as the base specification for implementation.*

