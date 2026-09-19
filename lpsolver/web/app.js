/* ============================================================
   GPU LP Solver — app.js (v3)
   ============================================================ */

"use strict";

// Global State
let fileText = "";
let allVars = [];
let filteredVars = [];
let currentPage = 1;
const PAGE_SIZE = 25;
let currentJobId = null;
let ws = null;
let convChart = null;
let currentFilterMode = "all"; // "all" | "nonzero"

// Helper
const qs = (id) => document.getElementById(id);

// DOM Elements
const dropZone = qs("drop-zone");
const fileInput = qs("model-file");
const fileLabel = qs("file-label");
const fileMeta = qs("file-meta");
const presetSel = qs("preset-select");
const cardHighs = qs("card-highs");
const cardGpu = qs("card-gpu");
const drawerBtn = qs("drawer-toggle");
const drawerArrow = qs("drawer-arrow");
const drawerBody = qs("drawer-body");
const iterSlider = qs("iter-slider");
const iterNum = qs("iterations");
const iterVal = qs("iter-val");
const checkSlider = qs("check-slider");
const checkNum = qs("check-every");
const checkVal = qs("check-val");
const solveBtn = qs("solve-btn");
const statusMsg = qs("status-msg");
const emptyState = qs("empty-state");
const results = qs("results");
const themeBtn = qs("theme-btn");
const themeIcon = qs("theme-icon");
const varSearch = qs("var-search");
const varSort = qs("var-sort");
const filterAll = qs("filter-all");
const filterNonzero = qs("filter-nonzero");
const sacBanner = qs("sac-banner");
const sacDismiss = qs("sac-dismiss");

// ── Theme Switcher ──────────────────────────────────────────
(function initTheme() {
  const saved = localStorage.getItem("theme") || "light";
  document.documentElement.setAttribute("data-theme", saved);
  if (themeIcon) {
    themeIcon.textContent = saved === "dark" ? "☀️" : "🌙";
  }
})();

if (themeBtn) {
  themeBtn.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
    if (themeIcon) themeIcon.textContent = next === "dark" ? "☀️" : "🌙";
    if (convChart) {
      updateChartTheme();
      convChart.update();
    }
  });
}

// ── Hardware Discovery ──────────────────────────────────────
async function loadCapabilities() {
  try {
    const res = await fetch("/api/v1/capabilities");
    const data = await res.json();
    const dot = qs("cluster-dot");
    const lbl = qs("cluster-label");

    if (data.gpuHardwareDetected) {
      const vramStr = data.vramTotalMB ? ` (${Math.round(data.vramTotalMB / 1024)} GB)` : "";
      if (lbl) lbl.textContent = `⚡ ${data.gpuDevice || "NVIDIA GPU"}${vramStr}`;
      if (dot) dot.className = "cluster-dot gpu";

      if (data.smartAppControlBlocked) {
        if (sacBanner) sacBanner.hidden = false;
        const desc = qs("gpu-description");
        if (desc) {
          desc.textContent = "PDHG First-Order iterative solver ready. (To unlock CuPy CUDA, toggle Windows Smart App Control off).";
        }
      } else if (data.gpuAvailable) {
        const desc = qs("gpu-description");
        if (desc) desc.textContent = "CuPy CUDA device acceleration active for massive sparse LP models.";
      }
    } else {
      if (dot) dot.className = "cluster-dot ok";
      if (lbl) lbl.textContent = "🖥️ CPU Ready (HiGHS)";
    }
  } catch (err) {
    const dot = qs("cluster-dot");
    const lbl = qs("cluster-label");
    if (dot) dot.className = "cluster-dot err";
    if (lbl) lbl.textContent = "Server Offline";
  }
}
loadCapabilities();

if (sacDismiss) {
  sacDismiss.addEventListener("click", () => {
    if (sacBanner) sacBanner.hidden = true;
  });
}

