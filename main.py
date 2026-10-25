"""
GorillaStats — FastAPI backend v2.0
Optimised for Raspberry Pi Zero 2 W (512 MB RAM).
Pure sqlite3, no heavy ORM.
"""

import csv
import io
import os
import sqlite3
from datetime import date, timedelta
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DB_FILE = "gym.db"
MEDIA_DIR = os.path.join("static", "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL mode: safe for concurrent reads, low RAM overhead on Pi Zero
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS exercises (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            routine     TEXT NOT NULL,
            name        TEXT NOT NULL,
            media_url   TEXT,
            notes       TEXT
        );

        CREATE TABLE IF NOT EXISTS logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            exercise_id INTEGER NOT NULL REFERENCES exercises(id),
            set_nr      INTEGER NOT NULL,
            weight      REAL NOT NULL,
            reps        INTEGER NOT NULL,
            is_pr       INTEGER DEFAULT 0,
            notes       TEXT
        );

        CREATE TABLE IF NOT EXISTS cardio_logs (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            date             TEXT NOT NULL,
            type             TEXT NOT NULL,
            duration_minutes REAL NOT NULL,
            distance_km      REAL,
            calories         INTEGER,
            notes            TEXT
        );

        CREATE TABLE IF NOT EXISTS bodyweight_logs (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            date           TEXT NOT NULL UNIQUE,
            weight_kg      REAL NOT NULL,
            body_fat_pct   REAL,
            muscle_mass_kg REAL,
            source         TEXT DEFAULT 'manual'
        );
    """)

    # Seed default exercises once
    cur.execute("SELECT COUNT(*) FROM exercises")
    if cur.fetchone()[0] == 0:
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
            ("Legs", "Standing Calf Raise (Machine)"),
        ]
        cur.executemany(
            "INSERT INTO exercises (routine, name) VALUES (?, ?)",
            default_exercises,
        )

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class LogEntry(BaseModel):
    exercise_id: int
    set_nr: int
    weight: float
    reps: int
    notes: Optional[str] = ""
    log_date: Optional[str] = None


class ExerciseCreate(BaseModel):
    routine: str
    name: str
    notes: Optional[str] = None


class CardioEntry(BaseModel):
    type: str
    duration_minutes: float
    distance_km: Optional[float] = None
    calories: Optional[int] = None
    notes: Optional[str] = None
    log_date: Optional[str] = None


class BodyweightEntry(BaseModel):
    weight_kg: float
    body_fat_pct: Optional[float] = None
    muscle_mass_kg: Optional[float] = None
    log_date: Optional[str] = None


# ---------------------------------------------------------------------------
# PR helpers
# ---------------------------------------------------------------------------

def epley_e1rm(weight: float, reps: int) -> float:
    """Epley formula: estimated 1-rep max."""
    if reps == 1:
        return weight
    return weight * (1 + reps / 30)


def check_pr(conn: sqlite3.Connection, exercise_id: int, weight: float, reps: int) -> bool:
    """Returns True when this set beats any historical best (weight OR e1RM)."""
    cur = conn.cursor()
    cur.execute(
        "SELECT MAX(weight) FROM logs WHERE exercise_id = ?",
        (exercise_id,),
    )
    row = cur.fetchone()
    best_weight = row[0] if row[0] is not None else 0

    cur.execute(
        "SELECT weight, reps FROM logs WHERE exercise_id = ?",
        (exercise_id,),
    )
    rows = cur.fetchall()
    best_e1rm = max(
        (epley_e1rm(r["weight"], r["reps"]) for r in rows),
        default=0,
    )

    new_e1rm = epley_e1rm(weight, reps)
    return weight > best_weight or new_e1rm > best_e1rm


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="GorillaStats", version="2.0.0")
init_db()


# --- Exercises ---

@app.get("/api/routines")
def get_routines():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, routine, name, media_url, notes FROM exercises ORDER BY routine, id"
    )
    rows = cur.fetchall()
    conn.close()
    routines: dict = {}
    for r in rows:
        routines.setdefault(r["routine"], []).append(dict(r))
    return routines


@app.post("/api/exercises", status_code=201)
def add_exercise(body: ExerciseCreate):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO exercises (routine, name, notes) VALUES (?, ?, ?)",
        (body.routine.strip(), body.name.strip(), body.notes),
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": new_id, "routine": body.routine, "name": body.name}


# --- Logs ---

@app.post("/api/logs")
def save_log(entry: LogEntry):
    entry_date = entry.log_date or date.today().isoformat()
    conn = get_conn()

    is_pr = 0
    if entry.weight and entry.reps:
        is_pr = 1 if check_pr(conn, entry.exercise_id, entry.weight, entry.reps) else 0

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO logs (date, exercise_id, set_nr, weight, reps, is_pr, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (entry_date, entry.exercise_id, entry.set_nr, entry.weight, entry.reps, is_pr, entry.notes or ""),
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "is_pr": bool(is_pr)}


@app.get("/api/logs/previous/{exercise_id}")
def get_previous_session(exercise_id: int):
    """Return sets from the most recent past training session for this exercise."""
    conn = get_conn()
    cur = conn.cursor()
    today = date.today().isoformat()
    cur.execute(
        "SELECT date FROM logs WHERE exercise_id = ? AND date < ? ORDER BY date DESC LIMIT 1",
        (exercise_id, today),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return []
    last_date = row["date"]
    cur.execute(
        "SELECT set_nr, weight, reps, notes FROM logs WHERE exercise_id = ? AND date = ? ORDER BY set_nr",
        (exercise_id, last_date),
    )
    sets = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"date": last_date, "sets": sets}


@app.get("/api/logs/today")
def get_today_logs():
    today = date.today().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT l.id, l.date, l.exercise_id, e.name AS exercise_name,
                  l.set_nr, l.weight, l.reps, l.is_pr, l.notes
           FROM logs l JOIN exercises e ON e.id = l.exercise_id
           WHERE l.date = ? ORDER BY l.id""",
        (today,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.delete("/api/logs/{log_id}")
def delete_log(log_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM logs WHERE id = ?", (log_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}


@app.get("/api/progress/{exercise_id}")
def get_progress(exercise_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT date,
                  MAX(weight)                        AS max_weight,
                  SUM(weight * reps)                 AS total_volume,
                  MAX(weight * (1 + reps / 30.0))   AS best_e1rm
           FROM logs WHERE exercise_id = ?
           GROUP BY date ORDER BY date ASC""",
        (exercise_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# --- Dashboard stats ---

@app.get("/api/stats")
def get_stats():
    conn = get_conn()
    cur = conn.cursor()
    today = date.today().isoformat()

    cur.execute("SELECT COALESCE(SUM(weight * reps), 0) FROM logs WHERE date = ?", (today,))
    tonnage_today = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(weight * reps), 0) FROM logs")
    total_volume = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT date) FROM logs")
    total_sessions = cur.fetchone()[0]

    # Streak: consecutive days backwards from today
    cur.execute("SELECT DISTINCT date FROM logs ORDER BY date DESC")
    dates = [r[0] for r in cur.fetchall()]
    streak = 0
    check = date.today()
    for d in dates:
        if d == check.isoformat():
            streak += 1
            check -= timedelta(days=1)
        elif d < check.isoformat():
            break

    cur.execute(
        """SELECT l.date, e.name, l.weight, l.reps
           FROM logs l JOIN exercises e ON e.id = l.exercise_id
           WHERE l.is_pr = 1
           ORDER BY l.date DESC, l.id DESC LIMIT 10"""
    )
    recent_prs = [dict(r) for r in cur.fetchall()]

    conn.close()
    return {
        "tonnage_today": round(tonnage_today, 1),
        "total_volume": round(total_volume, 1),
        "total_sessions": total_sessions,
        "streak": streak,
        "recent_prs": recent_prs,
    }


# --- Cardio ---

@app.post("/api/cardio", status_code=201)
def save_cardio(entry: CardioEntry):
    entry_date = entry.log_date or date.today().isoformat()
    conn = get_conn()
    conn.execute(
        "INSERT INTO cardio_logs (date, type, duration_minutes, distance_km, calories, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (entry_date, entry.type, entry.duration_minutes, entry.distance_km, entry.calories, entry.notes or ""),
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.get("/api/cardio")
def get_cardio(limit: int = 30):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM cardio_logs ORDER BY date DESC, id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# --- Bodyweight ---

@app.post("/api/bodyweight", status_code=201)
def save_bodyweight(entry: BodyweightEntry):
    entry_date = entry.log_date or date.today().isoformat()
    conn = get_conn()
    conn.execute(
        """INSERT INTO bodyweight_logs (date, weight_kg, body_fat_pct, muscle_mass_kg, source)
           VALUES (?, ?, ?, ?, 'manual')
           ON CONFLICT(date) DO UPDATE SET
               weight_kg = excluded.weight_kg,
               body_fat_pct = excluded.body_fat_pct,
               muscle_mass_kg = excluded.muscle_mass_kg,
               source = 'manual'""",
        (entry_date, entry.weight_kg, entry.body_fat_pct, entry.muscle_mass_kg),
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.get("/api/bodyweight")
def get_bodyweight(limit: int = 90):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM bodyweight_logs ORDER BY date ASC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.post("/api/bodyweight/import-csv")
async def import_fitdays_csv(file: UploadFile = File(...)):
    """Imports a Fitdays CSV export. Handles various column name formats."""
    content = await file.read()
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    inserted = 0
    skipped = 0
    conn = get_conn()

    for row in reader:
        def pick(keys):
            for k in keys:
                if k in row and row[k].strip():
                    return row[k].strip()
            return None

        raw_date = pick(["Date", "date", "日期"])
        raw_weight = pick(["Weight(kg)", "weight_kg", "Weight", "体重(kg)", "体重"])
        raw_fat = pick(["Body Fat(%)", "body_fat_pct", "Body Fat", "体脂率(%)"])
        raw_muscle = pick(["Muscle Mass(kg)", "muscle_mass_kg", "Skeletal Muscle Mass(kg)"])

        if not raw_date or not raw_weight:
            skipped += 1
            continue

        try:
            entry_date = raw_date.replace("/", "-")
            weight_kg = float(raw_weight)
            body_fat = float(raw_fat) if raw_fat else None
            muscle = float(raw_muscle) if raw_muscle else None
        except (ValueError, TypeError):
            skipped += 1
            continue

        conn.execute(
            """INSERT INTO bodyweight_logs (date, weight_kg, body_fat_pct, muscle_mass_kg, source)
               VALUES (?, ?, ?, ?, 'fitdays_csv')
               ON CONFLICT(date) DO UPDATE SET
                   weight_kg = excluded.weight_kg,
                   body_fat_pct = excluded.body_fat_pct,
                   muscle_mass_kg = excluded.muscle_mass_kg,
                   source = 'fitdays_csv'""",
            (entry_date, weight_kg, body_fat, muscle),
        )
        inserted += 1

    conn.commit()
    conn.close()
    return {"imported": inserted, "skipped": skipped}


# --- Media upload ---

@app.post("/api/exercises/{exercise_id}/media")
async def upload_media(exercise_id: int, file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    allowed = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    if ext not in allowed:
        raise HTTPException(400, "Unsupported file type. Use jpg, png, gif, or webp.")

    filename = f"ex_{exercise_id}{ext}"
    dest = os.path.join(MEDIA_DIR, filename)
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)

    media_url = f"/static/media/{filename}"
    conn = get_conn()
    conn.execute("UPDATE exercises SET media_url = ? WHERE id = ?", (media_url, exercise_id))
    conn.commit()
    conn.close()
    return {"media_url": media_url}


# --- Static files & SPA ---

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def serve_index():
    return FileResponse("static/index.html")