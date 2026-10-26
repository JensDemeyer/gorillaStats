import sqlite3
import unittest
from datetime import date, timedelta

from main import get_rewards


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


if __name__ == "__main__":
    unittest.main()