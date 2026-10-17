import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import date
from pathlib import Path

from tools import coach

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests/fixtures"
MANIFEST = ROOT / "data/history-review-2026-10-17.json"
TODAY = date(2026, 10, 17)


class HistoryImportTests(unittest.TestCase):
    def setUp(self):
        self.state = coach.load(FIXTURES / "learning-state.json")
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.log = FIXTURES / "learning-log.md"

    def recover(self, state=None, manifest=None, log=None):
        return coach.prepare_history_import(state or self.state, manifest or self.manifest, log or self.log, TODAY)

    def test_recovers_33_missing_problems_preserving_all_existing_progress(self):
        original = deepcopy(self.state)
        recovered, report = self.recover()
        self.assertEqual((report["before"], report["after"], len(report["added"])), (13, 46, 33))
        self.assertEqual(self.state, original)
        for pid, record in original["completed"].items():
            self.assertEqual(recovered["completed"][pid], record)
        self.assertEqual(recovered["session"], original["session"])
        self.assertEqual(recovered["current_topic"], original["current_topic"])
        self.assertEqual(report["topics"], {"双指针": 9, "BST": 11, "固定窗口": 2, "滑动窗口": 2,
                                           "二叉树": 15, "哈希": 3, "栈": 2, "链表": 2})
        self.assertNotIn("42", recovered["completed"])
        self.assertNotIn("11", recovered["next_new"])

    def test_attempts_oral_reviews_and_next_day_repeats_are_not_inflated(self):
        records = self.recover()[0]["completed"]
        self.assertEqual(records["20"]["count"], 2)
        self.assertEqual((records["102"]["count"], records["102"]["last_done"]), (1, "2026-09-26"))
        self.assertEqual(records["102"]["status"], "needs_review")
        for pid in ("144", "94", "145"):
            self.assertEqual((records[pid]["count"], records[pid]["last_done"]), (1, "2026-09-22"))
        self.assertEqual((records["206"]["count"], records["206"]["status"]), (2, "learning"))
        self.assertEqual((records["543"]["count"], records["543"]["status"]), (2, "learned"))

    def test_unknown_completion_and_independence_remain_uncertain(self):
        records = self.recover()[0]["completed"]
        self.assertEqual((records["977"]["count"], records["977"]["status"]), (0, "needs_calibration"))
        self.assertEqual(records["1"]["status"], "needs_calibration")
        self.assertEqual(records["701"]["last_done"], "2026-10-03")
        self.assertEqual(records["11"]["status"], "needs_review")
        self.assertTrue(records["1"]["count_is_lower_bound"])
        self.assertIn("evidence", records["1"]["history"][0]["source"])

    def test_repeat_import_preserves_newer_user_changes(self):
        recovered, _ = self.recover()
        recovered["completed"]["1"]["note_from_user"] = "新的用户记录"
        again, report = self.recover(state=recovered)
        self.assertFalse(report["added"])
        self.assertEqual(len(report["skipped"]), 33)
        self.assertEqual(again, recovered)

    def test_invalid_evidence_rejects_the_whole_import(self):
        bad = deepcopy(self.manifest)
        bad["records"][-1]["events"][0]["evidence"][0]["text"] = "并不存在的完成记录"
        original = deepcopy(self.state)
        with self.assertRaisesRegex(ValueError, "引用无法验证"):
            self.recover(manifest=bad)
        self.assertEqual(self.state, original)

    def test_duplicate_and_future_dates_are_rejected(self):
        bad = deepcopy(self.manifest)
        bad["records"][0]["events"].append(deepcopy(bad["records"][0]["events"][0]))
        with self.assertRaises(ValueError):
            self.recover(manifest=bad)
        bad["records"][0]["events"][0]["date"] = "2099-01-01"
        with self.assertRaises(ValueError):
            self.recover(manifest=bad)

    def test_append_only_log_growth_is_allowed_but_rewritten_source_is_not(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "learning-log.md"
            log.write_bytes(self.log.read_bytes() + "\n## 2026-10-17｜新记录\n".encode("utf-8"))
            self.assertEqual(self.recover(log=log)[1]["after"], 46)
            log.write_bytes(b"changed" + self.log.read_bytes())
            with self.assertRaisesRegex(ValueError, "日志与核对"):
                self.recover(log=log)

    def test_cli_preview_does_not_write_and_apply_keeps_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "learning-state.json"
            shutil.copyfile(FIXTURES / state.name, state)
            original = state.read_bytes()
            args = [sys.executable, str(ROOT / "tools/coach.py"), "import-history", "--manifest", str(MANIFEST),
                    "--state", str(state), "--log", str(self.log), "--date", str(TODAY)]
            subprocess.run(args, check=True, capture_output=True)
            self.assertEqual(state.read_bytes(), original)
            self.assertFalse(state.with_suffix(".json.bak").exists())
            subprocess.run(args + ["--apply"], check=True, capture_output=True)
            self.assertEqual(len(coach.load(state)["completed"]), 46)
            self.assertEqual(state.with_suffix(".json.bak").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
