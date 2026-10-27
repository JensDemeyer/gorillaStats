"""Populate an existing development database; never runs during app startup."""

import argparse
import random
import sqlite3
import tempfile
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path


DEMO_TAG = "demo:july-progress"
DEFAULT_DB = Path(__file__).resolve().parent / "gym.db"
LOADS = {
    "Incline Bench Press (Barbell)": (40, 60, 2.5),
    "Chest Press (Machine)": (40, 65, 5),
    "Butterfly (Pec Deck)": (25, 40, 2.5),
    "Decline Bench Press (Barbell)": (45, 67.5, 2.5),
    "Lateral Raise (Cable)": (5, 8.75, 1.25),
    "Overhead Triceps Extension (Cable)": (15, 25, 2.5),
    "Triceps Rope Pushdown": (17.5, 30, 2.5),
    "Lat Pulldown (Cable)": (40, 60, 5),
    "Bent Over Row (Barbell)": (35, 55, 2.5),
    "Seated Cable Row - Bar Grip": (35, 55, 5),
    "Rear Delt Reverse Fly (Machine)": (20, 32.5, 2.5),
    "Face Pull": (12.5, 22.5, 2.5),
    "Bicep Curl (Cable)": (12.5, 22.5, 2.5),
    "Reverse Curl (Cable)": (10, 17.5, 2.5),
    "Seated Wrist Curl (Barbell)": (15, 22.5, 2.5),
    "Hammer Curl (Dumbbell)": (8, 14, 2),
    "Squat (Barbell)": (50, 80, 2.5),
    "Romanian Deadlift (Barbell)": (45, 75, 2.5),
    "Leg Extension (Machine)": (30, 50, 5),
    "Lying Leg Curl (Machine)": (25, 40, 5),
    "Standing Calf Raise (Machine)": (40, 65, 5),
}


def seed_database(database: Path, end: date, apply: bool = False) -> dict:
    start = date(end.year, 7, 1)
    if end <= start:
        raise ValueError("The end date must be after July 1 of the same year.")
    database = database.resolve()
    conn = sqlite3.connect(database.as_uri() + "?mode=rw", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        exercises = conn.execute("SELECT id, routine, name FROM exercises ORDER BY id").fetchall()
        unknown = [exercise["name"] for exercise in exercises if exercise["name"] not in LOADS]
        if unknown:
            raise ValueError(f"Add realistic load ranges for these exercises first: {unknown}")
        if not exercises:
            raise ValueError("Start the app once to create the default exercises first.")
        backup_path = None
        if apply:
            backup_dir = Path(tempfile.gettempdir()) / "gorillastats-backups"
            backup_dir.mkdir(exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            backup_path = backup_dir / f"{database.stem}-{stamp}.sqlite3"
            with closing(sqlite3.connect(backup_path)) as backup:
                conn.backup(backup)
        rng = random.Random(20261026)
        days = (end - start).days
        routines = list(dict.fromkeys(exercise["routine"] for exercise in exercises))
        sessions = 0
        counts = {"sets": 0, "bodyweight": 0, "cardio": 0}
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute("DELETE FROM logs WHERE notes LIKE ?", (DEMO_TAG + "%",))
            conn.execute("DELETE FROM cardio_logs WHERE notes LIKE ?", (DEMO_TAG + "%",))
            conn.execute("DELETE FROM bodyweight_logs WHERE source = ?", (DEMO_TAG,))
            for offset in range(days + 1):
                current = start + timedelta(days=offset)
                progress = offset / days
                stamp = current.isoformat()
                if current.weekday() in (0, 2, 4) or offset in (0, days):
                    fluctuation = 0 if offset in (0, days) else rng.uniform(-0.45, 0.45)
                    weight = round(110 - 10 * progress + fluctuation, 1)
                    cursor = conn.execute(
                        """INSERT OR IGNORE INTO bodyweight_logs
                           (date, weight_kg, body_fat_pct, muscle_mass_kg, source)
                           VALUES (?, ?, ?, ?, ?)""",
                        (stamp, weight, round(30 - 5 * progress + rng.uniform(-0.3, 0.3), 1),
                         round(42 + 0.8 * progress + rng.uniform(-0.2, 0.2), 1), DEMO_TAG),
                    )
                    counts["bodyweight"] += cursor.rowcount
                if current.weekday() in (0, 1, 3, 5):
                    routine = routines[sessions % len(routines)]
                    sessions += 1
                    deload = offset // 7 in (6, 12)
                    readiness = 0.85 if deload else rng.choice([0.94, 0.98, 1, 1, 1, 1.02])
                    note = DEMO_TAG + (" | Herstelweek" if deload else " | Training")
                    for exercise in exercises:
                        if exercise["routine"] != routine:
                            continue
                        initial, final, increment = LOADS[exercise["name"]]
                        target = (initial + (final - initial) * progress) * readiness
                        load = max(increment, round(target / increment) * increment)
                        for set_nr in (1, 2, 3):
                            reps = max(6, rng.randint(9, 12) - (set_nr - 1))
                            if deload:
                                reps = 8
                            best = conn.execute(
                                """SELECT COALESCE(MAX(weight), 0),
                                   COALESCE(MAX(CASE WHEN reps = 1 THEN weight
                                       ELSE weight * (1 + reps / 30.0) END), 0)
                                   FROM logs WHERE exercise_id = ? AND date <= ?""",
                                (exercise["id"], stamp),
                            ).fetchone()
                            is_pr = load > best[0] or load * (1 + reps / 30) > best[1]
                            conn.execute(
                                """INSERT INTO logs
                                   (date, exercise_id, set_nr, weight, reps, is_pr, notes)
                                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                (stamp, exercise["id"], set_nr, load, reps, int(is_pr), note),
                            )
                            counts["sets"] += 1
                if current.weekday() in (2, 5) and rng.random() < 0.65:
                    activity = rng.choice(["Fietsen", "Loopband", "Roeien", "Crosstrainer"])
                    minutes = rng.choice([15, 20, 25, 30, 35])
                    speed = {"Fietsen": 19, "Loopband": 5.5, "Roeien": 9, "Crosstrainer": 7}[activity]
                    conn.execute(
                        """INSERT INTO cardio_logs
                           (date, type, duration_minutes, distance_km, calories, notes)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (stamp, activity, minutes, round(speed * minutes / 60, 1),
                         round(minutes * rng.uniform(5, 8)), DEMO_TAG + " | Rustig tempo"),
                    )
                    counts["cardio"] += 1
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
            if apply:
                conn.commit()
            else:
                conn.rollback()
        except BaseException:
            conn.rollback()
            raise
        return {"database": str(database), "start": start.isoformat(), "end": end.isoformat(),
                "sessions": sessions, **counts, "applied": apply,
                "backup": str(backup_path) if backup_path else None}
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    parser.add_argument("--apply", action="store_true", help="Write demo data; default is a rollback-only preview.")
    args = parser.parse_args()
    for key, value in seed_database(args.database, args.end, args.apply).items():
        print(f"{key}: {value}")