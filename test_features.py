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

    # --- insight on volume ---

    def test_insight_compares_sets_on_volume_not_weight(self):
        today = date.today()
        self.log(50, 3, (today - timedelta(days=14)).isoformat())
        self.log(30, 5, (today - timedelta(days=7)).isoformat())
        insight = main.get_exercise_insight(self.exercise_id)
        self.assertEqual((insight["trend"], insight["stagnation"]), ("same", 2))
        self.assertEqual(insight["sessions"][0]["best_set"], {"weight": 30, "reps": 5})

    # --- retries, single arm ---

    def test_retry_with_same_client_id_does_not_duplicate_the_set(self):
        entry = main.LogEntry(exercise_id=self.exercise_id, set_nr=1, weight=40, reps=8, client_id="retry-abcdef12")
        first = main.save_log(entry)
        again = main.save_log(entry)
        self.assertEqual(first["id"], again["id"])
        self.assertTrue(again["duplicate"])
        self.assertEqual(len(main.get_today_logs()), 1)

    def test_single_arm_is_stored_and_editable(self):
        saved = main.save_log(main.LogEntry(exercise_id=self.exercise_id, set_nr=1, weight=10, reps=10, single_arm=True))
        self.assertEqual(main.get_today_logs()[0]["single_arm"], 1)
        main.update_log(saved["id"], main.LogUpdate(weight=10, reps=10, single_arm=False))
        self.assertEqual(main.get_today_logs()[0]["single_arm"], 0)

    def test_arm_exercises_get_the_single_arm_option_by_default(self):
        exercises = {item["name"]: item for items in main.get_routines().values() for item in items}
        self.assertTrue(exercises["Bicep Curl (Cable)"]["single_arm_option"])
        self.assertTrue(exercises["Triceps Rope Pushdown"]["single_arm_option"])
        self.assertFalse(exercises["Squat (Barbell)"]["single_arm_option"])

    # --- muscle groups ---

    def test_default_exercises_get_muscles_and_user_choices_survive_restart(self):
        incline = main.get_routines()["Push"][0]
        self.assertEqual((incline["primary_muscles"], incline["secondary_muscles"]),
                         (["chest_upper"], ["shoulder_front", "triceps"]))
        main.update_routine("Push", main.RoutineUpdate(name="Push", exercises=[
            main.RoutineExercise(id=incline["id"], name=incline["name"], primary_muscles=["chest"], secondary_muscles=[])]))
        main.init_db()
        changed = main.get_routines()["Push"][0]
        self.assertEqual((changed["primary_muscles"], changed["secondary_muscles"]), (["chest"], []))

    def test_unknown_muscle_is_rejected_and_new_exercises_are_suggested(self):
        with self.assertRaises(HTTPException):
            main.create_routine(main.RoutineUpdate(name="X", exercises=[
                main.RoutineExercise(name="Curl", primary_muscles=["wings"])]))
        main.create_routine(main.RoutineUpdate(name="Armen", exercises=[main.RoutineExercise(name="dumbbell SHRUGS")]))
        self.assertEqual(main.get_routines()["Armen"][0]["primary_muscles"], ["traps"])

    def test_muscle_stats_count_primary_muscles_only_once_per_group(self):
        routines = main.get_routines()
        bent_row = next(item for item in routines["Pull"] if item["name"].startswith("Bent Over Row"))
        squat = next(item for item in routines["Legs"] if item["name"].startswith("Squat"))
        today = date.today().isoformat()
        for exercise_id, weight, reps in ((bent_row["id"], 50, 10), (squat["id"], 100, 5)):
            main.save_log(main.LogEntry(exercise_id=exercise_id, set_nr=1, weight=weight, reps=reps, log_date=today))
        groups = {item["group"]: item for item in main.get_muscle_stats("week")["groups"]}
        self.assertEqual((groups["Rug"]["volume"], groups["Rug"]["sets"]), (500, 1))
        self.assertEqual(groups["Quadriceps"]["volume"], 500)
        self.assertEqual(groups["Billen"]["volume"], 500)
        self.assertEqual(groups["Hamstrings"]["volume"], 0)
        with self.assertRaises(HTTPException):
            main.get_muscle_stats("decade")

    def test_abs_are_a_statistics_group(self):
        main.create_routine(main.RoutineUpdate(name="Buik", exercises=[main.RoutineExercise(name="Cable Crunch")]))
        crunch = main.get_routines()["Buik"][0]
        self.assertEqual(crunch["primary_muscles"], ["core"])
        main.save_log(main.LogEntry(exercise_id=crunch["id"], set_nr=1, weight=30, reps=15))
        groups = {item["group"]: item for item in main.get_muscle_stats("week")["groups"]}
        self.assertEqual((groups["Buikspieren"]["volume"], groups["Buikspieren"]["sets"]), (450, 1))

    def test_traps_lower_back_adductors_abductors_and_neck_have_their_own_group(self):
        names = ["Dumbbell Shrugs", "Back extension", "Hip adduction (machine)", "Hip abduction (machine)", "Neck curl"]
        main.create_routine(main.RoutineUpdate(name="Rest", exercises=[main.RoutineExercise(name=name) for name in names]))
        today = date.today().isoformat()
        for number, item in enumerate(main.get_routines()["Rest"], start=1):
            main.save_log(main.LogEntry(exercise_id=item["id"], set_nr=1, weight=10 * number, reps=10, log_date=today))
        groups = {item["group"]: item["volume"] for item in main.get_muscle_stats("week")["groups"]}
        self.assertEqual([groups[group] for group in ("Trapezius", "Onderrug", "Adductoren", "Abductoren", "Nek")],
                         [100, 200, 300, 400, 500])
        self.assertEqual(groups["Rug"], 0)

    # --- training overview ---

    def test_session_detail_lists_sets_prs_groups_and_neighbouring_days(self):
        today = date.today()
        earlier = (today - timedelta(days=7)).isoformat()
        self.log(50, 10, earlier)
        self.log(60, 10, today.isoformat(), 1)
        self.log(60, 8, today.isoformat(), 2)
        main.save_cardio(main.CardioEntry(type="Roeien", duration_minutes=15, log_date=today.isoformat()))
        detail = main.get_session(today)
        self.assertEqual(detail["totals"], {"sets": 2, "volume": 1080, "exercises": 1, "prs": detail["totals"]["prs"]})
        self.assertGreaterEqual(detail["totals"]["prs"], 1)
        exercise = detail["exercises"][0]
        self.assertEqual((exercise["volume"], exercise["best"]), (1080, {"weight": 60, "reps": 10}))
        self.assertEqual(exercise["previous"], {"date": earlier, "volume": 500, "best_weight": 50})
        self.assertEqual([item["group"] for item in detail["groups"]], ["Borst"])
        self.assertEqual(detail["cardio"][0]["type"], "Roeien")
        self.assertEqual((detail["previous_date"], detail["next_date"]), (earlier, None))
        self.assertEqual(main.get_session(today - timedelta(days=30))["totals"]["sets"], 0)

    def test_session_list_and_calendar_show_routines(self):
        today = date.today()
        self.log(50, 10, today.isoformat())
        sessions = main.list_sessions()
        self.assertEqual((sessions[0]["date"], sessions[0]["sets"], sessions[0]["routines"]), (today.isoformat(), 1, ["Push"]))
        entry = next(item for item in main.get_dashboard(weeks=4)["calendar"] if item["date"] == today.isoformat())
        self.assertEqual((entry["routines"], entry["tonnage"]), (["Push"], 500))

    def test_muscle_group_detail_lists_exercises_records_and_weekly_volume(self):
        today = date.today().isoformat()
        self.log(60, 10, today)
        detail = main.get_muscle_group("Borst", "week")
        self.assertEqual((detail["total_volume"], detail["total_sets"]), (600, 1))
        self.assertEqual(detail["exercises"][0]["record"]["weight"], 60)
        self.assertEqual(len(detail["weekly"]), 12)
        self.assertEqual(detail["weekly"][-1]["volume"], 600)
        with self.assertRaises(HTTPException):
            main.get_muscle_group("Vleugels")

    # --- schema library ---

    def test_removed_exercises_move_to_the_library_and_can_return(self):
        push = main.get_routines()["Push"]
        keep, removed = push[0], push[1]
        main.update_routine("Push", main.RoutineUpdate(name="Push", exercises=[
            main.RoutineExercise(id=keep["id"], name=keep["name"])]))
        library = main.get_exercise_library()
        self.assertIn(removed["id"], [item["id"] for item in library])
        main.update_routine("Push", main.RoutineUpdate(name="Push", exercises=[
            main.RoutineExercise(id=keep["id"], name=keep["name"]),
            main.RoutineExercise(id=removed["id"], name=removed["name"])]))
        self.assertEqual([item["id"] for item in main.get_routines()["Push"]], [keep["id"], removed["id"]])
        self.assertNotIn(removed["id"], [item["id"] for item in main.get_exercise_library()])

    def test_library_exercise_is_kept_apart_and_names_cannot_repeat(self):
        created = main.add_library_exercise(main.LibraryExercise(name="Dumbbell Shrugs"))
        self.assertEqual(created["primary_muscles"], ["traps"])
        self.assertNotIn("Dumbbell Shrugs", [item["name"] for items in main.get_routines().values() for item in items])
        with self.assertRaises(HTTPException) as error:
            main.add_library_exercise(main.LibraryExercise(name="dumbbell shrugs"))
        self.assertEqual(error.exception.status_code, 409)
        with self.assertRaises(HTTPException):
            main.update_routine("Push", main.RoutineUpdate(name="Push", exercises=[
                main.RoutineExercise(id=main.get_routines()["Pull"][0]["id"], name="Steal")]))


if __name__ == "__main__":
    unittest.main()
