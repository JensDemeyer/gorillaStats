"""Import gym visits from dates.json and fill empty days with estimated sessions.

Dry-run by default. Estimates are based only on real (non-estimated) logs and are
stored as estimated sets, so they never create PRs or feed later estimates.
"""

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from statistics import mean

TAG = "import:dates.json"
BASE_DIR = Path(__file__).resolve().parent
ROTATION = ("Push", "Pull", "Legs")
MIN_FREQUENCY = 0.5
DEFAULT_STEP = 2.5


@dataclass(frozen=True)
class Visit:
    day: date
    club: str
    time: str


def parse_visits(text: str, today: date) -> list:
    # raw_decode ignores stray text after the JSON array.
    try:
        raw, _ = json.JSONDecoder().raw_decode(text.lstrip("\ufeff \t\r\n"))
    except json.JSONDecodeError as error:
        raise ValueError(f"dates.json is geen geldige JSON: {error}") from error
    if not isinstance(raw, list):
        raise ValueError("dates.json moet een lijst met bezoeken bevatten.")
    visits, errors = [], []
    for position, item in enumerate(raw, 1):
        try:
            day = datetime.strptime(item["datum"], "%d-%m-%Y").date()
            datetime.strptime(item["tijd"], "%H:%M:%S")
            club = str(item["club"]).strip()
            if not club:
                raise ValueError("club is leeg")
            if day > today:
                raise ValueError("datum ligt in de toekomst")
            visits.append(Visit(day, club, item["tijd"]))
        except (KeyError, TypeError, ValueError) as error:
            errors.append(f"item {position}: {error!r}")
    duplicates = sorted(d for d, n in Counter(v.day for v in visits).items() if n > 1)
    errors += [f"datum komt meermaals voor: {d.isoformat()}" for d in duplicates]
    if errors:
        raise ValueError("Ongeldige dates.json:\n" + "\n".join(errors))
    return sorted(visits, key=lambda visit: visit.day)


def weight_step(weights) -> float:
    values = sorted({round(w, 4) for w in weights})
    diffs = [round(b - a, 4) for a, b in zip(values, values[1:])]
    return max(min(diffs), 0.5) if diffs else DEFAULT_STEP


def snap(value: float, step: float) -> float:
    return round(round(value / step) * step, 2)


