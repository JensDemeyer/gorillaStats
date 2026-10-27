"""
GorillaStats — FastAPI backend v2.0
Optimised for Raspberry Pi Zero 2 W (512 MB RAM).
Pure sqlite3, no heavy ORM.
"""

import csv
import io
import json
import math
import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DB_FILE = BASE_DIR / "gym.db"
MEDIA_DIR = STATIC_DIR / "media"
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
            weight      REAL,
            reps        INTEGER,
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

    conn.execute("BEGIN")
    columns = {row["name"] for row in cur.execute("PRAGMA table_info(exercises)")}
    if "active" not in columns:
        cur.execute("ALTER TABLE exercises ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
    if "sort_order" not in columns:
        cur.execute("ALTER TABLE exercises ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")
    log_columns = list(cur.execute("PRAGMA table_info(logs)"))
    if any(row["notnull"] for row in log_columns if row["name"] in ("weight", "reps")):
        cur.execute("""CREATE TABLE logs_optional (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL,
            exercise_id INTEGER NOT NULL REFERENCES exercises(id), set_nr INTEGER NOT NULL,
            weight REAL, reps INTEGER, is_pr INTEGER DEFAULT 0, notes TEXT
        )""")
        cur.execute("INSERT INTO logs_optional SELECT id, date, exercise_id, set_nr, weight, reps, is_pr, notes FROM logs")
        cur.execute("DROP TABLE logs")
        cur.execute("ALTER TABLE logs_optional RENAME TO logs")
    if "is_estimated" not in {row["name"] for row in cur.execute("PRAGMA table_info(logs)")}:
        cur.execute("ALTER TABLE logs ADD COLUMN is_estimated INTEGER NOT NULL DEFAULT 0")
    if "metrics_json" not in {row["name"] for row in cur.execute("PRAGMA table_info(bodyweight_logs)")}:
        cur.execute("ALTER TABLE bodyweight_logs ADD COLUMN metrics_json TEXT NOT NULL DEFAULT '{}'")

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
    set_nr: int = Field(ge=1)
    weight: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    reps: Optional[int] = Field(default=None, ge=1)
    notes: Optional[str] = ""
    log_date: Optional[date] = None


class LogUpdate(BaseModel):
    weight: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    reps: Optional[int] = Field(default=None, ge=1)
    notes: Optional[str] = ""
    exercise_id: Optional[int] = None
    log_date: Optional[date] = None
    is_estimated: Optional[bool] = None


class WorkoutExercise(BaseModel):
    exercise_id: int
    sets: int = Field(default=3, ge=1, le=20)
    weight: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    reps: Optional[int] = Field(default=None, ge=1)
    is_estimated: bool = True


class WorkoutEntry(BaseModel):
    log_date: date
    exercises: list[WorkoutExercise] = Field(min_length=1, max_length=50)


class RoutineExercise(BaseModel):
    id: Optional[int] = None
    name: str = Field(min_length=1)


class RoutineUpdate(BaseModel):
    name: str = Field(min_length=1)
    exercises: list[RoutineExercise] = Field(min_length=1)


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
        "SELECT weight, reps FROM logs WHERE exercise_id = ? AND weight IS NOT NULL AND reps IS NOT NULL",
        (exercise_id,),
    )
    rows = cur.fetchall()
    best_e1rm = max(
        (epley_e1rm(r["weight"], r["reps"]) for r in rows),
        default=0,
    )

    new_e1rm = epley_e1rm(weight, reps)
    return weight > best_weight or new_e1rm > best_e1rm


def refresh_prs(conn: sqlite3.Connection, exercise_id: int):
    best_weight = 0
    best_e1rm = 0
    for row in conn.execute("SELECT * FROM logs WHERE exercise_id = ? ORDER BY date, id", (exercise_id,)).fetchall():
        complete = row["weight"] is not None and row["reps"] is not None and not row["is_estimated"]
        estimated = epley_e1rm(row["weight"], row["reps"]) if complete else 0
        is_pr = complete and (row["weight"] > best_weight or estimated > best_e1rm)
        if row["is_pr"] != int(is_pr):
            conn.execute("UPDATE logs SET is_pr = ? WHERE id = ?", (int(is_pr), row["id"]))
        if complete:
            best_weight = max(best_weight, row["weight"])
            best_e1rm = max(best_e1rm, estimated)


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
        "SELECT id, routine, name, media_url, notes FROM exercises WHERE active = 1 ORDER BY routine, sort_order, id"
    )
    rows = cur.fetchall()
    conn.close()
    routines: dict = {}
    for r in rows:
        routines.setdefault(r["routine"], []).append(dict(r))
    return routines


