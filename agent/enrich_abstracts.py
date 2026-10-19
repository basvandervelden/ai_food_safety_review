#!/usr/bin/env python3
"""Enrich OpenAlex discoveries missing abstracts via public scholarly APIs.

No browser automation, Scopus, paid APIs, or full-text downloads. DOI matching
is mandatory; absent/uncertain matches are NOT assigned to a different paper.
The enrichment is a public, provenance-labelled research data cache. Evaluate
redistribution terms before republishing abstracts beyond this research archive.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode,quote
from urllib.request import Request,urlopen
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
POOL=ROOT/"data"/"openalex_pool.json"
CACHE=ROOT/"private"/"abstract_enrichment.json"
REPORT=ROOT/"data"/"abstract_enrichment_report.json"
MARKDOWN=ROOT/"data"/"abstract_enrichment_report.md"
USER_AGENT="LivingAIFoodSafety/1.0 (academic research; https://github.com/basvandervelden/ai_food_safety_review)"
DEFAULT_MAX=500
MAX_CALLS=1600
MIN_ABSTRACT_CHARS=80
MIN_DELAY_SECONDS=.24

def norm_doi(value):
    return re.sub(r"^https?://(?:dx\.)?doi\.org/","",str(value or "").strip().lower()).strip()

class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]
    def handle_data(self,data):
        self.parts.append(data)

def clean(value):
    parser=_Text()
    parser.feed(re.sub(r"<\?xml[^>]*\?>","",str(value or "")))
    return re.sub(r"\s+"," "," ".join(parser.parts)).strip()[:15000]

def usable(value):
    return len(value)>=MIN_ABSTRACT_CHARS

class LimitedHTTP:
    """Bounded REST calls with polite pacing and transient-status backoff."""
    def __init__(self,max_calls=MAX_CALLS,delay=MIN_DELAY_SECONDS):
        self.max_calls=max_calls
        self.delay=delay
        self.calls=0
        self.last=0.0
    def get(self,url,*,raw=False):
        for retry in range(3):
            if self.calls>=self.max_calls: raise StopIteration("Daily API-request ceiling reached")
            wait=self.delay-(time.monotonic()-self.last)
            if wait>0:time.sleep(wait)
            self.calls+=1
            self.last=time.monotonic()
            try:
                with urlopen(Request(url,headers={"User-Agent":USER_AGENT,"Accept":"application/xml" if raw else "application/json"}),timeout=20) as r:
                    payload=r.read()
                    return payload if raw else json.loads(payload)
            except HTTPError as exc:
                if exc.code==404:return None
                if exc.code not in (429,500,502,503,504) or retry==2:
                    raise RuntimeError(f"HTTP {exc.code} from {url.split('?')[0]}") from exc
                try: backoff=min(20,float(exc.headers.get("Retry-After","0")))
                except ValueError:backoff=0
                time.sleep(max(backoff,2**retry*2))
            except (URLError,TimeoutError) as exc:
                if retry==2:raise RuntimeError(f"API unreachable: {url.split('?')[0]}") from exc
                time.sleep(2**retry*2)

def europe_pmc(doi,http):
    q=urlencode({"query":f'DOI:"{doi}"',"format":"json","resultType":"core","pageSize":3})
    data=http.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search?"+q)
    for result in (data or {}).get("resultList",{}).get("result",[]):
        if norm_doi(result.get("doi"))==doi:
            abstract=clean(result.get("abstractText"))
            if usable(abstract):
                return {"abstract":abstract,"source":"Europe PMC","source_id":str(result.get("id") or ""),
                        "source_url":"https://europepmc.org/article/"+str(result.get("source","MED"))+"/"+str(result.get("id") or "")}
    return None

def pubmed(doi,http):
    params=urlencode({"db":"pubmed","term":f'"{doi}"[DOI]',"retmode":"json","retmax":3,"tool":"LivingAIFoodSafety"})
    r=http.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"+params)
    ids=(r or {}).get("esearchresult",{}).get("idlist",[])
    if not ids:return None
    query=urlencode({"db":"pubmed","id":",".join(ids[:3]),"retmode":"xml","tool":"LivingAIFoodSafety"})
    xml=http.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?"+query,raw=True)
    if not xml:return None
    root=ET.fromstring(xml)
    for article in root.findall(".//PubmedArticle"):
        dois=[norm_doi(x.text) for x in article.findall(".//ArticleId[@IdType='doi']")]
        if doi not in dois:continue
        passages=[]
        for el in article.findall(".//Abstract/AbstractText"):
            t=" ".join(el.itertext()).strip()
            if t:passages.append((el.attrib.get("Label","")+": " if el.attrib.get("Label") else "")+t)
        abstract=clean(" ".join(passages))
        if usable(abstract):
            pmid=article.findtext(".//MedlineCitation/PMID") or ""
            return {"abstract":abstract,"source":"PubMed","source_id":pmid,
                    "source_url":"https://pubmed.ncbi.nlm.nih.gov/"+pmid+"/"}
    return None

def crossref(doi,http):
    url="https://api.crossref.org/works/"+quote(doi,safe="")
    data=http.get(url)
    meta=(data or {}).get("message",{})
    if norm_doi(meta.get("DOI"))!=doi:return None
    abstract=clean(meta.get("abstract"))
    if not usable(abstract):return None
    return {"abstract":abstract,"source":"Crossref","source_id":doi,
            "source_url":"https://api.crossref.org/works/"+quote(doi,safe="")}

PROVIDERS=(europe_pmc,pubmed,crossref)

def load(path,default):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:return default

def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(path)

def summary(pool,cache,checked,requests,errors):
    missing=[p for p in pool if not str(p.get("abstract") or "").strip()]
    found={norm_doi(p.get("doi")):p for p in missing if norm_doi(p.get("doi"))}
    successes={doi:entry for doi,entry in cache.items() if entry.get("status")=="found" and doi in found and usable(entry.get("abstract",""))}
    cnt=Counter(v["source"] for v in successes.values())
    return {"updated_at":datetime.now(timezone.utc).isoformat(),
            "total_openalex_records":len(pool),
            "openalex_abstracts_present":len(pool)-len(missing),
            "openalex_abstracts_missing":len(missing),
            "additional_abstracts_found":len(successes),
            "combined_abstracts_present":len(pool)-len(missing)+len(successes),
            "combined_coverage_pct":round(100*(len(pool)-len(missing)+len(successes))/len(pool),1) if pool else None,
            "still_missing":len(missing)-len(successes),
            "additional_by_source":dict(cnt),
            "processed_today":checked,"requests_this_run":requests,"provider_errors":errors,
            "cached_misses":sum(v.get("status")=="not_found" for v in cache.values())}

def format_report(r):
    return "\n".join([
       "# Abstract enrichment via public research APIs","",
       "Latest run (UTC): "+r["updated_at"],"",
       "| Measure | Count |","| --- | ---: |",
       f"| OpenAlex records | {r['total_openalex_records']:,} |",
       f"| Abstracts already available from OpenAlex | {r['openalex_abstracts_present']:,} |",
       f"| Additional abstracts recovered | {r['additional_abstracts_found']:,} |",
       f"| **Combined abstract coverage** | **{r['combined_coverage_pct']}%** |",
       f"| Still missing abstracts | {r['still_missing']:,} |",
       f"| Papers checked in last run | {r['processed_today']:,} |",
       f"| API calls in last run | {r['requests_this_run']:,} |",
       "",
       "Additional abstracts by source: "+", ".join(f"{k}: {v}" for k,v in sorted(r["additional_by_source"].items())), "",
       "DOI-exact matching; no website browsing, bulk full-text download, OpenAI API or Work usage.",
       "Only the candidate universe indexed by OpenAlex and preserved in openalex_pool.json is considered.",
       "Missing results are revisited after 30 days. A blank abstract is never treated as irrelevant.",
       "Reconstructed abstracts remain subject to the publisher/author's applicable reuse terms.", ""
    ])

def run(pool,cache,http,*,max_articles=DEFAULT_MAX,days_to_retry=30,save_every=25,providers=PROVIDERS):
    now=datetime.now(timezone.utc)
    processed=0
    errors=0
    for p in pool:
        doi=norm_doi(p.get("doi"))
        if not doi or str(p.get("abstract") or "").strip():continue
        entry=cache.get(doi,{})
        if entry.get("status")=="found" and usable(entry.get("abstract","")):continue
        if entry.get("status")=="not_found":
            try:
                previous=datetime.fromisoformat(entry["checked_at"])
                if now-previous<timedelta(days=days_to_retry):continue
            except (ValueError,KeyError):pass
        if processed>=max_articles:break
        candidate=None;fault=False
        try:
            for service in providers:
                candidate=service(doi,http)
                if candidate:break
        except StopIteration:
            break
        except (RuntimeError,ET.ParseError,ValueError) as err:
            errors+=1;fault=True
            print(f"Temporary lookup issue for {doi}: {err}",file=sys.stderr)
        if not fault:
            cache[doi]={**candidate,"status":"found","checked_at":now.isoformat()} if candidate else {
                "status":"not_found","checked_at":now.isoformat()}
            processed+=1
        if errors>=8:
            print("Pausing: too many provider errors",file=sys.stderr)
            break
        if processed and processed%save_every==0:save(CACHE,cache)
    return processed,errors

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-articles",type=int,default=DEFAULT_MAX)
    parser.add_argument("--max-requests",type=int,default=MAX_CALLS)
    parser.add_argument("--report-only",action="store_true")
    args=parser.parse_args(argv)
    if not (0<=args.max_articles<=DEFAULT_MAX) or not (1<=args.max_requests<=MAX_CALLS):
        parser.error("Hard maximum: 500 articles and 1600 API calls per run")
    pool=load(POOL,None)
    if not isinstance(pool,list):parser.error("Missing data/openalex_pool.json. Run OpenAlex discovery first.")
    cache=load(CACHE,{})
    if not isinstance(cache,dict):parser.error("Malformed abstract-enrichment cache")
    http=LimitedHTTP(max_calls=args.max_requests)
    checked=errors=0
    if not args.report_only:
        checked,errors=run(pool,cache,http,max_articles=args.max_articles)
        save(CACHE,cache)
    info=summary(pool,cache,checked,http.calls,errors)
    save(REPORT,info)
    MARKDOWN.write_text(format_report(info),encoding="utf-8")
    print(format_report(info))

if __name__=="__main__":main()
