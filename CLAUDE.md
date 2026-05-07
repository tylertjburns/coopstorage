# CLAUDE.md

## Project Overview

`coopstorage` is a Python library for embedded storage system simulation and management.
It models physical storage locations containing containers, governed by channel processors
that enforce access patterns (FIFO, LIFO, OMNI, with flow variants and push options).
It ships a FastAPI-based live visualizer (isometric/top-down, SSE updates) and an optional
MongoDB persistence layer.

**PyPI package:** `coopstorage` (MIT) | **Version:** tracked in `setup.py`

---

## Project Structure

```
coopstorage/
├── coopstorage/            # Main package
│   ├── storage/
│   │   ├── api/            # FastAPI app — routers/v1/, static/index.html (visualizer UI)
│   │   └── loc_load/       # Core logic
│   │       ├── channel_processors.py   # 18 channel processor types
│   │       ├── storage.py              # Orchestration entry point
│   │       ├── reservation_provider.py
│   │       ├── qualifiers.py
│   │       ├── transferRequest.py
│   │       ├── event_bus.py
│   │       └── data/                   # Data persistence layer
│   ├── storage2mongo.py    # Optional MongoDB integration
│   ├── simulation.py
│   ├── storage_generators.py   # Benchmark / sim utilities
│   └── viz_helper.py
├── tests/                  # 8 test modules (exclude test_storage_benchmark.py from normal runs)
├── .github/
│   ├── skills/             # Claude Code skills (see below)
│   └── workflows/
│       └── python-package.yml  # CI: validate → publish → docker → benchmark
├── main.py                 # Entry point: uvicorn on port 1219
├── run_viz_benchmark.py    # Interactive benchmark/visualizer launcher
├── Dockerfile
└── setup.py
```

---

## Running the Project

```bash
# API server
python main.py                          # http://localhost:1219

# Visualizer + benchmark modes
python run_viz_benchmark.py --mode showcase --size SMALL

# Tests (exclude benchmark)
pytest tests/ --ignore=tests/test_storage_benchmark.py

# Docker
rundocker.bat
```

---

## CI/CD Pipeline

Triggers on push to master or PR touching code/tests/setup/requirements:

1. **validate** — flake8 lint + pytest (Python 3.11 / 3.12 / 3.13)
2. **publish** — auto-increments `setup.py` minor version, publishes to PyPI
3. **docker** — builds and pushes `tylertjburns/coopstorage:<version>` + `latest` to Docker Hub
4. **benchmark** — runs performance tests, captures artifact (90-day retention)

Chore-only PRs (docs/config) should include `[skip ci]` in the commit message to skip CI.

---

## Behavioral Preferences

### Code Review Before Applying
Always show proposed code changes as text/diff and wait for explicit confirmation before
using Edit or Write tools. Do not apply changes silently.

### Responses
Keep responses concise. Skip trailing summaries of what was just done. Present PR URLs as
clickable markdown links.

---

## Git Workflow

Use the `/git-branch-workflow` skill when the user says "commit", "push", "save", "open PR",
or similar. Key rules:

- Never commit to `master` — always branch → PR
- `feature/<desc>` for code/test changes; `chore/<desc>` for docs/config only
- Run `pytest tests/ --ignore=tests/test_storage_benchmark.py` before pushing functional changes
- Confirm with user before push or PR creation (shared/visible actions)
- `gh` CLI path in bash: `"/c/Program Files/GitHub CLI/gh.exe"`

---

## Skills (`.github/skills/`)

### `git-branch-workflow`
**Trigger:** user says "commit", "push", "save", "open PR", or similar

Full flow: show git status → pull master → create branch → coverage check → run tests →
confirm → push → open PR → sync local master after merge. Includes `[skip ci]` rules for
chore branches and branch cleanup after merge.

---

## Key Dependencies

| Package | Role |
|---|---|
| `fastapi` / `uvicorn` | REST API + live visualizer server |
| `pydantic` | Data validation and DTOs |
| `PyPubSub` | Internal event bus |
| `cooptools>=1.57` | Shared utility library |
| `coopmongo` | Optional MongoDB persistence |
| `matplotlib` / `numpy` | Visualization and benchmarking |

---

## Architecture Notes

- **Transfer resolution** is declarative: callers submit `TransferRequest` objects with
  location qualifiers (capacity, UoM, resource types, occupation state, accessibility);
  the engine resolves matching locations.
- **Channel processors** govern slot access per location — 18 variants covering FIFO/LIFO/OMNI
  with no-flow, flow, and push configurations.
- **Event bus** (`PyPubSub`) decouples state changes from downstream consumers (viz, logging).
- **Visualizer** streams real-time updates via SSE; served at `/static/index.html`.
- **MongoDB integration** is optional — `storage2mongo.py` handles persistence if configured.
- Python 3.11+ required (CI matrix: 3.11, 3.12, 3.13).
