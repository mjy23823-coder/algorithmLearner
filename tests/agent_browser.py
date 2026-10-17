"""智能体的浏览器验证：在设置里连接 CPA（本地假服务代替）、读取模型、找反例、填入草拟记录。不调用真实模型。

OpenAI 兼容接口（/v1/chat/completions）和 Claude 格式（/v1/messages）各走一遍完整流程。
"""
import json
import os
import shutil
import sys
import tempfile
import threading
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from playwright.sync_api import expect, sync_playwright
from tools import dashboard
from test_agent import BUGGY_209, GENERATOR_209, REFERENCE_209, FakeClaude, FakeOpenAI, chat, final, tool_calls, tool_use

TODAY = date(2026, 10, 17)
FIND = {"reference_code": REFERENCE_209, "generator_code": GENERATOR_209, "count": 120}
DRAFT = {"result": "independent", "error_tags": ["window_condition"], "takeaway": "题目要求和至少为 target，窗口条件用 >=", "why": "找到反例后改对"}
REPLY = "对拍发现 target=1、nums=[5,1] 时返回 0，期望 1。对照题意检查窗口条件。\n[[ASSIST:yes]]"
FLOWS = {
    "openai": {"handler": FakeOpenAI, "label": "OpenAI 兼容接口 / CPA", "model": "gpt-5",
               "script": lambda: [tool_calls(("call_c1", "find_counterexample", FIND)), tool_calls(("call_d1", "draft_record", DRAFT)), chat(REPLY)],
               "auth": lambda headers: headers.get("authorization") == "Bearer sk-cpa-browser-test"},
    "anthropic": {"handler": FakeClaude, "label": "Claude API / CPA 中转", "model": "claude-opus-5-5",
                  "script": lambda: [tool_use("c1", "find_counterexample", FIND), tool_use("d1", "draft_record", DRAFT), final(REPLY)],
                  "auth": lambda headers: headers.get("x-api-key") == "sk-cpa-browser-test"},
}


