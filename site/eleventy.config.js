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
  let d = `M${x(steps[0].year).toFixed(1)} ${y(steps[0].base).toFixed(1)}`;
  for (let i = 1; i < steps.length; i++) {
    d += ` H${x(steps[i].year).toFixed(1)} V${y(steps[i].base).toFixed(1)}`;
  }
  d += ` H${x(y1).toFixed(1)}`;
  const last = steps[steps.length - 1];
  const summary =
    `Step chart: the best base fell from ${steps[0].base} in ${steps[0].year} ` +
    `to ${last.base} in ${last.year}` + (last.year < y1 ? " and has not changed since" : "");
  let svg = `<svg class="chart" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${escapeHtml(summary)}">`;
  for (const t of ticks) {
    svg += `<line x1="${left}" y1="${y(t).toFixed(1)}" x2="${right}" y2="${y(t).toFixed(1)}" class="grid"/>`;
    svg += `<text x="${left - 6}" y="${(y(t) + 4).toFixed(1)}" text-anchor="end" class="axis">${t.toFixed(decimals)}</text>`;
  }
  for (const t of yearTicks) {
    svg += `<text x="${x(t).toFixed(1)}" y="${H - 8}" text-anchor="middle" class="axis">${t}</text>`;
  }
  svg += `<path d="${d}" class="line"/>`;
  for (const s of steps) svg += `<circle cx="${x(s.year).toFixed(1)}" cy="${y(s.base).toFixed(1)}" r="4" class="dot"/>`;
  svg += `<text x="${right}" y="${(y(last.base) - 8).toFixed(1)}" text-anchor="end" class="value">${last.base}</text>`;
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
