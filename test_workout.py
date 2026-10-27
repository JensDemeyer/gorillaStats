import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

import main


class WorkoutTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database = Path(self.directory.name) / "gym.db"
        self.db_patch = patch.object(main, "DB_FILE", self.database)
        self.db_patch.start()
        main.init_db()
        self.push = main.get_routines()["Push"]
        self.exercise_id = self.push[0]["id"]

    def tearDown(self):
        self.db_patch.stop()
        self.directory.cleanup()

    def save(self, **values):
        return main.save_log(main.LogEntry(exercise_id=self.exercise_id, set_nr=1, **values))

    def test_empty_set_and_later_completion(self):
        result = self.save()
        log = main.get_today_logs()[0]
        self.assertIsNone(log["weight"])
        self.assertIsNone(log["reps"])
        self.assertFalse(result["is_pr"])
        self.assertEqual(main.get_stats()["tonnage_today"], 0)
        main.update_log(result["id"], main.LogUpdate(weight=60, reps=8, notes="Later"))
        log = main.get_today_logs()[0]
        self.assertEqual((log["weight"], log["reps"], log["notes"]), (60, 8, "Later"))
        self.assertEqual(main.get_stats()["tonnage_today"], 480)
        self.assertEqual(len(main.get_today_logs()), 1)

    def test_partial_and_bodyweight_sets(self):
        self.save(reps=10)
        self.save(weight=60)
        self.save(weight=0, reps=12)
        self.assertEqual(main.get_stats()["tonnage_today"], 0)
        self.assertFalse(any(log["is_pr"] for log in main.get_today_logs()))
        self.save(weight=20, reps=10)
        self.assertEqual(main.get_stats()["tonnage_today"], 200)

    def test_past_day_completion_and_previous_session(self):
        yesterday = date.today() - timedelta(days=1)
        result = self.save(log_date=yesterday)
        self.assertEqual(main.get_today_logs(), [])
        main.update_log(result["id"], main.LogUpdate(weight=42.5, reps=9))
        previous = main.get_previous_session(self.exercise_id)
        self.assertEqual(previous["date"], yesterday.isoformat())
        self.assertEqual(previous["sets"][0]["weight"], 42.5)
        self.assertEqual(main.get_logs(yesterday)[0]["id"], result["id"])
        self.assertEqual(main.get_progress(self.exercise_id)[0]["total_volume"], 382.5)

    def test_prs_recalculated_after_edit_and_delete(self):
        first = self.save(weight=60, reps=8)
        second = self.save(weight=80, reps=8)
        main.update_log(first["id"], main.LogUpdate(weight=100, reps=8))
        self.assertEqual([log["is_pr"] for log in main.get_today_logs()], [1, 0])
        with closing(main.get_conn()) as conn:
            main.refresh_prs(conn, self.exercise_id)
            self.assertEqual(conn.total_changes, 0)
        main.delete_log(first["id"])
        self.assertEqual(main.get_today_logs()[0]["is_pr"], 1)
        main.update_log(second["id"], main.LogUpdate())
        self.assertEqual(main.get_stats()["recent_prs"], [])

    def test_schema_edit_keeps_history_and_orders_exercises(self):
        self.save(weight=60, reps=8)
        body = main.RoutineUpdate(name="Push A", exercises=[
            main.RoutineExercise(id=self.push[1]["id"], name="Machine press"),
            main.RoutineExercise(name="Dips"),
        ])
        main.update_routine("Push", body)
        routines = main.get_routines()
        self.assertNotIn("Push", routines)
        self.assertEqual([ex["name"] for ex in routines["Push A"]], ["Machine press", "Dips"])
        self.assertEqual(main.get_today_logs()[0]["exercise_id"], self.exercise_id)
        self.assertEqual(main.get_stats()["total_volume"], 480)
        main.init_db()
        self.assertEqual([ex["name"] for ex in main.get_routines()["Push A"]], ["Machine press", "Dips"])

    def test_invalid_schema_does_not_change_existing_data(self):
        duplicate = main.RoutineExercise(id=self.exercise_id, name="Press")
        with self.assertRaises(HTTPException):
            main.update_routine("Push", main.RoutineUpdate(name="New", exercises=[duplicate, duplicate]))
        with self.assertRaises(HTTPException):
            main.update_routine("Push", main.RoutineUpdate(name="Pull", exercises=[duplicate]))
        self.assertEqual(main.get_routines()["Push"], self.push)

    def test_invalid_set_values_rejected(self):
        for values in ({"weight": -1}, {"reps": 0}, {"reps": 1.5}, {"weight": float("inf")}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                main.LogEntry(exercise_id=self.exercise_id, set_nr=1, **values)
        with self.assertRaises(HTTPException):
            main.update_log(99999, main.LogUpdate(weight=1, reps=1))

    def test_legacy_migration_preserves_rows_and_ids(self):
        with closing(sqlite3.connect(self.database)) as conn:
            conn.executescript("""
                DROP TABLE logs;
                CREATE TABLE logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL,
                    exercise_id INTEGER NOT NULL REFERENCES exercises(id), set_nr INTEGER NOT NULL,
                    weight REAL NOT NULL, reps INTEGER NOT NULL, is_pr INTEGER DEFAULT 0, notes TEXT
                );
            """)
            conn.execute("INSERT INTO logs VALUES (41, ?, ?, 3, 80, 8, 1, 'Keep me')",
                         (date.today().isoformat(), self.exercise_id))
            conn.commit()
        main.init_db()
        main.init_db()
        log = main.get_today_logs()[0]
        self.assertEqual((log["id"], log["weight"], log["notes"], log["is_pr"]), (41, 80, "Keep me", 1))
        result = self.save()
        self.assertGreater(result["id"], 41)
        self.assertIsNone(main.get_today_logs()[-1]["weight"])


if __name__ == "__main__":
    unittest.main()