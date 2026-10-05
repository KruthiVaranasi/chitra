const $ = (id) => document.getElementById(id);
const grid = $("grid"), statusEl = $("status"), empty = $("empty"), viewer = $("viewer");
let results = [], current = -1;

async function api(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}

function yearParams() {
  const p = new URLSearchParams();
  if ($("year-from").value) p.set("year_from", $("year-from").value);
  if ($("year-to").value) p.set("year_to", $("year-to").value);
  return p;
}

async function run(label, request) {
  statusEl.textContent = "Searching…";
  empty.hidden = true;
  const t0 = performance.now();
  try {
    results = (await request()).results;
    const ms = Math.round(performance.now() - t0);
    statusEl.textContent = results.length ? `${results.length} results for ${label} · ${ms} ms` : `No results for ${label}`;
    render();
  } catch (e) {
    statusEl.textContent = `Error: ${e.message}`;
  }
}

function searchText(q) {
  q = q.trim();
  if (!q) return;
  const p = yearParams();
  p.set("q", q);
  history.replaceState(null, "", "?q=" + encodeURIComponent(q));
  run(`“${q}”`, () => api("/api/search?" + p));
}

function searchFile(file) {
  if (!file || !file.type.startsWith("image/")) return;
  const body = new FormData();
  body.append("file", file);
  run(`your image`, () => api("/api/search-image", { method: "POST", body }));
}

function searchSimilar(item) {
  viewer.close();
  run(`photos similar to ${item.path.split("/").pop()}`, () => api(`/api/similar/${item.id}`));
}

function render() {
  grid.replaceChildren(...results.map((r, i) => {
    const tile = document.createElement("button");
    tile.className = "tile";
    tile.title = r.path;
    tile.innerHTML = `<img loading="lazy" alt="" src="/api/thumb/${r.id}"><span class="badge"></span>`;
    tile.querySelector(".badge").textContent = [r.taken_at?.slice(0, 10), r.score.toFixed(2)].filter(Boolean).join(" · ");
    tile.onclick = () => openViewer(i);
    return tile;
  }));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function openViewer(i) {
  current = i;
  const r = results[i];
  $("viewer-img").src = `/api/image/${r.id}`;
  $("viewer-path").textContent = r.path;
  const info = {
    Taken: r.taken_at ? new Date(r.taken_at).toLocaleString() : "Unknown",
    Size: r.width && r.height ? `${r.width} × ${r.height}` : "—",
    File: `${(r.size / 1048576).toFixed(1)} MB`,
    Match: r.score.toFixed(3),
  };
  $("viewer-info").replaceChildren(...Object.entries(info).flatMap(([k, v]) => {
    const dt = document.createElement("dt"), dd = document.createElement("dd");
    dt.textContent = k; dd.textContent = v;
    return [dt, dd];
  }));
  $("btn-original").href = `/api/image/${r.id}`;
  if (!viewer.open) viewer.showModal();
}

$("search-form").onsubmit = (e) => { e.preventDefault(); searchText($("q").value); };
$("file").onchange = (e) => searchFile(e.target.files[0]);
document.querySelectorAll(".chips button").forEach((b) => b.onclick = () => { $("q").value = b.textContent; searchText(b.textContent); });
$("btn-close").onclick = () => viewer.close();
$("btn-similar").onclick = () => searchSimilar(results[current]);
$("btn-open").onclick = () => api(`/api/open/${results[current].id}`, { method: "POST" }).catch((e) => alert(e.message));
viewer.onclick = (e) => { if (e.target === viewer) viewer.close(); };
document.addEventListener("keydown", (e) => {
  if (!viewer.open) return;
  if (e.key === "ArrowRight" && current < results.length - 1) openViewer(current + 1);
  if (e.key === "ArrowLeft" && current > 0) openViewer(current - 1);
});

// Drag an image anywhere onto the page to search by example.
const dz = $("dropzone");
let depth = 0;
addEventListener("dragenter", (e) => { if (e.dataTransfer.types.includes("Files")) { depth++; dz.classList.add("on"); } });
addEventListener("dragleave", () => { if (--depth <= 0) { depth = 0; dz.classList.remove("on"); } });
addEventListener("dragover", (e) => e.preventDefault());
addEventListener("drop", (e) => {
  e.preventDefault(); depth = 0; dz.classList.remove("on");
  searchFile(e.dataTransfer.files[0]);
});

api("/api/stats").then((s) => {
  const folder = s.root.replace(/[\\/]+$/, "").split(/[\\/]/).pop() || s.root;
  $("meta").textContent = `${s.count.toLocaleString()} photos · ${folder}`;
  $("meta").title = s.root;
  const q = new URLSearchParams(location.search).get("q");
  if (q) { $("q").value = q; searchText(q); }
}).catch(() => { $("meta").textContent = "Not connected"; });
