# Living AI for Food Safety — living evidence map

An independent, locally viewable and searchable evidence-map prototype that builds on van Meer et al. (2026), [*Artificial intelligence in food safety*](https://doi.org/10.1038/s41538-026-00925-1), *npj Science of Food*.

## Daily OpenAlex scan (from 2024)

The `Refresh literature` GitHub Actions workflow runs **every day at 06:15 UTC**.
It searches each year from **2024-01-01 through today**, fetching up to 20 pages
of 100 works per query/year. The results are deduplicated by DOI, classified as
**automated candidates**, and added to the public dashboard.

**Costs:** OpenAlex search is $0.001 per API call. The pipeline stops after at
most 900 search requests per run (approximately $0.90), or earlier if the
API reports that the available daily credits are nearly exhausted. It saves
`data/search_progress.json` and resumes from the next query/page on the next run.
Once all planned searches finish, it stops rather than artificially spending
the remaining free budget. New daily runs rescan the period to discover newly
indexed older publications. If the OpenAlex API cap or a query's 20-page limit
is reached, completeness is **not** guaranteed.

Set `OPENALEX_API_KEY` under repository **Settings → Secrets and variables
→ Actions → Repository secrets**. The API key is free; the workflow fails
with an actionable error if it is absent. Daily runs deliberately leave
`OPENAI_API_KEY` unset to avoid separate paid LLM costs. Avoid enabling paid
OpenAlex prepayment if you require strictly zero payment, since other use
of the same key can affect the remaining free budget.

## What exactly is included?

**166 distinct bibliographic records:**

- **160 unique original papers**, transcribed from the **161 included-study table entries** in Tables 1–5 of the published systematic review. One paper, reference **128** (Wang et al.), appears twice in Table 2 under two implementation contexts, so the number of unique papers in the tables is 160.
- **6 additional research articles** published after the review's literature-search cutoff (1 April 2024). They came from the previous DOI-linked demonstration dataset. They are labelled `post_review_sample` and **must not be presented as included in the original systematic review**.

The published article explicitly reports **161 included studies**, not 166. Here, 166 is the size of this particular *expanded and deduplicated* collection. `data/original_review_records.json` contains the original source records and reference numbers, while `data/starter_22_archive.json` preserves all 22 records from the previous demonstration version (only six were added to the current collection).

All original paper titles, years, and citations were transcribed from the article's reference list, with original table-level classifications retained (`domain`, `application`, `data_collection_method`, `original_ai_techniques`, and `target`). The extra broad display tags (`data_type`, `ai_method`) are automatically grouped from these table values and **have not been manually validated against the underlying papers**. Metadata were not re-checked paper by paper against publisher sites. Not every article has an explicit DOI in the article's references; missing DOI links therefore open a bibliographic search rather than asserting a guessed DOI. The published extraction tables should be the authoritative source for research-grade interpretation.

## Open the site

Open `index.html` in a browser, or open the separate **`Living_AI_Food_Safety_demo.html`** next to the ZIP. The standalone demo includes its data, CSS and JavaScript in one HTML file and works offline. All **166 records are prerendered**, even with JavaScript disabled. JavaScript adds full-text metadata search, filters (including review versus newer publications), article details, descriptive charts, review decisions, and downloads.

For local serving:

```bash
python -m http.server 8000
```

Then visit `http://localhost:8000` from the project directory.

## Data and provenance

- `data/papers.json` — live display database, all 166 distinct records, source-labelled.
- `data/papers.csv` — complete flat bibliographic export, including original table method and citation fields. The `additional_contexts` field is JSON encoded where needed.
- `data/original_review_records.json` — 160 original unique bibliographic records, original reference numbers and any secondary implementation contexts.
- `data/starter_22_archive.json` — preserved earlier curated demonstration data, not all displayed in the updated site.
- `agent/import_original_review.py` — reproducible extraction of Tables 1–5 from a locally provided PDF of the open-access review. The original PDF itself is not redistributed in this project.
- `agent/build_baseline.py` — creates the 166-record baseline from the original data and six post-review publications. **This overwrites `papers.json`; do not run after an automated update unless you intend to reset the dataset.**
- `agent/render_static.py` — rebuilds prerendered HTML, standalone HTML, and CSV after changes.

## Automatic candidate monitoring (not yet activated)

`agent/update.py` can search OpenAlex for new articles, deduplicate DOI-based records and classify candidate studies by rule-based heuristics or by an optional OpenAI model. The supplied `.github/workflows/update-literature.yml` schedules Monday updates when installed in a GitHub repository. Use repository secret `OPENALEX_API_KEY` (free key from https://openalex.org/settings/api); optionally `OPENAI_API_KEY` (separate, usage-billed OpenAI API). No OpenAI key means heuristic-only screening. On GitHub, enable Actions and run **Refresh literature** manually for the first test. The script writes new candidates and the generated dataset back to the default branch. The standalone offline demo does NOT update itself. This release has **not** been tested end-to-end with a live OpenAlex API in this network-restricted environment.

```bash
export OPENALEX_API_KEY='your-openalex-key'       # optional depending on API access
export OPENAI_API_KEY='your-openai-key'           # optional; usage costs may apply
python agent/update.py --dry-run --days 90 --per-query 40
python agent/update.py --days 90 --per-query 40
python agent/render_static.py
```

Newly retrieved papers are `automated_candidate`, never automatically marked as expert verified. A separate reviewer workspace records local browser decisions; download overrides to `data/review_overrides.json` to apply these through the pipeline. This is not a secure multiuser research-audit system; researcher approval and validation are necessary before treating candidates as review inclusions.

## Automatic public site publishing (optional)

When the workflow commits updated files using its automatic `GITHUB_TOKEN`, this does **not** by itself trigger a GitHub Pages branch build. The package therefore includes a separate opt-in `deploy` job that directly deploys a fresh Pages artifact on every successful literature refresh.

1. On GitHub: **Settings → Pages → Source: GitHub Actions**. For GitHub Free, use a public repository for Pages.
2. In **Settings → Secrets and variables → Actions → Variables**, create repository variable `PUBLISH_PAGES` with value `true`. This is a **variable**, not a secret.
3. Trigger **Actions → Refresh literature → Run workflow**. The `update` job refreshes data and the `deploy` job publishes the site. The public URL appears in Pages settings or the deploy job.

No Pages hosting is needed just to search and update the source data on GitHub. Keep in mind that a separate manually downloaded HTML demo is never live-connected to the GitHub repository. The site has no background browser agent; all retrieval occurs in the scheduled Python job.

If GitHub Actions cannot commit, check branch protection and workflow permissions. The workflow declares `contents: write` for its update job. Scheduled runs only execute on the repository's default branch and GitHub may disable inactive scheduled workflows in public repositories.

## Quality checks

```bash
python -m unittest discover -s tests -v
node --check assets/app.js
```

The supplied records, counts, filters, offline fallback and local page rendering were tested. In a headless browser, the search matched 13 Salmonella-related records, and the source filters returned 160 original-review and 6 newer records. A no-JavaScript test rendered all 166 records. The scholarly extraction has not been checked independently against every full text.

This is an independent research prototype, not an official Wageningen University & Research, FAO, or journal service.