// ── Backend Selection Cards ─────────────────────────────────
[cardHighs, cardGpu].forEach((card) => {
  if (!card) return;
  card.addEventListener("click", (e) => {
    if (e.target.tagName.toLowerCase() === "summary" || e.target.closest("details ul")) {
      return;
    }
    document.querySelectorAll(".backend-card").forEach((c) => c.classList.remove("selected"));
    card.classList.add("selected");
    const radio = card.querySelector("input[type=radio]");
    if (radio) radio.checked = true;
  });
});

// ── Hyperparameter Drawer ───────────────────────────────────
if (drawerBtn && drawerBody) {
  drawerBtn.addEventListener("click", () => {
    const open = !drawerBody.hidden;
    drawerBody.hidden = open;
    if (drawerArrow) drawerArrow.classList.toggle("open", !open);
    drawerBtn.setAttribute("aria-expanded", String(!open));
  });
}

function syncSlider(slider, num, display, formatter) {
  if (!slider || !num || !display) return;
  slider.addEventListener("input", () => {
    num.value = slider.value;
    display.textContent = formatter(slider.value);
  });
  num.addEventListener("input", () => {
    slider.value = num.value;
    display.textContent = formatter(num.value);
  });
}
syncSlider(iterSlider, iterNum, iterVal, (v) => Number(v).toLocaleString());
syncSlider(checkSlider, checkNum, checkVal, (v) => v);

// ── Drag & Drop with Native Gzip Decompression ──────────────
if (dropZone && fileInput) {
  dropZone.addEventListener("click", () => fileInput.click());
  dropZone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  });
  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  });
}

async function handleFile(file) {
  const name = file.name.toLowerCase();
  if (file.size > 10 * 1024 * 1024) {
    toast("File exceeds 10 MB limit.", "error");
    return;
  }

  try {
    if (name.endsWith(".gz")) {
      toast("Decompressing .gz model in browser...", "info");
      const decompressedStream = file.stream().pipeThrough(new DecompressionStream("gzip"));
      fileText = await new Response(decompressedStream).text();
    } else {
      fileText = await file.text();
    }

    if (!fileText || !fileText.trim()) {
      toast("The selected file is empty.", "error");
      return;
    }

    if (fileLabel) fileLabel.textContent = file.name;
    if (fileMeta) fileMeta.textContent = `${(file.size / 1024).toFixed(1)} KB · Ready`;
    if (statusMsg) statusMsg.textContent = `Model "${file.name}" loaded. Click Solve.`;
    toast(`Loaded: ${file.name}`, "success");
    feedLog(`Ingested model file "${file.name}" (${(file.size / 1024).toFixed(1)} KB)`, "info");
  } catch (err) {
    toast(`Failed to read file: ${err.message}`, "error");
  }
}

