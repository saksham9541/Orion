# RailOpt

**One railway. Many maintenance requests. One optimised plan.**

AI-assisted railway maintenance block optimisation that coordinates engineering, signalling
and traction work while minimising operational disruption.

RailOpt recommends. A railway official reviews and approves. Nothing in this product grants a
block, holds a train, or writes back to a maintenance system.

---

## Running it

```bash
npm install
npm run dev
```

Vite dev server on port 5173. No backend, no API keys, no network calls.

## The rule that matters

**Every number on screen is derived. Nothing is typed in.**

Three files are the only inputs:

| File | What it holds |
| --- | --- |
| `src/data/tasks.js` | 22 pending jobs, and the window each department asked for in its own system |
| `src/data/plan.js` | which jobs RailOpt put in which block, and when — decisions only |
| `src/data/corridors.js` | section traffic, used to price a closure in train movements |

Everything else — block durations, the uncoordinated baseline, conflicts, deferral breaches,
efficiency scores, the risk grid, every scenario and the emergency re-plan — is computed in
`src/lib/optimizer.js` from those three.

Block duration is defined once, in `src/lib/possession.js`:

```
possession = longest job in the block + 45 min protection and handback
```

Jobs sharing a block work in parallel, so a merge saves the second job's overhead *and* the
shorter job's duration. That single rule generates every downtime figure in the product.

### How the headline numbers reconcile

| | Baseline | Optimised |
| --- | --- | --- |
| Possessions | 19 | 16 |
| Closure | 3420 min | 2735 min |
| Train movements held | 234 | 164 |
| Past deferral limit | 4 | 0 |

- 19 − 16 = **3 closures avoided**, which is also the 3 merged blocks
- 3420 − 2735 = **685 min = 11h 25m of track time returned**
- 234 − 164 = **70 movements protected**

Note that **B-108 fails one of its six constraint checks** — the Sunday ballast block overruns
the night window. It is left visible rather than smoothed over, because a constraint panel
where everything always passes is not a constraint panel.

The strongest check is in the Scenario Lab: switch *merge work across departments* **off** and
the simulator independently returns 19 blocks and 3420 minutes. It rediscovers the baseline
without being told it.

The baseline is not a stored table. It is reconstructed from the as-raised request windows, so
"what RailOpt changed" is always the same work planned two ways.

## What is demonstration data

All of it. Station codes and corridor shapes follow real trunk routes so the demo reads as a
real division, but:

- the maintenance tasks are synthetic
- the traffic profiles are synthetic
- the digital twin is a **replay of the plan**, not telemetry
- the copilot has **no language model and no database** behind it — its answers are prepared
  text, matched by keyword, and labelled as such on screen

The Data Sources page separates this explicitly: what the prototype generates versus what
would come from live systems. Nothing claims access to Indian Railways infrastructure.

## Structure

```
src/
  data/         tasks, plan decisions, corridors, network geometry, copilot script
  lib/
    possession.js   block duration arithmetic — the one definition
    optimizer.js    every derived figure in the product
    constants.js    departments, urgency bands, reason codes
  state/
    AppState.jsx    role, demo mode, optimisation reveal, approvals
  components/
    common/     Button, KPI, StatusChip + DataTag, ScoreMeter, Drawer, Toast
    app/        StageNav, RoleSelector, PageHeader, StageFooter, AppShell
    network/    RailwayNetwork, TimeSlider, SectionPanel, RiskHeatmap
    optimize/   OptimizationRun, ConflictRadar, PreventedPanel, PipelineFlow,
                ApprovalPanel, ObjectivePanel, ExplainDrawer
    scenario/   ScenarioComparison, EmergencyPanel
    plan/       Timeline, BlockDetail
    demo/       DemoMode
  pages/        Landing, Dashboard, Network, Tasks, BlockPlan, Simulator,
                Assistant, Sources
```

## Presenting it

Press **Demo mode** in the header. Nine stops, roughly four minutes, navigating the real
product rather than a recording — so any question from the floor can be answered by stopping
and using it. Arrow keys move between steps, Escape exits.

| Step | Screen | What it shows |
| --- | --- | --- |
| 1 Problem | Tasks | 22 jobs, three departments, one urgency scale |
| 2 Conflict | Overview | four contested sections; DER–KRJ overlaps by 135 min |
| 3 Optimisation | Overview | the seven-stage pipeline running, reporting real counts |
| 4 Coordination | Block plan | three shared possessions; open B-101 for *why this block* |
| 5 Impact | Network | play the week through on the twin |
| 6 Explainability | Tasks | decision trace: request → conflict → constraint → decision → impact |
| 7 Scenario | Scenario Lab | festival, restricted window, merging off |
| 8 Emergency | Scenario Lab | critical defect inserted; 16 blocks becomes 17 |
| 9 Approval | Block plan | controller approves or sends it back |

### Explainability surfaces

- **Decision trace** (overview) — one job's five beats, every beat read from the data
- **Why this block?** (block drawer) — the case for a possession plus the six constraints
  checked, each with the value it was checked against
- **Why *n*?** (block drawer) — the four components behind the efficiency score
- **Why this decision?** (task drawer, twin panel) — urgency, deferral limit, traffic,
  window fit, and the coordination opportunities that were and were not taken

## Accessibility

Section status is never carried by colour alone — every state has a shape, an icon and a word.
The five states are Available, Planned maintenance, Active block, Critical safety task and
Scheduling conflict. Timeline, heatmap and network diagram are keyboard reachable, and
`prefers-reduced-motion` is respected throughout.

## Known limits

- Only week 38 is solved. The monthly view's later weeks are illustrative demand, and say so.
- The eight-week availability trend is illustrative history, not optimiser output.
- Approval is recorded in session state only; there is no persistence and no write-back.


## Theming (light and dark)

Every colour resolves through the CSS variables in `src/index.css` (`:root`/`.dark` and
`.light`). Write components with `bg-surface`, `bg-raised`, `text-ink`, `text-muted`,
`text-faint`, `border-line` and the status tokens (`danger`, `high`, `warn`, `ok`, `info`,
`eng`, `snt`, `trd`) and they are correct in both themes. Avoid hard-coded `slate-*`, `white`
or `#hex` colours in UI components: they cannot follow the theme.

- Shared classes: `.field` (inputs), `.sev-critical|high|medium|low` (solid severity pills),
  `.tag-*` (tinted status tags), `.btn-primary`, `.btn-quiet`.
- Panel title bars use `bg-bar` / `text-onbar` / `text-barmuted`, which stay dark in both themes.
- `text-base` is font size only. The `base` colour token is excluded from text colours in
  `tailwind.config.js`; use `bg-base` for the page colour.
- `node tools/contrast.mjs` checks the palette against WCAG AA (4.5:1) in both themes.
- The portal opens in light theme; the choice is stored in `localStorage` (`railopt-theme`).
