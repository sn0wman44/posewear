"""Optional full gallery download. Restart safely to continue cached downloads."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'studio'))
import core as c
import shared
import requests
from PIL import Image

def main():
 folder=c.DATA/'gallery-cache';folder.mkdir(exist_ok=True)
 for catalog in ('poses','costumes','anime','portraits','depths'):
  data=json.loads((ROOT/'local-site'/(catalog+'.json')).read_text(encoding='utf-8'))
  if isinstance(data,dict):data=data.get('items',[])
  for row in data:
   for view in row.get('angles',[row]):
    url=view.get('o') or view.get('i') or view.get('m')
    if not url or not url.startswith('https://'):continue
    ident=hashlib.sha256(url.encode()).hexdigest();p=folder/(ident+'.png')
    if p.exists():continue
    try:
     from urllib.parse import urlparse
     if urlparse(url).hostname not in shared.ALLOWED:continue
     r=requests.get(url,timeout=45,stream=True,allow_redirects=False);r.raise_for_status();tmp=p.with_suffix('.part');size=0
     with tmp.open('wb') as f:
      for chunk in r.iter_content(65536):
       size+=len(chunk)
       if size>25*1024*1024:raise ValueError('Image too large')
       f.write(chunk)
     with Image.open(tmp) as im:im.convert('RGB').save(p)
     tmp.unlink(missing_ok=True)
     c.save('assets',dict(id=ident,name=row.get('ti') or row.get('en') or row['id'],role=catalog,prompt=row.get('en',''),source=url,path=c.relative(p),sha256=shared.digest(p),size=p.stat().st_size,mtime=p.stat().st_mtime_ns,key='assets/'+shared.digest(p)+'.png',synced=False,created_at=c.now()))
    except Exception as e:print('Skipped',url,type(e).__name__,flush=True)
  print(catalog,'cached',flush=True)
 print('Finished. Open Shared library and sync to R2.')
if __name__=='__main__':main()
