# PEAR: Parameterized and Exact Algorithms and Reductions

PEAR catalogues NP-hard problems, the reductions between them, and the fastest known exact and parameterized algorithms for each problem. Some best-known bounds come straight from papers; others are derived automatically by chaining reductions, and each derived bound shows the chain it comes from.

**Status:** under construction (Phase 1 pilot: 12 problems). Vertex Cover and Independent Set are entered.

## Contributing

- **Suggest a result**: open an issue with the *Suggest a result (link or DOI)* form. A single link or DOI is enough; at least one reference must be openly readable.
- **Report an error**: use the *Report an error* form, with a link to evidence where you have one.

## Repository layout

| Path | What it is |
| --- | --- |
| `docs/PLAN.md` | The agreed plan (source of truth) |
| `docs/DESIGN.md` | Design spec: tokens, type, layout, components, states |
| `HANDOFF.md` | Current state and next steps of the build |
| `CLAUDE.md` | Standing rules for Claude Code sessions in this repository |
| `data/` | The database: YAML files checked against a schema (from step 3) |
| `src/pear/` | Python pipeline: schema validation, bound language, derivation engine |
| `tests/` | pytest suite, run on every pull request |
| `site/` | Eleventy site rendering `build/site/site.json`; KaTeX at build time |
| `design/preview/` | Static HTML previews of the chosen design (open in a browser) |
| `design/source/` | Interactive mockup sources (design-canvas component format) |
| `design/tools/render_dc.py` | Re-renders a source mockup to a static preview (needs Python 3 and Node) |

## Development

```bash
pip install -e ".[dev]"
pytest
python -m pear validate          # check the data
python -m pear site              # derive bounds, write build/site/
cd site && npm ci && npx eleventy --serve   # the site on http://localhost:8080
```

## Licences

- Data (`data/`): [CC0 1.0](data/LICENSE)
- Code: [MIT](LICENSE)
