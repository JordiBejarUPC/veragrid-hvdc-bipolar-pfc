# Contingency analysis demo

Two ready-to-run files for a client discovery meeting. Open, run, read the report. No setup.

| File | What it holds |
|---|---|
| `Contingency_demo.veragrid` | 46 circuit outages + 9 unit trips, one at a time (**N-1**) |
| `Contingency_demo_N2.veragrid` | 6 hand-picked common-mode events (**N-2**) |

Both use the IEEE39 New England system, the same grid as `trunk/Demos/Investments`, so the two
demos can be presented back to back: *here is the N-1 risk* then *here is the plan that removes it*.

## How to run it

1. Open the file.
2. **Contingency analysis**, set **Method** to `Power flow`, leave **Use SRAP** unchecked.
3. Run. It takes about a second.
4. Go to **Results**, then **Contingencies report**.

> The method and SRAP settings live in VeraGrid's user configuration, not in the `.veragrid`
> file, so set them once before the meeting and they will persist.

## The base case

The standard IEEE39 dispatch: 6254 MW of demand, 10 units, 46 circuits, 39 buses in three areas.

**The intact network is secure.** Highest circuit loading 85.4%, voltages between 0.963 and
1.040 pu, nothing violated. That matters for the demo: the story is *the system looks fine until
something trips*, and it does not land if the grid is already broken when you open it.

Circuit ratings were chosen so the system is N-1 secure **except** on ten corridors. That is
deliberate, and it is what a planner's case actually looks like when they bring a problem to a
meeting: secure everywhere except the handful of corridors under discussion.

## Part 1, N-1: every circuit, every unit

**55 contingencies produce 17 violations.** The five worst:

| Monitored | Contingency | Base | Post-contingency | Verdict |
|---|---|---|---|---|
| L29-38 | L06-31 | 82.7% | **157.6%** | Not acceptable |
| L19-20 | L20-34 | 38.3% | **153.4%** | Not acceptable |
| L23-24 | L21-22 | 54.5% | **149.7%** | Not acceptable |
| L19-20 | Unit trip G34 | 38.3% | **148.7%** | Not acceptable |
| L28-29 | L06-31 | 69.7% | **143.2%** | Not acceptable |

Three things worth pointing at:

- **The victim is not the culprit.** Losing L06-31, on the far side of the system in Area 1, is
  what overloads L29-38 in Area 3. This is the whole reason contingency analysis exists and
  cannot be replaced by looking at a loading map.
- **Generator trips matter as much as circuit trips.** `Unit trip G34` is the fourth worst event
  in the system. A screening study that only opens lines would miss it.
- **Reciprocal pairs.** L19-20 and L20-34 are each other's worst outage, and so are L21-22 and
  L23-24. Lose one and the other takes the load. That sets up Part 2.

## Part 2, N-2: what single-outage screening misses

Six events, each a *single physical failure* that takes out more than one device, which is why
each is one contingency group holding several devices rather than several separate contingencies.

| Event | Devices | Result |
|---|---|---|
| Common tower, Bus 06 western exits | L05-06 + L06-07 | **L13-14 at 202%** |
| Unit and circuit, G39 with L09-39 | G39 + L09-39 | **L01-02 at 209%** |
| Common tower, L21-22 with L23-24 | L21-22 + L23-24 | L06-31 at 119%, 4 violations |
| Common tower, Bus 04 exits | L04-05 + L04-14 | L03-04 at 111% |
| Busbar fault, Bus 22 | L21-22 + L22-23 + L22-35 | *no overload, the system separates* |
| Independent pair, L03-18 with L25-26 | L03-18 + L25-26 | *nothing, the control case* |

**19 violations, every one worse than anything N-1 found.** The headline: individually, L21-22
and L23-24 each look merely uncomfortable. On the same tower, they are a different problem
entirely.

Two of the six deliberately return nothing, and both are worth explaining:

- **Busbar fault at Bus 22** produces no overload because the problem is not thermal. Losing all
  three circuits separates Bus 22 and the unit at Bus 35 from the system. Show this in
  **Pf: Active power "from"**: the flows on the islanded circuits read zero. A different failure
  mode, and the report is right to stay silent about overloads.
- **Independent pair** is the control case. Two circuits far enough apart that no single failure
  could take both. An empty result is the correct answer, not a failed run.

---

# Reading the contingencies report

> **SRAP** (*Sistema de Reduccion Automatica de Potencia*), an automatic generation-runback
> scheme that curtails nearby generation within seconds to relieve a post-contingency overload
> before the circuit's protections trip it.

## When a row appears at all

A circuit is reported only if the contingency **changed its flow**, made it **worse**, and pushed
it **above 100%** of its normal rating. Two consequences:

- A circuit sitting at 95% that the outage *relieves* never appears. **The report is a list of
  new problems, not a census of loading.**
- An **empty report means the system is secure**, not that the run failed.

Base-case violations, meaning circuits already overloaded before any outage, appear once with the
literal word `Base` in the `Contingency` column. There are none in these files, by design.

## The four verdicts

Every circuit carries three ratings: its normal rating, a short-term **contingency rating**
(here 1.20 times normal, what a control room tolerates for the minutes it takes to redispatch),
and a **SRAP rating** (1.40 times normal, where the protections trip). Post-contingency loading
against the normal rating decides the verdict:

