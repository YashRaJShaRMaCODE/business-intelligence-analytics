import os
from flask import Flask, render_template, request
import mysql.connector

app = Flask(__name__)

# Database connection
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password=os.getenv("MYSQL_PASSWORD", ""),
        database="cinerate"
    )

@app.route('/', methods=['GET'])
def index():
    search = request.args.get('search', '')
    genre = request.args.get('genre', '')
    year = request.args.get('year', '')

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    query = "SELECT * FROM movies WHERE 1=1"
    params = []

    if search:
        query += " AND (title LIKE %s OR description LIKE %s)"
        term = f"%{search}%"
        params.extend([term, term])

    if genre:
        query += " AND description LIKE %s"
        params.append(f"%Genre: {genre}%")

    if year:
        query += " AND description LIKE %s"
        params.append(f"%Year: {year}%")

    cursor.execute(query, params)
    movies = cursor.fetchall()
    db.close()

    return render_template('index.html', movies=movies, search=search, genre=genre, year=year)

if __name__ == '__main__':
    app.run(debug=True)
