"""One-off, reproducible import of the five evidence tables in van Meer et al. (2026).

Input: a local copy of the original open-access PDF, not redistributed here.
Run: python agent/import_original_review.py /path/to/s41538-026-00925-1.pdf
Writes data/original_review_records.json (preserves reference numbers and table context).
Published Tables 1–5 contain 161 table rows; reference 128 occurs twice,
yielding 160 unique study references. A duplicate study is not a new paper.
No full-text or external DOI enrichment is implied by this conversion.
"""
import re, sys, json, unicodedata, urllib.parse
from pathlib import Path
from collections import Counter
import fitz

ROOT=Path(__file__).resolve().parents[1]
HEAD=re.compile(r'(?m)^([0-9]{1,3})\.\s*$')
PAPERLINE=re.compile(r'^([^0-9]+?)([0-9]{1,3})$')
CONTEXTS={'Laboratory testing':'Laboratory testing','Forecasting':'Risk forecasting','Risk factors':'Risk analysis','Border inspection':'Inspection & enforcement','Regulatory efficiency':'Regulatory efficiency'}
DOMAIN={1:'Microbiological hazards',2:'Chemical hazards',3:'Food fraud & authenticity',4:'Foodborne illness',5:'General food safety'}
TITLES={1:'Table 1 |',2:'Table 2 |',3:'Table 3 |',4:'Table 4 |',5:'Table 5 |'}


def clean(s):
    s=s.replace('ﬁ','fi').replace('ﬂ','fl').replace('\u00ad','').replace('\u200b','')
    s=re.sub(r'(?<=[a-zA-Z])-\n(?=[a-zA-Z])','',s)
    return ' '.join(s.split())


def refs_from_pdf(doc):
    corpus='\n'.join(doc[i].get_text() for i in range(9,15))
    marks=list(HEAD.finditer(corpus)); refs={}
    for i,m in enumerate(marks):
        number=int(m.group(1)); nxt=marks[i+1].start() if i+1<len(marks) else corpus.find('\nAcknowledgements',m.end())
        entry=clean(corpus[m.end():nxt])
        entry=entry.replace('doi. org','doi.org').replace('doi.org/10. ','doi.org/10.')
        if number==85:entry='Munck, N., Njage, P. M. K., Leekitcharoenphon, P., Litrup, E. & Hald, T. Application of whole-genome sequences and machine learning in source attribution of Salmonella typhimurium. Risk Anal. 40, 1693–1705 (2020).'
        entry=re.split(r'https://doi\.org/10\.1038/s41538-026-00925-1\s+Review',entry)[0].strip()
        refs[number]=entry
    assert len(refs)==189 and set(refs)==set(range(1,190)),f'Bad bibliography: {len(refs)}'
    return refs


