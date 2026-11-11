"use strict";

// 原生 SVG 图谱。学习状态来自现有接口；视角、折叠和拖动位置只存浏览器。
window.AlgoGraph = (() => {
  const STORAGE = "algorithm-graph-v1";
  const ROOT = "goal";
  const LIMIT = 6;
  const statuses = {
    learned: "已掌握", learning: "待验证", review: "待复习",
    overdue: "已逾期", calibration: "待校准", new: "待学习",
  };
  let memory;
  let motionClock = 0;
  // 会话内保留绘制位置；持久化文件仍只保存用户布置的平衡位置。
  const visualMemory = new Map();

  function preferences() {
    if (memory) return memory;
    memory = {selected: ROOT, query: "", topic: "", status: "all", motion: true, relation: "topics", layoutRelation: "topics", collapsed: new Set(),
      expanded: new Set(), positions: new Map(), camera: null, size: null};
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE) || "null");
      if (saved && typeof saved === "object") {
        for (const key of ["selected", "query", "topic"]) {
          if (typeof saved[key] === "string") memory[key] = saved[key].slice(0, 200);
        }
        if (saved.status === "all" || Object.hasOwn(statuses, saved.status)) memory.status = saved.status;
        if (typeof saved.motion === "boolean") memory.motion = saved.motion;
        if (["topics","patterns","errors"].includes(saved.relation)) memory.relation = saved.relation;
        if (["topics","patterns","errors"].includes(saved.layoutRelation)) memory.layoutRelation = saved.layoutRelation;
        for (const key of ["collapsed", "expanded"]) {
          if (Array.isArray(saved[key])) memory[key] = new Set(saved[key].filter(v => typeof v === "string").slice(0, 500));
        }
        for (const point of Array.isArray(saved.positions) ? saved.positions.slice(0, 3000) : []) {
          if (Array.isArray(point) && typeof point[0] === "string" && point[1] &&
              Number.isFinite(point[1].x) && Number.isFinite(point[1].y) &&
              Math.abs(point[1].x) < 100000 && Math.abs(point[1].y) < 100000) {
            memory.positions.set(point[0], {x: point[1].x, y: point[1].y});
          }
        }
        if (saved.camera && ["x", "y", "k"].every(k => Number.isFinite(saved.camera[k])) && saved.camera.k >= .2 && saved.camera.k <= 3) {
          memory.camera = saved.camera;
        }
        if (saved.size && Number.isFinite(saved.size.width) && Number.isFinite(saved.size.height)) memory.size = saved.size;
      }
    } catch { /* 浏览器禁用存储时，图谱仍可正常使用。 */ }
    return memory;
  }

  function persist() {
    const state = preferences();
    try {
      localStorage.setItem(STORAGE, JSON.stringify({...state, collapsed: [...state.collapsed],
        expanded: [...state.expanded], positions: [...state.positions]}));
    } catch { /* 仅影响视角记忆，不影响学习进度。 */ }
  }

  function category(row) {
    if (row.status === "needs_calibration") return "calibration";
    if (row.overdue_days > 0) return "overdue";
    if (row.due || row.status === "needs_review") return "review";
    if (row.display_status === "learned") return "learned";
    if (row.display_status === "learning" || row.status === "learning") return "learning";
    return "new";
  }

  function model(data) {
    const relation = preferences().relation;
    const calibration = new Map(data.plan.calibration.map(row => [row.id, row]));
    const rows = new Map(data.next_new.map(row => [row.id, {...row, source: "queue"}]));
    for (const row of data.queue) rows.set(row.id, {...row, source: "record"});
    for (const [id, item] of calibration) {
      const row = rows.get(id);
      if (row) rows.set(id, {...row, status: "needs_calibration", reason: item.reason});
    }
    const groups = new Map(), problems = new Map();
    for (const row of rows.values()) {
      const topic = row.topic || "待分类";
      if (!groups.has(topic)) groups.set(topic, []);
      const node = {id: `problem:${row.id}`, kind: "problem", parent: `topic:${topic}`,
        title: row.title, topic, row, category: category(row), radius: 17};
      groups.get(topic).push(node); problems.set(row.id, node);
    }
    const order = ["双指针", "滑动窗口", "固定窗口", "哈希", "二叉树", "BST"];
    let topics = [...groups.keys()].sort((a, b) => {
      const ai = order.includes(a) ? order.indexOf(a) : 100;
      const bi = order.includes(b) ? order.indexOf(b) : 100;
      return ai - bi || a.localeCompare(b, "zh-CN");
    });
    const nodes = [{id: ROOT, kind: "root", title: data.goal, label: relation === "topics" ? "我的算法学习" : relation === "patterns" ? "解题模板" : "历史错因", radius: 34}];
    let groupNodes;
    if (relation === "topics") {
      groupNodes = topics.map(topic => ({id: `topic:${topic}`, kind: "topic", parent: ROOT, title: topic, topic,
        children: groups.get(topic).sort((a,b)=>Number(a.row.id)-Number(b.row.id)), radius: 25}));
    } else {
      const definitions = data.knowledge?.[relation] || [];
      groupNodes = definitions.map(def => ({id: `${relation}:${def.id}`, kind: "topic", parent: ROOT, title: def.title, topic: def.title,
        children: def.problem_ids.filter(pid=>problems.has(pid)).map(pid=>problems.get(pid)), radius: 25, details: def, relation})).filter(group=>group.children.length);
      if (relation === "patterns") {
        const linked = new Set(groupNodes.flatMap(group=>group.children.map(child=>child.row.id)));
        const unlinked = [...problems.values()].filter(child=>!linked.has(child.row.id));
        if(unlinked.length) groupNodes.push({id:"patterns:unclassified",kind:"topic",parent:ROOT,title:"待补充模板",topic:"待补充模板",children:unlinked,radius:25,relation,
          details:{description:"这些题尚未核对解题模板，保留在图中便于后续完善。",questions:[]}});
      }
      topics = groupNodes.map(group=>group.title);
    }
    const included = new Set();
    for(const group of groupNodes) {
      nodes.push(group);
      for(const child of group.children) if(!included.has(child.id)) {child.parent=group.id;included.add(child.id);nodes.push(child);}
    }
    const visibleRows = new Map([...rows].filter(([pid])=>included.has(`problem:${pid}`)));
    return {nodes, topics, rows:visibleRows, allRows:rows, relation, lookup: new Map(nodes.map(node => [node.id, node]))};
  }

  function shorten(value, max = 11) {
    const chars = [...String(value)];
    return chars.length > max ? chars.slice(0, max).join("") + "…" : chars.join("");
  }

  function caption(node) {
    if (node.kind === "root") return node.label || "我的算法学习";
    if (node.kind === "problem") return `LC${node.row.id} · ${shorten(node.title)}`;
    if (node.kind === "more") return `还有 ${node.count} 道题`;
    return shorten(node.title, 15);
  }

  function completionLabel(row) {
    if (row.count_is_lower_bound) return row.count ? `至少 ${row.count} 次` : "待核对";
    return `${row.count || 0} 次`;
  }

  function box(node) {
    const width = Math.max(64, [...caption(node)].reduce((n, c) => n + (c.charCodeAt(0) > 255 ? 11 : 6.5), 20));
    return {left: -width / 2, right: width / 2, top: -node.radius - 8, bottom: node.radius + 38, width};
  }

  function arrange(graph) {
    const points = new Map([[ROOT, {x: 0, y: 0}]]);
    const anchors = new Map();
    const groups = graph.nodes.filter(node => node.kind === "topic");
    const totalWeight = groups.reduce((n, group) => n + group.children.length + 2, 0) || 1;
    const spread = Math.max(1, Math.sqrt(graph.rows.size / 18));
    const proposals = new Map();
    let start = -Math.PI * .98;
    for (const group of groups) {
      const span = (group.children.length + 2) / totalWeight * Math.PI * 2;
      const angle = start + span / 2;
      points.set(group.id, {x: Math.cos(angle) * 180 * spread, y: Math.sin(angle) * 142 * spread});
      group.children.forEach((child, index) => {
        const childAngle = start + span * (.12 + .76 * (index + .5) / group.children.length);
        if(!proposals.has(child.id)) proposals.set(child.id,[]);
        proposals.get(child.id).push({x: Math.cos(childAngle) * 355 * spread, y: Math.sin(childAngle) * 265 * spread});
      });
      start += span;
    }
    for(const [id, options] of proposals) points.set(id,{x:options.reduce((n,p)=>n+p.x,0)/options.length,y:options.reduce((n,p)=>n+p.y,0)/options.length});
    for (const [id, point] of points) anchors.set(id, {...point});
    // 以标签矩形做碰撞分离，避免像密集拓扑图那样把题名叠在一起。
    for (let step = 0; step < 150; step++) {
      if (step < 120) {
        for (const node of graph.nodes) {
          if (node.id === ROOT) continue;
          const point = points.get(node.id), anchor = anchors.get(node.id);
          point.x += (anchor.x - point.x) * .035;
          point.y += (anchor.y - point.y) * .035;
        }
      }
      for (let i = 0; i < graph.nodes.length; i++) {
        for (let j = i + 1; j < graph.nodes.length; j++) {
          const a = graph.nodes[i], b = graph.nodes[j], ap = points.get(a.id), bp = points.get(b.id);
          const ab = box(a), bb = box(b);
          const dx = bp.x - ap.x;
          const dy = bp.y + (bb.top + bb.bottom) / 2 - ap.y - (ab.top + ab.bottom) / 2;
          const ox = (ab.width + bb.width) / 2 + 14 - Math.abs(dx);
          const oy = (ab.bottom - ab.top + bb.bottom - bb.top) / 2 + 12 - Math.abs(dy);
          if (ox <= 0 || oy <= 0) continue;
          const axis = ox < oy ? "x" : "y";
          const shift = (axis === "x" ? ox : oy) * (a.id === ROOT ? 1 : .5);
          const sign = (axis === "x" ? dx : dy) >= 0 ? 1 : -1;
          if (a.id !== ROOT) ap[axis] -= shift * sign;
          bp[axis] += shift * sign;
        }
      }
    }
    return points;
  }

  function page(data, ui) {
    const {esc, icon, button} = ui;
    const graph = model(data), state = preferences();
    if (state.topic && !graph.topics.includes(state.topic)) state.topic = "";
    return `<div class="page-heading graph-heading"><div><span class="eyebrow">CONNECT YOUR KNOWLEDGE</span><h1>算法学习图谱</h1><p class="muted">从专题到题目，看见你的学习脉络。</p></div><div class="heading-actions"><button class="button secondary" data-view="today">${icon("home")}今日计划</button>${button("记录练习", "practice", "primary", "plus")}</div></div>
      <section class="graph-workspace" aria-label="算法知识关系管理">
        <div class="graph-view-switch" role="group" aria-label="图谱关系类型">${[["topics","按专题"],["patterns","按模板"],["errors","按错因"]].map(([key,title])=>`<button data-action="graph-relation" data-relation="${key}" aria-pressed="${state.relation===key}">${title}</button>`).join("")}<span>${state.relation==="topics"?"专题归属":state.relation==="patterns"?"题目使用哪些解题模板":"有日志或复盘证据的历史错因"}</span></div>
        <div class="graph-toolbar"><div class="graph-search-wrap">${icon("network")}<input id="graph-search" type="search" maxlength="200" placeholder="搜索题号、题名、专题…" aria-label="搜索图谱节点" value="${esc(state.query)}"></div><div class="graph-filters"><button class="button graph-motion-toggle" data-graph-action="motion" aria-label="流动效果" aria-pressed="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M2 8c4-6 6 6 10 0s6 6 10 0M2 16c4-6 6 6 10 0s6 6 10 0"/></svg><span>流动中</span></button><select id="graph-topic" aria-label="图谱专题"><option value="">全部专题</option>${graph.topics.map(t => `<option ${state.topic === t ? "selected" : ""}>${esc(t)}</option>`).join("")}</select><select id="graph-status" aria-label="图谱状态"><option value="all">全部状态</option>${Object.entries(statuses).map(([key, value]) => `<option value="${key}" ${state.status === key ? "selected" : ""}>${value}</option>`).join("")}</select><button class="button graph-collapse" data-graph-action="collapse-all">${icon("layers")}<span>折叠专题</span></button></div></div>
        <div class="graph-layout"><div class="graph-stage" id="graph-stage"><div class="graph-canvas-note"><span class="graph-live-dot"></span>学习关系图<span id="graph-count" aria-live="polite"></span></div><svg id="learning-graph" class="learning-graph" tabindex="0" role="group" aria-label="算法学习关系图，可拖动节点、平移和缩放"><g class="graph-camera"><g class="graph-edges"></g><g class="graph-nodes"></g></g></svg><div class="graph-no-results" hidden><strong>没有找到匹配的题目</strong><p>换个关键词，或清除筛选查看全图。</p><button class="button secondary" data-graph-action="clear">清除筛选</button></div><div class="graph-controls"><button aria-label="放大图谱" title="放大图谱（+）" data-graph-action="zoom-in">${icon("plus")}</button><output id="graph-zoom" aria-label="图谱缩放比例">100%</output><button aria-label="缩小图谱" title="缩小图谱（-）" data-graph-action="zoom-out"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M5 12h14"/></svg></button><span class="graph-control-separator"></span><button aria-label="适应画布" title="适应画布（0）" data-graph-action="fit"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/><circle cx="12" cy="12" r="3"/></svg></button><button aria-label="重新布局" title="重新布局" data-graph-action="layout">${icon("refresh")}</button></div><p class="graph-gesture-hint">拖动节点或空白处 · 滚轮缩放 · 双击专题折叠</p></div><aside id="graph-detail" class="graph-detail" aria-label="所选节点详情"></aside></div>
        <div class="graph-footer"><div class="graph-legend" aria-label="节点颜色含义">${Object.entries(statuses).map(([key, value]) => `<span><i class="graph-dot category-${key}"></i>${value}</span>`).join("")}</div><span class="graph-edge-key"><i></i>${state.relation==="topics"?"连线表示专题归属":state.relation==="patterns"?"连线表示使用模板":"虚线表示历史错因"}</span></div>
      </section><p class="graph-bottom-note">${icon("info")}图谱包含已记录和待学题目；拖动位置仅保存在当前浏览器。历史状态不明确的题单独标记。</p>`;
  }

  function mount(container, data, ui) {
    const {esc, icon, button} = ui;
    const graph = model(data), state = preferences();
    const svg = container.querySelector("#learning-graph");
    const stage = container.querySelector("#graph-stage");
    const viewport = svg.querySelector(".graph-camera");
    const edgesGroup = svg.querySelector(".graph-edges");
    const nodesGroup = svg.querySelector(".graph-nodes");
    const detail = container.querySelector("#graph-detail");
    const abort = new AbortController();
    const pointers = new Map();
    const workspace = container.querySelector(".graph-workspace");
    const motionButton = container.querySelector('[data-graph-action="motion"]');
    const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
    const bodies = new Map();
    let visible = [], edges = [], connections = [], nodeElements = new Map(), gesture = null;
    let width = stage.clientWidth, height = stage.clientHeight;
    let camera = state.camera ? {...state.camera} : {x: width / 2, y: height / 2, k: 1};
    let frame = null, saveTimer = null, revealTimer = null, disposed = false, lastTap = null;
    let motionFrame = null, lastTick = null, motionTime = motionClock, cameraTarget = null, panVelocity = null;
    let hoveredId = null, focusedId = null, inViewport = true;
    let dialogOpen = Boolean(document.querySelector("dialog[open]"));

    const on = (element, event, handler, options = {}) => element.addEventListener(event, handler, {...options, signal: abort.signal});
    const point = id => state.positions.get(id) || {x: 0, y: 0};
    const visualPoint = id => bodies.get(id) || point(id);
    const motionEnabled = () => state.motion && !reducedMotion.matches;
    const running = () => motionEnabled() && !document.hidden && inViewport && !dialogOpen && !disposed;
    const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
    const phaseOf = id => [...id].reduce((sum, ch) => (sum * 31 + ch.charCodeAt(0)) % 997, 0) / 997 * Math.PI * 2;

    function ensureBodies(previous) {
      for (const node of visible) {
        const target = point(node.id);
        const returning = previous.size && !previous.has(node.id);
        let body = bodies.get(node.id);
        if (!body) {
          const cached = visualMemory.get(node.id);
          const origin = node.parent ? visualPoint(node.parent) : target;
          const start = cached || (motionEnabled() ? {
            x: target.x * .68 + origin.x * .32, y: target.y * .68 + origin.y * .32,
          } : target);
          body = {x: start.x, y: start.y, vx: 0, vy: 0, releaseUntil: 0, phase: phaseOf(node.id), bounds: box(node)};
          bodies.set(node.id, body);
        }
        if (returning && motionEnabled()) {
          const origin = visualPoint(node.parent || ROOT);
          body.x = origin.x * .65 + target.x * .35;
          body.y = origin.y * .65 + target.y * .35;
          body.vx = body.vy = 0;
        }
        if (!motionEnabled()) { body.x = target.x; body.y = target.y; body.vx = body.vy = 0; }
      }
    }

    function fixed(node, now) {
      if (gesture?.type === "node" && gesture.id === node.id) return true;
      const body = bodies.get(node.id);
      return now > body.releaseUntil && (node.id === hoveredId || node.id === focusedId || node.id === state.selected);
    }

    function stepBodies(dt, now) {
      const forces = new Map();
      for (const node of visible) {
        const body = bodies.get(node.id), anchor = point(node.id);
        const groupPhase = phaseOf(node.parent || node.id);
        // 低频、错相的椭圆轨迹：同组节点有轻微共振，但不会整组一起平移。
        const amplitude = node.kind === "root" ? 1.5 : node.kind === "topic" ? 5.5 : 7.5;
        const waveX = Math.sin(motionTime * .72 + body.phase) * amplitude + Math.sin(motionTime * .29 + groupPhase) * 2;
        const waveY = Math.cos(motionTime * .57 + body.phase) * amplitude * .78 + Math.cos(motionTime * .33 + groupPhase) * 1.5;
        const spring = node.kind === "root" ? .055 : .024;
        forces.set(node.id, {x: (anchor.x + waveX - body.x) * spring, y: (anchor.y + waveY - body.y) * spring});
      }
      // 连线像柔软的弹簧，拖拽时把牵引传给相邻节点。
      const rest = id => gesture?.rest?.get(id) || point(id);
      for (const edge of edges) {
        const a = bodies.get(edge.from), b = bodies.get(edge.to), ar = rest(edge.from), br = rest(edge.to);
        const fx = ((b.x - a.x) - (br.x - ar.x)) * .012;
        const fy = ((b.y - a.y) - (br.y - ar.y)) * .012;
        const af = forces.get(edge.from), bf = forces.get(edge.to);
        af.x += fx; af.y += fy; bf.x -= fx; bf.y -= fy;
      }
      // 只在标签接近时轻推，避免漂浮和拖动把文字压在一起。
      if (visible.length <= 160) {
        for (let i = 0; i < visible.length; i++) {
          for (let j = i + 1; j < visible.length; j++) {
            const an = visible[i], bn = visible[j], a = bodies.get(an.id), b = bodies.get(bn.id);
            const dx = b.x - a.x;
            const dy = b.y + (b.bounds.top + b.bounds.bottom) / 2 - a.y - (a.bounds.top + a.bounds.bottom) / 2;
            const ox = (a.bounds.width + b.bounds.width) / 2 + 5 - Math.abs(dx);
            const oy = (a.bounds.bottom - a.bounds.top + b.bounds.bottom - b.bounds.top) / 2 + 5 - Math.abs(dy);
            if (ox <= 0 || oy <= 0) continue;
            const axis = ox < oy ? "x" : "y";
            const force = Math.min(.8, (axis === "x" ? ox : oy) * .018) * ((axis === "x" ? dx : dy) >= 0 ? 1 : -1);
            forces.get(an.id)[axis] -= force;
            forces.get(bn.id)[axis] += force;
          }
        }
      }
      for (const node of visible) {
        const body = bodies.get(node.id);
        if (fixed(node, now)) { body.vx = body.vy = 0; continue; }
        const force = forces.get(node.id), mass = node.kind === "root" ? 2 : node.kind === "topic" ? 1.4 : 1;
        const damping = Math.pow(.82, dt);
        body.vx = clamp((body.vx + clamp(force.x / mass, -3, 3) * dt) * damping, -12, 12);
        body.vy = clamp((body.vy + clamp(force.y / mass, -3, 3) * dt) * damping, -12, 12);
        body.x += body.vx * dt; body.y += body.vy * dt;
      }
    }

    function moveCamera(target, smooth = motionEnabled()) {
      panVelocity = null;
      if (smooth) { cameraTarget = target; wake(); }
      else { cameraTarget = null; camera = target; applyCamera(); }
    }

    function tick(now) {
      motionFrame = null;
      if (!running()) { lastTick = null; return; }
      const elapsed = lastTick === null ? 16.67 : clamp(now - lastTick, 0, 34);
      const dt = elapsed / 16.67;
      lastTick = now; motionTime += elapsed / 1000;
      motionClock = motionTime;
      stepBodies(dt, now);
      if (cameraTarget) {
        const amount = 1 - Math.pow(.78, dt);
        for (const key of ["x", "y", "k"]) camera[key] += (cameraTarget[key] - camera[key]) * amount;
        if (Math.abs(camera.x - cameraTarget.x) + Math.abs(camera.y - cameraTarget.y) + Math.abs(camera.k - cameraTarget.k) * 100 < .04) {
          camera = cameraTarget; cameraTarget = null; applyCamera(); persist();
        } else applyCamera();
      } else if (panVelocity) {
        camera.x += panVelocity.x * dt; camera.y += panVelocity.y * dt;
        panVelocity.x *= Math.pow(.86, dt); panVelocity.y *= Math.pow(.86, dt);
        applyCamera();
        if (Math.hypot(panVelocity.x, panVelocity.y) < .08) { panVelocity = null; persist(); }
      }
      drawGeometry();
      motionFrame = requestAnimationFrame(tick);
    }

    function wake() {
      if (running() && motionFrame === null) motionFrame = requestAnimationFrame(tick);
    }

    function updateMotionMode() {
      const enabled = motionEnabled(), active = running();
      workspace.dataset.motion = enabled ? "on" : "off";
      workspace.dataset.running = active ? "true" : "false";
      motionButton.setAttribute("aria-pressed", String(enabled));
      motionButton.disabled = reducedMotion.matches;
      motionButton.querySelector("span").textContent = enabled ? "流动中" : "已静止";
      motionButton.title = reducedMotion.matches ? "系统已启用减少动态效果" : enabled ? "暂停流动，方便阅读" : "开启漂浮、弹性与连线光点";
      if (!active) {
        if (motionFrame !== null) cancelAnimationFrame(motionFrame);
        motionFrame = null; lastTick = null;
      }
      if (!enabled) {
        cameraTarget = null; panVelocity = null;
        for (const body of bodies.values()) body.vx = body.vy = 0;
        drawGeometry();
      }
      wake();
    }

    function ensurePositions(reset = false) {
      const missing = graph.nodes.filter(n => !state.positions.has(n.id)).length;
      const known = graph.nodes.length - missing;
      const reflow = reset || state.layoutRelation !== graph.relation || (known > 0 && missing >= Math.max(8, known / 2));
      if (reflow || missing) {
        const fresh = arrange(graph);
        for (const [id, position] of fresh) if (reflow || !state.positions.has(id)) state.positions.set(id, position);
        if (reflow) for (const id of state.positions.keys()) if (id.startsWith("more:")) state.positions.delete(id);
      }
      state.layoutRelation = graph.relation;
      return reflow;
    }

    function filteredChildren(group) {
      const query = state.query.trim().toLocaleLowerCase().replace(/^lc\s*/, "");
      if (state.topic && state.topic !== group.topic) return [];
      return group.children.filter(node => {
        const search = `${node.row.id} ${node.title} ${node.topic} ${node.row.note || ""}`.toLocaleLowerCase();
        const statusMatch = state.status === "all" || node.category === state.status || (state.status === "review" && node.category === "overdue");
        return statusMatch && (!query || search.includes(query) || group.title.toLocaleLowerCase().includes(query));
      });
    }

    function visibleGraph() {
      const filtering = Boolean(state.query.trim() || state.topic || state.status !== "all");
      const nodes = [graph.lookup.get(ROOT)];
      const included = new Set([ROOT]);
      connections = [];
      let matched = 0;
      for (const group of graph.nodes.filter(n => n.kind === "topic")) {
        const children = filteredChildren(group);
        if (!children.length) continue;
        matched += children.length;
        nodes.push(group);
        connections.push({from:ROOT,to:group.id,relation:graph.relation});
        const limit = filtering || state.expanded.has(group.id) ? children.length : state.collapsed.has(group.id) ? 0 : LIMIT;
        for(const child of children.slice(0,limit)) {
          if(!included.has(child.id)){nodes.push(child);included.add(child.id);}
          connections.push({from:group.id,to:child.id,relation:graph.relation});
        }
        if (children.length > limit) {
          const hidden = children.slice(limit), id = `more:${group.topic}`;
          if (!state.positions.has(id)) {
            state.positions.set(id, {x: hidden.reduce((n, child) => n + point(child.id).x, 0) / hidden.length,
              y: hidden.reduce((n, child) => n + point(child.id).y, 0) / hidden.length});
          }
          nodes.push({id, kind: "more", title: `还有 ${hidden.length} 道题`, topic: group.topic,
            parent: group.id, count: hidden.length, radius: 20});
          connections.push({from:group.id,to:id,relation:graph.relation,more:true});
        }
      }
      container.querySelector(".graph-no-results").hidden = matched > 0 || graph.rows.size === 0;
      const shown = nodes.filter(n => n.kind === "problem").length;
      const groupName = graph.relation === "topics" ? "专题" : graph.relation === "patterns" ? "模板" : "错因";
      container.querySelector("#graph-count").textContent = `${nodes.filter(n => n.kind === "topic").length} 个${groupName} · 展开 ${shown} / ${graph.rows.size} 道题`;
      const collapse = container.querySelector('[data-graph-action="collapse-all"]');
      collapse.querySelector("span").textContent = state.collapsed.size ? "展开专题" : "折叠专题";
      collapse.disabled = filtering || graph.topics.length === 0;
      return nodes;
    }

    function nodeMarkup(node, order = 0) {
      const bounds = box(node), label = caption(node), categoryClass = node.category ? `category-${node.category}` : "";
      let content;
      if (node.kind === "problem") content = `<text class="graph-node-number ${node.row.id.length > 4 ? "small" : ""}" text-anchor="middle" dominant-baseline="central">${esc(node.row.id)}</text>`;
      else if (node.kind === "more") content = `<text class="graph-node-more" text-anchor="middle" dominant-baseline="central">+${node.count}</text>`;
      else content = `<g class="graph-node-icon" transform="translate(-11 -11)">${icon(node.kind === "root" ? "network" : node.relation === "patterns" ? "book" : node.relation === "errors" ? "info" : "layers").replace("<svg ", '<svg width="22" height="22" ')}</g>`;
      const description = node.kind === "problem" ? `LC${node.row.id} ${node.title}，${statuses[node.category]}` : node.kind === "more" ? `展开${node.topic}的 ${node.count} 道题` : node.title;
      const revealDelay = node.kind === "root" ? 0 : node.kind === "topic" ? 180 + order * 90 : 520 + order * 42;
      const revealClass = `reveal-step-${Math.min(24, Math.floor(revealDelay / 100))}`;
      return `<g class="graph-node node-${node.kind} relation-${node.relation || "topics"} ${categoryClass} ${revealClass}" data-node="${esc(node.id)}" role="button" tabindex="0" aria-label="${esc(description)}" aria-pressed="false"><title>${esc(description)}</title><ellipse class="graph-node-aura" rx="${node.radius + 14}" ry="${node.radius + 11}"/><ellipse class="graph-node-aura graph-node-aura-secondary" rx="${node.radius + 10}" ry="${node.radius + 15}"/><circle class="graph-node-halo" r="${node.radius + 6}"/><circle class="graph-node-circle" r="${node.radius}"/>${content}<rect class="graph-label-bg" x="${-bounds.width / 2}" y="${node.radius + 10}" width="${bounds.width}" height="23" rx="4"/><text class="graph-label" text-anchor="middle" y="${node.radius + 26}">${esc(label)}</text></g>`;
    }

    function drawGeometry() {
      for (const node of visible) {
        const position = visualPoint(node.id);
        nodeElements.get(node.id)?.setAttribute("transform", `translate(${position.x} ${position.y})`);
      }
      for (const edge of edges) {
        const a = visualPoint(edge.from), b = visualPoint(edge.to);
        const dx = b.x - a.x, dy = b.y - a.y, length = Math.max(1, Math.hypot(dx, dy));
        const bend = Math.min(24, length * .09) * Math.sin(edge.phase) + Math.sin(motionTime * .8 + edge.phase) * 4;
        const control = {x: (a.x + b.x) / 2 - dy / length * bend, y: (a.y + b.y) / 2 + dx / length * bend};
        edge.element.setAttribute("d", `M${a.x},${a.y} Q${control.x},${control.y} ${b.x},${b.y}`);
        if (motionEnabled()) {
          const t = (motionTime / (5.5 + edge.phase * .45) + edge.phase / (Math.PI * 2)) % 1;
          const s = Math.max(0, t - .12);
          const curve = u => ({x: (1-u)**2*a.x + 2*(1-u)*u*control.x + u*u*b.x,
            y: (1-u)**2*a.y + 2*(1-u)*u*control.y + u*u*b.y});
          const start = curve(s), end = curve(t);
          const handle = {x: start.x + (t-s)*((1-s)*(control.x-a.x)+s*(b.x-control.x)),
            y: start.y + (t-s)*((1-s)*(control.y-a.y)+s*(b.y-control.y))};
          edge.flow.setAttribute("d", `M${start.x},${start.y} Q${handle.x},${handle.y} ${end.x},${end.y}`);
          const opacity = Math.sin(t * Math.PI) * .8;
          edge.flow.setAttribute("opacity", opacity * .65);
          for (const particle of [edge.dot, edge.glow]) {
            particle.setAttribute("cx", end.x); particle.setAttribute("cy", end.y);
            particle.setAttribute("opacity", particle === edge.dot ? opacity : opacity * .17);
          }
        }
      }
    }

    function applyCamera() {
      viewport.setAttribute("transform", `translate(${camera.x} ${camera.y}) scale(${camera.k})`);
      container.querySelector("#graph-zoom").textContent = `${Math.round(camera.k * 100)}%`;
      state.camera = {...camera};
      state.size = {width, height};
    }

    function fit() {
      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      for (const node of visible) {
        const position = point(node.id), bounds = box(node);
        minX = Math.min(minX, position.x + bounds.left); maxX = Math.max(maxX, position.x + bounds.right);
        minY = Math.min(minY, position.y + bounds.top); maxY = Math.max(maxY, position.y + bounds.bottom);
      }
      const k = Math.max(.2, Math.min(1.3, (width - 60) / Math.max(1, maxX - minX), (height - 140) / Math.max(1, maxY - minY)));
      moveCamera({k, x: width / 2 - (maxX + minX) / 2 * k, y: (height - 5) / 2 - (maxY + minY) / 2 * k});
    }

    function refreshSelection() {
      const selected = visible.find(node => node.id === state.selected) || graph.lookup.get(ROOT);
      state.selected = selected.id;
      const related = new Set([selected.id]);
      if (selected.kind === "root") visible.forEach(n => related.add(n.id));
      else if (selected.kind === "topic") { edges.filter(e=>e.from===selected.id).forEach(e=>related.add(e.to));related.add(ROOT); }
      else { edges.filter(e=>e.to===selected.id).forEach(e=>related.add(e.from)); related.add(ROOT); }
      for (const [id, element] of nodeElements) {
        element.classList.toggle("is-selected", id === selected.id);
        element.classList.toggle("is-muted", !related.has(id));
        element.setAttribute("aria-pressed", String(id === selected.id));
      }
      for (const edge of edges) {
        const active = related.has(edge.from) && related.has(edge.to);
        edge.element.classList.toggle("is-active", active && selected.kind !== "root");
        edge.element.classList.toggle("is-muted", !active);
        edge.group.classList.toggle("is-muted", !active);
      }
      showDetail(selected);
    }

    function detailHeader(kicker, title, subtitle, symbol = "network", color = "") {
      return `<div class="graph-detail-heading"><span class="eyebrow">${esc(kicker)}</span><div class="graph-detail-symbol ${color ? `category-${color}` : ""}">${icon(symbol)}</div><h2>${esc(title)}</h2><p>${esc(subtitle)}</p></div>`;
    }

    function showDetail(node) {
      if (node.kind === "problem") {
        const row = node.row;
        const status = node.category === "overdue" ? `已逾期 ${row.overdue_days} 天` : statuses[node.category];
        detail.innerHTML = detailHeader(`LEETCODE ${row.id}`, row.title, row.topic, "book", node.category) +
          `<span class="graph-status-pill category-${node.category}"><i></i>${esc(status)}</span><dl class="graph-facts"><div><dt>完成次数</dt><dd>${esc(completionLabel(row))}</dd></div><div><dt>最近练习</dt><dd>${esc(row.last_done || "尚未记录")}</dd></div><div><dt>下次复习</dt><dd>${esc(row.next_due || "记录完成后安排")}</dd></div><div><dt>掌握状态</dt><dd>${esc(row.source !== "record" && node.category === "calibration" ? "核对旧日志" : ({learned:"已掌握",learning:"待间隔验证",needs_review:"需要巩固",needs_calibration:"待校准"}[row.display_status || row.status] || "待学习"))}</dd></div></dl><div class="graph-detail-note"><h3>上次的卡点与收获</h3><p>${esc(row.note || "尚未填写单题复盘，可以在学习记录中回看历史讲解。")}</p></div>${row.history_import ? `<div class="graph-calibration-note">${icon("book")}<p>已从历史学习日志补回；次数按日志可确认的记录累计，可能少于实际练习次数。</p></div>` : ""}${row.reason ? `<div class="graph-calibration-note">${icon("info")}<p>${esc(row.reason)}</p></div>` : ""}<div class="graph-detail-actions">${button("记录练习", "practice", "primary", "plus", `data-id="${esc(row.id)}"`)}${button(node.category === "calibration" ? "请教练核对历史" : "让教练带我练", "coach", "secondary", "spark", `data-id="${esc(row.id)}"`)}</div><button class="text-button graph-log-link" data-view="log">查看学习记录 ${icon("arrow")}</button>`;
        const actions=detail.querySelector(".graph-detail-actions");
        actions.querySelector('[data-action="practice"]').className="button secondary";
        actions.insertAdjacentHTML("afterbegin",button("开始本题练习","workbench","primary","code",`data-id="${esc(row.id)}"`));
        const concepts=(data.knowledge?.patterns||[]).filter(p=>p.problem_ids.includes(row.id));
        const mistakes=(data.knowledge?.errors||[]).filter(e=>e.problem_ids.includes(row.id));
        actions.insertAdjacentHTML("beforebegin",`<div class="graph-detail-section"><h3>解题模板与历史错因</h3><div class="graph-knowledge-chips">${concepts.map(p=>`<button data-action="graph-relation" data-relation="patterns" data-focus="patterns:${esc(p.id)}">${esc(p.title)}</button>`).join("")}${mistakes.map(e=>`<button class="is-error" data-action="graph-relation" data-relation="errors" data-focus="errors:${esc(e.id)}">${esc(e.title)}</button>`).join("")}</div></div>`);
      } else if (node.kind === "topic") {
        const learned = node.children.filter(n => n.row.display_status === "learned").length;
        const due = node.children.filter(n => ["overdue", "review"].includes(n.category)).length;
        const hidden = state.collapsed.has(node.id) && !state.expanded.has(node.id);
        detail.innerHTML = detailHeader("TOPIC", node.title, `${node.children.length} 道题目，串起同一种思路`, "layers") +
          `<div class="graph-topic-stats"><div><strong>${learned}</strong><small>已掌握</small></div><div><strong>${due}</strong><small>待复习</small></div><div><strong>${node.children.length}</strong><small>关联题目</small></div></div><div class="graph-detail-actions"><button class="button primary" data-graph-action="focus-topic" data-topic="${esc(node.topic)}">${icon("network")}聚焦这个专题</button><button class="button secondary" data-graph-action="toggle-topic" data-topic-id="${esc(node.id)}">${icon("layers")}${hidden ? "展开题目" : "折叠题目"}</button></div><div class="graph-detail-section"><h3>专题里的题目</h3><div class="graph-topic-list">${node.children.map(child => `<button data-graph-select="${esc(child.id)}"><span class="graph-dot category-${child.category}"></span><span><strong>LC${esc(child.row.id)}</strong><small>${esc(child.title)}</small></span>${icon("arrow")}</button>`).join("")}</div></div>`;
        if(node.details) {
          const isError=graph.relation==="errors";
          detail.querySelector(".eyebrow").textContent=isError?"OBSERVED MISTAKE":"SOLUTION PATTERN";
          detail.querySelector(".graph-detail-heading p").textContent=isError?`${node.children.length} 道题中有记录，复习时可验证是否已纠正`:`${node.children.length} 道题共享这个解题模板`;
          detail.querySelector('[data-graph-action="focus-topic"]').innerHTML=icon("network")+(isError?"聚焦这个错因":"聚焦这个模板");
          const questions=node.details.questions || [node.details.question].filter(Boolean);
          detail.querySelector(".graph-topic-stats").insertAdjacentHTML("beforebegin",`<div class="graph-concept-description"><p>${esc(node.details.description)}</p><ul>${questions.map(q=>`<li>${esc(q)}</li>`).join("")}</ul></div>`);
          if(isError) detail.insertAdjacentHTML("beforeend",`<div class="graph-detail-section"><h3>记录依据</h3>${(node.details.evidence||[]).map(e=>`<details class="graph-evidence"><summary>${esc(e.date)} · LC${esc(e.problem_id)} · ${esc(e.source)}</summary><p>${esc(e.text)}</p></details>`).join("")}</div>`);
        }
      } else {
        const due = [...graph.rows.values()].filter(row => ["review", "overdue"].includes(category(row))).length;
        detail.innerHTML = detailHeader("YOUR LEARNING MAP", "每个节点，都是一份积累。", data.goal) +
          `<div class="graph-overview-stats"><div><strong>${graph.topics.length}</strong><span>学习专题</span></div><div><strong>${data.stats.recorded}</strong><span>练过的题目</span></div></div><div class="graph-summary-line"><span><i class="graph-dot category-overdue"></i>需要复习</span><strong>${due} 道</strong></div><div class="graph-summary-line"><span><i class="graph-dot category-calibration"></i>需要校准</span><strong>${[...graph.rows.values()].filter(row => category(row) === "calibration").length} 道</strong></div><div class="graph-detail-section"><h3>从一个节点开始</h3><ul class="graph-instructions"><li><b>01</b><span>点击题目，查看完成记录与复习时间。</span></li><li><b>02</b><span>点击专题，聚焦一组相关题目。</span></li><li><b>03</b><span>记录一次练习，图谱随进度更新。</span></li></ul></div><div class="graph-detail-actions"><button class="button secondary" data-view="today">${icon("arrow")}查看今日学习计划</button></div><p class="graph-source-note">练过 ${data.stats.recorded} 道，另有 ${Math.max(0,graph.rows.size - data.stats.recorded)} 道待学。折叠的题目也计入总数，可点击“还有 N 道题”展开。</p>`;
        if(graph.relation!=="topics") {
          detail.querySelector(".graph-overview-stats span").textContent=graph.relation==="patterns"?"解题模板":"有证据的错因";
          detail.querySelector(".graph-source-note").textContent=`本视图关联 ${graph.rows.size} 道题；全局练过 ${data.stats.recorded} 道，另有 ${Math.max(0,graph.allRows.size-data.stats.recorded)} 道待学。历史错因不代表现在仍不会。`;
          detail.querySelector(".graph-detail-heading h2").textContent=graph.relation==="patterns"?"找到题目之间的共同思路。":"从反复出现的问题里进步。";
        }
      }
    }

    function rebuild(refit = false) {
      const reflow = ensurePositions();
      const previous = new Set(visible.map(node => node.id));
      visible = visibleGraph();
      ensureBodies(previous);
      hoveredId = focusedId = null;
      if (!visible.some(node => node.id === state.selected)) state.selected = ROOT;
      if (state.query.trim() && visible.filter(n => n.kind === "problem").length === 1) state.selected = visible.find(n => n.kind === "problem").id;
      workspace.dataset.reveal = "true";
      clearTimeout(revealTimer);
      revealTimer = setTimeout(() => { if (!disposed) workspace.dataset.reveal = "false"; }, 3400);
      nodesGroup.innerHTML = visible.map((node, index) => nodeMarkup(node, index)).join("");
      nodeElements = new Map([...nodesGroup.children].map(el => [el.getAttribute("data-node"), el]));
      edgesGroup.innerHTML = connections.map((link, index) => {const node=graph.lookup.get(link.to);const revealDelay = link.from === ROOT ? 120 + index * 75 : 500 + index * 38;const revealClass = `reveal-step-${Math.min(24, Math.floor(revealDelay / 100))}`;return `<g class="graph-link relation-${link.relation} ${node?.category ? `category-${node.category}` : ""} ${revealClass}" data-from="${esc(link.from)}" data-to="${esc(link.to)}"><path class="graph-edge ${link.more ? "edge-more" : ""}"/><path class="graph-flow"/><circle class="graph-particle graph-particle-glow" r="5"/><circle class="graph-particle graph-particle-dot" r="2.1"/></g>`;}).join("");
      edges = [...edgesGroup.children].map(group => ({group, element: group.querySelector(".graph-edge"),
        flow: group.querySelector(".graph-flow"), dot: group.querySelector(".graph-particle-dot"), glow: group.querySelector(".graph-particle-glow"),
        from: group.getAttribute("data-from"), to: group.getAttribute("data-to"), phase: phaseOf(group.getAttribute("data-to"))}));
      drawGeometry();
      refreshSelection();
      if (refit || reflow) fit(); else applyCamera();
      updateMotionMode();
      persist();
    }

    function select(id) {
      const node = visible.find(n => n.id === id) || graph.lookup.get(id);
      if (!node) return;
      if (node.kind === "more") {
        state.collapsed.delete(node.parent); state.expanded.add(node.parent);
        state.selected = node.parent; rebuild(true); return;
      }
      if (!nodeElements.has(id) && node.parent) {
        const current=graph.lookup.get(state.selected);
        const host=current?.kind==="topic"&&current.children.some(child=>child.id===id)?current.id:node.parent;
        state.collapsed.delete(host); state.expanded.add(host);
        // 从专题明细跳转时，清除会遮住目标题的筛选。
        state.query = ""; state.status = "all";
        syncControls(); rebuild(true);
      }
      state.selected = id;
      refreshSelection(); persist();
    }

    function toggleTopic(id) {
      if (state.collapsed.has(id)) { state.collapsed.delete(id); state.expanded.add(id); }
      else { state.collapsed.add(id); state.expanded.delete(id); }
      state.selected = id;
      state.query = ""; state.status = "all"; state.topic = "";
      syncControls(); rebuild(true);
    }

    function syncControls() {
      container.querySelector("#graph-search").value = state.query;
      container.querySelector("#graph-topic").value = state.topic;
      container.querySelector("#graph-status").value = state.status;
    }

    function local(event) {
      const rect = svg.getBoundingClientRect();
      return {x: event.clientX - rect.left, y: event.clientY - rect.top};
    }
    function world(p) { return {x: (p.x - camera.x) / camera.k, y: (p.y - camera.y) / camera.k}; }
    function zoom(k, center = {x: width / 2, y: height / 2}) {
      const base = cameraTarget || camera;
      const before = {x: (center.x - base.x) / base.k, y: (center.y - base.y) / base.k};
      const scale = clamp(k, .2, 3);
      moveCamera({k: scale, x: center.x - before.x * scale, y: center.y - before.y * scale});
      clearTimeout(saveTimer); saveTimer = setTimeout(persist, 180);
    }
    function scheduleGeometry() {
      if (running()) { wake(); return; }
      if (frame !== null) return;
      frame = requestAnimationFrame(() => { frame = null; if (!disposed) drawGeometry(); });
    }

    on(svg, "pointerdown", event => {
      if (event.button !== 0 && event.pointerType === "mouse") return;
      event.preventDefault();
      cameraTarget = null; panVelocity = null;
      const p = local(event);
      pointers.set(event.pointerId, p);
      svg.setPointerCapture(event.pointerId);
      if (pointers.size === 2) {
        const [a, b] = [...pointers.values()];
        gesture = {type: "pinch", distance: Math.max(1, Math.hypot(a.x - b.x, a.y - b.y)),
          k: camera.k, center: world({x: (a.x + b.x) / 2, y: (a.y + b.y) / 2}), moved: true};
        return;
      }
      const id = event.target.closest("[data-node]")?.getAttribute("data-node");
      const node = visible.find(n => n.id === id);
      if (node) {
        const dragged = node.kind === "topic" ? [id,...node.children.map(n=>n.id)] : [id];
        visible.filter(n => n.kind === "more" && n.parent === id).forEach(n => dragged.push(n.id));
        gesture = {type: "node", id, start: p, moved: false, positions: new Map(dragged.map(key => [key, {x: visualPoint(key).x, y: visualPoint(key).y}])),
          rest: new Map(graph.nodes.map(n => [n.id, {...point(n.id)}])), lastPoint: p, lastTime: performance.now(), velocity: {x: 0, y: 0}};
      } else gesture = {type: "pan", start: p, camera: {...camera}, moved: false, lastPoint: p, lastTime: performance.now(), velocity: {x: 0, y: 0}};
      svg.classList.add("is-dragging");
    });
    on(svg, "pointermove", event => {
      if (!pointers.has(event.pointerId) || !gesture) return;
      const p = local(event); pointers.set(event.pointerId, p);
      if (gesture.type === "pinch" && pointers.size >= 2) {
        const [a, b] = [...pointers.values()];
        camera.k = Math.max(.2, Math.min(3, gesture.k * Math.hypot(a.x - b.x, a.y - b.y) / gesture.distance));
        camera.x = (a.x + b.x) / 2 - gesture.center.x * camera.k;
        camera.y = (a.y + b.y) / 2 - gesture.center.y * camera.k;
        applyCamera(); return;
      }
      if (!gesture.start) return;
      const dx = p.x - gesture.start.x, dy = p.y - gesture.start.y;
      if (Math.hypot(dx, dy) > 4) gesture.moved = true;
      if (!gesture.moved) return;
      const now = performance.now();
      if (gesture.lastPoint) {
        const elapsed = Math.max(8, now - gesture.lastTime);
        const divisor = gesture.type === "node" ? camera.k : 1;
        gesture.velocity = {x: clamp((p.x - gesture.lastPoint.x) / elapsed * 16.67 / divisor, -12, 12),
          y: clamp((p.y - gesture.lastPoint.y) / elapsed * 16.67 / divisor, -12, 12)};
      }
      gesture.lastPoint = p; gesture.lastTime = now;
      if (gesture.type === "node") {
        for (const [id, start] of gesture.positions) {
          const target = {x: start.x + dx / camera.k, y: start.y + dy / camera.k};
          state.positions.set(id, target);
          if (id === gesture.id || !motionEnabled()) Object.assign(bodies.get(id) || {}, target);
        }
        scheduleGeometry();
      } else if (gesture.type === "pan") {
        camera.x = gesture.camera.x + dx; camera.y = gesture.camera.y + dy; applyCamera();
      }
    });
    function endPointer(event) {
      if (!pointers.has(event.pointerId)) return;
      const last = gesture;
      pointers.delete(event.pointerId);
      if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId);
      if (!pointers.size) {
        gesture = null; svg.classList.remove("is-dragging");
        if (motionEnabled() && last?.moved && event.type !== "pointercancel") {
          const fresh = performance.now() - (last.lastTime || 0) < 100;
          if (last.type === "node") {
            const body = bodies.get(last.id);
            body.vx = fresh ? last.velocity.x * .45 : 0;
            body.vy = fresh ? last.velocity.y * .45 : 0;
            body.releaseUntil = performance.now() + 650;
          } else if (last.type === "pan" && fresh) panVelocity = {...last.velocity};
        }
        if (event.type !== "pointercancel" && last && !last.moved && last.type === "node") {
          const now = performance.now();
          const doubleTap = lastTap?.id === last.id && now - lastTap.time < 400;
          if (doubleTap && graph.lookup.get(last.id)?.kind === "topic") toggleTopic(last.id);
          else if (doubleTap && last.id === ROOT) { fit(); persist(); }
          else select(last.id);
          lastTap = doubleTap ? null : {id: last.id, time: now};
        }
        drawGeometry(); persist(); wake();
      } else {
        const remaining = [...pointers.values()][0];
        gesture = {type: "pan", start: remaining, camera: {...camera}, moved: true,
          lastPoint: remaining, lastTime: performance.now(), velocity: {x: 0, y: 0}};
      }
    }
    on(svg, "pointerup", endPointer);
    on(svg, "pointercancel", endPointer);
    on(svg, "pointerover", event => { hoveredId = event.target.closest("[data-node]")?.getAttribute("data-node") || null; });
    on(svg, "pointerout", event => { hoveredId = event.relatedTarget?.closest?.("[data-node]")?.getAttribute("data-node") || null; });
    on(svg, "pointerleave", () => { hoveredId = null; });
    on(svg, "focusin", event => { focusedId = event.target.closest("[data-node]")?.getAttribute("data-node") || null; });
    on(svg, "focusout", () => { focusedId = null; });
    on(svg, "wheel", event => { event.preventDefault(); zoom((cameraTarget || camera).k * Math.exp(-event.deltaY * .0016), local(event)); }, {passive: false});
    on(svg, "keydown", event => {
      const id = event.target.closest("[data-node]")?.getAttribute("data-node");
      if ((event.key === "Enter" || event.key === " ") && id) { event.preventDefault(); select(id); }
      if (event.key === "+" || event.key === "=") { event.preventDefault(); zoom((cameraTarget || camera).k * 1.2); }
      if (event.key === "-") { event.preventDefault(); zoom((cameraTarget || camera).k / 1.2); }
      if (event.key === "0") { event.preventDefault(); fit(); persist(); }
      if (event.target === svg && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
        event.preventDefault();
        cameraTarget = null; panVelocity = null;
        camera.x += event.key === "ArrowLeft" ? 35 : event.key === "ArrowRight" ? -35 : 0;
        camera.y += event.key === "ArrowUp" ? 35 : event.key === "ArrowDown" ? -35 : 0;
        applyCamera(); persist();
      }
    });
    on(container, "click", event => {
      const selection = event.target.closest("[data-graph-select]");
      if (selection) { select(selection.getAttribute("data-graph-select")); return; }
      const control = event.target.closest("[data-graph-action]");
      if (!control || control.disabled) return;
      const action = control.getAttribute("data-graph-action");
      if (action === "motion") { state.motion = !state.motion; updateMotionMode(); persist(); }
      if (action === "zoom-in") zoom((cameraTarget || camera).k * 1.25);
      if (action === "zoom-out") zoom((cameraTarget || camera).k / 1.25);
      if (action === "fit") { fit(); persist(); }
      if (action === "layout") { ensurePositions(true); state.positions.forEach((_, id) => { if (id.startsWith("more:")) state.positions.delete(id); }); rebuild(true); }
      if (action === "collapse-all") {
        if (state.collapsed.size) { state.collapsed.clear(); graph.nodes.filter(n=>n.kind==="topic").forEach(n=>state.expanded.add(n.id)); }
        else { state.expanded.clear(); graph.nodes.filter(n=>n.kind==="topic").forEach(n=>state.collapsed.add(n.id)); }
        state.selected = ROOT; rebuild(true);
      }
      if (action === "toggle-topic") toggleTopic(control.getAttribute("data-topic-id"));
      if (action === "focus-topic") { state.topic = control.getAttribute("data-topic"); state.query = ""; state.status = "all"; syncControls(); rebuild(true); }
      if (action === "clear") { state.query = ""; state.topic = ""; state.status = "all"; state.selected = ROOT; syncControls(); rebuild(true); }
    });
    on(container.querySelector("#graph-search"), "input", event => { state.query = event.target.value; rebuild(true); });
    on(container.querySelector("#graph-topic"), "change", event => { state.topic = event.target.value; rebuild(true); });
    on(container.querySelector("#graph-status"), "change", event => { state.status = event.target.value; rebuild(true); });

    const sizeChanged = !state.size || Math.abs(width - state.size.width) > 30 || Math.abs(height - state.size.height) > 30;
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    rebuild(!state.camera || sizeChanged);
    svg.setAttribute("data-ready", "true");
    const observer = new ResizeObserver(() => {
      if (disposed || !stage.clientWidth || !stage.clientHeight) return;
      const changed = Math.abs(width - stage.clientWidth) > 2 || Math.abs(height - stage.clientHeight) > 2;
      width = stage.clientWidth; height = stage.clientHeight;
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      if (changed) { fit(); persist(); }
    });
    observer.observe(stage);
    const intersection = new IntersectionObserver(entries => {
      inViewport = entries[0].isIntersecting; updateMotionMode();
    }, {threshold: .02});
    intersection.observe(stage);
    const dialogObserver = new MutationObserver(() => {
      dialogOpen = Boolean(document.querySelector("dialog[open]")); updateMotionMode();
    });
    dialogObserver.observe(document.body, {subtree: true, attributes: true, attributeFilter: ["open"]});
    on(document, "visibilitychange", updateMotionMode);
    on(reducedMotion, "change", updateMotionMode);
    return {focusProblem(pid) { state.topic="";state.query="";state.status="all";syncControls();rebuild(false);select(`problem:${pid}`);fit();persist(); }, destroy() {
      disposed = true; abort.abort(); observer.disconnect();
      intersection.disconnect(); dialogObserver.disconnect();
      if (frame !== null) cancelAnimationFrame(frame);
      if (motionFrame !== null) cancelAnimationFrame(motionFrame);
      for (const node of visible) {
        const body = bodies.get(node.id);
        visualMemory.set(node.id, {x: body.x, y: body.y});
      }
      if (visualMemory.size > 3000) visualMemory.clear();
      clearTimeout(saveTimer); persist();
    }};
  }

  function setRelation(relation, focus) {
    if(!["topics","patterns","errors"].includes(relation)) return;
    const state=preferences();state.relation=relation;state.selected=focus||ROOT;state.topic="";state.query="";state.status="all";
    state.collapsed.clear();state.expanded.clear();persist();
  }
  return {page, mount, setRelation};
})();
