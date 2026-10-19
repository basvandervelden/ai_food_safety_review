# Private abstract retrieval: OpenAlex + Europe PMC / PubMed / Crossref

**Status (19 October 2026): paused pending private repository setup.**

The original public GitHub Actions workflow was disabled and removed.
Previously copied abstracts have been deleted from the current public
repository, and affected public data / website histories were rewritten.
Older direct GitHub commit URLs or platform caches may remain accessible
until GitHub performs its own purge.

## Public vs. private data

**Public repository (this one):** code, article DOIs, titles, provenance counts,
human screening labels where explicitly released, predictions, and evaluation.
The public discovery pool (`data/openalex_pool.json`) intentionally has
**no article abstract fields**. The publication website likewise contains
only bibliographic metadata and original short summaries.

**Private storage:** third-party abstract text, source URLs, timestamps, DOI
checks, and any restricted Scopus exports. Never commit those texts to this
public repository. The local path `private/abstract_enrichment.json` is
ignored by Git and is understood by the retrieval and classifier scripts.
**No remote private repository has been created or populated yet.**
Create a private repository and store the retrieved texts there before
turning on any scheduled bulk retrieval. GitHub's repository creation and
visibility controls are not exposed to the connected GitHub tool.

## Retrieval (after secure storage is ready)

`agent/enrich_abstracts.py` retrieves abstracts by **exact DOI** from:

1. Europe PMC REST API
2. PubMed E-utilities
3. Crossref REST API

It uses no ChatGPT Work, browser browsing, Scopus API, paid service, or PDFs.
Hard upper bounds are 500 paper lookups and 1,600 API requests per run.
It records source provenance; unavailable abstracts are rechecked after
30 days. The local private JSON cache is resumable.

`agent/asreview_classifier.py` reads the local private cache when scoring
public OpenAlex records. It does not publish that cache.

## Baseline and first run

19 October 2026: 3,763 OpenAlex records, with 2,458 reconstructed abstracts.
The first enrichment run recovered an additional **208** abstracts from
Europe PMC, for a measured combined availability of **70.8%**.
Those recovery files are no longer in the public repository. This count
describes a historical run, not currently stored public text.

## Licensing

Publicly accessible APIs and research use do not necessarily authorize
bulk third-party abstract republication. Check reuse terms before distributing
a collection of full abstract texts. Original 0/1 ASReview labels and
DOI-linked bibliographic information can be published separately.
