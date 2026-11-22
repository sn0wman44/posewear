"""Resumable download then verified R2 upload, preserving gallery folders."""
import concurrent.futures as futures
import hashlib,json,re,sys,time,threading,sqlite3
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'studio'))
import core as c
import shared
import requests
from PIL import Image
REPORT=c.DATA/'gallery-transfer.json'
BUCKET='product-video-studio'
S3=None
def safe(s):return re.sub(r'[^A-Za-z0-9_.-]','_',s)
def tasks():
 result={}
 for catalog in ('poses','costumes','anime','portraits','depths'):
  data=json.loads((ROOT/'local-site'/(catalog+'.json')).read_text(encoding='utf-8'))
  for row in data.get('items',[]) if isinstance(data,dict) else data:
   for view in row.get('angles',[row]):
    for kind,url in [('original',view.get('o') or view.get('i') or view.get('m')),('thumbnail',view.get('t'))]:
     if not url or not url.startswith('https://'):continue
     u=urlparse(url)
     if u.hostname not in shared.ALLOWED:raise ValueError('Unexpected source host')
     path=f"galleries/{catalog}/{safe(row['id'])}/{kind}/{safe(Path(u.path).name)}"
     result[url]=dict(url=url,path=path,catalog=catalog,kind=kind,name=row.get('ti') or row.get('en') or row['id'],prompt=row.get('en',''))
 return list(result.values())
def download(t):
 p=c.local(t['path']);p.parent.mkdir(parents=True,exist_ok=True)
 for attempt in range(4):
  try:
   if not p.exists():
    tmp=p.with_suffix(p.suffix+'.part')
    with requests.get(t['url'],timeout=(15,90),stream=True,allow_redirects=False) as r:
     r.raise_for_status();size=0
     with tmp.open('wb') as f:
      for b in r.iter_content(262144):
       size+=len(b)
       if size>50*1024*1024:raise ValueError('Oversized source image')
       f.write(b)
    with Image.open(tmp) as im:im.verify()
    tmp.replace(p)
   sha=shared.digest(p);stat=p.stat()
   a=dict(id=hashlib.sha256(t['url'].encode()).hexdigest(),name=t['name'],role=t['catalog'],prompt=t['prompt'],source=t['url'],path=t['path'],sha256=sha,size=stat.st_size,mtime=stat.st_mtime_ns,key=t['path'],synced=False,created_at=c.now(),gallery_kind=t['kind'])
   try:
    old=c.get('assets',a['id'])
    if old.get('sha256')==sha and old.get('key')==a['key']:a['synced']=old.get('synced',False)
   except ValueError:pass
   c.save('assets',a);return a
  except Exception as exc:
   if attempt==3:return dict(failed=t['url'],error=type(exc).__name__,status=getattr(getattr(exc,'response',None),'status_code',None))
   time.sleep(1+attempt*2)
def upload(a):
 for attempt in range(4):
  try:
   s=S3
   try:head=s.head_object(Bucket=BUCKET,Key=a['key'])
   except Exception:head={}
   if head.get('ContentLength')!=a['size'] or head.get('Metadata',{}).get('sha256')!=a['sha256']:
    s.upload_file(str(c.local(a['path'])),BUCKET,a['key'],ExtraArgs={'Metadata':{'sha256':a['sha256']}})
    head=s.head_object(Bucket=BUCKET,Key=a['key'])
   if head['ContentLength']!=a['size'] or head.get('Metadata',{}).get('sha256')!=a['sha256']:raise ValueError('Verification failed')
   a['synced']=True;c.save('assets',a);return a
  except Exception as exc:
   if attempt==3:return dict(failed=a['key'],error=type(exc).__name__)
   time.sleep(attempt*2+1)
def phase(label,fn,items,workers):
 rows=[];start=time.monotonic()
 with futures.ThreadPoolExecutor(max_workers=workers) as pool:
  for n,r in enumerate(pool.map(fn,items),1):
   rows.append(r)
   if n%100==0 or n==len(items):
    status=dict(phase=label,completed=n,total=len(items),failed=sum('failed' in x for x in rows),seconds=round(time.monotonic()-start))
    REPORT.write_text(json.dumps(status));print(json.dumps(status),flush=True)
 return rows
def main():
 global S3
 s=S3=shared.client();s.head_bucket(Bucket=BUCKET)
 all_tasks=tasks();print('Planned image files:',len(all_tasks),flush=True)
 downloaded=([a for a in c.records('assets') if a['path'].startswith('galleries/')] if '--upload-only' in sys.argv else phase('download',download,all_tasks,4))
 if '--upload-only' in sys.argv and len(downloaded)!=len(all_tasks):raise ValueError('Local catalog incomplete; run the download phase first.')
 failures=[x for x in downloaded if 'failed' in x];assets=[x for x in downloaded if 'failed' not in x]
 (c.DATA/'gallery-sources.json').write_text(json.dumps({a['source']:a['path'] for a in assets}))
 result=phase('upload',upload,assets,16);failures.extend(x for x in result if 'failed' in x)
 verified=[a for a in result if 'failed' not in a]
 counts={}
 for a in verified:
  entry=counts.setdefault(a['role'],dict(originals=0,thumbnails=0,bytes=0));entry[a['gallery_kind']+'s']+=1;entry['bytes']+=a['size']
 for p in (ROOT/'local-site').glob('*.json'):s.upload_file(str(p),BUCKET,'catalogs/'+p.name)
 for p in [ROOT/'LICENSE',ROOT/'README.en.md']:s.upload_file(str(p),BUCKET,'attribution/'+p.name)
 manifest=c.DATA/'gallery-manifest.json';manifest.write_text(json.dumps(assets,ensure_ascii=False),encoding='utf-8');s.upload_file(str(manifest),BUCKET,'catalogs/gallery-manifest.json')
 s.put_object(Bucket=BUCKET,Key='library.json',Body=json.dumps(c.records('assets')).encode(),ContentType='application/json')
 backup=c.DATA/'backups/gallery-transfer.sqlite';backup.parent.mkdir(exist_ok=True)
 with c.connect() as src,sqlite3.connect(backup) as dest:src.backup(dest)
 s.upload_file(str(backup),BUCKET,'backups/gallery-transfer.sqlite')
 report=dict(phase='complete' if not failures else 'partial',planned=len(all_tasks),downloaded=len(assets),verified=len(verified),galleries=counts,failures=failures)
 REPORT.write_text(json.dumps(report,indent=2));s.upload_file(str(REPORT),BUCKET,'catalogs/transfer-report.json');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
