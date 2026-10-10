# Contributing

## Setup

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt                    # add requirements-neural.txt for the neural method
cd frontend && npm install && cd ..
```

COLMAP must be installed separately (see the README).

## Before opening a pull request

```bash
ruff check .          # lint
python -m pytest      # backend tests
cd frontend && npm run build
```

* Keep changes focused; one topic per pull request.
* Add or update tests for behaviour changes. The tests run without a GPU and without network access.
* Do not hard-code metric values or sample numbers outside tests and `frontend/src/services/mock.js`. A value that cannot be measured is `null`.
* Update `docs/API_CONTRACT.md` when an endpoint or response shape changes.
* Do not commit datasets, model weights, COLMAP binaries, `workspace/` or `outputs/`.

## Layout

| Path | Contents |
|---|---|
| `src/reconstruction/` | engine: quality checks, view selection, SfM orchestration, neural fusion, metrics, datasets |
| `src/backend/` | FastAPI app, job manager, SQLite history, analysis |
| `frontend/` | React + Vite + Tailwind UI |
| `tests/` | pytest suite |
| `docs/` | API contract, methodology, dataset guide |
