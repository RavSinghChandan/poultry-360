# 🐔 Poultry 360

A 360° assistant for Indian poultry farmers, built the **harness way** —
the model is one step inside a loop we control.

**Feature 1 (live):** enter a bird's age, get the exact ration — protein,
energy, amino acids, and how much feed the batch needs today. Every number
traced to a published standard.

## Run

```bash
./run.sh
```

Open **http://localhost:8000** — Hindi + English, built for a phone.

## Test

```bash
.venv/bin/python -m pytest tests/ -q
```

35 tests: data correctness, domain arithmetic, authority, budgets, and the
seams between them.

## Where the numbers come from

NRC *Nutrient Requirements of Poultry* (1994) Table 5-1, and BIS IS 1374:1992.
The agent looks them up and explains them. It never invents one — see
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Roadmap

| # | Feature | Status |
|---|---|---|
| 1 | Age → exact ration | **live** |
| 2 | Photo/video health scoring | next |
| 3 | Batch tracking, mortality, FCR | planned |
| 4 | Disease symptom triage | planned |
| 5 | Feed cost optimiser | planned |
