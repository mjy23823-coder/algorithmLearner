#!/usr/bin/env python3
"""本地算法学习面板。仅使用 Python 标准库，默认只监听本机。"""
import argparse
import json
import re
import secrets
import sys
import threading
import webbrowser
from collections import Counter
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

try:
    from . import assistant, coach, coach_ai, insights, knowledge, learner, workbench
except ImportError:
    import assistant, coach, coach_ai, insights, knowledge, learner, workbench

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def dashboard_data(state, log_path, today, minutes):
    plan = coach.build_plan(state, today, minutes, coach.log_mentions(log_path), knowledge.error_events(state, log_path))
    completed = state.get("completed", {})
    queue = []
    topics = {}
    for pid, rec in completed.items():
        row = coach.problem(state, pid)
        row["overdue_days"] = max(0, (today - coach.due_of(state, rec)).days)
        row["due"] = coach.due_of(state, rec) <= today
        # 保留旧文件的标记，但首刷不能在统计里冒充两次独立通过。
        row["display_status"] = coach.mastery_status(rec)
        row["review_state"] = coach.review_state(state, rec, today)
        row["history"] = [{k: v for k, v in e.items() if k not in ("before", "legacy_same_day")}
                          for e in rec.get("history", [])]
        queue.append(row)
        topic = topics.setdefault(rec["topic"], {"name": rec["topic"], "total": 0, "learned": 0})
        topic["total"] += 1
        topic["learned"] += int(row["display_status"] == "learned")
    queue.sort(key=lambda row: (row["next_due"], row["count"], int(row["id"])))
    activity = Counter(e["date"] for e in coach.practice_events(state) + coach.oral_events(state))
    days = []
    for offset in range(83, -1, -1):
        d = (today - timedelta(days=offset)).isoformat()
        days.append({"date": d, "count": activity[d]})
    forecast = []
    for offset in range(7):
        d = today + timedelta(days=offset)
        count = sum(max(coach.parse_date(r["next_due"]), today) == d for r in queue
                    if r["status"] != "needs_calibration")
        forecast.append({"date": d.isoformat(), "count": count})
    # 待校准题合并成一条提示，逐题明细在复习队列和题目档案中查看。
    unregistered_queue = [r for r in plan["calibration"] if r["id"] not in completed]
    warnings = [{"id": r["id"], "message": f"LC{r['id']}：{r['reason']}"} for r in unregistered_queue]
    old = [r for r in plan["calibration"] if r["id"] in completed]
    if old:
        warnings.append({"message": f"{len(old)} 道旧题的完成情况待校准（" + "、".join("LC" + r["id"] for r in old[:6]) + ("等" if len(old) > 6 else "")
                         + "），不会当作新题；待学不足时每天用 1 个空余名额核对。"})
    legacy = [pid for pid, rec in completed.items() if rec.get("status") == "learned" and rec.get("count", 0) < 2]
    if legacy:
        warnings.append({"message": f"{len(legacy)} 道旧题只有一次完成记录，面板将其显示为“待验证”，原有标记保留。"})
    unregistered = sorted(coach.log_mentions(log_path) - set(completed) - set(state.get("next_new", [])), key=int)
    if unregistered:
        warnings.append({"message": f"日志中另有 {len(unregistered)} 个题号尚未登记：" + "、".join("LC"+pid for pid in unregistered[:8]) + "。其中可能包含学习计划，请先核对是否实际练过。"})
    return {"date": today.isoformat(), "revision": state.source_hash,
            "goal": state.get("goal", "算法学习"), "language": state.get("language", "python"),
            "plan": plan, "queue": queue, "topics": list(topics.values()),
            "activity": days, "forecast": forecast, "warnings": warnings, "unregistered_mentions": unregistered,
            "stats": {"recorded": len(queue), "learned": coach.progress_summary(state, today)["learned"],
                      "due": len(plan["reviews"]) + len(plan["short_recall"]),
                      "today_done": sum(r["result"] in ("independent", "hinted") for r in plan["done_today"])},
            "weekly": coach.weekly_report(state, today), "knowledge": knowledge.build_knowledge(state, log_path),
            "insights": report_with_markdown(state, today, log_path),
            "next_new": [coach.problem(state, pid) for pid in state.get("next_new", [])],
            "profile": plan["profile"], "paces": learner.PACES, "advice": assistant.read_cache(log_path.parent, "profile-advice"),
            "weekly_advice": assistant.current_weekly(log_path.parent, today), "plan_chat": assistant.plan_chat(log_path.parent, today)}


