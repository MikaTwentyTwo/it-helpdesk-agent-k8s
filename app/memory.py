import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "memory.db"


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            session_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    return db


def read_history(session_id: str) -> list[dict]:
    db = connect()
    try:
        rows = db.execute(
            """
            SELECT question, answer FROM messages
            WHERE session_id = ?
            ORDER BY id DESC LIMIT 4
            """,
            (session_id,),
        ).fetchall()
        return [
            {"question": question, "answer": answer}
            for question, answer in reversed(rows)
        ]
    finally:
        db.close()


def save_turn(session_id: str, question: str, answer: str):
    db = connect()
    try:
        db.execute(
            """
            INSERT INTO messages(session_id, question, answer)
            VALUES (?, ?, ?)
            """,
            (session_id, question, answer),
        )
        db.commit()
    finally:
        db.close()


def connect_solutions():
    db = connect()
    db.execute("""
        CREATE TABLE IF NOT EXISTS confirmed_solutions (
            id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            problem TEXT NOT NULL,
            solution TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    return db


def save_confirmed_solution(
    user_id: str,
    problem: str,
    solution: str,
    *,
    confirmed: bool,
) -> int:
    if confirmed is not True:
        raise ValueError("Explicit confirmation is required")
    if not all(value.strip() for value in [user_id, problem, solution]):
        raise ValueError("Fields must not be empty")

    db = connect_solutions()
    try:
        cursor = db.execute(
            """
            INSERT INTO confirmed_solutions(user_id, problem, solution)
            VALUES (?, ?, ?)
            """,
            (user_id, problem, solution),
        )
        db.commit()
        return cursor.lastrowid
    finally:
        db.close()


def read_solutions(user_id: str) -> list[dict]:
    db = connect_solutions()
    try:
        rows = db.execute(
            """
            SELECT id, problem, solution
            FROM confirmed_solutions
            WHERE user_id = ?
            ORDER BY id DESC LIMIT 3
            """,
            (user_id,),
        ).fetchall()
        return [
            {"id": row[0], "problem": row[1], "solution": row[2]}
            for row in rows
        ]
    finally:
        db.close()
