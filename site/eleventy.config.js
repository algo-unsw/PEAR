// Eleventy renders the pipeline's JSON (build/site, from `python -m pear site`).
// Mathematics is typeset with KaTeX at build time (DESIGN.md); a TeX error fails the build.
import katex from "katex";

const REPO = "https://github.com/algo-unsw/PEAR";

const escapeHtml = (s) =>
  String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

function tex(source, display = false) {
  return katex.renderToString(String(source), { throwOnError: true, output: "html", strict: "error", displayMode: !!display });
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
  const W = 560, H = 210, left = 56, right = 540, top = 44, bottom = 175;
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
  // Record lines (decided 18 November 2026): a result is a record if it beats every earlier
  // result at least as strong (deterministic beats randomized, polynomial space beats
  // exponential space). One line per kind of record present; one line if all are of one kind.
  const path = (pts) => {
    if (!pts.length) return "";
    let d = `M${x(pts[0].year).toFixed(1)} ${y(pts[0].base).toFixed(1)}`;
    for (let i = 1; i < pts.length; i++) d += ` H${x(pts[i].year).toFixed(1)} V${y(pts[i].base).toFixed(1)}`;
    return d + ` H${x(y1).toFixed(1)}`;
  };
  const kindOf = (s) => [s.deterministic !== false, s.polynomial_space !== false];
  const kinds = [[true, true], [true, false], [false, true], [false, false]];
  const names = ["deterministic, polynomial space", "deterministic", "polynomial space", "any"];
  const styles = ["k1", "k2", "k3", "k4"]; // solid lines, one colour each
  const present = kinds.map((k) => steps.some((s) => { const q = kindOf(s); return q[0] === k[0] && q[1] === k[1]; }));
  const lines = [];
  kinds.forEach((k, i) => {
    if (!present[i]) return;
    const pts = [];
    for (const s of steps) {
      const q = kindOf(s);
      if ((q[0] || !k[0]) && (q[1] || !k[1]) && (!pts.length || s.base < pts[pts.length - 1].base)) pts.push(s);
    }
    lines.push({ name: names[i], style: styles[i], pts });
  });
  const overall = steps.reduce((acc, s) => (!acc.length || s.base < acc[acc.length - 1].base ? acc.concat([s]) : acc), []);
  const best = overall[overall.length - 1];
  const summary =
    `Step chart: the best base fell from ${overall[0].base} in ${overall[0].year} ` +
    `to ${best.base} in ${best.year}` + (best.year < y1 ? " and has not changed since" : "") +
    (lines.length > 1 ? lines.map((l) => `; ${l.name}: ${l.pts[l.pts.length - 1].base} (${l.pts[l.pts.length - 1].year})`).join("") : "");
  let svg = `<svg class="chart" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${escapeHtml(summary)}">`;
  for (const t of ticks) {
    svg += `<line x1="${left}" y1="${y(t).toFixed(1)}" x2="${right}" y2="${y(t).toFixed(1)}" class="grid"/>`;
    svg += `<text x="${left - 6}" y="${(y(t) + 4).toFixed(1)}" text-anchor="end" class="axis">${t.toFixed(decimals)}</text>`;
  }
  for (const t of yearTicks) {
    svg += `<text x="${x(t).toFixed(1)}" y="${H - 8}" text-anchor="middle" class="axis">${t}</text>`;
  }
  if (lines.length > 1) {
    // weakest kind first, so where lines coincide the strongest kind's colour shows
    for (const l of lines.slice().reverse()) svg += `<path d="${path(l.pts)}" class="line ${l.style}"/>`;
    let lx = left + 8, ly = 10;
    for (const l of lines) {
      const w = 40 + 7 * l.name.length;
      if (lx + w > W && lx > left + 8) { lx = left + 8; ly += 16; }
      svg += `<line x1="${lx}" y1="${ly}" x2="${lx + 22}" y2="${ly}" class="line ${l.style}"/><text x="${lx + 28}" y="${ly + 4}" class="axis">${l.name}</text>`;
      lx += w;
    }
  } else {
    svg += `<path d="${path(lines[0].pts)}" class="line k1"/>`;
  }
  for (const s of steps) {
    const q = kindOf(s);
    const st = styles[kinds.findIndex((k) => k[0] === q[0] && k[1] === q[1])];
    svg += `<circle cx="${x(s.year).toFixed(1)}" cy="${y(s.base).toFixed(1)}" r="4" class="dot ${lines.length > 1 ? st : "k1"}"/>`;
  }
  // value labels at the right end of each line, kept at least 14px apart
  const ends = [...new Set(lines.map((l) => l.pts[l.pts.length - 1].base))].sort((a, b) => b - a);
  let lastY = -Infinity, lineAbove = -Infinity;
  for (const end of ends) {
    // above its line if there is room under the line above, else below its line
    let ly = y(end) - lineAbove >= 26 ? y(end) - 8 : y(end) + 16;
    if (ly < lastY + 14) ly = lastY + 14;
    svg += `<text x="${right}" y="${ly.toFixed(1)}" text-anchor="end" class="value">${end}</text>`;
    lastY = ly;
    lineAbove = y(end);
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
