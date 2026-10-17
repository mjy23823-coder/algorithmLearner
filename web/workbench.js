"use strict";

window.AlgoWorkbench = (() => {
  let selected = null;
  try { const value=localStorage.getItem("algorithm-workbench-selected"); if(/^[1-9]\d{0,5}$/.test(value||"")) selected=value; } catch {}
  const CACHE = "algorithm-workbench-draft:";
  const fields = ["code", "idea", "time_complexity", "space_complexity", "boundary", "takeaway"];
  function choose(id) { if (/^[1-9]\d{0,5}$/.test(String(id))) {selected = String(id);try{localStorage.setItem("algorithm-workbench-selected",selected);}catch{}} }
  function cached(id) { try { return JSON.parse(localStorage.getItem(CACHE+id) || "null"); } catch { return null; } }
  function page(data, {esc, icon}) {
    // 可练的题：待学队列、已有记录，以及今日计划和画像推荐的新题。
    const rows = new Map([...data.plan.candidates, ...data.plan.tasks, ...data.next_new, ...data.queue].map(row => [row.id, row]));
    if (!selected || !rows.has(selected)) selected = data.plan.tasks.find(row => !row.recorded)?.id || data.next_new[0]?.id || data.queue[0]?.id;
    choose(selected);
    // 页头只保留一条工具栏：选题、计时、保存状态，把空间留给练习本身。
    return `<h1 class="visually-hidden">练习工作台</h1><section class="wb-toolbar"><label><span class="wb-toolbar-label">${icon("code")}正在练习</span><select id="wb-problem" aria-label="选择练习题目">${[...rows.values()].sort((a,b)=>Number(a.id)-Number(b.id)).map(row=>`<option value="${esc(row.id)}" ${row.id===selected?"selected":""}>LC${esc(row.id)} · ${esc(row.title)}</option>`).join("")}</select></label><div class="wb-timer"><span>${icon("clock")}</span><output id="wb-clock">00:00</output><button class="button secondary" data-wb="timer" disabled>开始计时</button></div><span id="wb-save-status" role="status">正在读取草稿…</span><button class="icon-button wb-graph-link" data-view="graph" aria-label="回到图谱" title="回到图谱">${icon("network")}</button></section><div id="wb-content"><div class="loading-state">正在准备题目和用例…</div></div>`;
  }

  function mount(root, data, ui) {
    const {esc, icon, api, post, toast} = ui;
    const id = selected;
    let info = null, revision = null, elapsed = 0, since = null, timer = null, debounce = null;
    let dirty = false, conflict = false, busy = false, disposed = false, stamp = 0, saveChain = Promise.resolve();
    let lastRun = null, runCode = "", runCases = "", hints = [], savedResult = false, coachHints = 0, agentHints = 0, coachPanel = null;
    const abort = new AbortController();
    const get = key => root.querySelector(`[data-wb-field="${key}"]`);
    const content = root.querySelector("#wb-content");
    const on = (element, event, fn) => element.addEventListener(event, fn, {signal: abort.signal});
    const seconds = () => elapsed + (since === null ? 0 : (performance.now()-since)/1000);
    const status = text => { if(!disposed) root.querySelector("#wb-save-status").textContent = text; };
    function message(text) { if(!disposed) { root.querySelector("#wb-error").textContent = text; } }

    function read() {
      const value = Object.fromEntries(fields.map(key=>[key,get(key)?.value || ""]));
      let extra_cases;
      try { extra_cases = JSON.parse(get("extra_cases")?.value || "[]"); }
      catch { throw new Error("自定义用例需要是 JSON 数组；暂时不用时填写 []。"); }
      value.extra_cases = extra_cases;
      value.elapsed_seconds = Math.floor(seconds());
      value.error_tags = [...root.querySelectorAll('[name="wb-error-tag"]:checked')].map(input=>input.value);
      return value;
    }
    function cache() {
      if (!info || !get("code")) return;
      const values = Object.fromEntries(fields.map(key=>[key,get(key).value]));
      values.extra_cases_text = get("extra_cases").value;
      values.elapsed_seconds = Math.floor(seconds());
      values.error_tags = [...root.querySelectorAll('[name="wb-error-tag"]:checked')].map(el=>el.value);
      try { localStorage.setItem(CACHE+id, JSON.stringify({values, base_revision:revision, pending:dirty, saved_at:Date.now()})); } catch {}
    }
    function populate(value) {
      for (const key of fields) get(key).value = value[key] || (key === "code" ? info.exercise?.starter || "" : "");
      get("extra_cases").value = value.extra_cases_text ?? JSON.stringify(value.extra_cases || [], null, 2);
      elapsed = value.elapsed_seconds || 0; since = null;
      root.querySelectorAll('[name="wb-error-tag"]').forEach(el=>{el.checked=(value.error_tags||[]).includes(el.value);});
      updateClock(); updateEditor(); updateActions();
    }
    function updateClock() {
      const total = Math.floor(seconds());
      root.querySelector("#wb-clock").textContent = `${String(Math.floor(total/60)).padStart(2,"0")}:${String(total%60).padStart(2,"0")}`;
      const control = root.querySelector('[data-wb="timer"]');
      control.textContent = since === null ? (total ? "继续计时" : "开始计时") : "暂停计时";
    }
    function pauseTimer() {
      if(since !== null) { elapsed=seconds(); since=null; dirty=true; stamp++; }
      if(timer) clearInterval(timer); timer=null;
      if(info && !disposed) updateClock();
      cache();
    }
    function updateEditor() {
      const code=get("code");
      root.querySelector("#wb-lines").textContent=code.value.split("\n").map((_,i)=>String(i+1)).join("\n");
    }
    function currentRun() {
      if(!lastRun || !info || get("code").value !== runCode) return false;
      try { return JSON.stringify(JSON.parse(get("extra_cases").value || "[]")) === runCases; } catch { return false; }
    }
    function updateActions() {
      if(!info || !get("code")) return;
      root.querySelector('[data-wb="run"]').disabled=busy || conflict || !info.exercise;
      root.querySelector('[data-wb="complete"]').disabled=busy || conflict || !currentRun();
      root.querySelector('[data-wb="save"]').disabled=busy || conflict;
      root.querySelector('[data-wb="fresh"]').disabled=busy || conflict || !info.exercise;
      root.querySelector("#wb-problem").disabled=busy;
      for(const field of root.querySelectorAll("[data-wb-field]")) field.readOnly=busy;
      root.querySelectorAll('[name="wb-error-tag"]').forEach(input=>{input.disabled=busy;});
      const result=root.querySelector("#wb-result");
      const helped=hints.length>0 || coachHints>0;
      result.querySelector('[value="independent"]').disabled=helped || !lastRun?.result.passed;
      result.querySelector('[value="hinted"]').disabled=!lastRun?.result.passed;
      if(helped && result.value === "independent") result.value="hinted";
      root.querySelector("#wb-stale").hidden=!lastRun || currentRun();
      root.querySelectorAll('[data-wb="hint"]').forEach(b=>{ b.disabled=busy || conflict || Number(b.dataset.level)>hints.length+1; });
    }
    async function save() {
      clearTimeout(debounce);
      const work = async () => {
        if(disposed || !info || !dirty) return;
        if(conflict) throw new Error("请先选择保留本机草稿或磁盘草稿。");
        const mark=stamp, values=read();
        status("正在保存草稿…");
        try {
          const response=await post("/api/workbench/draft",{id,...values,draft_revision:revision});
          revision=response.draft.revision;
          info.draft=response.draft;
          if(stamp===mark) dirty=false;
          cache(); status(dirty ? "有新修改待保存" : "草稿已保存");
        } catch(error) { status("草稿保留在本机，尚未同步"); cache(); throw error; }
      };
      const task=saveChain.catch(()=>{}).then(work);
      saveChain=task;
      return task;
    }
    // 教练请求排在草稿保存队列里：等待期间的输入会在回复后用新版本继续保存，不会触发冲突。
    async function exchange(extra) {
      if(conflict) throw new Error("请先选择保留本机草稿或磁盘草稿。");
      await save();
      const task=saveChain.catch(()=>{}).then(async()=>{
        const mark=stamp;
        const response=await post("/api/workbench/coach",{id,...read(),draft_revision:revision,...extra},undefined,undefined,100000);
        revision=response.draft.revision; info.draft=response.draft; coachHints=(response.draft.coach_hints || 0)+agentHints;
        if(stamp===mark) dirty=false;
        if(response.hints) hints=response.hints;
        cache(); if(!disposed) showHints();
        return response;
      });
      saveChain=task;
      return task;
    }
    // 智能体任务在服务端运行；开始请求排在草稿保存之后，任务本身不改草稿，页面可以继续编辑。
    async function agentStart(extra) {
      if(conflict) throw new Error("请先选择保留本机草稿或磁盘草稿。");
      await save();
      const task=saveChain.catch(()=>{}).then(async()=>{
        const response=await post("/api/workbench/agent",{id,...read(),draft_revision:revision,...extra},undefined,undefined,20000);
        if(response.draft?.revision && response.draft.revision!==revision){revision=response.draft.revision;info.draft=response.draft;}
        return response;
      });
      saveChain=task;
      return task;
    }
    function agentDone(result) {
      agentHints=result.agent_hints || 0; coachHints=(info.draft.coach_hints || 0)+agentHints;
      if(!disposed) showHints();
    }
    function applySuggestion(s) {
      if(!get("takeaway")) return;
      get("takeaway").value=s.takeaway || get("takeaway").value;
      if(s.time_complexity && !get("time_complexity").value) get("time_complexity").value=s.time_complexity;
      if(s.space_complexity && !get("space_complexity").value) get("space_complexity").value=s.space_complexity;
      root.querySelectorAll('[name="wb-error-tag"]').forEach(el=>{el.checked=s.error_tags.includes(el.value);});
      const select=root.querySelector("#wb-result"), option=select.querySelector(`[value="${s.result}"]`);
      if(option && !option.disabled) select.value=s.result;
      edited(); updateActions();
      root.querySelector("#wb-result").scrollIntoView({behavior:"smooth",block:"center"});
    }
    function coachContext(transcript) {
      return {esc,icon,api,post,toast,id,settings:info.coach,transcript,exchange,agentStart,agentDone,applySuggestion,
              errorTitle:tag=>info.errors.find(e=>e.id===tag)?.title};
    }
    function edited() {
      dirty=true; stamp++; cache(); updateActions();
      status("修改已保留在本机");
      clearTimeout(debounce);
      debounce=setTimeout(()=>save().catch(error=>message(error.message)),900);
    }
    function showHints() {
      root.querySelector("#wb-hints").innerHTML=hints.map((hint,i)=>`<div class="wb-hint"><b>提示 ${i+1}</b><p>${esc(hint)}</p></div>`).join("");
      const used=[hints.length ? `${hints.length} 层提示` : "", coachHints ? `${coachHints} 次教练提示` : ""].filter(Boolean).join("、");
      root.querySelector("#wb-hint-note").textContent=used ? `本轮已看 ${used}，完成时按“提示后完成”记录。` : "先尝试自己的思路，需要时再逐层展开。";
      updateActions();
    }
    function showRun(run) {
      const result=run.result;
      root.querySelector("#wb-test-results").innerHTML=`<div class="wb-test-summary ${result.passed?"pass":"fail"}">${icon(result.passed?"check":"info")}<strong>${result.passed?"本地用例全部通过":"还需要调整"}</strong><span>${result.passed_count} / ${result.total} · ${result.elapsed_ms} ms</span></div>${result.error?`<p class="wb-runtime-error">${esc(result.error)}</p>`:""}${result.cases.map(c=>`<details class="wb-test-case" ${!c.passed?"open":""}><summary><span class="${c.passed?"pass":"fail"}">${c.passed?"通过":"未通过"}</span>${esc(c.name)}</summary><dl><dt>输入参数</dt><dd><pre>${esc(JSON.stringify(c.args))}</pre></dd><dt>期望结果</dt><dd><pre>${esc(JSON.stringify(c.expected))}</pre></dd><dt>${c.error?"错误":"实际结果"}</dt><dd><pre>${esc(c.error || JSON.stringify(c.actual))}</pre></dd></dl></details>`).join("")}${result.stdout?`<details class="wb-test-case"><summary>调试输出</summary><pre>${esc(result.stdout)}</pre></details>`:""}<p class="form-hint">以上只证明这 ${result.total} 组本地用例的结果；平台提交、复杂度和思路表达仍需单独确认。</p>`;
      if(!result.passed) root.querySelector("#wb-result").value="failed";
      else if(hints.length || coachHints) root.querySelector("#wb-result").value="hinted";
      updateActions();
    }

    function formMarkup() {
      const exercise=info.exercise, row=info.problem;
      const statusText={learned:"已掌握",learning:"待间隔验证",needs_review:"需要巩固",needs_calibration:"历史状态待校准",new:"待学习"}[row.status] || row.status;
      const step=(n,eyebrow,title,extra="")=>`<div class="wb-card-head"><span class="wb-step" aria-hidden="true">${n}</span><div class="wb-card-title"><span class="eyebrow">${eyebrow}</span><h2>${title}</h2>${extra}</div>`;
      // 主栏按“理清问题 → 写代码验证 → 复盘”自上而下；教练固定在右栏，窄屏时排到代码之后。
      return `<div id="wb-conflict" class="notice" hidden><div><p>本机有尚未同步的草稿，磁盘版本也已变化。请选择保留哪一份。</p><div class="wb-conflict-actions"><button class="button secondary" data-wb="use-local">保留本机草稿</button><button class="button secondary" data-wb="use-remote">使用磁盘草稿</button></div></div></div><p id="wb-error" class="wb-error" role="alert"></p>
      <div class="wb-studio">
        <section class="panel wb-problem">${step(1,"理清问题",`LC${esc(id)} · ${esc(row.title)}`,`<p class="wb-meta"><span>${esc(row.topic)}</span><span class="wb-status status-${esc(row.status)}">${esc(statusText)}</span>${info.patterns.map(p=>`<span class="badge neutral">${esc(p.title)}</span>`).join("")}</p>`)}</div>
          <div class="panel-body">
            <p class="wb-description">${esc(exercise?.description || "这道题尚未配置本地题意和用例，可以先让聊天教练检查。")}</p>
            ${exercise?`<p class="wb-contract">方法 <code>Solution.${esc(exercise.method)}(${esc(exercise.params.join(", "))})</code><span>输入参数按顺序填写，已提供 ListNode、TreeNode、List 和 Optional。</span></p><details class="wb-cases"><summary>${icon("layers")}本地基础用例 · ${exercise.cases.length} 组</summary><div class="wb-default-cases">${exercise.cases.map(c=>`<details><summary>${esc(c.name)}</summary><pre>${esc(JSON.stringify({args:c.args,expected:c.expected},null,2))}</pre></details>`).join("")}</div></details>`:""}
            <div class="wb-think"><label>我的核心思路<textarea data-wb-field="idea" rows="3" maxlength="2000" placeholder="先用自己的话解释：题型、关键变量各代表什么。"></textarea></label><label>一个边界情况<textarea data-wb-field="boundary" rows="3" maxlength="2000" placeholder="最小输入、重复值、空节点或指针相遇时会怎样？"></textarea></label></div>
            <div class="wb-hintbar"><div class="wb-hintbar-row"><span class="wb-hintbar-title">${icon("bulb")}卡住了？逐层提示</span><div class="wb-hint-buttons">${[1,2,3].map(n=>`<button class="button secondary" data-wb="hint" data-level="${n}">提示 ${n}</button>`).join("")}</div><button class="text-button" data-action="coach" data-id="${esc(id)}">聊天教练 ${icon("arrow")}</button></div><p id="wb-hint-note" class="form-hint"></p><div id="wb-hints"></div></div>
          </div>
        </section>
        <section class="panel wb-code-panel">${step(2,"写代码并验证","你的 Python 实现")}<div class="wb-card-tags"><span class="subtle-pill">Python 3</span><span id="wb-run-state" class="subtle-pill">尚未运行</span></div></div>
          <div class="wb-code-editor"><pre id="wb-lines" aria-hidden="true">1</pre><textarea data-wb-field="code" aria-label="Python 代码" spellcheck="false" autocapitalize="off" autocomplete="off" wrap="off"></textarea></div>
          <div class="wb-code-actions"><span>Tab 缩进 · Ctrl+Enter 运行 · Ctrl+S 保存</span><div><button class="button secondary" data-wb="save">保存草稿</button><button class="button primary" data-wb="run">${icon("play")}运行本地用例</button></div></div>
          <div class="wb-results"><p id="wb-stale" class="wb-stale" hidden>代码或用例已修改，需要重新运行后才能记录结果。</p><div id="wb-test-results"><div class="empty">完成实现后，运行基础用例与自己补充的边界。</div></div><details class="wb-extra"><summary>追加自定义用例（JSON 数组）</summary><p class="form-hint">格式：[{"args": [按参数顺序填写], "expected": 期望结果}]。基础用例始终会运行。</p><textarea data-wb-field="extra_cases" rows="6" aria-label="自定义测试用例" spellcheck="false">[]</textarea></details></div>
        </section>
        <aside class="wb-coach-col"><section class="panel coach-panel" id="wb-coach"></section></aside>
        <section class="panel wb-reflect">${step(3,"复盘与下次复习","把这次练习留下来")}</div>
          <div class="panel-body"><div class="form-row"><label>时间复杂度<input data-wb-field="time_complexity" maxlength="2000" placeholder="例如 O(n)"></label><label>额外空间复杂度<input data-wb-field="space_complexity" maxlength="2000" placeholder="例如 O(1)"></label></div><fieldset class="wb-error-tags"><legend>本次遇到的错因（可多选，没有就不选）</legend>${info.errors.map(tag=>`<label><input type="checkbox" name="wb-error-tag" value="${esc(tag.id)}">${esc(tag.title)}</label>`).join("")}</fieldset><label>一句话复盘<textarea data-wb-field="takeaway" rows="3" maxlength="2000" placeholder="关键规律、修改了什么、下次怎样避免同样的问题。"></textarea></label><div class="wb-finish"><label>真实完成情况<select id="wb-result"><option value="">请选择</option><option value="independent">独立完成</option><option value="hinted">提示后完成</option><option value="failed">暂未完成</option></select></label><button class="button primary" data-wb="complete" disabled>${icon("check")}保存结果并更新复习</button></div><p class="form-hint">仅运行用例不会增加完成次数。保存结果后更新进度、复习排期和错因关系。</p></div>
        </section>
        <div class="wb-foot"><div class="wb-bottom"><button class="text-button" data-wb="fresh">从空白开始新一轮练习</button><span>旧草稿和已测试代码会保留版本</span></div><details class="wb-versions"><summary>最近的测试版本（${info.versions.length}）</summary>${info.versions.map(v=>`<button class="text-button" data-wb="version" data-run="${esc(v.run_id)}">${esc(v.created_at.slice(0,19).replace("T"," "))} · ${v.passed_count}/${v.total} 通过</button>`).join("")}</details></div>
      </div>`;
    }

    async function initialize() {
      try {
        info=await api(`/api/workbench?id=${id}`);
        if(disposed) return;
        revision=info.draft.revision; hints=info.exercise?.revealed_hints || []; agentHints=info.coach.agent_hints || 0; coachHints=(info.draft.coach_hints || 0)+agentHints;
        content.innerHTML=formMarkup();
        root.querySelector("#wb-result").setAttribute("aria-label","真实完成情况");
        populate(info.draft); showHints();
        const local=cached(id);
        if(local?.pending && local.values) {
          if(local.base_revision===revision) {populate(local.values); dirty=true; status("已恢复本机未同步草稿");}
          else { conflict=true; root.querySelector("#wb-conflict").hidden=false; status("草稿需要核对"); }
        } else status(revision ? "已载入保存的草稿" : "输入后自动保存草稿");
        root.querySelector('[data-wb="timer"]').disabled=false;
        coachPanel=AlgoCoach.mount(root.querySelector("#wb-coach"),coachContext(info.coach.transcript));
        updateActions();
        on(get("code"),"scroll",()=>{root.querySelector("#wb-lines").scrollTop=get("code").scrollTop;});
        on(get("code"),"keydown",event=>{
          if(event.key==="Tab") {event.preventDefault(); const el=get("code"); el.setRangeText("    ",el.selectionStart,el.selectionEnd,"end"); updateEditor(); edited();}
          if((event.ctrlKey||event.metaKey)&&event.key==="Enter") {event.preventDefault(); root.querySelector('[data-wb="run"]').click();}
          if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="s") {event.preventDefault(); save().catch(e=>message(e.message));}
        });
        if(dirty && !conflict) debounce=setTimeout(()=>save().catch(e=>message(e.message)),900);
      } catch(error) {if(!disposed) content.innerHTML=`<div class="empty">${esc(error.message)}</div>`;}
    }

    on(root,"input",event=>{if(event.target.matches("[data-wb-field], [name=wb-error-tag]")){if(event.target===get("code")) updateEditor(); edited();}});
    on(root.querySelector("#wb-problem"),"change",async event=>{
      const next=event.target.value;
      if(busy){event.target.value=id;return;}
      pauseTimer();
      try {await save(); choose(next); ui.onSelect();} catch(error){event.target.value=id;message(error.message);}
    });
    on(root,"click",async event=>{
      const control=event.target.closest("[data-wb]");
      if(!control || control.disabled || !info) return;
      const action=control.dataset.wb;
      if(action==="timer") {
        if(since!==null) {pauseTimer();save().catch(e=>message(e.message));}
        else {since=performance.now();updateClock();timer=setInterval(()=>{updateClock();dirty=true;stamp++;cache();},1000);}
        return;
      }
      if(action==="use-local" || action==="use-remote") {
        const local=cached(id);
        populate(action==="use-local" && local?.values ? local.values : info.draft);
        conflict=false;dirty=action==="use-local";stamp++;
        root.querySelector("#wb-conflict").hidden=true;cache();updateActions();
        if(dirty) save().catch(e=>message(e.message));
        return;
      }
      if(busy) return;
      busy=true;updateActions();message("");
      try {
        if(action==="save") {await save();toast("草稿已保存");}
        if(action==="hint") {
          await save();
          const response=await post("/api/workbench/hint",{id,...read(),draft_revision:revision,level:Number(control.dataset.level)});
          revision=response.draft.revision;info.draft=response.draft;hints=response.hints;dirty=false;cache();showHints();status("提示与草稿已保存");
        }
        if(action==="run") {
          await save(); get("code").readOnly=true;
          root.querySelector("#wb-run-state").textContent="运行中…";
          const values=read();
          const response=await post("/api/workbench/run",{id,...values,draft_revision:revision});
          revision=response.draft.revision;info.draft=response.draft;dirty=false;cache();
          lastRun=response;runCode=values.code;runCases=JSON.stringify(values.extra_cases);
          showRun(response);root.querySelector("#wb-run-state").textContent=response.result.passed?"本地通过":"需要调整";
          status("代码与测试结果已保存");
        }
        if(action==="complete") {
          const result=root.querySelector("#wb-result").value;
          if(!result) throw new Error("请选择本次真实完成情况。");
          if(!currentRun()) throw new Error("请先运行当前代码和用例。");
          pauseTimer(); await save();
          const response=await post("/api/workbench/complete",{id,...read(),run_id:lastRun.run_id,result});
          savedResult=true;dirty=false;cache();await ui.onComplete(id,response.message);
        }
        if(action==="fresh") {
          pauseTimer(); await save();
          const response=await post("/api/workbench/start",{id,draft_revision:revision});
          revision=response.draft.revision;info.draft=response.draft;hints=[];coachHints=0;lastRun=null;dirty=false;stamp++;
          agentHints=0;coachPanel?.destroy();coachPanel=AlgoCoach.mount(root.querySelector("#wb-coach"),coachContext([]));
          populate(response.draft);showHints();cache();root.querySelector("#wb-test-results").innerHTML='<div class="empty">新一轮从解释思路开始。</div>';
          root.querySelector("#wb-run-state").textContent="尚未运行";root.querySelector("#wb-result").value="";status("新一轮已开始，旧草稿已归档");
        }
        if(action==="version") {
          const run=await api(`/api/workbench/run?id=${id}&run_id=${control.dataset.run}`);
          const panel=document.createElement("dialog");panel.className="wb-version-dialog";
          panel.innerHTML=`<div class="dialog-heading"><h2>保存的代码版本</h2><button class="icon-button" data-close aria-label="关闭">${icon("close")}</button></div><p class="muted">${esc(run.created_at)} · ${run.result.passed_count}/${run.result.total} 本地用例通过</p><pre>${esc(run.code)}</pre>`;
          document.body.append(panel);panel.addEventListener("close",()=>panel.remove(),{once:true});panel.showModal();
        }
      } catch(error) {message(error.message);status("操作未完成，输入已保留");cache();}
      finally {busy=false;if(!disposed){get("code").readOnly=false;updateActions();}}
    });
    on(document,"visibilitychange",()=>{if(document.hidden && info){pauseTimer();save().catch(()=>{});}});
    on(window,"pagehide",()=>{pauseTimer();cache();});
    initialize();
    return {
      async beforeLeave(){ if(busy || coachPanel?.busy()){message("请等待当前操作完成。");return false;} pauseTimer();try{await save();return true;}catch(error){message(error.message);return false;} },
      destroy(){pauseTimer();cache();disposed=true;coachPanel?.destroy();abort.abort();clearTimeout(debounce);if(timer)clearInterval(timer);},
    };
  }
  return {page,mount,choose};
})();
