# Investment_demo.veragrid — client discovery demo

A self-contained IEEE39 (New England) snapshot carrying 25 preloaded candidate investments with costs so that **Investments Evaluation** produces a well-populated Pareto curve in
about 15 seconds.

---

## Run it

1. **Open** `Investment_demo.veragrid`.
2. Optional 20-second warm-up: run a plain **Power Flow** first. It shows 5 overloaded circuits
   and 3 buses below the 0.95 pu planning limit. This is the problem the client is being asked
   to solve, and it makes the Pareto curve mean something.
3. Go to the **Investments Evaluation** panel and set:

   | Setting | Value |
   |---|---|
   | Objective function | `PowerFlow` |
   | Method | `NSGA3` |
   | Max. evaluations | `1250` |

4. **Run.** It takes ~15 s.
5. Open the **Pareto plot** result. Click points on the curve — each click applies that portfolio
   to the grid, so the one-line diagram updates live.

---

## What to expect

| | |
|---|---|
| Investment groups | 25 (31 underlying investments) |
| Evaluations | 1251 |
| Runtime | ~15 s |
| Pareto points | ~210 |
| Technical score | 1272 with nothing built → ~57 at the best point |
| CAPEX span | 0 → ~760 |

The knee sits at roughly **CAPEX 110**, where the technical score falls from 1272 to about 104 —
around 9% of the maximum spend removes about 92% of the problem. That single fact is the demo.

Two portfolios worth naming out loud:

- **Cheapest portfolio that clears every thermal overload**: ~CAPEX 423, 8 groups.
- **Cheapest portfolio that clears everything, thermal and voltage**: ~CAPEX 608, 10 groups —
  a genuine mix of two new circuits, reconductoring, two capacitor banks and a reactor.

Exact numbers move slightly between runs because NSGA3 is stochastic. The shape does not.

---

## The base case

The historical peak hour of the IEEE39 one-week case, scaled into a forward-looking planning
scenario:

- Demand **and** dispatch scaled by 1.45 (scaling demand alone would just be absorbed by the
  slack machine and would barely move the corridor flows).
- Seasonal thermal ratings applied to four older circuits.
- Planning voltage band narrowed to 0.95–1.05 pu.

Resulting violations, all of them fixable by the candidates on offer:

| Overloaded | Loading |
|---|---|
| branch 26 (bus 15 → bus 18) | 158% |
| branch 2 (bus 1 → bus 2) | 137% |
| branch 36 (bus 21 → bus 34) | 103% |
| branch 17 (bus 9 → bus 10) | 101% |
| branch 4 (bus 1 → bus 29) | 101% |

Buses below 0.95 pu: **bus 11** (0.941), **bus 6** (0.944), **bus 7** (0.945).

---

## The candidate portfolio

| Family | Groups | What it is |
|---|---|---|
| New circuit | 7 | A second circuit on a congested corridor. The expensive answer. |
| Reconductoring | 6 | HTLS conductor on the existing towers: +60% rating, −15% resistance. Cheaper, and competes head-to-head with a new circuit on four of the same corridors. |
| Capacitor bank | 6 | 50–120 MVAr across the depressed-voltage load pocket. |
| Shunt reactor | 2 | 50–60 MVAr at the highest-voltage non-generator buses. |
| Battery (BESS) | 4 | 50–150 MW / 4 h at the largest load pockets, discharging at the peak. |

Four corridors carry **both** a new-circuit and a reconductoring option, so the optimizer has to
choose between building and uprating. That trade-off is what gives the middle of the curve its
texture, and it is the most useful thing to point at when a client asks "so what does it actually
decide?"

Storage sits in the same optimisation as the wires and competes directly against them — worth
saying explicitly, because most planning tools cannot do it.

---

## Talking points

- **The output is a curve, not a number.** Classical MIP planning returns one "optimal" portfolio
  and no way to interrogate it. Here the client sees the whole efficient frontier and picks their
  own risk appetite.
- **Low-regret vs high-regret.** Use the frequency report: candidates appearing in many
  Pareto-optimal portfolios are low-regret.
- **Every point is a real AC power flow**, not a linear surrogate. 1251 of them in 15 seconds.
- **Storage competes with wires** on equal footing in the same run.

---

## Caveats to take into account in the demo

- CAPEX values are calibrated, dimensionless planning units, not euros. They are scaled so total
  spend is commensurate with total technical benefit — without that the front collapses into a
  single cluster, which is the normalisation problem documented in
  `doc/md_source/investment_optimization.md`.
- Generator voltage setpoints were clamped into the planning band during the build. The source
  case schedules one machine at 1.0636 pu, and since a generator holds its own terminal voltage,
  no investment could ever clear that excursion.

---

## Rebuilding

```bash
PYTHONPATH=src python trunk/demos/build_investment_demo.py
```

Regenerates `Investment_demo.veragrid` from
`Grids_and_profiles/grids/IEEE39_1W.gridcal`, re-running the CAPEX calibration and printing the
base-case violation report.
