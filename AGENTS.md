# AGENTS.md

## Project

Clash of Clans clan manager — Flask web app that polls the Clash API on a 60-second scheduler, tracks war performance/donations/CWL, and renders member rankings via Mako templates.

## Runtime

- **Python 3.9** (pinned in Dockerfile)
- **PYTHONPATH must include `clashpy`** — all app modules are in the `clashpy/` package but imported at top level (e.g. `import clanManager`), so the path must be set before import
- **Config required**: `data/config.json` must exist with keys: `clanTag`, `key`, `email`, `password`, `keyName` — app exits without it

## Running

```sh
# Local (run.sh handles venv + PYTHONPATH + flask)
./run.sh

# Docker
docker build -t clash . && docker run -p 5000:5000 clash
```

`run.sh` sets `PYTHONPATH=clashpy` and `FLASK_APP=update.py`, then runs `flask run --port=5001`.

## Architecture

- **`update.py`** — Flask app entrypoint. Defines routes (`/`, `/cwl`, `/clan`, `/warnings`, `/post`), runs `main()` at import time which starts the 60s scheduler. Also contains ranking logic in `processResults()`. All mutable state (`clan`, `page`, `cwlPage`, `day`) managed through `AppState` singleton.
- **`clashpy/appState.py`** — Thread-safe `AppState` class that owns all shared mutable state. Uses `RLock` for scheduler/request thread safety. Provides typed accessors (`get_page()`, `get_member_list()`, etc.) and mutation methods (`begin_update()`, `add_warning()`, etc.).
- **`clashpy/`** — Core logic package:
  - `clanManager.py` — Wires config → `clashApi` + `persistanceManager`
  - `clashApi.py` — Auth with CoC developer site, fetches clan/war/CWL/player data
  - `persistanceManager.py` — JSON file persistence for wars, members, CWL seasons under `data/`
  - `cwlController.py` — CWL round tracking
  - `migration.py` — Data migration on startup
  - `utils.py`, `donationManager.py`, `notesController.py`, `warningsController.py`, `homeController.py` — Supporting modules
- **`templates/`** — Mako templates (`home.html`, `cwl.html`, `notes.html`, `warning.html`)
- **`data/`** — Runtime JSON state (gitignored). Created on first run if missing.

## Key conventions

- Imports from `clashpy` are **bare** (e.g. `import clanManager`), not `from clashpy import clanManager` — `PYTHONPATH=clashpy` makes this work
- `main()` in `update.py` runs at module level, so importing the module starts the app
- All mutable state is owned by `AppState` (`state` global in `update.py`). Routes and scheduler access state through accessor methods, not bare globals.
- `AppState` uses `RLock` — nested locks from `processResults()` calling `get_member_list()` then `set_page()` won't deadlock
- `begin_update()` / `processResults()` / `finish_update()` are intentionally NOT atomic — a concurrent request may see a new `lastUpdated` with the previous `page`. This is acceptable since page is always updated within the same scheduler tick.
- `state.get_clan_ref()` returns the internal dict reference (UNSAFE — use only at startup for `Migration`). `state.get_clan_snapshot()` returns a deep copy.
- `state.get_member_list()` returns a deep copy — mutating the result does NOT affect internal state.
- `PersistanceManager.getMembers()` returns a shallow copy list — callers should not mutate returned member dicts
- `PersistanceManager.getMember()` returns a shallow copy dict — mutations don't affect internal state
- `PersistanceManager` warning methods (`add_warning`, `remove_warning`, `add_cwl_warning`, `remove_cwl_warning`) hold `PM._lock` and are called by `AppState` with `AppState._lock` held (lock order: AppState → PM).
- `writeJson` is consolidated in `PersistanceManager` — uses atomic temp-file + `os.replace` pattern. `AppState` receives it as a dependency injection.
- `main()` in `update.py` runs at module level, so importing the module starts the app
- `Migration.__init__` mutates the `clan` dict in-place; use `state.get_clan_ref()` when passing to it
- Data files live under `data/` and are JSON; `data/config.json` contains credentials so it's gitignored

## Testing

```sh
python3 -m pytest tests/ -v
```

- **`tests/`** — pytest suite with `helpers.py` for shared test utilities and `MockLogger`/`MockClanManager`
- `test_appState.py` — AppState thread safety, init, snapshots, warning mutations, write-through, concurrent reads/writes
- `test_persistanceManager.py` — addWar, updateMembers, writeJson atomicity, corrupt JSON handling, trimList, CWL season
- `test_utils.py` — getCurrentSeason, getPreviousSeason, addDonationHistory, touch
- `test_cwlController.py` — _processCWLPlayer, rank calculation, sortStars
- `test_clanManager.py` — missing config raises FileNotFoundError, corrupt config raises RuntimeError
- `test_clashApi.py` — RuntimeError on failed clan fetch, InvalidCredentials on 403, API_TIMEOUT set
- `test_update.py` — expireWarnings, writeJson atomicity, pruneBackups, hmac.compare_digest usage
- Tests use `tmp_path` fixture for isolated `data/` directories via `TestablePersistanceManager`
- `test.py` at root is a legacy manual smoke test requiring real credentials