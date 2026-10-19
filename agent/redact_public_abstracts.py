#!/usr/bin/env python3
"""Remove third-party abstract texts from *public* research data exports.

Does not affect author-supplied titles/DOIs, independent human screening labels,
or short original research summaries. Does not rewrite past Git commits.
"""
import csv
import io
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
FIELDS={"abstract","abstract_inverted_index","abstract_text","abstracttext","raw_abstract","abstract_source","abstract_source_url"}
JSON_FILES=("openalex_pool.json","papers.json","original_review_records.json","starter_22_archive.json","review_queue.json")

def scrub(value):
    if isinstance(value,list):
        return [scrub(v) for v in value]
    if isinstance(value,dict):
        return {k:scrub(v) for k,v in value.items() if k.lower() not in FIELDS}
    return value

def redact():
    for name in JSON_FILES:
        path=DATA/name
        if path.exists():
            data=json.loads(path.read_text(encoding="utf-8"))
            path.write_text(json.dumps(scrub(data),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            print("Sanitized:",path)
    if (DATA/"papers.json").exists():
        papers=json.loads((DATA/"papers.json").read_text(encoding="utf-8"))
        safe=json.dumps(papers,separators=(",",":"),ensure_ascii=False).replace("<","\\u003c")
        (DATA/"papers.js").write_text("window.LIVING_REVIEW_DATA = "+safe+";\n",encoding="utf-8")
    csv_path=DATA/"papers.csv"
    if csv_path.exists():
        with csv_path.open(newline="",encoding="utf-8-sig") as f:
            reader=csv.DictReader(f);headers=reader.fieldnames or []
            kept=[h for h in headers if h.lower() not in FIELDS]
            rows=[{k:v for k,v in row.items() if k in kept} for row in reader]
        with csv_path.open("w",newline="",encoding="utf-8-sig") as f:
            wr=csv.DictWriter(f,fieldnames=kept);wr.writeheader();wr.writerows(rows)
    for name in ("abstract_enrichment.json",):
        path=DATA/name
        if path.exists():
            path.unlink()
            print("Deleted public abstract cache:",path)

def audit():
    for name in JSON_FILES:
        path=DATA/name
        if path.exists():
            raw=json.loads(path.read_text(encoding="utf-8"))
            def find(v):
                if isinstance(v,dict):
                    assert not FIELDS.intersection(k.lower() for k in v),f"Abstract fields in {name}"
                    for x in v.values():find(x)
                elif isinstance(v,list):
                    for x in v:find(x)
            find(raw)
    assert not (DATA/"abstract_enrichment.json").exists()
    data_js=(DATA/"papers.js").read_text(encoding="utf-8")
    for key in FIELDS:
        assert f'"{key}"' not in data_js
    print("Verified: no abstract fields in public research data.")

if __name__=="__main__":
    redact()
    audit()
