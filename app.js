(function () {
  'use strict';
  const D=window.REVIEW_DATA, M=window.ReviewModel, $=id=>document.getElementById(id);
  if(!D||!M) { $('original-paper').textContent='No se pudo cargar el manuscrito.'; return; }
  const proposals=new Map(D.initialProposals.map(p=>[p.blockId,p]));
  const progress=$('scroll-progress');
  const progressBar=$('scroll-progress-bar');
  let syncing=false, frame,activePane=$('original-pane');
  function updateProgress(pane=activePane) {
    const maximum=Math.max(0,pane.scrollHeight-pane.clientHeight);
    const percent=maximum?Math.round(Math.max(0,Math.min(1,pane.scrollTop/maximum))*100):0;
    const text=percent+'%';
    if(progress.textContent!==text)progress.textContent=text;
    if(progressBar.value!==percent)progressBar.value=percent;
  }
  function plain(html) {
    const t=document.createElement('template');t.innerHTML=html;
    return (t.content.textContent||'').replace(/\s+/g,' ').trim();
  }
  function proposalHtml(p) { return p.proposedHtml??M.editableHtml(p.proposedLatex); }
  function wordHtml(tokens,side,tag='p') {
    const text=tokens.map(t=>t.type==='same'?M.escapeHtml(t.text):'<mark class="'+(side==='original'?'word-removed':'word-added')+'">'+M.escapeHtml(t.text)+'</mark>').join('');
    return text?(tag?'<'+tag+'>'+text+'</'+tag+'>':text):'';
  }
  function listWordHtml(original,proposed,side) {
    const lists=[original,proposed].map(markup=>{
      const t=document.createElement('template');t.innerHTML=markup;
      return t.content.querySelector('ul,ol');
    });
    const items=lists.map(list=>[...(list?.children||[])]);
    const selected=side==='original'?0:1;
    const highlight=(a,b)=>{
      const diff=M.diffWords(plain(a),plain(b));
      return wordHtml(selected===0?diff.left:diff.right,side,'');
    };
    const output=[];
    for(let i=0;i<Math.max(...items.map(list=>list.length));i++) {
      if(!items[selected][i])continue;
      const parts=items.map(list=>{
        const copy=list[i]?.cloneNode(true);
        const label=copy?.firstElementChild?.tagName==='STRONG'?copy.firstElementChild:null;
        const title=label?.innerHTML||'';label?.remove();
        return [title,copy?.innerHTML||''];
      });
      const title=highlight(parts[0][0],parts[1][0]);
      const text=highlight(parts[0][1],parts[1][1]);
      output.push('<li>'+(title?'<strong>'+title+'</strong> ':'')+text+'</li>');
    }
    const tag=lists[selected]?.tagName.toLowerCase()||'ul';
    return '<'+tag+'>'+output.join('')+'</'+tag+'>';
  }
  function content(b,side) {
    if(b.proposedOnly) {
      if(side==='original')return '';
      if(b.kind==='paragraph'&&b.reviewStatus!=='accepted'&&$('word-diff').checked)
        return '<p><mark class="word-added">'+M.escapeHtml(plain(b.html))+'</mark></p>';
      return b.html;
    }
    const p=proposals.get(b.id);
    if(b.kind==='heading') {
      const heading=p&&side==='proposed'?M.escapeHtml(plain(proposalHtml(p))):b.html;
      return heading?'<h'+b.level+'>'+heading+'</h'+b.level+'>':'';
    }
    if(p&&p.status!=='accepted'&&$('word-diff').checked) {
      if(b.kind==='list')return listWordHtml(b.html,proposalHtml(p),side);
      if(b.kind==='paragraph') {
        const diff=M.diffWords(plain(b.html),plain(proposalHtml(p)));
        return wordHtml(side==='original'?diff.left:diff.right,side);
      }
    }
    return p&&side==='proposed'?proposalHtml(p):b.html;
  }
  function renderBlock(b,side) {
    const el=document.createElement('div');el.id=side+'-'+b.id;el.dataset.block=b.id;
    const status=proposals.get(b.id)?.status||b.reviewStatus;
    el.className='paper-block '+side+(status==='accepted'?' approved':['pending','needs_changes'].includes(status)?' changed':'');el.innerHTML=content(b,side);
    return el;
  }
  for(const side of ['original','proposed']) {
    const paper=$(side+'-paper'), header=document.createElement('header');header.className='paper-header';
    header.innerHTML='<h1>'+D.title+'</h1><p>'+M.escapeHtml(D.authors)+'</p>';
    paper.append(header);
    for(const b of D.blocks)paper.append(renderBlock(b,side));
  }
  function blockTop(el,pane) {return el.getBoundingClientRect().top-pane.getBoundingClientRect().top+pane.scrollTop;}
  function focusBoth(id) {
    syncing=true;
    for(const side of ['original','proposed']) {
      const pane=$(side+'-pane'),el=$(side+'-'+id);
      if(el) {
        const inset=Math.max(0,(pane.clientHeight-el.offsetHeight)/2);
        const maximum=Math.max(0,pane.scrollHeight-pane.clientHeight);
        pane.scrollTop=Math.max(0,Math.min(maximum,blockTop(el,pane)-inset));
      }
    }
    updateProgress();
    requestAnimationFrame(()=>syncing=false);
  }
  function align(source,target) {
    const y=source.scrollTop, blocks=[...source.querySelectorAll('.paper-block')];
    const top=blocks.filter(el=>blockTop(el,source)<=y+30).at(-1)||blocks[0];
    if(!top)return;
    const other=$(target.id.startsWith('original')?'original-'+top.dataset.block:'proposed-'+top.dataset.block);
    const fraction=Math.max(0,(y-blockTop(top,source))/Math.max(top.offsetHeight,1));
    syncing=true;target.scrollTop=blockTop(other,target)+fraction*other.offsetHeight;
    requestAnimationFrame(()=>syncing=false);
  }
  for(const side of ['original','proposed']) {
    const pane=$(side+'-pane'),other=$(side==='original'?'proposed-pane':'original-pane');
    pane.addEventListener('scroll',()=>{
      if(syncing)return;
      activePane=pane;
      updateProgress();
      if(!$('sync').checked)return;
      cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>align(pane,other));
    },{passive:true});
  }
  $('sync').addEventListener('change',()=>{
    if($('sync').checked) {
      activePane=$('original-pane');
      align(activePane,$('proposed-pane'));
      updateProgress();
    }
  });
  $('word-diff').addEventListener('change',()=>{
    document.body.classList.toggle('words-off',!$('word-diff').checked);
    const left=$('original-pane'),right=$('proposed-pane');
    const first=[...left.querySelectorAll('.paper-block')].find(el=>el.getBoundingClientRect().bottom>left.getBoundingClientRect().top+30);
    const offset=first?blockTop(first,left)-left.scrollTop:0;
    const positions=[left.scrollTop,right.scrollTop];syncing=true;
    for(const b of D.blocks)if(proposals.has(b.id)||(b.proposedOnly&&b.kind==='paragraph'))for(const side of ['original','proposed'])$(side+'-'+b.id).replaceWith(renderBlock(b,side));
    if($('sync').checked&&first) {
      left.scrollTop=blockTop($('original-'+first.dataset.block),left)-offset;
      requestAnimationFrame(()=>align(left,right));
    } else {
      left.scrollTop=positions[0];right.scrollTop=positions[1];requestAnimationFrame(()=>syncing=false);
    }
    requestAnimationFrame(()=>updateProgress());
  });
  window.addEventListener('resize',()=>updateProgress());
  document.addEventListener('load',()=>updateProgress(),true);
  const initial=D.blocks.find(b=>b.id===location.hash.slice(1))?.id||D.initialBlock;
  requestAnimationFrame(()=>focusBoth(initial));
})();
