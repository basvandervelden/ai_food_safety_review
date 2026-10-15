# Living AI for Food Safety — standalone research prototype

A standalone, responsive, locally viewable **living evidence map**, based on the four classification dimensions of van Meer et al., [*Artificial intelligence in food safety*](https://doi.org/10.1038/s41538-026-00925-1), *npj Science of Food* (2026).

## Included

- **Website:** searchable publications, facets, publication details, evidence snapshots, descriptive charts, research pulse, CSV/JSON exports, dark mode, mobile layout.
- **Seed collection:** 22 real publications with publisher DOI links. This is an illustrative, hand-selected reading list, **not** the paper's original screening dataset, **not** an exhaustive search, and **not** a validation of full text.
- **Scheduled pipeline:** Python standard-library code to query OpenAlex, reconstruct abstracts, deduplicate by DOI, identify and classify *candidate* papers, optionally using an OpenAI model, generate JSON and JavaScript files, and preserve a review queue.
- **Human validation:** optional `data/review_overrides.json` to verify, exclude or correct records.
- **GitHub Actions:** weekly scheduled workflow and manual dispatch.

## View locally (zero setup)

Simply **open `index.html` in your browser**. The page works offline because it loads generated `data/papers.js` rather than relying on `fetch()` from `file://`. The index also contains **pre-rendered article cards, counts and charts**, so it stays useful in iOS previews or readers where JavaScript is disabled. The `data/papers.csv` file is an independent, readable download of the records.

There is also a **single-file demo** (`Living_AI_Food_Safety_demo.html`) alongside the ZIP: this includes the CSS, JavaScript, dataset, and pre-rendered HTML. The single-file HTML can be opened without extracting an archive. Use Safari/Chrome for interactive filters; file previews may block JavaScript.

You can also run a local server:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000`.

## First live literature update

```bash
# Optional, but recommended for the OpenAlex API's higher usage allowance:
export OPENALEX_API_KEY='your-free-openalex-api-key'

# Optional: enables more nuanced title/abstract classification.
# Without it, conservative keyword/rule-based classification is used.
export OPENAI_API_KEY='your-openai-api-key'
export OPENAI_MODEL='gpt-4.1-mini'

python agent/update.py --days 90 --per-query 40
```

This requires outbound Internet access. The delivered demo could not be run against OpenAlex from the build environment (its network is restricted). API execution is consequently **not yet end-to-end verified**. API parameters follow [OpenAlex's current docs](https://help.openalex.org/api/). The API may have usage charges above free limits, and OpenAI calls incur model usage costs.

**First-run data note:** newly retrieved publications are tagged `automated_candidate`, never `verified`. A record with ambiguous relevance goes into `data/review_queue.json`; highly irrelevant entries are dropped by the conservative screening rule. A pipeline run merges into the existing preview collection; it does not remove the 22 starter records.

If you want to evaluate the pipeline without overwriting the example collection, run `python agent/update.py --dry-run`.

## Enable weekly automatic updates

1. Push this *entire folder* to your own GitHub repository. Keep `.github/workflows/update-literature.yml`.
2. Under repository **Settings → Secrets and variables → Actions**, add the repository secret `OPENALEX_API_KEY` (recommended) and optionally `OPENAI_API_KEY`.
3. Enable GitHub Actions; run the **Refresh literature** workflow manually once to test permissions and API access. The schedule is **Mondays at 06:15 UTC** (not necessarily Dutch local time).
4. The workflow rebuilds and commits the updated JSON, JS, CSV and static HTML snapshot to the repository. Publish the site using GitHub Pages, Netlify, or any static host. For FTP hosting, synchronize the **entire project or just `index.html`, `assets/`, and `data/papers.js`, `data/digest.js`** after updates. GitHub Pages/Netlify deployments can be automated; normal FTP upload requires a separate deployment step.

GitHub workflow repository write permissions must be available. The project does not ship with secrets; **never commit API keys**.

## Review and override records

You can use the **Reviewer workspace** at the bottom of the website to mark records as verified, excluded or requiring review. These choices are stored in browser local storage only; download `review_overrides.json` and put it in `data/` before rerunning the pipeline. This is a convenience interface, **not an authenticated or audit-trailed scholarly review system**.

Alternatively, populate `data/review_overrides.json` with the DOI as a key:

```json
{
  "10.1234/example": {
    "status": "verified",
    "domain": "Chemical hazards",
    "application": "Risk forecasting"
  },
  "10.5678/not-relevant": {"status": "excluded"}
}
```

Run the pipeline again to apply changes. Valid `status` values are `verified`, `excluded`, `needs_review`. The labels **refer to manual decisions entered by an authorized reviewer**; the script does not independently authenticate the reviewer. You should record reviewer identity, screening criteria and full-text audit trails before treating this as a scholarly screening system.

## Research-grade enhancements before publication

- Import the **161 included articles** from the original review, using the authors' actual extraction tables and original taxonomy (the starter data here is not a substitute).
- Freeze, version and validate search strings across OpenAlex and other indexes; add date windows that detect delayed indexing and backfilled records.
- Evaluate retrieval recall and title/abstract screening against gold-standard included and excluded sets; estimate missed papers; use dual human screening of uncertain records.
- Create a repeatable full-text assessment protocol. Automated candidates should be separated from verified inclusions in quantitative charts.
- Use validated topic codes, track disagreements and changes, and publish reproducible snapshots with methods and limitations.
- Add periodic synthesis with cited, exact-source-evidence sentences only once source-level checks are in place. This version intentionally avoids hallucinated AI summaries of research trends.

## Technical layout

```text
index.html                     Single-page website
assets/styles.css              Responsive styles
assets/app.js                  Filtering, charts, article details, exports
data/papers.json               Source dataset
 data/papers.csv               Static CSV for direct inspection
 agent/render_static.py        Rebuild no-JavaScript HTML snapshot, CSV, and standalone demo
 data/papers.js                JS mirror for offline viewing
 data/digest.json              Generated by pipeline on first run
 data/digest.js                Generated digest / preview placeholder
 data/review_overrides.json    Manual review decisions
 agent/seed.py                 Rebuild illustrative demo dataset (overwrites JSON/JS)
 agent/update.py               Scheduled OpenAlex candidate discovery & classification
 tests/test_pipeline.py        Unit tests
 .github/workflows/           Weekly scheduled workflow
```

## Tests

```bash
python -m unittest discover -s tests -v
```

No npm dependencies, runtime backend, database, or paid UI libraries. `python agent/render_static.py` rebuilds the progressive HTML snapshot after each data update. Work provided as an **independent research prototype**, not as an official Wageningen University & Research or FAO product.
