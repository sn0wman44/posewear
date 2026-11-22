// Bridge upstream Posewear selections into the existing local studio.
(() => {
 const bar=document.createElement('div');bar.className='studio-links';bar.style.cssText='padding:12px;background:#fff;color:#111;border-bottom:1px solid #ddd';
 bar.innerHTML='<a href="/video-studio">Video Studio</a> · <a href="/library">Shared library & storage</a>';if(!document.querySelector('.studio-links'))document.body.prepend(bar);
 const observer=new MutationObserver(()=>{
  const side=document.querySelector('#lbSide');if(!side||document.querySelector('#share-reference'))return;
  const button=document.createElement('button');button.id='share-reference';button.className='sm pri';button.textContent='Use in Video Studio';side.append(button);
  button.onclick=async()=>{button.disabled=true;try{
   const app=window.APP,it=app.st.list[app.li()];if(!it)throw Error('Select a gallery reference first.');
   if(it.asset_id){location.href='/library?asset='+encodeURIComponent(it.asset_id);return;}
   const state=await fetch('/api/shared').then(r=>r.json());const image=it.angles?it.angles[it.ai||0].o:(it.i||it.m);
   const r=await fetch('/api/shared/import',{method:'POST',headers:{'Content-Type':'application/json','X-Studio-Token':state.token},body:JSON.stringify({url:image,name:app.title(it),prompt:app.prompt(it,'en'),role:it.type})});const data=await r.json();if(!r.ok)throw Error(data.error);location.href='/library';
  }catch(e){alert(e.message);button.disabled=false;}};
 });observer.observe(document.body,{subtree:true,childList:true});
})();