def split_citation(entry):
    # Authors in this reference format end at et al. or after the last initial.
    if 'Mateo,E.M.,Tarazona,A.,Aznar,R.&Mateo,F.Exploring' in entry:
        entry=entry.replace('Mateo,F.Exploring','Mateo,F. Exploring')
    if 'Geng,Z.etal.Earlywarning' in entry:
        entry=entry.replace('Geng,Z.etal.Earlywarning','Geng, Z. et al. Early warning')
    m=re.search(r'(?:\bet al\.\s*|\betal\.\s*)',entry)
    if m:
        authors=entry[:m.end()-1].strip(); following=entry[m.end():]
    else:
        m=re.search(r'\.\s+(?=[A-ZÀ-Þ](?:[a-zÀ-ÿ][\wÀ-ÿ-]*|[A-Z][a-zA-Z]+|\s+[a-z]{2,}))',entry)
        if not m:
            print('WARN author split',entry[:100]); return {'authors_text':'','title':entry,'journal':'','year':int(re.findall(r'(?:19|20)\d{2}',entry)[-1]) if re.findall(r'(?:19|20)\d{2}',entry) else 0,'doi':'','citation_text':entry}
        authors=entry[:m.start()+1].strip();following=entry[m.end():]
    # The article title is the first completed sentence. Bibliographic series,
    # journal, volume and pagination follow. Titles with internal abbreviations
    # such as E. coli or spp. are treated separately.
    m=re.search(r'\.\s+(?=(?:in |J\.|Food\b|Front\b|Sci\b|Nature\b|Commun\b|Anal\b|Biosens\b|Sensors\b|Meat\b|Appl\b|Chem\b|Trends\b|IEEE\b|Int\b|PLoS\b|Comput\b|N\.|LWT\b|Talanta\b|Postharvest\b|Sustainab\b|Lecture\b|Current\b|Curr\b|Molecules\b|Risk\b|Poul\b|Spectrochim\b|Eur\b|New\b|ACS\b|Microb\b|Metabolites\b|Foodborne\b|Proc\b|Environ\b|Eng\b|Heliyon\b|Foods\b|Water\b|Toxins\b|Nutrients\b|Agric\b|Aquac\b|Ecol\b|Journal\b|Artif\b|Atmos\b|Syst\b|IEEE\b|Sensors\b|Phys\b|Remote\b|J\.|Med\b|Plant\b|Acta\b|Bio\b|Chemical\b|Trans\b|RSC\b|PeerJ\b|Electronics\b|Big\b|Conference\b|Ciencia\b|Ciência\b|202[0-9]\b))',following)
    if m:
        title=following[:m.start()+1].strip(); venue=following[m.end():].strip()
    else:
        # Fall back to the first sentence terminator which is not an abbreviation.
        m=re.search(r'\.\s+(?=[A-ZÀ-Þ][a-zÀ-ÿ])',following)
        if m:
            title=following[:m.start()+1].strip();venue=following[m.end():].strip()
        else:
            title=following;venue=''
    yr=re.findall(r'(?:\(|,\s*)(19\d\d|20\d\d)\)',entry)
    year=int(yr[-1]) if yr else 0
    doi_match=re.search(r'(?:https?://)?doi\.org/(10\.[0-9]{4,9}/[^\s(]+)',entry,re.I)
    doi=doi_match.group(1).rstrip('.,;') if doi_match else ''
    # Normalize line-wrapped DOI punctuation: "10.1109/... 9729384" may
    # need later manual resolving; never pretend a guessed DOI was verified.
    if doi and (' ' in doi or not re.match(r'^10\.\d{4,9}/[^\s]{5,}',doi) or doi.endswith('.') or doi=='10.1117/12' or doi=='10.1109/icspis54653.2021'):doi=''
    if venue:
        venue=re.sub(r'\s*https?://doi\.org/.*','',venue)
        venue=re.sub(r'\s*\(\d{4}\).*','',venue)
    return {'authors_text':authors,'title':title.rstrip('.'),'journal':venue.strip(' .'), 'year':year,'doi':doi,'citation_text':entry}


def read_rows(pdf):
    rows=[]; tablepages={1:4,2:6,3:7,4:7,5:8}
    for t,pid in tablepages.items():
        raw=pdf[pid].get_text().replace('ﬁ','fi').replace('ﬂ','fl').splitlines()
        start=next(i for i,s in enumerate(raw) if s.startswith(TITLES[t]))
        if t==3:
            stop=next(i for i,s in enumerate(raw) if s.startswith(TITLES[4]))
        else:
            stop=next((i for i in range(start+1,len(raw)) if raw[i].startswith('ANN artificial') or raw[i].startswith('BERT bidirectional') or raw[i].startswith('https://doi.org/10.1038/s41538')),len(raw))
        cur_context=''; current=None
        for line in raw[start:stop]:
            line=line.strip()
            if line in CONTEXTS: cur_context=CONTEXTS[line];continue
            if line in ('Implementation context','Paper','Data collection method','AI technique','AI Technique','Target organism','Target chemical','') or line.startswith('Table '):continue
            match=PAPERLINE.match(line)
            if match and int(match.group(2))>=12 and ('et al.' in line or ' and ' in line or re.fullmatch(r'[A-Za-z]+\d+',line)):
                if current:rows.append(current)
                current={'table':t,'reference_number':int(match.group(2)),'paper_label':match.group(1).strip(),'application':cur_context,'cells':[]}
            elif current:
                current['cells'].append(line)
        if current:rows.append(current)
    return rows


