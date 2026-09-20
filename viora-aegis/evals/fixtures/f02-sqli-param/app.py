"""Fixture f02: the same route, parameterised.

Negative fixture. The scanner may list a lead here — a query string next to a
request value is worth looking at — but the PLAN text must not call it a
finding: the value never reaches the SQL string, only the driver's parameter
slot.
"""
import sqlite3
from flask import Flask, request

app = Flask(__name__)


@app.route("/users")
def find_user():
    name = request.args.get("name")
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, email FROM users WHERE name = ?", (name,))
    return {"rows": cursor.fetchall()}