def report_with_markdown(state, today, log_path):
    report = insights.ability_report(state, today, log_path)
    report["markdown"] = insights.to_markdown(report)
    return report


def log_sections(path):
    content = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    matches = list(re.finditer(r"^## (\d{4}-\d{2}-\d{2})[^\r\n]*", content, re.M))
    sections = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[match.end():end].strip()
        body = re.sub(r"<!-- algo-wrap:[^>]+ -->", "", body).strip()
        sections.append({"date": match.group(1), "title": match.group()[3:], "body": body})
    return sorted(reversed(sections), key=lambda section: section["date"], reverse=True)


def field_text(payload, key, default="", maximum=2000):
    value = payload.get(key, default)
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"{key} 必须是长度不超过 {maximum} 的文字")
    return value.strip()


def make_server(state_path, log_path, port=8765, fixed_date=None):
    token = secrets.token_urlsafe(32)
    mutation_lock = threading.Lock()
    workspace = workbench.Workbench(state_path.parent, log_path, fixed_date)

    class Handler(BaseHTTPRequestHandler):
        def reject(self, status, message):
            # 消费已发送的短请求体，避免 Windows 在提前关闭连接时用 RST 丢弃错误响应。
            if self.command == "POST":
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if 0 < size <= 65536:
                        self.connection.settimeout(5)
                        self.rfile.read(size)
                except (ValueError, OSError):
                    pass
            self.send_json(status, {"error": message})

        def log_message(self, format, *args):
            # 终端只显示服务器状态，避免每次刷新刷屏。
            pass

        def local_request(self):
            expected = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host") not in expected:
                self.reject(403, "仅接受本机访问")
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {"http://" + host for host in expected}:
                self.reject(403, "访问来源不匹配")
                return False
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                self.reject(403, "请直接打开本地学习面板")
                return False
            return True

        def send_bytes(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, status, data):
            self.send_bytes(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self):
            if not self.local_request():
                return
            url = urlsplit(self.path)
            try:
                if url.path == "/api/health":
                    self.send_json(200, {"app": "algorithm-learning", "state": str(state_path.resolve())})
                elif url.path == "/api/dashboard":
                    state = coach.load(state_path)
                    # 页面没有指定时，用画像里设定的每日计划时间。
                    minutes = int(parse_qs(url.query).get("minutes", [learner.settings(state)["daily_minutes"]])[0])
                    data = dashboard_data(state, log_path, fixed_date or date.today(), minutes)
                    data["token"] = token
                    self.send_json(200, data)
                elif url.path == "/api/log":
                    self.send_json(200, {"sections": log_sections(log_path)})
                elif url.path == "/api/export":
                    self.send_json(200, coach.load(state_path))
                elif url.path == "/api/workbench":
                    pid = parse_qs(url.query).get("id", [""])[0]
                    self.send_json(200, workspace.describe(coach.load(state_path), pid))
                elif url.path == "/api/coach/settings":
                    self.send_json(200, coach_ai.load_settings(state_path.parent))
                elif url.path == "/api/workbench/agent":
                    params = parse_qs(url.query)
                    self.send_json(200, workspace.agents.status(coach.problem_id(params.get("id", [""])[0]), params.get("job", [""])[0]))
                elif url.path == "/api/workbench/run":
                    params = parse_qs(url.query)
                    self.send_json(200, workspace.read_run(params.get("id", [""])[0], params.get("run_id", [""])[0]))
                else:
                    assets = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "application/javascript"),
                          "/coach.js": ("coach.js", "application/javascript"), "/mock.js": ("mock.js", "application/javascript"),
                          "/profile.js": ("profile.js", "application/javascript"), "/ai.js": ("ai.js", "application/javascript"),
                          "/extras.css": ("extras.css", "text/css"),
                              "/graph.js": ("graph.js", "application/javascript"), "/graph.css": ("graph.css", "text/css"),
                              "/workbench.js": ("workbench.js", "application/javascript"), "/workbench.css": ("workbench.css", "text/css"),
                              "/style.css": ("style.css", "text/css"), "/favicon.svg": ("favicon.svg", "image/svg+xml")}
                    if url.path not in assets:
                        self.send_json(404, {"error": "页面不存在"})
                        return
                    filename, content_type = assets[url.path]
                    self.send_bytes(200, (WEB / filename).read_bytes(), content_type + "; charset=utf-8")
            except (ValueError, KeyError) as exc:
                self.send_json(400, {"error": str(exc)})
            except OSError as exc:
                self.send_json(500, {"error": "无法读取学习文件：" + str(exc)})

        def do_POST(self):
            if not self.local_request():
                return
            if not secrets.compare_digest(self.headers.get("X-Coach-Token", ""), token):
                self.reject(403, "页面已过期，请刷新后重试")
                return
            try:
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ValueError("请求必须使用 JSON")
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 200000:
                    raise ValueError("请求内容过长或为空")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("请求格式不正确")
                if urlsplit(self.path).path == "/api/shutdown":
                    self.send_json(200, {"message": "学习面板服务已停止"})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                endpoint = urlsplit(self.path).path
                if endpoint in ("/api/workbench/coach", "/api/workbench/agent", "/api/coach/settings", "/api/coach/test",
                                "/api/coach/models", "/api/mock/start", "/api/profile/advice", "/api/oral/judge", "/api/weekly/advice",
                                "/api/plan/ask"):
                    # 只写草稿、对话和本机设置，不改学习进度。
                    if endpoint == "/api/workbench/coach":
                        response = workspace.coach_chat(coach.load(state_path), payload)
                    elif endpoint == "/api/workbench/agent":
                        response = workspace.agents.start(coach.load(state_path), payload)
                    elif endpoint == "/api/coach/models":
                        try:
                            override = {"base_url": field_text(payload, "base_url", maximum=300), "api_key": field_text(payload, "api_key", maximum=400)}
                            provider = payload.get("provider") if payload.get("provider") in coach_ai.RELAYS else None
                            response = {"ok": True, "models": coach_ai.list_models(coach_ai.connection(state_path.parent, override, provider))}
                        except coach_ai.CoachError as exc:
                            response = {"ok": False, "error": str(exc)}
                    elif endpoint == "/api/coach/settings":
                        response = coach_ai.save_settings(state_path.parent, payload)
                    elif endpoint == "/api/coach/test":
                        response = self.test_coach(payload)
                    elif endpoint == "/api/profile/advice":
                        response = assistant.profile_advice(state_path.parent, coach.load(state_path), log_path, fixed_date or date.today())
                    elif endpoint == "/api/oral/judge":
                        response = assistant.judge_oral(state_path.parent, coach.load(state_path), payload.get("id", ""), payload.get("explanation"),
                                                        fixed_date or date.today())
                    elif endpoint == "/api/weekly/advice":
                        response = assistant.weekly_advice(state_path.parent, coach.load(state_path), log_path, fixed_date or date.today())
                    elif endpoint == "/api/plan/ask":
                        state = coach.load(state_path)
                        minutes = payload.get("minutes", learner.settings(state)["daily_minutes"])
                        if type(minutes) is not int or not 15 <= minutes <= 600:
                            raise ValueError("可用时间应为 15～600 分钟")
                        response = assistant.ask_plan(state_path.parent, state, log_path, fixed_date or date.today(), minutes, payload.get("question"))
                    else:
                        response = workspace.start_mock(coach.load(state_path), payload, fixed_date or date.today())
                    self.send_json(200, response)
                    return
                if endpoint in ("/api/workbench/draft", "/api/workbench/hint", "/api/workbench/run", "/api/workbench/start"):
                    if endpoint.endswith("/draft"):
                        response = {"draft": workspace.save_draft(payload)}
                    elif endpoint.endswith("/hint"):
                        response = workspace.reveal(payload)
                    elif endpoint.endswith("/start"):
                        response = {"draft": workspace.start_round(payload)}
                    else:
                        response = workspace.run(payload, fixed_date or date.today())
                    self.send_json(200, response)
                    return
                with mutation_lock:
                    state = coach.load(state_path)
                    request_id = field_text(payload, "request_id", maximum=80)
                    if request_id and request_id in state.get("_requests", {}):
                        self.send_json(200, state["_requests"][request_id])
                        return
                    if payload.get("revision") != state.source_hash:
                        self.send_json(409, {"error": "学习记录已更新，请刷新后再保存，避免覆盖其他会话"})
                        return
                    today = fixed_date or date.today()
                    result = self.mutate(urlsplit(self.path).path, state, payload, today)
                    if request_id:
                        receipts = state.setdefault("_requests", {})
                        receipts[request_id] = result
                        state["_requests"] = dict(list(receipts.items())[-100:])
                    if result.pop("_already_saved", False):
                        if request_id:
                            coach.save(state_path, state)
                    else:
                        coach.save(state_path, state)
                    self.send_json(200, result)
            except (ValueError, KeyError, TypeError) as exc:
                self.send_json(400, {"error": str(exc)})
            except OSError as exc:
                self.send_json(500, {"error": "保存失败，可重试：" + str(exc)})

        def test_coach(self, payload):
            provider = payload.get("provider")
            if provider not in (*coach_ai.RELAYS, "claude_cli"):
                raise ValueError("请选择要测试的模型通道")
            model = (payload.get("model") or coach_ai.DEFAULT_MODELS[provider]).strip()
            override = {"base_url": field_text(payload, "base_url", maximum=300), "api_key": field_text(payload, "api_key", maximum=400)}
            coach_ai.normalize_base(override["base_url"])
            try:
                result = coach_ai.probe(state_path.parent, provider, model, override)
            except coach_ai.CoachError as exc:
                return {"ok": False, "provider": provider, "error": str(exc)}
            # 测试成功后才保存地址、Key 并启用；Key 只写入本机文件，不返回页面。
            settings = {"provider": provider, "model": model, "tested_at": result["tested_at"]}
            if provider in coach_ai.RELAYS:
                settings.update(base_url=override["base_url"] or coach_ai.load_settings(state_path.parent)["base_url"], api_key=override["api_key"])
            coach_ai.save_settings(state_path.parent, settings)
            return result

        def mutate(self, path, state, payload, today):
            if path == "/api/workbench/complete":
                return workspace.complete(state, payload, today)
            if path == "/api/practice":
                pid = coach.problem_id(payload.get("id", ""))
                mock = payload.get("mock", False)
                if type(mock) is not bool:
                    raise ValueError("限时训练标记格式不正确")
                rec = coach.record_result(state, pid, payload.get("result"), today,
                                          field_text(payload, "title", maximum=100),
                                          field_text(payload, "topic", maximum=100),
                                          field_text(payload, "note"), payload.get("minutes"), mock)
                return {"message": f"LC{pid} 已记录，下次复习 {rec['next_due']}", "next_due": rec["next_due"]}
            if path == "/api/queue":
                ids = payload.get("ids")
                if not isinstance(ids, list) or len(ids) > 100:
                    raise ValueError("请提供最多 100 道题号")
                ids = [coach.problem_id(pid) for pid in ids]
                action = payload.get("action", "add")
                queue = state.get("next_new", [])
                if action == "add":
                    state["next_new"] = list(dict.fromkeys(queue + ids))
                elif action == "remove":
                    state["next_new"] = [pid for pid in queue if pid not in ids]
                else:
                    raise ValueError("不支持的队列操作")
                return {"message": "待学队列已更新"}
            if path == "/api/oral":
                result = payload.get("result")
                detail = {k: payload[k] for k in ("explanation", "marks", "judged_by") if k in payload}
                rec = coach.record_oral(state, payload.get("id", ""), result, today, detail or None)
                return {"message": f"LC{coach.problem_id(payload['id'])} 口述复习：{coach.ORAL_LABELS[result]}，下次复习 {rec['next_due']}"
                                   + ("（完整重写）" if result != "independent" else ""), "next_due": rec["next_due"]}
            if path == "/api/profile":
                saved = learner.apply_settings(state, {k: payload[k] for k in ("target_date", "daily_minutes", "pace") if k in payload}, today)
                return {"message": "学习目标已更新，推荐会按新的设定调整", "profile": saved}
            if path == "/api/recommend/skip":
                pid = coach.problem_id(payload.get("id", ""))
                if pid in state.get("completed", {}):
                    raise ValueError(f"LC{pid} 已经有练习记录，不在新题推荐里")
                learner.skip_recommendation(state, pid, today)
                return {"message": f"已换掉 LC{pid}，7 天内不再推荐"}
            if path == "/api/session":
                topic = field_text(payload, "topic", maximum=100)
                if not topic:
                    raise ValueError("请输入当前专题")
                state["current_topic"] = topic
                state.setdefault("session", {})["next_action"] = field_text(payload, "next_action")
                return {"message": "学习方向已更新"}
            if path == "/api/wrap":
                result = coach.wrap_session(state, state_path, log_path, today,
                                            field_text(payload, "note"), field_text(payload, "next_action"))
                result["_already_saved"] = True
                return result
            raise ValueError("不支持的操作")

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="算法学习管理面板（本机运行）")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--state", type=Path, default=ROOT / "learning-state.json")
    parser.add_argument("--log", type=Path)
    parser.add_argument("--open", action="store_true", help="启动后打开浏览器")
    parser.add_argument("--stop", action="store_true", help="停止同端口、同进度文件的本地面板")
    args = parser.parse_args()
    log_path = args.log or args.state.with_name("learning-log.md")
    url = f"http://127.0.0.1:{args.port}"
    running = False
    if args.open or args.stop:
        try:
            with urlopen(url + "/api/health", timeout=1) as response:
                health = json.load(response)
            running = health.get("app") == "algorithm-learning" and health.get("state") == str(args.state.resolve())
        except (OSError, ValueError):
            pass
    if args.stop:
        if not running:
            parser.exit(1, "没有找到这个项目正在运行的面板。\n")
        try:
            with urlopen(url + "/api/dashboard", timeout=5) as response:
                token = json.load(response)["token"]
            request = Request(url + "/api/shutdown", data=b"{}",
                              headers={"Content-Type": "application/json", "X-Coach-Token": token}, method="POST")
            with urlopen(request, timeout=5) as response:
                print(json.load(response)["message"])
        except (OSError, ValueError) as exc:
            parser.exit(1, f"停止失败：{exc}\n")
        return
    if running:
        webbrowser.open(url)
        print(f"面板已经运行，已打开：{url}")
        return
    try:
        coach.load(args.state)
        server = make_server(args.state, log_path, args.port)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"无法启动：{exc}\n如果端口被占用，可加 --port 8766。\n")
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"算法学习管理面板：{url}\n学习进度：{args.state}\n按 Ctrl+C 停止服务。", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
