import csv
import math
import sqlite3
from contextlib import closing
from pathlib import Path

from flask import Flask, render_template, request


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "data" / "titles.csv.csv"
PAGE_SIZE = 24


def database_path():
    return ROOT / "instance" / "catalog.sqlite3"


def init_catalog(database, source):
    source = Path(source)
    stamp = f"{source.stat().st_size}:{source.stat().st_mtime_ns}"
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database)) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS titles (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, media_type TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', release_year INTEGER,
            age_certification TEXT, runtime INTEGER, genres TEXT,
            production_countries TEXT, seasons INTEGER,
            imdb_score REAL, tmdb_score REAL
        )""")
        conn.execute("CREATE TABLE IF NOT EXISTS catalog_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        loaded = conn.execute("SELECT value FROM catalog_meta WHERE key='source_stamp'").fetchone()
        if loaded and loaded[0] == stamp:
            return

        with source.open(encoding="latin1", newline="") as file:
            rows = []
            for row in csv.DictReader(file):
                rows.append((
                    row["id"], row["title"], row["type"].upper(), row.get("description") or "",
                    _integer(row.get("release_year")), row.get("age_certification") or "",
                    _integer(row.get("runtime")), row.get("genres") or "",
                    row.get("production_countries") or "", _integer(row.get("seasons")),
                    _number(row.get("imdb_score")), _number(row.get("tmdb_score")),
                ))

        with conn:
            conn.execute("DELETE FROM titles")
            conn.executemany("""INSERT INTO titles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", rows)
            conn.execute("INSERT OR REPLACE INTO catalog_meta VALUES ('source_stamp', ?)", (stamp,))
            conn.execute("CREATE INDEX IF NOT EXISTS titles_type_year ON titles(media_type, release_year)")
            conn.execute("CREATE INDEX IF NOT EXISTS titles_rating ON titles(imdb_score)")


def _integer(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _number(value):
    try:
        number = float(value) if value not in (None, "") else None
        return number if number is not None and math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=str(database_path()),
        TITLES_CSV=str(DATASET),
        MAX_CONTENT_LENGTH=1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    init_catalog(app.config["DATABASE"], app.config["TITLES_CSV"])

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; img-src 'self' data:; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
        )
        return response

    @app.get("/")
    def index():
        search = request.args.get("search", "").strip()[:100]
        genre = request.args.get("genre", "").strip()[:40]
        media_type = request.args.get("type", "").upper()
        if media_type not in {"MOVIE", "SHOW"}:
            media_type = ""
        year_text = request.args.get("year", "").strip()
        year = _integer(year_text)
        if year is None or not 1888 <= year <= 2100:
            year = None
            year_text = ""

        where, params = [], []
        if search:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            where.append("(title LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\')")
            params.extend((f"%{escaped}%", f"%{escaped}%"))
        if genre:
            where.append("genres LIKE ?")
            params.append(f"%{genre}%")
        if media_type:
            where.append("media_type = ?")
            params.append(media_type)
        if year is not None:
            where.append("release_year = ?")
            params.append(year)
        clause = f"WHERE {' AND '.join(where)}" if where else ""

        with closing(sqlite3.connect(app.config["DATABASE"])) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute(f"SELECT COUNT(*) FROM titles {clause}", params).fetchone()[0]
            stats = conn.execute("""SELECT COUNT(*) AS titles,
                ROUND(AVG(imdb_score), 1) AS average_score,
                COUNT(DISTINCT release_year) AS years
                FROM titles""").fetchone()
            pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
            try:
                page = max(1, int(request.args.get("page", "1")))
            except ValueError:
                page = 1
            page = min(page, pages)
            offset = (page - 1) * PAGE_SIZE
            titles = conn.execute(f"""SELECT id, title, media_type, description, release_year,
                age_certification, runtime, genres, imdb_score, tmdb_score, seasons
                FROM titles {clause}
                ORDER BY imdb_score IS NULL, imdb_score DESC, release_year DESC, title COLLATE NOCASE
                LIMIT ? OFFSET ?""", (*params, PAGE_SIZE, offset)).fetchall()

        return render_template(
            "index.html", titles=titles, stats=stats, search=search, genre=genre,
            media_type=media_type, year=year_text, page=page, pages=pages,
            total=total, page_size=PAGE_SIZE,
        )

    return app


app = create_app()

if __name__ == "__main__":
    import os

    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