// ── Preset Benchmarks ───────────────────────────────────────
if (presetSel) {
  presetSel.addEventListener("change", async () => {
    const val = presetSel.value;
    if (!val) return;
    try {
      const res = await fetch(`/api/v1/sample?preset=${val}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to load preset.");
      fileText = data.mpsText;
      if (fileLabel) fileLabel.textContent = data.filename;
      if (fileMeta) fileMeta.textContent = `${(data.mpsText.length / 1024).toFixed(1)} KB · Benchmark`;
      if (statusMsg) statusMsg.textContent = `Preset "${data.filename}" ready. Click Solve.`;
      toast(`Loaded preset: ${data.filename}`, "success");
      feedLog(`Loaded preset benchmark "${data.filename}"`, "info");
    } catch (err) {
      toast(`Preset error: ${err.message}`, "error");
    }
    presetSel.value = "";
  });
}

// ── Solve Execution ─────────────────────────────────────────
if (solveBtn) {
  solveBtn.addEventListener("click", async () => {
    if (!fileText || !fileText.trim()) {
      toast("Please upload a model file or choose a preset benchmark.", "warning");
      return;
    }

    const checkedBackend = document.querySelector("input[name=backend]:checked");
    const backend = checkedBackend ? checkedBackend.value : "highs";
    const maxIter = Number(iterNum ? iterNum.value : 50000);
    const tolerance = Number(qs("tolerance") ? qs("tolerance").value : 1e-5);
    const checkEvery = Number(checkNum ? checkNum.value : 100);

    solveBtn.disabled = true;
    solveBtn.textContent = "⏳ Optimizing…";
    if (statusMsg) {
      statusMsg.textContent = backend === "gpu"
        ? "Running PDHG first-order solver on model…"
        : "Running CPU HiGHS solver…";
    }

    resetChart();
    feedLog(`Dispatched ${backend.toUpperCase()} solver task…`, "info");

    try {
      const res = await fetch("/api/v1/solve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mpsText: fileText,
          backend,
          maxIterations: maxIter,
          tolerance,
          checkEvery,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Solver error.");

      currentJobId = data.job_id;
      feedLog(`Task queued with Job ID ${currentJobId.slice(0, 8)}`, "info");
      openWebSocket(currentJobId, backend);
    } catch (err) {
      toast(`Submission error: ${err.message}`, "error");
      if (statusMsg) statusMsg.textContent = `Error: ${err.message}`;
      feedLog(`Job execution aborted: ${err.message}`, "err");
      solveBtn.disabled = false;
      solveBtn.textContent = "⚡ Solve Model";
    }
  });
}

// ── WebSocket Live Streaming ────────────────────────────────
function openWebSocket(jobId, backend) {
  if (ws) {
    try { ws.close(); } catch (_) {}
  }
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const wsUrl = `${protocol}://${location.host}/api/v1/ws/solver/${jobId}`;
  ws = new WebSocket(wsUrl);

  ws.addEventListener("open", () => {
    feedLog("Live telemetry channel connected", "info");
  });

  ws.addEventListener("message", (e) => {
    try {
      const msg = JSON.parse(e.data);

      if (msg.type === "status") {
        if (qs("stat-queue")) qs("stat-queue").textContent = msg.queueDepth ?? "0";
      }

      if (msg.type === "progress") {
        if (qs("stat-iters")) qs("stat-iters").textContent = msg.iteration.toLocaleString();
        if (qs("stat-feas") && msg.feasibility != null) {
          qs("stat-feas").textContent = msg.feasibility.toExponential(2);
        }
        pushChartPoint(msg.iteration, msg.objective);
      }

      if (msg.type === "result") {
        const payload = msg.payload;
        if (payload.status === "completed") {
          renderResult(payload);
          toast("Optimization completed!", "success");
          feedLog(`Optimal solution found! Obj = ${fmt(payload.result && payload.result.objective)}`, "ok");
          if (statusMsg) statusMsg.textContent = "Optimization completed successfully.";
        } else {
          toast(`Solver error: ${payload.error || "Unknown issue"}`, "error");
          feedLog(`Solver error: ${payload.error || "Unknown issue"}`, "err");
          if (statusMsg) statusMsg.textContent = `Error: ${payload.error || "Unknown issue"}`;
        }
        solveBtn.disabled = false;
        solveBtn.textContent = "⚡ Solve Model";
        try { ws.close(); } catch (_) {}
      }

      if (msg.type === "error") {
        toast(`WebSocket error: ${msg.message}`, "error");
        solveBtn.disabled = false;
        solveBtn.textContent = "⚡ Solve Model";
      }
    } catch (parseErr) {
      console.error("WS parse error:", parseErr);
    }
  });

  ws.addEventListener("close", () => {
    if (solveBtn && solveBtn.disabled) {
      solveBtn.disabled = false;
      solveBtn.textContent = "⚡ Solve Model";
    }
  });

  ws.addEventListener("error", () => {
    feedLog("WebSocket disconnected. Checking HTTP endpoint...", "warn");
    pollJobStatus(jobId);
  });
}

// Fallback polling
async function pollJobStatus(jobId) {
  const pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`/api/v1/jobs/${jobId}`);
      if (!res.ok) throw new Error("Status check failed");
      const job = await res.json();
      if (job.status === "completed") {
        clearInterval(pollTimer);
        renderResult(job);
        toast("Optimization completed!", "success");
        feedLog("Job completed successfully", "ok");
        if (statusMsg) statusMsg.textContent = "Solve completed.";
        solveBtn.disabled = false;
        solveBtn.textContent = "⚡ Solve Model";
      } else if (job.status === "failed") {
        clearInterval(pollTimer);
        toast(`Solve failed: ${job.error}`, "error");
        feedLog(`Solver error: ${job.error}`, "err");
        if (statusMsg) statusMsg.textContent = `Error: ${job.error}`;
        solveBtn.disabled = false;
        solveBtn.textContent = "⚡ Solve Model";
      }
    } catch (err) {
      clearInterval(pollTimer);
      solveBtn.disabled = false;
      solveBtn.textContent = "⚡ Solve Model";
    }
  }, 1000);
}

