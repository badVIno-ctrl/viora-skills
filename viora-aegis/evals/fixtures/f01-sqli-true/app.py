"""Fixture f01: SQL built by string concatenation, reaching cursor.execute.

Positive fixture. The plan text for this repo must call the query a finding:
the value arrives from the request and lands in the SQL string itself.
"""
import sqlite3
from flask import Flask, request

app = Flask(__name__)


@app.route("/users")
def find_user():
    name = request.args.get("name")
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    query = "SELECT id, email FROM users WHERE name = %s" % name
    cursor.execute(query)
    return {"rows": cursor.fetchall()}
