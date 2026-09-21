# Adding a feature

The architecture exists so this is safe. Adding feature N **must not touch**
feature N−1. Follow these five steps and the tests will hold you to it.

---

## 1. Create the package

```bash
mkdir -p backend/features/<key>
```

One folder. It owns its data, logic, routes, tools and self-check.

## 2. Implement the contract

`backend/features/<key>/__init__.py` must expose a `feature()` factory
returning something that satisfies `core.contracts.Feature`:

```python
def feature() -> MyFeature:
    return MyFeature()
```

Four methods, all required:

| Method | Returns | Notes |
|---|---|---|
| `info()` | `FeatureInfo` | stable `key`, both languages, `status` |
| `router()` | `APIRouter` | mounted at `/api/<key>` |
| `tools()` | `list[ToolSpec]` | **names must start with `<key>`** |
| `selfcheck()` | `list[str]` | empty means healthy |

Copy `backend/features/health/` — it was written without editing a single
line of `features/feed`, `core/` or `harness/`.

## 3. Add the Angular route

`frontend/src/app/app.routes.ts` — one lazy route:

```ts
{ path: '<key>',
  loadComponent: () => import('./features/<key>/<key>.component')
    .then(m => m.MyComponent) },
```

The nav menu needs **no change**: it renders from `/api/features`.

## 4. Write the tests

`tests/test_<key>.py`. The platform contract tests run against your feature
automatically — you do not add them.

## 5. Run everything

```bash
.venv/bin/python -m pytest tests/ -q
```

---

## The rules, and what enforces them

| Rule | Enforced by |
|---|---|
| A feature never imports another feature | `test_a_feature_never_imports_another_feature` — parses your imports |
| The platform never imports a feature | `test_the_platform_never_imports_a_feature` |
| Tool names are namespaced | `test_feature_tools_are_namespaced` |
| No two features share a tool name | `test_tool_names_are_unique_across_features` |
| A feature declares both languages | `test_feature_info_is_complete` |
| An unhealthy feature is not served | `test_an_unhealthy_feature_is_not_served` |

These are real. Adding `from features.feed import rations` to the health
feature makes the suite fail immediately — verified.

---

## What happens when a feature breaks

Nothing else does.

- **Fails to import** → recorded in `failed_to_load`, not mounted, app serves.
- **`selfcheck()` returns problems** → mounted nowhere, its tools unreachable,
  visible at `/api/health` and greyed out in the UI.
- **Duplicate key or tool name** → rejected at registration with a reason.

A farmer using feed advice is unaffected by a broken health feature.

---

## Shared code

Needed by two features? It does **not** go in either one.

- Agent loop, policy, tools, tracing, LLM → `backend/harness/`
- Contracts, registry, config → `backend/core/`
- Angular API client and shared UI → `frontend/src/app/core/`
