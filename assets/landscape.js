(function chartsModule(){
"use strict";
const FAMILIES=["Machine learning (ML)","Deep learning (DL)","LLMs / foundation models","Other / mixed"];
const TECH_COLOR=["#d77aa8","#f0ae64","#8aa9dc","#b8aebe"];
const DOMAINS=["Microbiological hazards","Chemical hazards","Food fraud & authenticity","Foodborne illness","General food safety"];
const DOM_COLORS=["#d676a3","#f2ae5f","#b99cd4","#9299aa","#8dbba9"];
const esc=x=>String(x??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;");
const shorter=x=>({"Microbiological hazards":"Microbial","Chemical hazards":"Chemical","Food fraud & authenticity":"Food fraud","Foodborne illness":"Outbreaks","General food safety":"Other hazards","Laboratory testing":"Lab testing","Risk forecasting":"Forecasting","Risk factor analysis":"Risk factors","Inspection & enforcement":"Inspection","Methods & perspectives":"Methods","Early warning":"Early warning"}[x]||x);
const polar=(a,r,cx=288,cy=282)=>[(cx+r*Math.cos((a-90)*Math.PI/180)),(cy+r*Math.sin((a-90)*Math.PI/180))];
function arc(start,end,r1,r2){
 if(end-start<.05)return "";
 end=Math.min(start+359.99,end);const a=polar(start,r2),b=polar(end,r2),c=polar(end,r1),d=polar(start,r1),large=end-start>180?1:0;
 return `M ${a[0].toFixed(2)} ${a[1].toFixed(2)} A ${r2} ${r2} 0 ${large} 1 ${b[0].toFixed(2)} ${b[1].toFixed(2)} L ${c[0].toFixed(2)} ${c[1].toFixed(2)} A ${r1} ${r1} 0 ${large} 0 ${d[0].toFixed(2)} ${d[1].toFixed(2)} Z`;
}
function grouping(p){
 if(FAMILIES.includes(p.ai_family))return p.ai_family;
 const m=String(p.ai_method||"").toLowerCase(),t=String(p.title||"");
 if(/llm|foundation model/i.test(m)||/\b(large language model|foundation model|ChatGPT|generative AI)\b/i.test(t))return FAMILIES[2];
 if(/deep learning|neural network|transformer/i.test(m)||/deep learning/i.test(t))return FAMILIES[1];
 if(/classical machine learning/i.test(m)||/machine learning/i.test(t))return FAMILIES[0];
 return FAMILIES[3];
}
function subset(papers,collection){
 return papers.filter(p=>p.screening?.status!=="excluded"&&(collection==="all"||p.source_group===collection));
}
function sunburst(rows,family){
 const N=rows.length||1, chosen=rows.filter(p=>grouping(p)===family).length;
 let s='<svg viewBox="0 0 576 565" role="img" aria-label="Sunburst: domain, implementation context, and share of selected AI family">';
 let cursor=0,legend="";
 for(let k=0;k<DOMAINS.length;k++){
  const domain=DOMAINS[k],arr=rows.filter(p=>p.domain===domain);
  if(!arr.length)continue;
  const a=cursor,b=a+arr.length/N*360;cursor=b;const col=DOM_COLORS[k],space=.6;
  const matches=arr.filter(p=>grouping(p)===family).length,ratio=matches/arr.length;
  const base=arc(a+space,b-space,134,195);
  s+=`<path class="viz-piece" data-viz-domain="${esc(domain)}" fill="${col}" d="${base}"><title>${esc(domain)}: ${arr.length} papers; ${matches} ${esc(family)} (${Math.round(ratio*100)}%). Click to filter.</title></path>`;
  s+=`<path d="${arc(a+space,b-space,109,128)}" fill="#e8e5ef"></path>`;
  if(matches){let slice=arc(a+space,Math.max(a+space+.05,a+(b-a)*ratio-space),109,128);
   s+=`<path class="viz-piece" data-viz-domain="${esc(domain)}" d="${slice}" fill="${col}"><title>${esc(domain)}: ${matches}/${arr.length} in ${esc(family)}</title></path>`;
  }
  if(b-a>20){let pt=polar((a+b)/2,166);s+=`<text class="viz-domain-text" x="${pt[0].toFixed(1)}" y="${pt[1].toFixed(1)}" text-anchor="middle">${esc(shorter(domain))}</text>`;}
  const grouped={};for(const p of arr){const appl=p.application||"Unclassified";grouped[appl]=(grouped[appl]||0)+1;}
  let theta=a,j=0;
  for(const [app,n] of Object.entries(grouped).sort((x,y)=>y[1]-x[1])){
   const start=theta,end=theta+(b-a)*n/arr.length;theta=end;
   s+=`<path class="viz-piece" fill="${col}" fill-opacity="${[.62,.39,.82,.5,.29][j++%5]}" data-viz-domain="${esc(domain)}" data-viz-app="${esc(app)}" d="${arc(start+.45,end-.45,201,249)}"><title>${esc(domain)} / ${esc(app)}: ${n} papers. Click to filter.</title></path>`;
   if(end-start>17){const pt=polar((start+end)/2,226);s+=`<text class="viz-context-text" text-anchor="middle" x="${pt[0].toFixed(1)}" y="${pt[1].toFixed(1)}">${esc(shorter(app))}</text>`;}
  }
  legend+=`<span class="viz-legend-item"><i style="background:${col}"></i><span>${esc(domain)}</span><b>${arr.length}</b></span>`;
 }
 const display=family===FAMILIES[2]?"LLMs / FMs":family===FAMILIES[1]?"Deep learning":family===FAMILIES[0]?"Machine learning":"Other / mixed";
 s+=`<circle cx="288" cy="282" r="103" fill="var(--card)" stroke="var(--line-soft)"/><text class="viz-center-small" x="288" y="248" text-anchor="middle">SELECTED METHOD</text><text class="viz-center-name" x="288" y="281" text-anchor="middle">${esc(display)}</text><text class="viz-center-ratio" x="288" y="317" text-anchor="middle">${Math.round(chosen/rows.length*100)||0}%</text><text class="viz-center-small" x="288" y="338" text-anchor="middle">${chosen} of ${rows.length} papers</text></svg>`;
 return {svg:s,legend,summary:`${rows.length} records · ${chosen} ${family} studies`};
}
function stacked(rows){
 const ys=[...new Set(rows.map(p=>Number(p.year)).filter(y=>y>=2010&&y<2100))].sort((a,b)=>a-b);
 if(!ys.length)return "<p>No papers in this selection.</p>";
 const W=830,H=340,L=58,R=20,T=23,B=54,gh=H-T-B,gw=W-L-R,step=gw/ys.length,bw=Math.min(step*.66,42);
 const counts={};ys.forEach(y=>counts[y]=[0,0,0,0]);
 rows.forEach(p=>{if(counts[Number(p.year)])counts[Number(p.year)][FAMILIES.indexOf(grouping(p))]++});
 const maxV=Math.max(1,...ys.map(y=>counts[y].reduce((a,b)=>a+b,0))),ymax=Math.max(5,Math.ceil(maxV/10)*10);
 let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Stacked number of papers per year by AI method">`;
 for(let i=0;i<=5;i++){const val=Math.round(ymax*i/5),y=T+gh-gh*val/ymax;s+=`<line x1="${L}" x2="${W-R}" y1="${y}" y2="${y}" stroke="var(--line)" stroke-dasharray="${i?'3 5':'0'}"/><text x="${L-12}" y="${y+4}" text-anchor="end" class="viz-axis-text">${val}</text>`;}
 ys.forEach((yr,i)=>{const x=L+i*step+(step-bw)/2;let bottom=T+gh;
  FAMILIES.forEach((fam,j)=>{const n=counts[yr][j];if(!n)return;const height=n/ymax*gh;bottom-=height;
   s+=`<rect x="${x.toFixed(1)}" y="${bottom.toFixed(1)}" width="${bw.toFixed(1)}" height="${height.toFixed(1)}" fill="${TECH_COLOR[j]}" class="viz-piece" data-viz-year="${yr}" data-viz-family="${esc(fam)}"><title>${yr}: ${n} ${esc(fam)} paper${n===1?'':'s'}; click to filter</title></rect>`;
  });
  s+=`<text x="${(x+bw/2).toFixed(1)}" y="${H-33}" text-anchor="middle" class="viz-axis-text">${yr}</text>`;
 });
 s+=`<text x="${W/2}" y="${H-6}" text-anchor="middle" class="viz-axis-title">Year</text><text x="15" y="${H/2}" transform="rotate(-90 15 ${H/2})" text-anchor="middle" class="viz-axis-title">Number of papers</text></svg>`;
 return s;
}
function render(papers,collection="original_review",family="Deep learning (DL)"){
 const rows=subset(papers,collection),sun=sunburst(rows,family);
 return {sun:sun.svg,legend:sun.legend,summary:sun.summary,bars:stacked(rows),key:FAMILIES.map((fam,j)=>`<span class="viz-legend-item"><i style="background:${TECH_COLOR[j]}"></i>${esc(fam)}</span>`).join("")};
}
window.LIVING_CHARTS={FAMILIES,render,grouping};
})();
