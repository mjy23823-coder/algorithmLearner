"use strict";

const paths = {
  code: '<path d="m8 6-6 6 6 6m8-12 6 6-6 6M14 3l-4 18"/>',
  network: '<circle cx="12" cy="12" r="3"/><circle cx="4" cy="5" r="2"/><circle cx="20" cy="5" r="2"/><circle cx="6" cy="21" r="2"/><circle cx="21" cy="19" r="2"/><path d="m6 7 4 3m4 0 4-3M10 15l-3 4m8-5 4 4"/>',
  home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
  repeat: '<path d="M3 10a9 9 0 0 1 15-6l3 3M21 3v4h-4M21 14a9 9 0 0 1-15 6l-3-3M3 21v-4h4"/>',
  layers: '<path d="m12 3 10 5-10 5L2 8zM2 12l10 5 10-5M2 16l10 5 10-5"/>',
  book: '<path d="M12 5c-3-2-7-2-10-1v15c3-1 7-1 10 1 3-2 7-2 10-1V4c-3-1-7-1-10 1v15"/>',
  chart: '<path d="M4 3v18h17M8 16v-5M13 16V7M18 16V4"/>',
  refresh: '<path d="M20 7a9 9 0 1 0 1 9M20 3v5h-5"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  spark: '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  edit: '<path d="m15 5 4 4M4 20l5-1L21 7a2 2 0 0 0-4-4L5 15z"/>',
  copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v1"/>',
  download: '<path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5"/>',
  flag: '<path d="M5 21V4c5-5 9 5 14 0v9c-5 5-9-5-14 0"/>',
  chat: '<path d="M20 12a8 8 0 0 1-11.6 7.1L4 20l1-4.4A8 8 0 1 1 20 12z"/><path d="M8.5 12h.01M12 12h.01M15.5 12h.01"/>',
  bot: '<rect x="4" y="8" width="16" height="12" rx="4"/><path d="M12 8V5"/><circle cx="12" cy="4" r="1"/><path d="M9.5 13.5v1M14.5 13.5v1M2 13v3M22 13v3"/>',
  send: '<path d="M21 3 10 14"/><path d="m21 3-7 18-4-7-7-4z"/>',
  bulb: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.8 10.6c.6.6.8 1.3.8 2.4h6c0-1.1.2-1.8.8-2.4A6 6 0 0 0 12 3z"/>',
  play: '<path d="M7 4.5v15l12-7.5z"/>',
  compare: '<path d="M7 3v14m0 0-3-3m3 3 3-3M17 21V7m0 0-3 3m3-3 3 3"/>',
  timer: '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l3 2M9.5 2h5M12 2v3"/>',
  target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.5"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
  note: '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9.5 13h6M9.5 17h4"/>',
  sliders: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  alert: '<path d="M12 4 2.8 20h18.4z"/><path d="M12 10v4M12 17v.01"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
};
const icon = (name) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.book}</svg>`;
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const $ = (selector) => document.querySelector(selector);
const labels = {graph:"知识图谱", today:"今日学习", profile:"我的画像", workbench:"练习工作台", mock:"模拟面试", review:"复习队列", problems:"题目档案", log:"学习记录", weekly:"能力周报"};
const statusLabels = {learned:"已掌握", learning:"待间隔验证", needs_review:"需要巩固", needs_calibration:"待校准", new:"待学习"};
const resultLabels = {independent:"独立完成", hinted:"提示后完成", failed:"暂未完成", unknown:"待校准"};
const oralLabels = {independent:"讲清楚了", hinted:"有卡顿", failed:"讲不出"};
// 口述复习里写了一半的讲解和 AI 判断，按题号保留，页面重绘时不丢。
const oralDrafts = {};
const WEEKLY_EMPTY = "点“生成点评”，根据本周记录写一段点评和下周安排。数字来自记录，未连接模型时按固定规则生成。";
let data = null;
let view = Object.hasOwn(labels, location.hash.slice(1)) ? location.hash.slice(1) : "graph";
let graphController = null;
let workbenchController = null;
let mockController = null;
let profileController = null;
let mockNotice = "";
let minutes = null;
try { const saved = Number(localStorage.getItem("algo-minutes")); if (saved >= 15 && saved <= 600) minutes = saved; } catch {}
let logs = null;
let requestSequence = 0;
let toastTimeout;
let filters = {text:"", topic:"", status:"", due:"all"};

document.querySelectorAll("[data-icon]").forEach(el => { el.innerHTML = icon(el.dataset.icon); });
document.querySelectorAll(".nav-button").forEach(button => {
  const label = button.querySelector(".nav-label")?.textContent.trim();
  if (label) { button.title = label; button.setAttribute("aria-label", label); }
});

const sidebarToggle = $("#sidebar-toggle");
function setSidebarCollapsed(collapsed) {
  document.body.classList.toggle("sidebar-collapsed", collapsed);
  if (sidebarToggle) {
    sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
    sidebarToggle.setAttribute("aria-label", collapsed ? "展开侧栏" : "折叠侧栏");
    sidebarToggle.title = collapsed ? "展开侧栏" : "折叠侧栏";
  }
  try { localStorage.setItem("algorithm-sidebar-collapsed", collapsed ? "1" : "0"); } catch {}
}
try { setSidebarCollapsed(localStorage.getItem("algorithm-sidebar-collapsed") === "1"); } catch { setSidebarCollapsed(false); }
sidebarToggle?.addEventListener("click", () => setSidebarCollapsed(!document.body.classList.contains("sidebar-collapsed")));

function toast(message, error = false, action = null) {
  const el = $("#toast");
  clearTimeout(toastTimeout);
  el.textContent = message;
  if (action) {
    const link = document.createElement("button");
    link.type = "button"; link.className = "toast-action"; link.textContent = action.label;
    link.addEventListener("click", () => { el.hidden = true; action.run(); }, {once: true});
    el.append(link);
  }
  el.className = `toast${error ? " error" : ""}${action ? " with-action" : ""}`;
  el.hidden = false;
  toastTimeout = setTimeout(() => { el.hidden = true; }, action ? 9000 : error ? 6500 : 4000);
}

async function api(path, options = {}) {
  const controller = new AbortController();
  const {timeout: limit = 12000, ...rest} = options;
  const timeout = setTimeout(() => controller.abort(), limit);
  try {
    const response = await fetch(path, {...rest, signal:controller.signal});
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || `请求失败（${response.status}）`);
    return body;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("本地服务响应超时，请确认启动窗口仍在运行");
    if (error instanceof TypeError) throw new Error("连接不到本地服务，请重新运行启动脚本后刷新");
    throw error;
  } finally { clearTimeout(timeout); }
}

async function load(quiet = false) {
  const seq = ++requestSequence;
  try {
    const next = await api(`/api/dashboard${minutes ? `?minutes=${minutes}` : ""}`);
    if (seq !== requestSequence) return;
    data = next;
    $("#connection").className = "connection";
    $("#connection").innerHTML = "<i></i>本地已连接";
    render();
  } catch (error) {
    $("#connection").className = "connection offline";
    $("#connection").innerHTML = "<i></i>连接已断开";
    if (!data) $("#main").innerHTML = `<div class="empty"><strong>暂时没有连接到学习空间</strong><p>${esc(error.message)}</p><br><button class="button secondary" data-action="refresh">重新连接</button></div>`;
    if (!quiet) toast(error.message, true);
  }
}

function pageHeading(title, subtitle, actions = "") {
  return `<div class="page-heading"><div><span class="eyebrow">YOUR ALGORITHM JOURNEY</span><h1>${esc(title)}</h1><p class="muted">${esc(subtitle)}</p></div>${actions ? `<div class="heading-actions">${actions}</div>` : ""}</div>`;
}
function button(text, action, type = "secondary", symbol = "", extra = "") {
  return `<button class="button ${type}" data-action="${action}" ${extra}>${symbol ? icon(symbol) : ""}${esc(text)}</button>`;
}
function metric(title, value, unit, foot, symbol, color = "") {
  return `<article class="stat-card"><div class="stat-label">${esc(title)}${icon(symbol)}</div><div class="stat-value">${esc(value)}<span>${esc(unit)}</span></div><div class="stat-foot ${color}">${esc(foot)}</div></article>`;
}
function taskRow(row) {
  const done = row.recorded && ["independent","hinted"].includes(row.result);
  const recommended = row.source === "recommended";
  const kind = recommended ? "为你推荐" : {review:"间隔复习", new:"新题", calibration:"校准练习", recall:"短时回忆"}[row.kind] || "练习";
  const result = row.recorded ? resultLabels[row.result] || "已记录" : "待开始";
  const badge = recommended ? "recommend" : {review:"review", calibration:"calibration"}[row.kind] || "new";
  // 排题理由只说明为什么排这道题，不写解法要点。
  const reasons = (row.reasons || []).filter(r => r !== "为你推荐");
  const reason = !row.recorded && reasons.length ? `<p class="task-reason">${esc(reasons.join(" · "))}</p>` : "";
  return `<div class="task-row"><span class="task-check ${done ? "done" : row.result === "failed" ? "failed" : ""}">${icon(done ? "check" : "clock")}</span><div class="task-main"><div class="task-title"><span class="task-id">LC ${esc(row.id)}</span>${esc(row.title)}</div><div class="task-meta"><span class="badge ${badge}">${kind}</span><span>${esc(row.topic)}</span><span>·</span><span>${esc(result)}</span>${row.recorded && row.next_due ? `<span>· ${esc(row.next_due.slice(5))} 再复习</span>` : ""}</div>${reason}</div><div class="task-action">${row.recorded ? `<button class="text-button" data-action="practice" data-id="${esc(row.id)}">${done ? "已记录" : "更新结果"}${icon(done ? "check" : "edit")}</button>` : `<button class="text-button" data-action="workbench" data-id="${esc(row.id)}">去练习${icon("code")}</button><button class="text-button" data-action="practice" data-id="${esc(row.id)}">记录${icon("arrow")}</button>${recommended ? `<button class="text-button muted-action" data-action="skip-recommend" data-id="${esc(row.id)}">换一题${icon("refresh")}</button>` : ""}`}</div></div>`;
}
function planWhy(plan) {
  const weak = plan.weak_errors || [], backlog = plan.backlog || {count:0};
  if (!weak.length && !backlog.count) return "";
  let body = "";
  if (backlog.count) body += `<div class="why-section"><h3>复习积压 ${backlog.count} 道${backlog.oral_ready ? `（${backlog.oral_ready} 道可以口述）` : ""} · 每天 ${backlog.per_day} 道正式复习 + ${backlog.oral_per_day} 道口述，约 ${backlog.clear_days} 天消化</h3><p>每天按优先级重新排序：遗忘风险、上次是否需要提示、近期错因、与当前专题的衔接，以及久未练习的专题轮换。选 180 分钟时会多安排 1 道复习。</p><div class="chip-row">${Object.entries(backlog.by_topic).map(([name,count])=>`<span class="chip">${esc(name)}<b>${count}</b></span>`).join("")}</div><ul class="deferred-list">${plan.deferred.slice(0,3).map(r=>`<li><strong>LC${esc(r.id)} ${esc(r.title)}</strong>：${esc(r.reasons.join("；"))}</li>`).join("")}</ul></div>`;
  if (weak.length) body += `<div class="why-section"><h3>近期反复错因</h3><div class="chip-row">${weak.slice(0,5).map(w=>`<button class="chip" data-action="graph-error" data-focus="errors:${esc(w.id)}" title="在图谱中查看证据">${esc(w.title)}<b>${w.count}</b></button>`).join("")}</div><p>涉及这些错因的到期题会优先复习。点击可在图谱里查看日志与复盘原文。</p></div>`;
  return `<section class="panel"><div class="panel-header"><div><h2>为什么这样排</h2><p class="muted">依据来自你的进度和有证据的错因记录。</p></div><button class="text-button" data-view="review">完整队列 ${icon("arrow")}</button></div><div class="panel-body">${body}</div></section>`;
}
function candidatePanel(plan) {
  if (!plan.candidates?.length) return "";
  return `<section class="panel"><div class="panel-header"><div><h2>更多为你推荐的新题</h2><p class="muted">按你的学习画像挑选：可以直接去练、固定加入待学，或换一题。</p></div><button class="text-button" data-view="profile">我的画像 ${icon("arrow")}</button></div><div class="task-list">${plan.candidates.map(c => AlgoProfile.recommendRow(c, {esc, icon})).join("")}</div></section>`;
}
// 口述复习：已写对过两次的题，2 分钟讲清思路，按结果调整下次复习。行不复用 .task-row，不计入今日清单。
function oralPanel(plan) {
  if (!plan.oral?.length && !plan.oral_done?.length) return "";
  const title = r => `<div class="task-title"><span class="task-id">LC ${esc(r.id)}</span>${esc(r.title)}</div>`;
  // 已记录的题高亮当前结果，点别的选项即更正（同一天再次记录会覆盖本次结果）。
  const choices = (r, current) => `<div class="oral-actions" role="group" aria-label="LC${esc(r.id)} 口述结果">${Object.entries(oralLabels).map(([key, text]) => `<button class="oral-choice ${key}${key === current ? " chosen" : ""}" data-action="oral" data-id="${esc(r.id)}" data-result="${key}" aria-pressed="${key === current}" ${key === current ? "disabled" : ""}>${text}</button>`).join("")}</div>`;
  const done = plan.oral_done.map(r => `<div class="oral-item"><div class="oral-row"><span class="task-check done">${icon("check")}</span><div class="task-main">${title(r)}<div class="task-meta"><span class="badge oral">口述复习</span><span>${esc(r.topic)}</span><span>·</span><span>${esc(oralLabels[r.result])}</span><span>· ${esc((r.next_due || "").slice(5))} ${r.result === "independent" ? "再复习" : "完整重写"}</span></div></div>${choices(r, r.result)}</div></div>`).join("");
  // 写下讲解后让 AI 按四项判断，建议结果由服务端按固定规则换算；保存仍要你点按钮。
  const judge = r => {
    const draft = oralDrafts[r.id];
    if (!draft?.open) return `<button class="text-button oral-open" data-action="oral-toggle" data-id="${esc(r.id)}">${icon("spark")}写下讲解，让 AI 判断</button>`;
    return `<div class="oral-judge"><textarea data-oral-text="${esc(r.id)}" rows="4" maxlength="2000" aria-label="LC${esc(r.id)} 的口述讲解" placeholder="合上代码，写下你会怎么讲：题型和依据、关键变量的含义与更新、时间和空间复杂度、一个边界。">${esc(draft.text || "")}</textarea><div class="oral-judge-actions"><button class="button primary" data-action="oral-judge" data-id="${esc(r.id)}" ${draft.busy ? "disabled" : ""}>${icon("spark")}${draft.busy ? "判断中…" : "让 AI 判断"}</button><button class="text-button" data-action="oral-toggle" data-id="${esc(r.id)}">收起</button></div>${draft.busy ? AlgoAI.waiting("正在按题型、思路、复杂度、边界四项判断…") : draft.judgment ? AlgoAI.judgment(draft.judgment, esc, icon) : ""}</div>`;
  };
  const todo = plan.oral.map(r => `<div class="oral-item"><div class="oral-row"><span class="task-check">${icon("chat")}</span><div class="task-main">${title(r)}<div class="task-meta"><span class="badge oral">口述复习</span><span>${esc(r.topic)}</span></div><p class="task-reason">${esc(r.reasons.join(" · "))}</p></div>${choices(r)}</div>${judge(r)}</div>`).join("");
  return `<section class="panel oral-panel"><div class="panel-header"><div><h2 class="tip-title">${icon("chat")}口述复习 · 每道约 2 分钟</h2><p class="muted">合上代码，说出题型、核心思路、时间与空间复杂度和一个边界。讲清楚了进入下一个复习间隔；卡住了会安排完整重写。不占正式复习名额。</p></div><span class="subtle-pill">今天 ${plan.oral_done.length} / ${plan.oral_slots}</span></div><div class="task-list">${done}${todo}</div></section>`;
}
// 问问 AI：只依据今天的计划回答；建议换可用时间时给出按钮，由你点了才重新排。
function askPanel(plan) {
  const messages = data.plan_chat || [];
  const chips = ["时间不够，先做哪道？", "为什么排这几道题？", "复习和新题怎么分配时间？"];
  const log = messages.map(m => m.role === "user" ? `<div class="ask-msg user"><p>${esc(m.text)}</p></div>`
    : `<div class="ask-msg coach"><p>${esc(m.text)}</p><small>${esc(m.label || "")}${m.model ? ` · ${esc(m.model)}` : ""}</small>${m.minutes && m.minutes !== plan.minutes ? `<button class="button secondary ask-minutes" data-action="minutes" data-minutes="${m.minutes}">${icon("clock")}按 ${m.minutes} 分钟重新排</button>` : ""}</div>`).join("");
  return `<section class="panel ask-panel"><div class="panel-header"><h2 class="tip-title">${icon("chat")}问问 AI</h2><span class="subtle-pill">只给建议，不改记录</span></div><div class="panel-body"><div class="ask-log" data-ask-log>${log || '<p class="form-hint">关于今天的计划，想问什么都可以。AI 可以建议顺序或时间，要改由你确认。</p>'}</div><div class="chip-row ask-chips">${chips.map(c => `<button class="chip" data-action="plan-ask" data-question="${esc(c)}">${esc(c)}</button>`).join("")}</div><form id="plan-ask-form" class="ask-form" autocomplete="off"><input name="question" maxlength="500" placeholder="例如：今天只有 1 小时，怎么安排？" aria-label="向 AI 提问今天的计划" autocomplete="off" autocapitalize="off" spellcheck="false"><button class="coach-send" type="submit" aria-label="提问" title="提问">${icon("send")}</button></form></div></section>`;
}
async function askPlan(question) {
  question = (question || "").trim();
  const panel = $(".ask-panel");
  if (!question || !panel || panel.dataset.busy) return;
  panel.dataset.busy = "1";
  panel.querySelectorAll("button, input").forEach(el => { el.disabled = true; });
  const log = panel.querySelector("[data-ask-log]");
  log.querySelector(".form-hint")?.remove();
  log.insertAdjacentHTML("beforeend", `<div class="ask-msg user"><p>${esc(question)}</p></div><div class="ask-msg coach">${AlgoAI.waiting("思考中…")}</div>`);
  log.scrollTop = log.scrollHeight;
  try {
    const result = await post("/api/plan/ask",{question,minutes:data.plan.minutes},undefined,undefined,100000);
    data.plan_chat = result.messages;
    if (result.notice) toast(result.notice,true);
  } catch (error) { toast(error.message,true); }
  render();
}
function profileCard() {
  const p = data.profile;
  return `<section class="panel profile-card"><div class="panel-header"><h2 class="tip-title">${icon("user")}你的学习画像</h2><button class="text-button" data-view="profile">完整画像 ${icon("arrow")}</button></div><div class="panel-body"><ul class="profile-lines">${p.summary.slice(0, 3).map(line => `<li>${esc(line)}</li>`).join("")}</ul>${p.focus[0] ? `<p class="profile-next">${icon("spark")}<span>${esc(p.focus[0])}</span></p>` : ""}</div></section>`;
}
function mockPanel(plan) {
  if (!plan.mock_due) return "";
  const pick = plan.mock_candidates?.[0];
  return `<section class="panel"><div class="panel-header"><h2 class="tip-title">${icon("flag")}本周还没有限时模拟</h2></div><div class="panel-body"><p class="muted">每周一次，练时间感和表达。${pick ? `可从已学专题抽一道 ${esc(pick.difficulty)}，限时 ${pick.limit_minutes} 分钟。` : ""}</p><button class="button secondary full-width" data-view="mock">${icon("clock")}开始模拟面试</button></div></section>`;
}
function heatmap() {
  const active = data.activity.filter(day => day.count > 0).length;
  return `<section class="panel"><div class="panel-header"><h2>一点一滴，都算数</h2><span class="subtle-pill">近 12 周</span></div><div class="panel-body"><div class="heatmap-head"><p>可追溯记录中，共有 ${active} 个练习日</p><p>保持自己的节奏</p></div><div class="heatmap" aria-label="近 12 周练习次数">${data.activity.map(day => `<span class="heat-cell" data-level="${Math.min(day.count,4)}" title="${esc(day.date)} · ${day.count} 次练习" aria-label="${esc(day.date)}，${day.count} 次练习"></span>`).join("")}</div><div class="heatmap-legend">少 ${[0,1,2,3,4].map(i=>`<span class="heat-cell" data-level="${i}"></span>`).join("")} 多</div></div></section>`;
}
function forecast() {
  const maximum = Math.max(1, ...data.forecast.map(day => day.count));
  return `<section class="panel"><div class="panel-header"><h2>接下来 7 天</h2><span class="subtle-pill">复习节奏</span></div><div class="panel-body"><div class="forecast">${data.forecast.map((day, i) => `<div class="forecast-item"><strong>${day.count || "—"}</strong><span class="bar" data-size="${day.count ? Math.max(1,Math.round(day.count / maximum * 7)) : 0}" title="${esc(day.date)}：${day.count} 道到期题"></span><small>${i === 0 ? "今天" : day.date.slice(5).replace("-","/")}</small></div>`).join("")}</div><p class="form-hint">逾期题计入今天，按可用时间逐步完成。</p></div></section>`;
}
function homePage() {
  const plan = data.plan;
  const pending = plan.pending_count;
  const day = new Date(`${data.date}T12:00:00`).toLocaleDateString("zh-CN",{year:"numeric",month:"long",day:"numeric",weekday:"long"});
  let html = pageHeading("每天进步一点点。",`${day} · ${data.goal}`,button("结束并保存","wrap","secondary","flag") + button("记录练习","practice","primary","plus"));
  html += `<div class="stats-grid">${metric("今日完成",data.stats.today_done,"道",pending ? `还有 ${pending} 道计划任务` : data.stats.today_done ? "今天的积累已经留下" : "从一道题开始", "check","green")}${metric("已记录题目",data.stats.recorded,"道","持续积累你的解题经验","layers")}${metric("到期复习",data.stats.due,"道","按到期顺序，逐步巩固","repeat", data.stats.due ? "amber" : "")}${metric("已掌握",data.stats.learned,"道","至少两次完成的掌握标记","spark","green")}</div>`;
  html += `<div class="content-grid"><div class="stack"><section class="panel"><div class="panel-header"><div><h2>今天的学习清单</h2><p class="muted">${data.stats.today_done && !pending ? "今天的计划已完成。整理收获，让知识留下来。" : "先复习，再前进。每一道题都给自己一次思考的机会。"}</p></div><span class="subtle-pill">${esc(plan.mode)}</span></div><div class="time-control"><span>今天可用时间</span><div class="time-options" role="group" aria-label="今天可用时间">${[...new Set([45,90,120,180,data.profile.settings.daily_minutes,plan.minutes])].sort((a,b)=>a-b).map(n=>`<button class="time-option ${plan.minutes === n ? "active" : ""}" data-action="minutes" data-minutes="${n}" aria-pressed="${plan.minutes === n}">${n} 分钟</button>`).join("")}</div></div><div class="task-list">${plan.tasks.length ? plan.tasks.map(taskRow).join("") : '<div class="empty"><strong>给今天留一个小目标</strong>暂时没有待安排的题目，可以在题目档案补充待学队列。</div>'}</div><div class="plan-footer"><span>${data.stats.today_done} 道已完成 · ${pending} 道待练习${plan.deferred.length ? ` · ${plan.deferred.length} 道复习顺延` : ""}</span><button class="text-button" data-action="coach">让教练带我学习 ${icon("arrow")}</button></div></section>${plan.short_recall.length ? `<section class="panel"><div class="panel-header"><h2>先花 5～10 分钟回忆</h2><span class="subtle-pill">不占正式名额</span></div><div class="task-list">${plan.short_recall.map(taskRow).join("")}</div></section>` : ""}${oralPanel(plan)}${planWhy(plan)}${candidatePanel(plan)}${heatmap()}</div><div class="stack right-column">${profileCard()}${askPanel(plan)}${mockPanel(plan)}<section class="panel focus-panel"><div class="panel-header"><span class="eyebrow">CURRENT FOCUS</span><button class="icon-button" data-action="settings" aria-label="调整学习方向">${icon("edit")}</button></div><div class="panel-body"><h2>${esc(plan.current_topic || "找到你的学习方向")}</h2><p>${esc(plan.session.next_action || "从到期复习开始，再推进一道新题。")}</p><div class="focus-steps" aria-label="间隔复习：3 天、7 天、21 天"><span>3 天</span><b>→</b><span>7 天</span><b>→</b><span>21 天</span></div>${button("与聊天教练继续","coach","secondary","arrow")}</div></section><section class="panel"><div class="panel-header"><h2 class="tip-title">${icon("spark")}先解释，再动手</h2></div><div class="panel-body"><ol class="coach-steps"><li><b>1</b><span><strong>说清题意</strong> · 这是什么类型的问题？</span></li><li><b>2</b><span><strong>解释变量</strong> · 每个变量代表什么？</span></li><li><b>3</b><span><strong>走一个例子</strong> · 手动验证你的思路。</span></li><li><b>4</b><span><strong>写完再复述</strong> · 一句话总结模板。</span></li></ol></div></section>${forecast()}</div></div>`;
  const notices = [...data.warnings.map(w => w.message)];
  if (plan.new_shortage) notices.push(`新题目录里暂时没有合适的推荐，还可以补充 ${plan.new_shortage} 道新题。`);
  html += `<div class="notices">${notices.map(n=>`<div class="notice">${icon("info")}<span>${esc(n)}</span></div>`).join("")}</div>`;
  return html;
}

function filterControls(isReview) {
  return `<div class="filters"><input class="search" id="search" placeholder="搜索题号、题名、错因…" aria-label="搜索题目" value="${esc(filters.text)}"><select id="topic-filter" aria-label="按专题筛选"><option value="">全部专题</option>${data.topics.map(t=>`<option ${filters.topic === t.name ? "selected" : ""}>${esc(t.name)}</option>`).join("")}</select>${isReview ? `<select id="due-filter" aria-label="按复习时间筛选"><option value="all" ${filters.due === "all" ? "selected" : ""}>全部排期</option><option value="due" ${filters.due === "due" ? "selected" : ""}>已经到期</option><option value="upcoming" ${filters.due === "upcoming" ? "selected" : ""}>尚未到期</option></select>` : `<select id="status-filter" aria-label="按掌握状态筛选"><option value="">全部状态</option>${Object.entries(statusLabels).filter(([key])=>key!=="new").map(([key,label])=>`<option value="${key}" ${filters.status===key ? "selected" : ""}>${label}</option>`).join("")}</select>`}</div>`;
}
function tableRows(isReview) {
  const query = filters.text.toLowerCase().replace(/^lc\s*/, "");
  const rows = data.queue.filter(row => (!query || `${row.id} ${row.title} ${row.note}`.toLowerCase().includes(query)) && (!filters.topic || row.topic===filters.topic) && (isReview ? filters.due === "all" || (filters.due === "due" ? row.due : !row.due) : !filters.status || row.display_status === filters.status));
  if (!rows.length) return `<tr><td colspan="6"><div class="empty">没有符合条件的题目，试试其他筛选条件。</div></td></tr>`;
  return rows.map(row=>`<tr><td><strong>LC ${esc(row.id)} · ${esc(row.title)}</strong><small>${esc(row.topic)}${row.history_import ? " · 历史日志补录" : ""}</small></td><td><span class="badge ${row.display_status === "learned" ? "green" : esc(row.display_status)}">${esc(statusLabels[row.display_status] || row.display_status)}</span></td><td>${row.count_is_lower_bound ? (row.count ? `至少 ${row.count} 次` : "待核对") : `${row.count} 次`}</td><td><span class="${row.overdue_days ? "overdue" : ""}">${esc(isReview ? row.next_due : row.last_done)}</span>${isReview ? `<small>${row.overdue_days ? `逾期 ${row.overdue_days} 天` : row.due ? "今天到期" : "按计划复习"}</small>` : ""}</td><td>${isReview ? `<span class="row-note">${esc(row.note || "不看代码，独立重写并解释思路")}</span>` : `<span>${esc(row.next_due)}</span>`}</td><td><button class="text-button" data-action="practice" data-id="${esc(row.id)}">记录练习</button><button class="text-button" data-action="coach" data-id="${esc(row.id)}">${row.status === "needs_calibration" ? "核对历史" : "教练带练"}</button></td></tr>`).join("");
}
function tablePage(isReview) {
  let html = pageHeading(isReview ? "让记忆，慢慢扎根。" : "走过的题，都留在这里。", isReview ? "按到期日期排序。忘记很正常，复习让理解更牢固。" : "记录真实状态，积累每一题的思路与卡点。", button("记录练习","practice","primary","plus"));
  html += filterControls(isReview) + `<section class="panel"><div class="table-scroll"><table><thead><tr><th>题目 / 专题</th><th>掌握状态</th><th>完成次数</th><th>${isReview ? "复习日期" : "最近练习"}</th><th>${isReview ? "上次复盘" : "下次复习"}</th><th>继续学习</th></tr></thead><tbody id="problem-rows">${tableRows(isReview)}</tbody></table></div></section>`;
  if (!isReview) html += `<br><section class="panel"><div class="panel-header"><div><h2>接下来想学的题</h2><p class="muted">填入题号即可加入队列。已做过或日志里提到的题会提示核对。</p></div></div><div class="queue-items">${data.next_new.map(row=>`<span class="queue-chip">LC ${esc(row.id)} ${row.title === "待填写题名" ? "" : esc(row.title)}<button data-action="remove-queue" data-id="${esc(row.id)}" aria-label="从待学队列移除 LC${esc(row.id)}">${icon("close")}</button></span>`).join("") || '<span class="muted">队列还是空的，加入下一道想学的题吧。</span>'}</div><form id="queue-form" class="queue-add"><input name="ids" placeholder="题号，用空格或逗号分隔，例如 42 239" aria-label="待学题号" required><button class="button secondary" type="submit">${icon("plus")}加入队列</button></form><p class="inline-error" id="queue-error" role="alert"></p></section>`;
  return html;
}
function logPage() {
  return pageHeading("留下今天，也照亮下一步。","学习记录按日期展示，原有日志完整保留。", button("保存今日总结","wrap","primary","book")) + (logs === null ? '<div class="loading-state">正在读取学习日志…</div>' : `<p class="topic-subtitle">共 ${logs.length} 篇学习记录</p><div class="log-list">${logs.map((entry,i)=>`<details class="log-entry" ${i===0 ? "open" : ""}><summary>${esc(entry.title)}</summary><div class="log-body">${esc(entry.body)}</div></details>`).join("") || '<div class="empty">还没有学习日志。完成一次练习后，保存今日总结。</div>'}</div>`);
}
function delta(now, before, unit, higherIsGood = true) {
  if (now === null || now === undefined || before === null || before === undefined) return {text:"上周没有可比数据", cls:""};
  const diff = Math.round((now - before) * 10) / 10;
  if (!diff) return {text:"与上周持平", cls:""};
  return {text:`较上周 ${diff > 0 ? "↑" : "↓"} ${Math.abs(diff)}${unit}`, cls:(diff > 0) === higherIsGood ? "green" : "down"};
}
function dimensionPanel(report) {
  const scored = report.dimensions.some(d => d.latest !== null);
  const rows = report.mocks.slice().reverse();
  const body = scored ? `<div class="dim-legend"><span><i class="key-bar"></i>最近一次</span><span><i class="key-avg"></i>近 4 次平均</span><span>满分 5 分</span></div><div class="dim-list">${report.dimensions.map(d => `<div class="dim-row" title="${esc(d.title)}：最近 ${d.latest ?? "—"} 分，近 4 次平均 ${d.average ?? "—"} 分"><span>${esc(d.title)}</span><div class="dim-track" role="img" aria-label="${esc(d.title)}：最近 ${d.latest ?? "无"} 分，近 4 次平均 ${d.average ?? "无"} 分，满分 5 分">${d.latest ? `<span class="dim-bar" data-score="${d.latest}"></span>` : ""}${d.average ? `<span class="dim-avg" data-avg="${Math.round(d.average * 2) * 5}"></span>` : ""}</div><output>${d.latest ?? "—"} 分 · 均 ${d.average ?? "—"}</output></div>`).join("")}</div>`
    : `<div class="empty"><strong>还没有分维度的模拟记录</strong>完成一场模拟面试后，这里会对比最近一次和近 4 次的平均分。<br><br><button class="button secondary" data-view="mock">${icon("clock")}开始模拟面试</button></div>`;
  const table = rows.length ? `<div class="table-scroll"><table class="compact-table"><thead><tr><th>日期 / 题目</th><th>用时 / 限时</th><th>平均分</th></tr></thead><tbody>${rows.map(m => `<tr><td><strong>LC ${esc(m.id)} · ${esc(m.title)}</strong><small>${esc(m.date)}${m.improve ? ` · ${esc(m.improve)}` : ""}</small></td><td>${m.minutes ?? "—"} / ${m.limit_minutes ?? "—"} 分钟${m.overtime ? "<small>超时</small>" : ""}</td><td>${m.average ?? "—"}<small>${m.scores ? ({coach_suggested:"参考教练建议", chat_coach:"聊天教练评分"}[m.scored_by] || "自评") : "未评分"}</small></td></tr>`).join("")}</tbody></table></div>` : "";
  return `<section class="panel"><div class="panel-header"><div><h2>模拟面试五维</h2><p class="muted">题型识别、沟通表达、代码正确性、复杂度分析、时间控制。</p></div><span class="subtle-pill">共 ${report.mock_total} 场</span></div><div class="panel-body">${body}</div>${table}</section>`;
}
function weeklyAdvice() {
  return `<section class="panel advice-panel"><div class="panel-header"><div><h2 class="tip-title">${icon("spark")}AI 周报点评</h2><p class="muted">数字来自记录，模型只写点评和下周安排，不发送代码。</p></div><button class="button secondary" data-action="weekly-advice">${icon("spark")}<span>${data.weekly_advice ? "重新点评" : "生成点评"}</span></button></div><div class="panel-body"><div class="advice-card"><div data-weekly-advice>${AlgoAI.noteBody(data.weekly_advice, esc, WEEKLY_EMPTY)}</div></div></div></section>`;
}
function weeklyPage() {
  const report = data.insights, week = report.week, previous = report.previous_week, legacy = data.weekly;
  const days = delta(week.active_days, previous.active_days, " 天");
  const rate = delta(week.independent_rate, previous.independent_rate, " 个百分点");
  const time = delta(week.avg_minutes, previous.avg_minutes, " 分钟", false);
  let html = pageHeading("回头看看，你已经走了多远。",`${week.start} — ${week.end} · 能力周报`,`<button class="button secondary" data-view="mock">${icon("clock")}开始模拟面试</button>` + button("导出周报","export-report","secondary","download") + button("导出进度","export","primary","download"));
  html += `<div class="stats-grid">${metric("学习日",week.active_days,"天",days.text,"book",days.cls)}${metric("独立完成率",week.independent_rate ?? "—",week.independent_rate === null ? "" : "%",`${week.graded} 次有结果 · ${rate.text}`,"check",rate.cls)}${metric("平均用时",week.avg_minutes ?? "—",week.avg_minutes === null ? "" : "分钟",week.timed ? `${week.timed} 次有用时记录 · ${time.text}` : "还没有用时记录","clock",week.timed ? time.cls : "")}${metric("限时模拟",week.mocks,"次",report.last_mock ? `上次 ${report.last_mock}` : "还没有模拟记录","flag",week.mocks ? "green" : "amber")}</div>`;
  const focus = `<section class="panel"><div class="panel-header"><div><h2>下周重点</h2><p class="muted">由错因、积压、模拟和用时记录自动生成。</p></div></div><div class="panel-body"><ol class="focus-list">${(report.focus.length ? report.focus : ["保持当前节奏，按复习队列推进。"]).map(item => `<li>${esc(item)}</li>`).join("")}</ol></div></section>`;
  const errors = `<section class="panel"><div class="panel-header"><div><h2>近期反复错因</h2><p class="muted">近 4 周至少出现两次，或 7 天内刚出现。历史错因不代表现在仍不会。</p></div><button class="text-button" data-action="graph-error" data-focus="">错因图谱 ${icon("arrow")}</button></div><div class="panel-body">${report.errors.length ? `<ul class="evidence-list">${report.errors.map(e => `<li><strong>${esc(e.title)}</strong> · 近 4 周 ${e.count} 次 · 最近 ${esc(e.last_seen)}<small>涉及 ${e.problem_ids.map(id => "LC" + esc(id)).join("、")}${e.improved.length ? `；之后已独立完成 ${e.improved.map(f => `LC${esc(f.id)}（${esc(f.fixed_date)}）`).join("、")}` : ""}</small><small>${esc(e.question)}</small></li>`).join("")}</ul>` : '<div class="empty">近 4 周没有反复出现的错因。</div>'}</div></section>`;
  const progress = `<section class="panel"><div class="panel-header"><div><h2>有记录支持的进步</h2><p class="muted">同一道题先需要提示或未完成，间隔至少两天后独立完成。</p></div></div><div class="panel-body">${report.progress.length ? `<ul class="evidence-list">${report.progress.map(p => `<li><strong>LC ${esc(p.id)} · ${esc(p.title)}</strong><small>${esc(p.from.date)} ${esc(resultLabels[p.from.result])} → ${esc(p.to.date)} 独立完成</small>${p.to.note ? `<small>${esc(p.to.note)}</small>` : ""}</li>`).join("")}</ul>` : '<div class="empty">还没有“先卡住、后独立完成”的记录。下一次复习时不看代码重写，就会留下证据。</div>'}</div></section>`;
  const notes = `<section class="panel"><div class="panel-header"><h2>这一周，记住了什么</h2><span class="subtle-pill">错因与收获</span></div><div class="panel-body">${legacy.notes.length ? `<ul class="weekly-notes">${legacy.notes.map(note=>`<li><strong>LC ${esc(note.id)} · ${esc(note.title)}</strong><small> · ${esc(note.date)}</small><p>${esc(note.note)}</p></li>`).join("")}</ul>` : '<div class="empty"><strong>下一次练习，留下一句话。</strong>记录核心思路或一个错因，之后会在这里汇成你的复盘。</div>'}</div></section>`;
  const topics = `<section class="panel"><div class="panel-header"><div><h2>专题进度</h2><p class="muted">已掌握 / 已记录 · 全部时间</p></div></div><div class="table-scroll"><table class="compact-table"><thead><tr><th>专题</th><th>已掌握</th><th>需巩固</th><th>待校准</th><th>到期</th></tr></thead><tbody>${report.topics.map(t => `<tr><td><strong>${esc(t.name)}</strong><meter min="0" max="${t.total}" value="${t.learned}" aria-label="${esc(t.name)}：${t.learned} 道已掌握，共 ${t.total} 道"></meter></td><td>${t.learned} / ${t.total}</td><td>${t.needs_review}</td><td>${t.calibration}</td><td>${t.due ? `<span class="overdue">${t.due}</span>` : "0"}</td></tr>`).join("")}</tbody></table></div></section>`;
  const results = `<section class="panel weekly-summary"><h2>本周练习结果</h2><p>独立完成 ${week.independent} 次<br>提示后完成 ${week.hinted} 次<br>暂未完成 ${week.failed} 次${week.inferred ? `<br>其中 ${week.inferred} 次按旧记录状态推断` : ""}<br>只有历史日期的记录 ${week.practices - week.graded} 次</p></section>`;
  html += `<div class="content-grid"><div class="stack">${weeklyAdvice()}${focus}${dimensionPanel(report)}${errors}${progress}${notes}</div><div class="stack">${topics}${results}${heatmap()}</div></div>`;
  html += `<div class="notices">${[...report.gaps, legacy.coverage].map(text => `<div class="notice">${icon("info")}<span>${esc(text)}</span></div>`).join("")}</div>`;
  return html;
}
function render() {
  if (!data) return;
  if (graphController) { graphController.destroy(); graphController = null; }
  if (workbenchController) { workbenchController.destroy(); workbenchController = null; }
  if (mockController) { mockController.destroy(); mockController = null; }
  if (profileController) { profileController.destroy(); profileController = null; }
  document.querySelectorAll("[data-view]").forEach(button => { const active = button.dataset.view === view; button.classList.toggle("active",active); if(active) button.setAttribute("aria-current","page"); else button.removeAttribute("aria-current"); });
  $("#breadcrumb").textContent = labels[view];
  $("#review-count").textContent = data.stats.due;
  $("#main").classList.toggle("graph-page", view === "graph");
  $("#main").classList.toggle("workbench-page", view === "workbench" || view === "mock");
  $("#main").classList.toggle("mock-page", view === "mock");
  $("#main").innerHTML = view === "graph" ? AlgoGraph.page(data, {icon, esc, button}) : view === "workbench" ? AlgoWorkbench.page(data, {icon, esc, button}) : view === "mock" ? AlgoMock.page() : view === "today" ? homePage() : view === "profile" ? AlgoProfile.page(data, profileUi()) : view === "review" ? tablePage(true) : view === "problems" ? tablePage(false) : view === "log" ? logPage() : weeklyPage();
  if (view === "graph") graphController = AlgoGraph.mount($("#main"), data, {icon, esc, button});
  if (view === "profile") profileController = AlgoProfile.mount($("#main"), data, profileUi());
  if (view === "workbench") workbenchController = AlgoWorkbench.mount($("#main"), data, {icon, esc, button, api, post, toast,
    onComplete: async (pid, message) => { view = "graph"; AlgoGraph.setRelation("topics"); history.replaceState(null,"","#graph"); await load(); graphController?.focusProblem(pid); window.scrollTo({top:0,behavior:"instant"}); suggestNext(message); }, onSelect: () => render()});
  if (view === "mock") {
    mockController = AlgoMock.mount($("#main"), data, {icon, esc, api, post, toast, notice:mockNotice,
      onComplete: async (text) => { mockNotice = text; logs = null; await load(); }});
    mockNotice = "";
  }
  if (view === "log" && logs === null) loadLogs();
}
function profileUi() {
  return {esc, icon, metric, button, api, post, toast, reload: () => load()};
}
// 保存一道题后，按最新计划提示下一题（复习或为你推荐的新题）。
function suggestNext(message) {
  const next = data.plan.tasks.find(t => !t.recorded);
  if (!next) { if (message) toast(`${message}。今天的计划已完成`); return; }
  const why = next.source === "recommended" ? "为你推荐" : {review:"复习", new:"新题", calibration:"校准"}[next.kind] || "练习";
  toast(`${message ? message + "。" : ""}下一题：LC${next.id} ${next.title}（${why}）`, false,
        {label: "去练习", run: async () => { AlgoWorkbench.choose(next.id); await navigate("workbench"); }});
}
async function loadLogs() {
  try { logs = (await api("/api/log")).sections; if(view === "log") render(); }
  catch (error) { if(view === "log") $("#main").innerHTML = pageHeading("学习记录","读取失败，请重试。",button("刷新","refresh")) + `<div class="empty">${esc(error.message)}</div>`; }
}
async function navigate(next) {
  if (!Object.hasOwn(labels,next)) return;
  if (workbenchController && !await workbenchController.beforeLeave()) return;
  if (mockController && !await mockController.beforeLeave()) return;
  view = next;
  filters = {text:"",topic:"",status:"",due:"all"};
  if (location.hash !== `#${next}`) history.replaceState(null,"",`#${next}`);
  render();
  window.scrollTo({top:0,behavior:"instant"});
}
function findProblem(id) {
  return data.queue.find(row => row.id === id) || data.next_new.find(row => row.id === id) || data.plan.tasks.find(row => row.id === id);
}
function openPractice(id) {
  const dialog = $("#practice-dialog"), form = $("#practice-form");
  form.reset();
  form.querySelector(".form-error").textContent = "";
  const row = id ? findProblem(id) : null;
  if (row) {
    form.elements.id.value = row.id;
    form.elements.title.value = row.title === "待填写题名" ? "" : row.title;
    form.elements.topic.value = row.topic || data.plan.current_topic;
    const entry = row.history?.at(-1);
    if (entry?.date === data.date) {
      form.elements.note.value = entry.note || "";
      form.elements.minutes.value = entry.minutes || "";
      form.elements.result.value = entry.result;
      form.elements.mock.checked = Boolean(entry.mock);
    }
  } else form.elements.topic.value = data.plan.current_topic || "";
  dialog.dataset.revision = data.revision;
  dialog.dataset.requestId = crypto.randomUUID();
  dialog.showModal();
}
function openCoach(id, mock = false) {
  let prompt = `请作为我的 Python 算法学习教练，先读取本项目的 agent.md、algorithm-agent.md、learning-state.json 和最近的 learning-log.md。\n\n`;
  const row = id ? findProblem(id) : null;
  if (mock) prompt += "我想做一次限时模拟面试。请基于已学专题选题，先让我复述题意和思路，再写代码；结束后检查边界、复杂度和表达，记录实际用时。";
  else if (row && (row.status === "needs_calibration" || data.plan.calibration.some(item => item.id === row.id))) prompt += `请先核对 LC${row.id} ${row.title} 的历史完成情况。它是待校准的旧题，不要当成新题；日期或独立完成情况不明确时先向我确认。`;
  else if (row) prompt += `请带我练习 LC${row.id} ${row.title}。先让我解释题意、变量和一个小例子，再按需要给分层提示。不要一开始直接给完整答案。`;
  else prompt += `今天可用 ${minutes} 分钟。请运行 python tools/coach.py today --minutes ${minutes}，按真实进度继续。今天已有 ${data.stats.today_done} 道完成记录，请计入题量；若已完成今天的计划，先帮我复盘收尾。`;
  prompt += "\n\n代码提交后请实际运行测试，检查正确性、边界和复杂度。完成后用 tools/coach.py 记录结果；今天结束时用 wrap 保存总结。不要编造完成记录。";
  $("#coach-prompt").value = prompt;
  $("#coach-dialog").showModal();
}
function openWrap() {
  const form = $("#wrap-form"), dialog = $("#wrap-dialog");
  form.reset();
  form.querySelector(".form-error").textContent = "";
  form.elements.next_action.value = data.plan.session.next_action || "先安排到期复习，再推进当前专题";
  $("#wrap-description").textContent = `今天已完成 ${data.stats.today_done} 道题。用一两句话记住最有价值的收获。`;
  dialog.dataset.revision = data.revision;
  dialog.dataset.requestId = crypto.randomUUID();
  dialog.showModal();
}
async function post(path, payload, revision = data.revision, requestId = crypto.randomUUID(), timeout = 12000) {
  return api(path,{method:"POST",timeout,headers:{"Content-Type":"application/json","X-Coach-Token":data.token},body:JSON.stringify({...payload,revision,request_id:requestId})});
}
async function submitDialog(form, path, payload) {
  const dialog = form.closest("dialog");
  const submit = form.querySelector('[type="submit"]');
  const error = form.querySelector(".form-error");
  submit.disabled = true;
  error.textContent = "";
  try {
    const result = await post(path,payload,dialog.dataset.revision,dialog.dataset.requestId);
    dialog.close();
    logs = null;
    toast(result.message);
    await load();
  } catch (failure) {
    error.textContent = failure.message;
    // 发生并发更新时保留输入，用户可关闭弹窗、刷新并核对后重试。
  } finally { submit.disabled = false; }
}

