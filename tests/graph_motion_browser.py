"""验证流态图谱的真实动画、弹性拖拽、暂停和减少动态效果，并录制演示。"""
import math
import shutil
import sys
import tempfile
import threading
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import expect, sync_playwright
from tools import dashboard


def samples(page, selector, frames=24):
    return page.evaluate("""async ({selector, frames}) => {
      const element = document.querySelector(selector), out = [];
      for (let i = 0; i < frames; i++) {
        await new Promise(requestAnimationFrame);
        const matrix = element.transform.baseVal.consolidate()?.matrix;
        out.push(matrix ? [matrix.e, matrix.f, matrix.a] : [0, 0, 1]);
      }
      return out;
    }""", {"selector": selector, "frames": frames})


def position(locator):
    return locator.evaluate("el => { const m=el.transform.baseVal.consolidate().matrix; return [m.e,m.f]; }")


def variation(values):
    return max(math.hypot(v[0]-values[0][0], v[1]-values[0][1]) for v in values)


def center(locator):
    bounds = locator.bounding_box()
    return bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    originals = {path: path.read_bytes() for path in (ROOT / "learning-state.json", ROOT / "learning-log.md")}
    artifacts = ROOT / "artifacts"
    errors = []
    with tempfile.TemporaryDirectory(prefix="algorithm-motion-tests-") as folder:
        state = Path(folder) / "learning-state.json"
        log = state.with_name("learning-log.md")
        shutil.copyfile(ROOT / "tests/fixtures" / state.name, state)
        shutil.copyfile(ROOT / "tests/fixtures" / log.name, log)
        original_test_state, original_test_log = state.read_bytes(), log.read_bytes()
        server = dashboard.make_server(state, log, 0, date(2026, 10, 17))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/#graph"
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 1050}, reduced_motion="no-preference")
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
                page.goto(url)
                workspace = page.locator(".graph-workspace")
                toggle = page.get_by_role("button", name="流动效果", exact=True)
                expect(workspace).to_have_attribute("data-running", "true")
                expect(toggle).to_have_attribute("aria-pressed", "true")
                page.wait_for_timeout(1000)  # 等待初次展开后，采样持续漂浮，而非入场位移。
                leaf_selector = '[data-node="problem:15"]'
                movement = samples(page, leaf_selector, 45)
                assert .15 < variation(movement) < 35, movement
                edge = page.locator(".graph-edge").first
                assert "Q" in edge.get_attribute("d")
                particle = page.locator(".graph-particle-dot").first
                initial_particle = particle.get_attribute("cx")
                expect(particle).not_to_have_attribute("cx", initial_particle)

                # 鼠标停留后节点稳定，用户能准确点选。
                leaf = page.locator(leaf_selector)
                page.mouse.move(*center(leaf.locator(".graph-node-circle")))
                assert variation(samples(page, leaf_selector, 18)) < .001
                page.mouse.click(*center(leaf.locator(".graph-node-circle")))
                expect(page.locator("#graph-detail")).to_contain_text("三数之和")
                page.mouse.click(*center(page.locator('[data-node="goal"] .graph-node-circle')))

                topic = page.locator('[data-node="topic:双指针"]')
                x, y = center(topic.locator(".graph-node-circle"))
                page.mouse.move(x, y)
                topic_before, child_before = position(topic), position(leaf)
                page.mouse.down()
                page.mouse.move(x + 90, y + 28, steps=16)
                page.wait_for_timeout(50)
                topic_after, child_after = position(topic), position(leaf)
                child_delta = [child_after[i]-child_before[i] for i in (0, 1)]
                topic_delta = [topic_after[i]-topic_before[i] for i in (0, 1)]
                assert math.hypot(*child_delta) > 3, child_delta
                assert math.hypot(*(child_delta[i]-topic_delta[i] for i in (0, 1))) > 2, (child_delta, topic_delta)
                page.mouse.up()
                released = samples(page, '[data-node="topic:双指针"]', 18)
                assert variation(released) > .1, released
                print("PASS: bounded drift, flowing curves, stable hover, elastic neighbors and release inertia")

                # 画布缩放分帧变化；暂停后节点和视角停止，且设置可保留。
                page.get_by_role("button", name="放大图谱", exact=True).click()
                zoom_frames = samples(page, ".graph-camera", 24)
                assert zoom_frames[-1][2] > zoom_frames[0][2]
                toggle.click()
                expect(workspace).to_have_attribute("data-motion", "off")
                assert variation(samples(page, leaf_selector, 20)) == 0
                assert variation(samples(page, ".graph-camera", 12)) == 0
                expect(particle).not_to_be_visible()
                page.reload()
                expect(toggle).to_have_attribute("aria-pressed", "false")
                toggle.click()
                expect(workspace).to_have_attribute("data-running", "true")

                # 系统减少动态效果、弹窗输入和页面切换都不能留下运行中的动画。
                page.emulate_media(reduced_motion="reduce")
                expect(workspace).to_have_attribute("data-motion", "off")
                expect(toggle).to_be_disabled()
                assert variation(samples(page, leaf_selector, 12)) == 0
                page.emulate_media(reduced_motion="no-preference")
                expect(toggle).to_be_enabled()
                expect(workspace).to_have_attribute("data-running", "true")
                page.get_by_role("button", name="记录练习", exact=True).first.click()
                expect(workspace).to_have_attribute("data-running", "false")
                assert variation(samples(page, leaf_selector, 12)) == 0
                page.locator("#practice-dialog").get_by_role("button", name="取消", exact=True).click()
                expect(workspace).to_have_attribute("data-running", "true")
                page.evaluate("window.oldGraphNode = document.querySelector('[data-node=\"problem:15\"]')")
                page.get_by_role("button", name="今日学习", exact=True).click()
                detached = page.evaluate("window.oldGraphNode.getAttribute('transform')")
                page.wait_for_timeout(200)
                assert page.evaluate("window.oldGraphNode.getAttribute('transform')") == detached
                page.get_by_role("button", name="知识图谱", exact=True).click()
                expect(workspace).to_have_attribute("data-running", "true")
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.locator("#learning-graph").scroll_into_view_if_needed()
                stage = page.locator("#graph-stage").bounding_box()
                cx, cy = stage["x"] + stage["width"] / 2, stage["y"] + stage["height"] / 2
                client = context.new_cdp_session(page)
                client.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": cx-25, "y": cy, "id": 1}, {"x": cx+25, "y": cy, "id": 2}]})
                client.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": cx-50, "y": cy, "id": 1}, {"x": cx+50, "y": cy, "id": 2}]})
                client.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": [{"x": cx-50, "y": cy, "id": 1}]})
                client.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": cx-25, "y": cy+15, "id": 1}]})
                client.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
                touch_frames = samples(page, ".graph-camera", 20)
                assert all(math.isfinite(value) for frame in touch_frames for value in frame), touch_frames
                print("PASS: smooth zoom, pause persistence, reduced motion, dialog pause, cleanup and mobile layout")
                context.close()

                # 单独录一段操作演示，避免把调试与检查流程交给用户。
                demo = browser.new_context(viewport={"width": 1440, "height": 1050},
                    record_video_dir=str(Path(folder) / "video"), record_video_size={"width": 1440, "height": 1050},
                    reduced_motion="no-preference")
                film = demo.new_page()
                film.goto(url)
                expect(film.locator(".graph-workspace")).to_have_attribute("data-running", "true")
                film.wait_for_timeout(1700)
                film.screenshot(path=str(artifacts / "algorithm-graph-fluid.png"), full_page=True)
                film.evaluate("window.scrollTo(0, 100)")
                x, y = center(film.locator('[data-node="topic:双指针"] .graph-node-circle'))
                film.mouse.move(x, y)
                film.mouse.down()
                film.mouse.move(x - 50, y + 30, steps=30)
                film.mouse.up()
                film.mouse.move(1100, 200)
                film.wait_for_timeout(1700)
                film.get_by_role("button", name="放大图谱", exact=True).click()
                film.wait_for_timeout(1100)
                film.get_by_role("button", name="适应画布", exact=True).click()
                film.wait_for_timeout(1300)
                film.mouse.click(*center(film.locator('[data-node="problem:26"] .graph-node-circle')))
                film.wait_for_timeout(1800)
                video = film.video
                demo.close()
                shutil.copyfile(video.path(), artifacts / "algorithm-graph-fluid.webm")
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        assert state.read_bytes() == original_test_state
        assert log.read_bytes() == original_test_log
    assert not errors, errors
    for path, original in originals.items():
        assert path.read_bytes() == original, f"Real learning data changed: {path}"
    print("PASS: original learning data unchanged; demo: artifacts/algorithm-graph-fluid.webm")


if __name__ == "__main__":
    main()
