"""SVG charts reflecting published Figure 2 taxonomy, generated from indexed records.
No hardcoded publication counts: runs on every literature refresh.
"""
from collections import Counter
from html import escape
from math import sin, cos, pi
from update import AI_FAMILIES, family_from_record

DOMAINS=['Microbiological hazards','Chemical hazards','Food fraud & authenticity','Foodborne illness','General food safety']
DCOLORS=['#d676a3','#f2ae5f','#b99cd4','#9299aa','#8dbba9']
ACOLORS=['#d77aa8','#f0ae64','#8aa9dc','#b8aebe']
SHORT={'Microbiological hazards':'Microbial','Chemical hazards':'Chemical','Food fraud & authenticity':'Food fraud',
       'Foodborne illness':'Outbreaks','General food safety':'Other hazards','Laboratory testing':'Lab testing',
       'Risk forecasting':'Forecasting','Risk factor analysis':'Risk factors','Inspection & enforcement':'Inspection',
       'Methods & perspectives':'Methods','Early warning':'Early warning'}

def esc(x):
    return escape(str(x or ''),quote=True)

def pos(a,r):
    theta=(a-90)*pi/180
    return 288+r*cos(theta),282+r*sin(theta)

def arc(a,b,inside,outside):
    if b-a < .05: return ''
    b=min(b,a+359.99)
    x1,y1=pos(a,outside);x2,y2=pos(b,outside)
    x3,y3=pos(b,inside);x4,y4=pos(a,inside)
    large=int(b-a>180)
    return f'M {x1:.2f} {y1:.2f} A {outside} {outside} 0 {large} 1 {x2:.2f} {y2:.2f} L {x3:.2f} {y3:.2f} A {inside} {inside} 0 {large} 0 {x4:.2f} {y4:.2f} Z'

def sunburst(rows,family='Deep learning (DL)'):
    rows=[p for p in rows if p.get('screening',{}).get('status')!='excluded']
    total=len(rows) or 1
    selected=sum(family_from_record(p)==family for p in rows)
    svg=['<svg viewBox="0 0 576 565" role="img" aria-label="Research domains, contexts and share of selected AI family">']
    legends=[]
    cursor=0
    for domain,color in zip(DOMAINS,DCOLORS):
        papers=[p for p in rows if p.get('domain')==domain]
        if not papers:continue
        a,b=cursor,cursor+len(papers)/total*360
        cursor=b
        matched=sum(family_from_record(p)==family for p in papers)
        ratio=matched/len(papers)
        svg.append(f'<path class="viz-piece" fill="{color}" data-viz-domain="{esc(domain)}" d="{arc(a+.6,b-.6,134,195)}"><title>{esc(domain)}: {len(papers)} papers; {matched} {esc(family)} ({ratio:.0%})</title></path>')
        svg.append(f'<path fill="#e8e5ef" d="{arc(a+.6,b-.6,109,128)}"></path>')
        if matched:
            svg.append(f'<path class="viz-piece" fill="{color}" data-viz-domain="{esc(domain)}" d="{arc(a+.6,max(a+.65,a+(b-a)*ratio-.6),109,128)}"><title>{matched}/{len(papers)} {esc(family)}</title></path>')
        if b-a>20:
            x,y=pos((a+b)/2,166)
            svg.append(f'<text class="viz-domain-text" x="{x:.1f}" y="{y:.1f}" text-anchor="middle">{esc(SHORT.get(domain,domain))}</text>')
        counts=Counter(p.get('application') or 'Unclassified' for p in papers)
        theta=a
        for j,(app,n) in enumerate(counts.most_common()):
            start,end=theta,theta+(b-a)*n/len(papers)
            theta=end
            opacity=[.62,.39,.82,.5,.29][j%5]
            svg.append(f'<path class="viz-piece" fill="{color}" fill-opacity="{opacity}" data-viz-domain="{esc(domain)}" data-viz-app="{esc(app)}" d="{arc(start+.45,end-.45,201,249)}"><title>{esc(domain)} / {esc(app)}: {n} papers</title></path>')
            if end-start>17:
                x,y=pos((start+end)/2,226)
                svg.append(f'<text class="viz-context-text" text-anchor="middle" x="{x:.1f}" y="{y:.1f}">{esc(SHORT.get(app,app))}</text>')
        legends.append(f'<span class="viz-legend-item"><i style="background:{color}"></i><span>{esc(domain)}</span><b>{len(papers)}</b></span>')
    family_label={'Machine learning (ML)':'Machine learning','Deep learning (DL)':'Deep learning','LLMs / foundation models':'LLMs / FMs'}.get(family,'Other / mixed')
    percentage=round(100*selected/len(rows)) if rows else 0
    svg.append(f'<circle cx="288" cy="282" r="103" fill="var(--card)" stroke="var(--line-soft)"/><text class="viz-center-small" x="288" y="248" text-anchor="middle">SELECTED METHOD</text><text class="viz-center-name" x="288" y="281" text-anchor="middle">{esc(family_label)}</text><text class="viz-center-ratio" x="288" y="317" text-anchor="middle">{percentage}%</text><text class="viz-center-small" x="288" y="338" text-anchor="middle">{selected} of {len(rows)} papers</text></svg>')
    return ''.join(svg),''.join(legends)

def stacked(rows):
    rows=[p for p in rows if p.get('screening',{}).get('status')!='excluded']
    years=sorted({p.get('year') for p in rows if isinstance(p.get('year'),int) and 2010 <= p['year'] <2100})
    if not years: return '<p>No publication years available.</p>'
    values={y:Counter(family_from_record(p) for p in rows if p.get('year')==y) for y in years}
    ymax=max(5,10*((max(sum(values[y].values()) for y in years)+9)//10))
    W,H,L,R,T,B=830,340,58,20,23,54
    gh,gw=H-T-B,W-L-R
    step=gw/len(years);bw=min(step*.66,42)
    svg=[f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Yearly publications stacked by AI method">']
    for i in range(6):
        tick=round(ymax*i/5);y=T+gh-gh*tick/ymax
        dash="3 5" if i else "0"
        svg.append(f'<line x1="{L}" x2="{W-R}" y1="{y}" y2="{y}" stroke="var(--line)" stroke-dasharray="{dash}"/><text x="{L-12}" y="{y+4}" text-anchor="end" class="viz-axis-text">{tick}</text>')
    for i,year in enumerate(years):
        x=L+i*step+(step-bw)/2;bottom=T+gh
        for fam,color in zip(AI_FAMILIES,ACOLORS):
            n=values[year][fam]
            if not n:continue
            height=n/ymax*gh;bottom-=height
            svg.append(f'<rect x="{x:.1f}" y="{bottom:.1f}" width="{bw:.1f}" height="{height:.1f}" class="viz-piece" fill="{color}" data-viz-year="{year}" data-viz-family="{esc(fam)}"><title>{year}: {n} {esc(fam)} papers</title></rect>')
        svg.append(f'<text class="viz-axis-text" x="{x+bw/2:.1f}" y="{H-33}" text-anchor="middle">{year}</text>')
    svg.append(f'<text class="viz-axis-title" x="{W/2}" y="{H-6}" text-anchor="middle">Year</text><text class="viz-axis-title" x="15" y="{H/2}" text-anchor="middle" transform="rotate(-90 15 {H/2})">Number of papers</text></svg>')
    return ''.join(svg)

def stacked_legend():
    return ''.join(f'<span class="viz-legend-item"><i style="background:{color}"></i>{esc(fam)}</span>' for fam,color in zip(AI_FAMILIES,ACOLORS))
