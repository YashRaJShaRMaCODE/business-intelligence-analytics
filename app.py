import ast
import csv
import io
import math
import os
from collections import Counter
from pathlib import Path

from flask import Flask, render_template, request, send_file

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
    source_ids = [(row.get("id") or "").strip() for row in rows if (row.get("id") or "").strip()]
    duplicate_ids = len(source_ids) - len(set(source_ids))
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


def _review_rows(rows):
    id_counts = Counter((row.get("id") or "").strip() for row in rows if (row.get("id") or "").strip())
    keys = Counter(
        ((row.get("title") or "").strip().casefold(), (row.get("type") or "").strip().upper(), (row.get("release_year") or "").strip())
        for row in rows if (row.get("title") or "").strip()
    )
    results = []
    for row in rows:
        title = (row.get("title") or "").strip()
        source_id = (row.get("id") or "").strip()
        year = (row.get("release_year") or "").strip()
        key = (title.casefold(), (row.get("type") or "").strip().upper(), year)
        issues = []
        if not title:
            issues.append(("missing_title", "Blank title"))
        if source_id and id_counts[source_id] > 1:
            issues.append(("repeated_id", "Repeated source ID"))
        if title and keys[key] > 1:
            issues.append(("possible_duplicate", "Possible duplicate key"))
        if year and not year.isdigit():
            issues.append(("invalid_year", "Invalid release year"))
        for field in SCORE_FIELDS:
            score = _number(row.get(field))
            if (row.get(field) or "").strip() and (score is None or not 0 <= score <= 10):
                issues.append(("invalid_score", f"Invalid {field.replace('_', ' ')}"))
        if issues:
            results.append({**row, "issue_codes": [code for code, _ in issues], "issues": [label for _, label in issues]})
    return results


def _matching_reviews(rows, query, flag):
    allowed = {"any", "missing_title", "repeated_id", "possible_duplicate", "invalid_year", "invalid_score"}
    flag = flag if flag in allowed else "any"
    term = query.casefold()
    return [
        row for row in rows
        if (flag == "any" or flag in row["issue_codes"])
        and (not term or term in " ".join(str(row.get(key) or "") for key in ("title", "id", "type", "release_year", "description")).casefold())
    ], flag


def create_app(test_config=None):
    static_folder = None if os.environ.get("VERCEL") else str(ROOT / "public" / "static")
    app = Flask(__name__, static_folder=static_folder, static_url_path="/static")
    app.config.from_mapping(TITLES_CSV=str(DATASET), MAX_CONTENT_LENGTH=1024 * 1024)
    if test_config:
        app.config.update(test_config)
    rows = _read_dataset(app.config["TITLES_CSV"])
    profile = _profile(rows)
    review_rows = _review_rows(rows)

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), usb=()")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        return response

    @app.get("/")
    def index():
        type_total = sum(profile["types"].values()) or 1
        max_genre = max((value for _, value in profile["genres"]), default=1)
        max_decade = max((value for _, value in profile["decades"]), default=1)
        query = request.args.get("q", "").strip()[:100]
        matches, flag = _matching_reviews(review_rows, query, request.args.get("flag", "any"))
        page_size = 15
        page_count = max(1, math.ceil(len(matches) / page_size))
        page = min(max(1, request.args.get("page", 1, type=int) or 1), page_count)
        return render_template(
            "index.html", profile=profile, type_total=type_total,
            max_genre=max_genre, max_decade=max_decade,
            critical_missing=sorted(profile["missing"].items(), key=lambda item: item[1], reverse=True)[:6],
            review_rows=matches[(page - 1) * page_size:page * page_size], review_query=query,
            review_flag=flag, review_total=len(matches), review_page=page, review_pages=page_count,
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

    @app.get("/download/review.csv")
    def download_review():
        query = request.args.get("q", "").strip()[:100]
        selected, _ = _matching_reviews(review_rows, query, request.args.get("flag", "any"))
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=(*FIELDS, "review_flags"))
        writer.writeheader()
        for row in selected:
            cleaned = _clean_row(row)
            cleaned["review_flags"] = "; ".join(row["issues"])
            writer.writerow(cleaned)
        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            mimetype="text/csv", as_attachment=True, download_name="catalog-quality-review.csv",
        )

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "records": profile["count"]}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
