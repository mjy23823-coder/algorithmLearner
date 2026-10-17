"use strict";

// 工作台与模拟面试共用的教练面板：“对话”一问一答，“智能体”会调用工具（运行用例、对拍、计时、草拟记录）。
// 提示类帮助由服务端计数，页面只负责展示。整卡只在离散事件时重绘；智能体轮询时只更新进度，避免动画反复重播。
window.AlgoCoach = (() => {
  const modeOrder = ["explain", "hint", "review", "reflect"];
  const modeIcons = {explain: "chat", hint: "bulb", review: "code", reflect: "book"};
  const mockLabels = {explain: "复述思路给面试官", hint: "向面试官求助", review: "请面试官看代码", reflect: "面试后复盘"};
  const agentLabels = {counterexample: "找反例", complexity: "实测复杂度", edge_cases: "补边界用例", draft: "草拟记录"};
  const agentInfo = {
    counterexample: ["compare", "写暴力解对拍，找出让代码出错的最小输入"],
    complexity: ["timer", "逐级放大输入规模计时，核对你写的复杂度"],
    edge_cases: ["target", "补 3～5 个关键边界用例，用你的代码运行"],
    draft: ["note", "根据本轮情况草拟练习记录，由你确认"],
  };
  const toolIcons = {run_tests: "play", find_counterexample: "compare", measure_complexity: "timer", draft_record: "note"};
  const resultLabels = {independent: "独立完成", hinted: "提示后完成", failed: "暂未完成"};
  const providerNote = {
    offline: "离线引导：按费曼步骤追问，提示即分层提示，不调用模型。",
    openai: "OpenAI 兼容接口：用你填写的服务地址和 Key 调用 GPT 等模型（/v1/chat/completions）。",
    anthropic: "Claude API / CPA 中转：用你填写的服务地址和 Key 调用模型（/v1/messages）。",
    claude_cli: "本机 Claude Code：用已登录的 Claude Code 生成回复，工具全部关闭。",
  };
  const shortLabel = {openai: "OpenAI 兼容接口", anthropic: "Claude API", claude_cli: "本机 Claude Code"};
  // 模型名和通道明显不匹配时（例如 OpenAI 接口里还是 claude-*），切换通道会换成该通道的默认模型。
  const family = name => /^claude/i.test(name) ? "claude" : /^(gpt|o\d|chatgpt|codex)/i.test(name) ? "openai" : "";
  const expectedFamily = {openai: "openai", anthropic: "claude", claude_cli: "claude"};

  function mount(container, ctx) {
    const {esc, icon, api, post, toast} = ctx;
    let settings = ctx.settings;
    let transcript = ctx.transcript || [];
    let busy = false, sending = false, disposed = false, tab = "chat", job = null, poll = null, started = 0, liveKey = "";
    // 已显示过的消息与步骤数：只有新出现的才播放入场动画。
    let seen = transcript.length, seenSteps = 0;
    const typed = {chat: "", agent: ""};
    const labels = mode => ctx.mock ? mockLabels[mode] : settings.modes[mode];
    const relays = () => settings.relays || ["openai", "anthropic"];
    const agentReady = () => relays().includes(settings.provider);
    const online = () => settings.provider !== "offline";
    const elapsed = () => `${Math.max(0, Math.round((Date.now() - started) / 1000))} 秒`;

    function clock(at) {
      const time = at ? new Date(at) : null;
      return time && !isNaN(time) ? time.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}) : "";
    }
    function avatar(role) {
      if (role === "user") return '<span class="coach-avatar user" aria-hidden="true">你</span>';
      return `<span class="coach-avatar ${role === "agent" ? "agent" : ""}" aria-hidden="true">${icon(role === "agent" ? "bot" : ctx.mock ? "chat" : "spark")}</span>`;
    }
    function bubble(m, index) {
      const who = m.role === "user" ? "你" : m.role === "agent" ? "智能体" : ctx.mock ? "面试官" : "教练";
      const via = m.role !== "user" ? `<small>${esc(settings.labels[m.provider] || "离线引导")}</small>` : "";
      const counted = m.role !== "user" && m.counted ? '<em class="coach-counted">计为提示</em>' : "";
      const steps = m.steps?.length ? `<ol class="agent-steps">${m.steps.map(s => stepItem(s)).join("")}</ol>` : "";
      return `<div class="coach-msg ${m.role === "user" ? "from-user" : "from-coach"}${index >= seen ? " enter" : ""}">${avatar(m.role)}<div class="coach-bubble"><div class="coach-who"><b>${who}</b>${via}${counted}<time>${esc(clock(m.at))}</time></div>${steps}<p>${esc(m.text)}</p></div></div>`;
    }
    function stepItem(s, fresh = false) {
      const state = s.status === "running" ? '<span class="coach-spin"></span>' : icon(s.status === "error" ? "alert" : "check");
      return `<li class="agent-step ${esc(s.status)}${fresh ? " enter" : ""}"><span class="step-icon">${icon(toolIcons[s.tool] || "spark")}</span><span class="step-text"><b>${esc(s.label || s.tool)}</b><span>${esc(s.status === "running" ? "进行中…" : s.summary || "")}</span></span><span class="step-state" aria-hidden="true">${state}</span></li>`;
    }
    function liveSteps() {
      if (!job.steps.length) return `<li class="agent-step running thinking"><span class="step-icon">${icon("spark")}</span><span class="step-text"><b>思考</b><span>正在决定先用哪个工具…</span></span><span class="step-state" aria-hidden="true"><span class="coach-spin"></span></span></li>`;
      return job.steps.map((s, i) => stepItem(s, i >= seenSteps)).join("");
    }
    function liveBubble() {
      if (!job || job.status === "done") return "";
      return `<div class="coach-msg agent-live enter">${avatar("agent")}<div class="coach-bubble"><div class="coach-who"><b>智能体</b><small>工作中 · <span data-elapsed>${elapsed()}</span> · 通常 10～60 秒</small></div><div class="agent-progress" aria-hidden="true"><i></i></div><ol class="agent-steps" data-live-steps>${liveSteps()}</ol></div></div>`;
    }
    const typingBubble = () => `<div class="coach-msg typing enter" role="status" aria-label="${ctx.mock ? "面试官" : "教练"}正在思考">${avatar("coach")}<div class="coach-bubble"><span class="coach-dots"><i></i><i></i><i></i></span></div></div>`;
    function empty(kind) {
      if (kind === "agent") return `<div class="coach-empty"><span class="coach-empty-orb agent" aria-hidden="true">${icon("bot")}</span><strong>交给智能体动手查</strong><p>它会自己挑工具、跑代码，每一步都列在这里；不改你的代码，也不直接写进度。</p><ul class="agent-menu">${Object.entries(agentInfo).map(([key, [name, text]]) => `<li><span>${icon(name)}</span><p><b>${esc(agentLabels[key])}</b>${esc(text)}</p></li>`).join("")}</ul></div>`;
      if (ctx.mock) return `<div class="coach-empty"><span class="coach-empty-orb" aria-hidden="true">${icon("chat")}</span><strong>面试开始</strong><p>先向面试官复述题意和思路。求助、请面试官定位错误都会计为提示。</p></div>`;
      return `<div class="coach-empty"><span class="coach-empty-orb" aria-hidden="true">${icon("spark")}</span><strong>先讲给我听</strong><p>写下思路后点“检查我的讲解”，我按费曼步骤追问；卡住时再逐层要提示。提示类帮助会按“提示后完成”记录。</p></div>`;
    }
    function composer(kind) {
      const agent = kind === "agent", action = agent ? "交给智能体" : "发送";
      const hint = agent ? "让智能体做…例如：我的代码在什么输入下会超时？" : ctx.mock ? "向面试官澄清题意…" : "问题意或 Python 写法…";
      return `<form class="coach-ask" autocomplete="off" ${agent ? "data-agent-form" : "data-coach-form"}><input name="message" maxlength="1000" value="${esc(typed[kind])}" placeholder="${esc(hint)}" aria-label="${agent ? "交给智能体的任务" : "向教练提问"}" autocomplete="off" autocapitalize="off" spellcheck="false" ${busy ? "disabled" : ""}><button class="coach-send" type="submit" aria-label="${action}" title="${action}" ${busy ? "disabled" : ""}>${busy ? '<span class="coach-spin"></span>' : icon("send")}</button></form>`;
    }
    function chatPane() {
      const items = transcript.map((m, i) => [m, i]).filter(([m]) => m.mode !== "agent");
      return `<div class="coach-log" role="log" aria-live="polite">${items.length ? items.map(([m, i]) => bubble(m, i)).join("") : empty("chat")}${sending ? typingBubble() : ""}</div>
        <div class="coach-actions">${modeOrder.map(mode => `<button class="coach-chip" data-coach-mode="${mode}" ${busy ? "disabled" : ""}>${icon(modeIcons[mode])}<span>${esc(labels(mode))}</span></button>`).join("")}</div>
        ${composer("chat")}
        <p class="coach-rule">${settings.provider === "offline" ? "离线模式下“帮我看代码”只复述测试结果，不计提示。" : "模型给出解题方向、或在用例通过前定位错误时，会计为提示。"}</p>`;
    }
    function agentPane() {
      if (!agentReady()) return `<div class="agent-locked"><div class="agent-tool-row" aria-hidden="true">${Object.values(agentInfo).map(([name]) => `<span>${icon(name)}</span>`).join("")}</div><p>智能体会自己调用工具：用你的代码跑用例、写暴力解对拍找反例、实测复杂度、草拟练习记录。</p><p class="form-hint">需要先连接 OpenAI 兼容接口或 Claude API，例如自建的 CPA（本机 Claude Code 和离线模式只支持对话）。</p><button class="button primary" data-coach="settings">${icon("sliders")}连接模型接口</button></div>`;
      const items = transcript.map((m, i) => [m, i]).filter(([m]) => m.mode === "agent");
      const suggestion = job?.result?.suggestion || null;
      return `<div class="coach-log" role="log" aria-live="polite">${items.length || job ? items.map(([m, i]) => bubble(m, i)).join("") + liveBubble() : empty("agent")}</div>
        ${suggestion ? suggestionCard(suggestion) : ""}
        <div class="coach-actions">${Object.keys(agentLabels).map(key => `<button class="coach-chip" data-agent-action="${key}" title="${esc(agentInfo[key][1])}" ${busy ? "disabled" : ""}>${icon(agentInfo[key][0])}<span>${esc(agentLabels[key])}</span></button>`).join("")}</div>
        ${composer("agent")}
        <p class="coach-rule">用例通过前找到反例，或回复里给出解题方向，会计为提示。</p>`;
    }
    function suggestionCard(s) {
      return `<div class="agent-suggestion enter"><div class="agent-suggestion-head">${icon("note")}<strong>草拟的记录</strong><span class="result-pill ${esc(s.result)}">${esc(resultLabels[s.result])}</span></div>${s.error_tags.length ? `<p class="agent-suggestion-tags">错因：${esc(s.error_tags.map(id => ctx.errorTitle?.(id) || id).join("、"))}</p>` : ""}<blockquote>${esc(s.takeaway)}</blockquote>${s.notes.length ? `<p class="form-hint">${esc(s.notes.join("；"))}</p>` : ""}<button class="button secondary" data-agent-apply>填入复盘（仍需你点保存）</button></div>`;
    }
    function head() {
      const status = online() ? `${settings.model} · ${shortLabel[settings.provider] || ""}` : "离线引导 · 不发送数据";
      return `<div class="coach-head"><span class="coach-orb${busy ? " busy" : ""}" aria-hidden="true">${icon(ctx.mock ? "chat" : "spark")}</span><div class="coach-title"><h2>${ctx.mock ? "面试官对话" : "教练"}</h2><p class="coach-status${online() ? " online" : ""}" title="${esc(providerNote[settings.provider])}"><i aria-hidden="true"></i><span>${esc(status)}</span></p></div><button class="icon-button" data-coach="settings" aria-label="教练设置" title="教练设置">${icon("sliders")}</button></div>`;
    }
    function tabs() {
      if (ctx.mock) return "";
      return `<div class="coach-tabs" role="tablist">${[["chat", "对话", "chat"], ["agent", "智能体", "bot"]].map(([key, label, name]) => `<button role="tab" data-coach-tab="${key}" aria-selected="${tab === key}">${icon(name)}<span>${label}</span>${key === "agent" && job && busy ? '<i class="tab-dot" aria-hidden="true"></i>' : ""}</button>`).join("")}</div>`;
    }
    function render() {
      if (disposed) return;
      container.innerHTML = `${head()}<div class="panel-body coach-body">${tabs()}<div class="coach-pane">${tab === "agent" && !ctx.mock ? agentPane() : chatPane()}</div><p class="form-error" data-coach-error role="alert"></p></div>`;
      seen = transcript.length;
      if (job) { seenSteps = job.steps.length; liveKey = JSON.stringify(job.steps); }
      const log = container.querySelector(".coach-log");
      if (log) log.scrollTop = log.scrollHeight;
    }
    // 轮询时只改步骤列表和计时，进度条与头像动画保持连续。
    function updateLive() {
      if (disposed || tab !== "agent" || !job) return;
      const list = container.querySelector("[data-live-steps]");
      if (!list) return render();
      container.querySelector("[data-elapsed]").textContent = elapsed();
      const key = JSON.stringify(job.steps);
      if (key === liveKey) return;
      list.innerHTML = liveSteps();
      liveKey = key; seenSteps = job.steps.length;
      const log = container.querySelector(".coach-log");
      log.scrollTop = log.scrollHeight;
    }
    function fail(message) {
      busy = sending = false; render();
      const error = container.querySelector("[data-coach-error]");
      if (error) error.textContent = message;
    }
    async function send(mode, message = "") {
      if (busy) return;
      busy = sending = true; typed.chat = "";
      transcript = [...transcript, {role: "user", mode, text: message || labels(mode)}];
      render();
      try {
        // 由宿主页面排在草稿保存之后发送，回复返回的新草稿版本也由宿主接收。
        const response = await ctx.exchange({mode, message});
        transcript = response.transcript;
        seen = transcript.length - 1;
        if (response.notice) toast(response.notice, !response.counted && /离线/.test(response.notice));
      } catch (error) {
        transcript = transcript.slice(0, -1);
        if (message) typed.chat = message;
        return fail(error.message);
      }
      busy = sending = false; render();
    }
    async function runAgent(action, message = "") {
      if (busy || !ctx.agentStart) return;
      busy = true; typed.agent = "";
      transcript = [...transcript, {role: "user", mode: "agent", text: message || agentLabels[action]}];
      job = {status: "running", steps: [], result: null}; started = Date.now(); seenSteps = 0;
      render();
      try {
        const begun = await ctx.agentStart({action, message});
        const deadline = Date.now() + 6 * 60 * 1000;
        for (;;) {
          await new Promise(resolve => { poll = setTimeout(resolve, 1200); });
          if (disposed) return;
          job = await api(`/api/workbench/agent?id=${encodeURIComponent(ctx.id)}&job=${begun.job_id}`);
          if (job.status === "done") break;
          if (job.status === "error") throw new Error(job.error || "智能体运行出错");
          if (Date.now() > deadline) throw new Error("智能体超过 6 分钟没有完成，请稍后重试");
          updateLive();
        }
        transcript = job.result.transcript;
        seen = transcript.length - 1;
        ctx.agentDone?.(job.result);
        if (job.result.notice) toast(job.result.notice);
      } catch (error) {
        if (disposed) return;
        transcript = transcript.slice(0, -1);
        job = null;
        if (message) typed.agent = message;
        return fail(error.message);
      }
      busy = false; render();
    }
    function openSettings() {
      const dialog = document.createElement("dialog");
      dialog.className = "coach-settings";
      const available = settings.available;
      const keyHint = settings.has_key ? `已保存 ${settings.key_hint}，留空表示不修改` : "CPA 填 config.yaml 里 api-keys 的一项";
      dialog.innerHTML = `<form method="dialog"><div class="dialog-heading"><div><span class="eyebrow">COACH SETTINGS</span><h2>教练设置</h2></div><button type="button" class="icon-button" data-close aria-label="关闭">${icon("close")}</button></div>
        <p class="muted">默认离线引导，不发送任何数据。连接模型后，这道题的题意、你的草稿和代码、本轮测试结果和这道题的练习记录会发送给所选服务。</p>
        <fieldset class="coach-providers"><legend>教练来源</legend>${Object.entries(settings.labels).map(([key, label]) => { const relay = relays().includes(key), usable = relay || available[key]; return `<label class="${usable ? "" : "unavailable"}"><input type="radio" name="provider" value="${key}" ${settings.provider === key ? "checked" : ""} ${usable ? "" : "disabled"}><span><strong>${esc(label)}</strong><small>${esc(usable ? providerNote[key] : "未找到 claude 命令。")}${relay ? " 支持智能体。" : ""}</small></span></label>`; }).join("")}</fieldset>
        <div class="coach-endpoint" data-endpoint><label>服务地址<input name="base_url" value="${esc(settings.base_url)}" spellcheck="false" autocomplete="off"></label>
        <label>API Key<input name="api_key" type="password" placeholder="${esc(keyHint)}" autocomplete="off" spellcheck="false"></label><p class="form-hint" data-http-warning hidden>当前地址使用 http，Key 和代码会以明文经过网络，建议给 CPA 配置 HTTPS。</p></div>
        <label>模型<input name="model" value="${esc(settings.model)}" maxlength="100" spellcheck="false" list="coach-model-options"></label><datalist id="coach-model-options"></datalist>
        <div class="coach-model-row" data-endpoint><button type="button" class="text-button" data-coach-models>读取接口提供的模型</button><span class="form-hint" data-models-status></span></div>
        <p class="form-hint">连接模型前先测试；测试通过后才会保存地址和 Key 并启用。Key 只保存在本机 .runtime 目录，不会显示在页面上。${settings.tested_at ? `上次测试通过：${esc(settings.tested_at.slice(0, 16).replace("T", " "))}` : ""}</p>
        <p class="form-error" role="alert"></p>
        <div class="dialog-actions"><button type="button" class="button secondary" data-coach-offline>使用离线引导</button><button type="button" class="button primary" data-coach-test>测试并启用</button></div></form>`;
      document.body.append(dialog);
      dialog.addEventListener("close", () => dialog.remove(), {once: true});
      const error = dialog.querySelector(".form-error");
      const value = name => dialog.querySelector(`[name=${name}]`).value.trim();
      const chosen = () => dialog.querySelector("[name=provider]:checked")?.value;
      const sync = () => {
        const provider = chosen();
        dialog.querySelectorAll("[data-endpoint]").forEach(el => { el.hidden = !relays().includes(provider); });
        const env = provider === "openai" ? "OPENAI_BASE_URL" : "ANTHROPIC_BASE_URL";
        dialog.querySelector("[name=base_url]").placeholder = settings.env_base_urls?.[provider] ? `留空使用环境变量 ${env}` : "https://你的 VPS 域名:8317（不要带 /v1）";
        const base = value("base_url");
        dialog.querySelector("[data-http-warning]").hidden = !/^http:\/\//i.test(base) || /^http:\/\/(127\.0\.0\.1|localhost)(:|\/|$)/i.test(base);
      };
      dialog.addEventListener("change", event => {
        if (event.target.name === "provider") {
          const model = dialog.querySelector("[name=model]"), current = model.value.trim(), defaults = settings.default_models || {};
          const mismatch = family(current) && expectedFamily[chosen()] && family(current) !== expectedFamily[chosen()];
          if (defaults[chosen()] && (!current || Object.values(defaults).includes(current) || mismatch)) model.value = defaults[chosen()];
        }
        sync();
      });
      dialog.addEventListener("input", sync);
      sync();
      dialog.querySelector("[data-coach-models]").addEventListener("click", async event => {
        const status = dialog.querySelector("[data-models-status]");
        event.target.disabled = true; status.textContent = "读取中…";
        try {
          const result = await post("/api/coach/models", {provider: chosen(), base_url: value("base_url"), api_key: value("api_key")}, undefined, undefined, 30000);
          if (!result.ok) throw new Error(result.error);
          dialog.querySelector("#coach-model-options").innerHTML = result.models.map(id => `<option value="${esc(id)}"></option>`).join("");
          status.textContent = result.models.length ? `共 ${result.models.length} 个模型，点模型输入框可选择` : "接口没有返回模型列表，请手动填写";
        } catch (failure) { status.textContent = failure.message; }
        finally { event.target.disabled = false; }
      });
      dialog.querySelector("[data-coach-offline]").addEventListener("click", async () => {
        try { settings = {...settings, ...await post("/api/coach/settings", {provider: "offline", model: value("model")})}; dialog.close(); render(); toast("已切换为离线引导"); }
        catch (failure) { error.textContent = failure.message; }
      });
      dialog.querySelector("[data-coach-test]").addEventListener("click", async event => {
        const provider = chosen(), relay = relays().includes(provider);
        if (!provider || provider === "offline") { error.textContent = "请选择一个模型通道：OpenAI 兼容接口、Claude API 或本机 Claude Code。"; return; }
        if (relay && !value("base_url") && !settings.base_url && !settings.env_base_urls?.[provider]) { error.textContent = "请填写服务地址。"; return; }
        // 填了自己的服务地址时，环境变量里的 Key 不会发给它，需要在这里填写。
        if (relay && !value("api_key") && !settings.has_key && (value("base_url") || settings.base_url || !available[provider])) { error.textContent = "请填写 API Key（CPA 填 config.yaml 里 api-keys 的一项）。"; return; }
        event.target.disabled = true; event.target.textContent = "测试中，最多约 1 分钟…"; error.textContent = "";
        try {
          const body = {provider, model: value("model")};
          if (relay) Object.assign(body, {base_url: value("base_url"), api_key: value("api_key")});
          const result = await post("/api/coach/test", body, undefined, undefined, 75000);
          if (!result.ok) throw new Error(result.error);
          settings = {...settings, ...await api("/api/coach/settings")};
          dialog.close(); render(); toast(`连接正常（${result.seconds} 秒），已启用${settings.labels[provider]}`);
        } catch (failure) { error.textContent = failure.message; event.target.disabled = false; event.target.textContent = "测试并启用"; }
      });
      dialog.showModal();
    }
    const abort = new AbortController();
    container.addEventListener("click", event => {
      const mode = event.target.closest("[data-coach-mode]");
      if (mode && !mode.disabled) send(mode.dataset.coachMode);
      const action = event.target.closest("[data-agent-action]");
      if (action && !action.disabled) runAgent(action.dataset.agentAction);
      const switcher = event.target.closest("[data-coach-tab]");
      if (switcher && tab !== switcher.dataset.coachTab) { tab = switcher.dataset.coachTab; render(); }
      if (event.target.closest("[data-agent-apply]") && job?.result?.suggestion) { ctx.applySuggestion?.(job.result.suggestion); toast("已填入复盘，确认无误后点“保存结果并更新复习”"); }
      if (event.target.closest("[data-coach=settings]")) openSettings();
    }, {signal: abort.signal});
    // 重绘时保留输入框里还没发送的文字。
    container.addEventListener("input", event => {
      const form = event.target.closest(".coach-ask");
      if (form && event.target.name === "message") typed[form.matches("[data-agent-form]") ? "agent" : "chat"] = event.target.value;
    }, {signal: abort.signal});
    container.addEventListener("submit", event => {
      const form = event.target;
      if (!form.matches("[data-coach-form], [data-agent-form]")) return;
      event.preventDefault();
      event.stopPropagation();
      const text = form.elements.message.value.trim();
      if (!text) return;
      if (form.matches("[data-agent-form]")) runAgent("", text);
      else send("ask", text);
    }, {signal: abort.signal});
    render();
    return {destroy() { disposed = true; clearTimeout(poll); abort.abort(); }, busy: () => busy, send};
  }
  return {mount};
})();
