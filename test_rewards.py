import sqlite3
import unittest
from datetime import date, timedelta

from main import LEVEL_PHASES, get_level_progression, get_rewards


class RewardsTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE exercises (id INTEGER, routine TEXT);
            CREATE TABLE logs (date TEXT, exercise_id INTEGER);
            CREATE TABLE cardio_logs (date TEXT, duration_minutes REAL);
            CREATE TABLE bodyweight_logs (date TEXT);
            INSERT INTO exercises VALUES (1, 'Push'), (2, 'Pull'), (3, 'Legs');
        """)
        self.today = date(2026, 10, 26)

    def tearDown(self):
        self.conn.close()

    def log_day(self, logged, sets=3, exercise_id=1):
        self.conn.executemany("INSERT INTO logs VALUES (?, ?)",
                              [(logged.isoformat(), exercise_id)] * sets)

    def rewards(self):
        return get_rewards(self.conn, self.today)

    def test_empty(self):
        result = self.rewards()
        self.assertEqual((result["xp"], result["level"], result["weekly_streak"]), (0, 1, 0))
        self.assertFalse(any(item["unlocked"] for item in result["achievements"]))
        self.assertEqual(len(result["calendar"]), 28)

    def test_first_activity_and_xp_cap(self):
        self.log_day(self.today)
        self.assertEqual(self.rewards()["xp"], 120)
        self.log_day(self.today, sets=20)
        self.assertEqual(self.rewards()["today_xp"], 160)
        self.assertEqual(self.rewards()["weekly_days"], 1)

    def test_cardio_and_strength_count_as_one_day(self):
        self.log_day(self.today)
        self.conn.execute("INSERT INTO cardio_logs VALUES (?, 10)", (self.today.isoformat(),))
        result = self.rewards()
        self.assertEqual(result["weekly_days"], 1)
        self.assertEqual(result["today_xp"], 100)

    def test_small_logs_do_not_count_as_active_day(self):
        self.log_day(self.today, sets=2)
        self.conn.execute("INSERT INTO cardio_logs VALUES (?, 9)", (self.today.isoformat(),))
        self.assertEqual(self.rewards()["weekly_days"], 0)

    def test_rest_days_and_new_week_preserve_streak(self):
        for weeks_ago in (1, 2, 3, 4):
            monday = self.today - timedelta(weeks=weeks_ago)
            for offset in (0, 2, 4):
                self.log_day(monday + timedelta(days=offset))
        result = self.rewards()
        self.assertEqual((result["weekly_streak"], result["best_weekly_streak"]), (4, 4))
        self.assertTrue(next(item for item in result["achievements"] if item["id"] == "weeks4")["unlocked"])
        self.log_day(self.today)
        self.today += timedelta(days=2)
        self.log_day(self.today)
        self.today += timedelta(days=2)
        self.log_day(self.today)
        self.assertEqual(self.rewards()["weekly_streak"], 5)

    def test_missed_week_resets_current_not_best(self):
        for weeks_ago in (2, 3):
            for offset in (0, 2, 4):
                self.log_day(self.today - timedelta(weeks=weeks_ago) + timedelta(days=offset))
        self.assertEqual(self.rewards()["weekly_streak"], 0)
        self.assertEqual(self.rewards()["best_weekly_streak"], 2)

    def test_future_data_ignored_and_deletion_recalculates(self):
        self.log_day(self.today + timedelta(days=1), sets=100)
        self.assertEqual(self.rewards()["xp"], 0)
        self.log_day(self.today)
        self.conn.execute("DELETE FROM logs WHERE date = ?", (self.today.isoformat(),))
        self.assertEqual(self.rewards()["xp"], 0)

    def test_weighing_only_and_routine_quest(self):
        self.conn.execute("INSERT INTO bodyweight_logs VALUES (?)", (self.today.isoformat(),))
        self.assertEqual(self.rewards()["xp"], 10)
        self.assertEqual(self.rewards()["weekly_days"], 0)
        for exercise_id in (1, 2, 3):
            self.log_day(self.today, exercise_id=exercise_id)
        self.assertEqual(self.rewards()["quests"][2]["progress"], 3)

    def test_all_rank_and_phase_boundaries(self):
        names = [name for _, _, ranks in LEVEL_PHASES for name, _ in ranks]
        self.assertEqual(len(names), 25)
        self.assertEqual(names[0], "Baby Gorillatje")
        self.assertEqual(names[-1], "Ultra Alfa Gorilla")
        for level, name in enumerate(names, start=1):
            with self.subTest(level=level):
                threshold = (level - 1) * 500
                result = get_level_progression(threshold)
                self.assertEqual((result["level"], result["rank"]), (level, name))
                self.assertEqual(result["phase_number"], (level - 1) // 5 + 1)
                self.assertEqual(sum(item["unlocked"] for item in result["phase_achievements"]), level // 5)
                self.assertEqual(sum(rank["current"] for phase in result["journey"] for rank in phase["levels"]), 1)
                self.assertEqual(result["is_max_level"], level == 25)
                if level > 1:
                    self.assertEqual(get_level_progression(threshold - 1)["level"], level - 1)

    def test_journey_previews_all_future_levels(self):
        result = get_level_progression(0)
        self.assertEqual(len(result["journey"]), 5)
        self.assertEqual([phase["end_level"] for phase in result["journey"]], [5, 10, 15, 20, 25])
        ranks = [rank for phase in result["journey"] for rank in phase["levels"]]
        self.assertEqual(sum(rank["unlocked"] for rank in ranks), 1)
        self.assertTrue(all(rank["description"] for rank in ranks))
        self.assertEqual(ranks[-1]["xp_required"], 12000)

    def test_final_rank_caps_level_but_keeps_total_xp(self):
        for xp in (12000, 12500, 100000):
            with self.subTest(xp=xp):
                result = get_level_progression(xp)
                self.assertEqual((result["level"], result["rank"]), (25, "Ultra Alfa Gorilla"))
                self.assertEqual(result["level_xp"], result["next_level_xp"])
                self.assertTrue(all(item["unlocked"] for item in result["phase_achievements"]))

    def test_phase_badges_do_not_add_xp_and_recalculate(self):
        for offset in range(14):
            self.log_day(self.today - timedelta(days=offset), sets=12)
        result = self.rewards()
        self.assertEqual((result["xp"], result["level"]), (2490, 5))
        self.assertEqual(len(result["achievements"]), 17)
        self.assertEqual(len({item["id"] for item in result["achievements"]}), 17)
        phases = [item for item in result["achievements"] if item.get("category") == "phase"]
        self.assertTrue(phases[0]["unlocked"])
        self.assertFalse(phases[1]["unlocked"])
        self.assertTrue(all(item["xp"] == 0 for item in phases))
        self.assertEqual(self.rewards()["xp"], result["xp"])
        self.conn.execute("DELETE FROM logs")
        reset = self.rewards()
        self.assertEqual((reset["level"], reset["rank"]), (1, "Baby Gorillatje"))
        self.assertFalse(any(item["unlocked"] for item in reset["achievements"]))


if __name__ == "__main__":
    unittest.main()