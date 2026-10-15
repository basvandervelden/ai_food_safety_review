import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'agent'))
import update
class PipelineTests(unittest.TestCase):
    def test_reconstruct_abstract(self):
        self.assertEqual(update.abstract_from_index({'food':[0],'safety':[1,4],'with':[2],'AI':[3]}),'food safety with AI safety')
    def test_doi_normalization(self):
        self.assertEqual(update.normalize_doi('https://doi.org/10.1038/ABC'),'10.1038/abc')
    def test_screen_without_ai(self):
        self.assertFalse(update.heuristic_classify('Salmonella detection in food','Using a conventional plate culture method.','article')['relevant'])
    def test_screen_with_ai(self):
        x=update.heuristic_classify('Deep learning detection of Salmonella in food','Raman spectroscopy with neural networks','article')
        self.assertTrue(x['relevant'])
        self.assertEqual(x['domain'],'Microbiological hazards')
    def test_ai_families(self):
        self.assertEqual(update.family_from_record({'title':'Large language models for food safety', 'ai_method':'Deep learning'}),'LLMs / foundation models')
        self.assertEqual(update.family_from_record({'title':'Random forest for aflatoxin', 'ai_method':'Classical machine learning'}),'Machine learning (ML)')
        self.assertEqual(update.family_from_record({'title':'CNN for pathogen detection', 'ai_method':'Deep learning'}),'Deep learning (DL)')
        self.assertEqual(update.family_from_record({'title':'Food safety policy review','ai_method':'Review / synthesis'}),'Other / mixed')
        self.assertEqual(update.heuristic_classify('Food safety with foundation models','We test a pretrained foundation model.','article')['ai_method'],'LLMs / foundation models')
    def test_full_dataset_charts(self):
        import json
        from visualizations import render_charts
        rows=json.loads((Path(__file__).resolve().parents[1]/'data'/'papers.json').read_text(encoding='utf-8'))['papers']
        figures=render_charts(rows,collection='all',family='Deep learning (DL)')
        eligible=[p for p in rows if p.get('screening',{}).get('status')!='excluded']
        self.assertIn(f'of {len(eligible)} papers',figures['sun'])
        self.assertIn('class="science-sunburst"',figures['sun'])
        self.assertIn('class="science-stacked"',figures['bars'])
        self.assertIn('LLMs / foundation models',figures['key'])
        self.assertGreater(figures['sun'].count('class="science-segment"'),10)
        self.assertGreater(figures['bars'].count('class="science-bar-segment"'),10)
    def test_search_year_partitions(self):
        self.assertEqual(list(update.year_windows('2024-01-01','2026-03-03')),
                         [('2024-01-01','2024-12-31'),
                          ('2025-01-01','2025-12-31'),
                          ('2026-01-01','2026-03-03')])
    def test_daily_budget_pause_and_resume(self):
        from unittest.mock import patch
        from tempfile import TemporaryDirectory
        import json
        with TemporaryDirectory() as tmp:
            progress_file=Path(tmp)/'search_progress.json'
            fetch=lambda url: {'results':[{'doi':'https://doi.org/10.5555/'+('first' if 'search.title_and_abstract=a' in url else 'second')}], 'meta':{'count':1}}
            normalize=lambda obj: {'id':'doi:'+obj['doi'].split('/')[-1], 'doi':obj['doi']}
            with patch.object(update,'PROGRESS',progress_file),patch.object(update,'SEARCHES',['a','b']), \
                 patch.object(update,'http_json',side_effect=fetch),patch.object(update,'normalize_work',side_effect=normalize), \
                 patch.object(update,'OPENALEX_REMAINING_CREDITS',None):
                first,status=update.fetch_works(90,100,start_date='2024-01-01',end_date='2024-12-31',max_requests=1)
                self.assertEqual(status['status'],'paused')
                self.assertEqual((status['year'],status['query_index'],status['page']),(2024,1,1))
                self.assertEqual(len(first),1)
                progress_file.write_text(json.dumps(status),encoding='utf-8')
                second,status2=update.fetch_works(90,100,start_date='2024-01-01',end_date='2024-12-31',max_requests=1)
                self.assertEqual(status2['status'],'completed')
                self.assertEqual(len(second),1)
    def test_unique_and_valid_records(self):
        import json
        data=json.loads((Path(__file__).resolve().parents[1]/'data'/'papers.json').read_text())
        ids=[p['id'] for p in data['papers']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertGreaterEqual(len(data['papers']),166)  # Baseline has 166; automated discovery appends new studies
        self.assertTrue(all(p['url'].startswith('https://') for p in data['papers']))
        self.assertEqual(sum(p.get('source_group')=='original_review' for p in data['papers']),160)
        self.assertEqual(sum(p.get('source_group')=='post_review_sample' for p in data['papers']),6)
if __name__=='__main__': unittest.main()


class StaticPreviewTests(unittest.TestCase):
    def test_static_records_are_rendered(self):
        from pathlib import Path
        import json
        root=Path(__file__).resolve().parents[1]
        html=(root/'index.html').read_text(encoding='utf-8')
        rows=[p for p in json.loads((root/'data/papers.json').read_text(encoding='utf-8'))['papers'] if p.get('screening',{}).get('status')!='excluded']
        self.assertEqual(html.count('class="paper-card"'),len(rows))
        self.assertIn(f'id="stat-papers">{len(rows)}</strong>',html)
        self.assertIn('<svg class="chart-svg"',html)
        self.assertIn('id="family-filter"',html)
        self.assertIn('AI technology families',html)
        self.assertIn('id="viz-sunburst"',html)
        self.assertIn('id="viz-stacked"',html)
        self.assertTrue((root/'data/papers.csv').is_file())
