(() => {
  'use strict';
  const dataset = window.LIVING_REVIEW_DATA || { meta: { mode: 'preview', updated_at: 'unknown' }, papers: [] };
  const digest = window.LIVING_REVIEW_DIGEST || null;
  const papers = Array.isArray(dataset.papers) ? dataset.papers : [];
  const $ = (id) => document.getElementById(id);
  const state = { search:'', domain:'', method:'', application:'', datatype:'', year:'', collection:'', tab:'all', sort:'newest', limit:6 };
  let activeId = null;
  let lastFocused = null;
  const esc = (s) => String(s ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
  const icon = (name) => `<svg aria-hidden="true"><use href="#i-${name}"></use></svg>`;
  const labelDate = (iso,precision) => {if(!iso) return 'Date unknown';if(precision==='year')return String(iso).slice(0,4);const d=new Date(iso.slice(0,10)+'T12:00:00Z');return Number.isNaN(d.valueOf())?iso:d.toLocaleDateString('en-GB',{month:'short',year:'numeric',timeZone:'UTC'});};
  const uniq = (key) => [...new Set(papers.map(p=>p[key]).filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b)));
  const summaryOf = (p) => p.summary || 'Automated candidate identified from publication metadata. Follow the DOI to assess the original study.';
  const isReview = p => /review|perspective/i.test(p.publication_type || '') || p.ai_method === 'Review / synthesis';
  const statusLabel = (p) => {
    switch(p.screening?.status){
      case 'verified':return 'Expert verified';
      case 'curated_metadata':return 'Bibliographic metadata';
      case 'excluded':return 'Excluded';
      case 'automated_candidate':return 'Automated candidate';
      default:return 'Needs review';
    }
  };
  function filtered() {
    const query=state.search.trim().toLowerCase();
    const arr=papers.filter(p=> {
      if(p.screening?.status==='excluded')return false;
      if(state.domain && p.domain!==state.domain)return false;
      if(state.collection && (p.source_group||'automated_candidate')!==state.collection)return false;
      if(state.method && p.ai_method!==state.method)return false;
      if(state.application && p.application!==state.application)return false;
      if(state.datatype && p.data_type!==state.datatype)return false;
      if(state.year && String(p.year)!==state.year)return false;
      if(state.tab==='research' && isReview(p))return false;
      if(state.tab==='review' && !isReview(p))return false;
      if(query){const hay=[p.title,p.abstract,p.summary,p.journal,p.doi,p.domain,p.ai_method,p.data_type,p.application,p.target,p.data_collection_method,p.original_ai_techniques,p.citation_text,...(p.authors || [])].join(' ').toLowerCase();if(!hay.includes(query))return false;}
      return true;
    });
    arr.sort((a,b)=>state.sort==='title'?a.title.localeCompare(b.title):state.sort==='oldest'?a.date.localeCompare(b.date):b.date.localeCompare(a.date));
    return arr;
  }
  function domainStyle(domain){if(domain==='Chemical hazards')return 'chem';if(domain==='Microbiological hazards')return 'micro';if(domain==='Food fraud & authenticity')return 'fraud';if(domain==='Foodborne illness')return 'illness';return '';}
  function authorsOf(p){ const people=(p.authors||[]).filter(Boolean);if(!people.length)return p.journal||'Author details available via DOI';return people.length>3?`${people.slice(0,3).join(', ')} et al.`:people.join(', '); }
  function card(p){return `<article class="paper-card">
    <div class="paper-meta"><span class="domain-badge ${domainStyle(p.domain)}">${esc(p.domain||'Unclassified')}</span><span>${esc(labelDate(p.date,p.date_precision))}</span><span>·</span><span>${esc(p.journal||'Unknown source')}</span></div>
    <button class="paper-title" data-open="${esc(p.id)}">${esc(p.title)}</button>
    <p class="paper-byline">${esc(authorsOf(p))} · ${esc(p.publication_type||'Publication')}</p>
    <p class="paper-summary">${esc(summaryOf(p))}</p>
    <div class="paper-bottom"><div class="tag-group"><span class="tag">${esc(p.ai_method||'Unspecified method')}</span><span class="tag">${esc(p.application||'Unclassified')}</span><span class="tag">${esc(p.data_type||'Unclassified')}</span></div><button class="paper-read" data-open="${esc(p.id)}">View study ${icon('arrow')}</button></div>
  </article>`;}
  function renderList(){const all=filtered();const visible=all.slice(0,state.limit);$('paper-list').innerHTML=visible.map(card).join('');$('results-count').textContent=`${all.length} ${all.length===1?'result':'results'}`;$('tab-total').textContent=papers.filter(p=>p.screening?.status!=='excluded').length;$('empty-state').hidden=all.length>0;$('show-more').hidden=all.length<=state.limit;$('show-more').textContent=`Show more papers (${Math.max(0,all.length-state.limit)} remaining)`;if(all.length>state.limit)$('show-more').insertAdjacentHTML('beforeend',' '+icon('chevron'));}
  function fillSelect(id,items){const select=$(id);items.forEach(value=>{const option=document.createElement('option');option.value=String(value);option.textContent=String(value);select.appendChild(option);});}
  function setupFilters(){fillSelect('domain-filter',uniq('domain'));for(const key of uniq('source_group')){const o=document.createElement('option');o.value=key;o.textContent=key==='original_review'?'Published review (160)':key==='post_review_sample'?'Newer studies (6)':'Automated candidates';$('collection-filter').appendChild(o);}fillSelect('method-filter',uniq('ai_method'));fillSelect('app-filter',uniq('application'));fillSelect('data-filter',uniq('data_type'));fillSelect('year-filter',[...new Set(papers.map(p=>p.year))].sort((a,b)=>b-a));
    for(const [name,id] of [['collection','collection-filter'],['domain','domain-filter'],['method','method-filter'],['application','app-filter'],['datatype','data-filter'],['year','year-filter']]){
      $(id).addEventListener('change',e=>{state[name]=e.target.value;state.limit=6;renderList();});
    }
    $('search-input').addEventListener('input',e=>{state.search=e.target.value;state.limit=6;renderList();});
    $('sort-select').addEventListener('change',e=>{state.sort=e.target.value;renderList();});
    document.querySelectorAll('[data-tab]').forEach(btn=>btn.addEventListener('click',()=>{
      state.tab=btn.dataset.tab;state.limit=6;
      document.querySelectorAll('[data-tab]').forEach(b=>{b.classList.toggle('active',b===btn);b.setAttribute('aria-selected',String(b===btn));});renderList();
    }));
    $('show-more').addEventListener('click',()=>{state.limit+=6;renderList();});
    function reset(){state.search=state.domain=state.method=state.application=state.datatype=state.year=state.collection='';state.tab='all';state.sort='newest';state.limit=6;
      for(const id of ['collection-filter','domain-filter','method-filter','app-filter','data-filter','year-filter']) $(id).value='';
      $('search-input').value='';$('sort-select').value='newest';
      document.querySelectorAll('[data-tab]').forEach(b=>{const active=b.dataset.tab==='all';b.classList.toggle('active',active);b.setAttribute('aria-selected',String(active));});renderList();}
    $('reset-filters').addEventListener('click',reset);$('empty-reset').addEventListener('click',reset);
    document.addEventListener('keydown',e=>{if(e.key==='/' && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName) && $('detail-backdrop').hidden){e.preventDefault();$('search-input').focus();}});
  }
  function showDetail(id){const p=papers.find(it=>it.id===id);if(!p)return;lastFocused=document.activeElement;activeId=id;
    $('detail-content').innerHTML=`<button class="detail-close" id="close-dialog">${icon('x')} Close article</button>
      <div class="paper-meta"><span class="domain-badge ${domainStyle(p.domain)}">${esc(p.domain||'Other')}</span><span>${esc(labelDate(p.date,p.date_precision))}</span><span>${esc(p.journal||'')}</span></div>
      <h2>${esc(p.title)}</h2><p class="detail-authors">${esc((p.authors||[]).join(', ')||'See publisher record for author details')}</p>
      <div class="detail-summary">${esc(summaryOf(p))}</div><p class="detail-authors"><strong>Source:</strong> ${esc(p.source||'Not specified')} ${p.original_reference_number?'· Reference '+esc(p.original_reference_number):''}${p.additional_contexts?.length?' · Also classified under '+esc(p.additional_contexts.map(x=>x.application).join(', ')):''}</p>
      <h3>Classification</h3><div class="detail-grid">
      <div><small>Food safety domain</small><strong>${esc(p.domain||'Unclassified')}</strong></div>
      <div><small>Application context</small><strong>${esc(p.application||'Unclassified')}</strong></div>
      <div><small>Data type</small><strong>${esc(p.data_type||'Unclassified')}</strong></div>
      ${p.data_collection_method?`<div><small>Data collection (review)</small><strong>${esc(p.data_collection_method)}</strong></div>`:''}
      ${p.original_ai_techniques?`<div><small>AI techniques (review)</small><strong>${esc(p.original_ai_techniques)}</strong></div>`:''}
      <div><small>AI approach</small><strong>${esc(p.ai_method||'Unclassified')}</strong></div>
      <div><small>Publication type</small><strong>${esc(p.publication_type||'Unknown')}</strong></div>
      <div><small>DOI</small><strong>${esc(p.doi||'Not available')}</strong></div>
      </div>
      <h3>Abstract ${p.abstract?'(OpenAlex metadata)':''}</h3><p class="abstract">${esc(p.abstract||'Abstract not included in the source bibliography. Follow the publication link to retrieve the original record.')}</p>
      <div class="detail-notice"><strong>Screening status: ${esc(statusLabel(p))}</strong><br>${esc(p.screening?.reason||'No validation note recorded.')}<br>Record provenance: ${esc(p.source||'Not specified')}. Classification is not an endorsement of study quality.</div>
      <div class="detail-bottom"><a class="btn btn-primary" href="${esc(p.url||'https://doi.org/'+p.doi)}" target="_blank" rel="noopener noreferrer">Open publication ${icon('external')}</a><button class="btn btn-outline" id="copy-doi">${p.doi?'Copy DOI':'Copy citation'}</button></div>`;
    $('detail-backdrop').hidden=false;document.body.style.overflow='hidden';$('close-dialog').addEventListener('click',hideDetail);$('copy-doi').addEventListener('click',()=>{const val=p.doi||p.citation_text||p.title;if(navigator.clipboard?.writeText){navigator.clipboard.writeText(val).then(()=>{$('copy-doi').textContent=p.doi?'Copied DOI':'Copied citation';}).catch(()=>fallbackCopy(val));}else fallbackCopy(val);});$('detail-dialog').focus();
  }
  function fallbackCopy(value){const temp=document.createElement('textarea');temp.value=value;document.body.appendChild(temp);temp.select();try{document.execCommand('copy');$('copy-doi').textContent=p.doi?'Copied DOI':'Copied citation';}catch(e){$('copy-doi').textContent=value;}temp.remove();}
  function hideDetail(){$('detail-backdrop').hidden=true;document.body.style.overflow='';activeId=null;if(lastFocused?.focus)lastFocused.focus();}
  function setupDetails(){document.addEventListener('click',e=>{const btn=e.target.closest('[data-open]');if(btn)showDetail(btn.dataset.open);});$('detail-backdrop').addEventListener('click',e=>{if(e.target===$('detail-backdrop'))hideDetail();});document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('detail-backdrop').hidden)hideDetail();if(e.key==='Tab'&&!$('detail-backdrop').hidden){const focusable=[...$('detail-dialog').querySelectorAll('button,a[href]')];if(!focusable.length)return;const first=focusable[0],last=focusable[focusable.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});}
  function countBy(key){return papers.filter(p=>p.screening?.status!=='excluded').reduce((counts,p)=>{const value=p[key]||'Other';counts[value]=(counts[value]||0)+1;return counts;},{});}
  function barsHtml(counts){const items=Object.entries(counts).sort((a,b)=>b[1]-a[1]);const max=items[0]?.[1]||1;return items.map(([title,n])=>`<div class="bar-item"><div class="bar-label"><span>${esc(title)}</span><span>${n} ${n===1?'paper':'papers'}</span></div><div class="track"><div class="fill" style="width:${Math.max(3,(n/max)*100)}%"></div></div></div>`).join('');}
  function renderTrends(){const ys=countBy('year'),years=Object.keys(ys).map(Number).sort((a,b)=>a-b),max=Math.max(1,...Object.values(ys)),width=500,height=176,top=17,base=147;
    const span=Math.max(years.length,4),step=width/span,barW=Math.min(48,step*.53);
    let svg=`<svg class="chart-svg" viewBox="0 0 540 ${height}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Publication counts by year">`;
    for(let tick=0;tick<=3;tick++){const n=Math.ceil(max*tick/3),y=base-(n/max)*(base-top);svg+=`<line x1="37" x2="527" y1="${y}" y2="${y}" stroke="var(--line)" stroke-width="1" stroke-dasharray="${tick?'3 5':'0'}"/><text x="27" y="${y+3}" text-anchor="end">${n}</text>`;}
    years.forEach((year,i)=>{const val=ys[year],x=42+step*i+step/2,y=base-(val/max)*(base-top);svg+=`<rect x="${x-barW/2}" y="${y}" width="${barW}" height="${base-y}" rx="5" fill="${i===years.length-1?'#8063ac':'#c8b4e2'}"><title>${year}: ${val} paper(s) in the selected collection</title></rect><text x="${x}" y="168" text-anchor="middle">${year}</text><text x="${x}" y="${Math.max(10,y-6)}" text-anchor="middle">${val}</text>`;});
    $('trend-chart').innerHTML=svg+'</svg>';
    $('domain-bars').innerHTML=barsHtml(countBy('domain'));
    $('method-bars').innerHTML=barsHtml(countBy('ai_method'));
  }
  function renderDigest(){const recent=papers.filter(p=>p.screening?.status!=='excluded').sort((a,b)=>b.date.localeCompare(a.date)).slice(0,3);
    const updateDate=dataset.meta?.updated_at||'2026-10-15';$('digest-date').textContent=dataset.meta?.mode==='review_baseline'?'Published review + curated extension':dataset.meta?.mode==='preview'?'Curated preview':`Updated ${labelDate(updateDate)}`;
    if(dataset.meta?.mode==='review_baseline'){$('digest-intro').textContent='Selected newer research alongside the complete unique set of studies in the published review tables. These additions are not part of the 2026 systematic review.';}
    else if(dataset.meta?.mode==='preview'){$('digest-intro').textContent='A few recent papers from the curated starter collection. This is a reading list, not an automatically generated scientific synthesis.';}
    else{const n=digest?.new_last_30_days??dataset.meta?.new_candidates??0;$('digest-intro').textContent=`${n} indexed paper${n===1?'':'s'} added over the last 30 days. New additions are automated candidates pending expert validation.`;}
    $('digest-list').innerHTML=recent.map(p=>`<div class="digest-entry"><span class="bullet"></span><button data-open="${esc(p.id)}">${esc(p.title)}</button></div>`).join('');
  }
  function renderStats(){const active=papers.filter(p=>p.screening?.status!=='excluded');$('stat-papers').textContent=active.length.toLocaleString('en-GB');$('stat-domains').textContent=new Set(active.map(p=>p.domain).filter(Boolean)).size;$('stat-methods').textContent=new Set(active.map(p=>p.ai_method).filter(Boolean)).size;$('stat-latest').textContent=Math.max(0,...active.map(p=>Number(p.year)||0))||'—';
    $('snapshot-updated').textContent=dataset.meta?.mode==='review_baseline'?'160 original + 6 post-review · 15 October 2026':dataset.meta?.mode==='preview'?'Curated starter collection · 15 October 2026':`Index refreshed · ${labelDate(dataset.meta?.updated_at)}`;
    if(dataset.meta?.mode==='review_baseline'){$('header-badge').textContent='Published review + new research';$('collection-disclaimer').textContent='166 distinct records: 160 unique studies from the 161 table entries in van Meer et al. (2026), plus 6 more recent studies. The newer studies are not included in the published systematic review.';}
    else if(dataset.meta?.mode!=='preview'){$('header-badge').innerHTML='<span class="pulse-dot"></span> Automated evidence map';$('collection-disclaimer').textContent='Automatically discovered records are candidates, not confirmed systematic-review inclusions. The figures describe indexed records and depend on search coverage.';}
  }
  function csvValue(val){const text=Array.isArray(val)?val.join('; '):String(val??'');return '"'+text.replaceAll('"','""')+'"';}
  function setupExport(){$('export-btn').addEventListener('click',e=>{e.stopPropagation();$('export-menu').hidden=!$('export-menu').hidden;});document.addEventListener('click',e=>{if(!e.target.closest('.export-dropdown'))$('export-menu').hidden=true;});
    function download(format){const rows=filtered();let content,mime,filename;if(format==='csv'){
      const cols=['date','title','authors','journal','doi','domain','application','data_type','ai_method','publication_type','summary','url','source','source_group','original_reference_number','target','data_collection_method','original_ai_techniques','citation_text'];
      content=[cols.join(','),...rows.map(p=>cols.map(c=>csvValue(p[c])).join(','))].join('\r\n');mime='text/csv;charset=utf-8';filename='living-ai-food-safety-filtered.csv';
    }else{content=JSON.stringify({meta:dataset.meta,papers:rows},null,2);mime='application/json;charset=utf-8';filename='living-ai-food-safety-filtered.json';}
    const blob=new Blob(['\ufeff'+content],{type:mime});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),500);$('export-menu').hidden=true;}
    $('export-csv').addEventListener('click',()=>download('csv'));
    $('export-json').addEventListener('click',()=>download('json'));
  }
  function setupCuration(){
    let overrides={};try{overrides=JSON.parse(localStorage.getItem('living-review-overrides')||'{}')||{};}catch(_){overrides={};}
    const active=papers.filter(p=>p.screening?.status!=='excluded');
    const domains=uniq('domain');
    const persist=()=>{try{localStorage.setItem('living-review-overrides',JSON.stringify(overrides));}catch(_){}$('curation-count').textContent=`${Object.keys(overrides).length} ${Object.keys(overrides).length===1?'decision':'decisions'} saved locally`;};
    $('toggle-curation').addEventListener('click',()=>{const panel=$('curation-panel');panel.hidden=!panel.hidden;$('toggle-curation').innerHTML=(panel.hidden?'Open':'Close')+' workspace '+icon('chevron');});
    $('curation-list').innerHTML=active.map(p=>{
      const current=overrides[p.doi||p.id]||{};
      const statusOpts=[['','No decision'],['needs_review','Needs review'],['verified','Expert verified'],['excluded','Exclude']].map(([val,lab])=>`<option value="${val}" ${current.status===val?'selected':''}>${lab}</option>`).join('');
      const domainOpts=domains.map(domain=>`<option value="${esc(domain)}" ${(current.domain||p.domain)===domain?'selected':''}>${esc(domain)}</option>`).join('');
      return `<div class="curation-row" data-curate="${esc(p.doi||p.id)}"><div class="curation-row-main"><strong>${esc(p.title)}</strong><span>${esc(p.doi||'DOI not listed')} · ${esc(statusLabel(p))}</span></div><div class="curation-selects"><select data-curation-status aria-label="Review decision for ${esc(p.title)}">${statusOpts}</select><select data-curation-domain aria-label="Domain for ${esc(p.title)}">${domainOpts}</select></div></div>`;
    }).join('');
    $('curation-list').addEventListener('change',e=>{
      const row=e.target.closest('[data-curate]');if(!row)return;const doi=row.dataset.curate;
      const paper=active.find(p=>(p.doi||p.id)===doi);if(!paper)return;
      const status=row.querySelector('[data-curation-status]').value;
      const domain=row.querySelector('[data-curation-domain]').value;
      const decision={};if(status)decision.status=status;if(domain!==paper.domain)decision.domain=domain;
      if(Object.keys(decision).length)overrides[doi]=decision;else delete overrides[doi];persist();
    });
    $('download-overrides').addEventListener('click',()=>{
      const blob=new Blob([JSON.stringify(overrides,null,2)+'\n'],{type:'application/json;charset=utf-8'});
      const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='review_overrides.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),500);
    });persist();
  }
  function setupTheme(){const saved=(()=>{try{return localStorage.getItem('living-review-theme')}catch(_){return null}})();if(saved==='dark')document.body.classList.add('dark');
    const sync=()=>{$('theme-btn').innerHTML=icon(document.body.classList.contains('dark')?'sun':'moon');$('theme-btn').setAttribute('aria-label',document.body.classList.contains('dark')?'Switch to light mode':'Switch to dark mode');};sync();$('theme-btn').addEventListener('click',()=>{document.body.classList.toggle('dark');try{localStorage.setItem('living-review-theme',document.body.classList.contains('dark')?'dark':'light')}catch(_){}sync();});}
  function setupNavigation(){const anchors=document.querySelectorAll('.nav-link');anchors.forEach(a=>a.addEventListener('click',()=>{anchors.forEach(it=>it.classList.remove('active'));a.classList.add('active');}));}
  setupTheme();setupFilters();setupDetails();setupExport();setupNavigation();setupCuration();renderStats();renderList();renderTrends();renderDigest();
})();
