import os
import mysql.connector
import pandas as pd
import math

# Helper functions to safely parse values and handle NaN
def safe_int(val):
    try:
        if val is None:
            return None
        if isinstance(val, float) and math.isnan(val):
            return None
        return int(val)
    except Exception:
        return None

def safe_float(val):
    try:
        if val is None:
            return None
        if isinstance(val, float) and math.isnan(val):
            return None
        return float(val)
    except Exception:
        return None

def clean_val(val):
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    if isinstance(val, str) and val.lower() == 'nan':
        return None
    return val

# Connect to MySQL database
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password=os.getenv("MYSQL_PASSWORD", ""),
    database="cinerate"
)
cursor = db.cursor()

# Import titles.csv into `titles` table
print("Importing titles...")

titles_df = pd.read_csv("data/titles.csv", encoding='latin1')

for _, row in titles_df.iterrows():
    params = (
        clean_val(row['id']),
        clean_val(row['title']),
        clean_val(row['type']),
        clean_val(row['description']),
        safe_int(row['release_year']),
        clean_val(row['age_certification']),
        safe_int(row['runtime']),
        clean_val(row['genres']),
        clean_val(row['production_countries']),
        safe_int(row['seasons']),
        clean_val(row['imdb_id']),
        safe_float(row['imdb_score']),
        safe_int(row['imdb_votes']),
        safe_float(row['tmdb_popularity']),
        safe_float(row['tmdb_score'])
    )

    try:
        cursor.execute("""
            INSERT INTO titles (
                id, title, type, description, release_year, age_certification, runtime, genres, production_countries,
                seasons, imdb_id, imdb_score, imdb_votes, tmdb_popularity, tmdb_score
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                title = VALUES(title),
                type = VALUES(type),
                description = VALUES(description),
                release_year = VALUES(release_year),
                age_certification = VALUES(age_certification),
                runtime = VALUES(runtime),
                genres = VALUES(genres),
                production_countries = VALUES(production_countries),
                seasons = VALUES(seasons),
                imdb_id = VALUES(imdb_id),
                imdb_score = VALUES(imdb_score),
                imdb_votes = VALUES(imdb_votes),
                tmdb_popularity = VALUES(tmdb_popularity),
                tmdb_score = VALUES(tmdb_score)
        """, params)
    except Exception as e:
        print(f"Error inserting row with id {row['id']}: {e}")

db.commit()

# Import credits.csv into `credits` table
print("Importing credits...")

credits_df = pd.read_csv("data/credits.csv", encoding='latin1')

for _, row in credits_df.iterrows():
    params = (
        safe_int(row['person_id']),
        clean_val(row['id']),
        clean_val(row['name']),
        clean_val(row['charactername']),
        clean_val(row['role'])
    )

    try:
        cursor.execute("""
            INSERT INTO credits (person_id, id, name, charactername, role)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                charactername = VALUES(charactername),
                role = VALUES(role)
        """, params)
    except Exception as e:
        print(f"Error inserting credit row with id {row['id']}: {e}")
        

db.commit()

cursor.close()
db.close()

import re

def parse_description(desc):
    result = {
        "year": "Unknown",
        "duration": "Unknown",
        "genre": "Unknown",
        "rating": "Unknown",
    }
    if not desc:
        return result

    year_match = re.search(r'Year:\s*([^,]+)', desc)
    genre_match = re.search(r'Genre:\s*([^,]+)', desc)
    rating_match = re.search(r'Rating:\s*([^,]+)', desc)
    duration_match = re.search(r'Duration:\s*([^,]+)', desc)

    if year_match:
        result['year'] = year_match.group(1).strip()
    if genre_match:
        result['genre'] = genre_match.group(1).strip()
    if rating_match:
        result['rating'] = rating_match.group(1).strip()
    if duration_match:
        result['duration'] = duration_match.group(1).strip()

    return result


print("✅ All data imported successfully.")
