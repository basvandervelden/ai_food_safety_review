"""Build offline, no-JavaScript previews using the exact same SVG engine as the website.

The charts are generated from data/papers.json by assets/landscape.js with Node.js.
This avoids divergent percentages or inconsistent graphic styles between browser
and weekly publication builds. Node.js 20+ is required only for chart rendering.
"""
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def render_charts(papers, collection="all", family="Deep learning (DL)"):
    javascript = r"""
const fs = require('fs');
const vm = require('vm');
global.window = {};
vm.runInThisContext(fs.readFileSync('assets/landscape.js', 'utf8'), {filename:'landscape.js'});
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const charts = window.LIVING_CHARTS.render(payload.papers, payload.collection, payload.family);
process.stdout.write(JSON.stringify(charts));
"""
    result = subprocess.run(
        ['node', '-e', javascript],
        cwd=ROOT, input=json.dumps({'papers':papers,'collection':collection,'family':family}),
        text=True, capture_output=True, check=True, timeout=30
    )
    result_data=json.loads(result.stdout)
    for field in ('sun','legend','summary','bars','key'):
        if field not in result_data: raise ValueError('Chart generator missing '+field)
    return result_data
