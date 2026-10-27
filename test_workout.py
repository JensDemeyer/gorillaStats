import asyncio
import io
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
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

    def test_historical_average_weights_sessions_equally(self):
        target = date.today() - timedelta(days=1)
        for days_ago, weights in [(4, [200]), (3, [40, 60]), (2, [70]), (1, [80, 90, 100])]:
            for weight in weights:
                self.save(weight=weight, reps=8, log_date=target - timedelta(days=days_ago))
        self.save(weight=999, reps=8, log_date=target)
        self.save(weight=999, reps=8, log_date=date.today())
        suggestion = next(item for item in main.get_workout_suggestions(target)
                          if item["exercise_id"] == self.exercise_id)
        self.assertEqual(suggestion["weight"], 70)
        self.assertEqual(suggestion["sessions"], 3)
        main.save_workout(main.WorkoutEntry(log_date=target, exercises=[
            main.WorkoutExercise(exercise_id=self.exercise_id, sets=2, reps=8),
        ]))
        logs = main.get_logs(target)
        self.assertEqual([log["set_nr"] for log in logs], [1, 2, 3])
        self.assertEqual([log["weight"] for log in logs[1:]], [70, 70])
        self.assertTrue(all(log["is_estimated"] and not log["is_pr"] for log in logs[1:]))

    def test_backfill_with_less_history_and_no_history(self):
        target = date.today() - timedelta(days=1)
        self.save(weight=0, reps=10, log_date=target - timedelta(days=1))
        other = self.push[1]["id"]
        main.save_workout(main.WorkoutEntry(log_date=target, exercises=[
            main.WorkoutExercise(exercise_id=self.exercise_id, sets=1),
            main.WorkoutExercise(exercise_id=other, sets=2),
        ]))
        logs = main.get_logs(target)
        self.assertEqual(logs[0]["weight"], 0)
        self.assertEqual(logs[0]["is_estimated"], 1)
        self.assertIsNone(logs[1]["weight"])
        self.assertEqual(logs[1]["is_estimated"], 0)
        self.assertEqual(main.get_stats()["rewards"]["weekly_days"], 1 if target.weekday() < date.today().weekday() else 0)

    def test_estimates_do_not_feed_future_estimates(self):
        target = date.today() - timedelta(days=1)
        self.save(weight=60, reps=8, log_date=target - timedelta(days=5))
        for offset in (3, 2, 1):
            main.save_workout(main.WorkoutEntry(log_date=target - timedelta(days=offset), exercises=[
                main.WorkoutExercise(exercise_id=self.exercise_id, sets=1, reps=8),
            ]))
        suggestion = next(item for item in main.get_workout_suggestions(target)
                          if item["exercise_id"] == self.exercise_id)
        self.assertEqual((suggestion["weight"], suggestion["sessions"]), (60, 1))

    def test_backfill_manual_weight_and_edit_exercise_date(self):
        target = date.today() - timedelta(days=1)
        main.save_workout(main.WorkoutEntry(log_date=target, exercises=[
            main.WorkoutExercise(exercise_id=self.exercise_id, sets=1, weight=45, reps=8, is_estimated=False),
        ]))
        log = main.get_logs(target)[0]
        self.assertEqual((log["weight"], log["is_estimated"]), (45, 0))
        main.update_log(log["id"], main.LogUpdate(
            exercise_id=self.push[1]["id"], log_date=date.today(), weight=50, reps=10, is_estimated=False))
        self.assertEqual(main.get_logs(target), [])
        updated = main.get_today_logs()[0]
        self.assertEqual((updated["exercise_id"], updated["weight"], updated["set_nr"]), (self.push[1]["id"], 50, 1))

    def test_backfill_rejects_invalid_exercises_atomically(self):
        target = date.today() - timedelta(days=1)
        for exercises in ([main.WorkoutExercise(exercise_id=self.exercise_id), main.WorkoutExercise(exercise_id=99999)],
                          [main.WorkoutExercise(exercise_id=self.exercise_id)] * 2):
            with self.assertRaises(HTTPException):
                main.save_workout(main.WorkoutEntry(log_date=target, exercises=exercises))
            self.assertEqual(main.get_logs(target), [])
        with self.assertRaises(HTTPException):
            main.save_workout(main.WorkoutEntry(log_date=date.today() + timedelta(days=1), exercises=[
                main.WorkoutExercise(exercise_id=self.exercise_id),
            ]))

    def test_estimate_can_be_confirmed_and_survives_restart(self):
        yesterday = date.today() - timedelta(days=1)
        self.save(weight=60, reps=8, log_date=yesterday)
        main.save_workout(main.WorkoutEntry(log_date=date.today(), exercises=[
            main.WorkoutExercise(exercise_id=self.exercise_id, sets=1, reps=12),
        ]))
        log = main.get_today_logs()[0]
        self.assertFalse(log["is_pr"])
        main.init_db()
        self.assertTrue(main.get_today_logs()[0]["is_estimated"])
        main.update_log(log["id"], main.LogUpdate(weight=60, reps=12, is_estimated=False))
        self.assertTrue(main.get_today_logs()[0]["is_pr"])

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

    def import_csv(self, text):
        upload = UploadFile(file=io.BytesIO(text.encode("utf-8-sig")), filename="fitdays.csv")
        return asyncio.run(main.import_fitdays_csv(upload))

    def test_fitdays_semicolon_units_and_all_metrics(self):
        content = (
            "Date;Weight;BMI;Body Fat;Subcutaneous fat;Heart Rate;Cardiac Index;Visceral Fat;Body Water;Skeletal Muscle;Muscle Mass;Bone Mass;Protein;BMR;Body age\n"
            "17:36 Jan.27,2025;108.2kg;29.0;42.1%;30.0%;- -;- -;14.6;50.4%;38.8%;58.8kg;3.9kg;4.0%;1888.0kcal;27.0\n"
        )
        result = self.import_csv(content)
        self.assertEqual((result["imported"], result["skipped"]), (1, 0))
        row = main.get_bodyweight()[0]
        self.assertEqual((row["date"], row["weight_kg"], row["body_fat_pct"], row["muscle_mass_kg"]),
                         ("2025-01-27", 108.2, 42.1, 58.8))
        self.assertEqual(len(row["metrics"]), 14)
        self.assertEqual(row["metrics"]["bmr"]["value"], 1888)
        self.assertIsNone(row["metrics"]["heart_rate"]["value"])
        self.assertIsNone(row["metrics"]["cardiac_index"]["value"])
        self.import_csv(content)
        self.assertEqual(len(main.get_bodyweight()), 1)

    def test_fitdays_decimal_comma_and_optional_missing_values(self):
        self.import_csv("Date;Weight;Body Fat;Muscle Mass;Heart Rate\n27/01/2025;108,2 kg;42,1 %;58,8 kg;72bpm\n")
        row = main.get_bodyweight()[0]
        self.assertEqual((row["weight_kg"], row["body_fat_pct"]), (108.2, 42.1))
        self.assertEqual(row["metrics"]["heart_rate"]["value"], 72)
        result = self.import_csv("Date;Weight;Body Fat\n2025-01-28;108kg;- -\n")
        self.assertEqual(result["skipped"], 0)
        self.assertIsNone(main.get_bodyweight()[-1]["body_fat_pct"])

    def test_fitdays_original_comma_csv_still_works(self):
        self.import_csv("Date,Weight(kg),Body Fat(%),Muscle Mass(kg)\n2025/01/27,108.2,42.1,58.8\n")
        self.assertEqual(main.get_bodyweight()[0]["weight_kg"], 108.2)

    def test_fitdays_invalid_file_reports_error_without_writes(self):
        for content in ("", "Bad;Headers\n1;2\n", "Date;Weight\nNot a date;108kg\n", "Date;Weight\n2025-01-27;unknown\n"):
            with self.subTest(content=content), self.assertRaises(HTTPException) as error:
                self.import_csv(content)
            self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(main.get_bodyweight(), [])

    def test_fitdays_skips_invalid_row_and_warns(self):
        result = self.import_csv("Date;Weight;BMI\n2025-01-27;100kg;29\nbad;101kg;30\n2025-01-29;99kg;invalid\n")
        self.assertEqual((result["imported"], result["skipped"]), (2, 1))
        self.assertTrue(result["warnings"])
        self.assertIsNone(main.get_bodyweight()[-1]["metrics"]["bmi"]["value"])

    def test_bodyweight_latest_rows_and_existing_metrics_survive(self):
        self.import_csv("Date;Weight;BMI\n2025-01-27;100kg;29\n2025-01-28;99kg;28\n")
        self.assertEqual(main.get_bodyweight(limit=1)[0]["date"], "2025-01-28")
        self.import_csv("Date;Weight\n2025-01-27;101kg\n")
        row = main.get_bodyweight()[0]
        self.assertEqual(row["weight_kg"], 101)
        self.assertEqual(row["metrics"]["bmi"]["value"], 29)
        main.init_db()
        self.assertEqual(main.get_bodyweight()[0]["metrics"]["bmi"]["value"], 29)


if __name__ == "__main__":
    unittest.main()