"use strict";

const LEETCODE_SLUGS = {"1":"two-sum","2":"add-two-numbers","3":"longest-substring-without-repeating-characters","5":"longest-palindromic-substring","11":"container-with-most-water","14":"longest-common-prefix","15":"3sum","16":"3sum-closest","17":"letter-combinations-of-a-phone-number","18":"4sum","19":"remove-nth-node-from-end-of-list","20":"valid-parentheses","21":"merge-two-sorted-lists","22":"generate-parentheses","23":"merge-k-sorted-lists","24":"swap-nodes-in-pairs","26":"remove-duplicates-from-sorted-array","27":"remove-element","33":"search-in-rotated-sorted-array","34":"find-first-and-last-position-of-element-in-sorted-array","35":"search-insert-position","39":"combination-sum","42":"trapping-rain-water","45":"jump-game-ii","46":"permutations","49":"group-anagrams","53":"maximum-subarray","55":"jump-game","62":"unique-paths","70":"climbing-stairs","74":"search-a-2d-matrix","75":"sort-colors","76":"minimum-window-substring","77":"combinations","78":"subsets","79":"word-search","84":"largest-rectangle-in-histogram","92":"reverse-linked-list-ii","94":"binary-tree-inorder-traversal","98":"validate-binary-search-tree","100":"same-tree","101":"symmetric-tree","102":"binary-tree-level-order-traversal","104":"maximum-depth-of-binary-tree","105":"construct-binary-tree-from-preorder-and-inorder-traversal","108":"convert-sorted-array-to-binary-search-tree","110":"balanced-binary-tree","112":"path-sum","114":"flatten-binary-tree-to-linked-list","121":"best-time-to-buy-and-sell-stock","122":"best-time-to-buy-and-sell-stock-ii","124":"binary-tree-maximum-path-sum","125":"valid-palindrome","128":"longest-consecutive-sequence","141":"linked-list-cycle","142":"linked-list-cycle-ii","144":"binary-tree-preorder-traversal","145":"binary-tree-postorder-traversal","150":"evaluate-reverse-polish-notation","151":"reverse-words-in-a-string","153":"find-minimum-in-rotated-sorted-array","155":"min-stack","160":"intersection-of-two-linked-lists","167":"two-sum-ii-input-array-is-sorted","198":"house-robber","199":"binary-tree-right-side-view","200":"number-of-islands","203":"remove-linked-list-elements","206":"reverse-linked-list","207":"course-schedule","209":"minimum-size-subarray-sum","215":"kth-largest-element-in-an-array","217":"contains-duplicate","222":"count-complete-tree-nodes","226":"invert-binary-tree","230":"kth-smallest-element-in-a-bst","232":"implement-queue-using-stacks","234":"palindrome-linked-list","235":"lowest-common-ancestor-of-a-binary-search-tree","236":"lowest-common-ancestor-of-a-binary-tree","239":"sliding-window-maximum","242":"valid-anagram","257":"binary-tree-paths","283":"move-zeroes","295":"find-median-from-data-stream","300":"longest-increasing-subsequence","322":"coin-change","344":"reverse-string","347":"top-k-frequent-elements","383":"ransom-note","404":"sum-of-left-leaves","416":"partition-equal-subset-sum","424":"longest-repeating-character-replacement","437":"path-sum-iii","438":"find-all-anagrams-in-a-string","450":"delete-node-in-a-bst","454":"4sum-ii","455":"assign-cookies","459":"repeated-substring-pattern","501":"find-mode-in-binary-search-tree","513":"find-bottom-left-tree-value","530":"minimum-absolute-difference-in-bst","538":"convert-bst-to-greater-tree","543":"diameter-of-binary-tree","547":"number-of-provinces","560":"subarray-sum-equals-k","567":"permutation-in-string","617":"merge-two-binary-trees","669":"trim-a-binary-search-tree","695":"max-area-of-island","700":"search-in-a-binary-search-tree","701":"insert-into-a-binary-search-tree","704":"binary-search","733":"flood-fill","739":"daily-temperatures","746":"min-cost-climbing-stairs","763":"partition-labels","876":"middle-of-the-linked-list","904":"fruit-into-baskets","977":"squares-of-a-sorted-array","994":"rotting-oranges","1004":"max-consecutive-ones-iii","1047":"remove-all-adjacent-duplicates-in-string","1143":"longest-common-subsequence"};
window.leetcodeUrl = id => `https://leetcode.cn/problems/${LEETCODE_SLUGS[String(id)] || `search-${encodeURIComponent(id)}`}/description/`;

