# Contributing

## The one rule

**Adding a feature must not change an existing one.**

Everything else follows from that. See
[docs/ADDING_A_FEATURE.md](docs/ADDING_A_FEATURE.md) for the five steps.

## Before you push

```bash
.venv/bin/python -m pytest tests/ -q      # includes platform contract tests
cd frontend && npx ng build --configuration production
```

## Numbers a farmer acts on

Must come from a cited published source, never from a model. If you add a
dataset, add its citation to `FeatureInfo.sources` and a `selfcheck()` that
validates its shape. A feature whose data is wrong must fail at startup, not
at a farmer's screen.
