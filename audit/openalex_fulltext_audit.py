#!/usr/bin/env python3
"""Metadata-only OpenAlex availability audit of the 166-paper review baseline.

No full texts are downloaded; unresolved bibliographic matches remain unknown.
Run: python audit/openalex_fulltext_audit.py (OPENALEX_API_KEY required)
"""
from __future__ import annotations

import csv
from difflib import SequenceMatcher
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "papers.json"
DEST = ROOT / "data"
SOURCE_GROUPS = {"original_review", "post_review_sample"}
BASE_URL = "https://api.openalex.org/works"
REQUEST_COUNT = 0
MAX_REQUESTS = 340  # Stop rather than make an unbounded number of paid API calls.


def cleaned(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", s.casefold()))


def normalize_doi(s):
    s = str(s or "").strip()
    s = re.sub(r"^https?://(?:dx\\.)?doi\\.org/", "", s, flags=re.I)
    return s.casefold()


def author_surname(paper):
    authors = paper.get("authors") or []
    if not authors:
        return ""
    first = authors[0].split(",", 1)[0]
    if "," not in authors[0]:
        first = authors[0].split()[-1]
    return cleaned(first)


def candidate_surname(work):
    authorships = work.get("authorships") or []
    if not authorships:
        return ""
    name = (authorships[0].get("author") or {}).get("display_name") or ""
    return cleaned(name.split()[-1])


def assess_match(paper, work, *, by_doi=False):
    """Return accepted, match method, title similarity; avoid false title matches."""
    if not work or not work.get("id"):
        return False, "unresolved", 0.0
    src = cleaned(paper.get("title"))
    dst = cleaned(work.get("display_name") or work.get("title"))
    ratio = SequenceMatcher(None, src, dst).ratio() if src and dst else 0.0
    sa, sb = set(src.split()), set(dst.split())
    overlap = len(sa & sb) / max(1, len(sa | sb))
    yr = int(paper.get("year") or 0)
    candidate_year = int(work.get("publication_year") or 0)
    year_ok = not yr or not candidate_year or abs(yr - candidate_year) <= 1
    ps, cs = author_surname(paper), candidate_surname(work)
    author_ok = not ps or not cs or ps == cs
    doi_same = bool(normalize_doi(paper.get("doi")) and normalize_doi(paper.get("doi")) == normalize_doi(work.get("doi")))

    if by_doi and doi_same and (ratio >= 0.72 or not dst):
        return True, "doi", ratio
    if not year_ok:
        return False, "year_mismatch", ratio
    if ratio >= 0.97 and (author_ok or not cs):
        return True, "exact_title", ratio
    if ratio >= 0.91 and overlap >= 0.78 and author_ok:
        return True, "title_author_year", ratio
    return False, "low_confidence", ratio


def api_json(url, key):
    global REQUEST_COUNT
    headers = {"Accept": "application/json", "User-Agent": "LivingAIFoodSafety/1.0 (research metadata audit)"}
    if key:
        headers["Authorization"] = "Bearer " + key
    for attempt in range(4):
        if REQUEST_COUNT >= MAX_REQUESTS:
            raise RuntimeError("Audit reached safety cap of %d requests" % MAX_REQUESTS)
        try:
            REQUEST_COUNT += 1
            with urlopen(Request(url, headers=headers), timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            detail = exc.read(500).decode("utf-8", "replace")
            if exc.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(min(20, 2 ** attempt * 2))
                continue
            raise RuntimeError("OpenAlex HTTP %d: %s" % (exc.code, detail[:160])) from exc
        except (URLError, TimeoutError) as exc:
            if attempt < 3:
                time.sleep(min(20, 2 ** attempt * 2))
                continue
            raise RuntimeError("OpenAlex connection failed: %s" % exc) from exc


def get_by_doi(doi, key):
    return api_json(BASE_URL + "/https://doi.org/" + quote(normalize_doi(doi), safe="/"), key)


def search_by_title(title, key):
    params = urlencode({"search.title": title[:500], "per_page": 7})
    return api_json(BASE_URL + "?" + params, key).get("results") or []


def resolve(paper, key):
    notes = []
    if paper.get("doi"):
        try:
            work = get_by_doi(paper["doi"], key)
            good, how, score = assess_match(paper, work, by_doi=True)
            if good:
                return work, how, score, ""
            notes.append("DOI match unverified (%s, %.2f)" % (how, score))
        except RuntimeError as exc:
            if "HTTP 404" not in str(exc):
                raise
            notes.append("DOI not found in OpenAlex")
    results = search_by_title(paper.get("title") or "", key)
    matches = []
    for w in results:
        accepted, how, score = assess_match(paper, w)
        if accepted:
            matches.append((score, w, how))
    matches.sort(key=lambda x: x[0], reverse=True)
    if not matches:
        return None, "unresolved", None, "; ".join(notes + ["No high-confidence title match"])
    if len(matches) > 1 and matches[0][0] - matches[1][0] < 0.025 and matches[0][1]["id"] != matches[1][1]["id"]:
        return None, "ambiguous", None, "Multiple near-identical OpenAlex candidates"
    score, work, how = matches[0]
    return work, how, score, "; ".join(notes)


def record(paper, key):
    work, method, score, note = resolve(paper, key)
    matched = work is not None
    availability = (work.get("has_content") or {}) if matched else {}
    urls = (work.get("content_urls") or {}) if matched else {}
    oa = (work.get("open_access") or {}) if matched else {}
    location = (work.get("best_oa_location") or {}) if matched else {}
    return {
        "source_id": paper.get("id", ""),
        "source_group": paper.get("source_group", ""),
        "title": paper.get("title", ""),
        "year": paper.get("year", ""),
        "doi_in_dataset": paper.get("doi", ""),
        "match_status": "matched" if matched else method,
        "match_method": method if matched else "",
        "title_similarity": round(score, 3) if score is not None else "",
        "openalex_id": work.get("id", "") if matched else "",
        "openalex_doi": normalize_doi(work.get("doi")) if matched else "",
        "openalex_title": work.get("display_name", "") if matched else "",
        "is_open_access": bool(oa.get("is_oa")) if matched else "",
        "oa_status": oa.get("oa_status", "") if matched else "",
        "has_openalex_pdf": bool(availability.get("pdf")) if matched else "",
        "has_openalex_xml": bool(availability.get("grobid_xml")) if matched else "",
        "openalex_pdf_url": urls.get("pdf", "") if matched else "",
        "openalex_xml_url": urls.get("grobid_xml", "") if matched else "",
        "best_oa_license": location.get("license", "") if matched else "",
        "note": note,
    }


def summarize(rows):
    matched = [r for r in rows if r["match_status"] == "matched"]
    def count(name):
        return sum(r[name] is True for r in matched)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "160 original unique review papers + 6 post-review sample papers; excludes automated candidates",
        "total": len(rows), "matched": len(matched), "unresolved": len(rows)-len(matched),
        "oa": count("is_open_access"), "pdf": count("has_openalex_pdf"), "xml": count("has_openalex_xml"),
        "by_group": {group: {
            "total": sum(r["source_group"] == group for r in rows),
            "matched": sum(r["source_group"] == group and r["match_status"] == "matched" for r in rows),
            "oa": sum(r["source_group"] == group and r["is_open_access"] is True for r in rows),
            "pdf": sum(r["source_group"] == group and r["has_openalex_pdf"] is True for r in rows),
            "xml": sum(r["source_group"] == group and r["has_openalex_xml"] is True for r in rows)
        } for group in ("original_review", "post_review_sample")}
    }


def markdown_report(s):
    body = [
        "# OpenAlex fulltext availability audit", "",
        "Run (UTC): " + s["generated_at_utc"], "",
        "**Metadata only.** PDF/XML flags indicate copies held by OpenAlex, not verified retrieval or parsing.", "",
        "| Metric | Count |", "| --- | ---: |",
        "| Baseline records | %d |" % s["total"],
        "| High-confidence OpenAlex matches | %d/%d |" % (s["matched"], s["total"]),
        "| Unresolved or ambiguous records | %d |" % s["unresolved"],
        "| Open access (among matched) | %d/%d |" % (s["oa"], s["matched"]),
        "| OpenAlex-hosted PDF (among matched) | %d/%d |" % (s["pdf"], s["matched"]),
        "| OpenAlex-hosted GROBID XML (among matched) | %d/%d |" % (s["xml"], s["matched"]),
        "", "## By source group", "",
        "| Group | Baseline | Matched | OA | PDF | XML |",
        "| --- | ---: | ---: | ---: | ---: | ---: |"
    ]
    for group, g in s["by_group"].items():
        body.append("| %s | %d | %d | %d | %d | %d |" %
                    (group, g["total"], g["matched"], g["oa"], g["pdf"], g["xml"]))
    body.extend([
        "", "See [fulltext_audit.csv](fulltext_audit.csv) for the status of every publication.",
        "", "Unmatched records remain **unknown**, not closed access. Ambiguous titles require manual review.",
        "Scope: 160 original-review papers + six post-review samples; automated candidates excluded.",
        "OpenAlex availability does not itself grant any additional copyright or mining rights.", ""
    ])
    return "\n".join(body)


def main():
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    baseline = [p for p in data["papers"] if p.get("source_group") in SOURCE_GROUPS]
    if len(baseline) != 166 or sum(p["source_group"] == "original_review" for p in baseline) != 160:
        raise SystemExit("Unexpected baseline composition: refusing to misreport 166-paper results.")
    key = os.getenv("OPENALEX_API_KEY", "").strip()
    if not key:
        raise SystemExit("Missing OPENALEX_API_KEY repository secret.")
    rows = []
    for i, paper in enumerate(baseline, 1):
        try:
            rows.append(record(paper, key))
        except RuntimeError as exc:
            raise SystemExit("Stopping without incomplete reports at %d/%d (%s): %s" %
                             (i, len(baseline), paper["id"], exc)) from exc
        if i % 20 == 0 or i == len(baseline):
            print("Audited %d/%d, requests: %d" % (i, len(baseline), REQUEST_COUNT), flush=True)
        time.sleep(0.12)
    summary = summarize(rows)
    with (DEST / "fulltext_audit.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (DEST / "fulltext_audit.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report = markdown_report(summary)
    (DEST / "fulltext_audit.md").write_text(report, encoding="utf-8")
    print(report)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(report)


if __name__ == "__main__":
    main()