@app.post("/api/exercises", status_code=201)
def add_exercise(body: ExerciseCreate):
    if not body.routine.strip() or not body.name.strip():
        raise HTTPException(422, "Routine en naam zijn verplicht")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO exercises (routine, name, notes, sort_order) VALUES (?, ?, ?, (SELECT COALESCE(MAX(sort_order), 0) + 1 FROM exercises WHERE routine = ?))",
        (body.routine.strip(), body.name.strip(), body.notes, body.routine.strip()),
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": new_id, "routine": body.routine, "name": body.name}


@app.put("/api/routines/{routine:path}")
def update_routine(routine: str, body: RoutineUpdate):
    name = body.name.strip()
    if not name or any(not item.name.strip() for item in body.exercises):
        raise HTTPException(422, "Namen mogen niet leeg zijn")
    conn = get_conn()
    try:
        with conn:
            existing = {row["id"] for row in conn.execute(
                "SELECT id FROM exercises WHERE routine = ? AND active = 1", (routine,))}
            if not existing:
                raise HTTPException(404, "Schema niet gevonden")
            ids = [item.id for item in body.exercises if item.id is not None]
            if len(ids) != len(set(ids)) or not set(ids).issubset(existing):
                raise HTTPException(422, "Ongeldige oefeningen")
            if name != routine and conn.execute(
                "SELECT 1 FROM exercises WHERE routine = ? AND active = 1", (name,)).fetchone():
                raise HTTPException(409, "Dit schema bestaat al")
            conn.execute("UPDATE exercises SET active = 0 WHERE routine = ? AND active = 1", (routine,))
            for position, item in enumerate(body.exercises):
                if item.id is None:
                    conn.execute("INSERT INTO exercises (routine, name, sort_order) VALUES (?, ?, ?)",
                                 (name, item.name.strip(), position))
                else:
                    conn.execute("UPDATE exercises SET routine = ?, name = ?, sort_order = ?, active = 1 WHERE id = ?",
                                 (name, item.name.strip(), position, item.id))
    finally:
        conn.close()
    return {"status": "ok"}


# --- Logs ---

def workout_suggestions(conn: sqlite3.Connection, log_date: date):
    rows = conn.execute("""
        WITH sessions AS (
            SELECT exercise_id, date, AVG(weight) AS weight, COUNT(*) AS sets,
                   ROW_NUMBER() OVER (PARTITION BY exercise_id ORDER BY date DESC) AS position
            FROM logs WHERE date < ? AND weight IS NOT NULL AND is_estimated = 0
            GROUP BY exercise_id, date
        ), averages AS (
            SELECT exercise_id, ROUND(AVG(weight), 2) AS weight, COUNT(*) AS sessions,
                   MAX(CASE WHEN position = 1 THEN sets END) AS sets
            FROM sessions WHERE position <= 3 GROUP BY exercise_id
        )
        SELECT e.id AS exercise_id, e.name, e.routine, e.active, a.weight,
               COALESCE(a.sessions, 0) AS sessions, COALESCE(a.sets, 3) AS sets
        FROM exercises e LEFT JOIN averages a ON a.exercise_id = e.id
        ORDER BY e.active DESC, e.routine, e.sort_order, e.id
    """, (log_date.isoformat(),)).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/workouts/suggestions")
def get_workout_suggestions(log_date: date):
    conn = get_conn()
    try:
        return workout_suggestions(conn, log_date)
    finally:
        conn.close()


