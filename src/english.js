// Translate interface text and accessible labels; keep source strings for language switching.
(() => {
 const originals=new WeakMap(),attributes=new WeakMap();let map,pattern,observer;
 const en=()=>window.APP?window.APP.st.lang==='en':JSON.parse(localStorage.getItem('lang')||'"en"')==='en';
 function text(value){return value.replace(pattern,match=>map.get(match));}
 function update(){
  if(!map)return;observer?.disconnect();
  const english=en();document.documentElement.lang=english?'en':'zh-CN';
  const walk=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let node;
  while(node=walk.nextNode()){
   if(node.parentElement.closest('script,style,textarea,[contenteditable]'))continue;
   const saved=originals.get(node);const source=saved&&node.nodeValue===saved.rendered?saved.source:node.nodeValue;
   const rendered=english?text(source):source;
   if(rendered!==node.nodeValue)node.nodeValue=rendered;
   originals.set(node,{source,rendered});
  }
  for(const el of document.querySelectorAll('[title],[aria-label],[placeholder],[alt]')){
   const saved=attributes.get(el)||{};
   for(const key of ['title','aria-label','placeholder','alt']){
    if(!el.hasAttribute(key))continue;
    const current=el.getAttribute(key),old=saved[key],source=old&&old.rendered===current?old.source:current,rendered=english?text(source):source;
    if(rendered!==current)el.setAttribute(key,rendered);saved[key]={source,rendered};
   }attributes.set(el,saved);
  }
  document.title=english?'Product Video Studio':document.title;
  observer.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['title','aria-label','placeholder','alt']});
 }
 Promise.all(['english.tsv','vocabulary.tsv','portrait-english.tsv'].map(url=>fetch('/'+url).then(r=>{if(!r.ok)throw Error('Could not load language resources');return r.text();}))).then(files=>{
  map=new Map(files.flatMap(file=>file.split('\n').filter(line=>line.includes('\t')).map(line=>{const i=line.indexOf('\t');return [line.slice(0,i),line.slice(i+1).trimEnd()];})));
  const escape=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  pattern=new RegExp([...map.keys()].sort((a,b)=>b.length-a.length).map(escape).join('|'),'g');
  observer=new MutationObserver(update);update();
  for(const method of ['alert','confirm','prompt']){
   const native=window[method].bind(window);
   window[method]=(message,...rest)=>native(en()?text(String(message)):message,...rest);
  }
  document.addEventListener('click',e=>{if(e.target.closest('[data-lang]'))setTimeout(update,0);});
  window.StudioLanguage={update,translate:text};
 }).catch(error=>console.error(error));
})();
