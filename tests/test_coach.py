import json
import os
import tempfile
import time
import unittest
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from tools import coach, records, store


TODAY = date(2026, 10, 16)


def empty_state():
    return {"completed": {}, "next_new": ["42", "239"], "review_intervals_days": [3, 7, 21],
            "current_topic": "双指针", "session": {}}


def record(state, result="independent", when=TODAY, pid="42", **kwargs):
    return coach.record_result(state, pid, result, when, "接雨水", "双指针", **kwargs)


class ReviewTests(unittest.TestCase):
    def test_spaced_independent_reviews_follow_3_7_21_days(self):
        state = empty_state()
        first = record(state)
        self.assertEqual((first["count"], first["status"], first["next_due"]), (1, "learning", "2026-10-19"))
        second = record(state, when=TODAY + timedelta(days=3))
        self.assertEqual((second["count"], second["status"], second["next_due"]), (2, "learned", "2026-10-26"))
        third = record(state, when=TODAY + timedelta(days=10))
        self.assertEqual(third["next_due"], "2026-11-16")

    def test_same_day_result_is_replaced_without_extra_completions(self):
        state = empty_state()
        for result, count in [("failed", 0), ("hinted", 1), ("independent", 1), ("independent", 1), ("failed", 0), ("independent", 1)]:
            rec = record(state, result)
            self.assertEqual(rec["count"], count)
            self.assertEqual(len(rec["history"]), 1)
            self.assertNotEqual(rec["status"], "learned")

    def test_failed_attempt_does_not_count_as_completed(self):
        state = empty_state()
        record(state)
        rec = record(state, "failed", TODAY + timedelta(days=3))
        self.assertEqual(rec["count"], 1)
        self.assertEqual(rec["next_due"], "2026-10-20")
        self.assertNotIn("42", state["session"]["last_completed"])
        self.assertGreater(coach.build_plan(state, TODAY + timedelta(days=3))["pending_count"], 0)
        plan = coach.build_plan(state, TODAY + timedelta(days=4))
        self.assertEqual([p["id"] for p in plan["short_recall"]], ["42"])
        self.assertFalse(plan["reviews"])

    def test_hint_resets_interval_and_requires_two_independent_reviews(self):
        state = empty_state()
        record(state)
        record(state, when=TODAY + timedelta(days=3))
        rec = record(state, "hinted", TODAY + timedelta(days=10))
        self.assertEqual(rec["next_due"], "2026-10-29")
        rec = record(state, when=TODAY + timedelta(days=13))
        self.assertEqual((rec["status"], rec["next_due"]), ("learning", "2026-11-01"))
        rec = record(state, when=TODAY + timedelta(days=16))
        self.assertEqual((rec["status"], rec["next_due"]), ("learned", "2026-11-08"))

    def test_next_day_practice_cannot_advance_mastery(self):
        state = empty_state()
        record(state)
        rec = record(state, when=TODAY + timedelta(days=1))
        self.assertEqual(rec["status"], "learning")
        self.assertEqual(rec["next_due"], "2026-10-19")

    def test_same_day_legacy_record_keeps_its_count_on_multiple_updates(self):
        state = empty_state()
        state["completed"]["42"] = {"title": "接雨水", "topic": "双指针", "last_done": str(TODAY), "count": 2, "status": "learned"}
        for result in ("independent", "hinted", "independent"):
            rec = record(state, result)
            self.assertEqual(rec["count"], 2)
            self.assertEqual(len(rec["history"]), 1)

    def test_backdating_requires_explicit_calibration(self):
        state = empty_state()
        record(state)
        original = deepcopy(state)
        with self.assertRaises(ValueError):
            record(state, when=TODAY - timedelta(days=1))
        self.assertEqual(state, original)

    def test_plan_does_not_replenish_tasks_after_completing_them(self):
        state = empty_state()
        record(state, pid="42")
        record(state, pid="239")
        state["next_new"].extend(["15", "16"])
        plan = coach.build_plan(state, TODAY, 120)
        self.assertEqual(len(plan["tasks"]), 2)
        self.assertTrue(all(p["recorded"] for p in plan["tasks"]))

    def test_due_sort_and_calibration_do_not_pollute_new_task_slots(self):
        state = empty_state()
        for pid, due in [("26", "2026-10-15"), ("3", "2026-10-16")]:
            state["completed"][pid] = {"title": pid, "topic": "双指针", "count": 1, "status": "learning", "last_done": "2026-10-12", "next_due": due}
        state["completed"]["209"] = {"title": "长度最小的子数组", "topic": "滑动窗口", "count": 1, "status": "needs_calibration", "last_done": "2026-10-13"}
        state["next_new"] = ["209", "11", "42", "239"]
        plan = coach.build_plan(state, TODAY, 120, {"11"})
        self.assertEqual([p["id"] for p in plan["tasks"]], ["26", "3", "42", "239"])
        self.assertEqual({p["id"] for p in plan["calibration"]}, {"209", "11"})
        self.assertEqual(plan["deferred"], [])

    def test_empty_review_queue_on_short_day_still_offers_one_task(self):
        plan = coach.build_plan(empty_state(), TODAY, 30)
        self.assertEqual([p["id"] for p in plan["tasks"]], ["42"])

    def test_completed_calibration_consumes_review_quota(self):
        state=empty_state()
        state["completed"]["42"]={"title":"接雨水","topic":"双指针","count":1,"last_done":"2026-10-10","status":"needs_calibration"}
        state["completed"]["26"]={"title":"删除重复项","topic":"双指针","count":1,"last_done":"2026-10-10","status":"learning"}
        record(state)
        plan=coach.build_plan(state,TODAY,90)
        self.assertEqual(plan["done_today"][0]["kind"],"calibration")
        self.assertNotIn("26",[p["id"] for p in plan["tasks"]])

    def test_invalid_id_and_minutes_are_rejected(self):
        for pid in ("0", "../secret", "1;exit", "-1", "1.0"):
            with self.assertRaises(ValueError):
                record(empty_state(), pid=pid)
        for minutes in (0, -1, True, "30", 1441):
            with self.assertRaises(ValueError):
                record(empty_state(), minutes=minutes)


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="algorithm-tests-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "learning-state.json"
        self.log = self.path.with_name("learning-log.md")
        self.path.write_text(json.dumps(empty_state(), ensure_ascii=False), encoding="utf-8")
        self.log.write_bytes("# 原有日志\r\n保持原始内容。\r\n".encode("utf-8"))

    def test_save_backs_up_and_rejects_stale_state(self):
        original = self.path.read_bytes()
        first, stale = coach.load(self.path), coach.load(self.path)
        record(first)
        coach.save(self.path, first)
        self.assertEqual(self.path.with_suffix(".json.bak").read_bytes(), original)
        record(stale, pid="239")
        with self.assertRaises(ValueError):
            coach.save(self.path, stale)
        self.assertNotIn("239", coach.load(self.path)["completed"])

    def test_stale_lock_left_by_crash_is_cleared(self):
        lock = self.path.with_name(self.path.name + ".lock")
        lock.write_text("", encoding="utf-8")
        old = time.time() - coach.STALE_LOCK_SECONDS - 5
        os.utime(lock, (old, old))
        state = coach.load(self.path)
        record(state)
        coach.save(self.path, state)
        self.assertFalse(lock.exists())
        self.assertIn("42", coach.load(self.path)["completed"])

    def test_fresh_lock_still_blocks_writes(self):
        lock = self.path.with_name(self.path.name + ".lock")
        lock.write_text("", encoding="utf-8")
        with patch.object(store.time, "sleep"), self.assertRaises(ValueError):
            with coach.file_lock(self.path):
                pass
        self.assertTrue(lock.exists())

    def test_daily_backups_keep_the_start_of_each_day_for_14_days(self):
        original = self.path.read_bytes()
        folder = self.path.parent / "backups"
        folder.mkdir()
        for i in range(16):
            (folder / f"learning-state-2026-09-{i + 1:02d}.json").write_text("{}", encoding="utf-8")
        state = coach.load(self.path)
        record(state)
        coach.save(self.path, state)
        state = coach.load(self.path)
        record(state, pid="239")
        coach.save(self.path, state)
        snapshots = sorted(p.name for p in folder.iterdir())
        self.assertEqual(len(snapshots), coach.BACKUP_DAYS)
        today = folder / f"learning-state-{date.today().isoformat()}.json"
        # 当天第二次保存不覆盖：快照是当天第一次修改前的进度。
        self.assertEqual(today.read_bytes(), original)
        self.assertNotIn("learning-state-2026-09-01.json", snapshots)

    def test_wrap_commits_only_learning_data_to_the_local_git_repo(self):
        import shutil
        import subprocess
        if not shutil.which("git"):
            self.skipTest("没有 git")
        root = self.path.parent

        def git(*args):
            return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", check=True).stdout

        git("init", "-q", "-b", "main")
        git("config", "user.name", "test")
        git("config", "user.email", "test@localhost")
        (root / "notes.txt").write_text("v1", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "初始")
        (root / "notes.txt").write_text("v2", encoding="utf-8")
        git("add", "notes.txt")
        state = coach.load(self.path)
        record(state)
        coach.save(self.path, state)
        result = coach.wrap_session(state, self.path, self.log, TODAY, "今天练了双指针")
        self.assertEqual(result["git"], "已提交到本地 git")
        self.assertIn("已提交到本地 git", result["message"])
        self.assertEqual(git("log", "-1", "--format=%s").strip(), f"学习记录 {TODAY.isoformat()}")
        self.assertEqual(sorted(git("show", "--name-only", "--format=", "HEAD").split()), ["learning-log.md", "learning-state.json"])
        # 用户自己暂存的其他改动不被带进学习记录的提交。
        self.assertIn("M  notes.txt", git("status", "--porcelain"))
        self.assertEqual(coach.commit_learning_data(root, TODAY), "学习数据没有新变化，无需提交")

    def test_wrap_appends_once_and_preserves_historical_bytes(self):
        original = self.log.read_bytes()
        state = coach.load(self.path)
        record(state, note="先算面积再移动指针")
        coach.save(self.path, state)
        first = coach.wrap_session(state, self.path, self.log, TODAY, "变量要解释清楚", "按复习队列继续")
        second = coach.wrap_session(coach.load(self.path), self.path, self.log, TODAY, "变量要解释清楚", "按复习队列继续")
        self.assertTrue(first["saved"])
        self.assertFalse(second["saved"])
        content = self.log.read_bytes()
        self.assertTrue(content.startswith(original))
        self.assertEqual(content.count(b"<!-- algo-wrap:"), 1)
        self.assertIn("2026-10-19", content.decode("utf-8"))

    def test_wrap_rolls_back_log_when_state_write_fails(self):
        state = coach.load(self.path)
        record(state)
        coach.save(self.path, state)
        original_state, original_log = self.path.read_bytes(), self.log.read_bytes()
        original_write = records.atomic_write

        def failing_write(path, content):
            if path == self.path:
                raise OSError("simulated full disk")
            original_write(path, content)

        with patch.object(records, "atomic_write", side_effect=failing_write):
            with self.assertRaises(OSError):
                coach.wrap_session(state, self.path, self.log, TODAY, "今日总结")
        self.assertEqual(self.path.read_bytes(), original_state)
        self.assertEqual(self.log.read_bytes(), original_log)


if __name__ == "__main__":
    unittest.main()