@app.post("/api/workouts", status_code=201)
def save_workout(entry: WorkoutEntry):
    if entry.log_date > date.today():
        raise HTTPException(422, "Kies vandaag of een eerdere datum")
    ids = [exercise.exercise_id for exercise in entry.exercises]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "Kies elke oefening slechts eenmaal")
    conn = get_conn()
    try:
        with conn:
            suggestions = {item["exercise_id"]: item for item in workout_suggestions(conn, entry.log_date)}
            if not set(ids).issubset(suggestions):
                raise HTTPException(404, "Oefening niet gevonden")
            for exercise in entry.exercises:
                weight = suggestions[exercise.exercise_id]["weight"] if exercise.is_estimated else exercise.weight
                estimated = exercise.is_estimated and weight is not None
                last_set = conn.execute(
                    "SELECT COALESCE(MAX(set_nr), 0) FROM logs WHERE date = ? AND exercise_id = ?",
                    (entry.log_date.isoformat(), exercise.exercise_id),
                ).fetchone()[0]
                conn.executemany(
                    "INSERT INTO logs (date, exercise_id, set_nr, weight, reps, is_estimated) VALUES (?, ?, ?, ?, ?, ?)",
                    [(entry.log_date.isoformat(), exercise.exercise_id, last_set + offset + 1,
                      weight, exercise.reps, int(estimated)) for offset in range(exercise.sets)],
                )
                refresh_prs(conn, exercise.exercise_id)
    finally:
        conn.close()
    return {"status": "ok", "sets": sum(exercise.sets for exercise in entry.exercises)}


@app.post("/api/logs")
def save_log(entry: LogEntry):
    entry_date = (entry.log_date or date.today()).isoformat()
    conn = get_conn()
    if not conn.execute("SELECT 1 FROM exercises WHERE id = ?", (entry.exercise_id,)).fetchone():
        conn.close()
        raise HTTPException(404, "Oefening niet gevonden")

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO logs (date, exercise_id, set_nr, weight, reps, is_pr, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (entry_date, entry.exercise_id, entry.set_nr, entry.weight, entry.reps, 0, entry.notes or ""),
    )
    log_id = cur.lastrowid
    refresh_prs(conn, entry.exercise_id)
    is_pr = conn.execute("SELECT is_pr FROM logs WHERE id = ?", (log_id,)).fetchone()[0]
    conn.commit()
    conn.close()
    return {"status": "ok", "id": log_id, "is_pr": bool(is_pr)}


@app.put("/api/logs/{log_id}")
def update_log(log_id: int, entry: LogUpdate):
    conn = get_conn()
    try:
        with conn:
            row = conn.execute("SELECT * FROM logs WHERE id = ?", (log_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Set niet gevonden")
            exercise_id = entry.exercise_id if entry.exercise_id is not None else row["exercise_id"]
            if not conn.execute("SELECT 1 FROM exercises WHERE id = ?", (exercise_id,)).fetchone():
                raise HTTPException(404, "Oefening niet gevonden")
            log_date = entry.log_date.isoformat() if entry.log_date else row["date"]
            if log_date > date.today().isoformat():
                raise HTTPException(422, "Kies vandaag of een eerdere datum")
            set_nr = row["set_nr"]
            if exercise_id != row["exercise_id"] or log_date != row["date"]:
                set_nr = conn.execute(
                    "SELECT COALESCE(MAX(set_nr), 0) + 1 FROM logs WHERE exercise_id = ? AND date = ?",
                    (exercise_id, log_date),
                ).fetchone()[0]
            estimated = row["is_estimated"] if entry.is_estimated is None else int(entry.is_estimated)
            conn.execute("UPDATE logs SET weight = ?, reps = ?, notes = ?, exercise_id = ?, date = ?, set_nr = ?, is_estimated = ? WHERE id = ?",
                         (entry.weight, entry.reps, entry.notes or "", exercise_id, log_date, set_nr, estimated, log_id))
            refresh_prs(conn, row["exercise_id"])
            if exercise_id != row["exercise_id"]:
                refresh_prs(conn, exercise_id)
    finally:
        conn.close()
    return {"status": "ok"}


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
        "SELECT set_nr, weight, reps, notes, is_estimated FROM logs WHERE exercise_id = ? AND date = ? ORDER BY set_nr",
        (exercise_id, last_date),
    )
    sets = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"date": last_date, "sets": sets}


@app.get("/api/logs/today")
def get_today_logs():
    return get_logs()


