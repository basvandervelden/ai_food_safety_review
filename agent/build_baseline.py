"""Combine every unique reference from the published five tables with six
subsequent research articles from the earlier illustrative starter list.

Source-of-truth preserved in data/original_review_records.json.
This is an editorial 166-record evidence map, NOT 166 studies included in 2026
systematic review (that review states 161 table rows / 160 distinct citations).
"""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
orig=json.loads((DATA/'original_review_records.json').read_text(encoding='utf-8'))['papers']
seed=json.loads((DATA/'starter_22_archive.json').read_text(encoding='utf-8'))['papers']
recent=[p for p in seed if p.get('year',0)>=2025 and p.get('publication_type')=='Research article']
recent=sorted(recent,key=lambda p:(p['date'],p['title']),reverse=True)[:6]
assert len(orig)==160 and len(recent)==6
ids={p['id'] for p in orig}
for p in recent:
    assert p['id'] not in ids
    p['source_group']='post_review_sample'
    p['screening']={'status':'curated_metadata','confidence':None,'reason':'Selected as a newer example from the previously curated DOI-linked reading list; not part of the original review.'}
    p['source']='Post-review curated extension (2025–2026)'
    p['collection_note']='Additional post-review research article, not part of van Meer et al. 2026 systematic review.'
allpapers=sorted(orig+recent,key=lambda p:(p['date'],p['title']),reverse=True)
payload={'meta':{'mode':'review_baseline','title':'Living AI for Food Safety','updated_at':'2026-10-15',
                 'note':'166 distinct records: 160 unique papers in 161 included-study table rows of van Meer et al. (2026), plus 6 separately labelled post-review studies. Not an update to the original systematic review.',
                 'original_review_doi':'10.1038/s41538-026-00925-1',
                 'original_review_table_rows':161,'original_review_unique_studies':160,
                 'post_review_papers':6,'source':'Published van Meer et al. Tables 1–5 and six curated DOI-linked post-review studies'},
         'papers':allpapers}
assert len(allpapers)==166
(DATA/'papers.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
js='window.LIVING_REVIEW_DATA = '+json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+';\n'
(DATA/'papers.js').write_text(js,encoding='utf-8')
print('Rebuilt',len(allpapers),'distinct records: 160 original and 6 additional')