def ai_group(method):
    tokens=method.upper()
    if re.search(r'CNN|DNN|RNN|LSTM|BERT|GAN|GNN|AUTOENCODER|RESNET|ALEXNET|DCNN|TRANSFORMER',tokens):
        return 'Deep learning'
    if 'NOT AVAILABLE' in tokens:return 'Not specified'
    return 'Classical machine learning'


def datatype_group(method):
    m=method.lower()
    if any(k in m for k in ['spectroscop','infrared','raman','ftir','hyperspectral','vis/nir','optical','nir','scatter']): return 'Spectroscopy & imaging'
    if any(k in m for k in ['mass spect','metabolom','chromatog','lc-ms','icp-ms','gc-fid']):return 'Analytical chemistry / MS'
    if any(k in m for k in ['genomic','sequenc','dna','snp','pcr','bacterial','colony','chromogenic','microbio']):return 'Microbiology & genomics'
    if any(k in m for k in ['image','microscop','video']):return 'Imaging & microscopy'
    if any(k in m for k in ['text','news','social media','recall']):return 'Text & reports'
    if any(k in m for k in ['sensor','e-nose','e-tongue','biolumin','electrochem','elisa']):return 'Sensors & biosensors'
    return 'Mixed / other data'


def split_methods(cells, domain):
    # The PDF's table cells are plain text lines. Split technique (rightmost
    # column) from source and optional hazard (left columns).
    raw=[clean(s) for s in cells if s]
    if not raw:return '', '', '', ''
    # AI method is last one or two lines of acronyms; legitimate long method
    # identifiers ("log-linear maximum entropy") are also treated as method.
    def methodish(s):
        key=('SVM','RF','CNN','DNN','DT','KNN','ANN','BN','ELM','GAN','LDA','LSTM','BERT','GNN','ResNet','Autoencoder','Active learning','GA','NLP','log-linear','XGBOOST','Not available','Neural','Computer vision','BP-NN','DCNN')
        return s.startswith(key) or re.match(r'^[A-Z][A-Z\d\- ]{2,}$',s) is not None
    idx=len(raw)-1
    # last cell is generally AI method; join continuation if adjacent techniques
    while idx>0 and methodish(raw[idx-1]) and len(raw)-idx<2: idx-=1
    meth=' '.join(raw[idx:]); middle=raw[:idx]
    if domain in [1,2]:
        known=('Optical','Hyperspectral','Microscop','Genomics','Colony','Mass Spectrometry','Image','Spectroscop','Chromogenic','E-nose','Metabolom','Combined','Several','Video','Electrochemical','Biolumin','Near-field','Inductively','PCR','ELISA','Molecular','CAMP','E-tongue','pH sensor','Not available')
        boundary=next((i for i,x in enumerate(middle) if x.startswith(known)),1 if len(middle)>1 else len(middle))
        target=' '.join(middle[:boundary]);collection=' '.join(middle[boundary:])
    else:
        target='';collection=' '.join(middle)
    return target,collection,meth,' | '.join(raw)


