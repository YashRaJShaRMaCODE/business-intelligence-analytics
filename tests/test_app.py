import csv
import io
import tempfile
import unittest
from pathlib import Path

from app import create_app


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
            {"id": "four", "title": "", "type": "MOVIE", "release_year": "2019", "imdb_score": "bad"},
            {"id": "five", "title": "=2+2", "type": "MOVIE", "release_year": "2022", "genres": "not a list", "imdb_score": "6"},
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
        self.assertIn(b"4 titled rows", response.data)
        self.assertIn(b"1 blank title", response.data)
        self.assertIn(b"1 possible duplicate keys", response.data)
        self.assertIn(b"Most tagged genres", response.data)
        self.assertNotIn(b"style=", response.data)
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])

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

    def test_health_route_reports_loaded_snapshot(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"records": 5, "status": "ok"})


if __name__ == "__main__":
    unittest.main()
