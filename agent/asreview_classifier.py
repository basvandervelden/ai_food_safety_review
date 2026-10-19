#!/usr/bin/env python3
"""Prepare, train and evaluate an ASReview-based title/abstract classifier.

Human ASReview labels 1/0 only. Never interpret -1/empty as excluded.
This CLI writes LOCAL model/validation artefacts, not the live website data.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import posixpath
import random
import re
import sys
from zipfile import ZipFile
import xml.etree.ElementTree as ET

TITLE = ("title","article_title","record_title")
ABSTRACT = ("abstract","article_abstract","description")
LABEL = ("label","screening_label","decision","human_label","relevance","include","included")
DOI = ("doi","doi_url","digital_object_identifier")
YES = {"1","yes","true","include","included","relevant"}
NO = {"0","no","false","exclude","excluded","irrelevant"}
MISSING = {"","-1","na","n/a","nan","none","null","unlabelled","unlabeled"}
XML = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"

def xlsx_rows(path,sheet=None):
    with ZipFile(path) as z:
        book=ET.fromstring(z.read("xl/workbook.xml"))
        relations=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets={x.attrib["Id"]:x.attrib["Target"] for x in relations.findall("{%s}Relationship"%PKG)}
        sheets=book.findall(".//{%s}sheet"%XML)
        tab=next((x for x in sheets if x.attrib["name"]==sheet),None) if sheet else (sheets[0] if sheets else None)
        if tab is None: raise ValueError("Worksheet not found. Available: "+", ".join(x.attrib["name"] for x in sheets))
        target=targets[tab.attrib["{%s}id"%REL]]
        target=target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl",target))
        shared=[]
        if "xl/sharedStrings.xml" in z.namelist():
            root=ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared=["".join(t.text or "" for t in item.iter("{%s}t"%XML)) for item in root.findall("{%s}si"%XML)]
        root=ET.fromstring(z.read(target))
        output=[]
        for row in root.iter("{%s}row"%XML):
            cells={}
            for c in row.findall("{%s}c"%XML):
                letters=re.match(r"^[A-Z]+",c.attrib.get("r",""))
                if not letters: continue
                col=0
                for ch in letters.group(): col=col*26+ord(ch)-64
                value=c.find("{%s}v"%XML)
                v=value.text if value is not None else ""
                if c.attrib.get("t")=="s" and v: v=shared[int(v)]
                if c.attrib.get("t")=="inlineStr": v="".join(t.text or "" for t in c.iter("{%s}t"%XML))
                cells[col-1]=v or ""
            if cells: output.append([cells.get(i,"") for i in range(max(cells)+1)])
        return output,tab.attrib["name"]

def read_table(path,sheet=None):
    p=Path(path)
    if p.suffix.lower() in (".xlsx",".xlsm"):
        matrix,tab=xlsx_rows(p,sheet)
    elif p.suffix.lower() in (".csv",".tsv"):
        with p.open(encoding="utf-8-sig",newline="") as f:
            head=f.read(4000);f.seek(0)
            try: dialect=csv.Sniffer().sniff(head,delimiters=",;\t")
            except csv.Error: dialect=csv.excel_tab if p.suffix.lower()==".tsv" else csv.excel
            matrix=list(csv.reader(f,dialect))
        tab=None
    else: raise ValueError("Use .xlsx, .xlsm, .csv or .tsv (not legacy .xls).")
    if not matrix:raise ValueError("Empty input")
    headers=[str(x or "").strip() for x in matrix[0]]
    rows=[]
    for values in matrix[1:]:
        if any(str(x or "").strip() for x in values):
            rows.append(dict(zip(headers,([str(x or "").strip() for x in values]+[""]*len(headers))[:len(headers)])))
    return headers,rows,tab

def norm(s):return re.sub(r"[^a-z0-9]","",str(s).lower())
def column(headers,names,override=None,required=True):
    lookup={norm(x):x for x in headers}
    options=(override,) if override else names
    found=next((lookup[norm(x)] for x in options if norm(x) in lookup),None)
    if required and not found:raise ValueError("Column not found: %s; found %s"%(options,headers))
    return found

def label_value(raw):
    s=str(raw if raw is not None else "").strip().lower()
    if s in MISSING:return None
    if s in YES:return 1
    if s in NO:return 0
    raise ValueError("Unknown human label %r. Check the ASReview export."%raw)

def paper_id(title,doi=""):
    doi=re.sub(r"^https?://(?:dx\.)?doi\.org/","",str(doi or "").strip().lower())
    return "doi:"+doi if doi else "title:"+re.sub(r"[^a-z0-9]+"," ",title.lower()).strip()

def records_from_asreview(headers,rows,args):
    tc=column(headers,TITLE,args.title_col)
    ac=column(headers,ABSTRACT,args.abstract_col,False)
    lc=column(headers,LABEL,args.label_col)
    dc=column(headers,DOI,args.doi_col,False)
    counts=Counter();unique={};unlabelled=0
    for r in rows:
        label=label_value(r.get(lc,""))
        if label is None:unlabelled+=1;continue
        title=r.get(tc,"").strip()
        if not title:raise ValueError("A human-labelled record has no title")
        key=paper_id(title,r.get(dc,"") if dc else "")
        item={"id":key,"title":title,"abstract":r.get(ac,"") if ac else "","label":label}
        if key in unique and unique[key]["label"]!=label:
            raise ValueError("Conflicting manual screening labels for "+key)
        if key not in unique or len(item["abstract"])>len(unique[key]["abstract"]):unique[key]=item
    result=list(unique.values())
    for r in result:counts[r["label"]]+=1
    info={"rows":len(rows),"labeled_unique":len(result),"positive_1":counts[1],"negative_0":counts[0],
          "unlabelled_ignored":unlabelled,"columns":{"title":tc,"abstract":ac,"label":lc,"doi":dc}}
    return result,info

def text_of(record):return record["title"]+"\n\n"+record.get("abstract","")

def csv_out(path,fields,rows):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f);w.writerow(fields);w.writerows(rows)

def inspect(args):
    headers,rows,tab=read_table(args.input,args.sheet)
    try:
        _,info=records_from_asreview(headers,rows,args)
        print(json.dumps({"sheet":tab,"available_columns":headers,**info},indent=2))
    except ValueError as e:
        print(json.dumps({"sheet":tab,"available_columns":headers,"inspection_warning":str(e)},indent=2))
        raise

def train(args):
    try:
        import joblib
        import numpy as np
        from sklearn.base import clone
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import confusion_matrix,precision_recall_fscore_support,average_precision_score
        from sklearn.model_selection import cross_val_predict,StratifiedKFold,train_test_split
        from sklearn.pipeline import make_pipeline
    except ImportError as e:raise RuntimeError("pip install -r requirements-classifier.txt") from e
    h,r,tab=read_table(args.input,args.sheet)
    records,info=records_from_asreview(h,r,args)
    if min(info["positive_1"],info["negative_0"])<10:
        raise ValueError("Need at least ten HUMAN labels in both classes. Do not infer negative labels from unlabelled records.")
    y=np.asarray([x["label"] for x in records])
    tr,te=train_test_split(np.arange(len(y)),test_size=.20,stratify=y,random_state=args.seed)
    def model():
        return make_pipeline(TfidfVectorizer(ngram_range=(1,2),min_df=2,strip_accents="unicode",
                                             sublinear_tf=True,max_features=100000),
                             LogisticRegression(class_weight="balanced",max_iter=2500,random_state=args.seed))
    train_y=y[tr];docs=[text_of(records[int(i)]) for i in tr]
    folds=min(5,int(min(Counter(map(int,train_y)).values())))
    cv=StratifiedKFold(n_splits=folds,shuffle=True,random_state=args.seed)
    cv_prob=cross_val_predict(model(),docs,train_y,cv=cv,method="predict_proba")[:,1]
    viable=[v for v in sorted(set(cv_prob),reverse=True) if
            ((cv_prob>=v)&(train_y==1)).sum()/(train_y==1).sum()>=args.target_recall]
    threshold=float(max(viable))
    learned=model().fit(docs,train_y)
    test_prob=learned.predict_proba([text_of(records[int(i)]) for i in te])[:,1]
    pred=np.asarray(test_prob>=threshold,dtype=int);truth=y[te]
    pr,rec,f1,_=precision_recall_fscore_support(truth,pred,average="binary",zero_division=0)
    tn,fp,fn,tp=[int(v) for v in confusion_matrix(truth,pred,labels=[0,1]).ravel()]
    report={"trained_utc":datetime.now(timezone.utc).isoformat(),"input":info,"model":"TF-IDF + balanced logistic regression",
            "threshold_selected_by_training_only_cv":threshold,"target_recall":args.target_recall,
            "heldout":{"n":len(te),"precision":float(pr),"recall":float(rec),"f1":float(f1),
                       "average_precision":float(average_precision_score(truth,test_prob)),
                       "tp":tp,"fp":fp,"fn":fn,"tn":tn},
            "limitations":["ASReview active learning human screening is selection-biased.",
                           "The held-out ASReview subset does not estimate performance on new literature.",
                           "An independent stratified sample from all OpenAlex records is required."]}
    dest=Path(args.output_dir);dest.mkdir(parents=True,exist_ok=True)
    (dest/"evaluation.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    csv_out(dest/"heldout_predictions.csv",("id","title","human_label","prediction","score"),
            [(records[int(i)]["id"],records[int(i)]["title"],int(y[int(i)]),int(pred[k]),round(float(test_prob[k]),5)) for k,i in enumerate(te)])
    final=model().fit([text_of(x) for x in records],y)
    joblib.dump({"model":final,"threshold":threshold,"training_ids":{x["id"] for x in records}},dest/"classifier.joblib")
    print(json.dumps({"model":str(dest/"classifier.joblib"),"labels":info,"heldout":report["heldout"]},indent=2))
    if args.pool: score_model(dest/"classifier.joblib",args.pool,dest,args.sample_size,args.seed)

def pool_rows(path):
    p=Path(path)
    if p.suffix.lower()==".json":
        d=json.loads(p.read_text(encoding="utf-8"))
        rows=d if isinstance(d,list) else d["papers"]
        # Enrichment is a separate DOI-keyed cache: never overwrite existing
        # OpenAlex abstracts, only fill genuine gaps for model training.
        if p.name=="openalex_pool.json":
            cache_path=p.parent/"abstract_enrichment.json"
            if cache_path.exists():
                cache=json.loads(cache_path.read_text(encoding="utf-8"))
                augmented=[]
                for row in rows:
                    value=cache.get(str(row.get("doi","")).lower(),{})
                    if not str(row.get("abstract") or "").strip() and value.get("status")=="found":
                        row={**row,"abstract":value["abstract"],"abstract_source":value["source"]}
                    augmented.append(row)
                return augmented
        return rows
    h,rows,_=read_table(p)
    tc=column(h,TITLE);ac=column(h,ABSTRACT,required=False);dc=column(h,DOI,required=False)
    return [{"title":r.get(tc,""),"abstract":r.get(ac,"") if ac else "",
             "doi":r.get(dc,"") if dc else ""} for r in rows]

def score_model(model_file,pool_file,output_dir,sample_size,seed):
    import joblib
    saved=joblib.load(model_file) # Only load locally created trusted joblib models.
    unique={}
    for row in pool_rows(pool_file):
        title=str(row.get("title","")).strip()
        if not title:continue
        key=paper_id(title,row.get("doi",""))
        if key not in unique:unique[key]={**row,"title":title,"id":key}
    if not unique:raise ValueError("No papers to score")
    docs=list(unique.values())
    probs=saved["model"].predict_proba([text_of(x) for x in docs])[:,1]
    for p,prob in zip(docs,probs):
        p["score"]=float(prob)
        p["predicted"]=int(prob>=saved["threshold"])
        p["training_overlap"]=p["id"] in saved["training_ids"]
    dest=Path(output_dir);dest.mkdir(parents=True,exist_ok=True)
    csv_out(dest/"all_discovered_predictions.csv",
            ("id","doi","title","year","score","predicted","training_overlap"),
            [(p["id"],p.get("doi",""),p["title"],p.get("year",""),round(p["score"],6),
              p["predicted"],int(p["training_overlap"])) for p in docs])
    eligible=sorted((p for p in docs if not p["training_overlap"]),key=lambda p:(p["score"],p["id"]))
    if not eligible:raise ValueError("All papers overlap training; no independent sample")
    strata={"low":[],"middle":[],"high":[]}
    for i,p in enumerate(eligible):
        stratum=("low","middle","high")[min(2,3*i//len(eligible))]
        strata[stratum].append(p)
    rng=random.Random(seed)
    blind=[];frame={"population":len(eligible),"seed":seed,"strata":{},"selected":[]}
    for i,(name,items) in enumerate(strata.items()):
        n=min(len(items),sample_size//3+int(i<sample_size%3))
        selection=rng.sample(items,n)
        blind.extend(selection)
        frame["strata"][name]={"population":len(items),"sample":len(selection)}
        frame["selected"].extend({"id":p["id"],"stratum":name,"predicted":p["predicted"]} for p in selection)
    rng.shuffle(blind)
    csv_out(dest/"blind_sample.csv",("id","doi","title","abstract","human_label","reviewer_id"),
            [(p["id"],p.get("doi",""),p["title"],p.get("abstract",""),"","") for p in blind])
    (dest/"sample_frame.json").write_text(json.dumps(frame,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"scored":len(docs),"independent_pool":len(eligible),
                      "blinded_sample":len(blind),"output":str(dest)},indent=2))

def score(args):score_model(args.model,args.pool,Path(args.output_dir),args.sample_size,args.seed)

def evaluate_sample(args):
    frame=json.loads(Path(args.frame).read_text(encoding="utf-8"))
    h,rows,_=read_table(args.labels,args.sheet)
    key_col=column(h,("id","record_id"),args.id_col)
    label_col=column(h,("human_label","label","decision"),args.label_col)
    labels={}
    for r in rows:
        if not r.get(key_col):continue
        label=label_value(r.get(label_col,""))
        if label is None:continue
        key=r[key_col]
        if key in labels and labels[key]!=label:raise ValueError("Conflicting labels for "+key)
        labels[key]=label
    selected={p["id"]:p for p in frame["selected"]}
    missing=set(selected)-set(labels)
    if missing:raise ValueError("%d sample items still need a human label"%len(missing))
    totals=Counter()
    for p in selected.values():
        s=frame["strata"][p["stratum"]]
        weight=s["population"]/s["sample"]
        predicted=p["predicted"];human=labels[p["id"]]
        totals["tp" if predicted and human else "fp" if predicted else "fn" if human else "tn"]+=weight
    tp,fp,fn,tn=[totals[x] for x in ("tp","fp","fn","tn")]
    ratio=lambda a,b:round(a/b,4) if b else None
    report={"sample_count":len(selected),"independent_population":frame["population"],
            "weighted_precision":ratio(tp,tp+fp),"weighted_recall":ratio(tp,tp+fn),
            "estimated_relevant_fraction":ratio(tp+fn,tp+fp+fn+tn),
            "weighted_counts":{k:round(totals[k],2) for k in ("tp","fp","fn","tn")},
            "note":"Weighted estimates cover the OpenAlex discovery pool, not records missed by the search queries."}
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    insp=sub.add_parser("inspect");insp.add_argument("--input",required=True);insp.add_argument("--sheet")
    tr=sub.add_parser("train");tr.add_argument("--input",required=True);tr.add_argument("--sheet")
    for p in (insp,tr):
        for field in ("title","abstract","label","doi"):p.add_argument("--"+field+"-col")
    tr.add_argument("--output-dir",default="output/classifier");tr.add_argument("--pool")
    tr.add_argument("--seed",type=int,default=42);tr.add_argument("--target-recall",type=float,default=.95)
    tr.add_argument("--sample-size",type=int,default=300)
    score_p=sub.add_parser("score");score_p.add_argument("--model",required=True);score_p.add_argument("--pool",required=True)
    score_p.add_argument("--output-dir",default="output/classifier")
    score_p.add_argument("--sample-size",type=int,default=300);score_p.add_argument("--seed",type=int,default=42)
    ev=sub.add_parser("evaluate-sample");ev.add_argument("--labels",required=True);ev.add_argument("--sheet")
    ev.add_argument("--frame",required=True);ev.add_argument("--output",default="output/classifier/sample_evaluation.json")
    ev.add_argument("--label-col");ev.add_argument("--id-col")
    a=parser.parse_args()
    if a.command=="train" and not (0<a.target_recall<=1):parser.error("target-recall must be in (0,1]")
    if hasattr(a,"sample_size") and a.sample_size<3:parser.error("sample-size must be >=3")
    try:
        {"inspect":inspect,"train":train,"score":score,"evaluate-sample":evaluate_sample}[a.command](a)
    except (ValueError,FileNotFoundError,RuntimeError) as e:
        print("ERROR:",e,file=sys.stderr)
        raise SystemExit(2)

if __name__=="__main__":main()
