"""工作台草稿、代码版本、本地测试与学习结果的连接。"""
import json
import math
import re
import secrets
import threading
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

try:
    from . import agent, coach, coach_ai, knowledge, learner, problem_bank, code_runner, statements
except ImportError:
    import agent, coach, coach_ai, knowledge, learner, problem_bank, code_runner, statements

DRAFT_FIELDS = ("code", "idea", "time_complexity", "space_complexity", "boundary", "takeaway", "recognition", "followup")
MOCK_DIMENSIONS = {"recognition": "题型识别", "communication": "沟通表达", "code": "代码正确性",
                   "complexity": "复杂度分析", "time": "时间控制"}


def text_field(data, key, maximum=2000):
    value = data.get(key, "")
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"{key} 必须是长度不超过 {maximum} 的文字")
    return value


def utc_now():
    return datetime.now(timezone.utc)


def mock_elapsed(mock):
    started = datetime.fromisoformat(mock["started_at"])
    return max(0, min(86400, round((utc_now() - started).total_seconds())))


class Workbench:
    def __init__(self, root, log_path, today=None):
        self.root, self.log_path = Path(root), log_path
        # 面板以固定日期启动时（测试），画像的时间窗口也按这个日期计算。
        self.fixed_today = today
        self.lock = threading.RLock()
        self.runners = threading.BoundedSemaphore(2)
        self.debug_sessions = {}
        self.agents = agent.AgentRunner(self)

    def start_debug(self, payload):
        pid = coach.problem_id(payload.get("id", ""))
        exercise = problem_bank.get_exercise(pid)
        if not exercise:
            raise ValueError("这道题没有可调试的本地练习")
        code = text_field(payload, "code", 48000)
        breakpoints = payload.get("breakpoints") or []
        with self.lock:
            # 已结束但页面未轮询的会话不会继续占用名额。
            self.debug_sessions = {key: value for key, value in self.debug_sessions.items() if not value.closed}
            if len(self.debug_sessions) >= 2:
                raise ValueError("最多同时调试 2 道题，请先停止已有会话")
            session = code_runner.DebugSession(code, exercise, breakpoints)
            self.debug_sessions[session.id] = session
        return {"debug_id": session.id, "events": session.poll()}

    def debug_status(self, debug_id):
        with self.lock:
            session = self.debug_sessions.get(debug_id)
            if not session:
                raise ValueError("调试会话不存在或已结束")
            events = session.poll()
            if any(e.get("event") in ("done", "error") for e in events):
                session.stop()
                self.debug_sessions.pop(debug_id, None)
            return {"events": events}

    def debug_command(self, debug_id, command):
        with self.lock:
            session = self.debug_sessions.get(debug_id)
            if not session or session.closed:
                raise ValueError("调试会话不存在或已结束")
            if command not in ("step", "continue", "stop"):
                raise ValueError("不支持的调试命令")
            if command == "stop":
                session.stop()
                self.debug_sessions.pop(debug_id, None)
                return {"events": [{"event": "done", "stopped": True}]}
            session.command(command)
            return {"events": session.poll()}

    def close_debug(self):
        with self.lock:
            for session in self.debug_sessions.values():
                session.stop()
            self.debug_sessions.clear()

    def agent_hints(self, pid, session_id):
        """智能体在本轮计为提示的次数，记在对话记录里，避免长任务改动草稿版本。"""
        return sum(1 for m in coach_ai.read_transcript(self.root, pid, session_id) if m.get("role") == "agent" and m.get("counted"))

    def draft_path(self, pid):
        return self.root / "solutions" / ".drafts" / f"lc{coach.problem_id(pid)}.json"

    def read_draft(self, pid):
        path = self.draft_path(pid)
        if not path.exists():
            return {"revision": None, "hints_used": 0}
        raw = path.read_bytes()
        return {**json.loads(raw.decode("utf-8")), "revision": coach.digest(raw)}

    def save_draft(self, payload, reveal=None):
        pid = coach.problem_id(payload.get("id", ""))
        with self.lock:
            old = self.read_draft(pid)
            if payload.get("draft_revision") != old["revision"]:
                raise ValueError("这道题的草稿已在另一页面更新，请重新打开后核对，当前输入仍保留")
            draft = {key: text_field(payload, key, 48000 if key == "code" else 2000) for key in DRAFT_FIELDS}
            extras = payload.get("extra_cases", [])
            if not isinstance(extras, list) or len(extras) > 20 or len(json.dumps(extras)) > 60000:
                raise ValueError("自定义用例过多或过大")
            elapsed = payload.get("elapsed_seconds", 0)
            if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or not 0 <= elapsed <= 86400:
                raise ValueError("练习计时超出范围")
            tags = payload.get("error_tags", [])
            allowed = {e["id"] for e in knowledge.ERRORS}
            if not isinstance(tags, list) or any(tag not in allowed for tag in tags):
                raise ValueError("存在无法识别的错因标签")
            hints = max(old.get("hints_used", 0), reveal or 0)
            draft.update(id=pid, extra_cases=extras, elapsed_seconds=round(elapsed), error_tags=list(dict.fromkeys(tags)),
                         hints_used=hints, coach_hints=old.get("coach_hints", 0), session_id=old.get("session_id") or uuid.uuid4().hex,
                         updated_at=utc_now().isoformat())
            if old.get("mock"):
                draft["mock"] = old["mock"]
            return self.write_draft(pid, draft)

    def write_draft(self, pid, draft):
        path = self.draft_path(pid)
        path.parent.mkdir(parents=True, exist_ok=True)
        coach.atomic_write(path, (json.dumps(draft, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        return {**draft, "revision": coach.digest(path.read_bytes())}

    def start_round(self, payload, mock_minutes=None):
        pid = coach.problem_id(payload.get("id", ""))
        exercise = problem_bank.get_exercise(pid)
        if not exercise:
            raise ValueError("这道题尚未配置工作台")
        with self.lock:
            old = self.read_draft(pid)
            if payload.get("draft_revision") != old["revision"]:
                raise ValueError("草稿已在另一页面更新，请先刷新核对")
            path = self.draft_path(pid)
            if path.exists():
                archive = self.root / "solutions" / ".drafts" / "archive"
                archive.mkdir(parents=True, exist_ok=True)
                coach.atomic_write(archive / f"lc{pid}-{uuid.uuid4().hex}.json", path.read_bytes())
            fresh = {"id": pid, "code": exercise["starter"], "extra_cases": [], "elapsed_seconds": 0,
                     "error_tags": [], "hints_used": 0, "coach_hints": 0, "session_id": uuid.uuid4().hex,
                     "updated_at": utc_now().isoformat(), **{key: "" for key in DRAFT_FIELDS if key != "code"}}
            if mock_minutes is not None:
                # 计时以服务端开始时间为准，刷新页面或换设备都不会重置。
                fresh["mock"] = {"started_at": utc_now().isoformat(), "limit_minutes": mock_minutes}
            path.parent.mkdir(parents=True, exist_ok=True)
            coach.atomic_write(path, json.dumps(fresh, ensure_ascii=False, indent=2).encode("utf-8"))
            return self.read_draft(pid)

    def start_mock(self, state, payload, today):
        pid = payload.get("id")
        if pid in (None, "", "random"):
            picks = coach.build_plan(state, today, 120, coach.log_mentions(self.log_path))["mock_candidates"]
            if not picks:
                raise ValueError("暂时没有可用于模拟的未做题，可先在题目档案加入新题")
            pid = secrets.choice(picks)["id"]
        pid = coach.problem_id(pid)
        limit = payload.get("limit_minutes")
        if type(limit) is not int or not 5 <= limit <= 90:
            raise ValueError("模拟时长应为 5～90 分钟")
        draft = self.start_round({"id": pid, "draft_revision": self.read_draft(pid)["revision"]}, mock_minutes=limit)
        return {"id": pid, "draft": draft}

    def latest_run(self, pid, session_id):
        folder = self.root / "solutions" / f"lc{pid}"
        if not session_id or not folder.exists():
            return None
        for path in sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                run = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if run.get("session_id") == session_id:
                return run
        return None

    def describe(self, state, pid):
        pid = coach.problem_id(pid)
        exercise = problem_bank.get_exercise(pid)
        draft = self.read_draft(pid)
        if exercise:
            # 未点击的提示不提前送到页面，避免绕过提示次数记录。
            hints = exercise.pop("hints")
            exercise["revealed_hints"] = hints[:draft.get("hints_used", 0)]
            exercise["hint_count"] = len(hints)
        links = knowledge.build_knowledge(state, self.log_path)
        runs = self.root / "solutions" / f"lc{pid}"
        versions = []
        if runs.exists():
            for path in sorted(runs.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
                entry = json.loads(path.read_text(encoding="utf-8"))
                versions.append({"run_id": entry["run_id"], "created_at": entry["created_at"], "passed": entry["result"]["passed"],
                                 "passed_count": entry["result"]["passed_count"], "total": entry["result"]["total"]})
        history = [{k: v for k, v in e.items() if k in ("date", "result", "note", "kind", "mock")}
                   for e in state.get("completed", {}).get(pid, {}).get("history", [])]
        # 模板列表只依据项目题解规则，与状态无关；未做过的题也能看到。
        patterns = [p for p in knowledge.PATTERNS if pid in p["problem_ids"]]
        return {"problem": coach.problem(state, pid), "exercise": exercise, "draft": draft, "versions": versions,
                "statement": statements.view(pid, exercise),
                "patterns": patterns, "history": history, "server_now": utc_now().isoformat(),
                "coach": {**coach_ai.load_settings(self.root),
                          "transcript": coach_ai.read_transcript(self.root, pid, draft.get("session_id")),
                          "agent_hints": self.agent_hints(pid, draft.get("session_id")), "agent_actions": agent.ACTIONS},
                # 学习画像：教练据此因材施教（模拟面试时不使用）。
                "learner": learner.coach_brief(state, self.fixed_today or date.today(), pid),
                "mock_dimensions": MOCK_DIMENSIONS,
                "errors": knowledge.ERRORS, "historical_errors": [e for e in links["errors"] if pid in e["problem_ids"]]}

    def reveal(self, payload):
        pid = coach.problem_id(payload.get("id", ""))
        exercise = problem_bank.get_exercise(pid)
        if not exercise:
            raise ValueError("这道题尚未配置分层提示")
        level = payload.get("level")
        if type(level) is not int or not 1 <= level <= len(exercise["hints"]):
            raise ValueError("提示层级不正确")
        draft = self.save_draft(payload, reveal=level)
        return {"draft": draft, "hints": exercise["hints"][:draft["hints_used"]]}

    def coach_chat(self, state, payload, on_delta=None):
        """一轮教练对话。提示类帮助计入本轮提示次数，完成时按“提示后完成”记录。"""
        pid = coach.problem_id(payload.get("id", ""))
        mode = payload.get("mode")
        if mode not in coach_ai.MODES:
            raise ValueError("不支持的教练模式")
        question = text_field(payload, "message", 1000).strip()
        if mode == "ask" and not question:
            raise ValueError("请输入想问的题意或 Python 写法问题")
        info = self.describe(state, pid)
        # 页面带上当前输入时先保存草稿，让教练看到最新的思路和代码。
        draft = self.save_draft(payload) if "code" in payload else info["draft"]
        mock = bool(draft.get("mock"))
        run = self.latest_run(pid, draft.get("session_id"))
        settings = coach_ai.load_settings(self.root)
        provider, notice, hint_text = settings["provider"], "", None
        level = draft.get("hints_used", 0) + draft.get("coach_hints", 0) + 1
        if mode == "hint" and provider == "offline":
            # 离线提示就是下一层分层提示，与“提示 1/2/3”按钮共用计数。
            exercise = info.get("exercise")
            if exercise and draft.get("hints_used", 0) < exercise["hint_count"]:
                revealed = self.reveal({**{k: draft.get(k, "") for k in DRAFT_FIELDS}, "id": pid, "extra_cases": draft.get("extra_cases", []),
                                        "elapsed_seconds": draft.get("elapsed_seconds", 0), "error_tags": draft.get("error_tags", []),
                                        "draft_revision": draft["revision"], "level": draft.get("hints_used", 0) + 1})
                draft, hint_text = revealed["draft"], f"提示 {len(revealed['hints'])}：{revealed['hints'][-1]}"
        transcript = coach_ai.read_transcript(self.root, pid, draft.get("session_id"))
        assisted = None
        text = None
        if provider != "offline":
            prompt = coach_ai.context_text(info, draft, run, transcript, mock) + f"\n\n用户这次选择「{coach_ai.MODES[mode]}」" + (f"，并说：{question}" if question else "。")
            try:
                system = coach_ai.system_prompt(mode, min(level, 3), mock)
                conn = coach_ai.connection(self.root, provider=provider) if provider in coach_ai.RELAYS else None
                raw = (coach_ai.ask_model_stream(provider, system, prompt, settings["model"], on_delta, conn=conn)
                       if on_delta else coach_ai.ask_model(provider, system, prompt, settings["model"], conn=conn))
                text, assisted = coach_ai.split_assist(raw)
            except coach_ai.CoachError as exc:
                notice = f"{exc}；本次改用离线引导。"
        if text is None:
            provider_used = "offline"
            text = coach_ai.offline_reply(mode, info, draft, run, hint_text, mock)
            counted = mode == "hint" and hint_text is not None
        else:
            provider_used = provider
            passed = bool(run and run["result"]["passed"])
            # 模型给出的提示、未通过用例前的代码定位，以及自由提问里给出的解题方向，都算作帮助。
            counted = mode == "hint" or (mode == "review" and not passed) or (mode in ("ask", "explain") and assisted is True)
        if counted and provider_used != "offline":
            with self.lock:
                current = self.read_draft(pid)
                current["coach_hints"] = current.get("coach_hints", 0) + 1
                current.pop("revision", None)
                draft = self.write_draft(pid, current)
        stamp = coach_ai.now()
        messages = [{"role": "user", "mode": mode, "text": question or coach_ai.MODES[mode], "at": stamp},
                    {"role": "coach", "mode": mode, "text": text, "at": stamp, "provider": provider_used, "counted": bool(counted)}]
        with self.lock:
            transcript = coach_ai.append_transcript(self.root, pid, draft["session_id"], messages, coach.atomic_write)
        if counted:
            notice = (notice + " " if notice else "") + "这次属于提示类帮助，完成时会按“提示后完成”记录。"
        return {"reply": text, "provider": provider_used, "counted": bool(counted), "notice": notice.strip(),
                "draft": draft, "transcript": transcript, "hints": (info.get("exercise") or {}).get("revealed_hints", []) if not hint_text
                else problem_bank.get_exercise(pid)["hints"][:draft["hints_used"]]}

    def run(self, payload, today=None):
        pid = coach.problem_id(payload.get("id", ""))
        exercise = problem_bank.get_exercise(pid)
        if not exercise:
            raise ValueError("这道题尚未配置本地用例，可先通过聊天教练检查")
        if not self.runners.acquire(blocking=False):
            raise ValueError("已有两份代码正在测试，请稍后重试")
        try:
            draft = self.save_draft(payload)
            result = code_runner.run_code(draft["code"], exercise, draft["extra_cases"])
            run_id = uuid.uuid4().hex
            folder = self.root / "solutions" / f"lc{pid}"
            folder.mkdir(parents=True, exist_ok=True)
            source = folder / f"{run_id}.py"
            coach.atomic_write(source, draft["code"].encode("utf-8"))
            run = {"id": pid, "run_id": run_id, "code": draft["code"], "code_hash": coach.digest(draft["code"].encode("utf-8")),
                   "session_id": draft["session_id"], "practice_date": (today or date.today()).isoformat(),
                   "extra_cases": draft["extra_cases"],
                   "created_at": datetime.now(timezone.utc).isoformat(), "hints_used": draft["hints_used"], "result": result,
                   "source_path": source.relative_to(self.root).as_posix()}
            coach.atomic_write(folder / f"{run_id}.json", json.dumps(run, ensure_ascii=False, indent=2).encode("utf-8"))
            return {"run_id": run_id, "result": result, "draft": draft, "code_hash": run["code_hash"]}
        finally:
            self.runners.release()

    def read_run(self, pid, run_id):
        if not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f]{32}", run_id):
            raise ValueError("测试记录编号无效")
        path = self.root / "solutions" / f"lc{coach.problem_id(pid)}" / f"{run_id}.json"
        if not path.exists():
            raise ValueError("找不到对应测试记录，请重新运行用例")
        return json.loads(path.read_text(encoding="utf-8"))

    def complete(self, state, payload, today):
        pid = coach.problem_id(payload.get("id", ""))
        run = self.read_run(pid, payload.get("run_id"))
        code = text_field(payload, "code", 48000)
        if coach.digest(code.encode("utf-8")) != run["code_hash"]:
            raise ValueError("代码已在测试后修改，请重新运行用例再保存结果")
        if payload.get("extra_cases", []) != run.get("extra_cases", []):
            raise ValueError("自定义用例已改变，请重新运行后再保存结果")
        result = payload.get("result")
        if result not in coach.RESULTS:
            raise ValueError("请选择真实完成情况")
        if result != "failed" and not run["result"]["passed"]:
            raise ValueError("本地用例尚未全部通过，可保存为暂未完成，或修正后重试")
        draft = self.read_draft(pid)
        if run.get("session_id") != draft.get("session_id") or run.get("practice_date") != today.isoformat():
            raise ValueError("请在本轮练习中重新运行用例，再记录今天的结果")
        hints = max(draft.get("hints_used", 0), run["hints_used"])
        coach_hints = draft.get("coach_hints", 0) + self.agent_hints(pid, draft.get("session_id"))
        adjusted = result == "independent" and (hints > 0 or coach_hints > 0)
        if adjusted:
            result = "hinted"
        mock = draft.get("mock")
        if mock and mock.get("completed"):
            raise ValueError("这场模拟面试已经保存过，请开始新的一场")
        elapsed = mock_elapsed(mock) if mock else payload.get("elapsed_seconds", draft.get("elapsed_seconds", 0))
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or not 0 <= elapsed <= 86400:
            raise ValueError("练习计时超出范围")
        tags = payload.get("error_tags", [])
        if not isinstance(tags, list) or any(tag not in {e["id"] for e in knowledge.ERRORS} for tag in tags):
            raise ValueError("错因标签无效")
        fields = {key: text_field(payload, key) for key in DRAFT_FIELDS if key != "code"}
        fields = {k: v for k, v in fields.items() if v or k not in ("recognition", "followup")}
        review = self.mock_review(payload, mock, elapsed, hints + coach_hints) if mock else None
        row = coach.problem(state, pid)
        note = (fields["takeaway"] or (review or {}).get("improve", "")).strip()
        record = coach.record_result(state, pid, result, today, row["title"], row["topic"], note,
                                     max(1, math.ceil(elapsed / 60)) if elapsed else None, mock=bool(mock))
        record["history"][-1].update(error_tags=list(dict.fromkeys(tags)), pattern_ids=knowledge.pattern_ids(pid), **fields,
                                    validation={"kind": "local_cases", "run_id": run["run_id"], "passed": run["result"]["passed"],
                                                "passed_count": run["result"]["passed_count"], "total": run["result"]["total"], "code_hash": run["code_hash"]},
                                    code_path=run["source_path"], elapsed_seconds=round(elapsed), hints_used=hints, coach_hints=coach_hints)
        if review:
            record["history"][-1]["mock_review"] = review
            with self.lock:
                current = self.read_draft(pid)
                current.pop("revision", None)
                current["mock"] = {**current.get("mock", {}), "completed": True}
                self.write_draft(pid, current)
        message = f"LC{pid} 已记录，下次复习 {record['next_due']}"
        if adjusted:
            message += "；本次看过提示，已按提示后完成保存"
        return {"message": message, "result": result, "next_due": record["next_due"], "status": coach.mastery_status(record),
                "mock_review": review}

    def mock_review(self, payload, mock, elapsed, helps):
        scores = payload.get("scores")
        if not isinstance(scores, dict) or set(scores) != set(MOCK_DIMENSIONS) or any(type(v) is not int or not 1 <= v <= 5 for v in scores.values()):
            raise ValueError("请为五个维度各打 1～5 分")
        reasons = payload.get("score_reasons", {})
        if not isinstance(reasons, dict) or any(k not in MOCK_DIMENSIONS or not isinstance(v, str) or len(v) > 300 for k, v in reasons.items()):
            raise ValueError("评分理由格式不正确，每条不超过 300 字")
        scored_by = payload.get("scored_by", "self")
        if scored_by not in ("self", "coach_suggested"):
            raise ValueError("评分来源不正确")
        limit = mock["limit_minutes"] * 60
        return {"limit_minutes": mock["limit_minutes"], "elapsed_seconds": elapsed, "overtime": elapsed > limit,
                "scores": scores, "score_reasons": {k: v.strip() for k, v in reasons.items() if v.strip()},
                "improve": text_field(payload, "improve", 500).strip(), "help_used": helps, "scored_by": scored_by,
                "average": round(sum(scores.values()) / len(scores), 1)}