// ── Render Results ──────────────────────────────────────────
function renderResult(job) {
  if (emptyState) emptyState.hidden = true;
  if (results) results.hidden = false;

  const model = job.model || {};
  const result = job.result || {};

  if (qs("model-name")) {
    qs("model-name").textContent = `${model.name || "Model"} (${(model.rows || 0).toLocaleString()} constraints × ${(model.columns || 0).toLocaleString()} variables)`;
  }

  const badge = qs("result-status-badge");
  const s = (result.status || "unknown").toLowerCase();
  if (badge) {
    badge.textContent = s.toUpperCase();
    badge.className = "status-badge";
    if (s === "optimal" || s === "approximate") {
      badge.classList.remove("warning", "error");
    } else if (s.includes("infeasible") || s.includes("unbounded") || s === "failed") {
      badge.classList.add("error");
    } else {
      badge.classList.add("warning");
    }
  }

  if (qs("m-objective")) qs("m-objective").textContent = fmt(result.objective);
  if (qs("m-status")) qs("m-status").textContent = result.status || "—";
  if (qs("m-time")) {
    qs("m-time").textContent = result.elapsed_sec != null
      ? `${(result.elapsed_sec * 1000).toFixed(2)} ms`
      : "—";
  }

  if (qs("m-gpu")) {
    qs("m-gpu").textContent = result.solver || (result.device ? result.device : "HiGHS (CPU)");
  }

  const gpuDetails = qs("gpu-details");
  if (gpuDetails) {
    if (result.iterations != null) {
      gpuDetails.hidden = false;
      gpuDetails.innerHTML =
        `<b>Solver Engine:</b> ${escHtml(result.solver || "PDHG")} &nbsp;|&nbsp; ` +
        `<b>Iterations:</b> ${(result.iterations || 0).toLocaleString()} &nbsp;|&nbsp; ` +
        `<b>Max Violation:</b> ${fmt(result.max_constraint_violation)}`;
    } else {
      gpuDetails.hidden = false;
      gpuDetails.innerHTML =
        `<b>Solver Engine:</b> HiGHS Reference (Exact Simplex/Interior-Point) &nbsp;|&nbsp; ` +
        `<b>Nonzeros:</b> ${(model.nonzeros || 0).toLocaleString()}`;
    }
  }

  // Draw chart for CPU HiGHS if only 1 point was received
  if (result.objective != null && (!convChart || convChart.data.labels.length <= 1)) {
    pushChartPoint(0, result.objective * 1.05);
    pushChartPoint(1, result.objective);
  }

  // Variables Table
  allVars = (job.variables || []).map((v) => ({
    name: v.name,
    value: v.value,
    reduced_cost: v.reduced_cost ?? 0.0,
    type: v.type || "Continuous",
  }));

  if (qs("var-count")) {
    qs("var-count").textContent = `(${allVars.length.toLocaleString()} total)`;
  }

  applyTableFilters();
}

