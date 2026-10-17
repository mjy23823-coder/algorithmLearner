"use strict";

// “我的画像”：学习画像、个性化推荐与 AI 阶段建议。数据来自 /api/dashboard 的 profile 与 plan，页面只负责展示和发起操作。
window.AlgoProfile = (() => {
  const tagClass = {"当前专题": "current", "推进主线": "advance", "弱项巩固": "weak", "补弱专题": "weak"};
  const minuteOptions = [45, 60, 90, 120, 150, 180, 240];

  function tagList(tags, esc) {
    return (tags || []).map(t => `<span class="rec-tag ${tagClass[t] || ""}">${esc(t)}</span>`).join("");
  }
  // 推荐行：今日计划与画像页共用。理由只说明为什么适合你，不写解法要点。
  function recommendRow(c, {esc, icon}, planned = false) {
    const reasons = (c.reasons || c.reason || []).filter(r => r !== "为你推荐");
    const meta = [c.topic, c.difficulty].filter(Boolean).map(esc).join(" · ");
    return `<div class="rec-row"><div class="rec-main"><div class="task-title"><span class="task-id">LC ${esc(c.id)}</span>${esc(c.title)}<small>${meta}</small></div><div class="rec-tags">${planned ? '<span class="rec-tag planned">已排进今日计划</span>' : ""}${tagList(c.tags, esc)}</div><p class="task-reason">${esc(reasons.join(" · "))}</p></div><div class="task-action">${c.workbench !== false ? `<button class="text-button" data-action="workbench" data-id="${esc(c.id)}">去练习${icon("code")}</button>` : ""}${planned ? "" : `<button class="text-button" data-action="add-candidate" data-id="${esc(c.id)}">固定加入待学${icon("plus")}</button>`}<button class="text-button muted-action" data-action="skip-recommend" data-id="${esc(c.id)}">换一题${icon("refresh")}</button></div></div>`;
  }

  function adviceBody(advice, {esc}) {
    return AlgoAI.noteBody(advice, esc, "点“让 AI 分析我的情况”，根据你的画像生成一份阶段建议。连接模型时只发送画像和今日计划，不发送代码；未连接时按固定规则生成。");
  }

  function goalPanel(p, {esc, icon}) {
    const g = p.goal, s = p.settings;
    const hero = g.days_left === null ? `<div class="goal-hero empty"><strong>未设置</strong><span>面试日期</span><button class="text-button" data-profile="settings">去设置 ${icon("arrow")}</button></div>`
      : `<div class="goal-hero${g.urgent ? " urgent" : ""}"><strong>${g.days_left}</strong><span>天后面试 · ${esc(s.target_date)}</span></div>`;
    const steps = Array.from({length: g.total_topics}, (_, i) => {
      const state = i + 1 < g.position ? "done" : i + 1 === g.position ? "current" : "todo";
      return `<i class="${state}"></i>`;
    }).join("");
    return `<section class="panel goal-panel"><div class="panel-header"><div><h2>我的目标</h2><p class="muted">${esc(g.text)}</p></div><button class="icon-button" data-profile="settings" aria-label="设置学习目标" title="设置学习目标">${icon("sliders")}</button></div><div class="panel-body">${hero}
      <dl class="goal-facts"><div><dt>每天计划</dt><dd>${s.daily_minutes} 分钟</dd></div><div><dt>节奏</dt><dd>${esc(p.pace_label)}</dd></div><div><dt>主线专题</dt><dd>${g.position} / ${g.total_topics}</dd></div></dl>
      <div class="mainline" aria-label="主线第 ${g.position} 个专题，共 ${g.total_topics} 个">${steps}</div>
      <p class="mainline-note">当前「${esc(p.current_topic || "未设置")}」${p.next_topic ? ` → 下一站「${esc(p.next_topic)}」` : ""}${g.days_per_topic !== null && g.remaining_topics.length ? ` · 剩余 ${g.remaining_topics.length} 个专题，平均每个约 ${g.days_per_topic} 天` : ""}</p></div></section>`;
  }

  // 单一系列的横向条形：一种颜色，数值写在条的末端，等级用文字说明；悬停或聚焦显示明细。
  function masteryPanel(p, {esc}) {
    if (!p.topics.length) return `<section class="panel"><div class="panel-header"><h2>专题掌握度</h2></div><div class="empty">记录一次练习后，这里会显示各专题的掌握度。</div></section>`;
    const rows = p.topics.map(t => {
      const detail = `${t.problems} 道题 · ${t.graded} 次有结果（独立 ${t.independent} · 提示后 ${t.hinted} · 未完成 ${t.failed}）· 到期 ${t.due} 道${t.idle_days !== null ? ` · ${t.idle_days} 天没练` : ""}`;
      return `<li class="mastery-row" tabindex="0" aria-label="${esc(t.name)}：掌握度 ${t.mastery}%，${esc(t.level)}。${esc(detail)}"><span class="mastery-name">${esc(t.name)}</span><span class="mastery-track"><i class="mastery-fill${t.level === "起步" ? " sparse" : ""}" data-width="${t.mastery}"></i></span><span class="mastery-value">${t.mastery}%</span><span class="mastery-level">${esc(t.level)}</span><span class="mastery-tip" role="tooltip"><b>${esc(t.name)} · ${esc(t.level_note)}</b>${esc(detail)}</span></li>`;
    }).join("");
    return `<section class="panel"><div class="panel-header"><div><h2>专题掌握度</h2><p class="muted">按练习结果计分（独立 1、提示后 0.4、未完成 0），近期权重更高；有结果的练习少于 2 次时显示“起步”。</p></div></div><div class="panel-body"><ul class="mastery-list">${rows}</ul></div></section>`;
  }

  function page(data, ui) {
    const {esc, icon, metric} = ui;
    const p = data.profile, h = p.habits;
    const planned = data.plan.tasks.filter(t => t.source === "recommended" && !t.recorded);
    const plannedRows = planned.map(t => ({...t, ...(data.plan.candidates.find(c => c.id === t.id) || {}), reasons: t.reasons, tags: t.tags}));
    const recs = [...plannedRows.map(r => recommendRow(r, ui, true)), ...data.plan.candidates.map(c => recommendRow(c, ui))];
    const queued = data.next_new.length;
    const heading = `<div class="page-heading"><div><span class="eyebrow">YOUR PERSONAL COACH</span><h1>先读懂你，再给你下一题。</h1><p class="muted">${esc(p.summary.join(""))}</p></div><div class="heading-actions"><button class="button secondary" data-profile="settings">${icon("sliders")}设置学习目标</button><button class="button primary" data-profile="advice">${icon("spark")}让 AI 分析我的情况</button></div></div>`;
    const stats = `<div class="stats-grid">${metric("近 4 周练习", h.practices, "次", `近 14 天练了 ${h.active_days_14} 天`, "book")}${metric("独立完成率", h.independent_rate ?? "—", h.independent_rate === null ? "" : "%", `${h.graded} 次有结果${h.inferred ? ` · ${h.inferred} 次按旧记录推断` : ""}`, "check")}${metric("提示依赖", h.hint_rate ?? "—", h.hint_rate === null ? "" : "%", "提示后完成的占比", "bulb", (h.hint_rate || 0) >= 50 ? "down" : "")}${metric("连续打卡", h.streak, "天", h.timed ? `近 4 周计时 ${h.timed} 次` : "还没有计时记录", "flag")}</div>`;
    const advice = `<section class="panel advice-panel"><div class="panel-header"><div><h2 class="tip-title">${icon("spark")}给你的建议</h2><p class="muted">根据掌握度、反复错因、习惯和目标自动生成。</p></div></div><div class="panel-body"><ol class="focus-list">${(p.focus.length ? p.focus : ["保持当前节奏，按今日计划推进。"]).map(x => `<li>${esc(x)}</li>`).join("")}</ol><div class="advice-card" data-advice-card><div class="advice-head"><span class="advice-orb" aria-hidden="true">${icon("spark")}</span><strong>AI 阶段分析</strong><button class="text-button" data-profile="advice">${data.advice ? "重新分析" : "开始分析"}${icon("arrow")}</button></div><div data-advice-body>${adviceBody(data.advice, ui)}</div></div></div></section>`;
    const recommend = `<section class="panel"><div class="panel-header"><div><h2>为你推荐的新题</h2><p class="muted">综合主线位置、专题掌握度、近期错因、难度匹配、节奏和目标日期挑选。不合适就换一题，7 天内不再推荐。</p></div></div><div class="task-list">${recs.length ? recs.join("") : `<div class="empty"><strong>待学队列已有 ${queued} 道</strong>先按队列练；队列少于 3 道时，会自动按画像补推荐。</div>`}</div></section>`;
    const weak = `<section class="panel"><div class="panel-header"><div><h2>反复出现的错因</h2><p class="muted">近 4 周至少两次，或 7 天内刚出现。涉及这些错因的到期题会优先复习。</p></div><button class="text-button" data-action="graph-error" data-focus="">错因图谱 ${icon("arrow")}</button></div><div class="panel-body">${p.weaknesses.length ? `<ul class="weak-list">${p.weaknesses.slice(0, 3).map(w => `<li><div class="weak-head"><strong>${esc(w.title)}</strong><span class="weak-count">近 4 周 ${w.count} 次</span></div><p>${esc(w.description)}</p><p class="weak-question">${icon("bulb")}<span>写代码前先问：${esc(w.question)}</span></p><div class="weak-foot">${w.problem_ids.slice(0, 5).map(id => `<span class="chip">LC${esc(id)}</span>`).join("")}<button class="text-button" data-action="graph-error" data-focus="errors:${esc(w.id)}">看证据 ${icon("arrow")}</button></div></li>`).join("")}</ul>${p.weaknesses.length > 3 ? `<p class="weak-more">其他近期错因：${p.weaknesses.slice(3).map(w => `<button class="chip" data-action="graph-error" data-focus="errors:${esc(w.id)}">${esc(w.title)}<b>${w.count}</b></button>`).join("")}</p>` : ""}` : '<div class="empty"><strong>最近没有反复出现的错因</strong>保存练习时勾选真实遇到的错因，画像会更准。</div>'}</div></section>`;
    return `${heading}${stats}<div class="content-grid profile-grid"><div class="stack">${advice}${recommend}${weak}</div><div class="stack right-column">${goalPanel(p, ui)}${masteryPanel(p, ui)}</div></div>`;
  }

  function openSettings(data, ui) {
    const {esc, icon, post, toast} = ui;
    const s = data.profile.settings;
    const options = [...new Set([...minuteOptions, s.daily_minutes])].sort((a, b) => a - b);
    const paceNotes = {steady: "新题偏 Easy / 基础 Medium，少碰 Hard，先把每道做独立", normal: "按掌握度自动调整难度", push: "多推 Medium 和高频 Hard，适合离面试近、状态好的时候"};
    const dialog = document.createElement("dialog");
    dialog.className = "profile-settings";
    dialog.innerHTML = `<form method="dialog"><div class="dialog-heading"><div><span class="eyebrow">MY GOAL</span><h2>设置学习目标</h2></div><button type="button" class="icon-button" data-close aria-label="关闭">${icon("close")}</button></div>
      <p class="muted">推荐会按这些设定调整：面试日期越近越偏向大厂高频题；节奏决定新题的难度倾向；每天计划时间决定今日题量。</p>
      <label>目标面试日期<input type="date" name="target_date" value="${esc(s.target_date || "")}" min="${esc(data.date)}"></label><p class="form-hint">不确定可以留空，之后随时改。</p>
      <label>每天计划学习<select name="daily_minutes">${options.map(n => `<option value="${n}" ${n === s.daily_minutes ? "selected" : ""}>${n} 分钟</option>`).join("")}</select></label>
      <fieldset class="pace-options"><legend>节奏</legend>${Object.entries(data.paces).map(([key, label]) => `<label><input type="radio" name="pace" value="${key}" ${s.pace === key ? "checked" : ""}><span><strong>${esc(label)}</strong><small>${esc(paceNotes[key])}</small></span></label>`).join("")}</fieldset>
      <p class="form-error" role="alert"></p>
      <div class="dialog-actions"><button type="button" class="button secondary" data-close>取消</button><button type="submit" class="button primary">保存</button></div></form>`;
    document.body.append(dialog);
    dialog.addEventListener("close", () => dialog.remove(), {once: true});
    dialog.querySelector("form").addEventListener("submit", async event => {
      event.preventDefault();
      event.stopPropagation();
      const form = event.target, submit = form.querySelector("[type=submit]");
      submit.disabled = true;
      try {
        const result = await post("/api/profile", {target_date: form.elements.target_date.value || null, daily_minutes: Number(form.elements.daily_minutes.value), pace: form.elements.pace.value});
        // 今日页的时间档改回跟随画像里的每日计划时间。
        try { localStorage.removeItem("algo-minutes"); } catch {}
        dialog.close(); toast(result.message); await ui.reload();
      } catch (failure) { form.querySelector(".form-error").textContent = failure.message; submit.disabled = false; }
    });
    dialog.showModal();
  }

  function mount(root, data, ui) {
    const abort = new AbortController();
    let disposed = false;
    // CSP 不允许内联 style 属性，条形宽度用 CSSOM 设置。
    root.querySelectorAll(".mastery-fill[data-width]").forEach(el => { el.style.width = `${Math.max(2, Math.min(100, Number(el.dataset.width)))}%`; });
    root.addEventListener("click", async event => {
      const control = event.target.closest("[data-profile]");
      if (!control || control.disabled) return;
      if (control.dataset.profile === "settings") return openSettings(data, ui);
      const buttons = root.querySelectorAll('[data-profile="advice"]');
      const card = root.querySelector("[data-advice-card]");
      buttons.forEach(b => { b.disabled = true; });
      card.classList.add("busy");
      root.querySelector("[data-advice-body]").innerHTML = AlgoAI.waiting("正在根据你的画像分析，通常 10～40 秒…");
      try {
        const result = await ui.post("/api/profile/advice", {}, undefined, undefined, 100000);
        data.advice = result;
        if (result.notice) ui.toast(result.notice, true);
        if (!disposed) root.querySelector("[data-advice-body]").innerHTML = adviceBody(result, ui);
      } catch (failure) {
        if (!disposed) root.querySelector("[data-advice-body]").innerHTML = `${adviceBody(data.advice, ui)}<p class="form-error">${ui.esc(failure.message)}</p>`;
      } finally {
        if (!disposed) { card.classList.remove("busy"); buttons.forEach(b => { b.disabled = false; }); }
      }
    }, {signal: abort.signal});
    return {destroy() { disposed = true; abort.abort(); }};
  }

  return {page, mount, recommendRow, openSettings};
})();