def load(pdf_file):
    doc=fitz.open(pdf_file);refs=refs_from_pdf(doc);rows=read_rows(doc)
    groups=Counter(r['table'] for r in rows)
    assert groups=={1:56,2:40,3:27,4:9,5:29},f'Unexpected table lengths: {groups}'
    byref={}
    for r in rows:
        n=r['reference_number']; pub=split_citation(refs[n]); target,collection,tech,raw=split_methods(r['cells'],r['table'])
        if n in byref:
            byref[n]['additional_contexts'].append({'application':r['application'],'original_technique':tech,'table':r['table']})
            continue
        link='https://doi.org/'+pub['doi'] if pub['doi'] else 'https://scholar.google.com/scholar?q='+urllib.parse.quote(pub['title'])
        override_journal={15:'Sensors 22, 9979',26:'Foods 12, 2118',76:'IEEE conference proceedings',114:'Food Control 103, 111–118',143:'E3S Web Conf. 430, 1074',152:'Spectrochim. Acta Part B Spectrosc. 205, 106693',154:'IFAC-PapersOnLine 52, 397–402',157:'TELKOMNIKA 14, 778',160:'JAMIA Open 2, 330–338',164:'AI Mag. 38, 37–48',74:'Water Res. 242, 120258',163:'Proc. AAAI Conf. Hum. Comput. Crowdsourc 1, 138–146',135:'Commun. Comput. Inform. Sci. 122–130',167:'Lecture Notes Networks Syst. 381–391'}
        if n in override_journal:pub['journal']=override_journal[n]
        override_titles={26:'E. L. V. 2 model for predicting food safety risks at Taiwan border using the voting-based ensemble method',74:'AI-enabled biosensing for rapid pathogen detection: From liquid food to agricultural water',163:'nEmesis: Which restaurants should you avoid today?',76:'Classification and identification of food-borne pathogens by Raman spectra based on XGBoost and PCA',135:'Data driven methods for finding pattern anomalies in food safety',15:'Machine learning-assisted synchronous fluorescence sensing approach for rapid and simultaneous quantification of thiabendazole and fuberidazole in red wine',114:'Quantitative TLC-SERS detection of histamine in seafood with support vector machine analysis',143:'IoT-powered intelligent framework for detecting food adulteration: a smart approach',152:'Analytical approaches for food authentication using LIBS fingerprinting',167:'Chicken quality evaluation using deep learning'}
        if n in override_titles:pub['title']=override_titles[n]
        p={'id':'review-ref-'+str(n),'doi':pub['doi'],'title':pub['title'], 'authors':[pub['authors_text']],
           'date':str(pub['year'])+'-01-01' if pub['year'] else '', 'date_precision':'year','year':pub['year'],'journal':pub['journal'],'url':link,
           'summary':f'{r["application"]}. Data: {collection or "not reported"}. Technique(s): {tech or "not reported"}.'+ (f' Target: {target}.' if target else ''),
           'domain':DOMAIN[r['table']],'application':r['application'],'data_type':datatype_group(collection),'ai_method':ai_group(tech),
           'publication_type':'Research article', 'screening':{'status':'curated_metadata','confidence':None,'reason':'Listed in the included-study table of van Meer et al. (2026); transcribed from the published paper, not independently re-screened.'},
           'source':'van Meer et al. (2026) · Table '+str(r['table']), 'source_group':'original_review', 'first_seen':'2026-10-15',
           'original_reference_number':n,'citation_text':pub['citation_text'],'target':target,'data_collection_method':collection,
           'original_ai_techniques':tech,'additional_contexts':[], 'extraction_note':'Bibliographic record extracted from published reference list; details should be confirmed against publisher before reuse.'}
        byref[n]=p
    assert len(rows)==161 and len(byref)==160,(len(rows),len(byref))
    out={'metadata':{'source_doi':'10.1038/s41538-026-00925-1','table_rows':len(rows),'distinct_referenced_papers':len(byref),'duplicate_reference':128,'version':'2026-10-15'}, 'papers':sorted(byref.values(),key=lambda x:x['original_reference_number'])}
    (ROOT/'data/original_review_records.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Wrote',len(byref),'unique papers from',len(rows),'table rows; table counts',groups)
    return out

if __name__=='__main__':
    if len(sys.argv)!=2:sys.exit('Usage: python agent/import_original_review.py ORIGINAL_REVIEW.pdf')
    load(Path(sys.argv[1]))