// ── Variable Filtering & Sorting ────────────────────────────
function applyTableFilters() {
  const query = (varSearch ? varSearch.value : "").toLowerCase().trim();
  const sort = varSort ? varSort.value : "name-asc";

  filteredVars = allVars.filter((v) => {
    if (query && !v.name.toLowerCase().includes(query)) return false;
    if (currentFilterMode === "nonzero" && Math.abs(v.value) <= 1e-7) return false;
    return true;
  });

  filteredVars.sort((a, b) => {
    if (sort === "name-asc") return a.name.localeCompare(b.name);
    if (sort === "name-desc") return b.name.localeCompare(a.name);
    if (sort === "val-desc") return b.value - a.value;
    if (sort === "val-asc") return a.value - b.value;
    if (sort === "rc-desc") return b.reduced_cost - a.reduced_cost;
    return 0;
  });

  currentPage = 1;
  renderTablePage();
}

if (varSearch) varSearch.addEventListener("input", applyTableFilters);
if (varSort) varSort.addEventListener("change", applyTableFilters);

if (filterAll && filterNonzero) {
  filterAll.addEventListener("click", () => {
    currentFilterMode = "all";
    filterAll.classList.add("active");
    filterNonzero.classList.remove("active");
    applyTableFilters();
  });
  filterNonzero.addEventListener("click", () => {
    currentFilterMode = "nonzero";
    filterNonzero.classList.add("active");
    filterAll.classList.remove("active");
    applyTableFilters();
  });
}

function renderTablePage() {
  const tbody = qs("var-tbody");
  if (!tbody) return;

  const start = (currentPage - 1) * PAGE_SIZE;
  const page = filteredVars.slice(start, start + PAGE_SIZE);

  if (!page.length) {
    tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text3);text-align:center;padding:24px">No variables matched the current filters.</td></tr>';
  } else {
    tbody.innerHTML = page.map((v) =>
      `<tr>
        <td><strong>${escHtml(v.name)}</strong></td>
        <td><span style="color:var(--text3);font-size:11.5px">${escHtml(v.type)}</span></td>
        <td class="right">${fmt(v.value)}</td>
        <td class="right" style="color:var(--text2)">${fmt(v.reduced_cost)}</td>
      </tr>`
    ).join("");
  }

  renderPagination();
}

function renderPagination() {
  const pg = qs("pagination");
  if (!pg) return;

  const total = Math.ceil(filteredVars.length / PAGE_SIZE);
  if (total <= 1) {
    pg.innerHTML = "";
    return;
  }

  let html = "";
  pagesToShow(currentPage, total).forEach((p) => {
    if (p === "…") {
      html += '<span style="padding:5px 6px;color:var(--text3)">…</span>';
    } else {
      html += `<button class="page-btn${p === currentPage ? " active" : ""}" data-page="${p}">${p}</button>`;
    }
  });
  pg.innerHTML = html;

  pg.querySelectorAll(".page-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      currentPage = Number(btn.dataset.page);
      renderTablePage();
    });
  });
}

function pagesToShow(cur, total) {
  if (total <= 7) {
    const arr = [];
    for (let i = 1; i <= total; i++) arr.push(i);
    return arr;
  }
  const out = [1];
  if (cur > 3) out.push("…");
  for (let i = Math.max(2, cur - 1); i <= Math.min(total - 1, cur + 1); i++) {
    out.push(i);
  }
  if (cur < total - 2) out.push("…");
  out.push(total);
  return out;
}

// ── Chart.js Convergence Curve ──────────────────────────────
function resetChart() {
  if (convChart) {
    convChart.destroy();
    convChart = null;
  }
}