window.AlgoWorkbench = (() => {
  let selected = null;
  try { const value=localStorage.getItem("algorithm-workbench-selected"); if(/^[1-9]\d{0,5}$/.test(value||"")) selected=value; } catch {}
  const CACHE = "algorithm-workbench-draft:";
  const fields = ["code", "idea", "time_complexity", "space_complexity", "boundary", "takeaway"];
  function choose(id) { if (/^[1-9]\d{0,5}$/.test(String(id))) {selected = String(id);try{localStorage.setItem("algorithm-workbench-selected",selected);}catch{}} }
  function cached(id) { try { return JSON.parse(localStorage.getItem(CACHE+id) || "null"); } catch { return null; } }

  const PYTHON_KEYWORDS = new Set("and as assert async await break case class continue def del elif else except finally for from global if import in is lambda match nonlocal not or pass raise return try while with yield True False None".split(" "));
  const PYTHON_BUILTINS = new Set("abs all any bool dict enumerate filter float int len list map max min print range reversed set sorted str sum tuple zip".split(" "));
  const COMPLETIONS = [...new Set([...PYTHON_KEYWORDS, ...PYTHON_BUILTINS, "self", "nums", "target", "left", "right", "window", "current", "result", "answer", "append", "pop"])]
    .sort((a,b) => a.localeCompare(b));

  function highlightPython(source, esc) {
    let out = "", index = 0;
    const add = (className, value) => { out += className ? `<span class="py-${className}">${esc(value)}</span>` : esc(value); };
    while (index < source.length) {
      const char = source[index];
      if (char === "#") {
        const end = source.indexOf("\n", index);
        const value = source.slice(index, end < 0 ? source.length : end);
        add("comment", value); index += value.length; continue;
      }
      if (char === "'" || char === '"') {
        const quote = char, start = index++;
        while (index < source.length) {
          if (source[index] === "\\") { index += 2; continue; }
          if (source[index] === quote) { index++; break; }
          index++;
        }
        add("string", source.slice(start, index)); continue;
      }
      if (/\d/.test(char)) {
        const start = index++;
        while (index < source.length && /[\w.]/.test(source[index])) index++;
        add("number", source.slice(start, index)); continue;
      }
      if (/[A-Za-z_]/.test(char)) {
        const start = index++;
        while (index < source.length && /[A-Za-z0-9_]/.test(source[index])) index++;
        const word = source.slice(start, index);
        add(PYTHON_KEYWORDS.has(word) ? "keyword" : PYTHON_BUILTINS.has(word) ? "builtin" : "name", word); continue;
      }
      add("", char); index++;
    }
    return out || " ";
  }

  function syntaxHint(message) {
    const text = String(message || "").toLowerCase();
    if (text.includes("expected ':'")) return "这类语句通常需要以冒号结束，检查 if、for、while、def 或 class 行末。";
    if (text.includes("unexpected indent")) return "这一行缩进多了一层，统一使用 4 个空格，并和同一代码块对齐。";
    if (text.includes("unindent does not match")) return "这一行的缩进无法回到已有代码块，检查 Tab 和空格是否混用。";
    if (text.includes("unterminated string")) return "字符串没有闭合，检查这一行前后的单引号或双引号。";
    if (text.includes("was never closed") || text.includes("parenthesis")) return "括号没有成对闭合，向前检查最近的括号、方括号或花括号。";
    if (text.includes("invalid syntax")) return "这一行的 Python 结构不完整，先检查本行和上一行的冒号、括号、引号与缩进。";
    return "先定位到报错行，再检查这一行和上一行的语法结构。";
  }

  function figureBars(figure, esc) {
    const values = Array.isArray(figure.value) ? figure.value.map(Number).filter(Number.isFinite) : [];
    if (!values.length) return "";
    const width = 520, height = 190, left = 32, right = 12, top = 16, bottom = 30, base = height - bottom;
    const leftMax = [], rightMax = [];
    let maxLeft = 0, maxRight = 0;
    values.forEach((value, index) => { maxLeft = Math.max(maxLeft, value); leftMax[index] = maxLeft; });
    values.slice().reverse().forEach((value, reverseIndex) => { maxRight = Math.max(maxRight, value); rightMax[values.length - 1 - reverseIndex] = maxRight; });
    const waterLevels = values.map((value, index) => Math.max(0, Math.min(leftMax[index], rightMax[index]) - value));
    const maxLevel = Math.max(1, ...values, ...values.map((value, index) => value + waterLevels[index]));
    const unit = (base - top) / maxLevel, slot = (width - left - right) / values.length, barWidth = Math.max(3, slot - 3);
    const x = index => left + index * slot + (slot - barWidth) / 2;
    const y = value => base - value * unit;
    const bars = values.map((value, index) => {
      const water = figure.water && waterLevels[index] > 0 ? `<rect class="wb-bar-water" x="${x(index).toFixed(1)}" y="${y(value + waterLevels[index]).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${(waterLevels[index] * unit).toFixed(1)}" rx="1"/>` : "";
      const barHeight = Math.max(0, value * unit);
      return `${water}<rect class="wb-bar-solid" x="${x(index).toFixed(1)}" y="${y(value).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barHeight.toFixed(1)}" rx="1"/><text class="wb-visual-index" x="${(x(index) + barWidth / 2).toFixed(1)}" y="${height - 10}" text-anchor="middle">${index}</text>`;
    }).join("");
    const marks = [0, maxLevel].map(value => `<text class="wb-visual-scale" x="${left - 8}" y="${(y(value) + 4).toFixed(1)}" text-anchor="end">${value}</text>`).join("");
    return `<div class="wb-visual wb-visual-bars"><div class="wb-visual-caption">${esc(figure.label || "数组")} · 柱状图${figure.water ? `<span class="wb-visual-legend"><i></i>积水</span>` : ""}</div><svg data-visual="bars" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(figure.label || "数组")}柱状图"><title>${esc(figure.label || "数组")}柱状图${figure.water ? "，蓝色区域表示积水" : ""}</title><path class="wb-visual-axis" d="M${left} ${top}V${base}H${width - right}"/>${marks}${bars}</svg></div>`;
  }

  function figureTree(figure, esc) {
    const values = Array.isArray(figure.value) ? figure.value : [];
    if (!values.some(value => value !== null && value !== undefined)) return "";
    const nodes = [], byIndex = new Map(); let order = 0, maxDepth = 0;
    function visit(index, depth) {
      if (index >= values.length || values[index] === null || values[index] === undefined) return;
      const node = {index, depth, order: order++, value: values[index]};
      nodes.push(node); byIndex.set(index, node); maxDepth = Math.max(maxDepth, depth);
      visit(index * 2 + 1, depth + 1); visit(index * 2 + 2, depth + 1);
    }
    visit(0, 0);
    const width = Math.max(360, Math.min(720, nodes.length * 68)), height = Math.max(110, 58 + maxDepth * 58);
    const step = width / (nodes.length + 1);
    nodes.forEach(node => { node.x = step * (node.order + 1); node.y = 28 + node.depth * 54; });
    const edges = nodes.map(node => {
      const parent = byIndex.get(Math.floor((node.index - 1) / 2));
      return parent ? `<line class="wb-tree-edge" x1="${parent.x.toFixed(1)}" y1="${(parent.y + 16).toFixed(1)}" x2="${node.x.toFixed(1)}" y2="${(node.y - 16).toFixed(1)}"/>` : "";
    }).join("");
    const circles = nodes.map(node => `<g class="wb-tree-node"><circle cx="${node.x.toFixed(1)}" cy="${node.y.toFixed(1)}" r="16"/><text x="${node.x.toFixed(1)}" y="${(node.y + 4).toFixed(1)}" text-anchor="middle">${esc(node.value)}</text></g>`).join("");
    return `<div class="wb-visual wb-visual-tree"><div class="wb-visual-caption">${esc(figure.label || "树")} · 节点关系图</div><svg data-visual="tree" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(figure.label || "二叉树")}节点关系图"><title>${esc(figure.label || "二叉树")}节点关系图</title>${edges}${circles}</svg></div>`;
  }

  function figureList(figure, esc) {
    const values = Array.isArray(figure.value) ? figure.value : [];
    const width = Math.max(250, values.length * 68 + 34), height = 92, center = 42;
    if (!values.length) return `<div class="wb-visual wb-visual-list"><div class="wb-visual-caption">${esc(figure.label || "链表")}</div><div class="wb-list-empty">空链表</div></div>`;
    const nodes = values.map((value, index) => {
      const x = 17 + index * 68;
      const next = index < values.length - 1 ? `<line class="wb-list-arrow" x1="${x + 42}" y1="${center}" x2="${x + 61}" y2="${center}"/><path class="wb-list-arrow-head" d="M${x + 56} ${center - 5}l6 5-6 5"/>` : "";
      return `${next}<rect class="wb-list-node" x="${x}" y="${center - 17}" width="42" height="34" rx="8"/><text x="${x + 21}" y="${center + 4}" text-anchor="middle">${esc(value)}</text>`;
    }).join("");
    return `<div class="wb-visual wb-visual-list"><div class="wb-visual-caption">${esc(figure.label || "链表")} · 指针方向</div><svg data-visual="list" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(figure.label || "链表")}节点和指针方向"><title>${esc(figure.label || "链表")}节点和指针方向</title>${nodes}</svg></div>`;
  }

  function figureMarkup(figure, esc) {
    if (!figure || !figure.kind) return "";
    if (figure.kind === "bars") return figureBars(figure, esc);
    if (figure.kind === "tree") return figureTree(figure, esc);
    if (figure.kind === "list") return figureList(figure, esc);
    return "";
  }
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
    let debugId = null, debugPoll = null, debugPending = false, debugPolling = false, debugGeneration = 0, debugLine = null, debugErrorLine = false;
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
    // 开始写思路或代码时自动计时；10 分钟没有任何操作（输入、点击、滚动、按键）就自动暂停，
    // 只多计 2 分钟，离开座位的时间不算进用时。
    const IDLE_MS = 10 * 60 * 1000, IDLE_GRACE_MS = 2 * 60 * 1000;
    let lastInput = 0;
    function tick() {
      if(since !== null && performance.now() - lastInput > IDLE_MS) {
        elapsed += Math.max(0, (Math.max(since, lastInput + IDLE_GRACE_MS) - since) / 1000);
        since = null; clearInterval(timer); timer = null; dirty = true; stamp++;
        updateClock(); cache(); status("10 分钟没有操作，计时已自动暂停；继续输入会接着计时");
        return;
      }
      updateClock(); dirty = true; stamp++; cache();
    }
    function startTimer() {
      if(since !== null || !info) return;
      lastInput = performance.now(); since = lastInput;
      updateClock(); timer = setInterval(tick, 1000);
    }
    function parseBreakpoints(value) {
      const input=value.trim();
      if(input && !/^[0-9\s,，]+$/.test(input)) throw new Error("断点只支持逗号分隔的正整数行号。");
      const lines=input ? input.split(/[\s,，]+/).filter(Boolean).map(Number) : [];
      if(lines.some(n=>!Number.isSafeInteger(n) || n<1 || n>100000)) throw new Error("断点行号应在 1～100000 之间。");
      if(new Set(lines).size>100) throw new Error("最多设置 100 个断点。");
      return new Set(lines);
    }
    function syncBreakpointMarks() {
      const field=root.querySelector("#wb-breakpoints");
      if(!field) return;
      let lines;
      try { lines=parseBreakpoints(field.value); } catch { lines=new Set(); }
      root.querySelectorAll(".wb-gutter-line").forEach(item=>{
        const line=Number(item.dataset.line), active=lines.has(line);
        item.classList.toggle("has-breakpoint",active);
        item.setAttribute("aria-pressed",String(active));
        item.setAttribute("aria-label",`第 ${line} 行，${active?"取消":"设置"}断点`);
      });
    }
    function toggleBreakpoint(line) {
      const field=root.querySelector("#wb-breakpoints");
      if(!field) return;
      try {
        const lines=parseBreakpoints(field.value);
        if(lines.has(line)) lines.delete(line);
        else {
          if(lines.size>=100) throw new Error("最多设置 100 个断点。");
          lines.add(line);
        }
        field.value=[...lines].sort((a,b)=>a-b).join(", ");
        syncBreakpointMarks();
        message("");
      } catch(error) { message(error.message); }
    }
    function updateEditor() {
      const code=get("code");
      root.querySelector("#wb-lines").innerHTML=code.value.split("\n").map((_,i)=>`<span class="wb-gutter-line${debugLine===i+1?(debugErrorLine?" is-error":" is-current"):""}" role="button" tabindex="0" data-line="${i+1}">${i+1}</span>`).join("");
      syncBreakpointMarks();
      root.querySelector("#wb-highlight").innerHTML=highlightPython(code.value,esc);
      syncDebugLine();
    }
    function syncDebugLine() {
      const marker=root.querySelector("#wb-execution-line"), code=get("code");
      if(!marker || !code) return;
      marker.hidden=debugLine===null;
      marker.classList.toggle("is-error",debugErrorLine);
      if(debugLine!==null) marker.style.top=`${17+(debugLine-1)*23-code.scrollTop}px`;
    }
    function setDebugLine(value, error=false) {
      const code=get("code");
      if(!code) {debugLine=null;debugErrorLine=false;return;}
      const line=Number(value);
      debugLine=Number.isInteger(line) && line>=1 && line<=code.value.split("\n").length ? line : null;
      debugErrorLine=debugLine!==null && error;
      root.querySelectorAll(".wb-gutter-line").forEach((item,i)=>{
        item.classList.toggle("is-current",i+1===debugLine && !debugErrorLine);
        item.classList.toggle("is-error",i+1===debugLine && debugErrorLine);
      });
      if(debugLine!==null) {
        const top=17+(debugLine-1)*23;
        if(top<code.scrollTop || top+23>code.scrollTop+code.clientHeight)
          code.scrollTop=Math.max(0,top-code.clientHeight/2);
        root.querySelector("#wb-lines").scrollTop=code.scrollTop;
        root.querySelector("#wb-highlight").scrollTop=code.scrollTop;
      }
      syncDebugLine();
    }
    let completionItems = [], completionIndex = 0;
    function hideCompletions() {
      completionItems=[]; completionIndex=0;
      const popup=root.querySelector("#wb-completions");
      popup.hidden=true; popup.innerHTML="";
    }
    function codePrefix() {
      const code=get("code"), before=code.value.slice(0,code.selectionStart);
      const match=before.match(/[A-Za-z_][A-Za-z0-9_]*$/);
      return match ? {before, prefix:match[0], start:code.selectionStart-match[0].length} : {before, prefix:"", start:code.selectionStart};
    }
    function renderCompletions(force=false) {
      const code=get("code"), popup=root.querySelector("#wb-completions"), {prefix}=codePrefix();
      if (!force && prefix.length < 2) { hideCompletions(); return; }
      completionItems=COMPLETIONS.filter(word=>word.startsWith(prefix) && word!==prefix).slice(0,8);
      if (!completionItems.length) { hideCompletions(); return; }
      completionIndex=Math.min(completionIndex,completionItems.length-1);
      popup.innerHTML=completionItems.map((word,index)=>`<button type="button" role="option" data-completion="${esc(word)}" aria-selected="${index===completionIndex}"><span>${esc(word)}</span><small>${PYTHON_KEYWORDS.has(word)?"关键字":PYTHON_BUILTINS.has(word)?"内置函数":"变量/方法"}</small></button>`).join("");
      const before=code.value.slice(0,code.selectionStart), line=before.split("\n").length, column=before.length-(before.lastIndexOf("\n")+1);
      popup.style.left=`${Math.min(Math.max(12,column*7.7),Math.max(12,code.clientWidth-190))}px`;
      popup.style.top=`${Math.max(8,(line-1)*23+37-code.scrollTop)}px`;
      popup.hidden=false;
    }
    function acceptCompletion(index=completionIndex) {
      if (!completionItems.length) return false;
      const code=get("code"), {start}=codePrefix(), word=completionItems[index];
      code.setRangeText(word,start,code.selectionStart,"end");
      hideCompletions(); updateEditor(); edited();
      return true;
    }
    function currentRun() {
      if(!lastRun || !info || get("code").value !== runCode) return false;
      try { return JSON.stringify(JSON.parse(get("extra_cases").value || "[]")) === runCases; } catch { return false; }
    }
    function updateActions() {
      if(!info || !get("code")) return;
      root.querySelector('[data-wb="run"]').disabled=busy || conflict || !info.exercise;
      for (const control of root.querySelectorAll('[data-wb-debug]')) {
        const action = control.dataset.wbDebug;
        control.disabled = debugPending || (action === "start" ? busy || conflict || !info.exercise || !!debugId :
          action === "stop" ? !debugId : !debugId || root.querySelector("#wb-debug-state")?.dataset.paused !== "true");
      }
      root.querySelector('[data-wb="complete"]').disabled=busy || conflict || !currentRun();
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
        const {onDelta, ...request}=extra;
        const payload={id,...read(),draft_revision:revision,...request};
        const streaming=onDelta && ["openai","anthropic"].includes(info.coach.provider);
        const response=streaming
          ? await ui.streamPost("/api/workbench/coach/stream",payload,undefined,undefined,onDelta,100000)
          : await post("/api/workbench/coach",payload,undefined,undefined,100000);
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
    function syntaxErrorMarkup(detail) {
      if(!detail) return "";
      const line=Number(detail.line)||0, column=Math.max(1,Number(detail.column)||1);
      const source=detail.text || (get("code").value.split("\n")[line-1] || "");
      const caret=" ".repeat(Math.max(0,column-1))+"^";
      return `<section class="wb-error-detail"><div class="wb-error-head"><strong>${esc(detail.name || "SyntaxError")}</strong><span>${line ? `第 ${line} 行${detail.column ? ` · 第 ${detail.column} 列` : ""}` : "语法位置未知"}</span></div><p class="wb-error-message">${esc(detail.message || "语法结构不完整")}</p>${line ? `<pre class="wb-error-source"><span class="wb-error-line">${line}</span><code>${esc(source || " ")}</code><span class="wb-error-caret">${esc(caret)}</span></pre>` : ""}<p class="wb-error-hint"><b>怎么修：</b>${esc(syntaxHint(detail.message))}</p>${line ? `<button type="button" class="button secondary wb-error-jump" data-wb="goto-line" data-line="${line}">跳到第 ${line} 行</button>` : ""}</section>`;
    }
    function runErrorMarkup(result) {
      return result.error_detail?.kind === "syntax" ? syntaxErrorMarkup(result.error_detail) : (result.error ? `<p class="wb-runtime-error">${esc(result.error)}</p>` : "");
    }
    function showRun(run) {
      const result=run.result;
      const meta=root.querySelector("#wb-results-meta"); if(meta) meta.textContent=`${result.passed_count} / ${result.total} 通过 · ${result.elapsed_ms} ms`;
      const firstFail=result.cases.findIndex(c=>!c.passed);
      const activeIndex=firstFail >= 0 ? firstFail : 0;
      const tabs=result.cases.map((c,index)=>`<button type="button" class="wb-case-tab${index===activeIndex?" active":""}" data-wb-case="${index}"><span class="wb-case-status ${c.passed?"ok":"fail"}">${c.passed?"✓":"!"}</span>Case ${index+1}</button>`).join("");
      const panels=result.cases.map((c,index)=>`<section class="wb-case-panel${index===activeIndex?" active":""}" data-wb-case-panel="${index}"><h4>${esc(c.name)} <span class="${c.passed?"pass":"fail"}">${c.passed?"通过":"未通过"}</span></h4><dl><dt>输入参数</dt><dd><pre>${esc(JSON.stringify(c.args))}</pre></dd><dt>期望结果</dt><dd><pre>${esc(JSON.stringify(c.expected))}</pre></dd><dt>${c.error?"错误":"实际结果"}</dt><dd><pre>${esc(c.error || JSON.stringify(c.actual))}</pre></dd></dl></section>`).join("");
      root.querySelector("#wb-test-results").innerHTML=`<div class="wb-test-summary ${result.passed?"pass":"fail"}">${icon(result.passed?"check":"info")}<strong>${result.passed?"本地用例全部通过":"还需要调整"}</strong><span>${result.passed_count} / ${result.total} · ${result.elapsed_ms} ms</span></div>${runErrorMarkup(result)}<div class="wb-case-workbench"><div class="wb-case-tabs" role="tablist" aria-label="测试用例">${tabs}</div><div class="wb-case-panels">${panels}</div></div>${result.stdout?`<details class="wb-test-case"><summary>调试输出</summary><pre>${esc(result.stdout)}</pre></details>`:""}<p class="form-hint">以上只证明这 ${result.total} 组本地用例的结果；平台提交、复杂度和思路表达仍需单独确认。</p>`;
      if(!result.passed) root.querySelector("#wb-result").value="failed";
      else if(hints.length || coachHints) root.querySelector("#wb-result").value="hinted";
      updateActions();
    }

    function debugState(text, paused=false, state=paused?"paused":"idle") {
      const label=root.querySelector("#wb-debug-state");
      if(!label || disposed) return;
      label.textContent=text;
      label.dataset.paused=String(paused);
      label.dataset.state=state;
      if(!paused) setDebugLine(null);
      updateActions();
    }
    function finishDebug() {
      debugId=null;
      clearInterval(debugPoll);debugPoll=null;
      updateActions();
    }
    function debugEvents(events) {
      for(const event of events || []) {
        if(event.event === "paused") {
          debugState(`停在第 ${event.line} 行 · 首组本地用例`,true);
          setDebugLine(event.line);
          if(event.case) showDebugCase(event.case);
          root.querySelector("#wb-debug-locals").textContent=JSON.stringify(event.locals || {},null,2);
        } else if(event.event === "done") {
          debugState(event.stopped ? "调试已停止。" : "调试执行结束；结果仅供定位问题，不计为完成。",false,event.stopped?"stopped":"completed");
          if(!event.stopped) root.querySelector("#wb-debug-locals").textContent=JSON.stringify({实际结果:event.actual,期望结果:event.expected},null,2);
          finishDebug();
        } else if(event.event === "error") {
          const timedOut=String(event.error || "").includes("超时");
          debugState(event.error || "调试进程已结束。",false,timedOut?"timeout":"error");
          if(event.line) setDebugLine(event.line,true);
          finishDebug();
        }
      }
    }
    function showDebugCase(testCase) {
      const display=root.querySelector("#wb-debug-case");
      if(display) display.textContent=JSON.stringify({输入参数:testCase.args,期望结果:testCase.expected},null,2);
    }
    function stopDebug(unloading=false) {
      setDebugLine(null);
      ++debugGeneration;
      clearInterval(debugPoll);debugPoll=null;
      const id=debugId;debugId=null;
      if(id) {
        if(unloading) ui.debugStopOnUnload(id);
        else post("/api/workbench/debug/command",{debug_id:id,command:"stop"}).catch(()=>{});
      }
      if(!disposed) updateActions();
    }
    async function pollDebug() {
      if(!debugId || debugPending || debugPolling || disposed) return;
      const id=debugId;debugPolling=true;
      try {
        const response=await api(`/api/workbench/debug?debug_id=${encodeURIComponent(id)}`);
        if(id===debugId && !disposed) debugEvents(response.events);
      } catch(error) {
        if(id===debugId && !disposed) {stopDebug();debugState(error.message,false,"error");}
      } finally {debugPolling=false;}
    }
    async function debugAction(action) {
      if(action === "stop") {stopDebug();debugState("调试已停止。",false,"stopped");return;}
      debugPending=true;updateActions();
      try {
        if(action === "start") {
          const breakpoints=[...parseBreakpoints(root.querySelector("#wb-breakpoints").value)];
          const generation=++debugGeneration;
          root.querySelector("#wb-debug-locals").textContent="";
          debugState("调试启动中…",false,"starting");
          const response=await post("/api/workbench/debug/start",{id,code:get("code").value,breakpoints});
          if(disposed || generation!==debugGeneration) {
            post("/api/workbench/debug/command",{debug_id:response.debug_id,command:"stop"}).catch(()=>{});
            return;
          }
          debugId=response.debug_id;
          debugState("正在运行首组本地用例…",false,"running");debugEvents(response.events);
          if(debugId) debugPoll=setInterval(pollDebug,250);
        } else {
          debugState("正在运行首组本地用例…",false,"running");
          const response=await post("/api/workbench/debug/command",{debug_id:debugId,command:action});
          if(!disposed && debugId) debugEvents(response.events);
        }
      } catch(error) {if(!disposed) {stopDebug();debugState(error.message,false,"error");}}
      finally {debugPending=false;if(!disposed) updateActions();}
    }

    function formMarkup() {
      const exercise=info.exercise, row=info.problem, statement=info.statement || {};
      const statusText={learned:"已掌握",learning:"待间隔验证",needs_review:"需要巩固",needs_calibration:"历史状态待校准",new:"待学习"}[row.status] || row.status;
      const step=(n,eyebrow,title,extra="")=>`<div class="wb-card-head"><span class="wb-step" aria-hidden="true">${n}</span><div class="wb-card-title"><span class="eyebrow">${eyebrow}</span><h2>${title}</h2>${extra}</div>`;
      const statementText=statement.text || exercise?.description || "这道题尚未配置题面，可以先让聊天教练说明题意。";
      const constraints=statement.constraints || [];
      const paramNotes=statement.param_notes || [];
      const examples=statement.examples || [];
      const statementBody=`<div class="wb-statement" data-problem-statement>
          <div class="wb-statement-lead"><span class="wb-statement-label">题目要求</span><p>${esc(statementText)}</p></div>
          <div class="wb-statement-grid">
            ${constraints.length ? `<section class="wb-statement-block"><h3>约束条件</h3><ul>${constraints.map(item=>`<li>${esc(item)}</li>`).join("")}</ul></section>` : ""}
            ${paramNotes.length ? `<section class="wb-statement-block"><h3>参数说明</h3><ul>${paramNotes.map(item=>`<li>${esc(item)}</li>`).join("")}</ul></section>` : ""}
            ${examples.length ? `<section class="wb-statement-block wb-examples"><h3>示例</h3>${examples.map((example,index)=>`<article class="wb-example ${(example.figures || []).length && index === 0 ? "wb-example-featured" : ""}"><div class="wb-example-title">示例 ${index+1}</div>${(example.figures || []).length ? `<div class="wb-example-visuals">${example.figures.map(figure=>figureMarkup(figure,esc)).join("")}</div>` : ""}<dl><dt>输入</dt><dd><code>${esc(example.input)}</code></dd><dt>输出</dt><dd><code>${esc(example.output)}</code></dd>${example.note ? `<dd class="wb-example-note">${esc(example.note)}</dd>` : ""}</dl></article>`).join("")}</section>` : ""}
          </div>
          ${statement.url ? `<a class="wb-statement-link" href="${esc(statement.url)}" target="_blank" rel="noreferrer">${icon("arrow")}查看力扣原题（完整描述以原题为准）</a>` : ""}
        </div>`;
      // 主栏按“理清问题 → 写代码验证 → 复盘”自上而下；教练固定在右栏，窄屏时排到代码之后。
      return `<div id="wb-conflict" class="notice" hidden><div><p>本机有尚未同步的草稿，磁盘版本也已变化。请选择保留哪一份。</p><div class="wb-conflict-actions"><button class="button secondary" data-wb="use-local">保留本机草稿</button><button class="button secondary" data-wb="use-remote">使用磁盘草稿</button></div></div></div><p id="wb-error" class="wb-error" role="alert"></p>
      <div class="wb-studio">
        <section class="panel wb-problem">${step(1,"理清问题",`LC${esc(id)} · ${esc(row.title)}`,`<div class="wb-header-actions"><a class="wb-lc-link" href="${leetcodeUrl(id)}" target="_blank" rel="noopener noreferrer">力扣原题 ↗</a><p class="wb-meta"><span>${esc(row.topic)}</span><span class="wb-status status-${esc(row.status)}">${esc(statusText)}</span>${info.patterns.map(p=>`<span class="badge neutral">${esc(p.title)}</span>`).join("")}</p></div>`)}</div>
          <div class="panel-body">
            ${statementBody}
            ${exercise?`<p class="wb-contract">方法 <code>Solution.${esc(exercise.method)}(${esc(exercise.params.join(", "))})</code><span>输入参数按顺序填写，已提供 ListNode、TreeNode、List 和 Optional。</span></p><details class="wb-cases"><summary>${icon("layers")}本地基础用例 · ${exercise.cases.length} 组</summary><div class="wb-default-cases">${exercise.cases.map(c=>`<details><summary>${esc(c.name)}</summary><pre>${esc(JSON.stringify({args:c.args,expected:c.expected},null,2))}</pre></details>`).join("")}</div></details>`:""}
          </div>
        </section>
        <section class="panel wb-code-panel">${step(2,"写代码并验证","你的 Python 实现")}<div class="wb-card-tags"><span class="subtle-pill">Python 3</span><span id="wb-run-state" class="subtle-pill">尚未运行</span></div></div>
          <div class="wb-code-editor"><pre id="wb-lines" aria-label="编辑器行号及断点">1</pre><div class="wb-code-pane"><div id="wb-execution-line" aria-hidden="true" hidden></div><pre id="wb-highlight" aria-hidden="true"></pre><textarea data-wb-field="code" aria-label="Python 代码" spellcheck="false" autocapitalize="off" autocomplete="off" wrap="off"></textarea><div id="wb-completions" class="wb-completions" role="listbox" aria-label="代码补全" hidden></div></div></div>
          <div class="wb-code-actions"><span>Tab 缩进 · Ctrl+Enter 运行 · 自动保存</span><div><button class="button primary" data-wb="run">${icon("play")}运行本地用例</button></div></div>
          <details class="wb-debug"><summary>逐步调试 · 首组本地用例</summary><div class="wb-debug-body"><p class="form-hint">点击行号设置断点，也可填写逗号分隔的行号；没有断点时从首行暂停。调试不会保存完成记录。</p><label>断点行号（可留空）<input id="wb-breakpoints" inputmode="numeric" placeholder="例如 3, 8" aria-label="调试断点行号"></label><div class="wb-debug-actions"><button type="button" class="button secondary" data-wb-debug="start">开始调试</button><button type="button" class="button secondary" data-wb-debug="step" disabled>单步</button><button type="button" class="button secondary" data-wb-debug="continue" disabled>继续</button><button type="button" class="button secondary" data-wb-debug="stop" disabled>停止</button></div><p id="wb-debug-state" role="status" aria-live="polite" data-state="idle">尚未开始调试。</p><div class="wb-debug-snapshot"><span>本地用例输入</span><pre id="wb-debug-case" aria-label="调试用例输入"></pre><span>当前局部变量 / 结果</span><pre id="wb-debug-locals" aria-label="调试局部变量"></pre></div></div></details>
          <div class="wb-results"><div class="wb-results-head"><strong>测试结果</strong><span id="wb-results-meta">运行代码后查看每个 Case 的详细结果</span></div><p id="wb-stale" class="wb-stale" hidden>代码或用例已修改，需要重新运行后才能记录结果。</p><div id="wb-test-results"><div class="empty">完成实现后，运行基础用例与自己补充的边界。</div></div><details class="wb-extra"><summary>追加自定义用例（JSON 数组）</summary><p class="form-hint">格式：[{"args": [按参数顺序填写], "expected": 期望结果}]。基础用例始终会运行。</p><textarea data-wb-field="extra_cases" rows="6" aria-label="自定义测试用例" spellcheck="false">[]</textarea></details></div>
        </section>
        <section class="panel wb-approach">${step("A","作答前检查","先说思路，再写代码",`<p class="wb-meta"><span>先写下你的判断，再开始修改实现。</span></p>`)}</div>
          <div class="panel-body"><div class="wb-think"><label>我的核心思路<textarea data-wb-field="idea" rows="3" maxlength="2000" placeholder="先用自己的话解释：题型、关键变量各代表什么。"></textarea></label><label>一个边界情况<textarea data-wb-field="boundary" rows="3" maxlength="2000" placeholder="最小输入、重复值、空节点或指针相遇时会怎样？"></textarea></label></div><div class="wb-hintbar"><div class="wb-hintbar-row"><span class="wb-hintbar-title">${icon("bulb")}卡住了？逐层提示</span><div class="wb-hint-buttons">${[1,2,3].map(n=>`<button class="button secondary" data-wb="hint" data-level="${n}">提示 ${n}</button>`).join("")}</div><button class="text-button" data-action="coach" data-id="${esc(id)}">聊天教练 ${icon("arrow")}</button></div><p id="wb-hint-note" class="form-hint"></p><div id="wb-hints"></div></div></div>
        </section>
        <aside class="wb-coach-col"><section class="panel coach-panel" id="wb-coach"></section></aside>
        <section class="panel wb-reflect">${step(3,"复盘与下次复习","把这次练习留下来")}</div>
          <div class="panel-body"><div class="form-row"><label>时间复杂度<input data-wb-field="time_complexity" maxlength="2000" placeholder="例如 O(n)"></label><label>额外空间复杂度<input data-wb-field="space_complexity" maxlength="2000" placeholder="例如 O(1)"></label></div><fieldset class="wb-error-tags"><legend>本次遇到的错因（可多选，没有就不选）</legend>${info.errors.map(tag=>`<label><input type="checkbox" name="wb-error-tag" value="${esc(tag.id)}">${esc(tag.title)}</label>`).join("")}</fieldset><label>一句话复盘<textarea data-wb-field="takeaway" rows="3" maxlength="2000" placeholder="关键规律、修改了什么、下次怎样避免同样的问题。"></textarea></label><div class="wb-finish"><label>真实完成情况<select id="wb-result"><option value="">请选择</option><option value="independent">独立完成</option><option value="hinted">提示后完成</option><option value="failed">暂未完成</option></select></label><button class="button primary" data-wb="complete" disabled>${icon("check")}保存结果并更新复习</button><button class="text-button" data-wb="record">在力扣完成后直接记录</button></div><p class="form-hint">仅运行用例不会增加完成次数。保存结果后更新进度、复习排期和错因关系。</p></div>
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
        if(info.exercise?.cases?.length) showDebugCase(info.exercise.cases[0]);
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
        on(get("code"),"scroll",()=>{root.querySelector("#wb-lines").scrollTop=get("code").scrollTop;const highlight=root.querySelector("#wb-highlight");highlight.scrollTop=get("code").scrollTop;highlight.scrollLeft=get("code").scrollLeft;syncDebugLine();renderCompletions();});
        on(get("code"),"keydown",event=>{
          if(event.key==="Tab") {event.preventDefault(); if(!acceptCompletion()){const el=get("code"); el.setRangeText("    ",el.selectionStart,el.selectionEnd,"end"); updateEditor(); edited();} return;}
          if((event.ctrlKey||event.metaKey)&&event.code==="Space") {event.preventDefault(); renderCompletions(true); return;}
          if(!root.querySelector("#wb-completions").hidden && ["ArrowDown","ArrowUp","Enter","Escape"].includes(event.key)) {
            if(event.key==="Escape"){hideCompletions();return;}
            if(event.key==="ArrowDown"){event.preventDefault();completionIndex=(completionIndex+1)%completionItems.length;renderCompletions(true);return;}
            if(event.key==="ArrowUp"){event.preventDefault();completionIndex=(completionIndex+completionItems.length-1)%completionItems.length;renderCompletions(true);return;}
            if(event.key==="Enter" && acceptCompletion()){event.preventDefault();return;}
          }
          if((event.ctrlKey||event.metaKey)&&event.key==="Enter") {event.preventDefault(); root.querySelector('[data-wb="run"]').click();}
          if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="s") {event.preventDefault(); save().catch(e=>message(e.message));}
        });
        if(dirty && !conflict) debounce=setTimeout(()=>save().catch(e=>message(e.message)),900);
      } catch(error) {if(!disposed) content.innerHTML=`<div class="empty">${esc(error.message)}</div>`;}
    }

    // 滚动事件不冒泡，用捕获阶段监听页面内各区域，另外监听整页滚动。
    const active=()=>{lastInput=performance.now();};
    for(const type of ["pointerdown","keydown","wheel","scroll"]) root.addEventListener(type,active,{capture:true,passive:true,signal:abort.signal});
    on(window,"scroll",active);
    on(root,"input",event=>{
      if(event.target.id==="wb-breakpoints") {
        syncBreakpointMarks();
        try {
          parseBreakpoints(event.target.value);
          if(/^(断点|最多设置)/.test(root.querySelector("#wb-error").textContent)) message("");
        } catch { /* 保留当前手填内容，启动时再显示校验错误。 */ }
        return;
      }
      if(!event.target.matches("[data-wb-field], [name=wb-error-tag]")) return;
      if(event.target===get("code")) {
        if(debugId || debugPending) {stopDebug();debugState("代码已修改，本次调试已停止。",false,"stopped");}
        else if(debugErrorLine) {setDebugLine(null);debugState("代码已修改，旧错误位置已清除。",false,"idle");}
        updateEditor();renderCompletions();
      }
      if(event.target.matches('[data-wb-field="idea"], [data-wb-field="boundary"], [data-wb-field="code"]') && !savedResult && !conflict) {
        lastInput=performance.now();
        if(since===null) startTimer();
      }
      edited();
    });
    on(root.querySelector("#wb-problem"),"change",async event=>{
      const next=event.target.value;
      if(busy){event.target.value=id;return;}
      pauseTimer();
      try {await save(); choose(next); ui.onSelect();} catch(error){event.target.value=id;message(error.message);}
    });
    on(root,"click",async event=>{
      const gutter=event.target.closest(".wb-gutter-line");
      if(gutter && root.contains(gutter)) { toggleBreakpoint(Number(gutter.dataset.line)); return; }
      const completion=event.target.closest("[data-completion]");
      if(completion){acceptCompletion(completionItems.indexOf(completion.dataset.completion));return;}
      const caseTab=event.target.closest("[data-wb-case]");
      if(caseTab){
        const index=caseTab.dataset.wbCase;
        root.querySelectorAll("[data-wb-case]").forEach(tab=>tab.classList.toggle("active",tab===caseTab));
        root.querySelectorAll("[data-wb-case-panel]").forEach(panel=>panel.classList.toggle("active",panel.dataset.wbCasePanel===index));
        return;
      }
      const debugControl=event.target.closest("[data-wb-debug]");
      if(debugControl) {if(!debugControl.disabled && info) debugAction(debugControl.dataset.wbDebug);return;}
      const control=event.target.closest("[data-wb]");
      if(!control || control.disabled || !info) return;
      const action=control.dataset.wb;
      if(action==="goto-line") {
        const line=Math.max(1,Number(control.dataset.line)||1), code=get("code"), lines=code.value.split("\n");
        const start=lines.slice(0,line-1).reduce((sum,item)=>sum+item.length+1,0);
        code.focus(); code.setSelectionRange(start,Math.min(code.value.length,start+lines[line-1].length));
        code.scrollTop=Math.max(0,(line-1)*23-100); hideCompletions(); return;
      }
      if(action==="record") {
        ui.onRecord?.(id);
        return;
      }
      if(action==="timer") {
        if(since!==null) {pauseTimer();save().catch(e=>message(e.message));}
        else startTimer();
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
    on(root,"keydown",event=>{
      const gutter=event.target.closest(".wb-gutter-line");
      if(gutter && (event.key==="Enter" || event.key===" ")) {
        event.preventDefault();toggleBreakpoint(Number(gutter.dataset.line));
      }
    });
    on(window,"pagehide",()=>{stopDebug(true);pauseTimer();cache();});
    initialize();
    return {
      async beforeLeave(){ if(busy || coachPanel?.busy()){message("请等待当前操作完成。");return false;} pauseTimer();try{await save();return true;}catch(error){message(error.message);return false;} },
      destroy(){stopDebug();pauseTimer();cache();disposed=true;coachPanel?.destroy();abort.abort();clearTimeout(debounce);if(timer)clearInterval(timer);},
    };
  }
  return {page,mount,choose};
})();
