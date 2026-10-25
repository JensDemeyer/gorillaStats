import sqlite3
from datetime import date
from typing import Optional
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI()

DB_FILE = "gym.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            routine TEXT NOT NULL,
            name TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            exercise_id INTEGER NOT NULL,
            set_nr INTEGER NOT NULL,
            weight REAL NOT NULL,
            reps INTEGER NOT NULL,
            notes TEXT,
            FOREIGN KEY (exercise_id) REFERENCES exercises (id)
        )
    """)
    cursor.execute("SELECT COUNT(*) FROM exercises")
    if cursor.fetchone()[0] == 0:
        default_exercises = [
            ("Push", "Incline Bench Press (Barbell)"),
            ("Push", "Chest Press (Machine)"),
            ("Push", "Butterfly (Pec Deck)"),
            ("Push", "Decline Bench Press (Barbell)"),
            ("Push", "Lateral Raise (Cable)"),
            ("Push", "Overhead Triceps Extension (Cable)"),
            ("Push", "Triceps Rope Pushdown"),
            ("Pull", "Lat Pulldown (Cable)"),
            ("Pull", "Bent Over Row (Barbell)"),
            ("Pull", "Seated Cable Row - Bar Grip"),
            ("Pull", "Rear Delt Reverse Fly (Machine)"),
            ("Pull", "Face Pull"),
            ("Pull", "Bicep Curl (Cable)"),
            ("Pull", "Reverse Curl (Cable)"),
            ("Pull", "Seated Wrist Curl (Barbell)"),
            ("Pull", "Hammer Curl (Dumbbell)"),
            ("Legs", "Squat (Barbell)"),
            ("Legs", "Romanian Deadlift (Barbell)"),
            ("Legs", "Leg Extension (Machine)"),
            ("Legs", "Lying Leg Curl (Machine)"),
            ("Legs", "Standing Calf Raise (Machine)")
        ]
        cursor.executemany("INSERT INTO exercises (routine, name) VALUES (?, ?)", default_exercises)
    conn.commit()
    conn.close()

init_db()

class LogEntry(BaseModel):
    exercise_id: int
    set_nr: int
    weight: float
    reps: int
    notes: Optional[str] = ""
    log_date: Optional[str] = None

@app.get("/api/routines")
def get_routines():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, routine, name FROM exercises ORDER BY routine, id")
    rows = cursor.fetchall()
    conn.close()
    
    routines = {}
    for r in rows:
        routines.setdefault(r["routine"], []).append({"id": r["id"], "name": r["name"]})
    return routines

@app.post("/api/logs")
def save_log(entry: LogEntry):
    entry_date = entry.log_date or date.today().isoformat()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO logs (date, exercise_id, set_nr, weight, reps, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (entry_date, entry.exercise_id, entry.set_nr, entry.weight, entry.reps, entry.notes)
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/api/progress/{exercise_id}")
def get_progress(exercise_id: int):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date, MAX(weight) as max_weight, SUM(weight * reps) as total_volume
        FROM logs
        WHERE exercise_id = ?
        GROUP BY date
        ORDER BY date ASC
    """, (exercise_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_index():
    return FileResponse("static/index.html")