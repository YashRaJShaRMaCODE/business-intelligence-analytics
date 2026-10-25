import csv
import tempfile
import unittest
from pathlib import Path

from app import create_app


class CatalogTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[1] / "instance" / "test-tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        root = Path(self.temp.name)
        self.database = root / "catalog.sqlite3"
        self.titles = root / "titles.csv"
        fields = ["id", "title", "type", "description", "release_year", "age_certification",
                  "runtime", "genres", "production_countries", "seasons", "imdb_score", "tmdb_score"]
        rows = [{
            "id": "movie-1", "title": "Sea of Stories", "type": "MOVIE", "description": "A comedy by the sea",
            "release_year": "2020", "age_certification": "PG-13", "runtime": "98", "genres": "['comedy']",
            "production_countries": "['US']", "seasons": "", "imdb_score": "8.2", "tmdb_score": "7.8",
        }, {
            "id": "show-1", "title": "Sea Archive", "type": "SHOW", "description": "A documentary series",
            "release_year": "2020", "age_certification": "TV-14", "runtime": "42", "genres": "['documentation']",
            "production_countries": "['GB']", "seasons": "2", "imdb_score": "7.1", "tmdb_score": "7.0",
        }, {
            "id": "xss-1", "title": "<script>alert(1)</script>", "type": "MOVIE", "description": "A drama",
            "release_year": "2019", "age_certification": "R", "runtime": "90", "genres": "['drama']",
            "production_countries": "['CA']", "seasons": "", "imdb_score": "", "tmdb_score": "",
        }]
        for index in range(27):
            rows.append({**rows[0], "id": f"extra-{index}", "title": f"Extra Title {index}", "release_year": "2001"})
        with self.titles.open("w", encoding="latin1", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        self.app = create_app({
            "TESTING": True,
            "DATABASE": str(self.database),
            "TITLES_CSV": str(self.titles),
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def test_catalog_loads_and_shows_overview(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<strong>30</strong><span>titles indexed</span>", response.data)
        self.assertIn(b"Sea of Stories", response.data)

    def test_filters_are_combined_and_parameterized(self):
        response = self.client.get("/?search=sea&type=show&year=2020&genre=documentation")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Sea Archive", response.data)
        self.assertNotIn(b"Sea of Stories", response.data)
        injection = self.client.get("/?search=%25%27%20OR%201%3D1%20--")
        self.assertIn(b"No titles match", injection.data)

    def test_pagination_is_bounded_and_keeps_filters(self):
        response = self.client.get("/?type=movie&page=999")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Page 2 of 2", response.data)
        self.assertIn(b'type=MOVIE', response.data)

    def test_template_escapes_catalog_text_and_sets_security_headers(self):
        response = self.client.get("/?search=script")
        self.assertIn(b"&lt;script&gt;alert(1)&lt;/script&gt;", response.data)
        self.assertNotIn(b"<script>alert(1)</script>", response.data)
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])


if __name__ == "__main__":
    unittest.main()
