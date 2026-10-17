"use strict";

// 限时模拟面试：服务端记录开始时间，题号与题名在面试中不显示。
window.AlgoMock = (() => {
  const KEY = "algorithm-mock-active";
  const STAGES = ["讲思路", "写代码", "回答追问", "复盘评分"];
  const RUBRIC = {
    recognition: "5 开口就说清题型和依据 · 3 想了一阵或靠提示 · 1 没识别出",
    communication: "5 先讲思路、变量和例子再写 · 3 讲得零散 · 1 直接闷头写",
    code: "5 一次通过且边界完整 · 3 调试后通过 · 1 没有通过",
    complexity: "5 时间空间都准确并说明依据 · 3 部分正确 · 1 说不出",
    time: "5 用时在限时 70% 内 · 4 限时内 · 3 超时 25% 内 · 1 严重超时",
  };
  const fields = ["code", "idea", "recognition", "time_complexity", "space_complexity", "boundary", "followup"];
  const store = {
    get(key) { try { return JSON.parse(localStorage.getItem(key) || "null"); } catch { return null; } },
    set(key, value) { try { value === null ? localStorage.removeItem(key) : localStorage.setItem(key, JSON.stringify(value)); } catch {} },
  };

  const scoreSource = m => ({coach_suggested: "参考教练建议", chat_coach: "聊天教练评分"}[m.scored_by] || "自评");

  function page() {
    return `<div class="page-heading"><div><span class="eyebrow">TIMED · INTERVIEW · REVIEW</span><h1>限时模拟，练面试里的自己。</h1><p class="muted">像真实面试一样：先讲思路，再写代码，回答追问，最后从五个维度复盘。</p></div><div class="heading-actions"><button class="button secondary" data-view="weekly">查看能力周报</button></div></div><div id="mock-root"><div class="loading-state"><span class="loading-dot"></span>正在准备模拟面试…</div></div>`;
  }

  function mount(container, data, ui) {
    const {esc, icon, api, post, toast} = ui;
    const root = container.querySelector("#mock-root");
    const abort = new AbortController();
    let disposed = false, timer = null, debounce = null, coachPanel = null, saveChain = Promise.resolve();
    let session = null;
    const on = (el, type, fn) => el.addEventListener(type, fn, {signal: abort.signal});

    function setup(notice = "") {
      session = null;
      const picks = data.plan.mock_candidates || [];
      const mocks = (data.insights?.mocks || []).slice().reverse();
      root.innerHTML = `${notice ? `<div class="notice">${icon("info")}<span>${esc(notice)}</span></div><br>` : ""}<div class="content-grid"><div class="stack">
        <section class="panel"><div class="panel-header"><div><h2>开始一场模拟</h2><p class="muted">从已学专题里没做过、能本地验证的高频题中抽 1 道。开始前不显示题目。</p></div><span class="subtle-pill">${data.plan.last_mock ? `上次 ${esc(data.plan.last_mock)}` : "还没有模拟记录"}</span></div>
          <div class="panel-body mock-start"><label>限时<select id="mock-limit">${[15, 25, 35, 45].map(n => `<option value="${n}" ${n === 25 ? "selected" : ""}>${n} 分钟${n === 15 ? "（Easy）" : n === 25 ? "（Medium）" : n === 35 ? "（Hard）" : ""}</option>`).join("")}</select></label><button class="button primary" data-mock="random" ${picks.length ? "" : "disabled"}>${icon("clock")}抽题并开始计时</button></div>
          ${picks.length ? "" : '<p class="inline-error">暂时没有可用于模拟的未做题，可在题目档案加入新题。</p>'}</section>
        <section class="panel"><div class="panel-header"><div><h2>或者指定题目</h2><p class="muted">会提前看到题名，适合针对性训练。</p></div></div><div class="task-list">${picks.map(p => `<div class="task-row"><div class="task-main"><div class="task-title"><span class="task-id">LC ${esc(p.id)}</span>${esc(p.title)}</div><div class="task-meta"><span class="badge neutral">${esc(p.difficulty)}</span><span>${esc(p.reason.join(" · "))}</span></div></div><div class="task-action"><button class="text-button" data-mock="pick" data-id="${esc(p.id)}" data-limit="${p.limit_minutes}">用这题模拟（${p.limit_minutes} 分钟）${icon("arrow")}</button></div></div>`).join("") || '<div class="empty">暂无可选题目。</div>'}</div></section>
        <section class="panel"><div class="panel-header"><h2>最近的模拟</h2><span class="subtle-pill">共 ${data.insights?.mock_total || 0} 场</span></div>${mocks.length ? `<div class="table-scroll"><table><thead><tr><th>日期 / 题目</th><th>用时 / 限时</th><th>平均分</th><th>最该改进的一点</th></tr></thead><tbody>${mocks.map(m => `<tr><td><strong>LC ${esc(m.id)} · ${esc(m.title)}</strong><small>${esc(m.date)} · ${esc({independent:"独立完成",hinted:"提示后完成",failed:"未完成"}[m.result] || "")}</small></td><td>${m.minutes ?? "—"} / ${m.limit_minutes ?? "—"} 分钟${m.overtime ? "<small>超时</small>" : ""}</td><td>${m.average ?? "—"}${m.scores ? `<small>${esc(scoreSource(m))}</small>` : ""}</td><td><span class="row-note">${esc(m.improve || "—")}</span></td></tr>`).join("")}</tbody></table></div>` : '<div class="empty"><strong>完成第一场模拟后，这里会记录每次的五维评分。</strong>每周至少一次，练的是时间感和表达。</div>'}</section>
      </div><div class="stack"><section class="panel"><div class="panel-header"><h2 class="tip-title">${icon("spark")}面试流程</h2></div><div class="panel-body"><ol class="coach-steps">${["复述题意，说出题型识别依据、思路和预估复杂度", "边讲边写代码，运行本地用例；求助会计为提示", "回答一个边界追问和一个延伸追问", "按五个维度自评，写下最该改进的一点"].map((t, i) => `<li><b>${i + 1}</b><span><strong>${STAGES[i]}</strong> · ${esc(t)}</span></li>`).join("")}</ol><p class="form-hint">计时以开始时的本机服务时间为准，刷新页面不会重置。结果会记为一次限时训练，并按真实完成情况安排复习。</p></div></section></div></div>`;
    }

    async function start(id, limit) {
      try {
        const started = await post("/api/mock/start", {id, limit_minutes: limit});
        store.set(KEY, {id: started.id});
        await resume(started.id);
      } catch (error) { toast(error.message, true); }
    }

    async function resume(id) {
      const info = await api(`/api/workbench?id=${id}`);
      if (disposed) return;
      if (!info.draft.mock || info.draft.mock.completed || !info.exercise) { store.set(KEY, null); setup(); return; }
      interview(info);
    }

    function interview(info) {
      const draft = info.draft, exercise = info.exercise, mock = draft.mock;
      const stageKey = `${KEY}:stage:${draft.session_id}`;
      session = {id: info.problem.id, info, revision: draft.revision, dirty: false, stamp: 0, lastRun: null, runCode: "",
                 hints: exercise.revealed_hints || [], coachHints: draft.coach_hints || 0, scoredBy: "self", warned: false,
                 offset: Date.parse(info.server_now) - Date.now(), stage: store.get(stageKey) || 0, stageKey};
      const s = session;
      const follow = [
        "边界追问：输入为空、只有一个元素或全部相同时，你的代码返回什么？为什么？",
        "延伸追问：" + ((info.patterns[0]?.questions || [])[0] || "如果要把额外空间降到 O(1)，或输入规模扩大 100 倍，你会怎样调整？"),
      ];
      root.innerHTML = `<section class="wb-toolbar mock-toolbar"><div class="mock-clock"><span>${icon("clock")}</span><output id="mock-clock" aria-live="off">--:--</output><small>限时 ${mock.limit_minutes} 分钟</small></div><ol class="mock-stages">${STAGES.map((t, i) => `<li data-stage="${i}">${i + 1}. ${t}</li>`).join("")}</ol><button class="text-button" data-mock="abandon">暂时离开</button></section>
        <p id="mock-error" class="wb-error" role="alert"></p>
        <div class="wb-layout"><div class="wb-left stack">
          <section class="panel"><div class="panel-header"><div><span class="eyebrow">面试题</span><h2>请先复述题意</h2></div><span class="subtle-pill">不显示题号与题型</span></div><div class="panel-body"><p class="wb-description">${esc(exercise.description)}</p><p class="wb-contract">方法：<code>Solution.${esc(exercise.method)}(${esc(exercise.params.join(", "))})</code></p><div class="wb-default-cases">${exercise.cases.map(c => `<details><summary>${esc(c.name)}</summary><pre>${esc(JSON.stringify({args: c.args, expected: c.expected}, null, 2))}</pre></details>`).join("")}</div></div></section>
          <section class="panel" data-panel="0"><div class="panel-header"><div><span class="eyebrow">01 · 讲思路</span><h2>先讲，再写</h2></div></div><div class="panel-body"><label>题型识别与依据<textarea data-field="recognition" rows="2" maxlength="2000" placeholder="这是哪类题？从题目的哪个特征看出来的？"></textarea></label><label>思路与关键变量<textarea data-field="idea" rows="4" maxlength="2000" placeholder="核心思路；每个变量代表什么；用一个小例子怎么走。"></textarea></label><div class="form-row"><label>预估时间复杂度<input data-field="time_complexity" maxlength="2000" placeholder="例如 O(n)"></label><label>预估空间复杂度<input data-field="space_complexity" maxlength="2000" placeholder="例如 O(1)"></label></div><button class="button secondary" data-mock="stage" data-to="1">讲完了，开始写代码 ${icon("arrow")}</button></div></section>
          <section class="panel coach-panel" id="mock-coach"></section>
        </div><div class="stack">
          <section class="panel wb-code-panel" data-panel="1"><div class="panel-header"><div><span class="eyebrow">02 · 写代码</span><h2>你的 Python 实现</h2></div><span id="mock-save" class="subtle-pill">草稿自动保存</span></div><div class="wb-code-editor"><pre id="mock-lines" aria-hidden="true">1</pre><textarea data-field="code" aria-label="Python 代码" spellcheck="false" autocapitalize="off" autocomplete="off" wrap="off"></textarea></div><div class="wb-code-actions"><span>Tab 缩进 · Ctrl+Enter 运行</span><div><button class="button primary" data-mock="run">${icon("code")}运行本地用例</button></div></div><div class="panel-body"><p id="mock-stale" class="wb-stale" hidden>代码已在测试后修改，保存前需要重新运行。</p><div id="mock-results"><div class="empty">写完后运行本地用例。</div></div></div></section>
          <section class="panel" data-panel="2"><div class="panel-header"><div><span class="eyebrow">03 · 追问</span><h2>面试官还想问</h2></div></div><div class="panel-body"><label>${esc(follow[0])}<textarea data-field="boundary" rows="2" maxlength="2000"></textarea></label><label>${esc(follow[1])}<textarea data-field="followup" rows="3" maxlength="2000"></textarea></label><button class="button secondary" data-mock="stage" data-to="3">回答完了，进入复盘 ${icon("arrow")}</button></div></section>
          <section class="panel" data-panel="3"><div class="panel-header"><div><span class="eyebrow">04 · 复盘评分</span><h2>给这场面试打分</h2><p class="muted">每项 1～5 分。用时和代码正确性按记录给出建议，可以调整。</p></div><button class="text-button" data-mock="suggest">请面试官给建议分</button></div><div class="panel-body"><div class="mock-scores">${Object.entries(info.mock_dimensions).map(([key, title]) => `<fieldset class="mock-score" data-dim="${key}"><legend>${esc(title)}<small>${esc(RUBRIC[key])}</small></legend><div>${[1, 2, 3, 4, 5].map(n => `<label><input type="radio" name="score-${key}" value="${n}"><span>${n}</span></label>`).join("")}</div><input data-reason="${key}" maxlength="300" placeholder="一句理由（可选）" aria-label="${esc(title)}的理由"></fieldset>`).join("")}</div><label>最该改进的一点<textarea id="mock-improve" rows="2" maxlength="500" placeholder="例如：先讲清 left 和 right 的含义再写代码。"></textarea></label><div class="wb-finish"><label>真实完成情况<select id="mock-result" aria-label="真实完成情况"><option value="">请选择</option><option value="independent">独立完成</option><option value="hinted">提示后完成</option><option value="failed">暂未完成</option></select></label><button class="button primary" data-mock="save">保存这场模拟</button></div><p class="form-hint">保存后记为一次限时训练，用时按服务端计时；看过提示或求助过的面试按“提示后完成”记录。</p></div></section>
        </div></div>`;
      const get = key => root.querySelector(`[data-field="${key}"]`);
      for (const key of fields) get(key).value = draft[key] || (key === "code" ? exercise.starter : "");
      updateLines();
      coachPanel = AlgoCoach.mount(root.querySelector("#mock-coach"), {esc, icon, api, post, toast, settings: info.coach, transcript: info.coach.transcript, mock: true, exchange});
      showStage(); tick(); timer = setInterval(tick, 1000);
    }

    const elapsed = () => Math.max(0, (Date.now() + session.offset - Date.parse(session.info.draft.mock.started_at)) / 1000);
    function tick() {
      if (!session || disposed) return;
      const limit = session.info.draft.mock.limit_minutes * 60, left = Math.round(limit - elapsed());
      const value = Math.abs(left), text = `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
      const clock = root.querySelector("#mock-clock");
      clock.textContent = left >= 0 ? text : `超时 ${text}`;
      clock.parentElement.classList.toggle("over", left < 0);
      if (left < 0 && !session.warned) { session.warned = true; toast("时间到了。可以继续完成，复盘时如实记录用时。"); }
    }
    function showStage() {
      root.querySelectorAll(".mock-stages li").forEach(li => { const n = Number(li.dataset.stage); li.classList.toggle("done", n < session.stage); li.classList.toggle("current", n === session.stage); });
      root.querySelectorAll("[data-panel]").forEach(panel => { panel.hidden = Number(panel.dataset.panel) > session.stage; });
      if (session.stage >= 3) suggestScores();
      updateResult();
    }
    function values() {
      const v = Object.fromEntries(fields.map(key => [key, root.querySelector(`[data-field="${key}"]`).value]));
      return {...v, takeaway: "", extra_cases: [], error_tags: [], elapsed_seconds: Math.min(86400, Math.floor(elapsed()))};
    }
    function updateLines() {
      const code = root.querySelector('[data-field="code"]');
      root.querySelector("#mock-lines").textContent = code.value.split("\n").map((_, i) => i + 1).join("\n");
    }
    function helped() { return session.hints.length > 0 || session.coachHints > 0; }
    function fresh() { return session.lastRun && root.querySelector('[data-field="code"]').value === session.runCode; }
    function updateResult() {
      const select = root.querySelector("#mock-result"), passed = Boolean(fresh() && session.lastRun.result.passed);
      select.querySelector('[value="independent"]').disabled = !passed || helped();
      select.querySelector('[value="hinted"]').disabled = !passed;
      if (!select.value || select.selectedOptions[0].disabled) select.value = !session.lastRun ? "" : passed ? (helped() ? "hinted" : "independent") : "failed";
      root.querySelector("#mock-stale").hidden = !session.lastRun || fresh();
    }
    function suggestScores() {
      const ratio = elapsed() / (session.info.draft.mock.limit_minutes * 60);
      const time = ratio <= .7 ? 5 : ratio <= 1 ? 4 : ratio <= 1.25 ? 3 : ratio <= 1.5 ? 2 : 1;
      const run = session.lastRun?.result;
      const code = !run ? null : run.passed ? (helped() ? 3 : 4) : run.passed_count ? 2 : 1;
      for (const [key, value] of [["time", time], ["code", code]]) {
        if (!value || root.querySelector(`[name="score-${key}"]:checked`)) continue;
        root.querySelector(`[name="score-${key}"][value="${value}"]`).checked = true;
      }
    }
    async function saveDraft() {
      clearTimeout(debounce);
      const work = async () => {
        if (!session || !session.dirty || disposed) return;
        const mark = session.stamp;
        root.querySelector("#mock-save").textContent = "正在保存…";
        const response = await post("/api/workbench/draft", {id: session.id, ...values(), draft_revision: session.revision});
        session.revision = response.draft.revision;
        if (session.stamp === mark) session.dirty = false;
        if (!disposed) root.querySelector("#mock-save").textContent = session.dirty ? "有新修改待保存" : "草稿已保存";
      };
      const task = saveChain.catch(() => {}).then(work);
      saveChain = task;
      return task;
    }
    async function exchange(extra) {
      await saveDraft();
      const task = saveChain.catch(() => {}).then(async () => {
        const mark = session.stamp;
        const response = await post("/api/workbench/coach", {id: session.id, ...values(), draft_revision: session.revision, ...extra}, undefined, undefined, 100000);
        session.revision = response.draft.revision;
        session.coachHints = response.draft.coach_hints || 0;
        if (response.hints) session.hints = response.hints;
        if (session.stamp === mark) session.dirty = false;
        if (!disposed) updateResult();
        if (extra.mode === "reflect") applySuggestion(response.reply);
        return response;
      });
      saveChain = task;
      return task;
    }
    function applySuggestion(text) {
      let found = 0;
      for (const [key, title] of Object.entries(session.info.mock_dimensions)) {
        const match = new RegExp(`${title}[：:]\\s*([1-5])(?:\\s*分)?\\s*[｜|，,]?\\s*([^\\n]*)`).exec(text);
        if (!match) continue;
        found++;
        root.querySelector(`[name="score-${key}"][value="${match[1]}"]`).checked = true;
        const reason = root.querySelector(`[data-reason="${key}"]`);
        if (!reason.value && match[2]) reason.value = match[2].slice(0, 300);
      }
      if (found >= 3) { session.scoredBy = "coach_suggested"; toast("已填入面试官的建议分，可以按自己的判断调整。"); }
    }
    function showRun(response) {
      const result = response.result;
      root.querySelector("#mock-results").innerHTML = `<div class="wb-test-summary ${result.passed ? "pass" : "fail"}">${icon(result.passed ? "check" : "info")}<strong>${result.passed ? "本地用例全部通过" : "还需要调整"}</strong><span>${result.passed_count} / ${result.total} · ${result.elapsed_ms} ms</span></div>${result.error ? `<p class="wb-runtime-error">${esc(result.error)}</p>` : ""}${result.cases.filter(c => !c.passed).slice(0, 2).map(c => `<details class="wb-test-case" open><summary><span class="fail">未通过</span>${esc(c.name)}</summary><dl><dt>输入参数</dt><dd><pre>${esc(JSON.stringify(c.args))}</pre></dd><dt>期望结果</dt><dd><pre>${esc(JSON.stringify(c.expected))}</pre></dd><dt>${c.error ? "错误" : "实际结果"}</dt><dd><pre>${esc(c.error || JSON.stringify(c.actual))}</pre></dd></dl></details>`).join("")}`;
    }
    function message(text) { if (!disposed && session) root.querySelector("#mock-error").textContent = text; }

    on(root, "input", event => {
      if (!session || !event.target.matches("[data-field]")) return;
      if (event.target.dataset.field === "code") updateLines();
      session.dirty = true; session.stamp++;
      root.querySelector("#mock-save").textContent = "修改待保存";
      updateResult();
      clearTimeout(debounce);
      debounce = setTimeout(() => saveDraft().catch(error => message(error.message)), 1200);
    });
    on(root, "keydown", event => {
      if (!event.target.matches('[data-field="code"]')) return;
      if (event.key === "Tab") { event.preventDefault(); event.target.setRangeText("    ", event.target.selectionStart, event.target.selectionEnd, "end"); event.target.dispatchEvent(new Event("input", {bubbles: true})); }
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); root.querySelector('[data-mock="run"]').click(); }
    });
    root.addEventListener("scroll", event => { if (event.target.matches?.('[data-field="code"]')) root.querySelector("#mock-lines").scrollTop = event.target.scrollTop; }, {signal: abort.signal, capture: true});
    on(root, "change", event => { if (event.target.matches(".mock-score input[type=radio]")) updateResult(); });
    on(root, "click", async event => {
      const control = event.target.closest("[data-mock]");
      if (!control || control.disabled) return;
      const action = control.dataset.mock;
      if (action === "random") return start("random", Number(root.querySelector("#mock-limit").value));
      if (action === "pick") return start(control.dataset.id, Number(control.dataset.limit));
      if (!session) return;
      message("");
      if (action === "stage") { session.stage = Math.max(session.stage, Number(control.dataset.to)); store.set(session.stageKey, session.stage); showStage(); root.querySelector(`[data-panel="${session.stage}"]`)?.scrollIntoView({behavior: "smooth", block: "start"}); return; }
      if (action === "abandon") { await saveDraft().catch(() => {}); clearInterval(timer); coachPanel?.destroy(); setup("这场模拟仍在计时。回到“模拟面试”页即可继续；开始新的一场会归档它。"); return; }
      control.disabled = true;
      try {
        if (action === "run") {
          await saveDraft();
          const v = values();
          const response = await post("/api/workbench/run", {id: session.id, ...v, draft_revision: session.revision});
          session.revision = response.draft.revision; session.lastRun = response; session.runCode = v.code; session.dirty = false;
          showRun(response);
          if (response.result.passed && session.stage < 2) { session.stage = 2; store.set(session.stageKey, 2); showStage(); }
          updateResult();
        }
        if (action === "suggest") {
          session.stage = 3; showStage();
          await coachPanel.send("reflect", "请按“题型识别：分数｜理由”的格式，逐行给出五个维度（题型识别、沟通表达、代码正确性、复杂度分析、时间控制）的建议分，再说最该改进的一点。");
          if (session.scoredBy !== "coach_suggested") toast("没有拿到可用的建议分（离线模式不评分），请对照评分标准自评。");
        }
        if (action === "save") {
          if (!fresh()) throw new Error("请先运行当前代码；保存需要与最近一次测试的代码一致。");
          const result = root.querySelector("#mock-result").value;
          if (!result) throw new Error("请选择真实完成情况。");
          const scores = {}, reasons = {};
          for (const key of Object.keys(session.info.mock_dimensions)) {
            const checked = root.querySelector(`[name="score-${key}"]:checked`);
            if (!checked) throw new Error("请为五个维度都打分。");
            scores[key] = Number(checked.value);
            reasons[key] = root.querySelector(`[data-reason="${key}"]`).value;
          }
          await saveDraft();
          const response = await post("/api/workbench/complete", {id: session.id, ...values(), run_id: session.lastRun.run_id, result, scores, score_reasons: reasons,
            improve: root.querySelector("#mock-improve").value, scored_by: session.scoredBy});
          store.set(KEY, null); store.set(session.stageKey, null);
          clearInterval(timer); coachPanel?.destroy();
          toast(response.message);
          await ui.onComplete(`模拟已保存：平均 ${response.mock_review.average} 分，用时 ${Math.ceil(response.mock_review.elapsed_seconds / 60)} 分钟。${response.message}`);
          return;
        }
      } catch (error) { message(error.message); }
      finally { if (!disposed && control.isConnected) control.disabled = false; }
    });

    const active = store.get(KEY);
    if (active?.id) resume(active.id).catch(error => { store.set(KEY, null); setup(error.message); });
    else setup(ui.notice || "");
    return {
      async beforeLeave() { if (session) { try { await saveDraft(); } catch (error) { message(error.message); return false; } } return true; },
      destroy() { disposed = true; clearInterval(timer); clearTimeout(debounce); coachPanel?.destroy(); abort.abort(); },
    };
  }
  return {page, mount};
})();
