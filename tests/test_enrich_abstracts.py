import json
from datetime import datetime,timezone
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"agent"))
import enrich_abstracts as a

class EnrichTests(TestCase):
    def test_do_not_accept_wrong_doi_crossref(self):
        class HTTP:
            def get(self,url,**kw):
                return {"message":{"DOI":"10.1234/other","abstract":"A long and completely different article's abstract "+("data "*25)}}
        self.assertIsNone(a.crossref("10.1234/correct",HTTP()))
    def test_clean_jats(self):
        s=a.clean("<jats:abstract><jats:p>A <jats:italic>useful</jats:italic> study &amp; discussion.</jats:p></jats:abstract>")
        self.assertEqual(s,"A useful study & discussion.")
    def test_europe_pmc_exact_doi(self):
        class HTTP:
            def get(self,url,**kw):
                return {"resultList":{"result":[{"doi":"10.2222/incorrect","abstractText":"Invalid text "+("no "*60)},
                    {"doi":"10.2222/correct","abstractText":"Correct food safety abstract "+("science "*20),"id":"42","source":"MED"}]}}
        result=a.europe_pmc("10.2222/correct",HTTP())
        self.assertEqual(result["source"],"Europe PMC")
        self.assertIn("Correct",result["abstract"])
    def test_pubmed_requires_doi_match(self):
        class HTTP:
            def get(self,url,**kw):
                if "esearch" in url:return {"esearchresult":{"idlist":["22"]}}
                return b'''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>22</PMID><Article><Abstract><AbstractText>Substantial but wrong abstract '''+b'x'*100+b'''</AbstractText></Abstract></Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="doi">10.2000/other</ArticleId></ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>'''
        self.assertIsNone(a.pubmed("10.2000/correct",HTTP()))
    def test_limit_and_resume_and_no_title_only_false_negative(self):
        rows=[{"doi":"10.1000/first","title":"First","abstract":""},
              {"doi":"10.1000/second","title":"Second","abstract":""},
              {"doi":"10.1000/third","title":"Third","abstract":"Already had an abstract"}]
        calls=[]
        def getter(doi,http):
            calls.append(doi)
            return {"abstract":"Science and food safety analytical methods "+("research "*18),
                    "source":"Crossref","source_id":doi,"source_url":"https://api.crossref.org/works/"+doi}
        with TemporaryDirectory() as tmp,patch.object(a,"CACHE",Path(tmp)/"enrichment.json"):
            cache={}
            p,e=a.run(rows,cache,object(),max_articles=1,providers=[getter])
            self.assertEqual((p,e),(1,0))
            self.assertEqual(calls,["10.1000/first"])
            p,e=a.run(rows,cache,object(),max_articles=1,providers=[getter])
            self.assertEqual((p,e),(1,0))
            self.assertEqual(calls,["10.1000/first","10.1000/second"])
            report=a.summary(rows,cache,2,2,0)
            self.assertEqual(report["combined_abstracts_present"],3)
            self.assertEqual(report["still_missing"],0)
    def test_missing_is_cached_without_negative_label(self):
        rows=[{"doi":"10.1000/first","title":"First","abstract":""}]
        cache={}
        with TemporaryDirectory() as tmp,patch.object(a,"CACHE",Path(tmp)/"enrichment.json"):
            p,e=a.run(rows,cache,object(),max_articles=1,providers=[lambda doi,http:None])
            self.assertEqual(cache["10.1000/first"]["status"],"not_found")
            self.assertNotIn("screening",cache["10.1000/first"])
            calls=[]
            p,e=a.run(rows,cache,object(),max_articles=1,providers=[lambda doi,http:calls.append(doi)])
            self.assertEqual(p,0)
            self.assertEqual(calls,[])
