(function livingCharts(){
"use strict";
const FAMILIES=["Machine learning (ML)","Deep learning (DL)","LLMs / foundation models","Other / mixed"];
const TECH_COLORS=["#eb3b84","#fab05c","#a68bcf","#b9b4bf"];
const DOMAINS=[
  {name:"Chemical hazards",short:["Chemical","hazards"],color:"#fab05c"},
  {name:"Food fraud & authenticity",short:["Food fraud","& authenticity"],color:"#f2d4bb"},
  {name:"Foodborne illness",short:["Foodborne","disease"],color:"#47464b"},
  {name:"Microbiological hazards",short:["Microbiological","hazards"],color:"#eb3b84"},
  {name:"General food safety",short:["Other food","safety"],color:"#ff7063"}
];
const esc=(s)=>String(s??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;");
const contextLabel=s=>({"Laboratory testing":"Laboratory testing","Risk forecasting":"Forecasting","Risk analysis":"Risk factors","Risk factor analysis":"Risk factors","Regulatory efficiency":"Regulatory efficiency","Inspection & enforcement":"Border / inspection","Early warning":"Early warning","Methods & perspectives":"Methods / reviews"}[s]||s);
function method(p){
 if(FAMILIES.includes(p.ai_family))return p.ai_family;
 const a=(p.ai_method||"").toLowerCase();
 if(/llm|foundation model/.test(a))return FAMILIES[2];
 if(/deep learning|neural network|transformer/.test(a))return FAMILIES[1];
 if(/classical machine learning/.test(a))return FAMILIES[0];
 return FAMILIES[3];
}
function eligible(papers,collection){return papers.filter(p=>p.screening?.status!=="excluded"&&(collection==="all"||p.source_group===collection));}
const X=470,Y=386;
function xy(angle,r){const a=(angle-90)*Math.PI/180;return [X+r*Math.cos(a),Y+r*Math.sin(a)];}
function arc(start,end,rIn,rOut){
 if(end-start<=.07)return "";
 const e=Math.min(start+359.999,end),l=(e-start)>180?1:0;
 const [x1,y1]=xy(start,rOut),[x2,y2]=xy(e,rOut),[x3,y3]=xy(e,rIn),[x4,y4]=xy(start,rIn);
 return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${rOut} ${rOut} 0 ${l} 1 ${x2.toFixed(2)} ${y2.toFixed(2)} L ${x3.toFixed(2)} ${y3.toFixed(2)} A ${rIn} ${rIn} 0 ${l} 0 ${x4.toFixed(2)} ${y4.toFixed(2)} Z`;
}
function opacity(i){return [.98,.76,.61,.43,.31,.22][i%6];}
function labelLayout(segments){
 const placed=[];
 for(const side of [-1,1]){
  const items=segments.filter(s=>s.side===side).sort((a,b)=>a.desiredY-b.desiredY);
  const min=62,max=713,gap=22;
  items.forEach((s,i)=>{s.labelY=Math.max(min,s.desiredY,i?items[i-1].labelY+gap:min)});
  if(items.length&&items[items.length-1].labelY>max){
    items[items.length-1].labelY=max;
    for(let i=items.length-2;i>=0;i--)items[i].labelY=Math.min(items[i].labelY,items[i+1].labelY-gap);
  }
  placed.push(...items);
 }
 return placed;
}
function sunburst(rows,family){
 const all=rows.length,N=all||1, chosen=rows.filter(p=>method(p)===family).length;
 const svg=['<svg class="science-sunburst" viewBox="0 0 940 768" role="img" aria-label="Sunburst showing food safety domains, contexts, and selected AI method percentages">'];
 const legend=[];const labelCandidates=[];let cursor=0;
 for(const domain of DOMAINS){
  const ps=rows.filter(p=>p.domain===domain.name);
  if(!ps.length)continue;
  const a=cursor,b=a+ps.length/N*360;cursor=b;
  const target=ps.filter(p=>method(p)===family).length;
  const share=target/ps.length;const span=b-a,totPct=Math.round(ps.length/N*100);
  const title=`${domain.name}: ${ps.length} papers (${totPct}%); ${target} ${family} (${Math.round(100*share)}%)`;
  const shrink=Math.min(.7,span*.09);
  svg.push(`<path class="science-segment" data-viz-domain="${esc(domain.name)}" d="${arc(a+shrink,b-shrink,143,213)}" fill="${domain.color}"><title>${esc(title)}. Click to filter.</title></path>`);
  svg.push(`<path d="${arc(a+shrink,b-shrink,93,135)}" fill="var(--science-inner-empty,#eae7ed)" stroke="var(--card)" stroke-width="1.4"></path>`);
  if(target){const ending=a+(b-a)*share;svg.push(`<path class="science-segment" data-viz-domain="${esc(domain.name)}" d="${arc(a+shrink,Math.max(a+shrink+.08,ending-shrink),93,135)}" fill="${domain.color}"><title>${esc(domain.name)}: ${target} of ${ps.length} (${Math.round(100*share)}%) use ${esc(family)}</title></path>`);}
  if(span>15){
    const mid=(a+b)/2,p=xy(mid,180);
    const color=domain.name==="Foodborne illness"?"#fff":"#28212a";
    svg.push(`<text x="${p[0].toFixed(1)}" y="${(p[1]-7).toFixed(1)}" text-anchor="middle" class="science-domain-text" fill="${color}"><tspan x="${p[0].toFixed(1)}">${esc(domain.short[0])}</tspan><tspan x="${p[0].toFixed(1)}" dy="16">${esc(domain.short[1])}</tspan><tspan x="${p[0].toFixed(1)}" dy="18" font-weight="700">${totPct}%</tspan></text>`);
  }
  if(span>10){
    const p=xy((a+b)/2,113);
    svg.push(`<text class="science-percent" x="${p[0].toFixed(1)}" y="${(p[1]+4).toFixed(1)}" text-anchor="middle">${Math.round(share*100)}%</text>`);
  }
  const ctx={};ps.forEach(p=>{const app=p.application||"Unclassified";ctx[app]=(ctx[app]||0)+1;});
  let cursor2=a,idx=0;
  for(const [app,n] of Object.entries(ctx).sort((a,b)=>b[1]-a[1])){
    const from=cursor2,to=from+(n/ps.length)*span;cursor2=to;
    const sectorGap=Math.min(.45,(to-from)*.12),middle=(from+to)/2;
    svg.push(`<path class="science-segment" data-viz-domain="${esc(domain.name)}" data-viz-app="${esc(app)}" fill="${domain.color}" fill-opacity="${opacity(idx++)}" stroke="var(--card)" stroke-width="1.5" d="${arc(from+sectorGap,to-sectorGap,220,274)}"><title>${esc(domain.name)} / ${esc(app)}: ${n} paper${n===1?"":"s"}. Click to filter.</title></path>`);
    if(to-from>=4.0){
      const [vx,vy]=xy(middle,299);
      labelCandidates.push({side:vx<X?-1:1,desiredY:vy,angle:middle,n,app,domain:domain.name,color:domain.color});
    }
  }
  legend.push(`<div class="science-domain-row"><i style="background:${domain.color}"></i><div><span>${esc(domain.name)}</span><small>${ps.length} papers · ${Math.round(100*target/ps.length)}% ${esc(family==="Deep learning (DL)"?"DL":family==="Machine learning (ML)"?"ML":family==="LLMs / foundation models"?"LLMs / FMs":"other")}</small></div><strong>${totPct}%</strong></div>`);
 }
 for(const item of labelLayout(labelCandidates)){
  const [sx,sy]=xy(item.angle,277),[bx,by]=xy(item.angle,296);
  const ex=item.side>0?823:116;
  const tx=item.side>0?829:110,anchor=item.side>0?"start":"end";
  svg.push(`<path d="M ${sx.toFixed(1)} ${sy.toFixed(1)} L ${bx.toFixed(1)} ${by.toFixed(1)} L ${ex} ${item.labelY.toFixed(1)}" class="science-leader"/>`);
  svg.push(`<text x="${tx}" y="${(item.labelY+4).toFixed(1)}" class="science-callout" text-anchor="${anchor}">${esc(contextLabel(item.app))} <tspan class="science-callout-count">(${item.n})</tspan></text>`);
 }
 const centerName=family==="Deep learning (DL)"?"Deep learning":family==="Machine learning (ML)"?"Machine learning":family==="LLMs / foundation models"?"LLMs / FMs":"Other / mixed";
 svg.push(`<circle cx="${X}" cy="${Y}" r="85" fill="var(--card)" /><text x="${X}" y="${Y-29}" text-anchor="middle" class="science-center-cap">SELECTED METHOD</text><text x="${X}" y="${Y+1}" text-anchor="middle" class="science-center-method">${esc(centerName)}</text><text x="${X}" y="${Y+35}" text-anchor="middle" class="science-center-count">${Math.round(chosen/N*100)}%</text><text x="${X}" y="${Y+57}" text-anchor="middle" class="science-center-sub">${chosen} of ${all} papers</text></svg>`);
 return {svg:svg.join(""),legend:legend.join(""),summary:`${all} indexed papers · ${chosen} classified as ${family}`};
}
function stacked(rows){
 const years=[...new Set(rows.map(p=>Number(p.year)).filter(y=>y>=2012&&y<2100))].sort((a,b)=>a-b);
 if(!years.length)return '<p>No publication years available.</p>';
 const W=920,H=380,L=61,R=16,T=25,B=73,gh=H-T-B,gw=W-L-R;
 const groups={};years.forEach(y=>groups[y]=FAMILIES.map(()=>0));
 for(const p of rows){const yr=Number(p.year);if(groups[yr])groups[yr][FAMILIES.indexOf(method(p))]++;}
 const maxN=Math.max(...years.map(y=>groups[y].reduce((a,b)=>a+b,0)),1);
 const maxY=Math.max(5,Math.ceil(maxN/10)*10),step=gw/years.length,bw=Math.min(43,step*.72);
 let svg=`<svg class="science-stacked" viewBox="0 0 ${W} ${H}" role="img" aria-label="Yearly paper counts split into machine learning, deep learning, LLMs or foundation models and others">`;
 for(let tick=0;tick<=5;tick++){
  const val=maxY*tick/5,y=T+gh*(1-val/maxY);
  svg+=`<line class="science-grid" x1="${L}" y1="${y.toFixed(1)}" x2="${W-R}" y2="${y.toFixed(1)}"/><text class="science-axis-text" x="${L-12}" y="${(y+4).toFixed(1)}" text-anchor="end">${Math.round(val)}</text>`;
 }
 for(let i=0;i<years.length;i++){
  const yr=years[i],x=L+i*step+(step-bw)/2;let y0=T+gh;
  for(let k=0;k<FAMILIES.length;k++){
    const n=groups[yr][k];if(!n)continue;
    const h=n/maxY*gh;y0-=h;
    svg+=`<rect class="science-bar-segment" data-viz-year="${yr}" data-viz-family="${esc(FAMILIES[k])}" x="${x.toFixed(1)}" y="${y0.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" fill="${TECH_COLORS[k]}"><title>${yr}: ${n} ${esc(FAMILIES[k])} paper${n===1?"":"s"}. Click to filter.</title></rect>`;
  }
  const tx=x+bw/2;
  svg+=`<text class="science-axis-text" x="${tx.toFixed(1)}" y="${H-48}" text-anchor="end" transform="rotate(-43 ${tx.toFixed(1)} ${H-48})">${yr}</text>`;
 }
 svg+=`<text class="science-axis-title" x="${W/2}" y="${H-6}" text-anchor="middle">Publication year</text><text class="science-axis-title" x="19" y="${H/2}" text-anchor="middle" transform="rotate(-90 19 ${H/2})">Number of papers</text></svg>`;
 return svg;
}
function render(papers,collection="all",family="Deep learning (DL)"){
 const rows=eligible(papers,collection),sun=sunburst(rows,family);
 return {sun:sun.svg,legend:sun.legend,summary:sun.summary,bars:stacked(rows),key:FAMILIES.map((f,i)=>`<span class="science-key"><i style="background:${TECH_COLORS[i]}"></i>${esc(f)}</span>`).join("")};
}
const api={FAMILIES,render,method,eligible};
if(typeof window!=="undefined")window.LIVING_CHARTS=api;
return api;
})();
