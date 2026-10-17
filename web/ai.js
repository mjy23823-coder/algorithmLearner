"use strict";

// AI 点评卡的公共展示：画像阶段分析、周报点评、口述判断共用。服务端返回的结果都带 provider / label / model / at。
window.AlgoAI = (() => {
  const markLabels = {ok: "讲到了", partial: "不完整", missing: "没讲到"};

  function when(at) {
    const time = at ? new Date(at) : null;
    return time && !isNaN(time) ? time.toLocaleString([], {month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit"}) : "";
  }
  function meta(note, esc) {
    return [note.label || "离线", note.model, when(note.at)].filter(Boolean).map(esc).join(" · ");
  }
  function noteBody(note, esc, empty) {
    if (!note) return `<p class="advice-empty">${esc(empty)}</p>`;
    return `<p class="advice-text">${esc(note.text)}</p><p class="advice-meta">${meta(note, esc)}</p>`;
  }
  const waiting = text => `<p class="advice-empty"><span class="coach-dots"><i></i><i></i><i></i></span>${text}</p>`;

  // 口述判断：四项评分、点评和建议结果。建议结果由服务端按固定规则从四项评分换算。
  function judgment(j, esc, icon) {
    const items = Object.entries(j.items).map(([key, title]) => `<li class="mark ${esc(j.marks[key])}">${icon(j.marks[key] === "ok" ? "check" : j.marks[key] === "partial" ? "info" : "close")}<span>${esc(title)}</span><b>${esc(markLabels[j.marks[key]])}</b></li>`).join("");
    return `<div class="oral-judgment"><ul class="mark-list">${items}</ul>${j.feedback ? `<p class="advice-text">${esc(j.feedback)}</p>` : ""}<p class="advice-meta">${meta(j, esc)}</p>
      <div class="oral-suggest"><span>建议记：<b class="result-pill ${esc(j.result)}">${esc(j.result_label)}</b></span><button class="button primary" data-action="oral" data-id="${esc(j.id)}" data-result="${esc(j.result)}">按建议记录</button></div></div>`;
  }

  return {noteBody, meta, waiting, judgment, when};
})();
