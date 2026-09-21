# Poultry 360 — architecture

Built the **harness way**: the model is one step inside a loop we control, not
the system itself. This document is the blueprint to copy for the next agentic
app.

---

## The rule this app is built on

> A model is a function. A harness is a system.

Reliability lives in the loop, the tools, the policy and the trace — not in the
prompt. If the model is replaced tomorrow, everything below still holds.

---

## Layers

```
frontend/               farmer UI — Hindi + English, phone-first
backend/
  api/main.py           HTTP surface, thin on purpose
  domain/
    feed.py             arithmetic on published numbers
    advisor.py          wires tools into the harness
  harness/
    agent.py            the loop: budgets, termination, observation
    tools.py            registry — validate, authorise, execute
    policy.py           effects and modes; who may do what
    tracing.py          every step recorded
  data/rations.py       the published standards (single source of truth)
```

The dependency arrow points one way: `api → domain → harness → data`. The
harness knows nothing about poultry; the data knows nothing about agents.

---

## The nine steps of a turn

Eight of them are ours. Only **DECIDE** is the model's.

```
assemble → budget → call → DECIDE → validate → authorise
         → execute → observe → loop
```

| Step | Where | What it prevents |
|---|---|---|
| assemble | `agent.run` | context that grows without limit |
| budget | `agent.run` | a loop that never ends, a phone that hangs |
| call | `agent.run` | an exception in the model killing the request |
| **decide** | the model | — |
| validate | `tools.execute` | a call to a tool that does not exist |
| authorise | `policy.check` | a write in an advice-only session |
| execute | `tools.execute` | an exception reaching the user |
| observe | `agent.run` | the model not seeing what happened |
| loop | `agent.run` | repeating the same failed call forever |

---

## Why the numbers do not come from a model

Feeding the wrong protein at the wrong age stunts or kills birds.

`data/rations.py` is a transcription of **NRC (1994) Table 5-1** and
**BIS IS 1374:1992**. The agent may look those numbers up and explain them. It
may never originate one. Every API response carries `source` and
`dataset_version` so any figure on a farmer's screen can be traced to a
published table.

A test asserts the same question returns the same answer five times running.
An advice app that answers differently each run is not advice.

---

## Authority

Tools declare an `Effect`; policy keys off the effect, never off the name.

| Effect | Example | READ_ONLY | ASK_FIRST | AUTONOMOUS |
|---|---|---|---|---|
| READ | `lookup_ration` | allowed | allowed | allowed |
| WRITE | record mortality | denied | confirm | allowed |
| DESTRUCTIVE | order feed (spends money) | denied | confirm | **confirm** |

Destruction always asks, even when autonomous. The default mode is READ_ONLY,
so the demo cannot change anything.

**Injection containment:** any tool marked `reads_untrusted` (a farmer's photo
caption, a supplier page) withdraws destructive tools for the rest of the run.
An injected instruction then has nothing to reach.

---

## Termination

Three independent stops, checked *before* spending:

- `max_turns` (6) — a model that never finishes
- `max_seconds` (20) — a farmer on a slow connection
- `repeat_limit` (2) — the same call repeated is a stuck model

`RunResult.ok` is true **only** for `COMPLETED`. A budget stop is never
reported as success.

---

## Adding feature 2 (photo/video health scoring)

Nothing in the harness changes. The work is:

1. A tool `assess_photo(image)` with `effect=READ, reads_untrusted=True`.
2. Swap `_planner` in `advisor.py` for a real LLM adapter returning the same
   `{"type": "tool"|"final", ...}` shape.
3. Tests for the new tool's failure modes.

The budgets, policy, tracing and error handling are already there. That is the
return on building it this way.

---

## Running it

```bash
./run.sh                                   # http://localhost:8000
.venv/bin/python -m pytest tests/ -q       # 35 tests
```