| Post-contingency loading | `Overload` | `SRAP availability` | Meaning |
|---|---|---|---|
| 100 to 120% | Overload acceptable | SRAP not needed | Within the short-term rating. Ride it out. |
| 120 to 140% | Overload not acceptable | SRAP applicable | Too high to sit on, low enough for runback to fix. |
| 140 to 150% | Overload not acceptable | SRAP not applicable | Past the protection rating. |
| above 150% | Overload not acceptable | SRAP not applicable | Well past it. Needs reinforcement, not operations. |

This is why the contingency rating is set to 1.20 and not left at its default of 1.00: at 1.00
the first band is empty and *every* overload reports as unacceptable, which throws away the
distinction the client most wants to see.

## All 20 columns

| Column | What it means |
|---|---|
| `Time idx` | Time-step index. Always `0` here, these are snapshots. |
| `Time` | Timestamp. Blank in a snapshot, filled in a time-series study. |
| `Probability cluster` | Weight of this time step, `1.0` here. Weights statistics when a year is clustered into representative hours. |
| `Area 1`, `Area 2` | Areas of the monitored circuit's two ends. Lets a planner filter down to the interface they own. |
| `Monitored` | **The circuit that overloads, the victim.** |
| `Contingency` | **The event that caused it, the culprit.** Or `Base` for a pre-existing violation. |
| `Base rating (MW)` | Normal continuous rating of the monitored circuit. |
| `Contingency rating (MW)` | Short-term rating, `rate x 1.20` here. The threshold for "acceptable". |
| `SRAP rating (MW)` | Protection rating, `rate x 1.40`. Above this nothing can save the circuit. |
| `Base flow (MW)` | Flow on the monitored circuit **before** the outage. |
| `Post-Contingency flow (MW)` | Flow **after** the outage. |
| `Post-SRAP flow (MW)` | Flow after remedial runback. **Equals the post-contingency flow here, because SRAP is off.** |
| `Base loading (pu)` | Base flow divided by base rating. |
| `Post-Contingency loading (pu)` | Post-contingency flow divided by the **base rating**. Always measured against the *normal* rating, never the contingency rating. This is the most commonly misread column: `1.58` means 158% of normal, which is 131% of the short-term rating. |
| `Post-SRAP loading (pu)` | Post-SRAP flow divided by base rating. |
| `Overload` | Verdict: `Overload acceptable` or `Overload not acceptable`. |
| `SRAP availability` | `SRAP not needed`, `SRAP applicable`, or `SRAP not applicable`. Computed from the ratings **even when SRAP is disabled**, so it answers "could runback help here", not "runback ran". |
| `SRAP Power (MW)` | MW of runback consumed. `0` here. |
| `Solved with SRAP` | Whether runback fixed it. `False` here. |

## A worked example

The worst row in Part 1, in full:

| Column | Value |
|---|---|
| `Monitored` | `L29-38` |
| `Contingency` | `L06-31` |
| `Area 1` / `Area 2` | `Area 3 - South East` |
| `Base rating (MW)` | `1000.0` |
| `Contingency rating (MW)` | `1200.0` |
| `SRAP rating (MW)` | `1400.0` |
| `Base flow (MW)` | `827.1` |
| `Post-Contingency flow (MW)` | `1575.9` |
| `Base loading (pu)` | `0.827` |
| `Post-Contingency loading (pu)` | `1.576` |
| `Overload` | `Overload not acceptable` |
| `SRAP availability` | `SRAP not applicable` |

Read out loud: *L29-38 normally carries 827 MW against a 1000 MW rating, comfortable at 83%. Lose
L06-31, a different corridor in a different area, and it jumps to 1576 MW. That is 158% of its
rating, past the 1200 MW it could hold briefly and past the 1400 MW at which its protections
trip. Generation runback cannot save it. This corridor needs reinforcement.*

That last sentence is the handover to the investments demo.

---

## The other result tabs

| Tab | Rows x columns | Use it for |
|---|---|---|
| **P: Active power** | contingencies x buses | Net injection per bus. Shows where generation was lost or redispatched. |
| **Pf: Active power "from" base case** | circuits x 1 | The intact-network reference flow. The "before" column. |
| **Pf: Active power "from"** | contingencies x circuits | Post-contingency flow at the circuit's *from* end. Negative just means flow runs to-from. Zeros here reveal islanding. |
| **Branch Loading** | contingencies x circuits | Flow divided by rating, in percent. The full picture behind the report. |
| **Contingencies report** | one row per violation | The filtered answer. |
| **Srap used power** | circuits x buses | Empty here, SRAP is off. |

Rows are labelled by **contingency group**, not by device, which is exactly why one N-2 event is
one row rather than several.

## Caveats

- **SRAP is off.** The `SRAP availability` column still fills in from the ratings, so it reads as
  "could runback help", not "runback ran". The `Post-SRAP` columns simply repeat the
  post-contingency values.
- **The ratings are the demo's design, not IEEE39 canon.** The published IEEE39 case has no
  meaningful thermal limits, so ratings were set against measured flows to produce a case that is
  N-0 secure and N-1 insecure on ten corridors. Everything else is stock.
- **Voltages are not in the results panel.** The engine computes bus voltage for every contingency
  and stores it, but it is not exposed as a result tab, so this demo is about thermal security
  only.
- **Slack unit excluded.** G31 is the slack. Tripping the machine that absorbs every other
  outage's imbalance is a study about the reference, not about the network.

## Rebuilding

```bash
PYTHONPATH=src ./.venv/Scripts/python.exe trunk/Demos/Contingencies/build_contingency_demo.py
```

Rebuilds both files from `Grids_and_profiles/grids/IEEE39_1W.gridcal` and prints both reports.
