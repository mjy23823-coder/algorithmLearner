import json
import os
import shutil
import tempfile
import threading
import unittest
from datetime import date, timedelta
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

from tools import assistant, coach, coach_ai, dashboard

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests/fixtures"
TODAY = date(2026, 10, 17)
GOOD = "这是栈的题。遍历字符串，左括号入栈，右括号时看栈顶是否匹配，不匹配返回 False，最后栈为空才有效。时间 O(n)，空间 O(n)。边界：字符串为空返回 True，只有右括号时栈为空直接返回 False。"


class WorkspaceCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="assistant-")
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.state_path = self.root / "learning-state.json"
        self.log_path = self.root / "learning-log.md"
        shutil.copyfile(FIXTURES / "learning-state.json", self.state_path)
        shutil.copyfile(FIXTURES / "learning-log.md", self.log_path)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC_", "OPENAI_"))}
        patcher = patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.state = coach.load(self.state_path)
        self.pid = next(pid for pid, rec in self.state["completed"].items() if coach.oral_eligible(rec))

    def use_model(self):
        path = coach_ai.settings_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"provider": "openai", "model": "gpt-5"}), encoding="utf-8")


class OralJudgeTests(WorkspaceCase):
    def test_marks_map_to_results_by_fixed_rules(self):
        ok = dict.fromkeys(assistant.ORAL_ITEMS, "ok")
        self.assertEqual(assistant.oral_result(ok), "independent")
        self.assertEqual(assistant.oral_result({**ok, "boundary": "partial"}), "independent")
        self.assertEqual(assistant.oral_result({**ok, "boundary": "partial", "complexity": "partial"}), "hinted")
        self.assertEqual(assistant.oral_result({**ok, "recognition": "missing"}), "hinted")
        self.assertEqual(assistant.oral_result({**ok, "idea": "partial"}), "hinted")
        self.assertEqual(assistant.oral_result({**ok, "idea": "missing"}), "failed")

    def test_model_marks_decide_the_suggestion_not_the_models_own_verdict(self):
        self.use_model()
        reply = '好的：```json\n{"recognition": "ok", "idea": "ok", "complexity": "missing", "boundary": "ok", "result": "independent", "feedback": "思路清楚，复杂度没讲。"}\n```'
        before = self.state_path.read_bytes()
        with patch.object(coach_ai, "ask_model", return_value=reply) as ask:
            judged = assistant.judge_oral(self.root, self.state, self.pid, GOOD, TODAY)
        system, prompt = ask.call_args.args[1], ask.call_args.args[2]
        self.assertEqual(system, assistant.ORAL_SYSTEM)
        self.assertIn(GOOD, prompt)
        self.assertIn(f"LC{self.pid}", prompt)
        self.assertEqual((judged["result"], judged["result_label"], judged["provider"]), ("hinted", "有卡顿", "openai"))
        self.assertEqual(judged["feedback"], "思路清楚，复杂度没讲。")
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_bad_model_reply_and_offline_mode_fall_back_to_a_checklist(self):
        self.use_model()
        with patch.object(coach_ai, "ask_model", return_value="我觉得讲得不错"):
            judged = assistant.judge_oral(self.root, self.state, self.pid, GOOD, TODAY)
        self.assertEqual(judged["provider"], "offline")
        self.assertIn("格式不对", judged["notice"])
        coach_ai.save_settings(self.root, {"provider": "offline", "model": "gpt-5"})
        judged = assistant.judge_oral(self.root, self.state, self.pid, GOOD, TODAY)
        self.assertEqual((judged["marks"], judged["result"]), (dict.fromkeys(assistant.ORAL_ITEMS, "ok"), "independent"))
        thin = assistant.judge_oral(self.root, self.state, self.pid, "用栈来做，遍历字符串一遍，遇到右括号就和栈顶比较，最后判断栈是不是没有元素", TODAY)
        self.assertEqual((thin["marks"]["idea"], thin["marks"]["complexity"], thin["marks"]["boundary"], thin["result"]),
                         ("partial", "missing", "missing", "hinted"))
        self.assertEqual(assistant.judge_oral(self.root, self.state, self.pid, "用栈，遍历一遍就行了", TODAY)["result"], "failed")
        with self.assertRaises(ValueError):
            assistant.judge_oral(self.root, self.state, self.pid, "用栈", TODAY)
        with self.assertRaises(ValueError):
            assistant.judge_oral(self.root, self.state, "9999", GOOD, TODAY)

    def test_oral_record_keeps_the_explanation_and_marks(self):
        marks = {"recognition": "ok", "idea": "ok", "complexity": "partial", "boundary": "ok"}
        rec = coach.record_oral(self.state, self.pid, "independent", TODAY, {"explanation": GOOD, "marks": marks, "judged_by": "openai"})
        self.assertEqual({k: rec["oral"][-1][k] for k in ("explanation", "marks", "judged_by")}, {"explanation": GOOD, "marks": marks, "judged_by": "openai"})
        with self.assertRaises(ValueError):
            coach.record_oral(self.state, self.pid, "independent", TODAY, {"marks": {"idea": "great"}})


