"""Render a .dc.html mockup to a static HTML preview (one state, no runtime).

Usage: python3 render_dc.py <in.dc.html> <out.html> <theme: light|dark> [state-json]
Evaluates the component's renderVals() with node, substitutes {{holes}},
resolves <sc-if> blocks, and drops event handlers and the logic script.
"""
import json, re, subprocess, sys, html

src_path, out_path, theme = sys.argv[1], sys.argv[2], sys.argv[3]
extra_state = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
src = open(src_path, encoding="utf-8").read()

script = re.search(r'<script type="text/x-dc"[^>]*>(.*?)</script>', src, re.S).group(1)
harness = """
class DCLogic { constructor(props){ this.props = props; this.state = {}; } setState(){} forceUpdate(){} }
%s
const c = new Component({ theme: %s });
Object.assign(c.state, %s);
const v = c.renderVals();
const out = {};
for (const [k, val] of Object.entries(v)) { if (typeof val !== 'function') out[k] = val; }
console.log(JSON.stringify(out));
""" % (script, json.dumps(theme), json.dumps(extra_state))
vals = json.loads(subprocess.run(["node", "-e", harness], capture_output=True, text=True, check=True).stdout)

def lookup(path):
    cur = vals
    for part in path.split("."):
        cur = cur[part]
    return cur

body = re.search(r"<x-dc>(.*)</x-dc>", src, re.S).group(1)
helmet = re.search(r"<helmet>(.*?)</helmet>", body, re.S).group(1)
body = re.sub(r"<helmet>.*?</helmet>", "", body, flags=re.S)

# drop event handlers
body = re.sub(r'\s+on[A-Z][A-Za-z]*="\{\{[^}]*\}\}"', "", body)

# resolve sc-if, innermost first
pat = re.compile(r'<sc-if value="\{\{\s*([\w.]+)\s*\}\}"[^>]*>((?:(?!<sc-if).)*?)</sc-if>', re.S)
while True:
    m = pat.search(body)
    if not m:
        break
    keep = bool(lookup(m.group(1)))
    body = body[:m.start()] + (m.group(2) if keep else "") + body[m.end():]

def sub(m):
    v = lookup(m.group(1))
    if isinstance(v, bool):
        return "true" if v else "false"
    return html.escape(str(v), quote=True)

body = re.sub(r"\{\{\s*([\w.]+)\s*\}\}", sub, body)
title = re.search(r"<title>(.*?)</title>", src).group(1)
out = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} (static preview, {theme})</title>
{helmet}
</head>
<body>
{body}
</body>
</html>
"""
open(out_path, "w", encoding="utf-8").write(out)
print("wrote", out_path)
