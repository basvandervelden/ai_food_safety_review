#!/usr/bin/env python3
"""Update a living, *candidate* literature map from OpenAlex.

No automatic paper is declared included in a systematic review. LLM screening is
optional and all automated output is clearly labelled pending validation.
Standard-library-only implementation, suitable for GitHub Actions and cron.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT/'data'/'papers.json'
DOMAINS = ['Microbiological hazards','Chemical hazards','Food fraud & authenticity','Foodborne illness','General food safety']
APPLICATIONS = ['Laboratory testing','Risk forecasting','Risk factor analysis','Inspection & enforcement','Early warning','Methods & perspectives']
DATATYPES = ['Spectroscopy','Imaging & microscopy','Mass spectrometry','Monitoring & climate','Genomics & sequencing','Text & reports','Sensors & biosensors','Multimodal','Literature & reviews','Other']
AI_METHODS = ['Classical machine learning','Deep learning','LLMs / foundation models','Hybrid / ensemble','Review / synthesis','Other / unspecified']

# Dashboard grouping: single-label by prominent technique, without modifying the
# historical per-paper taxonomy or conflating reviews with techniques.
AI_FAMILIES = ['Machine learning (ML)', 'Deep learning (DL)', 'LLMs / foundation models', 'Other / mixed']
FM_SIGNALS = [r'\blarge language models?\b',r'\bfoundation models?\b',r'\bLLMs?\b',r'\bChatGPT\b',
              r'\bGPT[- ]?[345]\b',r'\bgenerative (?:AI|artificial intelligence|language model)',
              r'\bvision[- ]language models?\b',r'\bmultimodal (?:large )?language models?\b']
def family_from_record(p):
    method=str(p.get('ai_method') or '').lower()
    title=str(p.get('title') or '')
    family=p.get('ai_family')
    if family in AI_FAMILIES and family != 'Other / mixed': return family
    if any(re.search(pattern,title,re.I) for pattern in FM_SIGNALS) or 'llm' in method or 'foundation model' in method:
        return AI_FAMILIES[2]
    if 'deep learning' in method or 'neural network' in method or re.search(r'\bdeep learning\b',title,re.I):
        return AI_FAMILIES[1]
    if 'classical machine learning' in method or re.search(r'\bmachine learning\b',title,re.I):
        return AI_FAMILIES[0]
    return AI_FAMILIES[3]

# Deliberately include broader subject queries to catch works that do not say "AI".
SEARCHES = [
    '"food safety" "machine learning"',
    '"food safety" "deep learning"',
    '"foodborne pathogen" detection',
    '"mycotoxin" prediction',
    '"pesticide residues" spectroscopy',
    '"Salmonella" classification food',
    '"food fraud" chemometrics',
    '"food safety" inspection prediction',
    '"aflatoxin" hyperspectral imaging',
    '"foodborne" outbreak forecasting',
    '"mass spectrometry" food authentication',
    '"food safety" language models',
    '"food safety" "large language model"',
    '"food safety" "foundation model"',
    '"food safety" "generative AI"',
    '"food safety" "ChatGPT"',
    '"foodborne" "language model"',
    '"contaminants" "foundation model"',
    '"food safety" "vision language model"',
]
FOOD = [r'food\s*safe',r'foodborne',r'contaminat',r'mycotoxin',r'aflatoxin',r'ochratoxin',r'fusarium',r'pesticide',r'veterinary residue',r'salmonella',r'listeria',r'e\. coli',r'escherichia coli',r'pathogen',r'food fraud',r'food authentic',r'adulterat',r'shellfish toxin',r'heavy metal',r'cadmium',r'dioxin',r'microplastic',r'food spoilage',r'food inspection']
AI = [r'machine learning',r'deep learning',r'neural network',r'random forest',r'support vector',r'gradient boost',r'xgboost',r'artificial intelligence',r'computer vision',r'convolutional',r'transformer',r'large language model',r'foundation model',r'\bLLMs?\b',r'\bChatGPT\b',r'\bGPT[- ]?[345]\b',r'generative AI',r'vision.language model',r'chemometric',r'pattern recognition',r'partial least squares discriminant',r'bayesian network',r'predictive model',r'multivariate classification',r'YOLO\b',r'ResNet']

def http_json(url, *, payload=None, api_key=None, retries=3):
    headers={'User-Agent':'LivingAIFoodSafety/0.1 (noncommercial academic prototype)', 'Accept':'application/json'}
    if payload is not None:
        headers['Content-Type']='application/json'
    if api_key:
        headers['Authorization']='Bearer '+api_key
    body=json.dumps(payload).encode() if payload is not None else None
    for attempt in range(retries):
        try:
            with urlopen(Request(url, data=body, headers=headers), timeout=35) as r:
                return json.load(r)
        except HTTPError as exc:
            if exc.code in (429,500,502,503,504) and attempt+1<retries:
                time.sleep(2**attempt*2)
                continue
            detail=exc.read(1000).decode('utf-8','replace')
            raise RuntimeError(f'HTTP {exc.code}: {url.split("?")[0]}: {detail[:300]}') from exc
        except (URLError,TimeoutError) as exc:
            if attempt+1 < retries:
                time.sleep(2**attempt*2)
                continue
            raise RuntimeError(f'Network error: {exc}') from exc

def abstract_from_index(index):
    if not isinstance(index,dict): return ''
    terms=[]
    for word,positions in index.items():
        for pos in positions:
            if isinstance(pos,int) and pos >= 0 and pos < 50000: terms.append((pos,word))
    return ' '.join(w for _,w in sorted(terms))[:9000]

def normalize_doi(value):
    return re.sub(r'^https?://(dx\.)?doi\.org/', '', value or '',flags=re.I).strip().lower()

def pick(text, rules, fallback):
    for name,terms in rules:
        if any(re.search(t,text,re.I) for t in terms): return name
    return fallback

def heuristic_classify(title,abstract,publication_type):
    text=f'{title} {abstract}'.lower()
    food_hits=sum(bool(re.search(p,text,re.I)) for p in FOOD)
    ai_hits=sum(bool(re.search(p,text,re.I)) for p in AI)
    # A heuristic priority score, explicitly NOT a calibrated probability.
    score=round(min(0.97,0.12 + min(3,food_hits)*0.18 + min(3,ai_hits)*0.18),2)
    is_review=bool(re.search(r'\breview\b|\bperspective\b|systematic|bibliometric',title,re.I)) or publication_type=='review'
    domain=pick(text,[
      ('Microbiological hazards',[r'salmonella',r'listeria',r'e\. coli',r'pathogen',r'bacteria',r'microbiol']),
      ('Chemical hazards',[r'mycotoxin',r'aflatoxin',r'pesticide',r'heavy metal',r'cadmium',r'dioxin',r'microplastic',r'chemical contaminant']),
      ('Foodborne illness',[r'foodborne outbreak',r'foodborne disease',r'food poisoning']),
      ('Food fraud & authenticity',[r'food fraud',r'authentication',r'authenticity',r'adulterat']),
    ],'General food safety')
    app='Methods & perspectives' if is_review else pick(text,[
      ('Inspection & enforcement',[r'inspection',r'compliance',r'border control']),
      ('Risk forecasting',[r'forecast',r'predict.*risk',r'climate change',r'early warning',r'predict.*contaminat']),
      ('Laboratory testing',[r'detect',r'microscop',r'quantif',r'spectroscop',r'screening']),
      ('Risk factor analysis',[r'risk factor',r'source attribution',r'determinant']),
    ],'Early warning')
    dtype=pick(text,[
      ('Mass spectrometry',[r'mass spectrom',r'lc.?ms',r'gc.?ms']),
      ('Genomics & sequencing',[r'genom',r'sequence',r'metagenom']),
      ('Spectroscopy',[r'spectroscop',r'raman',r'near.infrared',r'ftir']),
      ('Imaging & microscopy',[r'hyperspectral imag',r'computer vision',r'microscop',r'imag']),
      ('Sensors & biosensors',[r'biosensor',r'electronic nose',r'sensor']),
      ('Monitoring & climate',[r'weather',r'climate',r'monitoring data']),
      ('Text & reports',[r'natural language',r'news',r'report']),
    ],'Literature & reviews' if is_review else 'Other')
    method='Review / synthesis' if is_review else pick(text,[
      ('LLMs / foundation models',FM_SIGNALS),
      ('Deep learning',[r'deep learning',r'convolutional',r'neural network',r'transformer',r'\bcnn\b',r'YOLO',r'ResNet']),
      ('Classical machine learning',[r'machine learning',r'random forest',r'support vector',r'chemometric',r'xgboost']),
    ],'Other / unspecified')
    relevance=food_hits>0 and ai_hits>0
    return {'relevant':relevance,'score':score,'domain':domain,'application':app,'data_type':dtype,
            'ai_method':method,'summary':'','reason':f'Keyword evidence: {food_hits} food-safety signals, {ai_hits} AI signals. Heuristic output requires validation.'}

def llm_classify(title,abstract,publication_type):
    key=os.getenv('OPENAI_API_KEY')
    if not key: return None
    model=os.getenv('OPENAI_MODEL','gpt-4.1-mini')
    prompt=(
       'Screen this TITLE/ABSTRACT for research about actual food safety hazards, contamination, food fraud or regulatory enforcement using AI/ML. '
       'Do NOT include generic agriculture, food quality, food security, or nutrition with no explicit food-safety connection. '
       'Return a JSON object ONLY with keys relevant (boolean), score (number 0-1, subjective not calibrated), domain, application, '
       'data_type, ai_method, summary (one neutral <=35-word sentence paraphrasing only title/abstract), reason (brief). '
       'Choose exactly one value per taxonomy. Classify LLMs/foundation models separately from general deep learning when central to the study; generic transformers alone are deep learning. Set no invented results, quantitative claims, authors, or methods. '
       'If unclear mark relevant=false or score<0.65.\n'
       f'Domains: {DOMAINS}\nApplications: {APPLICATIONS}\nData types: {DATATYPES}\nAI techniques: {AI_METHODS}\n'
       f'Type: {publication_type}\nTITLE: {title[:800]}\nABSTRACT: {abstract[:6500]}'
    )
    payload={'model':model,'temperature':0,'response_format':{'type':'json_object'},
        'messages':[{'role':'system','content':'You are a conservative, evidence-grounded scientific title/abstract screener. Output valid JSON only.'},
                    {'role':'user','content':prompt}]}
    result=http_json('https://api.openai.com/v1/chat/completions',payload=payload,api_key=key)
    data=json.loads(result['choices'][0]['message']['content'])
    for field,choices in [('domain',DOMAINS),('application',APPLICATIONS),('data_type',DATATYPES),('ai_method',AI_METHODS)]:
        if data.get(field) not in choices: raise ValueError(f'Unexpected LLM taxonomy value for {field}: {data.get(field)}')
    data['score']=max(0,min(1,float(data.get('score',0))))
    data['relevant']=data.get('relevant') is True
    data['summary']=str(data.get('summary') or '')[:360]
    data['reason']=str(data.get('reason') or '')[:400]
    return data

def normalize_work(w):
    doi=normalize_doi(w.get('doi'))
    if not doi: return None
    pub_date=w.get('publication_date') or ''
    if not re.match(r'^\d{4}-\d{2}-\d{2}$',pub_date): return None
    if pub_date>date.today().isoformat(): return None
    if (w.get('language') not in (None,'en')): return None
    if w.get('type') not in (None,'article','review'): return None
    title=(w.get('title') or w.get('display_name') or '').strip()
    if not title: return None
    journal=((w.get('primary_location') or {}).get('source') or {}).get('display_name') or 'Unknown source'
    authors=[(a.get('author') or {}).get('display_name') for a in w.get('authorships',[]) if (a.get('author') or {}).get('display_name')]
    return {'id':'doi:'+doi,'doi':doi,'title':title,'authors':authors[:20],
            'date':pub_date,'year':int(pub_date[:4]),'journal':journal,'url':'https://doi.org/'+doi,
            'abstract':abstract_from_index(w.get('abstract_inverted_index')),
            'publication_type':'Review' if w.get('type')=='review' else 'Research article',
            'source':'OpenAlex','first_seen':date.today().isoformat(),'openalex_id':w.get('id','')}

def fetch_works(days,per_query):
    key=os.getenv('OPENALEX_API_KEY','')
    since=(date.today()-timedelta(days=days)).isoformat()
    found={}
    for i,query in enumerate(SEARCHES,1):
        params={'search.title_and_abstract':query, 'filter':f'from_publication_date:{since},to_publication_date:{date.today().isoformat()}',
                'per_page':per_query,'page':1,'sort':'publication_date:desc',
                'select':'id,doi,title,publication_date,language,type,authorships,primary_location,abstract_inverted_index'}
        if key: params['api_key']=key
        url='https://api.openalex.org/works?'+urlencode(params)
        js=http_json(url)
        for work in js.get('results',[]):
            doc=normalize_work(work)
            if doc: found[doc['id']]=doc
        print(f'  [{i}/{len(SEARCHES)}] {query}: {len(js.get("results",[]))} records',file=sys.stderr)
        time.sleep(0.15)
    return list(found.values())

def make_digest(papers):
    active=[p for p in papers if p.get('screening',{}).get('status')!='excluded']
    last_month=(date.today()-timedelta(days=30)).isoformat()
    new=[p for p in active if p.get('first_seen','')>=last_month]
    by_domain=Counter(p.get('domain','Other') for p in new)
    highlights=sorted(new,key=lambda p:(p.get('date',''),p.get('title','')),reverse=True)[:5]
    return {'generated_on':date.today().isoformat(),'new_last_30_days':len(new),
            'domains':dict(by_domain),'recent_ids':[p['id'] for p in highlights],
            'caveat':'Counts reflect ingestion into this prototype, not all papers published in the period.'}

def write_json_and_js(name, data, variable):
    path=ROOT/'data'/name
    payload=json.dumps(data,indent=2,ensure_ascii=False)+'\n'
    path.write_text(payload,encoding='utf-8')
    (ROOT/'data'/name.replace('.json','.js')).write_text('window.'+variable+' = '+json.dumps(data,separators=(',',':'),ensure_ascii=False)+';\n',encoding='utf-8')

def main(argv=None):
    arg=argparse.ArgumentParser(description=__doc__)
    arg.add_argument('--days',type=int,default=60,help='Look-back window in publication days (default 60)')
    arg.add_argument('--per-query',type=int,default=40,help='First-page maximum per query (1-200)')
    arg.add_argument('--dry-run',action='store_true',help='Run without modifying data files')
    a=arg.parse_args(argv)
    if not 1<=a.per_query<=200 or a.days<1: arg.error('Invalid days or per-query')
    old=json.loads(DB.read_text(encoding='utf-8')) if DB.exists() else {'meta':{},'papers':[]}
    existing={p['id']:p for p in old['papers']}
    overrides_file=ROOT/'data'/'review_overrides.json'
    overrides=json.loads(overrides_file.read_text(encoding='utf-8')) if overrides_file.exists() else {}
    print('Retrieving recent publications…',file=sys.stderr)
    works=fetch_works(a.days,a.per_query)
    added=0; queued=[]; dropped=0
    for doc in works:
        if doc['id'] in existing: continue
        title,abstract=doc['title'],doc['abstract']
        heur=heuristic_classify(title,abstract,doc['publication_type'])
        if not heur['relevant']:
            dropped+=1
            continue
        method='heuristic'
        output=heur
        if os.getenv('OPENAI_API_KEY'):
            try:
                output=llm_classify(title,abstract,doc['publication_type'])
                method='llm'
            except Exception as exc:
                print(f'  LLM failed on {doc["doi"]}: {exc} — using heuristic',file=sys.stderr)
        if not output['relevant'] or output['score']<0.65:
            queued.append({'id':doc['id'],'title':title,'doi':doc['doi'],'score':output['score'],'reason':output['reason']})
            continue
        doc.update({k:output[k] for k in ('domain','application','data_type','ai_method')})
        doc['ai_family']=family_from_record(doc)
        doc['source_group']='automated_candidate'
        doc['summary']=output.get('summary') or ('Automated candidate identified from title and abstract. Open the source to assess the study.')
        doc['screening']={'status':'automated_candidate','confidence':output['score'],
                          'reason':output['reason'],'classification_method':method}
        existing[doc['id']]=doc
        added+=1
    for id_or_doi, override in overrides.items():
        key=(id_or_doi if id_or_doi in existing else id_or_doi if id_or_doi.startswith('doi:') else 'doi:'+normalize_doi(id_or_doi))
        if key not in existing: continue
        paper=existing[key]
        if override.get('status') in ('verified','excluded','needs_review'):
            paper.setdefault('screening',{})['status']=override['status']
        for field,valid in [('domain',DOMAINS),('application',APPLICATIONS),('data_type',DATATYPES),('ai_method',AI_METHODS)]:
            if override.get(field) in valid: paper[field]=override[field]
        if 'summary' in override and isinstance(override['summary'],str): paper['summary']=override['summary'][:500]
    for paper in existing.values():
        paper['ai_family']=family_from_record(paper)
    papers=sorted(existing.values(),key=lambda p:(p.get('date',''),p['id']),reverse=True)
    payload={'meta':{'mode':'automated_candidates','title':'Living AI for Food Safety','updated_at':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                     'note':'Automated candidate evidence map; not a validated systematic review. Publication-date search may miss delayed indexing.',
                     'original_review_doi':'10.1038/s41538-026-00925-1',
                     'source':'OpenAlex title/abstract search + optional LLM classification',
                     'retrieved':len(works),'new_candidates':added,'review_queue':len(queued),
                     'lookback_days':a.days,'query_count':len(SEARCHES),'llm_enabled':bool(os.getenv('OPENAI_API_KEY'))},
              'papers':papers}
    print(f'Retrieved={len(works)}, added={added}, queued={len(queued)}, basic-screen rejected={dropped}, total={len(papers)}',file=sys.stderr)
    if not a.dry_run:
        write_json_and_js('papers.json',payload,'LIVING_REVIEW_DATA')
        write_json_and_js('digest.json',make_digest(papers),'LIVING_REVIEW_DIGEST')
        (ROOT/'data'/'review_queue.json').write_text(json.dumps(queued,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 0

if __name__=='__main__': raise SystemExit(main())
