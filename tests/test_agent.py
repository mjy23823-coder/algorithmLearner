import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from datetime import date
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from tools import agent, coach, coach_ai, dashboard, workbench
from reference_solutions import solution

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests/fixtures"
TODAY = date(2026, 10, 17)
BUGGY_209 = """class Solution:
    def minSubArrayLen(self, target, nums):
        left = total = 0
        best = len(nums) + 1
        for right, x in enumerate(nums):
            total += x
            while total == target:
                best = min(best, right - left + 1)
                total -= nums[left]
                left += 1
        return 0 if best > len(nums) else best
"""
REFERENCE_209 = """class Solution:
    def minSubArrayLen(self, target, nums):
        best = 0
        for i in range(len(nums)):
            s = 0
            for j in range(i, len(nums)):
                s += nums[j]
                if s >= target:
                    best = j - i + 1 if not best else min(best, j - i + 1)
                    break
        return best
"""
GENERATOR_209 = "import random\ndef make(i):\n    return [random.randint(1, 12), [random.randint(1, 5) for _ in range(random.randint(1, 6))]]\n"


class FakeClaude(BaseHTTPRequestHandler):
    calls, script = [], []

    def respond(self, status, data):
        raw = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        FakeClaude.calls.append({"method": "GET", "path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}})
        self.respond(200, {"object": "list", "data": [{"id": "claude-opus-5-5"}, {"id": "claude-sonnet-5-5"}, {"id": "bad name!"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeClaude.calls.append({"method": "POST", "path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
        status, data = FakeClaude.script.pop(0) if FakeClaude.script else (200, {"content": [{"type": "text", "text": "连接正常"}], "stop_reason": "end_turn"})
        self.respond(status, data)

    def log_message(self, *args):
        pass


class FakeOpenAI(BaseHTTPRequestHandler):
    """模拟 CPA 的 OpenAI 兼容接口：GET /v1/models、POST /v1/chat/completions。"""
    calls, script = [], []
    respond, log_message = FakeClaude.respond, FakeClaude.log_message

    def do_GET(self):
        FakeOpenAI.calls.append({"method": "GET", "path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}})
        self.respond(200, {"object": "list", "data": [{"id": "gpt-5", "object": "model"}, {"id": "gpt-5-codex", "object": "model"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOpenAI.calls.append({"method": "POST", "path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
        self.respond(*(FakeOpenAI.script.pop(0) if FakeOpenAI.script else chat("连接正常")))


def chat(text, finish="stop"):
    return (200, {"id": "chatcmpl-test", "object": "chat.completion",
                  "choices": [{"index": 0, "finish_reason": finish, "message": {"role": "assistant", "content": text}}]})


def tool_calls(*items):
    """items 为 (调用编号, 工具名, 参数)；参数是字典时按 OpenAI 的习惯编码成 JSON 字符串，是字符串时原样发送。"""
    calls = [{**({"id": uid} if uid else {}), "type": "function",
              "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else args}}
             for uid, name, args in items]
    return (200, {"choices": [{"index": 0, "finish_reason": "tool_calls", "message": {"role": "assistant", "content": None, "tool_calls": calls}}]})


def tool_use(uid, name, payload, text="我先用工具看看。"):
    return (200, {"stop_reason": "tool_use", "content": [{"type": "thinking", "thinking": "", "signature": "sig-" + uid},
                                                         {"type": "text", "text": text},
                                                         {"type": "tool_use", "id": uid, "name": name, "input": payload}]})


def final(text):
    return (200, {"stop_reason": "end_turn", "content": [{"type": "text", "text": text}]})


class FakeServerCase(unittest.TestCase):
    handler = FakeClaude

    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.handler.calls, self.handler.script = [], []
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        env = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC_", "OPENAI_"))}
        patcher = patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.temp = tempfile.TemporaryDirectory(prefix="agent-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state_path = self.root / "learning-state.json"
        self.log_path = self.root / "learning-log.md"
        shutil.copyfile(FIXTURES / "learning-state.json", self.state_path)
        shutil.copyfile(FIXTURES / "learning-log.md", self.log_path)


class SettingsTests(FakeServerCase):
    def test_cpa_address_key_and_models(self):
        self.assertEqual(coach_ai.normalize_base("https://vps.example.com:8317/v1/"), "https://vps.example.com:8317")
        self.assertEqual(coach_ai.normalize_base("http://1.2.3.4:8317/v1/messages"), "http://1.2.3.4:8317")
        with self.assertRaises(ValueError):
            coach_ai.normalize_base("vps.example.com:8317")
        with self.assertRaises(ValueError):
            coach_ai.save_settings(self.root, {"provider": "anthropic", "model": "claude-opus-5-5", "base_url": self.base})
        self.assertFalse(coach_ai.settings_path(self.root).exists())
        saved = coach_ai.save_settings(self.root, {"provider": "anthropic", "model": "claude-sonnet-4-5-20250929",
                                                   "base_url": self.base + "/v1", "api_key": "sk-cpa-1234567890"})
        self.assertEqual((saved["base_url"], saved["has_key"], saved["key_hint"]), (self.base, True, "…7890"))
        self.assertNotIn("sk-cpa-1234567890", json.dumps(saved))
        self.assertNotIn("sk-cpa", coach_ai.settings_path(self.root).read_text(encoding="utf-8"))
        # 只改模型时保留已保存的 Key。
        coach_ai.save_settings(self.root, {"provider": "anthropic", "model": "claude-opus-5-5", "api_key": ""})
        conn = coach_ai.connection(self.root)
        self.assertEqual((conn["base_url"], conn["headers"]), (self.base, {"x-api-key": "sk-cpa-1234567890"}))
        self.assertEqual(coach_ai.list_models(conn), ["claude-opus-5-5", "claude-sonnet-5-5"])
        self.assertEqual(FakeClaude.calls[-1]["headers"]["authorization"], "Bearer sk-cpa-1234567890")

    def test_dashboard_test_endpoint_saves_only_after_success(self):
        server = dashboard.make_server(self.state_path, self.log_path, 0, TODAY)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        def call(path, payload=None, token=None):
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=20)
            headers = {"Content-Type": "application/json", **({"X-Coach-Token": token} if token else {})}
            connection.request("POST" if payload is not None else "GET", path, json.dumps(payload).encode() if payload is not None else None, headers)
            response = connection.getresponse()
            return json.loads(response.read())

        token = call("/api/dashboard")["token"]
        FakeClaude.script = [(401, {"type": "error", "error": {"type": "authentication_error", "message": "bad key"}})]
        failed = call("/api/coach/test", {"provider": "anthropic", "model": "claude-opus-5-5", "base_url": self.base, "api_key": "wrong"}, token)
        self.assertFalse(failed["ok"])
        self.assertIn("api-keys", failed["error"])
        self.assertEqual(call("/api/coach/settings")["provider"], "offline")
        ok = call("/api/coach/test", {"provider": "anthropic", "model": "claude-opus-5-5", "base_url": self.base + "/v1", "api_key": "sk-cpa-good-key"}, token)
        self.assertTrue(ok["ok"], ok)
        settings = call("/api/coach/settings")
        self.assertEqual((settings["provider"], settings["base_url"], settings["has_key"]), ("anthropic", self.base, True))
        self.assertEqual(FakeClaude.calls[-1]["headers"]["x-api-key"], "sk-cpa-good-key")
        models = call("/api/coach/models", {"base_url": "", "api_key": ""}, token)
        self.assertEqual(models["models"], ["claude-opus-5-5", "claude-sonnet-5-5"])


class AgentLoopTests(FakeServerCase):
    def setUp(self):
        super().setUp()
        coach_ai.save_settings(self.root, {"provider": "anthropic", "model": "claude-opus-5-5", "base_url": self.base, "api_key": "sk-cpa-test-key"})
        self.store = workbench.Workbench(self.root, self.log_path)
        self.state = coach.load(self.state_path)
        self.payload = {"id": "209", "code": BUGGY_209, "extra_cases": [], "draft_revision": None, "elapsed_seconds": 30,
                        "idea": "滑动窗口，和满足条件就收缩", "takeaway": "", "error_tags": []}

    def wait(self, job_id, pid="209"):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            view = self.store.agents.status(pid, job_id)
            if view["status"] != "running":
                return view
            time.sleep(0.1)
        self.fail("智能体任务没有结束")

    def test_tool_loop_counts_counterexample_before_tests_pass(self):
        FakeClaude.script = [
            tool_use("t1", "run_tests", {"extra_cases": [{"name": "刚好超过", "args": [4, [5]], "expected": 1}]}),
            tool_use("t2", "find_counterexample", {"reference_code": REFERENCE_209, "generator_code": GENERATOR_209, "count": 150}),
            final("在输入 target=1, nums=[5,1] 时你的代码返回 0，期望 1。看看窗口条件和题目要求的“至少”是否一致。\n[[ASSIST:yes]]"),
        ]
        started = self.store.agents.start(self.state, {**self.payload, "action": "counterexample"})
        view = self.wait(started["job_id"])
        self.assertEqual(view["status"], "done", view)
        self.assertEqual([s["tool"] for s in view["steps"]], ["run_tests", "find_counterexample"])
        self.assertTrue(all(s["status"] == "done" for s in view["steps"]), view["steps"])
        self.assertIn("不一致", view["steps"][1]["summary"])
        self.assertTrue(view["result"]["counted"])
        self.assertNotIn("[[ASSIST", view["result"]["reply"])
        first, second, third = [c for c in FakeClaude.calls if c["method"] == "POST"]
        self.assertEqual(first["body"]["output_config"], {"effort": "medium"})
        self.assertEqual([t["name"] for t in first["body"]["tools"]], ["run_tests", "find_counterexample", "measure_complexity", "draft_record"])
        self.assertIn(BUGGY_209.strip(), first["body"]["messages"][0]["content"])
        # 模型返回的内容块（包括 thinking）原样回传，工具结果对应 tool_use_id。
        self.assertEqual(second["body"]["messages"][1]["content"][0], {"type": "thinking", "thinking": "", "signature": "sig-t1"})
        result_block = second["body"]["messages"][2]["content"][0]
        self.assertEqual((result_block["type"], result_block["tool_use_id"]), ("tool_result", "t1"))
        self.assertIn('"passed_count"', result_block["content"])
        self.assertIn("mismatches", third["body"]["messages"][-1]["content"][0]["content"])
        draft = self.store.read_draft("209")
        self.assertEqual(self.store.agent_hints("209", draft["session_id"]), 1)
        self.assertEqual(self.store.describe(self.state, "209")["coach"]["agent_hints"], 1)
        fixed = {**self.payload, "code": solution("209"), "draft_revision": draft["revision"]}
        run = self.store.run(fixed, TODAY)
        result = self.store.complete(self.state, {**fixed, "run_id": run["run_id"], "result": "independent"}, TODAY)
        self.assertEqual(result["result"], "hinted")

    def test_report_only_reply_does_not_count_and_draft_is_a_suggestion(self):
        draft = self.store.save_draft({**self.payload, "code": solution("209")})
        self.store.run({**self.payload, "code": solution("209"), "draft_revision": draft["revision"]}, TODAY)
        original = self.state_path.read_bytes()
        FakeClaude.script = [
            tool_use("m1", "measure_complexity", {"generator_code": "import random\ndef make(n):\n    return [n, [random.randint(1, 5) for _ in range(n)]]\n", "sizes": [2000, 4000, 8000]}),
            tool_use("d1", "draft_record", {"result": "independent", "error_tags": ["window_condition", "made_up"], "takeaway": "满足至少 target 后持续收缩",
                                            "time_complexity": "O(n)", "why": "测试全部通过"}),
            final("实测时间随规模大致线性增长，与 O(n) 相符；已草拟记录。\n[[ASSIST:no]]"),
        ]
        view = self.wait(self.store.agents.start(self.state, {**self.payload, "code": solution("209"), "action": "draft"})["job_id"])
        self.assertEqual(view["status"], "done", view)
        self.assertFalse(view["result"]["counted"])
        self.assertIn("增长约 n^", view["steps"][0]["summary"])
        suggestion = view["result"]["suggestion"]
        self.assertEqual((suggestion["result"], suggestion["error_tags"], suggestion["notes"]), ("independent", ["window_condition"], []))
        self.assertEqual(self.state_path.read_bytes(), original)

    def test_round_limit_forces_a_final_answer_and_errors_are_reported(self):
        FakeClaude.script = [tool_use(f"r{i}", "run_tests", {}) for i in range(agent.MAX_ROUNDS - 1)] + [final("基础用例未全部通过。\n[[ASSIST:no]]")]
        view = self.wait(self.store.agents.start(self.state, {**self.payload, "message": "跑一下用例"})["job_id"])
        self.assertEqual(view["status"], "done", view)
        last = [c for c in FakeClaude.calls if c["method"] == "POST"][-1]["body"]
        self.assertEqual(last["tool_choice"], {"type": "none"})
        self.assertEqual(last["messages"][-1]["content"][-1]["type"], "text")
        FakeClaude.script = [tool_use("bad", "find_counterexample", {"reference_code": "import os", "generator_code": GENERATOR_209}),
                             final("参考解有问题。\n[[ASSIST:no]]")]
        view = self.wait(self.store.agents.start(self.state, {**self.payload, "action": "counterexample"})["job_id"])
        self.assertEqual(view["steps"][0]["status"], "error")
        FakeClaude.script = [(500, {"type": "error", "error": {"type": "api_error", "message": "boom"}})]
        view = self.wait(self.store.agents.start(self.state, {**self.payload, "action": "edge_cases"})["job_id"])
        self.assertEqual(view["status"], "error")
        self.assertIn("500", view["error"])

    def test_agent_requires_the_api_channel_and_a_local_exercise(self):
        with self.assertRaises(ValueError):
            self.store.agents.start(self.state, {**self.payload, "id": "155", "action": "complexity"})
        coach_ai.save_settings(self.root, {"provider": "offline", "model": "claude-opus-5-5"})
        with self.assertRaisesRegex(ValueError, "CPA"):
            self.store.agents.start(self.state, {**self.payload, "action": "complexity"})


class OpenAIChannelTests(FakeServerCase):
    handler = FakeOpenAI

    def test_settings_request_shape_retry_and_errors(self):
        self.assertEqual(coach_ai.normalize_base("https://vps.example.com:8317/v1/chat/completions"), "https://vps.example.com:8317")
        saved = coach_ai.save_settings(self.root, {"provider": "openai", "model": "gpt-5", "base_url": self.base + "/v1", "api_key": "sk-cpa-openai-123"})
        self.assertEqual((saved["provider"], saved["base_url"], saved["available"]["openai"]), ("openai", self.base, True))
        conn = coach_ai.connection(self.root)
        self.assertEqual((conn["format"], conn["headers"]), ("openai", {"authorization": "Bearer sk-cpa-openai-123"}))
        self.assertEqual(coach_ai.list_models(conn), ["gpt-5", "gpt-5-codex"])
        self.assertEqual(FakeOpenAI.calls[-1]["path"], "/v1/models")
        FakeOpenAI.script = [(400, {"error": {"message": "Unsupported parameter: 'reasoning_effort'", "type": "invalid_request_error"}}), chat("你好")]
        self.assertEqual(coach_ai.call_openai("系统", "问题", "gpt-5", conn=conn), "你好")
        first, second = FakeOpenAI.calls[-2:]
        self.assertEqual(first["path"], "/v1/chat/completions")
        self.assertEqual(first["headers"]["authorization"], "Bearer sk-cpa-openai-123")
        self.assertNotIn("x-api-key", first["headers"])
        self.assertNotIn("anthropic-version", first["headers"])
        self.assertEqual(first["body"]["messages"], [{"role": "system", "content": "系统"}, {"role": "user", "content": "问题"}])
        self.assertEqual((first["body"]["model"], first["body"]["reasoning_effort"]), ("gpt-5", "low"))
        self.assertNotIn("reasoning_effort", second["body"])
        # 部分中转把 content 返回成片段数组。
        FakeOpenAI.script = [(200, {"choices": [{"message": {"role": "assistant", "content": [{"type": "text", "text": "片段"}]}}]}),
                             (200, {"choices": [{"message": {"role": "assistant", "content": None, "refusal": "不能回答"}}]}),
                             (401, {"error": {"message": "Invalid API key", "type": "invalid_request_error"}}),
                             (200, {"error": "upstream down"})]
        self.assertEqual(coach_ai.call_openai("系统", "问题", "gpt-5", conn=conn), "片段")
        with self.assertRaisesRegex(coach_ai.CoachError, "拒绝"):
            coach_ai.call_openai("系统", "问题", "gpt-5", conn=conn)
        with self.assertRaisesRegex(coach_ai.CoachError, "api-keys"):
            coach_ai.call_openai("系统", "问题", "gpt-5", conn=conn)
        with self.assertRaisesRegex(coach_ai.CoachError, "choices"):
            coach_ai.call_openai("系统", "问题", "gpt-5", conn=conn)

    def test_environment_key_is_never_sent_to_a_custom_address(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-official-env"}):
            official = coach_ai.connection(self.root, provider="openai")
            self.assertEqual((official["base_url"], official["headers"]), ("https://api.openai.com", {"authorization": "Bearer sk-official-env"}))
            self.assertIsNone(coach_ai.connection(self.root, {"base_url": self.base}, "openai")["source"])
            with self.assertRaisesRegex(ValueError, "API Key"):
                coach_ai.save_settings(self.root, {"provider": "openai", "model": "gpt-5", "base_url": self.base, "api_key": ""})
            coach_ai.save_settings(self.root, {"provider": "openai", "model": "gpt-5", "base_url": self.base, "api_key": "sk-cpa-own"})
            self.assertEqual(coach_ai.connection(self.root)["headers"], {"authorization": "Bearer sk-cpa-own"})

    def test_dashboard_test_models_and_chat_use_the_openai_format(self):
        server = dashboard.make_server(self.state_path, self.log_path, 0, TODAY)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        def call(path, payload=None, token=None):
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=20)
            headers = {"Content-Type": "application/json", **({"X-Coach-Token": token} if token else {})}
            connection.request("POST" if payload is not None else "GET", path, json.dumps(payload).encode() if payload is not None else None, headers)
            response = connection.getresponse()
            return json.loads(response.read())

        token = call("/api/dashboard")["token"]
        models = call("/api/coach/models", {"provider": "openai", "base_url": self.base, "api_key": "sk-cpa-ui"}, token)
        self.assertEqual(models["models"], ["gpt-5", "gpt-5-codex"])
        self.assertEqual(FakeOpenAI.calls[-1]["headers"]["authorization"], "Bearer sk-cpa-ui")
        ok = call("/api/coach/test", {"provider": "openai", "model": "gpt-5-codex", "base_url": self.base + "/v1/chat/completions", "api_key": "sk-cpa-ui"}, token)
        self.assertTrue(ok["ok"], ok)
        settings = call("/api/coach/settings")
        self.assertEqual((settings["provider"], settings["model"], settings["base_url"]), ("openai", "gpt-5-codex", self.base))
        FakeOpenAI.script = [chat("先想想每个位置能接多少水由什么决定。\n[[ASSIST:yes]]")]
        reply = call("/api/workbench/coach", {"id": "42", "code": solution("42"), "extra_cases": [], "draft_revision": None, "mode": "hint", "message": ""}, token)
        self.assertEqual((reply["provider"], reply["counted"]), ("openai", True), reply)
        self.assertNotIn("[[ASSIST", reply["reply"])
        body = FakeOpenAI.calls[-1]["body"]
        self.assertEqual((body["model"], body["messages"][0]["role"]), ("gpt-5-codex", "system"))
        self.assertIn("第 1 层提示", body["messages"][0]["content"])


class OpenAIAgentTests(FakeServerCase):
    handler = FakeOpenAI
    wait = AgentLoopTests.wait

    def setUp(self):
        super().setUp()
        coach_ai.save_settings(self.root, {"provider": "openai", "model": "gpt-5", "base_url": self.base, "api_key": "sk-cpa-test-key"})
        self.store = workbench.Workbench(self.root, self.log_path)
        self.state = coach.load(self.state_path)
        self.payload = {"id": "209", "code": BUGGY_209, "extra_cases": [], "draft_revision": None, "elapsed_seconds": 30,
                        "idea": "滑动窗口，和满足条件就收缩", "takeaway": "", "error_tags": []}

    def posts(self):
        return [c["body"] for c in FakeOpenAI.calls if c["method"] == "POST"]

    def test_parallel_tool_calls_round_trip_and_counting(self):
        FakeOpenAI.script = [
            tool_calls(("call_a", "run_tests", {"extra_cases": [{"name": "刚好超过", "args": [4, [5]], "expected": 1}]}),
                       ("call_b", "find_counterexample", {"reference_code": REFERENCE_209, "generator_code": GENERATOR_209, "count": 150})),
            chat("在 target=1、nums=[5,1] 时你的代码返回 0，期望 1。对照题意看窗口条件。\n[[ASSIST:yes]]"),
        ]
        view = self.wait(self.store.agents.start(self.state, {**self.payload, "action": "counterexample"})["job_id"])
        self.assertEqual(view["status"], "done", view)
        self.assertEqual([s["tool"] for s in view["steps"]], ["run_tests", "find_counterexample"])
        self.assertTrue(all(s["status"] == "done" for s in view["steps"]), view["steps"])
        self.assertTrue(view["result"]["counted"])
        self.assertNotIn("[[ASSIST", view["result"]["reply"])
        first, second = self.posts()
        self.assertEqual((first["tool_choice"], first["reasoning_effort"]), ("auto", "medium"))
        self.assertEqual(first["tools"][0]["type"], "function")
        self.assertEqual([t["function"]["name"] for t in first["tools"]], ["run_tests", "find_counterexample", "measure_complexity", "draft_record"])
        self.assertEqual(first["tools"][1]["function"]["parameters"]["required"], ["reference_code", "generator_code"])
        self.assertEqual(first["messages"][0], {"role": "system", "content": agent.SYSTEM})
        self.assertIn(BUGGY_209.strip(), first["messages"][1]["content"])
        assistant, result_a, result_b = second["messages"][2:5]
        self.assertEqual([c["id"] for c in assistant["tool_calls"]], ["call_a", "call_b"])
        self.assertIsNone(assistant["content"])
        self.assertEqual((result_a["role"], result_a["tool_call_id"]), ("tool", "call_a"))
        self.assertIn('"passed_count"', result_a["content"])
        self.assertEqual(result_b["tool_call_id"], "call_b")
        self.assertIn("mismatches", result_b["content"])
        draft = self.store.read_draft("209")
        transcript = coach_ai.read_transcript(self.root, "209", draft["session_id"])
        self.assertEqual(transcript[-1]["provider"], "openai")
        self.assertEqual(self.store.agent_hints("209", draft["session_id"]), 1)
        fixed = {**self.payload, "code": solution("209"), "draft_revision": draft["revision"]}
        run = self.store.run(fixed, TODAY)
        self.assertEqual(self.store.complete(self.state, {**fixed, "run_id": run["run_id"], "result": "independent"}, TODAY)["result"], "hinted")

    def test_bad_arguments_missing_ids_and_call_cap(self):
        FakeOpenAI.script = [
            tool_calls((None, "run_tests", "{not json"), ("call_obj", "run_tests", "")),
            tool_calls(*[(f"call_{i}", "run_tests", {}) for i in range(9)]),
            chat("基础用例没有全部通过，先看失败的那组输入。\n[[ASSIST:no]]"),
        ]
        # 参数直接给成对象的中转写法也要能执行。
        FakeOpenAI.script[0][1]["choices"][0]["message"]["tool_calls"][1]["function"]["arguments"] = {}
        view = self.wait(self.store.agents.start(self.state, {**self.payload, "message": "跑一下用例"})["job_id"])
        self.assertEqual(view["status"], "done", view)
        self.assertFalse(view["result"]["counted"])
        self.assertEqual(len(view["steps"]), agent.MAX_CALLS)
        self.assertEqual((view["steps"][0]["status"], view["steps"][1]["status"]), ("error", "done"))
        self.assertIn("JSON", view["steps"][0]["summary"])
        first, second, third = self.posts()
        assistant = second["messages"][2]
        generated = assistant["tool_calls"][0]["id"]
        self.assertTrue(generated)
        # 无法解析的参数不原样回传，避免中转转换格式时出错。
        self.assertEqual([c["function"]["arguments"] for c in assistant["tool_calls"]], ["{}", "{}"])
        self.assertEqual([m["tool_call_id"] for m in second["messages"][3:5]], [generated, "call_obj"])
        self.assertIn("工具调用失败", second["messages"][3]["content"])
        # 第二轮 9 个并行调用只执行到总数上限，其余返回未执行；随后强制给出结论。
        tool_messages = [m for m in third["messages"] if m["role"] == "tool"]
        self.assertEqual(len(tool_messages), 11)
        self.assertEqual(sum("没有执行" in m["content"] for m in tool_messages), 11 - agent.MAX_CALLS)
        self.assertEqual(third["tool_choice"], "none")
        self.assertEqual(third["messages"][-1]["role"], "user")
        self.assertIn("基础用例没有全部通过", view["result"]["reply"])

    def test_round_limit_and_service_errors(self):
        FakeOpenAI.script = [tool_calls((f"r{i}", "run_tests", {})) for i in range(agent.MAX_ROUNDS - 1)] + [chat("用例未全部通过。\n[[ASSIST:no]]")]
        view = self.wait(self.store.agents.start(self.state, {**self.payload, "message": "跑一下用例"})["job_id"])
        self.assertEqual(view["status"], "done", view)
        bodies = self.posts()
        self.assertEqual(len(bodies), agent.MAX_ROUNDS)
        self.assertEqual(bodies[-1]["tool_choice"], "none")
        self.assertEqual(bodies[-1]["messages"][-1], {"role": "user", "content": "工具调用次数已用完，请根据已有结果直接给出结论。"})
        FakeOpenAI.script = [(502, {"error": {"message": "upstream codex unavailable"}})]
        view = self.wait(self.store.agents.start(self.state, {**self.payload, "action": "edge_cases"})["job_id"])
        self.assertEqual(view["status"], "error")
        self.assertIn("502", view["error"])
        self.assertIn("upstream codex unavailable", view["error"])


if __name__ == "__main__":
    unittest.main()