def flow(kind, pw, screenshots):
    spec = FLOWS[kind]
    handler = spec["handler"]
    handler.calls, handler.script = [], []
    fake = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=fake.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{fake.server_port}"
    with tempfile.TemporaryDirectory(prefix="agent-ui-") as folder:
        path = Path(folder) / "learning-state.json"
        log = path.with_name("learning-log.md")
        shutil.copyfile(ROOT / "tests/fixtures/learning-state.json", path)
        shutil.copyfile(ROOT / "tests/fixtures/learning-log.md", log)
        server = dashboard.make_server(path, log, 0, TODAY)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        errors = []
        try:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 1050}, reduced_motion="reduce")
            context.add_init_script("localStorage.setItem('algorithm-workbench-selected', '209')")
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.goto(f"http://127.0.0.1:{server.server_port}/#workbench")
            coach_panel = page.locator("#wb-coach")
            expect(coach_panel.get_by_role("tab", name="智能体")).to_be_visible()
            coach_panel.get_by_role("tab", name="智能体").click()
            expect(coach_panel).to_contain_text("需要先连接 OpenAI 兼容接口或 Claude API")

            # 在设置里选通道，填写 CPA 地址和 Key，读取模型，测试并启用。
            coach_panel.get_by_role("button", name="连接模型接口").click()
            dialog = page.locator("dialog.coach-settings")
            expect(dialog.get_by_label("服务地址", exact=True)).to_be_hidden()
            dialog.locator("label").filter(has_text=spec["label"]).click()
            # 切换通道时，默认模型换成该通道的默认值。
            expect(dialog.get_by_label("模型", exact=True)).to_have_value(spec["model"])
            dialog.get_by_label("服务地址", exact=True).fill(base + "/v1")
            expect(dialog.locator("[data-http-warning]")).to_be_hidden()
            dialog.get_by_label("服务地址", exact=True).fill("http://203.0.113.9:8317")
            expect(dialog.locator("[data-http-warning]")).to_be_visible()
            dialog.get_by_label("服务地址", exact=True).fill(base + "/v1")
            dialog.get_by_label("API Key", exact=True).fill("sk-cpa-browser-test")
            dialog.get_by_role("button", name="读取接口提供的模型").click()
            expect(dialog.locator("[data-models-status]")).to_contain_text("共 2 个模型")
            dialog.get_by_role("button", name="测试并启用").click()
            expect(dialog).not_to_be_visible()
            expect(page.locator("#toast")).to_contain_text("连接正常")
            saved = json.loads((Path(folder) / ".runtime/coach-settings.json").read_text(encoding="utf-8"))
            assert (saved["base_url"], saved["provider"], saved["model"]) == (base, kind, spec["model"]), saved
            assert "sk-cpa" not in json.dumps(saved)

            # 智能体找反例：步骤逐条显示，草拟记录可填入复盘。
            page.get_by_label("Python 代码", exact=True).fill(BUGGY_209)
            handler.script = spec["script"]()
            coach_panel.get_by_role("tab", name="智能体").click()
            coach_panel.get_by_role("button", name="找反例").click()
            expect(coach_panel.locator(".agent-step").filter(has_text="对拍找反例")).to_contain_text("不一致", timeout=30000)
            expect(coach_panel.locator(".coach-msg.from-coach").last).to_contain_text("对照题意检查窗口条件", timeout=30000)
            expect(coach_panel.locator(".coach-msg.from-coach").last).to_contain_text("计为提示")
            expect(coach_panel.locator(".coach-msg.from-coach").last).to_contain_text(spec["label"])
            expect(page.locator("#wb-hint-note")).to_contain_text("1 次教练提示")
            expect(coach_panel.locator(".agent-suggestion")).to_contain_text("提示后完成")
            if screenshots:
                page.screenshot(path=str(ROOT / "artifacts/workbench-agent.png"), full_page=True)
            coach_panel.get_by_role("button", name="填入复盘（仍需你点保存）").click()
            expect(page.locator('[data-wb-field="takeaway"]')).to_have_value(DRAFT["takeaway"])
            assert page.locator('[name="wb-error-tag"][value="window_condition"]').is_checked()
            assert page.evaluate("document.querySelector('#wb-result [value=independent]').disabled")
            posts = [c for c in handler.calls if c["method"] == "POST"]
            assert all(spec["auth"](c["headers"]) for c in posts[-3:]), posts[-1]["headers"]
            assert all(c["body"]["model"] == spec["model"] for c in posts), [c["body"]["model"] for c in posts]

            page.reload()
            page.locator("#wb-coach").get_by_role("tab", name="智能体").click()
            expect(page.locator("#wb-coach .agent-step")).to_have_count(2)
            expect(page.locator("#wb-hint-note")).to_contain_text("1 次教练提示")
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(300)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            if screenshots:
                page.locator("#wb-coach").scroll_into_view_if_needed()
                page.screenshot(path=str(ROOT / "artifacts/workbench-agent-mobile.png"), full_page=False)
            browser.close()
        finally:
            server.shutdown()
            server.server_close()
            fake.shutdown()
            fake.server_close()
            thread.join(timeout=5)
        assert not errors, (kind, errors)


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    for key in [k for k in os.environ if k.startswith(("ANTHROPIC_", "OPENAI_"))]:
        del os.environ[key]
    originals = {p: p.read_bytes() for p in (ROOT / "learning-state.json", ROOT / "learning-log.md")}
    with sync_playwright() as pw:
        for index, kind in enumerate(FLOWS):
            flow(kind, pw, screenshots=index == 0)
            print(f"PASS [{kind}]: settings (address/key/models/test), agent steps, counterexample counting, draft suggestion fill, reload persistence, mobile")
    for original, content in originals.items():
        assert original.read_bytes() == content, f"{original.name} 被修改"
    print("Screenshots: artifacts/workbench-agent.png, artifacts/workbench-agent-mobile.png")


if __name__ == "__main__":
    main()
