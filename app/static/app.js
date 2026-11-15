"use strict";

const API = "/api/v1";
const ROLE_RANK = { VIEWER: 0, EDITOR: 1, ADMIN: 2 };
const state = { token: sessionStorage.getItem("govlens_token"), me: null, sources: [], jobTimer: null };
const $ = (selector) => document.querySelector(selector);

// ---------- helpers ----------

function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (value !== null && value !== undefined && value !== false) node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child !== null && child !== undefined) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function pill(value) { return el("span", { class: `pill ${value}` }, value); }

function toast(message, ms = 4000) {
  const box = $("#toast");
  box.textContent = message;
  box.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (box.hidden = true), ms);
}

function formatDate(value) { return value ? new Date(value).toLocaleString() : "—"; }

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.json);
  }
  const response = await fetch(API + path, { ...options, headers });
  if (response.status === 401 && path !== "/auth/login") {
    signOut(false);
    throw new Error("Your session has ended. Please sign in again.");
  }
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try { const body = await response.json(); detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail); } catch (_) { /* not JSON */ }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  if (response.status === 204) return null;
  return options.raw ? response : response.json();
}

// Escape first, then apply a small markdown subset, then turn [S1] tags into clickable chips.
function renderMarkdown(markdown) {
  const lines = escapeHtml(markdown).split("\n");
  let html = "", inList = false;
  const inline = (text) => text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[((?:S\d+)(?:\s*,\s*S\d+)*)\]/g, (_, group) =>
      group.split(/\s*,\s*/).map((label) => `<span class="tag" data-label="${label}">${label}</span>`).join(" "));
  for (const raw of lines) {
    const line = raw.trim();
    const bullet = line.match(/^[-*•]\s+(.*)/);
    if (bullet) { if (!inList) { html += "<ul>"; inList = true; } html += `<li>${inline(bullet[1])}</li>`; continue; }
    if (inList) { html += "</ul>"; inList = false; }
    if (!line || /^-{3,}$/.test(line)) continue;
    const heading = line.match(/^#{1,6}\s+(.*)/);
    html += heading ? `<p><strong>${inline(heading[1])}</strong></p>` : `<p>${inline(line)}</p>`;
  }
  return html + (inList ? "</ul>" : "");
}

// ---------- session ----------

async function signIn(event) {
  event.preventDefault();
  $("#login-error").textContent = "";
  try {
    const result = await api("/auth/login", { method: "POST", json: { username: $("#login-username").value, password: $("#login-password").value } });
    state.token = result.access_token;
    sessionStorage.setItem("govlens_token", state.token);
    $("#login-password").value = "";
    await start();
  } catch (error) {
    $("#login-error").textContent = error.message;
  }
}

function signOut(callServer = true) {
  if (callServer && state.token) fetch(API + "/auth/logout", { method: "POST", headers: { Authorization: `Bearer ${state.token}` } });
  state.token = null;
  state.me = null;
  sessionStorage.removeItem("govlens_token");
  clearInterval(state.jobTimer);
  $("#app-view").hidden = true;
  $("#login-view").hidden = false;
}

async function start() {
  if (!state.token) { $("#login-view").hidden = false; return; }
  try {
    state.me = await api("/auth/me");
  } catch (_) {
    signOut(false);
    return;
  }
  $("#who").textContent = `${state.me.username} (${state.me.role.toLowerCase()})`;
  for (const button of document.querySelectorAll("nav [data-role]")) {
    button.hidden = ROLE_RANK[state.me.role] < ROLE_RANK[button.dataset.role];
  }
  $("#password-button").hidden = state.me.via !== "session";
  $("#login-view").hidden = true;
  $("#app-view").hidden = false;
  showTab("ask");
}

function can(role) { return state.me && ROLE_RANK[state.me.role] >= ROLE_RANK[role]; }

function showTab(name) {
  for (const button of document.querySelectorAll("nav button")) button.classList.toggle("active", button.dataset.tab === name);
  for (const section of document.querySelectorAll(".tab")) section.hidden = section.id !== `tab-${name}`;
  clearInterval(state.jobTimer);
  if (name === "documents") loadDocuments();
  if (name === "compare") loadCompareOptions();
  if (name === "upload") { loadJobs(); state.jobTimer = setInterval(loadJobs, 4000); }
  if (name === "users") loadUsers();
}

// ---------- ask ----------