class WeeklyAndPlanTests(WorkspaceCase):
    def test_weekly_advice_offline_model_and_failure(self):
        advice = assistant.weekly_advice(self.root, self.state, self.log_path, TODAY)
        self.assertEqual(advice["provider"], "offline")
        self.assertIn("独立完成率", advice["text"])
        self.assertEqual(assistant.current_weekly(self.root, TODAY + timedelta(days=6))["text"], advice["text"])
        self.assertIsNone(assistant.current_weekly(self.root, TODAY + timedelta(days=7)))
        self.use_model()
        with patch.object(coach_ai, "ask_model", return_value="1. 本周节奏稳定。") as ask:
            advice = assistant.weekly_advice(self.root, self.state, self.log_path, TODAY)
        self.assertEqual((advice["text"], advice["model"]), ("1. 本周节奏稳定。", "gpt-5"))
        prompt = ask.call_args.args[2]
        self.assertIn("近期反复错因", prompt)
        self.assertNotIn("class Solution", prompt)
        with patch.object(coach_ai, "ask_model", side_effect=coach_ai.CoachError("连接不到模型服务")):
            advice = assistant.weekly_advice(self.root, self.state, self.log_path, TODAY)
        self.assertEqual(advice["provider"], "offline")
        self.assertIn("改用离线版本", advice["notice"])

    def test_plan_questions_suggest_minutes_without_changing_progress(self):
        before = self.state_path.read_bytes()
        offline = assistant.ask_plan(self.root, self.state, self.log_path, TODAY, 120, "今天只有1个小时，怎么安排？")
        self.assertEqual((offline["minutes"], offline["provider"]), (60, "offline"))
        self.use_model()
        with patch.object(coach_ai, "ask_model", return_value="先做复习，再做推荐新题。\n[[MINUTES:90]]") as ask:
            answer = assistant.ask_plan(self.root, self.state, self.log_path, TODAY, 120, "时间不够，先做哪道？")
        self.assertEqual((answer["reply"], answer["minutes"]), ("先做复习，再做推荐新题。", 90))
        prompt = ask.call_args.args[2]
        self.assertIn("今日任务", prompt)
        self.assertIn("今天只有1个小时", prompt)
        with patch.object(coach_ai, "ask_model", return_value="按现在的安排就好。\n[[MINUTES:120]]"):
            same = assistant.ask_plan(self.root, self.state, self.log_path, TODAY, 120, "要调整吗？")
        self.assertIsNone(same["minutes"])
        self.assertEqual(len(assistant.plan_chat(self.root, TODAY)), 6)
        self.assertEqual(assistant.plan_chat(self.root, TODAY + timedelta(days=1)), [])
        self.assertEqual(self.state_path.read_bytes(), before)
        with self.assertRaises(ValueError):
            assistant.ask_plan(self.root, self.state, self.log_path, TODAY, 120, " ")
        self.assertEqual([assistant.parse_minutes(q) for q in ("半小时", "一个半小时", "两个小时", "90分钟", "随便")], [30, 90, 120, 90, None])


class EndpointTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.server = dashboard.make_server(self.state_path, self.log_path, 0, TODAY)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def call(self, path, payload=None, token=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=30)
        try:
            headers = {"Content-Type": "application/json", **({"X-Coach-Token": token} if token else {})}
            connection.request("POST" if payload is not None else "GET", path, json.dumps(payload).encode() if payload is not None else None, headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_ai_endpoints_are_read_only_and_oral_save_keeps_detail(self):
        _, data = self.call("/api/dashboard")
        token = data["token"]
        self.assertEqual((data["weekly_advice"], data["plan_chat"]), (None, []))
        before = self.state_path.read_bytes()
        status, judged = self.call("/api/oral/judge", {"id": self.pid, "explanation": GOOD}, token)
        self.assertEqual((status, judged["result"]), (200, "independent"))
        self.assertEqual(self.call("/api/oral/judge", {"id": self.pid, "explanation": "短"}, token)[0], 400)
        status, weekly = self.call("/api/weekly/advice", {}, token)
        self.assertEqual(status, 200)
        status, answer = self.call("/api/plan/ask", {"question": "半小时够吗", "minutes": 120}, token)
        self.assertEqual((status, answer["minutes"]), (200, 30))
        self.assertEqual(self.call("/api/plan/ask", {"question": "好", "minutes": 5}, token)[0], 400)
        self.assertEqual(self.state_path.read_bytes(), before)
        _, data = self.call("/api/dashboard")
        self.assertEqual(data["weekly_advice"]["text"], weekly["text"])
        self.assertEqual(len(data["plan_chat"]), 2)
        status, saved = self.call("/api/oral", {"id": self.pid, "result": judged["result"], "explanation": GOOD,
                                                "marks": judged["marks"], "judged_by": judged["provider"], "revision": data["revision"]}, token)
        self.assertEqual(status, 200, saved)
        entry = coach.load(self.state_path)["completed"][self.pid]["oral"][-1]
        self.assertEqual((entry["explanation"], entry["judged_by"]), (GOOD, "offline"))


if __name__ == "__main__":
    unittest.main()
