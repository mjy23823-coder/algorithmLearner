"""逐步调试工作台浏览器回归；仅在临时副本运行，不写真实学习进度。"""
import shutil
import sys
import tempfile
import threading
import time
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import expect, sync_playwright
from tools import code_runner, dashboard


def main():
    originals = {p: p.read_bytes() for p in (ROOT / "learning-state.json", ROOT / "learning-log.md")}
    with tempfile.TemporaryDirectory(prefix="debug-browser-") as folder:
        state = Path(folder) / "learning-state.json"
        log = Path(folder) / "learning-log.md"
        shutil.copyfile(ROOT / "tests/fixtures/learning-state.json", state)
        shutil.copyfile(ROOT / "tests/fixtures/learning-log.md", log)
        before = state.read_bytes()
        server = dashboard.make_server(state, log, 0, date(2026, 10, 17))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page(reduced_motion="reduce")
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}/#workbench")
                page.locator("#wb-problem").select_option("42")
                editor = page.get_by_label("Python 代码", exact=True)
                editor.fill("class Solution:\n    def trap(self, height):\n        answer = len(height)\n        return answer\n")
                page.locator(".wb-debug summary").click()
                page.get_by_label("调试断点行号").fill("0")
                page.get_by_role("button", name="开始调试").click()
                expect(page.locator("#wb-debug-state")).to_contain_text("断点行号应在")
                page.get_by_label("调试断点行号").fill("")
                line4=page.locator('.wb-gutter-line[data-line="4"]')
                line4.click()
                expect(line4).to_have_class("wb-gutter-line has-breakpoint")
                expect(page.get_by_label("调试断点行号")).to_have_value("4")
                line4.focus()
                line4.press("Enter")
                expect(line4).to_have_attribute("aria-pressed", "false")
                expect(page.get_by_label("调试断点行号")).to_have_value("")
                page.get_by_label("调试断点行号").fill("3, 4")
                expect(page.locator(".wb-gutter-line.has-breakpoint")).to_have_count(2)
                page.get_by_label("调试断点行号").fill("x")
                line4.click()
                expect(page.get_by_label("调试断点行号")).to_have_value("x")
                expect(page.locator("#wb-error")).to_contain_text("断点只支持")
                page.get_by_label("调试断点行号").fill("4")
                expect(line4).to_have_attribute("aria-pressed", "true")
                page.get_by_role("button", name="开始调试").click()
                status = page.locator("#wb-debug-state")
                expect(status).to_contain_text("停在第 4 行", timeout=12000)
                page.get_by_role("button", name="停止", exact=True).click()
                page.get_by_label("调试断点行号").fill("")
                expect(page.locator(".wb-gutter-line.has-breakpoint")).to_have_count(0)
                page.get_by_role("button", name="开始调试").click()
                expect(status).to_contain_text("停在第 3 行", timeout=12000)
                expect(page.locator("#wb-execution-line")).to_be_visible()
                expect(page.locator(".wb-gutter-line.is-current")).to_have_text("3")
                assert page.locator("#wb-execution-line").evaluate("el => Math.abs(parseFloat(el.style.top) - (17 + 2*23 - document.querySelector('[data-wb-field=code]').scrollTop)) < 1")
                expect(page.get_by_label("调试用例输入")).to_contain_text("输入参数")
                expect(page.get_by_label("调试用例输入")).to_contain_text("期望结果")
                expect(page.get_by_label("调试局部变量")).to_contain_text("height")
                page.get_by_role("button", name="单步", exact=True).click()
                expect(status).to_contain_text("停在第 4 行", timeout=12000)
                expect(page.locator(".wb-gutter-line.is-current")).to_have_text("4")
                expect(page.get_by_label("调试局部变量")).to_contain_text("answer")
                page.get_by_role("button", name="继续", exact=True).click()
                expect(status).to_contain_text("调试执行结束", timeout=12000)
                expect(page.locator("#wb-execution-line")).to_be_hidden()
                expect(page.locator(".wb-gutter-line.is-current")).to_have_count(0)
                expect(page.get_by_label("调试局部变量")).to_contain_text("实际结果")
                expect(page.get_by_role("button", name="单步", exact=True)).to_be_disabled()
                assert state.read_bytes() == before
                page.get_by_role("button", name="开始调试").click()
                expect(status).to_contain_text("停在第 3 行", timeout=12000)
                page.get_by_role("button", name="停止", exact=True).click()
                expect(status).to_contain_text("调试已停止")
                # 停在断点时改代码必须结束旧会话，不能继续看过时变量。
                page.get_by_role("button", name="开始调试").click()
                expect(status).to_contain_text("停在第 3 行", timeout=12000)
                editor.fill("class Solution:\n    def trap(self, height):\n        return 0\n")
                expect(status).to_contain_text("代码已修改，本次调试已停止")
                expect(page.locator("#wb-execution-line")).to_be_hidden()
                expect(page.get_by_role("button", name="继续", exact=True)).to_be_disabled()

                # 运行时错误与语法错误应标出真实代码行；修改后清理旧标记。
                editor.fill("class Solution:\n    def trap(self, height):\n        raise ValueError('test crash')\n")
                page.get_by_role("button", name="开始调试").click()
                expect(status).to_contain_text("停在第 3 行", timeout=12000)
                page.get_by_role("button", name="继续", exact=True).click()
                expect(status).to_contain_text("ValueError（代码第 3 行）", timeout=12000)
                expect(status).to_have_attribute("data-state", "error")
                expect(page.locator('.wb-gutter-line[data-line="3"]')).to_have_class("wb-gutter-line is-error")
                expect(page.locator("#wb-execution-line")).to_have_class("is-error")
                editor.fill("class Solution:\n    def trap(self, height)\n        return 0\n")
                expect(page.locator("#wb-execution-line")).to_be_hidden()
                page.get_by_role("button", name="开始调试").click()
                expect(status).to_contain_text("SyntaxError", timeout=12000)
                expect(page.locator('.wb-gutter-line[data-line="2"]')).to_have_class("wb-gutter-line is-error")
                editor.fill("class Solution:\n    def trap(self, height):\n        return 0\n")
                expect(page.locator(".wb-gutter-line.is-error")).to_have_count(0)

                base = f"http://127.0.0.1:{server.server_port}"
                def expect_released(debug_id):
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        if page.request.get(f"{base}/api/workbench/debug?debug_id={debug_id}").status == 400:
                            return
                        time.sleep(.05)
                    raise AssertionError(f"调试会话仍未回收：{debug_id}")

                # SPA 切题会销毁旧工作台；刷新/离开页面通过 keepalive 停止进程。
                with page.expect_response(lambda r: r.url.endswith("/api/workbench/debug/start")) as started:
                    page.get_by_role("button", name="开始调试").click()
                debug_id = started.value.json()["debug_id"]
                expect(status).to_contain_text("停在", timeout=12000)
                page.locator("#wb-problem").select_option("15")
                expect(page.locator("#wb-problem")).to_have_value("15")
                expect_released(debug_id)

                page.locator("#wb-problem").select_option("42")
                expect(page.locator("#wb-problem")).to_have_value("42")
                page.locator(".wb-debug summary").click()
                with page.expect_response(lambda r: r.url.endswith("/api/workbench/debug/start")) as started:
                    page.get_by_role("button", name="开始调试").click()
                debug_id = started.value.json()["debug_id"]
                expect(page.locator("#wb-debug-state")).to_contain_text("停在", timeout=12000)
                page.reload()
                expect(page.get_by_label("Python 代码", exact=True)).to_be_visible()
                expect_released(debug_id)
                editor = page.get_by_label("Python 代码", exact=True)
                editor.fill("class Solution:\n    def trap(self, height):\n        while True: pass\n")
                page.locator(".wb-debug summary").click()
                with patch.object(code_runner, "DEBUG_TIMEOUT", 1.5):
                    with page.expect_response(lambda r: r.url.endswith("/api/workbench/debug/start")):
                        page.get_by_role("button", name="开始调试").click()
                status = page.locator("#wb-debug-state")
                expect(status).to_contain_text("停在第 3 行", timeout=12000)
                page.get_by_role("button", name="继续", exact=True).click()
                expect(status).to_contain_text("调试超时", timeout=12000)
                expect(status).to_have_attribute("data-state", "timeout")
                expect(page.locator("#wb-execution-line")).to_be_hidden()
                editor.fill("class Solution:\n    def trap(self, height):\n        return 0\n")
                with page.expect_response(lambda r: r.url.endswith("/api/workbench/debug/start")) as started:
                    page.get_by_role("button", name="开始调试").click()
                debug_id = started.value.json()["debug_id"]
                expect(page.locator("#wb-debug-state")).to_contain_text("停在", timeout=12000)
                page.get_by_role("button", name="今日学习", exact=True).click()
                expect(page.get_by_role("heading", name="每天进步一点点。")).to_be_visible()
                expect_released(debug_id)
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        assert state.read_bytes() == before
    for path, original in originals.items():
        assert path.read_bytes() == original
    print("PASS: debug step, stop on edit, switch problem, refresh and leave; progress unchanged")


if __name__ == "__main__":
    main()
