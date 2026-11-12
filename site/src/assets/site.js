// PEAR page behaviour: theme switch, version tabs, Overview/Details, disclosures,
// bound history, Details filters, search. The page is complete without it (default
// version, Overview).
(function () {
  "use strict";
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
  };

  // Theme: dark by default; the reader's choice is remembered.
  const root = document.documentElement;
  const dark = () => root.dataset.theme !== "light";
  function syncSwitch() {
    $$("[data-theme-switch]").forEach((b) => b.setAttribute("aria-checked", String(dark())));
  }
  $$("[data-theme-switch]").forEach((b) =>
    b.addEventListener("click", () => {
      const next = dark() ? "light" : "dark";
      root.dataset.theme = next;
      store.set("pear-theme", next);
      syncSwitch();
    }));
  syncSwitch();

  // Disclosures (filled triangles): aria-controls points at the content.
  document.addEventListener("click", (ev) => {
    const btn = ev.target.closest("button[aria-controls]");
    if (btn && !btn.matches("[role=tab]")) {
      const target = document.getElementById(btn.getAttribute("aria-controls"));
      if (target) {
        const open = btn.getAttribute("aria-expanded") !== "true";
        btn.setAttribute("aria-expanded", String(open));
        target.hidden = !open;
        return;
      }
    }
    const toggle = ev.target.closest(".phone-toggle");
    if (toggle) toggle.setAttribute("aria-expanded", String(toggle.getAttribute("aria-expanded") !== "true"));
  });

  // Version tabs and views; the hash keeps the state (#weighted, #details, #weighted/details).
  const page = document.querySelector("main[data-default-version]");
  if (page) {
    const tabs = $$("[role=tab][data-version]");
    const versions = tabs.map((t) => t.dataset.version);
    const state = { version: page.dataset.defaultVersion, view: "overview" };
    function apply() {
      tabs.forEach((t) => {
        const on = t.dataset.version === state.version;
        t.setAttribute("aria-selected", String(on));
        t.tabIndex = on ? 0 : -1;
      });
      $$(".version-panel").forEach((p) => { p.hidden = p.dataset.version !== state.version; });
      document.body.dataset.view = state.view;
      $$("[data-view-button]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.viewButton === state.view)));
    }
    function writeHash() {
      const parts = [];
      if (state.version !== page.dataset.defaultVersion) parts.push(state.version);
      if (state.view !== "overview") parts.push(state.view);
      history.replaceState(null, "", parts.length ? "#" + parts.join("/") : location.pathname + location.search);
    }
    function readHash() {
      const parts = location.hash.replace(/^#/, "").split("/");
      for (const part of parts) {
        if (versions.includes(part)) state.version = part;
        if (part === "details" || part === "overview") state.view = part;
      }
    }
    tabs.forEach((t) => {
      t.addEventListener("click", () => { state.version = t.dataset.version; apply(); writeHash(); });
      t.addEventListener("keydown", (ev) => {
        const i = tabs.indexOf(t);
        const j = ev.key === "ArrowRight" ? (i + 1) % tabs.length : ev.key === "ArrowLeft" ? (i - 1 + tabs.length) % tabs.length : -1;
        if (j >= 0) { tabs[j].focus(); tabs[j].click(); ev.preventDefault(); }
      });
    });
    $$("[data-view-button]").forEach((b) =>
      b.addEventListener("click", () => { state.view = b.dataset.viewButton; apply(); writeHash(); }));
    readHash();
    apply();

    // Details filters ("Show only"), per version panel.
    function filter(panel) {
      const on = {};
      $$("[data-filter]", panel).forEach((c) => { on[c.dataset.filter] = c.checked; });
      let shown = 0;
      $$("table.results tbody tr[data-row]", panel).forEach((tr) => {
        const ok =
          (!on.det || tr.dataset.det === "true") &&
          (!on.poly || tr.dataset.poly === "true") &&
          (!on.constr || tr.dataset.constr === "true") &&
          (!on.nonalg || tr.dataset.nonalg === "true") &&
          (!on.lean || tr.dataset.lean === "true") &&
          (on.derived || tr.dataset.derived !== "true");
        tr.hidden = !ok;
        tr.dataset.filteredOut = String(!ok);
        if (ok) shown++;
      });
      $$("table.results tbody tr.extra", panel).forEach((tr) => {
        const parent = panel.querySelector(`tr[data-row="${CSS.escape(tr.dataset.parent)}"]`);
        tr.classList.toggle("filtered", !!(parent && parent.hidden));
      });
      const empty = panel.querySelector("[data-filter-empty]");
      if (empty) empty.hidden = shown > 0;
    }
    $$(".version-panel").forEach((panel) => {
      $$("[data-filter]", panel).forEach((c) => c.addEventListener("change", () => filter(panel)));
    });
  }

  // Unverified results: each reader chooses which to include in the Overview (stored in
  // this browser only). An included result shows in its group and hides the entries it beats.
  const KEY = "pear-include-unverified";
  let included = new Set();
  try { included = new Set(JSON.parse(localStorage.getItem(KEY) || "[]")); } catch (e) { /* none */ }
  function applyUnverified() {
    $$("[data-include-unverified]").forEach((c) => { c.checked = included.has(c.dataset.includeUnverified); });
    $$("[data-optional]").forEach((el) => { el.hidden = !included.has(el.dataset.optional); });
    $$("[data-beaten-by]").forEach((el) => {
      el.hidden = el.dataset.beatenBy.split(" ").some((id) => included.has(id));
    });
    $$(".ov-group").forEach((g) => {
      if (g.hasAttribute("data-only-optional")) {
        g.hidden = !$$("[data-optional]", g).some((el) => !el.hidden);
      }
    });
  }
  $$("[data-include-unverified]").forEach((c) => c.addEventListener("change", () => {
    if (c.checked) included.add(c.dataset.includeUnverified); else included.delete(c.dataset.includeUnverified);
    try { localStorage.setItem(KEY, JSON.stringify(Array.from(included))); } catch (e) { /* private mode */ }
    applyUnverified();
  }));
  applyUnverified();

  // Search: names and aliases; "vc k" style shorthand picks the problem from the first words.
  const form = document.querySelector("[data-search]");
  const indexEl = document.getElementById("search-index");
  if (form && indexEl) {
    const index = JSON.parse(indexEl.textContent);
    const base = form.getAttribute("action");
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      const q = form.querySelector("input").value.trim().toLowerCase();
      if (!q) return;
      const words = q.split(/\s+/);
      let best = null;
      for (let cut = words.length; cut > 0 && !best; cut--) {
        const head = words.slice(0, cut).join(" ");
        best = index.find((p) => p.names.some((n) => n.toLowerCase() === head)) ||
          index.find((p) => p.names.some((n) => n.toLowerCase().startsWith(head)));
      }
      if (!best) best = index.find((p) => p.names.some((n) => n.toLowerCase().includes(q)));
      if (best) location.href = base + "problems/" + best.id + "/";
      else form.querySelector("input").setCustomValidity("No problem with that name yet."), form.reportValidity();
    });
    form.querySelector("input").addEventListener("input", (e) => e.target.setCustomValidity(""));
  }
})();
