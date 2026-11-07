import ast
import csv
import io
import math
import os
from collections import Counter
from pathlib import Path

from flask import Flask, render_template, send_file

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "data" / "titles.csv.csv"
FIELDS = (
    "id", "title", "type", "description", "release_year", "age_certification",
    "runtime", "genres", "production_countries", "seasons", "imdb_id",
    "imdb_score", "imdb_votes", "tmdb_popularity", "tmdb_score",
)
SCORE_FIELDS = ("imdb_score", "tmdb_score")


def _number(value):
    try:
        number = float(value) if value not in (None, "") else None
        return number if number is not None and math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _genres(value):
    try:
        parsed = ast.literal_eval(value) if value else []
    except (ValueError, SyntaxError):
        parsed = []
    if not isinstance(parsed, (list, tuple)):
        return []
    return sorted({str(item).strip().casefold() for item in parsed if str(item).strip()})


def _read_dataset(path):
    with Path(path).open(encoding="latin1", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or not set(FIELDS).issubset(reader.fieldnames):
            raise ValueError("The catalog file is missing required columns.")
        return list(reader)


def _profile(rows):
    count = len(rows)
    missing = {field: sum(not (row.get(field) or "").strip() for row in rows) for field in FIELDS}
    years = [int(row["release_year"]) for row in rows if (row.get("release_year") or "").isdigit()]
    ratings = [_number(row.get("imdb_score")) for row in rows]
    ratings = [score for score in ratings if score is not None]
    duplicate_ids = count - len({(row.get("id") or "").strip() for row in rows})
    names = Counter(
        ((row.get("title") or "").strip().casefold(), (row.get("type") or "").strip().upper(), (row.get("release_year") or "").strip())
        for row in rows if (row.get("title") or "").strip()
    )
    possible_duplicates = sum(total - 1 for total in names.values() if total > 1)
    genre_counts = Counter(genre for row in rows for genre in _genres(row.get("genres", "")))
    year_counts = Counter(year // 10 * 10 for year in years)
    quality = round(100 * sum(count - missing[field] for field in FIELDS) / (count * len(FIELDS))) if count else 0
    return {
        "count": count,
        "quality": quality,
        "missing": missing,
        "missing_total": sum(missing.values()),
        "duplicate_ids": duplicate_ids,
        "possible_duplicates": possible_duplicates,
        "years": years,
        "year_min": min(years, default=None),
        "year_max": max(years, default=None),
        "average_imdb": round(sum(ratings) / len(ratings), 1) if ratings else None,
        "rated_count": len(ratings),
        "types": Counter((row.get("type") or "Unknown").upper() for row in rows),
        "genres": genre_counts.most_common(8),
        "decades": sorted(year_counts.items()),
        "columns": len(FIELDS),
    }


def _clean_row(row):
    cleaned = {field: (row.get(field) or "").strip() for field in FIELDS}
    cleaned["title"] = " ".join(cleaned["title"].split())
    cleaned["type"] = cleaned["type"].upper()
    cleaned["genres"] = "; ".join(_genres(cleaned["genres"]))
    for field in ("release_year", "runtime", "seasons", "imdb_votes"):
        value = cleaned[field]
        cleaned[field] = str(int(value)) if value.isdigit() else ""
    for field in SCORE_FIELDS + ("tmdb_popularity",):
        value = _number(cleaned[field])
        cleaned[field] = str(value) if value is not None else ""
    for field in ("title", "description", "age_certification", "genres", "production_countries", "imdb_id"):
        if cleaned[field].lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
            cleaned[field] = "'" + cleaned[field]
    return cleaned


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(TITLES_CSV=str(DATASET), MAX_CONTENT_LENGTH=1024 * 1024)
    if test_config:
        app.config.update(test_config)
    rows = _read_dataset(app.config["TITLES_CSV"])
    profile = _profile(rows)

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'; style-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        return response

    @app.get("/")
    def index():
        type_total = sum(profile["types"].values()) or 1
        max_genre = max((value for _, value in profile["genres"]), default=1)
        max_decade = max((value for _, value in profile["decades"]), default=1)
        return render_template(
            "index.html", profile=profile, type_total=type_total,
            max_genre=max_genre, max_decade=max_decade,
            critical_missing=sorted(profile["missing"].items(), key=lambda item: item[1], reverse=True)[:6],
        )

    @app.get("/download/clean.csv")
    def download_clean():
        cleaned = (_clean_row(row) for row in rows if (row.get("title") or "").strip())
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(cleaned)
        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            mimetype="text/csv", as_attachment=True, download_name="catalog-quality-clean.csv",
        )

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "records": profile["count"]}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