function pushChartPoint(iteration, objective) {
  const canvas = qs("conv-chart");
  if (!canvas) return;

  if (!convChart) {
    const ctx = canvas.getContext("2d");
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    const grid = dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)";
    const tick = dark ? "#8cb0c9" : "#688599";

    convChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [{
          label: "Objective Value",
          data: [],
          borderColor: "#0aa1a6",
          backgroundColor: "rgba(10,161,166,0.12)",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.3,
          fill: true,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: {
          legend: { display: false },
          tooltip: { mode: "index", intersect: false },
        },
        scales: {
          x: {
            title: { display: true, text: "Iteration", color: tick, font: { size: 11 } },
            ticks: { color: tick, maxTicksLimit: 8, font: { size: 11 } },
            grid: { color: grid },
          },
          y: {
            title: { display: true, text: "Objective Value", color: tick, font: { size: 11 } },
            ticks: { color: tick, font: { size: 11 } },
            grid: { color: grid },
          },
        },
      },
    });
  }

  if (objective == null) return;
  convChart.data.labels.push(iteration);
  convChart.data.datasets[0].data.push(objective);
  convChart.update("none");
}

function updateChartTheme() {
  if (!convChart) return;
  const dark = document.documentElement.getAttribute("data-theme") === "dark";
  const grid = dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)";
  const tick = dark ? "#8cb0c9" : "#688599";
  ["x", "y"].forEach((axis) => {
    if (convChart.options.scales[axis]) {
      convChart.options.scales[axis].ticks.color = tick;
      convChart.options.scales[axis].grid.color = grid;
      convChart.options.scales[axis].title.color = tick;
    }
  });
}

// ── Export Handling ─────────────────────────────────────────
const exportCsvBtn = qs("export-csv");
const exportJsonBtn = qs("export-json");

if (exportCsvBtn) exportCsvBtn.addEventListener("click", () => exportFile("csv"));
if (exportJsonBtn) exportJsonBtn.addEventListener("click", () => exportFile("json"));

async function exportFile(format) {
  if (!currentJobId) {
    toast("No solved optimization job to export.", "warning");
    return;
  }
  try {
    const res = await fetch(`/api/v1/jobs/${currentJobId}/export?format=${format}`);
    if (!res.ok) throw new Error("Export download failed.");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `solution_${currentJobId.slice(0, 8)}.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    toast(`Exported solution as .${format.toUpperCase()}`, "success");
    feedLog(`Exported solution (.${format})`, "ok");
  } catch (err) {
    toast(`Export error: ${err.message}`, "error");
  }
}

// ── Sidebar Feed Log ────────────────────────────────────────
function feedLog(msg, type = "info") {
  const log = qs("feed-log");
  if (!log) return;
  const idle = log.querySelector(".feed-idle");
  if (idle) idle.remove();

  const item = document.createElement("div");
  item.className = `feed-item feed-${type}`;
  item.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
  log.prepend(item);

  const items = log.querySelectorAll(".feed-item");
  for (let i = 35; i < items.length; i++) {
    items[i].remove();
  }
}

// ── Notification Toast Manager ──────────────────────────────
function toast(msg, type = "info", durationMs = 3500) {
  const container = qs("toasts");
  if (!container) return;

  const icons = { success: "✓", warning: "⚠", error: "✕", info: "ℹ" };
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${icons[type] || "ℹ"}</span><span>${escHtml(msg)}</span>`;
  container.appendChild(el);

  setTimeout(() => {
    el.classList.add("out");
    el.addEventListener("animationend", () => el.remove());
  }, durationMs);
}

// ── Formatting Utilities ────────────────────────────────────
function fmt(val) {
  if (val == null || !Number.isFinite(val)) return "—";
  return Number(val).toPrecision(8);
}

function escHtml(str) {
  const div = document.createElement("span");
  div.textContent = String(str);
  return div.innerHTML;
}
