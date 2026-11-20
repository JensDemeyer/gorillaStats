import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path
from unittest.mock import patch

import import_dates
import main

TODAY = date(2026, 11, 20)


def visit(day, time="18:00:00"):
    return {"club": "Club", "datum": day.strftime("%d-%m-%Y"), "tijd": time}


class ImportDatesTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database = Path(self.directory.name) / "gym.db"
        self.dates_file = Path(self.directory.name) / "dates.json"
        with patch.object(main, "DB_FILE", self.database):
            main.init_db()
        with closing(sqlite3.connect(self.database)) as conn:
            self.ids = {routine: [row[0] for row in conn.execute(
                "SELECT id FROM exercises WHERE routine = ? ORDER BY id", (routine,))]
                for routine in ("Push", "Pull", "Legs")}

    def tearDown(self):
        self.directory.cleanup()

    def real_session(self, day, routine, weight, reps=10, exercises=3, sets=3):
        with closing(sqlite3.connect(self.database)) as conn, conn:
            for exercise_id in self.ids[routine][:exercises]:
                for set_nr in range(1, sets + 1):
                    conn.execute("INSERT INTO logs (date, exercise_id, set_nr, weight, reps) VALUES (?, ?, ?, ?, ?)",
                                 (day.isoformat(), exercise_id, set_nr, weight, reps))

    def write_dates(self, *days):
        self.dates_file.write_text(json.dumps([visit(day) for day in days]) + "\n```[cite: 1]", encoding="utf-8")

    def run_import(self, apply=False):
        return import_dates.run_import(self.database, self.dates_file, apply, TODAY)

    def query(self, sql, *args):
        with closing(sqlite3.connect(self.database)) as conn:
            return conn.execute(sql, args).fetchall()

    def test_parse_ignores_trailing_text_and_rejects_bad_dates(self):
        self.write_dates(date(2026, 11, 19))
        visits = import_dates.parse_visits(self.dates_file.read_text(encoding="utf-8"), TODAY)
        self.assertEqual(visits[0].day, date(2026, 11, 19))
        bad = json.dumps([visit(date(2026, 11, 21)), visit(date(2026, 11, 1)), visit(date(2026, 11, 1))])
        with self.assertRaises(ValueError) as error:
            import_dates.parse_visits(bad, TODAY)
        self.assertIn("toekomst", str(error.exception))
        self.assertIn("meermaals", str(error.exception))

    def cycle(self):
        """One real Push, Pull and Legs session (20-22 October)."""
        for offset, (routine, weight) in enumerate((("Push", 40), ("Pull", 30), ("Legs", 60))):
            self.real_session(date(2026, 10, 20 + offset), routine, weight)

    def test_dry_run_writes_nothing(self):
        self.cycle()
        self.write_dates(date(2026, 11, 3))
        result = self.run_import()
        self.assertFalse(result["applied"])
        self.assertGreater(result["sets"], 0)
        self.assertEqual(self.query("SELECT COUNT(*) FROM logs WHERE is_estimated = 1"), [(0,)])
        self.assertEqual(self.query("SELECT name FROM sqlite_master WHERE name = 'workout_sessions'"), [])

    def test_rotation_follows_real_days_and_weights_interpolate(self):
        self.real_session(date(2026, 11, 1), "Push", 40)
        self.real_session(date(2026, 11, 4), "Pull", 30)
        self.real_session(date(2026, 11, 6), "Legs", 60)
        self.real_session(date(2026, 11, 11), "Push", 50)
        self.real_session(date(2026, 11, 14), "Pull", 35)
        self.write_dates(date(2026, 11, 3), date(2026, 11, 8))
        plan = {entry["date"]: entry for entry in self.run_import(True)["plan"]}
        # After Push the rotation says Pull, but a real Pull follows next day: Legs instead.
        self.assertEqual(plan[date(2026, 11, 3)]["routine"], "Legs")
        # After Legs the rotation says Push, but a real Push follows: Pull instead.
        self.assertEqual(plan[date(2026, 11, 8)]["routine"], "Pull")
        weights = [s[3] for s in plan[date(2026, 11, 8)]["sets"]]
        self.assertTrue(all(30 <= w <= 35 for w in weights), weights)
        self.assertEqual(len(plan[date(2026, 11, 8)]["sets"]), 9)
        row = self.query("SELECT is_estimated, is_pr, notes FROM logs WHERE date = '2026-11-08' LIMIT 1")[0]
        self.assertEqual(row[:2], (1, 0))
        self.assertIn("import:dates.json | Club 18:00", row[2])

    def test_rarely_used_exercises_are_left_out(self):
        for index in range(4):
            self.real_session(date(2026, 10, 1 + index), "Pull", 30, exercises=2)
        self.real_session(date(2026, 10, 9), "Pull", 30, exercises=3)
        self.real_session(date(2026, 10, 10), "Push", 40)
        self.write_dates(date(2026, 10, 12))
        sets = self.run_import()["plan"][0]["sets"]
        self.assertEqual({s[0] for s in sets}, set(self.ids["Pull"][:2]))

    def test_existing_days_are_kept_and_import_is_idempotent(self):
        self.cycle()
        self.write_dates(date(2026, 10, 21), date(2026, 11, 3))
        first = self.run_import(True)
        self.assertEqual(first["plan"][0]["status"], "bestaand")
        self.assertEqual(first["plan"][1]["routine"], "Push")
        before = self.query("SELECT COUNT(*) FROM logs")
        second = self.run_import(True)
        self.assertEqual(self.query("SELECT COUNT(*) FROM logs"), before)
        self.assertEqual(second["sets"], 0)
        self.assertEqual(self.query("SELECT COUNT(*) FROM workout_sessions"), [(2,)])
        self.assertEqual(len(list(self.database.parent.glob("gym.db.pre-import-*"))), 2)

    def test_estimates_are_not_used_as_reference(self):
        self.cycle()
        self.write_dates(date(2026, 11, 3))
        self.run_import(True)
        with closing(sqlite3.connect(self.database)) as conn:
            series, _ = import_dates.load_reference(conn)
        days = {d for sets in series[self.ids["Push"][0]].values() for d, _ in sets["weight"]}
        self.assertEqual(days, {date(2026, 10, 20)})

    def test_rollback_removes_only_imported_data(self):
        self.cycle()
        self.write_dates(date(2026, 11, 3))
        self.run_import(True)
        result = import_dates.run_rollback(self.database, True)
        self.assertEqual(result["deleted_sets"], 9)
        self.assertEqual(self.query("SELECT COUNT(*) FROM logs WHERE is_estimated = 1"), [(0,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM logs"), [(27,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM workout_sessions"), [(0,)])

    def test_weight_before_first_session_is_slightly_lower(self):
        step = 2.5
        self.assertEqual(import_dates.estimate_weight([(date(2026, 11, 1), 50)], date(2026, 10, 25), step), 50)
        self.assertEqual(import_dates.estimate_weight([(date(2026, 11, 1), 50)], date(2026, 10, 4), step), 45)
        self.assertEqual(import_dates.estimate_weight([(date(2026, 11, 1), 50)], date(2026, 8, 1), step), 45)


if __name__ == "__main__":
    unittest.main()