async function ask(event) {
  event.preventDefault();
  const question = $("#question").value.trim();
  if (!question) return;
  const numbers = $("#filter-numbers").value.split(",").map((s) => s.trim()).filter(Boolean);
  const button = $("#ask-button");
  button.disabled = true;
  $("#answer-area").hidden = false;
  $("#answer").innerHTML = "";
  $("#verification").hidden = true;
  $("#supersession-banner").hidden = true;
  $("#source-list").innerHTML = "";
  $("#source-text").hidden = true;
  state.sources = [];
  setStatus("Searching the documents…", true);
  let text = "";
  const started = performance.now();
  try {
    const response = await api("/query/stream", { method: "POST", json: { query: question, top_k: Number($("#top-k").value), document_numbers: numbers }, raw: true });
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const event = (block.match(/^event: (.*)$/m) || [])[1];
        const data = JSON.parse((block.match(/^data: (.*)$/m) || [, "{}"])[1]);
        if (event === "retrieval") {
          showSupersession(data.supersession_warnings || []);
          setStatus(data.retrieved_chunks ? `Reading ${data.retrieved_chunks} passage(s) from ${data.documents} document(s) and writing the answer…` : "No relevant passages found.", Boolean(data.retrieved_chunks));
        } else if (event === "token") {
          text += data.text;
          $("#answer").innerHTML = renderMarkdown(text);
        } else if (event === "done") {
          showResult(data, performance.now() - started);
        } else if (event === "error") {
          throw new Error(data.detail);
        }
      }
    }
  } catch (error) {
    setStatus("");
    $("#answer").innerHTML = "";
    $("#answer").append(el("div", { class: "banner bad" }, error.message));
  } finally {
    button.disabled = false;
  }
}

function setStatus(message, busy = false) {
  const status = $("#answer-status");
  status.innerHTML = "";
  if (busy) status.append(el("span", { class: "spinner" }));
  status.append(message);
}

function showSupersession(warnings) {
  const banner = $("#supersession-banner");
  const superseded = warnings.filter((w) => w.is_superseded);
  banner.hidden = !superseded.length;
  banner.textContent = superseded.map((w) => `Document ${w.document_number} has been superseded; the latest version is ${w.latest_document_number}.`).join(" ");
}

function showResult(result, elapsedMs) {
  setStatus(`Answered in ${(elapsedMs / 1000).toFixed(1)} s.`);
  $("#answer").innerHTML = renderMarkdown(result.answer_markdown);
  showSupersession(result.supersession_warnings || []);
  state.sources = result.sources || [];
  const list = $("#source-list");
  list.innerHTML = "";
  if (!state.sources.length) list.append(el("li", { class: "muted" }, "No sources cited."));
  for (const source of state.sources) {
    list.append(el("li", {},
      el("span", { class: "tag", "data-label": source.label }, source.label || "•"), " ",
      source.citation_text.replace(/\n/g, ", ")));
  }
  if (result.citations_inferred) list.append(el("li", { class: "muted" }, "The answer did not tag its sources, so every retrieved source is listed."));
  showVerification(result.verification);
}

function showVerification(report) {
  const box = $("#verification");
  box.innerHTML = "";
  if (!report || !report.checked) { box.hidden = true; return; }
  box.hidden = false;
  if (report.all_supported) {
    box.append(el("div", { class: "banner ok" }, `All ${report.checked} statement(s) were found in the cited pages.`));
    return;
  }
  const problems = report.sentences.filter((s) => s.status !== "SUPPORTED");
  box.append(el("div", { class: "banner bad" }, `${problems.length} of ${report.checked} statement(s) could not be confirmed in the cited pages. Check them before relying on this answer.`));
  box.append(el("ul", { class: "plain" }, problems.map((s) => el("li", {}, pill(s.status), " ", s.text, el("div", { class: "muted" }, s.reason || "")))));
}

async function showSource(label) {
  const source = state.sources.find((s) => s.label === label);
  for (const tag of document.querySelectorAll(".tag")) tag.classList.toggle("active", tag.dataset.label === label);
  const box = $("#source-text");
  if (!source) { box.hidden = false; box.textContent = "This tag does not match a cited source."; return; }
  box.hidden = false;
  box.textContent = "Loading…";
  try {
    const page = await api(`/documents/${source.document_id}/pages/${source.page_number}`);
    box.textContent = `${source.citation_text.replace(/\n/g, ", ")}\n\n${page.text}`;
  } catch (error) {
    box.textContent = error.message;
  }
}

