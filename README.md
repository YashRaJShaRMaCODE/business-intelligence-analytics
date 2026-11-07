# Catalog Quality Lab

A deployable data quality workbench for the bundled Netflix titles snapshot. It profiles record completeness, surfaces questionable rows in a searchable review queue, and exports normalized data for follow-on analysis.

This is an independent portfolio project. It does not connect to Netflix or another streaming service, and it does not report current availability or viewing behavior.

## What it does

- Profiles the 15 source fields and shows how many cells are blank.
- Breaks down movies, shows, genre tags, release decades, and IMDb rating coverage.
- Flags blank titles, repeated IDs, and repeated normalized title/type/year keys for human review.
- Adds a paged review queue for blank titles, repeated IDs, possible duplicates, malformed years, and out-of-range rating scores. Search by title, ID, type, year, or description; filter by issue and export the matching rows.
- Downloads a UTF-8 cleaned CSV. Rows with no title are excluded; genre tags are normalized; missing values remain blank; spreadsheet formula prefixes are escaped. Similar-title records are never silently removed.
- Serves a lightweight `/healthz` endpoint for deployment checks.
- Adds a restrictive Content Security Policy, browser permission limits, and clickjacking, MIME-sniffing, and referrer protections.

## Run locally

Python 3.10 or later is required.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`. Set `PORT` to change the listening port. The app reads the checked-in CSV at startup and does not require a database, account, API key, or external asset host.

## Routes

- `/` — dataset quality dashboard
- `/download/clean.csv` — cleaned CSV attachment
- `/download/review.csv` — filtered review queue CSV, including issue labels
- `/healthz` — JSON health status and loaded record count

## Checks

```powershell
python -m unittest discover -s tests
python -m compileall -q app.py tests
```

The tests use a temporary fixture CSV and do not modify the bundled dataset.
GitHub Actions runs the tests, Python compilation, and a dependency security audit on pushes and pull requests to `main`.

## Data notes

The repository includes titles and credits CSVs plus SQL analysis material. The dashboard uses the titles CSV only. The source file has 5,850 rows and includes title/type, descriptions, year, genres, countries, certification, runtime, seasons, and IMDb/TMDb fields. Its recorded years span 1945–2022. Figures are computed from the checked-in snapshot, not a live feed. The data source and its terms should be checked before redistribution of the raw files; this project license does not claim ownership of the dataset.

## Deployment

The Flask app binds to `0.0.0.0` and reads the host-provided `PORT`, so it can run on a standard Python web host. A production server command is:

```text
gunicorn app:app
```

The runtime dependency is listed in `requirements.txt`.

Static files live in `public/static/` so Vercel can serve them directly at `/static/`; local and Render runs use the same files through Flask. `render.yaml` keeps the Render Blueprint configuration available.
