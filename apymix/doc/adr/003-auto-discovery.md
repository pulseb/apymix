# ADR-003 : Automatic Discovery of API Sub-Apps

**Status:** Accepted
**Date:** 2026-02-24

## Context

Apymix must allow adding new business APIs without modifying the technical module's code (`apymix/`). The module must stay **completely agnostic** of the APIs to remain reusable (and even open-sourceable).

Three approaches can be considered for connecting sub-apps to the main app.

## Considered options

### Option A : Manual registration

Each sub-app is imported and mounted explicitly in `apymix/app.py`.

```python
from apis.wedding.app import app as wedding_app
main_app.mount("/wedding", wedding_app)
```

- **Pros:** Explicit, easy to understand, full control.
- **Cons:** The `apymix/` module imports directly from `apis/` → strong coupling. Each new API requires modifying `apymix/app.py`.

### Option B : Central configuration file

An `apis.yaml` file at the root lists the APIs to mount.

```yaml
apis:
  - module: apis.wedding.app
    prefix: /wedding
  - module: apis.finance.app
    prefix: /finance
```

- **Pros:** Decoupled (no import in `apymix/`), easy to read.
- **Cons:** Central file to maintain, no co-location (config is separated from the API code).

### Option C : Convention + local manifest (auto-discovery)

The app factory walks the workspace for `amx.yaml` files. Each project declaring `type: api` is automatically mounted. An optional `amx.yaml` per project allows customizing metadata.

- **Pros:** Zero central configuration, co-location (each API carries its own metadata), adding an API = creating a project, simple and documented convention.
- **Cons:** Implicit "magic" (dynamic import), can surprise a new contributor. Requires a well-documented convention.

## Decision

**Option C: Convention + local manifest (auto-discovery).**

This is the approach most aligned with the project's goals:

1. **Full decoupling**: `apymix/` knows no API by name
2. **Frictionless**: adding an API = creating a project with an `amx.yaml`
3. **Flexible**: the `amx.yaml` allows customization without imposing it

### Discovery convention

For a project to be recognized:

| Element | Required | Description |
|---------|-------------|-------------|
| `amx.yaml` with `type: api` and `module: <module>` exporting `app: FastAPI` | ✅ Yes | Sub-app entry point |
| `amx.yaml` fields: `route`, `enabled`, `version`, `description` | ❌ No | Metadata overrides |

### Default values (without overrides)

| Field | Inferred value |
|-------|----------------|
| `route` | `/<directory_name>` |
| `enabled` | `true` |

### Exclusion conventions

- Folders starting with `_` are ignored (e.g. `_archive/`)
- Folders without `amx.yaml` declaring `type: api` are silently ignored
- An `amx.yaml` with `enabled: false` disables the API without removing it

## Consequences

### Positive
- The `apymix/` module is 100% agnostic of APIs → open-sourceable
- Adding an API requires no existing modification
- `amx.yaml` offers flexibility without complexity
- The same convention is used for frontends (consistency)

### Negative
- Dynamic import (`importlib.import_module`) can make debugging less intuitive
- If an `amx.yaml` is malformed, the error message may be less clear

### Risks
- Risk of prefix collision if two APIs share the same directory name → mitigated by validation at startup
- Non-deterministic mount order → mitigated by alphabetical sorting of directories
