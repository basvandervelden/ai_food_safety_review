"""Render an always-visible, script-independent literature snapshot.

The browser JS enhances the static snapshot with filters, curation, and charts.
Use after each data refresh so that HTML previews and no-JavaScript browsers
show real publication records immediately.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path
import csv
import io
import json
import re
from update import AI_FAMILIES, family_from_record
from visualizations import sunburst, stacked, stacked_legend

ROOT = Path(__file__).resolve().parents[1]
IDX = ROOT / 'index.html'
DATA = ROOT / 'data' / 'papers.json'
CSV = ROOT / 'data' / 'papers.csv'
DEMO = ROOT.parent / 'Living_AI_Food_Safety_demo.html'


def e(value):
    return escape(str(value or ''), quote=True)


def label_date(iso, precision=None):
    if precision=='year': return str(iso or '')[:4]
    try:
        return datetime.strptime(iso[:10], '%Y-%m-%d').strftime('%b %Y')
    except (ValueError, TypeError):
        return str(iso or 'Date unknown')


def domain_style(domain):
    return {'Chemical hazards':'chem', 'Microbiological hazards':'micro',
            'Food fraud & authenticity':'fraud', 'Foodborne illness':'illness'}.get(domain,'')


def card(p):
    authors=[a for a in p.get('authors',[]) if a]
    byline=(', '.join(authors[:3]) + (' et al.' if len(authors)>3 else '')) if authors else (p.get('journal') or 'Author details via DOI')
    tags=f'<span class="tag">{e(family_from_record(p))}</span>'+''.join(f'<span class="tag">{e(p.get(field) or label)}</span>' for field,label in [
        ('application','Unclassified'),('data_type','Unclassified')])
    url=p.get('url') or f"https://doi.org/{p.get('doi','')}"
    linklabel='Open DOI ↗' if p.get('doi') else 'Find article ↗'
    return f'''<article class="paper-card">
      <div class="paper-meta"><span class="domain-badge {e(domain_style(p.get('domain')))}">{e(p.get('domain') or 'Unclassified')}</span><span>{e(label_date(p.get('date'),p.get('date_precision')))}</span><span>·</span><span>{e(p.get('journal') or 'Unknown source')}</span></div>
      <a class="paper-title" href="{e(url)}" target="_blank" rel="noopener noreferrer">{e(p.get('title'))}</a>
      <p class="paper-byline">{e(byline)} · {e(p.get('publication_type') or 'Publication')}</p>
      <p class="paper-summary">{e(p.get('summary') or 'Publication metadata. Open the DOI for the original study.')}</p>
      <div class="paper-bottom"><div class="tag-group">{tags}</div><a class="paper-read" href="{e(url)}" target="_blank" rel="noopener noreferrer">{e(linklabel)}</a></div>
    </article>'''


def horizontal_bars(counts, order=None):
    items=[(name,counts.get(name,0)) for name in order] if order else sorted(counts.items(),key=lambda it:-it[1])
    peak=max(counts.values(),default=1)
    return '\n'.join(f'''<div class="bar-item"><div class="bar-label"><span>{e(label)}</span><span>{num} {'paper' if num==1 else 'papers'}</span></div><div class="track"><div class="fill" style="width:{max(3, num / peak * 100):.2f}%"></div></div></div>''' for label,num in items)


def year_chart(papers):
    counts=Counter(p.get('year') for p in papers if isinstance(p.get('year'),int))
    years=sorted(counts)
    maximum=max(counts.values(),default=1)
    width,height,top,base=500,176,17,147
    step=width/max(len(years),4)
    barwidth=min(48,step*.53)
    pieces=[f'<svg class="chart-svg" viewBox="0 0 540 {height}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Publication counts by year">']
    for tick in range(4):
        n=-(-maximum*tick//3)
        y=base-(n/maximum)*(base-top)
        pieces.append(f'<line x1="37" x2="527" y1="{y}" y2="{y}" stroke="var(--line)" stroke-width="1" stroke-dasharray="3 5"/><text x="27" y="{y+3}" text-anchor="end">{n}</text>')
    for i,yr in enumerate(years):
        n=counts[yr]
        x=42+step*i+step/2
        y=base-(n/maximum)*(base-top)
        color='#8063ac' if i==len(years)-1 else '#c8b4e2'
        pieces.append(f'<rect x="{x-barwidth/2}" y="{y}" width="{barwidth}" height="{base-y}" rx="5" fill="{color}"><title>{yr}: {n} indexed publications</title></rect><text x="{x}" y="168" text-anchor="middle">{yr}</text><text x="{x}" y="{max(10,y-6)}" text-anchor="middle">{n}</text>')
    return ''.join(pieces)+'</svg>'


def replace_marker(doc, key, content):
    pattern = rf'(<!-- SSR:{re.escape(key)}:start -->).*?(<!-- SSR:{re.escape(key)}:end -->)'
    doc,n=re.subn(pattern, lambda m:m.group(1)+'\n'+content+'\n'+m.group(2),doc,flags=re.S)
    if n!=1:
        raise RuntimeError(f'Cannot update static region {key}: found {n}')
    return doc


def replace_text(doc, ident, content):
    pat=rf'(<(?:strong|span|p) id="{re.escape(ident)}"[^>]*>).*?(</(?:strong|span|p)>)'
    doc,n=re.subn(pat,lambda m:m.group(1)+content+m.group(2),doc,count=1,flags=re.S)
    if n!=1:
        raise RuntimeError(f'Missing static label {ident}')
    return doc


def create_csv(papers):
    columns=['date','title','authors','journal','doi','domain','application','data_type','ai_method','ai_family','publication_type','summary','url','source','source_group','original_reference_number','target','data_collection_method','original_ai_techniques','citation_text','additional_contexts']
    with CSV.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.writer(f)
        writer.writerow(columns)
        for p in papers:
            writer.writerow(['; '.join(p.get(c,[]) or []) if isinstance(p.get(c),list) and all(isinstance(x,str) for x in (p.get(c,[]) or [])) else json.dumps(p.get(c,[]),ensure_ascii=False) if isinstance(p.get(c),list) else family_from_record(p) if c=='ai_family' else p.get(c,'') for c in columns])


def render():
    data=json.loads(DATA.read_text(encoding='utf-8'))
    papers=sorted((p for p in data['papers'] if p.get('screening',{}).get('status')!='excluded'),key=lambda p:p.get('date',''),reverse=True)
    create_csv(papers)
    doc=IDX.read_text(encoding='utf-8')
    doc=replace_marker(doc,'paper-list','\n'.join(card(p) for p in papers))
    doc=replace_marker(doc,'trend-chart',year_chart(papers))
    doc=replace_marker(doc,'domain-bars',horizontal_bars(Counter(p.get('domain') or 'Other' for p in papers)))
    doc=replace_marker(doc,'method-bars',horizontal_bars(Counter(family_from_record(p) for p in papers), AI_FAMILIES))
    review=[p for p in papers if p.get('source_group')=='original_review']
    image,legend=sunburst(review,'Deep learning (DL)')
    doc=replace_marker(doc,'sunburst',image)
    doc=replace_marker(doc,'sun-legend',legend)
    doc=replace_marker(doc,'stacked',stacked(review))
    doc=replace_marker(doc,'stacked-legend',stacked_legend())
    digest=''.join(f'<div class="digest-entry"><span class="bullet"></span><a href="{e(p.get("url") or "https://doi.org/"+p.get("doi",""))}" target="_blank" rel="noopener noreferrer">{e(p.get("title"))}</a></div>' for p in papers[:3])
    doc=replace_marker(doc,'digest-list',digest)
    counts={'stat-papers':str(len(papers)),'stat-domains':str(len(set(p.get('domain') for p in papers if p.get('domain')))),
            'stat-methods':'3',
            'stat-latest':str(max((p.get('year',0) for p in papers),default=0)),'results-count':f'{len(papers)} results',
            'tab-total':str(len(papers))}
    for key,val in counts.items():
        doc=replace_text(doc,key,val)
    # The HTML itself is always a complete reading list. JavaScript initializes
    # the enhanced view to six records and exposes the remaining entries on click.
    IDX.write_text(doc,encoding='utf-8')

    styles=(ROOT/'assets/styles.css').read_text(encoding='utf-8')
    app=(ROOT/'assets/app.js').read_text(encoding='utf-8')
    landscape=(ROOT/'assets/landscape.js').read_text(encoding='utf-8')
    digest_json=(ROOT/'data/digest.js').read_text(encoding='utf-8')
    safe_data=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    standalone=doc.replace('<link rel="stylesheet" href="assets/styles.css" />','<style>\n'+styles+'\n</style>')
    standalone=standalone.replace('<script src="data/papers.js"></script><script src="data/digest.js"></script><script src="assets/landscape.js"></script><script src="assets/app.js"></script>',
        '<script>window.LIVING_REVIEW_DATA = '+safe_data+';</script>\n<script>'+digest_json+'</script>\n<script>'+landscape+'</script>\n<script>'+app+'</script>')
    if '<script src="assets/app.js">' in standalone:raise RuntimeError('Standalone packaging failed')
    # The standalone file does not rely on an adjacent data file, even for the CSV link.
    csv_bytes=CSV.read_bytes()
    import base64
    csv_uri='data:text/csv;base64,'+base64.b64encode(csv_bytes).decode('ascii')
    standalone=standalone.replace('href="data/papers.csv"',f'href="{csv_uri}"')
    DEMO.write_text(standalone,encoding='utf-8')
    print(f'Built static fallback with {len(papers)} studies: {IDX}, {DEMO}, {CSV}')

if __name__=='__main__':render()
