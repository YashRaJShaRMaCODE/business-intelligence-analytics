import csv
import io
import tempfile
import unittest
from xml.etree import ElementTree
from pathlib import Path
from unittest.mock import patch

from app import _clean_row, _profile, create_app


class QualityLabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.titles = Path(self.temp.name) / "titles.csv"
        self.fields = [
            "id", "title", "type", "description", "release_year", "age_certification",
            "runtime", "genres", "production_countries", "seasons", "imdb_id",
            "imdb_score", "imdb_votes", "tmdb_popularity", "tmdb_score",
        ]
        self.rows = [
            {"id": "one", "title": "Sea of Stories", "type": "MOVIE", "release_year": "2020", "genres": "['Comedy', 'Drama']", "imdb_score": "8.2"},
            {"id": "two", "title": "Sea Archive", "type": "SHOW", "release_year": "2020", "genres": "['documentation']", "seasons": "2", "imdb_score": "7.1"},
            {"id": "three", "title": "Sea of Stories", "type": "MOVIE", "release_year": "2020", "genres": "['Comedy']", "imdb_score": ""},
            {"id": "four", "title": "", "type": "MOVIE", "release_year": "bad-year", "imdb_score": "bad"},
            {"id": "five", "title": "=2+2", "type": "MOVIE", "release_year": "2022", "genres": "not a list", "imdb_score": "6", "tmdb_score": "11.2"},
        ]
        with self.titles.open("w", encoding="latin1", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=self.fields)
            writer.writeheader()
            writer.writerows(self.rows)
        self.app = create_app({"TESTING": True, "TITLES_CSV": str(self.titles)})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def test_dashboard_reports_quality_signals_and_sets_security_headers(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Catalog Quality Lab", response.data)
        self.assertIn(b'rel="canonical" href="https://catalog-quality-lab.vercel.app/"', response.data)
        self.assertIn(b'property="og:type" content="website"', response.data)
        self.assertIn(b"4 titled rows", response.data)
        self.assertIn(b"1 blank title", response.data)
        self.assertIn(b"1 possible duplicate keys", response.data)
        self.assertIn(b"Most tagged genres", response.data)
        self.assertNotIn(b"style=", response.data)
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
        self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])
        self.assertIn("object-src 'none'", response.headers["Content-Security-Policy"])
        self.assertEqual(response.headers["Permissions-Policy"], "camera=(), microphone=(), geolocation=(), usb=()")

    def test_robots_and_sitemap_point_to_the_canonical_dashboard(self):
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertIn(b"Sitemap: https://catalog-quality-lab.vercel.app/sitemap.xml", robots.data)
        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        root = ElementTree.fromstring(sitemap.data)
        self.assertEqual(root[0][0].text, "https://catalog-quality-lab.vercel.app/")

    def test_clean_download_normalizes_fields_and_excludes_blank_title(self):
        response = self.client.get("/download/clean.csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertIn("text/csv", response.headers["Content-Type"])
        rows = list(csv.DictReader(io.StringIO(response.data.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["genres"], "comedy; drama")
        self.assertEqual(rows[-1]["title"], "'=2+2")
        self.assertEqual(rows[0]["imdb_score"], "8.2")

    def test_clean_export_escapes_formula_prefixes_in_ids_and_types(self):
        row = self.rows[0] | {"id": "=HYPERLINK(\"https://bad.example\")", "type": "+cmd|calc"}
        cleaned = _clean_row(row)
        self.assertEqual(cleaned["id"], "'=HYPERLINK(\"https://bad.example\")")
        self.assertEqual(cleaned["type"], "'+CMD|CALC")

    def test_health_route_reports_loaded_snapshot(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"records": 5, "status": "ok"})

    def test_vercel_uses_public_asset_paths_without_flask_static_route(self):
        with patch.dict("os.environ", {"VERCEL": "1"}):
            app = create_app({"TESTING": True, "TITLES_CSV": str(self.titles)})
        response = app.test_client().get("/")
        endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'href="/static/styles.css"', response.data)
        self.assertNotIn("static", endpoints)

    def test_review_queue_filters_and_exports_matching_rows(self):
        self.rows[2]["id"] = "one"
        with self.titles.open("w", encoding="latin1", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=self.fields)
            writer.writeheader()
            writer.writerows(self.rows)
        self.app = create_app({"TESTING": True, "TITLES_CSV": str(self.titles)})
        self.client = self.app.test_client()

        page = self.client.get("/?q=Sea%20of%20Stories&flag=possible_duplicate")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"2 matching records", page.data)
        self.assertIn(b"Possible duplicate key", page.data)
        self.assertIn(b"Source record", page.data)
        self.assertNotIn(b"Sea Archive", page.data)

        export = self.client.get("/download/review.csv?flag=repeated_id")
        rows = list(csv.DictReader(io.StringIO(export.data.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 2)
        self.assertTrue(all("Repeated source ID" in row["review_flags"] for row in rows))
        self.assertEqual([row["source_record"] for row in rows], ["1", "3"])

    def test_review_queue_handles_no_matches_and_invalid_filters(self):
        empty = self.client.get("/?q=not-a-real-title&flag=invalid_score")
        self.assertIn(b"No flagged records match those filters", empty.data)
        safe = self.client.get("/?flag=unknown")
        self.assertEqual(safe.status_code, 200)
        self.assertIn(b"All flags", safe.data)

    def test_review_queue_flags_malformed_years_and_rating_ranges(self):
        year = self.client.get("/?flag=invalid_year")
        self.assertIn(b"Invalid release year", year.data)
        score = self.client.get("/?flag=invalid_score")
        self.assertIn(b"Invalid imdb score", score.data)
        self.assertIn(b"Invalid tmdb score", score.data)

    def test_blank_source_ids_are_not_counted_as_repeated_ids(self):
        self.assertEqual(_profile([{"id": "", "title": "One"}, {"id": "", "title": "Two"}])["duplicate_ids"], 0)

    def test_header_only_catalog_renders_empty_metrics_without_dividing_by_zero(self):
        with self.titles.open("w", encoding="latin1", newline="") as file:
            csv.DictWriter(file, fieldnames=self.fields).writeheader()
        app = create_app({"TESTING": True, "TITLES_CSV": str(self.titles)})

        response = app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No source records to measure", response.data)
        self.assertIn(b"No source rows to classify yet", response.data)
        self.assertIn(b"No source rows are available to review", response.data)
        self.assertIn("—".encode(), response.data)


if __name__ == "__main__":
    unittest.main()
