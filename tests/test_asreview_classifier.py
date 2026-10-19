"""Import and screening-label safeguards for the optional ASReview pipeline."""
import csv
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"agent"))
import asreview_classifier as model

class ASReviewTests(unittest.TestCase):
    def test_label_values(self):
        self.assertEqual([model.label_value(x) for x in ("1","0","-1","", "Included","Excluded")],
                         [1,0,None,None,1,0])
        with self.assertRaises(ValueError): model.label_value("unknown")
    def test_no_unlabelled_negatives(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"decisions.csv"
            with path.open("w",newline="",encoding="utf-8") as f:
                w=csv.writer(f);w.writerow(["title","abstract","label","doi"])
                w.writerows([["Food AI study","Test","1","10.5555/positive"],
                             ["Not relevant","Test","0","10.5555/negative"],
                             ["Not reviewed","Test","-1","10.5555/unlabelled"],
                             ["Duplicate positive","More text","1","10.5555/positive"]])
            h,rows,_=model.read_table(path)
            args=type("Args",(),dict(title_col=None,abstract_col=None,label_col=None,doi_col=None))()
            records,info=model.records_from_asreview(h,rows,args)
            self.assertEqual(len(records),2)
            self.assertEqual(info["positive_1"],1)
            self.assertEqual(info["negative_0"],1)
            self.assertEqual(info["unlabelled_ignored"],1)
    def test_conflicting_labels_rejected(self):
        args=type("Args",(),dict(title_col=None,abstract_col=None,label_col=None,doi_col=None))()
        with self.assertRaises(ValueError):
            model.records_from_asreview(["title","label"],
                [{"title":"Same","label":"1"},{"title":"Same","label":"0"}],args)
    def test_excel_xlsx_reader(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"sample.xlsx"
            with ZipFile(path,"w") as z:
                z.writestr("xl/workbook.xml",
                    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="ASReview" sheetId="1" r:id="rId1"/></sheets></workbook>')
                z.writestr("xl/_rels/workbook.xml.rels",
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
                z.writestr("xl/sharedStrings.xml",
                    '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>title</t></si><si><t>label</t></si><si><t>Example</t></si></sst>')
                z.writestr("xl/worksheets/sheet1.xml",
                    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row><row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2"><v>1</v></c></row></sheetData></worksheet>')
            columns,rows,sheet=model.read_table(path)
            self.assertEqual(columns,["title","label"])
            self.assertEqual(rows[0]["title"],"Example")
            self.assertEqual(rows[0]["label"],"1")
            self.assertEqual(sheet,"ASReview")
    def test_synthetic_training_and_blind_sampling(self):
        import importlib.util
        if importlib.util.find_spec("sklearn") is None:
            self.skipTest("Optional ML dependencies are not installed")
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            input_file=root/"training.csv"
            with input_file.open("w",newline="",encoding="utf-8") as f:
                w=csv.writer(f);w.writerow(["title","abstract","label","doi"])
                for i in range(160):
                    label=int(i%4==0 or i%4==1)
                    title=("Food safety pathogen AI" if label else "Farming crop yield prediction")+" study "+str(i)
                    abstract=("Deep learning detects Salmonella in food" if label else "Machine learning predicts agricultural harvest outcomes")
                    w.writerow([title,abstract,label,"10.1000/"+str(i)])
                for i in range(4):w.writerow(["Unscreened "+str(i),"","-1",""])
            pool_file=root/"pool.json"
            candidates=[]
            for i in range(210):
                label=int(i%4<2)
                candidates.append({"doi":"10.2000/"+str(i),
                    "title":("Food safety pathogen AI" if label else "Farming crop yield prediction")+" study "+str(i),
                    "abstract":("Deep learning detects Salmonella in food" if label else "Machine learning predicts agricultural harvest outcomes")})
            pool_file.write_text(json.dumps(candidates),encoding="utf-8")
            args=type("Args",(),{"input":str(input_file),"sheet":None,
                "title_col":None,"abstract_col":None,"label_col":None,"doi_col":None,
                "seed":42,"sample_size":30,"target_recall":.95,"pool":str(pool_file),
                "output_dir":str(root/"output")})()
            model.train(args)
            out=root/"output"
            self.assertTrue((out/"classifier.joblib").exists())
            report=json.loads((out/"evaluation.json").read_text())
            self.assertEqual(report["input"]["unlabelled_ignored"],4)
            self.assertEqual(report["heldout"]["n"],32)
            frame=json.loads((out/"sample_frame.json").read_text())
            self.assertEqual(frame["population"],210)
            self.assertEqual(len(frame["selected"]),30)
            with (out/"blind_sample.csv").open(encoding="utf-8-sig") as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),30)
            self.assertNotIn("score",rows[0])
            self.assertNotIn("predicted",rows[0])
            for row in rows:
                row["human_label"]=int("Food safety" in row["title"])
            labeled=out/"independent_labels.csv"
            with labeled.open("w",newline="",encoding="utf-8-sig") as f:
                w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
            evaluate_args=type("Args",(),{"labels":str(labeled),"frame":str(out/"sample_frame.json"),
                "sheet":None,"id_col":None,"label_col":None,"output":str(out/"sample_eval.json")})()
            model.evaluate_sample(evaluate_args)
            self.assertTrue((out/"sample_eval.json").exists())

if __name__=="__main__":unittest.main()
