"""调试进程超时/清理/并发上限，以及页面断连后的响应行为。"""
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tools import code_runner, dashboard, problem_bank, workbench


LOOP = "class Solution:\n    def containsDuplicate(self, nums):\n        while True: pass\n"


class DebugLifecycleTests(unittest.TestCase):
    def test_timeout_terminates_abandoned_worker_and_reports_error(self):
        session = code_runner.DebugSession(LOOP, problem_bank.get_exercise("217"), [], timeout=.4)
        self.addCleanup(session.stop)
        deadline = time.monotonic() + 5
        events = []
        while time.monotonic() < deadline:
            events += session.poll()
            if any(item.get("event") == "error" and "超时" in item.get("error", "") for item in events):
                break
            time.sleep(.03)
        self.assertTrue(any("超时" in item.get("error", "") for item in events))
        while time.monotonic() < deadline and session.process.poll() is None:
            time.sleep(.01)
        self.assertTrue(session.closed)
        self.assertIsNotNone(session.process.poll())
        self.assertFalse(Path(session.folder.name).exists())

    def test_manual_stop_and_invalid_breakpoints(self):
        exercise = problem_bank.get_exercise("217")
        for breakpoints in ("3", [0], [1.5], [True], list(range(101))):
            with self.subTest(breakpoints=str(breakpoints)[:30]), self.assertRaises(ValueError):
                code_runner.DebugSession(LOOP, exercise, breakpoints)
        session = code_runner.DebugSession(LOOP, exercise, [])
        session.stop()
        session.stop()  # 多次关闭不会再次访问已释放的资源。
        self.assertIsNotNone(session.process.poll())
        self.assertFalse(Path(session.folder.name).exists())

    def test_workbench_limits_concurrent_sessions_and_reclaims_slots(self):
        with tempfile.TemporaryDirectory() as folder:
            wb = workbench.Workbench(folder, Path(folder) / "learning-log.md")
            self.addCleanup(lambda: [session.stop() for session in wb.debug_sessions.values()])
            ids = [wb.start_debug({"id": "217", "code": LOOP})["debug_id"] for _ in range(2)]
            with self.assertRaisesRegex(ValueError, "最多同时调试 2"):
                wb.start_debug({"id": "217", "code": LOOP})
            wb.debug_command(ids[0], "stop")
            third = wb.start_debug({"id": "217", "code": LOOP})["debug_id"]
            self.assertNotIn(third, ids)
            wb.debug_command(ids[1], "stop")
            wb.debug_command(third, "stop")
            final = wb.start_debug({"id": "217", "code": LOOP})["debug_id"]
            session = wb.debug_sessions[final]
            wb.close_debug()
            self.assertEqual(wb.debug_sessions, {})
            self.assertIsNotNone(session.process.poll())

    def test_expired_session_is_reported_once_and_frees_a_slot(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(code_runner, "DEBUG_TIMEOUT", .3):
            wb = workbench.Workbench(folder, Path(folder) / "learning-log.md")
            self.addCleanup(lambda: [session.stop() for session in wb.debug_sessions.values()])
            debug_id = wb.start_debug({"id": "217", "code": LOOP})["debug_id"]
            deadline = time.monotonic() + 5
            session = wb.debug_sessions[debug_id]
            while time.monotonic() < deadline:
                with session.events.mutex:
                    timed_out = any("超时" in item.get("error", "") for item in session.events.queue)
                if timed_out:
                    break
                time.sleep(.03)
            result = wb.debug_status(debug_id)
            self.assertTrue(any("超时" in item.get("error", "") for item in result["events"]))
            self.assertNotIn(debug_id, wb.debug_sessions)
            with self.assertRaises(ValueError):
                wb.debug_status(debug_id)

    def test_closed_session_waits_for_terminal_event_before_reclaim(self):
        with tempfile.TemporaryDirectory() as folder:
            wb = workbench.Workbench(folder, Path(folder) / "learning-log.md")
            debug_id = wb.start_debug({"id": "217", "code": LOOP})["debug_id"]
            session = wb.debug_sessions[debug_id]
            session.stop()
            session.poll()  # 模拟关闭完成但超时事件仍未入队。
            self.assertEqual(wb.debug_status(debug_id)["events"], [])
            self.assertIn(debug_id, wb.debug_sessions)
            session.events.put({"event": "error", "error": "调试超时"})
            self.assertEqual(wb.debug_status(debug_id)["events"][0]["error"], "调试超时")
            self.assertNotIn(debug_id, wb.debug_sessions)

    def test_disconnect_during_debug_start_releases_orphaned_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            server = dashboard.make_server(Path(folder) / "learning-state.json", Path(folder) / "learning-log.md", 0)
            self.addCleanup(server.server_close)
            handler = server.RequestHandlerClass.__new__(server.RequestHandlerClass)
            handler.local_request = Mock(return_value=True)
            handler.send_json = Mock(return_value=False)  # 发送响应时浏览器已经离开。
            handler.path = "/api/workbench/debug/start"
            body = json.dumps({"id": "217", "code": LOOP}).encode()
            handler.headers = {"X-Coach-Token": "test", "Content-Type": "application/json", "Content-Length": str(len(body))}
            handler.rfile = io.BytesIO(body)
            with patch.object(dashboard.secrets, "compare_digest", return_value=True):
                handler.do_POST()
            response = handler.send_json.call_args.args[1]
            self.assertIn("debug_id", response)
            # 已主动停止并移出会话表，不能等待 120 秒定时器才回收。
            handler.send_json.reset_mock()
            handler.path = "/api/workbench/debug?debug_id=" + response["debug_id"]
            handler.do_GET()
            self.assertEqual(handler.send_json.call_args.args[0], 400)

    def test_client_disconnect_is_not_reported_as_save_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            server = dashboard.make_server(Path(folder) / "learning-state.json", Path(folder) / "learning-log.md", 0)
            self.addCleanup(server.server_close)
            handler = server.RequestHandlerClass.__new__(server.RequestHandlerClass)
            handler.send_response = Mock()
            handler.send_header = Mock()
            handler.end_headers = Mock()
            handler.wfile = Mock()
            handler.wfile.write.side_effect = ConnectionAbortedError("client closed")
            handler.close_connection = False
            handler.send_json(200, {"ok": True})
            self.assertTrue(handler.close_connection)
            handler.wfile.write.assert_called_once()
            # 非断连 I/O 错误仍传给上层，避免吞掉实际磁盘或服务错误。
            handler.wfile.write.side_effect = PermissionError("real error")
            with self.assertRaises(PermissionError):
                handler.send_json(200, {"ok": True})


if __name__ == "__main__":
    unittest.main()
