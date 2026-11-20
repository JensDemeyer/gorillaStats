import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

import main


class BackendFeatureTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(main, "DB_FILE", Path(self.directory.name) / "gym.db")
        self.db_patch.start()
        main.init_db()
        self.exercise_id = main.get_routines()["Push"][0]["id"]

    def tearDown(self):
        self.db_patch.stop()
        self.directory.cleanup()

    def weigh(self, kg, day=None):
        main.save_bodyweight(main.BodyweightEntry(weight_kg=kg, log_date=(day or date.today()).isoformat()))

    def log(self, weight, reps, day, set_nr=1):
        main.save_log(main.LogEntry(exercise_id=self.exercise_id, set_nr=set_nr, weight=weight, reps=reps, log_date=day))

    # --- settings and BMI ---

    def test_bmi_uses_190_cm_by_default_and_reports_distance_to_healthy_range(self):
        self.assertIsNone(main.get_settings()["bmi"])
        self.weigh(100)
        summary = main.get_settings()
        self.assertEqual(summary["height_cm"], 190)
        self.assertEqual(summary["bmi"], 27.7)
        self.assertEqual(summary["bmi_category"], "Overgewicht")
        self.assertEqual(summary["healthy_max_kg"], 89.9)
        self.assertEqual(summary["to_healthy_kg"], 10.1)

    def test_goal_weight_tracks_progress_from_the_weight_at_goal_time(self):
        self.weigh(100)
        main.update_settings(main.SettingsUpdate(goal_weight_kg=90))
        self.weigh(95, date.today() + timedelta(days=1))
        summary = main.get_settings()
        self.assertEqual((summary["goal_start_kg"], summary["goal_remaining_kg"], summary["goal_progress"]), (100, 5, 0.5))
        main.update_settings(main.SettingsUpdate(clear_goal=True))
        self.assertIsNone(main.get_settings()["goal_weight_kg"])
        main.update_settings(main.SettingsUpdate(height_cm=180))
        self.assertEqual(main.get_settings()["height_cm"], 180)
        with self.assertRaises(ValidationError):
            main.SettingsUpdate(height_cm=20)

    # --- cardio ---

    def treadmill(self, minutes, speed, incline):
        return main.CardioSegment(minutes=minutes, speed_kmh=speed, incline_pct=incline)

    def test_treadmill_calories_follow_acsm_with_incline_and_stages(self):
        flat = main.estimate_cardio("Loopband", [self.treadmill(60, 5, 0)], 100)
        steep = main.estimate_cardio("Loopband", [self.treadmill(60, 5, 15)], 100)
        # 5 km/h flat: VO2 = 0.1 * 83.33 + 3.5 = 11.83 ml/kg/min = 3.38 MET.
        self.assertAlmostEqual(flat["average_met"], 3.38, places=2)
        self.assertEqual(flat["kcal"], 355)
        self.assertGreater(steep["kcal"], flat["kcal"] * 2)
        stages = main.estimate_cardio("Loopband", [self.treadmill(15, 5.5, 15), self.treadmill(5, 5, 0)], 105)
        self.assertEqual(stages["minutes"], 20)
        self.assertEqual(stages["distance_km"], 1.79)
        self.assertEqual(stages["kcal"], sum(item["kcal"] for item in stages["segments"]))

    def test_running_uses_the_running_equation_and_other_types_use_met_tables(self):
        run = main.estimate_cardio("Loopband", [self.treadmill(30, 10, 0)], 80)
        self.assertAlmostEqual(run["average_met"], 10.52, places=2)
        rowing = main.estimate_cardio("Roeien", [main.CardioSegment(minutes=30, intensity="zwaar")], 80)
        self.assertEqual(rowing["kcal"], round(8.5 * 80 * 30 * main.KCAL_PER_MET_KG_MINUTE))
        self.assertIsNone(main.estimate_cardio("Roeien", [main.CardioSegment(minutes=30)], None)["kcal"])

    def test_cardio_is_saved_with_stages_and_estimated_calories(self):
        self.weigh(100)
        result = main.save_cardio(main.CardioEntry(
            type="Loopband", segments=[self.treadmill(15, 5.5, 15), self.treadmill(5, 5, 0)]))
        row = main.get_cardio()[0]
        self.assertEqual(row["duration_minutes"], 20)
        self.assertEqual(row["calories"], result["calories"])
        self.assertGreater(row["calories"], 150)
        self.assertEqual(len(row["segments"]), 2)
        self.assertEqual(row["segments"][0]["incline_pct"], 15)
        self.assertEqual(row["distance_km"], 1.79)

    def test_legacy_cardio_entry_and_manual_calories_still_work(self):
        self.weigh(80)
        main.save_cardio(main.CardioEntry(type="Loopband", duration_minutes=30, distance_km=3))
        self.assertEqual(main.get_cardio()[0]["calories"], round(main.treadmill_met(6, 0) * 80 * 30 * main.KCAL_PER_MET_KG_MINUTE))
        main.save_cardio(main.CardioEntry(type="Roeien", duration_minutes=20, calories=222))
        self.assertEqual(main.get_cardio()[0]["calories"], 222)
        with self.assertRaises(HTTPException):
            main.save_cardio(main.CardioEntry(type="Roeien"))
        with self.assertRaises(HTTPException):
            main.save_cardio(main.CardioEntry(type="Roeien", duration_minutes=5, log_date="gisteren"))

    # --- routines ---

    def test_new_routine_is_created_in_one_step_and_cannot_duplicate(self):
        result = main.create_routine(main.RoutineUpdate(name="Armen", exercises=[
            main.RoutineExercise(name="Curl"), main.RoutineExercise(name="Dips")]))
        self.assertEqual(result["name"], "Armen")
        self.assertEqual([item["name"] for item in main.get_routines()["Armen"]], ["Curl", "Dips"])
        with self.assertRaises(HTTPException) as error:
            main.create_routine(main.RoutineUpdate(name="Armen", exercises=[main.RoutineExercise(name="Curl")]))
        self.assertEqual(error.exception.status_code, 409)
        with self.assertRaises(HTTPException):
            main.create_routine(main.RoutineUpdate(name="  ", exercises=[main.RoutineExercise(name="Curl")]))

    # --- dashboard and insight ---

    def test_dashboard_counts_active_days_per_week(self):
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        for offset in range(0, 3):
            day = (monday - timedelta(weeks=1) + timedelta(days=offset)).isoformat()
            for set_nr in (1, 2, 3):
                self.log(50, 10, day, set_nr)
        main.save_cardio(main.CardioEntry(type="Roeien", duration_minutes=15, log_date=(monday - timedelta(weeks=2)).isoformat()))
        data = main.get_dashboard(weeks=4)
        self.assertEqual(len(data["weeks"]), 4)
        self.assertEqual([week["active_days"] for week in data["weeks"]], [0, 1, 3, 0])
        self.assertEqual(data["weeks"][2]["tonnage"], 4500)
        self.assertEqual(data["weeks"][1]["cardio_minutes"], 15)
        self.assertTrue(data["weeks"][-1]["current"])
        self.assertEqual(data["best_week_days"], 3)

    def test_insight_detects_stagnation_and_ignores_estimates_and_today(self):
        today = date.today()
        for days_ago, weight in ((21, 50), (14, 60), (7, 60), (3, 60)):
            self.log(weight, 8, (today - timedelta(days=days_ago)).isoformat())
        self.log(100, 8, today.isoformat())
        main.save_workout(main.WorkoutEntry(log_date=today - timedelta(days=1), exercises=[
            main.WorkoutExercise(exercise_id=self.exercise_id, sets=3)]))
        insight = main.get_exercise_insight(self.exercise_id)
        self.assertEqual([item["max_weight"] for item in insight["sessions"]], [60, 60, 60, 50])
        self.assertEqual((insight["stagnation"], insight["trend"], insight["days_since"]), (3, "same", 3))
        self.assertEqual(insight["best_weight"], 100)
        self.assertEqual(main.get_exercise_insight(main.get_routines()["Pull"][0]["id"])["trend"], "new")

    def test_insight_counts_consecutive_improvements(self):
        today = date.today()
        for days_ago, weight in ((21, 40), (14, 45), (7, 50)):
            self.log(weight, 8, (today - timedelta(days=days_ago)).isoformat())
        insight = main.get_exercise_insight(self.exercise_id)
        self.assertEqual((insight["trend"], insight["climbing"], insight["stagnation"]), ("up", 2, 1))


if __name__ == "__main__":
    unittest.main()
