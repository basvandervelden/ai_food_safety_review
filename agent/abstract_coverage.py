#!/usr/bin/env python3
"""Audit title/abstract availability for *all* preserved OpenAlex discoveries.

The pool includes heuristic negatives; it is not the screened-in evidence map.
This is an availability audit, not abstract accuracy or licensing verification.
"""
from collections import Counter,defaultdict
from datetime import datetime,timezone
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
POOL=ROOT/"data"/"openalex_pool.json"
OUTPUT_JSON=ROOT/"data"/"abstract_coverage.json"
OUTPUT_MD=ROOT/"data"/"abstract_coverage.md"

def summarise(rows):
    unique={}
    for row in rows:
        key=row.get("id") or row.get("doi")
        if key:unique[key]=row
    records=list(unique.values())
    def stats(items):
        n=len(items)
        available=sum(bool(str(x.get("abstract") or "").strip()) for x in items)
        usable=sum(len(str(x.get("abstract") or "").strip())>=100 for x in items)
        return {"total":n,"abstract_present":available,
                "abstract_missing":n-available,
                "abstract_present_pct":round(100*available/n,1) if n else None,
                "abstract_100_chars_or_more":usable,
                "abstract_100_chars_or_more_pct":round(100*usable/n,1) if n else None}
    groups=defaultdict(list)
    for row in records:
        year=row.get("year")
        if not year:
            year=str(row.get("date") or "")[:4]
        groups[str(year) if year else "unknown"].append(row)
    return {"generated_at":datetime.now(timezone.utc).isoformat(),
            "scope":"All DOI-bearing, English-language article/review OpenAlex records retained by the automated discovery pipeline",
            "measurement":"Nonempty reconstructed abstract; >=100 characters is a rough proxy for usable text, not validation",
            "overall":stats(records),
            "by_publication_year":{k:stats(v) for k,v in sorted(groups.items())}}

def render_report(report):
    overall=report["overall"]
    def fmt(n,d):return f"{n:,} / {d:,}"
    lines=["# Abstract availability in OpenAlex discovery pool","",
           f"Last generated (UTC): {report['generated_at']}","",
           f"Scope: {report['scope']}.","",
           "## All retrieved publications","",
           f"- **Records:** {overall['total']:,}",
           f"- **Abstract available:** {fmt(overall['abstract_present'],overall['total'])} ({overall['abstract_present_pct']}%)",
           f"- **Abstract missing:** {overall['abstract_missing']:,}",
           f"- **Abstract >=100 characters:** {fmt(overall['abstract_100_chars_or_more'],overall['total'])} ({overall['abstract_100_chars_or_more_pct']}%)",
           "","## By publication year","","| Year | Papers | With abstract | Abstract coverage | >=100 characters |",
           "| --- | ---: | ---: | ---: | ---: |"]
    for year,stats in report["by_publication_year"].items():
        lines.append(f"| {year} | {stats['total']:,} | {stats['abstract_present']:,} | {stats['abstract_present_pct']}% | {stats['abstract_100_chars_or_more']:,} |")
    lines+=["",
            "Notes: counts refer to all retained OpenAlex discoveries, **including the papers screened out by the current keyword heuristic**.",
            "The OpenAlex parser filters for DOI-bearing English articles/reviews; excluded formats and missing DOIs are not in the denominator.",
            "Availability does not imply abstract accuracy, completeness, or permission to redistribute.",
            "The reconstructed abstract is truncated to 9,000 characters by the retrieval agent.",
            ""]
    return "\n".join(lines)

def main():
    if not POOL.exists():raise SystemExit("Missing data/openalex_pool.json: run the OpenAlex discovery agent first")
    rows=json.loads(POOL.read_text(encoding="utf-8"))
    if not isinstance(rows,list):raise SystemExit("Unexpected OpenAlex pool structure")
    report=summarise(rows)
    OUTPUT_JSON.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    OUTPUT_MD.write_text(render_report(report),encoding="utf-8")
    print(render_report(report))

if __name__=="__main__":main()