// ---------- documents ----------

async function loadDocuments() {
  const params = new URLSearchParams({ limit: "200" });
  if ($("#doc-search").value.trim()) params.set("search", $("#doc-search").value.trim());
  if ($("#doc-status").value) params.set("status", $("#doc-status").value);
  const tbody = $("#doc-table tbody");
  try {
    const page = await api(`/documents?${params}`);
    tbody.innerHTML = "";
    if (!page.items.length) tbody.append(el("tr", {}, el("td", { colspan: 6, class: "muted" }, "No documents yet.")));
    for (const doc of page.items) {
      tbody.append(el("tr", { class: "clickable", onclick: () => showDocument(doc.id) },
        el("td", {}, doc.document_number || "—"), el("td", {}, doc.document_type), el("td", {}, doc.title),
        el("td", {}, doc.issue_date || "—"), el("td", {}, pill(doc.status)), el("td", {}, doc.chunk_count)));
    }
  } catch (error) { toast(error.message); }
}

async function showDocument(id) {
  const box = $("#doc-detail");
  box.hidden = false;
  box.textContent = "Loading…";
  try {
    const doc = await api(`/documents/${id}`);
    const linkList = (items, verb) => items.length
      ? el("ul", { class: "plain" }, items.map((r) => el("li", {}, `${verb(r.relationship_type)} ${r.document_type.toLowerCase()} ${r.document_number || r.document_id} `, pill(r.status),
          r.origin === "MANUAL" ? el("span", { class: "muted" }, " (added manually)") : null,
          can("EDITOR") ? el("button", { class: "link", onclick: () => removeLink(r.relationship_id, id) }, "remove") : null)))
      : el("p", { class: "muted" }, "None");
    box.innerHTML = "";
    box.append(...[
      el("h3", {}, `${doc.document_type} ${doc.document_number || ""} — ${doc.title}`),
      el("p", {}, pill(doc.status), ` Issued ${doc.issue_date || "(date not found)"} · ${doc.department || "department not found"} · ${doc.page_count} page(s), ${doc.chunk_count} chunk(s)`),
      doc.subject ? el("p", {}, el("strong", {}, "Subject: "), doc.subject) : null,
      el("h3", {}, "This document…"), linkList(doc.outgoing, (t) => ({ SUPERSEDES: "supersedes", AMENDS: "amends", REFERENCES: "references" })[t]),
      el("h3", {}, "Other documents…"), linkList(doc.incoming, (t) => ({ SUPERSEDES: "superseded by", AMENDS: "amended by", REFERENCES: "referenced by" })[t]),
      doc.pending_references.length ? el("p", { class: "muted" }, `Mentions not yet ingested: ${doc.pending_references.map((p) => p.referenced_number).join(", ")}`) : null,
      can("EDITOR") ? el("div", { class: "row" },
        el("button", { onclick: () => addLink(doc) }, "Add link"),
        el("button", { onclick: () => reingest(doc.id) }, "Re-ingest"),
        el("button", { class: "danger", onclick: () => deleteDocument(doc) }, "Delete")) : null,
    ].filter(Boolean));
  } catch (error) { box.textContent = error.message; }
}

async function deleteDocument(doc) {
  if (!confirm(`Delete ${doc.document_number || doc.title}? Its chunks, vectors, and links are removed.`)) return;
  try { await api(`/documents/${doc.id}`, { method: "DELETE" }); toast("Document deleted."); $("#doc-detail").hidden = true; loadDocuments(); }
  catch (error) { toast(error.message); }
}

async function reingest(id) {
  toast("Re-ingesting… this can take a while for scanned files.", 8000);
  try { const result = await api(`/documents/${id}/reingest`, { method: "POST" }); toast("Re-ingested."); loadDocuments(); showDocument(result.document_id); }
  catch (error) { toast(error.message); }
}

async function removeLink(relationshipId, documentId) {
  if (!confirm("Remove this link?")) return;
  try { await api(`/documents/relationships/${relationshipId}`, { method: "DELETE" }); showDocument(documentId); loadDocuments(); }
  catch (error) { toast(error.message); }
}

