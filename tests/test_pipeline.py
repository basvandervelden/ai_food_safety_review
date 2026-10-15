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
    def test_unique_and_valid_records(self):
        import json
        data=json.loads((Path(__file__).resolve().parents[1]/'data'/'papers.json').read_text())
        ids=[p['id'] for p in data['papers']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(len(data['papers']),166)
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
        self.assertTrue((root/'data/papers.csv').is_file())