def estimate_weight(points, day: date, step: float) -> float:
    """Interpolate between real sessions; extrapolate conservatively."""
    before = [(d, w) for d, w in points if d < day]
    after = [(d, w) for d, w in points if d > day]
    before_value = mean(w for _, w in before[-3:]) if before else None
    after_value = mean(w for _, w in after[:3]) if after else None
    if before and after:
        span = (after[0][0] - before[-1][0]).days
        fraction = (day - before[-1][0]).days / span
        value = before_value + (after_value - before_value) * fraction
        low, high = sorted((snap(before_value, step), snap(after_value, step)))
        return min(max(snap(value, step), low), high)
    if before:
        return snap(before_value, step)
    # Before the first real session: at most one step lower per 14 days, never over 10% lower.
    gap = (after[0][0] - day).days
    return snap(max(after_value * 0.9, after_value - step * (gap // 14)), step)


def estimate_reps(points, day: date):
    nearest = sorted(points, key=lambda point: (abs((point[0] - day).days), point[0]))[:3]
    return int(mean(r for _, r in nearest) + 0.5) if nearest else None


def nearest_series(series_by_set: dict, set_nr: int) -> list:
    keys = sorted((k for k, v in series_by_set.items() if v), key=lambda k: (abs(k - set_nr), k))
    return series_by_set[keys[0]] if keys else []


def load_reference(conn):
    rows = conn.execute(
        """SELECT l.date, l.exercise_id, l.set_nr, l.weight, l.reps
           FROM logs l WHERE l.is_estimated = 0 AND COALESCE(l.notes, '') NOT LIKE ?
           ORDER BY l.date, l.set_nr""",
        (TAG + "%",),
    ).fetchall()
    series = defaultdict(lambda: defaultdict(lambda: {"weight": [], "reps": []}))
    sessions = defaultdict(Counter)
    for log_date, exercise_id, set_nr, weight, reps in rows:
        day = date.fromisoformat(log_date)
        sessions[exercise_id][day] += 1
        if weight is not None:
            series[exercise_id][set_nr]["weight"].append((day, weight))
        if reps is not None:
            series[exercise_id][set_nr]["reps"].append((day, reps))
    return series, sessions


def typical_exercises(exercises, sessions) -> dict:
    """Exercises done in at least half of the real sessions of their routine."""
    routine_days = defaultdict(set)
    for exercise in exercises:
        routine_days[exercise["routine"]].update(sessions[exercise["id"]])
    typical = defaultdict(list)
    for exercise in exercises:
        if not exercise["active"]:
            continue
        total = len(routine_days[exercise["routine"]])
        counts = sessions[exercise["id"]]
        if total and len(counts) / total >= MIN_FREQUENCY:
            sets = Counter(counts.values())
            usual = max(sets, key=lambda value: (sets[value], value))
            typical[exercise["routine"]].append((exercise, usual))
    return typical


def day_routines(conn) -> dict:
    rows = conn.execute(
        """SELECT l.date, e.routine, COUNT(*) FROM logs l JOIN exercises e ON e.id = l.exercise_id
           GROUP BY l.date, e.routine"""
    ).fetchall()
    best = {}
    for log_date, routine, count in rows:
        day = date.fromisoformat(log_date)
        if day not in best or count > best[day][1]:
            best[day] = (routine, count)
    return {day: routine for day, (routine, _) in best.items()}


def choose_routine(day: date, rotation, assigned: dict, fixed: dict) -> str:
    previous = next((assigned[d] for d in sorted(assigned, reverse=True) if d < day), None)
    upcoming = next((fixed[d] for d in sorted(fixed) if d > day), None)
    index = rotation.index(previous) if previous in rotation else -1
    base = rotation[(index + 1) % len(rotation)]
    candidates = [base] + [r for r in rotation if r not in (base, previous)]
    return next((r for r in candidates if r != upcoming), base)


def plan_import(conn, visits) -> list:
    exercises = conn.execute(
        "SELECT id, routine, name, active FROM exercises ORDER BY routine, sort_order, id"
    ).fetchall()
    exercises = [dict(zip(("id", "routine", "name", "active"), row)) for row in exercises]
    if not exercises:
        raise ValueError("Start de app eerst eenmaal zodat de oefeningen bestaan.")
    routines = list(dict.fromkeys(e["routine"] for e in exercises if e["active"]))
    rotation = [r for r in ROTATION if r in routines]
    rotation = rotation if len(rotation) == len(ROTATION) else routines
    series, sessions = load_reference(conn)
    typical = typical_exercises(exercises, sessions)
    fixed = day_routines(conn)
    assigned = dict(fixed)
    plan = []
    for visit in visits:
        entry = {"date": visit.day, "club": visit.club, "time": visit.time,
                 "sets": [], "skipped": []}
        if visit.day in fixed:
            entry.update(status="bestaand", routine=fixed[visit.day])
            plan.append(entry)
            continue
        routine = choose_routine(visit.day, rotation, assigned, fixed)
        assigned[visit.day] = routine
        entry.update(status="nieuw", routine=routine)
        if not typical[routine]:
            entry["skipped"].append(f"{routine}: geen eigen sessies als referentie")
        for exercise, count in typical[routine]:
            by_set = series[exercise["id"]]
            weights = [w for sets in by_set.values() for _, w in sets["weight"]]
            if not weights:
                entry["skipped"].append(f"{exercise['name']}: geen gewichten gelogd")
                continue
            step = weight_step(weights)
            for set_nr in range(1, count + 1):
                weight_points = nearest_series({k: v["weight"] for k, v in by_set.items()}, set_nr)
                reps_points = nearest_series({k: v["reps"] for k, v in by_set.items()}, set_nr)
                entry["sets"].append((exercise["id"], exercise["name"], set_nr,
                                      estimate_weight(weight_points, visit.day, step),
                                      estimate_reps(reps_points, visit.day)))
        plan.append(entry)
    return plan


def ensure_schema(conn):
    needed = {"exercises": {"active", "sort_order"}, "logs": {"is_estimated"}}
    for table, columns in needed.items():
        present = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if not columns <= present:
            raise ValueError("Start de bijgewerkte app eerst eenmaal zodat de database migreert.")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS workout_sessions (
               id         INTEGER PRIMARY KEY AUTOINCREMENT,
               date       TEXT NOT NULL UNIQUE,
               club       TEXT,
               start_time TEXT,
               routine    TEXT,
               source     TEXT NOT NULL DEFAULT 'manual'
           )"""
    )


def write_plan(conn, plan) -> dict:
    counts = {"sessions": 0, "sets": 0}
    for entry in plan:
        iso = entry["date"].isoformat()
        conn.execute(
            """INSERT INTO workout_sessions (date, club, start_time, routine, source)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET club = excluded.club,
                   start_time = excluded.start_time, routine = excluded.routine""",
            (iso, entry["club"], entry["time"], entry["routine"], TAG),
        )
        counts["sessions"] += 1
        note = f"{TAG} | {entry['club']} {entry['time'][:5]}"
        conn.executemany(
            """INSERT INTO logs (date, exercise_id, set_nr, weight, reps, is_pr, notes, is_estimated)
               VALUES (?, ?, ?, ?, ?, 0, ?, 1)""",
            [(iso, exercise_id, set_nr, weight, reps, note)
             for exercise_id, _, set_nr, weight, reps in entry["sets"]],
        )
        counts["sets"] += len(entry["sets"])
    return counts


def backup_database(conn, database: Path) -> Path:
    path = database.with_name(f"{database.name}.pre-import-{datetime.now():%Y%m%d-%H%M%S-%f}")
    with closing(sqlite3.connect(path)) as backup:
        conn.backup(backup)
    return path


def connect(database: Path):
    conn = sqlite3.connect(database.resolve().as_uri() + "?mode=rw", uri=True,
                           isolation_level=None, timeout=30)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def run_import(database: Path, dates_file: Path, apply: bool = False, today: date = None) -> dict:
    visits = parse_visits(dates_file.read_text(encoding="utf-8"), today or date.today())
    with closing(connect(database)) as conn:
        backup = backup_database(conn, database) if apply else None
        conn.execute("BEGIN IMMEDIATE")
        try:
            ensure_schema(conn)
            plan = plan_import(conn, visits)
            counts = write_plan(conn, plan)
            if conn.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Foreign key check mislukt.")
            conn.execute("COMMIT" if apply else "ROLLBACK")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    return {"plan": plan, "applied": apply, "backup": backup, **counts}


def run_rollback(database: Path, apply: bool = False) -> dict:
    with closing(connect(database)) as conn:
        backup = backup_database(conn, database) if apply else None
        conn.execute("BEGIN IMMEDIATE")
        try:
            sets = conn.execute("DELETE FROM logs WHERE COALESCE(notes, '') LIKE ?", (TAG + "%",)).rowcount
            has_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'workout_sessions'"
            ).fetchone()
            sessions = conn.execute(
                "DELETE FROM workout_sessions WHERE source = ?", (TAG,)).rowcount if has_table else 0
            conn.execute("COMMIT" if apply else "ROLLBACK")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    return {"deleted_sets": sets, "deleted_sessions": sessions, "applied": apply, "backup": backup}


def print_report(result: dict, verbose: bool):
    for entry in result["plan"]:
        print(f"{entry['date']}  {entry['routine']:<5} {entry['status']:<8} "
              f"{len(entry['sets']):>3} sets  {entry['club']} {entry['time'][:5]}")
        for message in entry["skipped"]:
            print(f"    overgeslagen: {message}")
        if verbose:
            for _, name, set_nr, weight, reps in entry["sets"]:
                print(f"    {name} set {set_nr}: {weight} kg x {reps}")
    new_days = sum(entry["status"] == "nieuw" for entry in result["plan"])
    print(f"\nsessies: {result['sessions']} ({new_days} nieuw ingevuld), sets: {result['sets']}")
    print("TOEGEPAST" if result["applied"] else "DRY-RUN: er is niets geschreven. Gebruik --apply.")
    if result["backup"]:
        print(f"backup: {result['backup']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=BASE_DIR / "gym.db")
    parser.add_argument("--dates", type=Path, default=BASE_DIR / "dates.json")
    parser.add_argument("--apply", action="store_true", help="Schrijf naar de database (met backup).")
    parser.add_argument("--rollback", action="store_true", help="Verwijder alles wat dit script importeerde.")
    parser.add_argument("--verbose", action="store_true", help="Toon alle gewichten en reps.")
    args = parser.parse_args()
    if args.rollback:
        for key, value in run_rollback(args.database, args.apply).items():
            print(f"{key}: {value}")
    else:
        print_report(run_import(args.database, args.dates, args.apply), args.verbose)