async function addLink(doc) {
  const others = (await api("/documents?limit=500")).items.filter((d) => d.id !== doc.id);
  const target = el("select", {}, others.map((d) => el("option", { value: d.id }, `${d.document_number || d.title} (${d.document_type.toLowerCase()})`)));
  const type = el("select", {}, ["SUPERSEDES", "AMENDS", "REFERENCES"].map((t) => el("option", {}, t)));
  const ok = await openDialog(`Link from ${doc.document_number || doc.title}`, [el("label", {}, "This document", type), el("label", {}, "Other document", target)]);
  if (!ok) return;
  try { await api(`/documents/${doc.id}/relationships`, { method: "POST", json: { target_document_id: target.value, relationship_type: type.value } }); showDocument(doc.id); loadDocuments(); }
  catch (error) { toast(error.message); }
}

// ---------- compare ----------

async function loadCompareOptions() {
  try {
    const docs = (await api("/documents?limit=500")).items;
    for (const select of [$("#compare-base"), $("#compare-target")]) {
      const previous = select.value;
      select.innerHTML = "";
      for (const d of docs) select.append(el("option", { value: d.id }, `${d.document_number || d.title} — ${d.issue_date || "undated"}`));
      if (previous) select.value = previous;
    }
    if (docs.length > 1 && $("#compare-base").value === $("#compare-target").value) $("#compare-target").selectedIndex = 1;
  } catch (error) { toast(error.message); }
}

async function compare(event) {
  event.preventDefault();
  const button = $("#compare-button");
  button.disabled = true;
  $("#compare-result").hidden = false;
  $("#compare-heading").innerHTML = "";
  $("#compare-heading").append(el("span", { class: "spinner" }), "Comparing…");
  $("#compare-summary-text").innerHTML = "";
  $("#change-table tbody").innerHTML = "";
  try {
    const result = await api("/compare", { method: "POST", json: { base: $("#compare-base").value, target: $("#compare-target").value, focus: $("#compare-focus").value || null, summarize: $("#compare-summary").checked } });
    $("#compare-heading").innerHTML = "";
    $("#compare-heading").append(
      el("h3", {}, `${result.base.document_number || result.base.title} → ${result.target.document_number || result.target.title}`),
      el("p", { class: "muted" }, `${result.modified} modified, ${result.added} added, ${result.removed} removed, ${result.unchanged_sentences} unchanged sentence(s).` + (result.relationship ? ` Stored link: ${result.relationship}.` : "")));
    if (result.summary_markdown) $("#compare-summary-text").innerHTML = renderMarkdown(result.summary_markdown);
    const tbody = $("#change-table tbody");
    if (!result.changes.length) tbody.append(el("tr", {}, el("td", { colspan: 3, class: "muted" }, "No differences.")));
    for (const c of result.changes) {
      tbody.append(el("tr", {}, el("td", {}, pill(c.change_type)),
        el("td", {}, c.base_text ? `p.${c.base_page}: ${c.base_text}` : ""),
        el("td", {}, c.target_text ? `p.${c.target_page}: ${c.target_text}` : "")));
    }
  } catch (error) {
    $("#compare-heading").innerHTML = "";
    $("#compare-heading").append(el("div", { class: "banner bad" }, error.message));
  } finally { button.disabled = false; }
}

// ---------- upload ----------

async function upload(event) {
  event.preventDefault();
  const file = $("#upload-file").files[0];
  if (!file) return;
  const background = $("#upload-background").checked;
  const form = new FormData();
  form.append("file", file);
  const button = $("#upload-button");
  button.disabled = true;
  $("#upload-message").textContent = background ? "Uploading…" : "Uploading and processing… this can take a few minutes.";
  try {
    const response = await api(`/ingest/upload?background=${background}`, { method: "POST", body: form });
    $("#upload-message").textContent = background
      ? `Queued as job ${response.id.slice(0, 8)}. Progress appears below.`
      : `Stored as ${response.document_type} ${response.document_number || response.title} (${response.chunk_count} chunks).`;
    $("#upload-form").reset();
    $("#upload-background").checked = true;
    loadJobs();
  } catch (error) {
    $("#upload-message").textContent = error.message;
  } finally { button.disabled = false; }
}

