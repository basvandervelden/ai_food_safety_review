# Filling missing OpenAlex abstracts without ChatGPT Work

## Overview

The [Recover missing abstracts](../.github/workflows/enrich-abstracts.yml)
workflow runs daily at **08:45 UTC** (GitHub Actions can start later).
It operates exclusively through HTTP APIs, **not through ChatGPT Work, a browser
agent, publisher website scraping, or a subscription**.

Baseline from 19 October 2026: **3,763 DOI-bearing OpenAlex records**, of which
**2,458 (65.3%)** already have reconstructed abstracts and **1,305** lack one.

For up to **500 missing papers per run**, the code requests in order:

1. [Europe PMC REST](https://europepmc.org/RestfulWebService) by exact DOI.
2. [PubMed E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25497/) with
   DOI search, then XML abstract, verifying the returned DOI.
3. [Crossref REST](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
   by exact DOI (with HTML/JATS markup removed).

The script never accepts an abstract when the returned DOI differs from the
requested DOI. It waits between API calls, handles rate limits with retries,
has a hard maximum of **1,600 requests** and **500 candidate articles** per
run, pauses after persistent provider errors and records the original source.

## Files and integration

- `agent/enrich_abstracts.py`: standard-library retrieval and safe caching.
- `data/abstract_enrichment.json`: persistent DOI-keyed provenance, abstracts,
  lookup timestamps and negative lookups.
- `data/abstract_enrichment_report.md`: public summary of coverage
  and additional sources.
- `data/abstract_enrichment_report.json`: machine-readable metrics.
- `agent/asreview_classifier.py`: automatically uses recovered abstracts
  where OpenAlex has none. Original OpenAlex text is never overwritten.

The GitHub Pages deployment does **not** copy the enrichment cache. It is
stored as source data in the repository and is therefore available to GitHub
repository readers.

Previously unavailable abstracts are rechecked only after **30 days**,
rather than wasting calls every day. Newly indexed OpenAlex publications
are picked up on subsequent runs. Manual action:
**Actions → Recover missing abstracts → Run workflow**.

## Reuse and provenance

The public APIs make text retrievable, but publisher copyright or licenses
may still govern bulk redistribution of abstracts. Crossref warns
specifically that abstracts can carry publisher/author copyright. This
pipeline retains exact source and identifiers to support later permission
audits. **Do not add private Scopus exports or institution-only full-text
material to this public repository.** A private repository is optional if
we decide to archive that restricted material later.

This pipeline does not estimate search recall: it only enriches previously
discovered, DOI-bearing articles.