document.addEventListener("click", async event => {
  const close = event.target.closest("[data-close]");
  if (close) { close.closest("dialog").close(); return; }
  const nav = event.target.closest("[data-view]");
  if (nav) { navigate(nav.dataset.view); return; }
  const target = event.target.closest("[data-action]");
  if (!target || target.disabled) return;
  const action = target.dataset.action;
  if (action === "refresh") { logs = null; await load(); return; }
  if (!data) return;
  if (action === "practice") openPractice(target.dataset.id);
  if (action === "workbench") { AlgoWorkbench.choose(target.dataset.id); await navigate("workbench"); }
  if (action === "graph-relation") { AlgoGraph.setRelation(target.dataset.relation, target.dataset.focus); render(); }
  if (action === "graph-error") { AlgoGraph.setRelation("errors", target.dataset.focus || undefined); await navigate("graph"); }
  if (action === "add-candidate") {
    target.disabled = true;
    try { await post("/api/queue",{action:"add",ids:[target.dataset.id]}); toast(`LC${target.dataset.id} 已加入待学队列`); await load(); }
    catch (error) { toast(error.message,true); target.disabled = false; }
  }
  if (action === "oral") {
    // 有讲解或 AI 评分时一并保存，结果以你点的按钮为准。
    const id = target.dataset.id, draft = oralDrafts[id], text = (draft?.text || "").trim();
    const detail = {...(text ? {explanation: text} : {}), ...(draft?.judgment ? {marks: draft.judgment.marks, judged_by: draft.judgment.provider} : {})};
    target.disabled = true;
    try { const response = await post("/api/oral",{id,result:target.dataset.result,...detail}); delete oralDrafts[id]; toast(response.message); await load(); }
    catch (error) { toast(error.message,true); target.disabled = false; }
  }
  if (action === "oral-toggle") {
    const draft = oralDrafts[target.dataset.id] ||= {text: ""};
    draft.open = !draft.open; render();
  }
  if (action === "oral-judge") {
    const id = target.dataset.id, draft = oralDrafts[id];
    if ((draft?.text || "").trim().length < 10) { toast("先写几句你的讲解（至少 10 个字）", true); return; }
    draft.busy = true; render();
    try { draft.judgment = await post("/api/oral/judge",{id,explanation:draft.text},undefined,undefined,100000); if (draft.judgment.notice) toast(draft.judgment.notice,true); }
    catch (error) { toast(error.message,true); }
    draft.busy = false; render();
  }
  if (action === "plan-ask") askPlan(target.dataset.question);
  if (action === "weekly-advice") {
    const body = $("[data-weekly-advice]");
    target.disabled = true; body.innerHTML = AlgoAI.waiting("正在根据本周记录写点评，通常 10～40 秒…");
    try { data.weekly_advice = await post("/api/weekly/advice",{},undefined,undefined,100000); if (data.weekly_advice.notice) toast(data.weekly_advice.notice,true); }
    catch (error) { toast(error.message,true); }
    body.innerHTML = AlgoAI.noteBody(data.weekly_advice, esc, WEEKLY_EMPTY); target.disabled = false;
    target.querySelector("span").textContent = data.weekly_advice ? "重新点评" : "生成点评";
  }
  if (action === "skip-recommend") {
    target.disabled = true;
    try { const result = await post("/api/recommend/skip",{id:target.dataset.id}); toast(result.message); await load(); }
    catch (error) { toast(error.message,true); target.disabled = false; }
  }
  if (action === "export-report") {
    const url = URL.createObjectURL(new Blob([data.insights.markdown],{type:"text/markdown;charset=utf-8"}));
    const link = document.createElement("a");
    link.href = url; link.download = `algorithm-weekly-${data.date}.md`; link.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
    toast("周报已导出为 Markdown");
  }
  if (action === "coach" || action === "mock") openCoach(target.dataset.id,action === "mock");
  if (action === "wrap") openWrap();
  if (action === "settings") {
    const form = $("#settings-form"), dialog = $("#settings-dialog");
    form.elements.topic.value = data.plan.current_topic || "";
    form.elements.next_action.value = data.plan.session.next_action || "";
    form.querySelector(".form-error").textContent = "";
    dialog.dataset.revision = data.revision;
    dialog.dataset.requestId = crypto.randomUUID();
    dialog.showModal();
  }
  if (action === "minutes") {
    minutes = Number(target.dataset.minutes);
    try { localStorage.setItem("algo-minutes",String(minutes)); } catch {}
    await load();
  }
  if (action === "remove-queue") {
    target.disabled = true;
    try { const result = await post("/api/queue",{action:"remove",ids:[target.dataset.id]}); toast(result.message); await load(); }
    catch (error) { toast(error.message,true); target.disabled = false; }
  }
  if (action === "export") {
    try {
      const state = await api("/api/export");
      const url = URL.createObjectURL(new Blob([JSON.stringify(state,null,2)],{type:"application/json;charset=utf-8"}));
      const link = document.createElement("a");
      link.href = url; link.download = `algorithm-progress-${data.date}.json`; link.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
      toast("进度文件已导出");
    } catch (error) { toast(error.message,true); }
  }
});
document.addEventListener("submit", async event => {
  const form = event.target;
  event.preventDefault();
  const values = Object.fromEntries(new FormData(form));
  const formId = form.getAttribute("id");
  if (formId === "practice-form") await submitDialog(form,"/api/practice",{...values,minutes:values.minutes ? Number(values.minutes) : null,mock:form.elements.mock.checked});
  if (formId === "wrap-form") await submitDialog(form,"/api/wrap",values);
  if (formId === "settings-form") await submitDialog(form,"/api/session",values);
  if (formId === "plan-ask-form") await askPlan(values.question);
  if (formId === "queue-form") {
    const ids = values.ids.split(/[\s,，、]+/).filter(Boolean);
    if (!ids.length || ids.some(id=>!/^[1-9]\d{0,5}$/.test(id))) { $("#queue-error").textContent = "请输入有效题号，用空格或逗号分隔。"; return; }
    const submit = form.querySelector("button"); submit.disabled = true;
    try { const result = await post("/api/queue",{ids,action:"add"}); toast(result.message); await load(); }
    catch (error) { $("#queue-error").textContent = error.message; submit.disabled = false; }
  }
});
document.addEventListener("input", event => {
  if (event.target.dataset?.oralText) (oralDrafts[event.target.dataset.oralText] ||= {open: true}).text = event.target.value;
  if (event.target.id === "search") { filters.text = event.target.value; $("#problem-rows").innerHTML = tableRows(view === "review"); }
});
document.addEventListener("change", event => {
  const keys = {"topic-filter":"topic","status-filter":"status","due-filter":"due"};
  if (keys[event.target.id]) { filters[keys[event.target.id]] = event.target.value; $("#problem-rows").innerHTML = tableRows(view === "review"); }
  if (event.target.form?.getAttribute("id") === "practice-form" && event.target.name === "id" && data) {
    const row = findProblem(event.target.value.trim());
    if (row) { event.target.form.elements.title.value = row.title === "待填写题名" ? "" : row.title; event.target.form.elements.topic.value = row.topic; }
  }
});
$("#refresh").addEventListener("click",()=>{logs=null;load();});
$("#copy-prompt").addEventListener("click",async()=>{
  const textarea = $("#coach-prompt");
  try { await navigator.clipboard.writeText(textarea.value); toast("已复制，粘贴到当前项目的聊天会话即可"); }
  catch { textarea.focus(); textarea.select(); toast("请按 Ctrl+C 复制选中的学习指令"); }
});
window.addEventListener("hashchange",()=>{ const next = location.hash.slice(1); if(Object.hasOwn(labels,next)) navigate(next); });
// 工作台和模拟面试保留正在编辑的输入，不在切回窗口时整页重绘。
const editing = () => view === "workbench" || view === "mock";
window.addEventListener("focus",()=>{ if(data && !editing() && !document.querySelector("dialog[open]")) load(true); });
document.addEventListener("visibilitychange",()=>{ if(!document.hidden && data && !editing() && !document.querySelector("dialog[open]")) load(true); });
load();
