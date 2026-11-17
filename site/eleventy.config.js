// Eleventy renders the pipeline's JSON (build/site, from `python -m pear site`).
// Mathematics is typeset with KaTeX at build time (DESIGN.md); a TeX error fails the build.
import katex from "katex";

const REPO = "https://github.com/algo-unsw/PEAR";

const escapeHtml = (s) =>
  String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

function tex(source) {
  return katex.renderToString(String(source), { throwOnError: true, output: "html", strict: "error" });
}

// Text with inline $...$ maths: escape the prose, typeset the maths.
function mathText(source) {
  if (source === null || source === undefined) return "";
  const parts = String(source).split(/(\$[^$]+\$)/g);
  return parts
    .map((p) => (p.length > 1 && p.startsWith("$") && p.endsWith("$") ? tex(p.slice(1, -1)) : escapeHtml(p)))
    .join("");
}

// Step chart of the best base over the years (DESIGN.md, bound history). Polynomial factors ignored.
function historyChart(steps, paramTex, label) {
  if (!steps || steps.length < 2) return "";
  const W = 560, H = 200, left = 56, right = 540, top = 30, bottom = 165;
  const years = steps.map((s) => s.year);
  const bases = steps.map((s) => s.base);
  const y0 = Math.min(...years), y1 = Math.max(new Date().getFullYear(), ...years);
  let b0 = Math.min(...bases), b1 = Math.max(...bases);
  const pad = (b1 - b0) * 0.08 || 0.01;
  b0 -= pad; b1 += pad;
  const x = (yr) => left + 4 + ((yr - y0) / Math.max(1, y1 - y0)) * (right - left - 8);
  const y = (b) => bottom - ((b - b0) / (b1 - b0)) * (bottom - top);
  const ticks = [];
  const yStep = niceStep((b1 - b0) / 3);
  for (let v = Math.ceil(b0 / yStep) * yStep; v <= b1; v += yStep) ticks.push(v);
  const yearStep = niceStep((y1 - y0) / 4) || 1;
  const yearTicks = [];
  for (let v = Math.ceil(y0 / yearStep) * yearStep; v <= y1; v += yearStep) yearTicks.push(v);
  const decimals = Math.max(2, -Math.floor(Math.log10(yStep)));
  // Two record lines (decided 18 November 2026): deterministic records, and the best bound
  // with randomized algorithms allowed (deterministic ones count there too). One line when no
  // randomized result is a record.
  const path = (pts) => {
    if (!pts.length) return "";
    let d = `M${x(pts[0].year).toFixed(1)} ${y(pts[0].base).toFixed(1)}`;
    for (let i = 1; i < pts.length; i++) d += ` H${x(pts[i].year).toFixed(1)} V${y(pts[i].base).toFixed(1)}`;
    return d + ` H${x(y1).toFixed(1)}`;
  };
  const det = steps.filter((s) => s.deterministic !== false);
  const anyLine = [];
  for (const s of steps) if (!anyLine.length || s.base < anyLine[anyLine.length - 1].base) anyLine.push(s);
  const twoLines = steps.some((s) => s.deterministic === false);
  const best = anyLine[anyLine.length - 1];
  const last = best;
  const summary =
    `Step chart: the best base fell from ${anyLine[0].base} in ${anyLine[0].year} ` +
    `to ${best.base} in ${best.year}` + (best.year < y1 ? " and has not changed since" : "") +
    (twoLines && det.length ? `; the best deterministic base is ${det[det.length - 1].base} (${det[det.length - 1].year})` : "");
  let svg = `<svg class="chart" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${escapeHtml(summary)}">`;
  for (const t of ticks) {
    svg += `<line x1="${left}" y1="${y(t).toFixed(1)}" x2="${right}" y2="${y(t).toFixed(1)}" class="grid"/>`;
    svg += `<text x="${left - 6}" y="${(y(t) + 4).toFixed(1)}" text-anchor="end" class="axis">${t.toFixed(decimals)}</text>`;
  }
  for (const t of yearTicks) {
    svg += `<text x="${x(t).toFixed(1)}" y="${H - 8}" text-anchor="middle" class="axis">${t}</text>`;
  }
  if (twoLines) {
    if (det.length) svg += `<path d="${path(det)}" class="line"/>`;
    svg += `<path d="${path(anyLine)}" class="line rand"/>`;
    svg += `<line x1="${left + 8}" y1="14" x2="${left + 32}" y2="14" class="line"/><text x="${left + 38}" y="18" class="axis">deterministic</text>`;
    svg += `<line x1="${left + 150}" y1="14" x2="${left + 174}" y2="14" class="line rand"/><text x="${left + 180}" y="18" class="axis">randomized allowed</text>`;
  } else {
    svg += `<path d="${path(steps)}" class="line"/>`;
  }
  for (const s of steps) {
    svg += `<circle cx="${x(s.year).toFixed(1)}" cy="${y(s.base).toFixed(1)}" r="4" class="dot${s.deterministic === false ? " rand" : ""}"/>`;
  }
  svg += `<text x="${right}" y="${(y(last.base) - 8).toFixed(1)}" text-anchor="end" class="value">${last.base}</text>`;
  if (twoLines && det.length && det[det.length - 1].base !== last.base) {
    const dl = det[det.length - 1];
    svg += `<text x="${right}" y="${(y(dl.base) - 8).toFixed(1)}" text-anchor="end" class="value">${dl.base}</text>`;
  }
  return svg + "</svg>";
}

function niceStep(raw) {
  if (raw <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  for (const m of [1, 2, 5, 10]) if (raw <= m * p) return m * p;
  return 10 * p;
}

export default function (eleventyConfig) {
  eleventyConfig.addFilter("tex", tex);
  eleventyConfig.addFilter("mathtext", mathText);
  eleventyConfig.addFilter("lcfirst", (s) => (s ? s[0].toLowerCase() + s.slice(1) : s));
  eleventyConfig.addFilter("refs", (ns) => (ns || []).map((n) => `<a href="#ref-${n}">[${n}]</a>`).join(""));
  eleventyConfig.addShortcode("historyChart", historyChart);
  eleventyConfig.addGlobalData("repo", REPO);

  eleventyConfig.addPassthroughCopy({ "src/assets": "assets" });
  eleventyConfig.addPassthroughCopy({ "node_modules/katex/dist/katex.min.css": "assets/katex/katex.min.css" });
  eleventyConfig.addPassthroughCopy({ "node_modules/katex/dist/fonts": "assets/katex/fonts" });
  eleventyConfig.addPassthroughCopy({ "../build/site/entries": "data" });

  return {
    dir: { input: "src", output: "_site", includes: "_includes", data: "_data" },
    pathPrefix: process.env.PATH_PREFIX || "/",
    templateFormats: ["njk"],
    htmlTemplateEngine: "njk",
  };
}
