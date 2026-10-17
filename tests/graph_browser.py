"""知识图谱端到端验证。只操作临时副本，不改真实学习数据。"""
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
    errors = []
    with tempfile.TemporaryDirectory(prefix="algorithm-graph-tests-") as folder:
        state_path = Path(folder) / "learning-state.json"
        log_path = state_path.with_name("learning-log.md")
        shutil.copyfile(ROOT / "tests/fixtures" / state_path.name, state_path)
        shutil.copyfile(ROOT / "tests/fixtures" / log_path.name, log_path)
        original_test_log = log_path.read_bytes()
        before = state_path.read_bytes()
        server = dashboard.make_server(state_path, log_path, 0, date(2026, 10, 17))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1500, "height": 1050}, device_scale_factor=1, reduced_motion="reduce")
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
                page.goto(f"http://127.0.0.1:{server.server_port}/#graph")
                graph = page.locator("#learning-graph")
                expect(graph).to_have_attribute("data-ready", "true")
                expect(page.get_by_role("heading", name="算法学习图谱", exact=True)).to_be_visible()
                expect(graph.locator(".node-problem")).to_have_count(15)
                expect(graph.locator(".node-topic")).to_have_count(6)
                expect(graph.locator(".graph-edge")).to_have_count(21)
                expect(graph.locator('[data-node="problem:11"]')).to_have_class(re.compile("category-calibration"))
                expect(graph.locator('[data-node="problem:209"]')).to_have_class(re.compile("category-calibration"))
                expect(graph.locator('[data-node="problem:26"]')).to_have_class(re.compile("category-overdue"))
                page.screenshot(path=str(artifacts / "algorithm-graph.png"), full_page=True)

                node26 = graph.locator('[data-node="problem:26"]')
                node26.locator(".graph-node-circle").click()
                detail = page.locator("#graph-detail")
                expect(detail).to_contain_text("删除有序数组中的重复项")
                expect(detail).to_contain_text("已逾期 2 天")
                expect(detail).to_contain_text("2026-10-15")
                expect(node26).to_have_attribute("aria-pressed", "true")
                page.screenshot(path=str(artifacts / "algorithm-graph-detail.png"), full_page=True)
                graph.locator('[data-node="problem:11"] .graph-node-circle').click()
                detail.get_by_role("button", name="请教练核对历史", exact=True).click()
                expect(page.locator("#coach-prompt")).to_have_value(re.compile("核对 LC11"))
                page.locator("#coach-dialog").get_by_role("button", name="关闭", exact=True).click()

                page.get_by_role("button", name="折叠专题", exact=True).click()
                expect(graph.locator(".node-problem")).to_have_count(0)
                expect(graph.locator(".node-more")).to_have_count(6)
                graph.locator('[data-node="more:双指针"] .graph-node-circle').click()
                expect(graph.locator(".node-problem")).to_have_count(6)
                page.get_by_role("button", name="展开专题", exact=True).click()
                expect(graph.locator(".node-problem")).to_have_count(15)

                topic = graph.locator('[data-node="topic:双指针"]')
                topic.locator(".graph-node-circle").dblclick()
                expect(graph.locator(".node-problem")).to_have_count(9)
                expect(graph.locator('[data-node="more:双指针"]')).to_be_visible()
                detail.get_by_role("button", name="展开题目", exact=True).click()
                expect(graph.locator(".node-problem")).to_have_count(15)
                detail.get_by_role("button", name="聚焦这个专题", exact=True).click()
                expect(graph.locator(".node-topic")).to_have_count(1)
                expect(graph.locator(".node-problem")).to_have_count(6)
                page.get_by_label("图谱专题", exact=True).select_option("")
                page.get_by_label("搜索图谱节点", exact=True).fill("LC26")
                expect(graph.locator(".graph-node")).to_have_count(3)
                expect(detail).to_contain_text("删除有序数组中的重复项")
                page.get_by_label("图谱状态", exact=True).select_option("new")
                expect(page.get_by_text("没有找到匹配的题目", exact=True)).to_be_visible()
                page.get_by_role("button", name="清除筛选", exact=True).click()
                expect(graph.locator(".node-problem")).to_have_count(15)
                page.get_by_label("图谱状态", exact=True).select_option("review")
                expect(graph.locator(".node-problem")).to_have_count(5)
                page.get_by_label("图谱状态", exact=True).select_option("all")

                # 缩放、拖动和平移使用真实鼠标事件，刷新后应保留布局。
                camera = graph.locator(".graph-camera")
                before_zoom = camera.get_attribute("transform")
                page.get_by_role("button", name="放大图谱", exact=True).click()
                assert camera.get_attribute("transform") != before_zoom
                page.get_by_role("button", name="适应画布", exact=True).click()
                dragged = graph.locator('[data-node="problem:15"]')
                initial_position = dragged.get_attribute("transform")
                bounds = dragged.locator(".graph-node-circle").bounding_box()
                x, y = bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2
                page.mouse.move(x, y)
                page.mouse.down()
                page.mouse.move(x + 45, y + 24, steps=8)
                page.mouse.up()
                changed_position = dragged.get_attribute("transform")
                assert changed_position != initial_position
                page.reload()
                expect(graph).to_have_attribute("data-ready", "true")
                expect(dragged).to_have_attribute("transform", changed_position)
                stage = page.locator("#graph-stage").bounding_box()
                before_pan = camera.get_attribute("transform")
                page.mouse.move(stage["x"] + 10, stage["y"] + 140)
                page.mouse.down()
                page.mouse.move(stage["x"] + 65, stage["y"] + 165, steps=5)
                page.mouse.up()
                assert camera.get_attribute("transform") != before_pan
                page.mouse.move(stage["x"] + stage["width"] / 2, stage["y"] + stage["height"] / 2)
                old_scale = page.locator("#graph-zoom").inner_text()
                page.mouse.wheel(0, -160)
                expect(page.locator("#graph-zoom")).not_to_have_text(old_scale)
                page.get_by_role("button", name="重新布局", exact=True).click()
                expect(dragged).to_have_attribute("transform", initial_position)
                assert state_path.read_bytes() == before
                assert log_path.read_bytes() == original_test_log

                # 键盘选择、移动端、触摸双指缩放。
                node42 = graph.locator('[data-node="problem:42"]')
                node42.focus()
                page.keyboard.press("Enter")
                expect(detail).to_contain_text("接雨水")
                page.set_viewport_size({"width": 390, "height": 844})
                expect(graph).to_be_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.screenshot(path=str(artifacts / "algorithm-graph-mobile.png"), full_page=True)
                graph.scroll_into_view_if_needed()
                stage = page.locator("#graph-stage").bounding_box()
                client = context.new_cdp_session(page)
                cx, cy = stage["x"] + stage["width"] / 2, stage["y"] + stage["height"] / 2
                client.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": cx - 25, "y": cy, "id": 1}, {"x": cx + 25, "y": cy, "id": 2}]})
                old_scale = page.locator("#graph-zoom").inner_text()
                client.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": cx - 65, "y": cy, "id": 1}, {"x": cx + 65, "y": cy, "id": 2}]})
                client.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
                expect(page.locator("#graph-zoom")).not_to_have_text(old_scale)
                page.get_by_role("button", name="适应画布", exact=True).click()
                page.set_viewport_size({"width": 1500, "height": 1050})

                # 从图谱直接记录练习，颜色和详情必须随真实接口更新。
                detail.get_by_role("button", name="记录练习", exact=True).click()
                form = page.locator("#practice-dialog")
                expect(form.get_by_label("LeetCode 题号")).to_have_value("42")
                form.get_by_label("一句话复盘").fill("理解左右最大值 <script>window.injected=true</script>")
                form.get_by_role("button", name="保存练习", exact=True).click()
                expect(form).not_to_be_visible()
                expect(graph.locator('[data-node="problem:42"]')).to_have_class(re.compile("category-learning"))
                expect(detail).to_contain_text("2026-10-20")
                assert coach.load(state_path)["completed"]["42"]["count"] == 1
                assert page.evaluate("window.injected") is None
                page.get_by_role("button", name="今日学习", exact=True).click()
                page.get_by_role("button", name="知识图谱", exact=True).click()
                expect(graph.locator('[data-node="problem:42"]')).to_have_attribute("aria-pressed", "true")

                # 多题专题自动分组，以及完全没有学习数据时的空状态。
                synthetic = {"current_topic": "双指针", "goal": "测试图谱", "next_new": [], "completed": {
                    str(pid): {"title": f"演示题目 {pid}", "topic": "双指针", "count": 1, "status": "learning", "last_done": "2026-10-14"}
                    for pid in range(1000, 1020)}}
                state_path.write_text(json.dumps(synthetic, ensure_ascii=False), encoding="utf-8")
                page.evaluate("localStorage.removeItem('algorithm-graph-v1')")
                page.reload()
                expect(graph.locator(".node-problem")).to_have_count(6)
                more = graph.locator('[data-node="more:双指针"]')
                expect(more).to_contain_text("还有 14 道题")
                more.locator(".graph-node-circle").click()
                expect(graph.locator(".node-problem")).to_have_count(20)
                synthetic["completed"] = {}
                state_path.write_text(json.dumps(synthetic, ensure_ascii=False), encoding="utf-8")
                page.reload()
                expect(graph.locator(".graph-node")).to_have_count(1)
                expect(page.locator("#graph-count")).to_contain_text("0 / 0")
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)
    assert not errors, errors
    for path, original in originals.items():
        assert path.read_bytes() == original, f"Real learning data changed: {path}"
    print("PASS: graph data, statuses, selection, calibration, collapse, search, filters, drag persistence, pan, zoom, keyboard, touch, mobile, practice update, large topics and empty state")
    print("Screenshots: artifacts/algorithm-graph.png, artifacts/algorithm-graph-detail.png, artifacts/algorithm-graph-mobile.png")


if __name__ == "__main__":
    main()
