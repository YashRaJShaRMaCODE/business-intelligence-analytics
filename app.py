import ast
import csv
import io
import math
import os
from collections import Counter
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from flask import Flask, Response, render_template, request, send_file

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "data" / "titles.csv.csv"
FIELDS = (
    "id", "title", "type", "description", "release_year", "age_certification",
    "runtime", "genres", "production_countries", "seasons", "imdb_id",
    "imdb_score", "imdb_votes", "tmdb_popularity", "tmdb_score",
)
SCORE_FIELDS = ("imdb_score", "tmdb_score")
INTEGER_FIELDS = ("runtime", "seasons", "imdb_votes")


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
        return [{"_source_record": number, **row} for number, row in enumerate(reader, start=1)]


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
    quality = round(100 * sum(count - missing[field] for field in FIELDS) / (count * len(FIELDS))) if count else None
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
    for field in ("id", "title", "type", "description", "age_certification", "genres", "production_countries", "imdb_id"):
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
        if not year:
            issues.append(("missing_year", "Missing release year"))
        elif not year.isdigit():
            issues.append(("invalid_year", "Invalid release year"))
        for field in SCORE_FIELDS:
            score = _number(row.get(field))
            if (row.get(field) or "").strip() and (score is None or not 0 <= score <= 10):
                issues.append(("invalid_score", f"Invalid {field.replace('_', ' ')}"))
        for field in INTEGER_FIELDS:
            value = (row.get(field) or "").strip()
            try:
                invalid = value and (not value.isdigit() or int(value) < (1 if field in ("runtime", "seasons") else 0))
            except ValueError:
                invalid = bool(value)
            if invalid:
                issues.append(("invalid_numeric", f"Invalid {field.replace('_', ' ')}"))
        popularity = (row.get("tmdb_popularity") or "").strip()
        popularity_value = _number(popularity)
        if popularity and (popularity_value is None or popularity_value < 0):
            issues.append(("invalid_numeric", "Invalid tmdb popularity"))
        if issues:
            results.append({**row, "source_record": row.get("_source_record"),
                            "issue_codes": [code for code, _ in issues], "issues": [label for _, label in issues]})
    return results


def _matching_reviews(rows, query, flag, media_type="any"):
    allowed = {"any", "missing_title", "missing_year", "repeated_id", "possible_duplicate", "invalid_year", "invalid_score", "invalid_numeric"}
    flag = flag if flag in allowed else "any"
    media_type = media_type if media_type in {"any", "MOVIE", "SHOW"} else "any"
    term = query.casefold()
    return [
        row for row in rows
        if (flag == "any" or flag in row["issue_codes"])
        and (media_type == "any" or (row.get("type") or "").strip().upper() == media_type)
        and (not term or term in " ".join(str(row.get(field) or "") for field in FIELDS).casefold())
    ], flag


def _sort_reviews(rows, order):
    allowed = {"source", "title", "year", "imdb_score"}
    order = order if order in allowed else "source"
    source_record = lambda row: int(row["source_record"])
    keys = {
        "source": lambda row: (source_record(row),),
        "title": lambda row: ((row.get("title") or "").strip().casefold(), source_record(row)),
        "year": lambda row: (int(row["release_year"]) if (row.get("release_year") or "").isdigit() else math.inf, source_record(row)),
        "imdb_score": lambda row: (_number(row.get("imdb_score")) if _number(row.get("imdb_score")) is not None else math.inf, source_record(row)),
    }
    return sorted(rows, key=keys[order]), order


def create_app(test_config=None):
    static_folder = None if os.environ.get("VERCEL") else str(ROOT / "public" / "static")
    app = Flask(__name__, static_folder=static_folder, static_url_path="/static")
    app.config.from_mapping(
        TITLES_CSV=str(DATASET), MAX_CONTENT_LENGTH=1024 * 1024,
        PUBLIC_BASE_URL=os.environ.get("PUBLIC_BASE_URL", "https://catalog-quality-lab.vercel.app").rstrip("/"),
    )
    if test_config:
        app.config.update(test_config)
    rows = _read_dataset(app.config["TITLES_CSV"])
    profile = _profile(rows)
    review_rows = _review_rows(rows)
    review_issue_counts = Counter(code for row in review_rows for code in row["issue_codes"])

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
        media_type = request.args.get("type", "any").upper()
        matches, flag = _matching_reviews(review_rows, query, request.args.get("flag", "any"), media_type)
        matches, sort_by = _sort_reviews(matches, request.args.get("sort", "source"))
        page_size = 15
        page_count = max(1, math.ceil(len(matches) / page_size))
        page = min(max(1, request.args.get("page", 1, type=int) or 1), page_count)
        return render_template(
            "index.html", profile=profile, type_total=type_total,
            max_genre=max_genre, max_decade=max_decade,
            critical_missing=sorted(profile["missing"].items(), key=lambda item: item[1], reverse=True)[:6],
            review_rows=matches[(page - 1) * page_size:page * page_size], review_query=query,
            review_flag=flag, review_total=len(matches), review_page=page, review_pages=page_count,
            review_type=media_type if media_type in {"any", "MOVIE", "SHOW"} else "any",
            review_sort=sort_by, review_issue_counts=review_issue_counts,
            public_url=f'{app.config["PUBLIC_BASE_URL"]}/',
        )

    @app.get("/robots.txt")
    def robots_txt():
        sitemap_url = f'{app.config["PUBLIC_BASE_URL"]}/sitemap.xml'
        return Response(f"User-agent: *\nAllow: /\nSitemap: {sitemap_url}\n", mimetype="text/plain")

    @app.get("/sitemap.xml")
    def sitemap_xml():
        sitemap = Element("urlset", {"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"})
        entry = SubElement(sitemap, "url")
        SubElement(entry, "loc").text = f'{app.config["PUBLIC_BASE_URL"]}/'
        return Response(tostring(sitemap, encoding="utf-8", xml_declaration=True), mimetype="application/xml")

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
        selected, _ = _matching_reviews(
            review_rows, query, request.args.get("flag", "any"), request.args.get("type", "any").upper(),
        )
        selected, _ = _sort_reviews(selected, request.args.get("sort", "source"))
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=(*FIELDS, "source_record", "review_flags"))
        writer.writeheader()
        for row in selected:
            cleaned = _clean_row(row)
            cleaned["source_record"] = row["source_record"]
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
