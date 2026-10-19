# ASReview-trained screening classifier — preparation for the original export

**Status:** pipeline prepared and tested with synthetic labels, not yet trained on the real ASReview decisions. Its outputs do not change the live website or the existing inclusion decisions.

## Input required

Provide the original ASReview export (.xlsx, .xlsm, .csv or .tsv) containing, ideally:

- **Title**, **abstract**, DOI (when available).
- **Human 0/1 screening decision**: 1 = include, 0 = exclude.
- Unlabelled/-1/empty records are skipped, **not** treated as negative labels.
- If multiple sheets or ambiguous column names exist, inspect the file first and specify `--sheet`, `--label-col`, etc.

**Do not commit the ASReview export to this public repository.** Upload it to the private conversation for processing, or run the script locally; `.gitignore` excludes common filenames and model artifacts.

## Commands

```bash
python agent/asreview_classifier.py inspect --input /private/ASReview_export.xlsx

python -m pip install -r requirements-classifier.txt

python agent/asreview_classifier.py train \
  --input /private/ASReview_export.xlsx \
  --pool data/openalex_pool.json \
  --output-dir output/asreview \
  --target-recall 0.95 --sample-size 300
```

Training writes (locally, **not** to GitHub Pages):

- `evaluation.json` — held-out test-set precision, recall, F1, PR-AUC and confusion matrix.
- `heldout_predictions.csv` — individual independent holdout results.
- `classifier.joblib` — fitted TF-IDF + class-balanced logistic regression and selected threshold.
- `all_discovered_predictions.csv` — score and prediction for the full OpenAlex discovery pool, not just the formerly accepted records.
- `blind_sample.csv` — up to 300 randomly drawn articles from three model-score strata; model scores and predictions are **hidden** during human review.
- `sample_frame.json` — sampling probabilities/stratum sizes to enable unbiased weighted evaluation.

After independently completing all human 0/1 labels in a copy of `blind_sample.csv`:

```bash
python agent/asreview_classifier.py evaluate-sample \
  --labels output/asreview/blind_sample_labeled.csv \
  --frame output/asreview/sample_frame.json \
  --output output/asreview/sample_evaluation.json
```

The evaluation uses inverse sampling fractions to estimate precision, recall, and relevant-paper prevalence across **the searched OpenAlex candidate pool**. It cannot measure recall of the **search queries** relative to the entire scientific literature; that requires a separate search-retrieval benchmark.

## Collection completeness

The daily agent now accumulates **all** OpenAlex discoveries in `data/openalex_pool.json`, including works rejected by the old keyword heuristic. It adds papers to this archive on the **next successful scheduled/manual scan**. Before that first scan, this file does not exist.

`data/papers.json` remains the live candidate evidence map. Do not use it as the full independent test pool: it omits rejected papers. Do not train directly on its automatically assigned relevance labels.

## Study-design safeguards

1. All **threshold selection and model development** occur on the 80% training portion (stratified CV), leaving 20% ASReview human-labelled papers as a held-out test set.
2. The final model is refitted on all labelled ASReview papers only **after** the held-out metrics have been recorded. Original 0/1 labels are not changed.
3. The original ASReview dataset is **active-learning selected**. Thus its holdout metrics are not representative performance estimates for the newly discovered papers. The independently labelled stratified sample provides the more relevant external validation.
4. Compare the new model with the existing keyword heuristic, and investigate disagreements/false negatives. If searching recall matters, independently verify that known relevant papers are found by OpenAlex searches.
5. Human-review disagreements need adjudication, and a separate doubly-reviewed sample is needed to estimate interobserver agreement.
6. The current classifier is a transparent baseline, not calibrated confidence. Do not interpret model probabilities as true inclusion probabilities before calibration.
7. No deployment of automated include/exclude decisions to the public site is wired up. Require validation and approval before using the classifier to exclude papers from a systematic review.

## Reproducibility

The train/test split is seeded (default 42), DOI records are deduplicated, human labels 0/1 remain the source of truth, and prediction/sampling files preserve the sampling frame. `python -m unittest discover -s tests -v` includes ASReview import and label-safety tests.

For the initial paper, report the original inclusion/exclusion criteria, ASReview human-label composition, prior review's search cutoff, model development, held-out evaluation, external blinded sample with sampling weights, and a plan for ongoing model drift checks.
