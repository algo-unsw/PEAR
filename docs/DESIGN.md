# PEAR design spec (Encyclopedia look)

The chosen design is the "Encyclopedia combined" mockup for Vertex Cover, desktop and phone. Open the static previews in `../design/preview/` in a browser; the interactive sources are in `../design/source/` (see "About the source files" below).

## Principles

- Experts come for bounds: **best bounds first**, right under the title. The definition follows, compact and collapsible.
- Two views of the same facts: **Overview** (default, prose-style) and **Details** (filters and tables). Details adds tools, not new facts, with two exceptions that appear only in Details: the Implementations section and the bound history.
- Every page stays the same length as the site grows; history, long reduction lists and details sit behind a click.
- No reduction-graph diagram. Each derived bound expands to its own chain instead.
- Lean status is a small label only.
- Sans-serif type everywhere, except mathematics, which is typeset properly (TeX-style).

## Tokens

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| bg | #FFFFFF | #111514 | page background |
| band | #F2F5F5 | #1A201F | header band, info box, insets, table headers |
| text | #1A1D21 | #E6ECEB | body text |
| muted | #4D5660 | #A3B0AE | secondary text |
| border | #D3DBDB | #2F3A39 | rules, table borders, tabs |
| accent | #0B6B66 | #6FD3CA | links, interactive text, chart line |
| boxHead | #0B6B66 | #0B6B66 | info-box header, selected Overview/Details, primary buttons (white text) |
| tagBg / tagText | #E3F1F0 / #064A46 | #123A37 / #A7EAE3 | "derived" tag, selected parameter chip |
| grid | #DCE3E3 | #2F3A39 | chart gridlines |
| switch track | #C9D6D5 | #0B6B66 | theme switch |

All text pairs meet WCAG AA (4.5:1) in both themes; keep it that way when adding colours.

## Typography

- Text: **Source Sans 3** (400, 600, 700; italic 400). Body 18px desktop / 17px phone, line height 1.6.
- H1 42px/700 (phone 30px). Section H2 28px/700 with a 1px bottom rule (phone 22px). H3 20px/600.
- Mathematics: render with **KaTeX or MathJax** on the real site (the mockup uses native MathML only because the design canvas blocks external scripts). Bounds in O* notation, e.g. `O^*(1.2738^k)`; non-stretchy parentheses inline.
- Parameter names (k, n, tw) are maths, not code.
- Greek letters, above all the matrix multiplication exponent $\omega$, are always rendered through KaTeX/MathJax (`\omega`), never as plain Unicode characters in page text: some fonts and pages show a plain lowercase omega as an uppercase Omega (decided 7 November 2026).

## Layout (desktop, max width 1180px)

1. **Header band**: "PEAR" wordmark + "Parameterized and Exact Algorithms and Reductions"; search field (placeholder: name, shorthand like "vc k", or describe the problem); nav (Browse, Recently improved, Hypotheses); **light/dark switch at the far right** (sliding switch, sun/moon on the knob, `role="switch"`).
2. **Title row**: H1 problem name, "Also known as …"; page tools on the right: History, Watch, Report an error, Suggest a link or DOI, Cite.
3. **Tab row**: version tabs on the left (Decision default, Optimisation, Search, Weighted; encyclopedia-style tabs); **Overview / Details** segmented control on the right.
4. **Two columns**: article (flexible) + info box (280–340px) on the right; the info box wraps below on narrow screens.
   - Info box: also known as, complexity, parameters, versions, Lean status, papers tracked (OpenAlex), last checked.
5. **Article sections, in order**: equivalence note (for decision/optimisation/search) → Fastest known algorithms → Definition → Reductions → Related problems → Implementations (Details only) → References → footer line (Data CC0 · code MIT · curated automatically · JSON).

### Fastest known algorithms