@app.get("/api/logs")
def get_logs(log_date: Optional[date] = None):
    selected_date = (log_date or date.today()).isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT l.id, l.date, l.exercise_id, e.name AS exercise_name,
                  l.set_nr, l.weight, l.reps, l.is_pr, l.notes, l.is_estimated
           FROM logs l JOIN exercises e ON e.id = l.exercise_id
           WHERE l.date = ? ORDER BY l.id""",
        (selected_date,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.delete("/api/logs/{log_id}")
def delete_log(log_id: int):
    conn = get_conn()
    row = conn.execute("SELECT exercise_id FROM logs WHERE id = ?", (log_id,)).fetchone()
    conn.execute("DELETE FROM logs WHERE id = ?", (log_id,))
    if row:
        refresh_prs(conn, row["exercise_id"])
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

LEVEL_PHASES = (
    ("De Wieg van het Regenwoud", "Beginnersfase", (
        ("Baby Gorillatje", "Moet nog leren kruipen, hangt hulpeloos aan moeders rug en drinkt nog moedermelk."),
        ("Melkmuil Makaak", "Gooit met bananenschillen, durft alleen naar de lichte roze dumbellset te kijken."),
        ("Takjesbuiger", "Probeert zich op te trekken aan lianen; valt er meestal na twee seconden af."),
        ("Gym-Chimpansee", "Maakt vooral veel kabaal bij het dumbellrek, maar tilt nog geen deuk in een pakje boter."),
        ("Palmboom Schudder", "Eerste noob-gains; schudt bomen heen en weer om kokosnoten te laten vallen."),
    )),
    ("De Puber Apen", "De Bouwfase & Eerste Spiergroei", (
        ("Baviaan op Pre-Workout", "Hyperactief, hartslag op 180, stuitert door de jungle op zoek naar zware stenen."),
        ("Bananen-Bulker", "Eet alles wat los en vast zit in het struikgewas; de bulk is officieel begonnen."),
        ("IJzerknagende Oerang-oetan", "Lange armen, perfecte hefboom voor deadlifts, begint langzaam gevaarlijk te worden."),
        ("Jonge Sloper", "Sloopt bamboestengels met blote handen en weigert het squatrek te verlaten."),
        ("Rotsensleper", "Begint rotsblokken van 100 kg door de modder te rollen puur voor het pompgevoel."),
    )),
    ("De Zilverruggelings", "Gevorderde Krachtpatsers", (
        ("Eerstejaars Zilverrug", "De eerste grijze haren verschijnen op de rug; het fysiek begint angstaanjagend te worden."),
        ("Borstkas Trommelaar", "Slaat zo hard op eigen borstkas na een zware set dat de hele vallei trilt."),
        ("Schijven-Stapelaar", "Er passen bijna geen 20kg-plates meer op de barbell; traint met pure oerwoede."),
        ("Mangrove Monster", "Breekt door plateaus heen alsof het rot hout is. Geen spierpijn, alleen honger."),
        ("Territorium Bewaker", "Kijkt andere gymgangers weg bij de bench press met \u00e9\u00e9n doodse gorilla-blik."),
    )),
    ("Opperbeesten", "Zware Gewichten & Elite Tonnage", (
        ("Kong Junior", "Direct nazaat van Skull Island. De apparaten kraken zodra hij erop gaat zitten."),
        ("Gietijzer Vreter", "Verwerkt tonnen gewicht per sessie. Zweet puur vloeibaar testosteron."),
        ("Silverback Berserker", "Gaat in trance voor elke PR-poging; ademt stoom uit en voelt geen vermoeidheid."),
        ("Jungle Dictator", "Heerst over de halterzone. Wat hij vastpakt gaat omhoog, zonder compromis."),
        ("Apex Primate", "Bovenaan de voedselketen van het ecosysteem. Geen natuurlijk roofdier over."),
    )),
    ("Primal Mythologie", "God Tier & Eindbazen", (
        ("Vallei Pletter", "Laat bij elke squat de aarde beven tot in de dichtstbijzijnde nederzetting."),
        ("Oer-Titaan", "Gebouwd uit vulkanisch basalt en pezen van staalkabel. Pure oerkracht."),
        ("King Kong Tier", "Beklimt wolkenkrabbers puur als cardiotraining na een zware beensessie."),
        ("Opperste Territorium Heerser", "Zelfs de jungle buigt voor zijn fysiek; benchmarks en records worden verpulverd."),
        ("Ultra Alfa Gorilla", "De absolute oppergod van testosteron, gietijzer en spiermassa. Onbetwist, ontembaar en onverslaanbaar."),
    )),
)


def get_level_progression(xp: int) -> dict:
    max_level = sum(len(ranks) for _, _, ranks in LEVEL_PHASES)
    level = min(xp // 500 + 1, max_level)
    journey = []
    phase_achievements = []
    current = None
    level_number = 1
    for phase_number, (name, description, ranks) in enumerate(LEVEL_PHASES, start=1):
        start = level_number
        levels = []
        for rank, detail in ranks:
            item = {"level": level_number, "name": rank, "description": detail,
                    "xp_required": (level_number - 1) * 500,
                    "unlocked": level >= level_number, "current": level == level_number}
            levels.append(item)
            if item["current"]:
                current = {"rank": rank, "rank_description": detail, "phase": name, "phase_number": phase_number}
            level_number += 1
        end = level_number - 1
        journey.append({"number": phase_number, "name": name, "description": description,
                        "start_level": start, "end_level": end, "levels": levels,
                        "current": start <= level <= end, "completed": level >= end})
        phase_achievements.append({
            "id": f"phase{phase_number}", "title": name,
            "description": f"Fase {phase_number} voltooid: bereik level {end} ({ranks[-1][0]}).",
            "icon": "crown" if phase_number == len(LEVEL_PHASES) else "medal",
            "progress": min(level, end), "target": end, "unlocked": level >= end,
            "xp": 0, "category": "phase",
        })
    return {"level": level, **current, "max_level": max_level, "is_max_level": level == max_level,
            "level_xp": 500 if level == max_level else xp % 500, "next_level_xp": 500,
            "journey": journey, "phase_achievements": phase_achievements}


def get_rewards(conn: sqlite3.Connection, today: date) -> dict:
    rows = conn.execute(
        """SELECT date, SUM(sets) AS sets, SUM(minutes) AS minutes, MAX(weighed) AS weighed
           FROM (
               SELECT date, COUNT(*) AS sets, 0 AS minutes, 0 AS weighed
               FROM logs WHERE date <= ? GROUP BY date
               UNION ALL
               SELECT date, 0, SUM(duration_minutes), 0
               FROM cardio_logs WHERE date <= ? GROUP BY date
               UNION ALL
               SELECT date, 0, 0, 1 FROM bodyweight_logs WHERE date <= ?
           ) GROUP BY date ORDER BY date""",
        (today.isoformat(),) * 3,
    ).fetchall()
    days = {}
    weeks = {}
    total_xp = 0
    for row in rows:
        try:
            logged = date.fromisoformat(row["date"])
        except ValueError:
            continue
        sets = row["sets"]
        minutes = max(0, row["minutes"])
        active = sets >= 3 or minutes >= 10
        xp = min(sets, 12) * 10 + (40 if sets >= 3 else 0)
        xp += (30 if minutes >= 10 else 0) + (10 if row["weighed"] else 0)
        total_xp += xp
        days[logged] = {"sets": sets, "minutes": minutes, "active": active, "xp": xp}
        monday = logged - timedelta(days=logged.weekday())
        weeks[monday] = weeks.get(monday, 0) + int(active)

    monday = today - timedelta(days=today.weekday())
    week_days = weeks.get(monday, 0)
    completed_weeks = {week for week, count in weeks.items() if count >= 3}
    anchor = monday if monday in completed_weeks else monday - timedelta(weeks=1)
    streak = 0
    while anchor in completed_weeks:
        streak += 1
        anchor -= timedelta(weeks=1)
    best_streak = 0
    running = 0
    previous = None
    for week in sorted(completed_weeks):
        running = running + 1 if previous == week - timedelta(weeks=1) else 1
        best_streak = max(best_streak, running)
        previous = week

    sessions = sum(day["active"] for day in days.values())
    total_sets = sum(day["sets"] for day in days.values())
    cardio_days = sum(day["minutes"] >= 10 for day in days.values())
    weigh_days = conn.execute(
        "SELECT COUNT(*) FROM bodyweight_logs WHERE date <= ?", (today.isoformat(),)
    ).fetchone()[0]
    variety = conn.execute(
        """SELECT COUNT(DISTINCT e.routine) FROM logs l JOIN exercises e ON e.id = l.exercise_id
           WHERE l.date BETWEEN ? AND ?""", (monday.isoformat(), today.isoformat())
    ).fetchone()[0]
    milestones = [
        ("first", "Eerste stap", "1 actieve dag", "flag", sessions, 1, 50),
        ("ten", "In je ritme", "10 actieve dagen", "flame", sessions, 10, 100),
        ("fifty", "Vaste waarde", "50 actieve dagen", "medal", sessions, 50, 200),
        ("hundred", "Honderd keer opdagen", "100 actieve dagen", "crown", sessions, 100, 300),
        ("sets100", "Stevige basis", "100 sets gelogd", "dumbbell", total_sets, 100, 100),
        ("sets500", "IJzersterk", "500 sets gelogd", "dumbbell", total_sets, 500, 200),
        ("sets1500", "Lange adem", "1.500 sets gelogd", "trophy", total_sets, 1500, 300),
        ("cardio1", "In beweging", "1 dag met 10 minuten cardio", "heart", cardio_days, 1, 50),
        ("cardio10", "Conditie opgebouwd", "10 cardiodagen", "heart", cardio_days, 10, 150),
        ("weigh10", "Inzicht telt", "10 wegingen bijgehouden", "chart", weigh_days, 10, 100),
        ("weeks4", "Vier weken sterk", "4 doelweken op rij", "flame", best_streak, 4, 200),
        ("weeks12", "Blijver", "12 doelweken op rij", "crown", best_streak, 12, 400),
    ]
    achievements = [
        {"id": key, "title": title, "description": description, "icon": icon,
         "progress": min(value, target), "target": target, "unlocked": value >= target,
         "xp": bonus}
        for key, title, description, icon, value, target, bonus in milestones
    ]
    total_xp += sum(item["xp"] for item in achievements if item["unlocked"])
    progression = get_level_progression(total_xp)
    achievements.extend(progression.pop("phase_achievements"))
    current = days.get(today, {"sets": 0, "minutes": 0, "active": False, "xp": 0})
    calendar = []
    for offset in range(28):
        logged = today - timedelta(days=27 - offset)
        calendar.append({"date": logged.isoformat(), "active": days.get(logged, {}).get("active", False)})
    return {
        "xp": total_xp, **progression, "today_xp": current["xp"],
        "weekly_streak": streak, "best_weekly_streak": best_streak,
        "weekly_days": week_days, "weekly_target": 3,
        "week": [{"date": (monday + timedelta(days=offset)).isoformat(),
                  "active": days.get(monday + timedelta(days=offset), {}).get("active", False),
                  "today": monday + timedelta(days=offset) == today,
                  "future": monday + timedelta(days=offset) > today} for offset in range(7)],
        "calendar": calendar, "achievements": achievements,
        "quests": [
            {"title": "Vandaag in beweging", "detail": "3 sets of 10 minuten cardio",
             "progress": int(current["active"]), "target": 1},
            {"title": "Je weekdoel", "detail": "3 actieve dagen; rust hoort erbij",
             "progress": min(week_days, 3), "target": 3},
            {"title": "Sterk in balans", "detail": "3 verschillende routines deze week",
             "progress": min(variety, 3), "target": 3},
        ],
    }


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

    rewards = get_rewards(conn, date.today())
    conn.close()
    return {
        "tonnage_today": round(tonnage_today, 1),
        "total_volume": round(total_volume, 1),
        "total_sessions": total_sessions,
        "streak": streak,
        "recent_prs": recent_prs,
        "rewards": rewards,
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
    cur.execute("SELECT * FROM (SELECT * FROM bodyweight_logs ORDER BY date DESC LIMIT ?) ORDER BY date ASC", (max(1, min(limit, 5000)),))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    for row in rows:
        row["metrics"] = json.loads(row.pop("metrics_json"))
        for key in ("weight_kg", "body_fat_pct", "muscle_mass_kg"):
            row["metrics"][key] = {"label": FITDAYS_METRICS[key][0], "unit": FITDAYS_METRICS[key][1], "value": row[key]}
    return rows


FITDAYS_METRICS = {
    "weight_kg": ("Gewicht", "kg", ("Weight", "Weight(kg)", "weight_kg", "Gewicht", "Gewicht(kg)", "体重", "体重(kg)")),
    "bmi": ("BMI", "", ("BMI",)),
    "body_fat_pct": ("Vetpercentage", "%", ("Body Fat", "Body Fat(%)", "body_fat_pct", "Vetpercentage", "体脂率", "体脂率(%)")),
    "subcutaneous_fat_pct": ("Onderhuids vet", "%", ("Subcutaneous fat", "Subcutaneous fat(%)", "Onderhuids vet")),
    "heart_rate": ("Hartslag", "bpm", ("Heart Rate", "Heart Rate(bpm)", "Hartslag")),
    "cardiac_index": ("Cardiale index", "L/min/m²", ("Cardiac Index",)),
    "visceral_fat": ("Visceraal vet", "", ("Visceral Fat", "Visceraal vet")),
    "body_water_pct": ("Lichaamswater", "%", ("Body Water", "Body Water(%)", "Lichaamswater")),
    "skeletal_muscle_pct": ("Skeletspieren", "%", ("Skeletal Muscle", "Skeletal Muscle(%)", "Skeletspieren")),
    "muscle_mass_kg": ("Spiermassa", "kg", ("Muscle Mass", "Muscle Mass(kg)", "muscle_mass_kg", "Spiermassa", "Spiermassa(kg)")),
    "bone_mass_kg": ("Botmassa", "kg", ("Bone Mass", "Bone Mass(kg)", "Botmassa")),
    "protein_pct": ("Eiwitpercentage", "%", ("Protein", "Protein(%)", "Eiwitpercentage")),
    "bmr": ("Basaal metabolisme", "kcal", ("BMR", "BMR(kcal)")),
    "body_age": ("Lichaamsleeftijd", "jaar", ("Body age", "Body Age(years)", "Lichaamsleeftijd")),
}


def fitdays_header(value):
    return re.sub(r"[\W_]+", "", str(value).strip().casefold())


def fitdays_number(value):
    raw = str(value).strip()
    if raw.casefold() in ("", "-", "--", "- -", "n/a", "na", "null", "none"):
        return None
    match = re.fullmatch(r"([+-]?\d+(?:[.,]\d+)?)\s*(?:kg|%|kcal|bpm|years?|jaar|L/min/m²)?", raw, re.IGNORECASE)
    if not match:
        raise ValueError(f"Ongeldige meetwaarde: {raw[:40]}")
    number = float(match[1].replace(",", "."))
    if not math.isfinite(number) or number < 0:
        raise ValueError("Een meetwaarde moet een positief getal zijn.")
    return number


def fitdays_date(value):
    raw = str(value).strip()
    try:
        return datetime.fromisoformat(raw.replace("/", "-")).date().isoformat()
    except ValueError:
        pass
    match = re.fullmatch(r"(?:\d{1,2}:\d{2}(?::\d{2})?\s+)?([A-Za-z]+)\.?\s*(\d{1,2}),\s*(\d{4})", raw)
    if match:
        months = {name: index for index, name in enumerate(
            ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}
        month = months.get(match[1][:3].casefold())
        if month:
            return date(int(match[3]), month, int(match[2])).isoformat()
    for pattern in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M"):
        try:
            return datetime.strptime(raw, pattern).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"Onbekend datumformaat: {raw[:40]}")


def iter_fitdays_rows(content: bytes):
    if content.startswith(b"PK"):
        raise ValueError("Dit bestand is geen tekst-CSV. Exporteer of bewaar het als CSV.")
    encoding = "utf-16" if content.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    try:
        text = content.decode(encoding)
    except UnicodeDecodeError:
        text = content.decode("cp1252")
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    try:
        dialect = csv.Sniffer().sniff(first_line, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    for index, row in enumerate(csv.reader(io.StringIO(text), dialect)):
        if index >= 20000:
            raise ValueError("Maximaal 20.000 rijen per bestand. Exporteer een kortere periode.")
        if any(cell.strip() for cell in row):
            yield row


def parse_fitdays_csv(content: bytes):
    aliases = {fitdays_header(alias): key for key, (_, _, names) in FITDAYS_METRICS.items() for alias in names}
    rows = iter_fitdays_rows(content)
    headers = next(rows, [])
    normalized = [fitdays_header(header) for header in headers]
    date_headers = {fitdays_header(name) for name in ("Date", "Datum", "日期")}
    date_column = next((index for index, header in enumerate(normalized) if header in date_headers), None)
    if date_column is None or not any(aliases.get(header) == "weight_kg" for header in normalized):
        raise ValueError("CSV-kolommen Date/Datum en Weight/Gewicht ontbreken. Kies een Fitdays-export.")
    measurements = {}
    skipped = 0
    warnings = []
    for row_number, values in enumerate(rows, start=2):
        try:
            if len(values) != len(headers):
                raise ValueError("Aantal kolommen klopt niet met de kopregel.")
            measured_date = fitdays_date(values[date_column])
            metrics = {}
            for index, header in enumerate(normalized):
                if index == date_column:
                    continue
                key = aliases.get(header, header)
                label, unit = FITDAYS_METRICS[key][:2] if key in FITDAYS_METRICS else (headers[index].strip(), "")
                try:
                    number = fitdays_number(values[index])
                except ValueError as error:
                    if key == "weight_kg":
                        raise
                    number = None
                    if len(warnings) < 5:
                        warnings.append(f"Rij {row_number}, {label}: {error}")
                metrics[key] = {"label": label, "unit": unit, "value": number}
            if metrics["weight_kg"]["value"] is None or metrics["weight_kg"]["value"] <= 0:
                raise ValueError("Gewicht ontbreekt of is nul.")
            measurements[measured_date] = metrics
        except (ValueError, KeyError) as error:
            skipped += 1
            if len(warnings) < 5:
                warnings.append(f"Rij {row_number}: {error}")
    if not measurements:
        raise ValueError("Geen geldige metingen gevonden. " + (warnings[0] if warnings else "Het bestand bevat geen meetrijen."))
    return measurements, skipped, warnings


@app.post("/api/bodyweight/import-csv")
async def import_fitdays_csv(file: UploadFile = File(...)):
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "Maximaal 5 MB per CSV-bestand. Exporteer een kortere periode.")
    try:
        measurements, skipped, warnings = parse_fitdays_csv(content)
    except (ValueError, csv.Error) as error:
        raise HTTPException(422, str(error)) from error
    conn = get_conn()
    try:
        with conn:
            for measured_date, metrics in measurements.items():
                existing = conn.execute("SELECT metrics_json FROM bodyweight_logs WHERE date = ?", (measured_date,)).fetchone()
                merged = json.loads(existing["metrics_json"]) if existing else {}
                merged.update(metrics)
                conn.execute(
                    """INSERT INTO bodyweight_logs (date, weight_kg, body_fat_pct, muscle_mass_kg, source, metrics_json)
                       VALUES (?, ?, ?, ?, 'fitdays_csv', ?)
                       ON CONFLICT(date) DO UPDATE SET
                           weight_kg = excluded.weight_kg,
                           body_fat_pct = COALESCE(excluded.body_fat_pct, bodyweight_logs.body_fat_pct),
                           muscle_mass_kg = COALESCE(excluded.muscle_mass_kg, bodyweight_logs.muscle_mass_kg),
                           source = 'fitdays_csv', metrics_json = excluded.metrics_json""",
                    (measured_date, metrics["weight_kg"]["value"], metrics.get("body_fat_pct", {}).get("value"),
                     metrics.get("muscle_mass_kg", {}).get("value"), json.dumps(merged, ensure_ascii=False)),
                )
    finally:
        conn.close()
    return {"imported": len(measurements), "skipped": skipped, "warnings": warnings}


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

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/logo.png", include_in_schema=False)
def serve_logo():
    return FileResponse(BASE_DIR / "img" / "zl5vhf5d3m6ce1pjma536glrqn33.png", media_type="image/png")