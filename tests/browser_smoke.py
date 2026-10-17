"""可选的浏览器端到端验证；需要本机安装 Playwright 和 Chromium。

运行：python tests/browser_smoke.py
所有操作使用临时副本；截图输出到 artifacts/。
"""
import json
import re
import shutil
import sys
import tempfile
import threading
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import expect, sync_playwright
from tools import coach, dashboard


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    originals = {p: p.read_bytes() for p in (ROOT / "learning-state.json", ROOT / "learning-log.md")}
    with tempfile.TemporaryDirectory(prefix="algorithm-browser-tests-") as folder:
        state = Path(folder) / "learning-state.json"
        log = state.with_name("learning-log.md")
        shutil.copyfile(ROOT / "tests/fixtures" / state.name, state)
        shutil.copyfile(ROOT / "tests/fixtures" / log.name, log)
        original_test_log = log.read_bytes()
        server = dashboard.make_server(state, log, 0, date(2026, 10, 16))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        errors = []
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 1050}, device_scale_factor=1,
                                              permissions=["clipboard-read", "clipboard-write"])
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
                page.goto(f"http://127.0.0.1:{server.server_port}/#today")
                expect(page.get_by_role("heading", name="每天进步一点点。")).to_be_visible()
                expect(page.locator(".task-row")).to_have_count(4)
                page.screenshot(path=str(artifacts / "dashboard-desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                page.screenshot(path=str(artifacts / "dashboard-mobile.png"), full_page=True)
                page.set_viewport_size({"width": 1440, "height": 1050})
                page.get_by_role("button", name="90 分钟", exact=True).click()
                expect(page.get_by_role("button", name="90 分钟", exact=True)).to_have_attribute("aria-pressed", "true")
                page.get_by_role("button", name="120 分钟", exact=True).click()
                expect(page.get_by_role("button", name="120 分钟", exact=True)).to_have_attribute("aria-pressed", "true")

                page.get_by_role("button", name="复习队列").click()
                page.locator("#due-filter").select_option("due")
                expect(page.locator("#problem-rows tr")).to_have_count(4)
                page.get_by_label("搜索题目").fill("LC26")
                expect(page.locator("#problem-rows tr")).to_have_count(1)
                expect(page.locator("#problem-rows")).to_contain_text("删除有序数组中的重复项")

                page.get_by_role("button", name="题目档案", exact=True).click()
                page.get_by_label("待学题号").fill("239 739")
                page.get_by_role("button", name="加入队列", exact=True).click()
                expect(page.get_by_label("从待学队列移除 LC739")).to_be_visible()
                page.get_by_label("从待学队列移除 LC739").click()
                expect(page.get_by_label("从待学队列移除 LC739")).to_have_count(0)
                page.get_by_role("button", name="记录练习", exact=True).first.click()
                dialog = page.locator("#practice-dialog")
                dialog.get_by_label("LeetCode 题号").fill("42")
                dialog.get_by_label("LeetCode 题号").press("Tab")
                expect(dialog.get_by_label("题目名称")).to_have_value("接雨水")
                dialog.get_by_label("题目名称").fill("接雨水")
                dialog.get_by_label("所属专题").fill("双指针")
                dialog.get_by_label("练习用时（分钟）").fill("25")
                dialog.get_by_label("一句话复盘").fill("先更新左右最大值；<script>window.injected=true</script>")
                dialog.get_by_role("button", name="保存练习", exact=True).click()
                try:
                    expect(dialog).not_to_be_visible()
                except AssertionError:
                    print("Practice error:", dialog.locator(".form-error").inner_text())
                    print("Form:", dialog.locator("form").evaluate("f => ({id: String(f.id), valid: f.checkValidity(), values: Object.fromEntries(new FormData(f))})"))
                    print("Browser errors:", errors)
                    raise
                expect(page.locator("#toast")).to_contain_text("2026-10-19")
                self_record = coach.load(state)["completed"]["42"]
                assert self_record["count"] == 1 and self_record["status"] == "learning"
                assert self_record["title"] == "接雨水"

                page.get_by_role("button", name="今日学习", exact=True).click()
                row = page.locator(".task-row").filter(has_text="接雨水")
                row.get_by_role("button", name="已记录").click()
                dialog.get_by_role("button", name="保存练习", exact=True).click()
                expect(dialog).not_to_be_visible()
                assert coach.load(state)["completed"]["42"]["count"] == 1

                page.get_by_role("button", name="与聊天教练继续", exact=True).click()
                expect(page.locator("#coach-prompt")).to_have_value(re.compile("先读取本项目"))
                page.get_by_role("button", name="复制学习指令", exact=True).click()
                assert "tools/coach.py" in page.evaluate("navigator.clipboard.readText()")
                page.locator("#coach-dialog").get_by_role("button", name="关闭", exact=True).click()

                page.get_by_role("button", name="结束并保存", exact=True).click()
                wrap = page.locator("#wrap-dialog")
                wrap.get_by_label("今天的收获或卡点").fill("注意左右指针更新顺序")
                wrap.get_by_role("button", name="保存今日总结", exact=True).click()
                expect(wrap).not_to_be_visible()
                assert log.read_bytes().startswith(original_test_log)
                page.get_by_role("button", name="学习记录", exact=True).click()
                expect(page.locator(".log-entry").first).to_contain_text("学习总结")
                expect(page.locator(".log-entry").first).to_contain_text("注意左右指针更新顺序")

                page.get_by_role("button", name="能力周报", exact=True).click()
                expect(page.locator(".weekly-notes")).to_contain_text("先更新左右最大值")
                assert page.evaluate("window.injected") is None
                with page.expect_download() as download:
                    page.get_by_role("button", name="导出进度", exact=True).click()
                exported = json.loads(Path(download.value.path()).read_text(encoding="utf-8"))
                assert exported["completed"]["42"]["count"] == 1

                page.get_by_role("button", name="今日学习", exact=True).click()
                page.get_by_role("button", name="记录练习", exact=True).click()
                dialog.get_by_label("LeetCode 题号").fill("239")
                dialog.get_by_label("LeetCode 题号").press("Tab")
                dialog.get_by_label("题目名称").fill("滑动窗口最大值")
                dialog.get_by_label("所属专题").fill("单调队列")
                dialog.get_by_role("radio", name="暂未完成", exact=False).check()
                dialog.get_by_role("button", name="保存练习", exact=True).click()
                expect(dialog).not_to_be_visible()
                assert coach.load(state)["completed"]["239"]["count"] == 0
                expect(page.locator(".plan-footer")).to_contain_text("1 道待练习")

                page.get_by_role("button", name="调整学习方向", exact=True).click()
                external = coach.load(state)
                external["current_topic"] = "外部聊天更新的专题"
                coach.save(state, external)
                page.locator("#settings-dialog").get_by_label("当前专题", exact=True).fill("不会覆盖的旧页面")
                page.get_by_role("button", name="保存方向", exact=True).click()
                expect(page.locator("#settings-dialog .form-error")).to_contain_text("学习记录已更新")
                assert coach.load(state)["current_topic"] == "外部聊天更新的专题"
                page.locator("#settings-dialog").get_by_role("button", name="关闭", exact=True).click()
                page.get_by_role("button", name="刷新进度", exact=True).click()
                expect(page.locator(".focus-panel")).to_contain_text("外部聊天更新的专题")

                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                for name in ("复习队列", "题目档案", "学习记录", "能力周报", "模拟面试", "今日学习"):
                    page.get_by_role("button", name=name, exact=True).click()
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), name
                page.get_by_role("button", name="记录练习", exact=True).click()
                expect(dialog).to_be_visible()
                assert dialog.bounding_box()["width"] < 390
                dialog.get_by_role("button", name="关闭", exact=True).click()
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    # 409 并发冲突的浏览器控制台消息是上面的预期行为。
    unexpected = [e for e in errors if "409 (Conflict)" not in e]
    assert not unexpected, unexpected
    for path, original in originals.items():
        assert path.read_bytes() == original, f"Real progress changed: {path}"
    print("PASS: browser navigation, filters, queue, practice, duplicate submission, clipboard, wrap, export, conflict, mobile, and original data preservation")
    print("Screenshots: artifacts/dashboard-desktop.png, artifacts/dashboard-mobile.png")


if __name__ == "__main__":
    main()