async function loadJobs() {
  try {
    const jobs = await api("/ingest/jobs?limit=20");
    const tbody = $("#job-table tbody");
    tbody.innerHTML = "";
    if (!jobs.length) tbody.append(el("tr", {}, el("td", { colspan: 5, class: "muted" }, "No jobs yet.")));
    for (const job of jobs) {
      tbody.append(el("tr", {},
        el("td", {}, job.original_filename || job.file_path.split("/").pop()),
        el("td", {}, ["PENDING", "RUNNING"].includes(job.status) ? el("span", { class: "spinner" }) : null, pill(job.status)),
        el("td", {}, job.attempts), el("td", {}, formatDate(job.created_at)),
        el("td", {}, job.error ? el("span", { class: "error" }, job.error)
          : job.document_id ? el("button", { class: "link", onclick: () => { showTab("documents"); showDocument(job.document_id); } }, "Open document") : "")));
    }
  } catch (error) { toast(error.message); }
}

// ---------- users ----------

async function loadUsers() {
  try {
    const users = await api("/users");
    const tbody = $("#user-table tbody");
    tbody.innerHTML = "";
    for (const user of users) {
      const role = el("select", { onchange: (e) => updateUser(user.id, { role: e.target.value }) },
        ["VIEWER", "EDITOR", "ADMIN"].map((r) => el("option", { selected: r === user.role }, r)));
      tbody.append(el("tr", {},
        el("td", {}, user.username), el("td", {}, role),
        el("td", {}, el("input", { type: "checkbox", checked: user.is_active, onchange: (e) => updateUser(user.id, { is_active: e.target.checked }) })),
        el("td", {}, formatDate(user.last_login_at)),
        el("td", {},
          el("button", { class: "link", onclick: () => resetPassword(user) }, "Set password"),
          el("button", { class: "link danger", onclick: () => deleteUser(user) }, "Delete"))));
    }
  } catch (error) { toast(error.message); }
}

async function updateUser(id, changes) {
  try { await api(`/users/${id}`, { method: "PATCH", json: changes }); toast("Saved."); }
  catch (error) { toast(error.message); }
  loadUsers();
}

async function resetPassword(user) {
  const input = el("input", { type: "password", minlength: 8, placeholder: "new password (8+ characters)" });
  if (await openDialog(`New password for ${user.username}`, [input])) updateUser(user.id, { password: input.value });
}

async function deleteUser(user) {
  if (!confirm(`Delete user ${user.username}?`)) return;
  try { await api(`/users/${user.id}`, { method: "DELETE" }); loadUsers(); }
  catch (error) { toast(error.message); }
}

async function addUser(event) {
  event.preventDefault();
  try {
    await api("/users", { method: "POST", json: { username: $("#new-username").value, password: $("#new-password").value, role: $("#new-role").value } });
    $("#user-message").textContent = "User added.";
    $("#user-form").reset();
    loadUsers();
  } catch (error) { $("#user-message").textContent = error.message; }
}

async function changeOwnPassword() {
  const current = el("input", { type: "password", placeholder: "current password", autocomplete: "current-password" });
  const next = el("input", { type: "password", placeholder: "new password (8+ characters)", autocomplete: "new-password" });
  if (!(await openDialog("Change your password", [current, next]))) return;
  try {
    await api("/auth/password", { method: "POST", json: { current_password: current.value, new_password: next.value } });
    toast("Password changed. Please sign in again.");
    signOut(false);
  } catch (error) { toast(error.message); }
}

function openDialog(title, fields) {
  const dialog = $("#dialog");
  $("#dialog-title").textContent = title;
  $("#dialog-body").replaceChildren(...fields);
  dialog.showModal();
  return new Promise((resolve) => dialog.addEventListener("close", () => resolve(dialog.returnValue === "ok"), { once: true }));
}

// ---------- wiring ----------

$("#login-form").addEventListener("submit", signIn);
$("#logout-button").addEventListener("click", () => signOut(true));
$("#password-button").addEventListener("click", changeOwnPassword);
$("#nav").addEventListener("click", (e) => { if (e.target.dataset.tab) showTab(e.target.dataset.tab); });
$("#ask-form").addEventListener("submit", ask);
$("#question").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#ask-form").requestSubmit(); } });
document.addEventListener("click", (e) => { const tag = e.target.closest(".tag[data-label]"); if (tag) showSource(tag.dataset.label); });
$("#doc-refresh").addEventListener("click", loadDocuments);
$("#doc-search").addEventListener("keydown", (e) => { if (e.key === "Enter") loadDocuments(); });
$("#compare-form").addEventListener("submit", compare);
$("#upload-form").addEventListener("submit", upload);
$("#user-form").addEventListener("submit", addUser);
start();
