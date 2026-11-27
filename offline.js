(function () {
  'use strict';
  const $=id=>document.getElementById(id);
  const left=$('original-pane'),right=$('proposed-pane'),progress=$('scroll-progress');
  const progressBar=$('scroll-progress-bar');
  const blocks=new Map([left,right].map(pane=>[pane,[...pane.querySelectorAll('.paper-block')]]));
  let updating=false,frame,activePane=left;
  function updateProgress(pane=activePane) {
    const maximum=Math.max(0,pane.scrollHeight-pane.clientHeight);
    const percent=maximum?Math.round(Math.max(0,Math.min(1,pane.scrollTop/maximum))*100):0;
    const text=percent+'%';
    if(progress.textContent!==text)progress.textContent=text;
    if(progressBar.value!==percent)progressBar.value=percent;
  }
  function top(element,pane) {
    return element.getBoundingClientRect().top-pane.getBoundingClientRect().top+pane.scrollTop;
  }
  function align(source,target) {
    const list=blocks.get(source),y=source.scrollTop;
    let low=0,high=list.length-1;
    while(low<high) {
      const middle=Math.ceil((low+high)/2);
      if(top(list[middle],source)<=y+1)low=middle;
      else high=middle-1;
    }
    const block=list[low];
    if(!block)return;
    const other=$(target===left?'original-'+block.dataset.block:'proposed-'+block.dataset.block);
    const fraction=Math.max(0,(y-top(block,source))/Math.max(block.offsetHeight,1));
    const position=top(other,target)+fraction*other.offsetHeight;
    if(Math.abs(target.scrollTop-position)<1)return;
    updating=true;target.scrollTop=position;
    requestAnimationFrame(()=>updating=false);
  }
  for(const [source,target] of [[left,right],[right,left]]) {
    source.addEventListener('scroll',()=>{
      if(updating)return;
      activePane=source;
      updateProgress();
      if(!$('sync').checked)return;
      cancelAnimationFrame(frame);
      frame=requestAnimationFrame(()=>align(source,target));
    },{passive:true});
  }
  $('sync').addEventListener('change',()=>{
    if($('sync').checked) {
      activePane=left;
      align(left,right);
      updateProgress();
    }
  });
  $('word-diff').addEventListener('change',()=>{
    document.body.classList.toggle('words-off',!$('word-diff').checked);
    requestAnimationFrame(()=>updateProgress());
  });
  window.addEventListener('resize',()=>updateProgress());
  document.addEventListener('load',()=>updateProgress(),true);
  requestAnimationFrame(()=>{
    const requested=location.hash.slice(1);
    const id=$('original-'+requested)?requested:document.body.dataset.initialBlock;
    updating=true;
    for(const [side,pane] of [['original',left],['proposed',right]]) {
      const block=$(side+'-'+id);
      if(block) {
        const inset=Math.max(0,(pane.clientHeight-block.offsetHeight)/2);
        const maximum=Math.max(0,pane.scrollHeight-pane.clientHeight);
        pane.scrollTop=Math.max(0,Math.min(maximum,top(block,pane)-inset));
      }
    }
    updateProgress();
    requestAnimationFrame(()=>updating=false);
  });
})();
