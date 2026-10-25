# ScreenScope: streaming catalog analytics

A small, local catalog explorer for the bundled titles dataset. Search titles and descriptions, filter by genre, release year and format, and browse IMDb ratings in a paginated view.

This is an independent analysis project. The dataset does not represent a live streaming service catalog and ScreenScope is not affiliated with a streaming provider.

## Run locally

Python 3.10 or later is required.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`. On first start, ScreenScope imports `data/titles.csv.csv` into an ignored SQLite cache under `instance/`. The cache refreshes when the source CSV changes. No MySQL server, database account, API key or external asset host is needed.

## Tests

```powershell
python -m unittest discover -s tests
python -m compileall -q app.py tests
```

The tests use a temporary CSV and SQLite database; they do not access the network or alter the bundled dataset.

## Dataset fields

The explorer uses title, format, description, release year, certification, runtime, genres and IMDb/TMDb scores. `data/credits.csv.csv` and the SQL analysis folder are retained as source material; cast/crew exploration is not implemented in the web app yet.

## Current scope

This repository is a local analytics prototype. It does not provide streaming recommendations, subscriber demographics, live platform data, authentication, or a hosted production service. The age-risk model scripts that were previously mixed into this folder belong to the separate AgeWell project and have been removed from this repository.
