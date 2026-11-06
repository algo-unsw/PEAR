# PEAR handoff package

Everything a new Claude Code session needs to start building PEAR (Parameterized and Exact Algorithms and Reductions).

| Path | What it is |
| --- | --- |
| `HANDOFF.md` | Current state, Phase 1 goal, step-by-step plan, schema sketch, questions for Serge |
| `CLAUDE.md` | Standing rules for any Claude Code session in the repo (copy to the repo root) |
| `docs/PLAN.md` | The full agreed plan |
| `docs/DESIGN.md` | Design spec: tokens, type, layout, components, states |
| `design/preview/` | Static HTML previews of the chosen design (open in a browser) |
| `design/source/` | Interactive mockup sources (design-canvas component format) |
| `design/tools/render_dc.py` | Re-renders a source mockup to a static preview (needs Python 3 and Node) |

## How to start

1. Create the GitHub repository (suggested name `pear-algorithms`) and clone it.
2. Unzip this package into the repository root.
3. Start Claude Code in the repository and say:

   > Read CLAUDE.md, HANDOFF.md, docs/PLAN.md and docs/DESIGN.md, then begin with step 1 of HANDOFF.md. Ask me before deciding anything the brief marks as mine.