- **Overview**: one H3 per parameter ("By solution size k", "By number of vertices n", "By treewidth tw"). Under it: the O* bound, properties in words, footnote reference, "proved for the … version". No bound history in the Overview (decided 10 November 2026). Derived bounds get a "derived" tag and a disclosure "Where this bound comes from" that expands to the numbered chain (source problem and bound → reduction with type and parameter map → result).
- **Details**: a "Show only" filter row (deterministic, polynomial space, constructive, non-algebraic, Lean-verified, include derived) and a bordered table: Param · Bound · Properties · Proved for · Source · Origin (direct / derived, n steps). Source notes and derivation chains open in a full-width row below their result.
- **Unverified results** (12 November 2026): left out of the Overview by default. In Details, the Origin cell of each unverified result has a checkbox "include in Overview"; the choice is stored in the reader's browser (localStorage), and an included result appears in its Overview group and hides the results it beats. Without JavaScript the Overview shows verified results only.
- **Bound history** (Details only, decided 10 November 2026; one card per parameter, below the results table): a step chart of the best base over the years plus a reversed list of improvements (bound · authors · venues). Polynomial factors ignored in the chart. Flagged results stay in the list, marked.
- **Weighted tab**: its own bounds; note that weighted algorithms also give derived bounds for unweighted versions, never the reverse.

### Implementations (Details only; agreed 8 November 2026, revised 10 November 2026)

- H2 "Implementations", placed after Related problems and before References; not shown in Overview.
- Bulleted list in the order stored in the data, with no claim that it is a ranking (decided 10 November 2026): name (linked), language · licence, versions solved, a note when solved through a transformation (e.g. "via the complement"), then the facts as short bullets with their sources as footnotes. Dated facts show "as of".

### Definition

- Collapsible via a **filled triangle** (points right when closed, down when open), on the H2.
- Always visible, on **separate lines**: **Input:** … / **Question:** …
- Expanded: context sentence(s) and parameter definitions (n, m, N, k, tw — what each counts).

### Reductions

- Overview: short list grouped "From …" / "To …" with parameter maps.
- Details: table: Reduction · Type · Parameter map · Variants · Formal status.

## Phone (390px)

- Header: wordmark with small full name; search icon button; theme switch rightmost.
- Title, one-line facts (aka · NP-complete · Lean status).
- Version tabs (horizontally scrollable).
- **Fastest known algorithms first**, expanded: parameter, O* bound, one line of properties; "filters" opens a bottom-sheet panel with checkboxes and Done.
- Then collapsible sections with filled triangles, closed by default: Definition, Reductions, Related problems, References.
- Submission box: "Know a better result? Paste a link or DOI. At least one reference must be openly readable."
- Footer line: Data CC0 · code MIT · Cite · Report an error.

## Interaction and accessibility

- Real `<button>`, `<a href>`, `<input>` + `<label>`; `aria-expanded` on disclosures; `aria-label` on icon-only buttons; chart has `role="img"` with a text summary.
- Touch targets ≥ 44px on phone.
- Theme: follow `prefers-color-scheme` by default, remember the user's choice.
- Hover explanations for every tag (derived, constructive, algebraic, …).

## About the source files

`design/source/*.dc.html` are mockups in the design canvas's component format (not production code): markup with inline styles, `{{holes}}` filled by the `renderVals()` method at the bottom, and `<sc-if>` for conditional blocks. Use them for exact spacing, colours and states; reimplement in whatever stack the site uses. `design/preview/*.html` are static renders of specific states:

| File | State |
| --- | --- |
| desktop-overview-light.html | default page |
| desktop-overview-dark.html | dark theme |
| desktop-overview-expanded-light.html | definition open, chain open, k history open |
| desktop-details-light.html | Details view |
| phone-light.html | all sections open |
| phone-dark.html | dark theme, default |

## Mockup content warnings

- The k-history values and years (1.3247^k 1998, 1.2918^k 1999, 1.2852^k 2001, 1.2738^k 2006) are from memory; **verify against the papers** before using them as data.
- `[Thm X.Y]`, `[version]`, `[DATE]`, `[count from OpenAlex]` and the weighted bounds are placeholders.
- Do not reuse mockup content as site data without checking sources.
