"""第二轮功能的浏览器验证：排题理由、候选新题、教练对话、限时模拟面试和能力周报。"""
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
from reference_solutions import solution

TODAY = date(2026, 10, 17)


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    originals = {p: p.read_bytes() for p in (ROOT / "learning-state.json", ROOT / "learning-log.md")}
    artifacts = ROOT / "artifacts"
    with tempfile.TemporaryDirectory(prefix="coach-mock-ui-") as folder:
        path = Path(folder) / "learning-state.json"
        log = path.with_name("learning-log.md")
        shutil.copyfile(ROOT / "tests/fixtures/learning-state.json", path)
        shutil.copyfile(ROOT / "tests/fixtures/learning-log.md", log)
        manifest = json.loads((ROOT / "data/history-review-2026-10-17.json").read_text(encoding="utf-8"))
        recovered, _ = coach.prepare_history_import(coach.load(path), manifest, log, TODAY)
        coach.save(path, recovered)
        server = dashboard.make_server(path, log, 0, TODAY)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        errors = []
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 1050}, reduced_motion="reduce")
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
                base = f"http://127.0.0.1:{server.server_port}"

                # 今日计划：每道待练题都有排题理由；画像推荐的新题可以固定加入队列，也可以换一题。
                page.goto(base + "/#today")
                expect(page.get_by_role("heading", name="每天进步一点点。")).to_be_visible()
                expect(page.locator(".task-reason").first).to_be_visible()
                expect(page.get_by_role("heading", name="为什么这样排")).to_be_visible()
                expect(page.get_by_role("heading", name="你的学习画像")).to_be_visible()
                expect(page.get_by_role("heading", name="更多为你推荐的新题")).to_be_visible()
                expect(page.get_by_role("heading", name="本周还没有限时模拟")).to_be_visible()
                rows = page.locator(".rec-row")
                first = rows.first
                candidate = first.locator(".task-id").inner_text().replace("LC", "").strip()
                first.get_by_role("button", name="固定加入待学").click()
                expect(page.locator("#toast")).to_contain_text(f"LC{candidate} 已加入待学队列")
                assert candidate in coach.load(path)["next_new"]
                # 等列表按新进度重绘：加入待学的题不再出现在推荐里。
                expect(page.locator(".rec-row .task-id").filter(has_text=re.compile(rf"^LC {candidate}$"))).to_have_count(0)
                swapped = rows.first.locator(".task-id").inner_text().replace("LC", "").strip()
                rows.first.get_by_role("button", name="换一题").click()
                expect(page.locator("#toast")).to_contain_text(f"已换掉 LC{swapped}")
                assert swapped in coach.load(path)["recommend_skips"]
                expect(page.locator(".rec-row .task-id").filter(has_text=re.compile(rf"^LC {swapped}$"))).to_have_count(0)
                # 口述复习：讲清楚了只改下次复习日期，当前结果高亮，可以当天更正。
                oral = page.locator(".oral-panel")
                expect(oral.get_by_role("heading", name=re.compile("口述复习"))).to_be_visible()
                row = oral.locator(".oral-row").first
                spoken = row.locator(".task-id").inner_text().replace("LC", "").strip()
                row.get_by_role("button", name="讲清楚了").click()
                expect(page.locator("#toast")).to_contain_text(f"LC{spoken} 口述复习：讲清楚了")
                expect(oral.locator(".oral-choice.chosen")).to_have_count(1)
                oral.get_by_label(f"LC{spoken} 口述结果", exact=True).get_by_role("button", name="有卡顿").click()
                expect(page.locator("#toast")).to_contain_text("完整重写")
                assert [e["result"] for e in coach.load(path)["completed"][spoken]["oral"]] == ["hinted"]
                page.screenshot(path=str(artifacts / "smart-plan.png"), full_page=True)

                # 工作台里的教练对话：离线模式下讲解检查不计提示，要提示会展开分层提示。
                page.locator(".task-row").filter(has_text="接雨水").get_by_role("button", name="去练习").click()
                coach_panel = page.locator("#wb-coach")
                expect(coach_panel.get_by_role("heading", name="教练", exact=True)).to_be_visible()
                expect(coach_panel.get_by_role("tab", name="对话")).to_have_attribute("aria-selected", "true")
                coach_panel.get_by_role("button", name="检查我的讲解").click()
                expect(coach_panel.locator(".coach-msg.from-coach").last).to_contain_text("核心思路")
                page.get_by_label("我的核心思路", exact=True).fill("两侧最大高度中较低的一侧决定水位")
                coach_panel.get_by_role("button", name="检查我的讲解").click()
                expect(coach_panel.locator(".coach-msg.from-coach").last).to_contain_text("关键变量")
                coach_panel.get_by_role("button", name="给我一层提示").click()
                expect(coach_panel.locator(".coach-msg.from-coach").last).to_contain_text("提示 1")
                expect(page.locator("#wb-hint-note")).to_contain_text("已看 1 层提示")
                expect(page.locator("#wb-hints .wb-hint")).to_have_count(1)
                coach_panel.get_by_role("button", name="教练设置").click()
                settings = page.locator("dialog.coach-settings")
                expect(settings).to_contain_text("默认离线引导")
                settings.get_by_role("button", name="关闭").click()
                page.screenshot(path=str(artifacts / "workbench-coach.png"), full_page=True)
                draft = json.loads((Path(folder) / "solutions/.drafts/lc42.json").read_text(encoding="utf-8"))
                assert draft["hints_used"] == 1 and draft["idea"].startswith("两侧最大高度"), draft

                # 限时模拟：指定一道题，讲思路、写代码、运行、追问、评分并保存。
                page.get_by_role("button", name="模拟面试", exact=True).click()
                expect(page.get_by_role("heading", name="限时模拟，练面试里的自己。")).to_be_visible()
                page.get_by_role("button", name="用这题模拟（25 分钟）").filter(has=page.locator("xpath=..")).first.click()
                expect(page.locator("#mock-clock")).to_have_text(__import__("re").compile(r"^2[45]:\d\d$"))
                pid = json.loads(page.evaluate("localStorage.getItem('algorithm-mock-active')"))["id"]
                expect(page.locator(".mock-page")).not_to_contain_text(coach.problem(coach.load(path), pid)["title"])
                page.get_by_label("题型识别与依据").fill("按层处理的二叉树题")
                page.get_by_label("思路与关键变量").fill("队列保存当前层，记录每层信息")
                page.get_by_label("预估时间复杂度").fill("O(n)")
                expect(page.locator('[data-panel="1"]')).to_be_hidden()
                page.get_by_role("button", name="讲完了，开始写代码").click()
                page.get_by_label("Python 代码", exact=True).fill(solution(pid))
                page.get_by_role("button", name="运行本地用例").click()
                expect(page.locator("#mock-results")).to_contain_text("本地用例全部通过", timeout=15000)
                expect(page.locator('[data-panel="2"]')).to_be_visible()
                page.locator('[data-field="boundary"]').fill("空树返回空结果")
                page.locator('[data-field="followup"]').fill("可以改成迭代减少递归栈")
                page.get_by_role("button", name="回答完了，进入复盘").click()
                expect(page.locator('[name="score-time"]:checked')).to_have_value("5")
                expect(page.locator('[name="score-code"]:checked')).to_have_value("4")
                for key, value in (("recognition", "4"), ("communication", "3"), ("complexity", "4")):
                    page.locator(f'[data-dim="{key}"] label').filter(has_text=value).click()
                expect(page.locator("#mock-result")).to_have_value("independent")
                page.get_by_label("最该改进的一点").fill("先讲清队列里保存的是什么")
                page.screenshot(path=str(artifacts / "mock-interview.png"), full_page=True)
                page.get_by_role("button", name="保存这场模拟").click()
                expect(page.locator(".notice").first).to_contain_text("模拟已保存")
                entry = coach.load(path)["completed"][pid]["history"][-1]
                assert entry["mock"] and entry["mock_review"]["scores"]["communication"] == 3, entry
                assert coach.load(path)["last_mock"] == TODAY.isoformat()
                expect(page.locator(".mock-page table")).to_contain_text("先讲清队列里保存的是什么")

                # 能力周报：模拟维度、下周重点和 Markdown 导出。
                page.get_by_role("button", name="能力周报", exact=True).click()
                expect(page.get_by_role("heading", name="模拟面试五维")).to_be_visible()
                expect(page.locator(".dim-row")).to_have_count(5)
                expect(page.locator(".dim-bar[data-score='3']")).to_have_count(1)
                expect(page.get_by_role("heading", name="下周重点")).to_be_visible()
                expect(page.get_by_role("heading", name="有记录支持的进步")).to_be_visible()
                with page.expect_download() as download:
                    page.get_by_role("button", name="导出周报", exact=True).click()
                text = Path(download.value.path()).read_text(encoding="utf-8")
                assert text.startswith("# 算法能力周报") and "## 模拟面试" in text, text[:200]
                page.screenshot(path=str(artifacts / "ability-report.png"), full_page=True)

                page.set_viewport_size({"width": 390, "height": 844})
                for name in ("今日学习", "模拟面试", "能力周报", "练习工作台"):
                    page.get_by_role("button", name=name, exact=True).click()
                    page.wait_for_timeout(250)
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), name
                page.get_by_role("button", name="模拟面试", exact=True).click()
                page.screenshot(path=str(artifacts / "mock-mobile.png"), full_page=True)
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        assert not errors, errors
        for original, content in originals.items():
            assert original.read_bytes() == content, f"{original.name} 被修改"
    print("PASS: plan reasons, candidate queue, offline coach chat and hint counting, timed mock with scoring, ability report export, mobile widths")
    print("Screenshots: artifacts/smart-plan.png, artifacts/workbench-coach.png, artifacts/mock-interview.png, artifacts/ability-report.png, artifacts/mock-mobile.png")


if __name__ == "__main__":
    main()
