"""Shared asset catalog, frozen references and private R2 synchronization."""
import hashlib, json, os, shutil, sqlite3, threading, time, uuid
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image
from flask import request, jsonify, send_from_directory, send_file
import core as c

ROOT=Path(__file__).resolve().parent.parent
ALLOWED={'ai-pose-gallery.pages.dev','ai-costume-gallery.pages.dev','ai-costume-anime-gallery.pages.dev','ai-portrait-gallery.pages.dev','ai-pose-depth-gallery.pages.dev'}
SYNC={'running':False,'error':None,'uploaded':0}; GUARD=threading.Lock()
SOURCE_CACHE={'mtime':None,'paths':{}}
def cached_source(url):
 index=c.DATA/'gallery-sources.json'
 if not index.exists():return None
 stamp=index.stat().st_mtime_ns
 if SOURCE_CACHE['mtime']!=stamp:
  SOURCE_CACHE.update(mtime=stamp,paths=json.loads(index.read_text()))
 relative=SOURCE_CACHE['paths'].get(url)
 if relative:
  p=c.local(relative)
  if p.is_file():return p
def config():
 p=c.ROOT/'storage-private.json'
 return json.loads(p.read_text()) if p.exists() else {}
def client():
 import boto3
 from botocore.config import Config
 v=config()
 if not v.get('access_key') or not v.get('secret_key'):raise ValueError('Configure R2 credentials in Storage settings first.')
 return boto3.client('s3',endpoint_url='https://0ebe9972b1b37d1975a18feb6f790fc0.r2.cloudflarestorage.com',aws_access_key_id=v['access_key'],aws_secret_access_key=v['secret_key'],region_name='auto',config=Config(max_pool_connections=32))
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def index_files():
 existing={r['path']:r for r in c.records('assets')}
 for p in c.DATA.rglob('*'):
  if not p.is_file() or p.is_symlink() or p.suffix.lower() not in ('.png','.jpg','.jpeg','.webp','.mp4','.mov','.webm','.zip'):continue
  path=c.relative(p); old=existing.get(path)
  if old and old.get('size')==p.stat().st_size and old.get('mtime')==p.stat().st_mtime_ns:continue
  sha=digest(p); c.save('assets',dict(old or {},id=(old or {}).get('id',uuid.uuid4().hex),name=(old or {}).get('name',p.name),path=path,sha256=sha,size=p.stat().st_size,mtime=p.stat().st_mtime_ns,key=path if path.startswith('galleries/') else 'assets/'+sha+p.suffix.lower(),synced=False,created_at=c.now()))
def ensure(asset):
 p=c.local(asset['path'])
 if p.exists():return p
 p.parent.mkdir(parents=True,exist_ok=True); temp=p.with_suffix(p.suffix+'.part')
 try:
  client().download_file('product-video-studio',asset['key'],str(temp))
  if digest(temp)!=asset['sha256']:raise ValueError('Downloaded asset checksum mismatch.')
  temp.replace(p)
 finally:temp.unlink(missing_ok=True)
 return p
def freeze(job):
 result=[]
 for ident in job.get('shared_assets',[]):
  a=c.get('assets',ident); source=ensure(a); target=c.DATA/'jobs'/job['id']/'shared'/a['sha256']/source.name
  target.parent.mkdir(parents=True,exist_ok=True)
  if not target.exists():shutil.copy2(source,target)
  role={'poses':'pose','depths':'depth','costumes':'costume','portraits':'portrait'}.get(a.get('role'),a.get('role','reference'))
  result.append(dict(id=ident,path=str(target),role=role,prompt=a.get('prompt',''),source=a.get('source','')))
 return result
def synchronize():
 with GUARD:
  if SYNC['running']:return
  SYNC.update(running=True,error=None,uploaded=0)
 try:
  s=client();index_files()
  for a in c.records('assets'):
   if a.get('synced'):continue
   p=c.local(a['path'])
   if not p.exists():continue
   for attempt in range(3):
    try:
     s.upload_file(str(p),'product-video-studio',a['key'],ExtraArgs={'Metadata':{'sha256':a['sha256']}})
     head=s.head_object(Bucket='product-video-studio',Key=a['key'])
     if head['ContentLength']!=a['size'] or head.get('Metadata',{}).get('sha256')!=a['sha256']:raise ValueError('Upload verification failed.')
     a['synced']=True;c.save('assets',a);SYNC['uploaded']+=1;break
    except Exception:
     if attempt==2:raise
     time.sleep(attempt+1)
  backup=c.DATA/'backups';backup.mkdir(exist_ok=True)
  with c.connect() as source,sqlite3.connect(backup/'studio.sqlite') as target:source.backup(target)
  s.upload_file(str(backup/'studio.sqlite'),'product-video-studio','backups/studio.sqlite')
  manifest=json.dumps(c.records('assets')).encode();s.put_object(Bucket='product-video-studio',Key='library.json',Body=manifest,ContentType='application/json')
 except Exception as exc:SYNC['error']=type(exc).__name__+': check storage settings and connection.'
 finally:SYNC['running']=False

def start_auto_sync():
 def loop():
  while True:
   if config().get('secret_key'):synchronize()
   time.sleep(60)
 threading.Thread(target=loop,daemon=True).start()
def register(app,token):
 @app.get('/reference-image')
 def reference_image():
  url=request.args.get('url','');u=urlparse(url)
  if u.scheme!='https' or u.hostname not in ALLOWED or u.port not in (None,443):raise ValueError('Unsupported image source.')
  cached=cached_source(url)
  if cached:return send_file(cached,conditional=True)
  folder=c.DATA/'previews';folder.mkdir(exist_ok=True);p=folder/(hashlib.sha256(url.encode()).hexdigest()+'.png')
  if not p.exists():
   import io
   with requests.get(url,stream=True,timeout=30,allow_redirects=False) as r:
    r.raise_for_status();content=bytearray()
    for chunk in r.iter_content(65536):
     content.extend(chunk)
     if len(content)>25*1024*1024:raise ValueError('Image too large.')
   with Image.open(io.BytesIO(content)) as im:
    temp=folder/(uuid.uuid4().hex+'.tmp');im.convert('RGB').save(temp,format='PNG');temp.replace(p)
  return send_file(p,conditional=True)
 @app.get('/video-studio')
 def video_page():return app.send_static_file('index.html')
 @app.get('/library')
 def library_page():return send_from_directory(ROOT/'integration','library.html')
 @app.get('/integration.js')
 def integration_js():return send_from_directory(ROOT/'integration','integration.js')
 @app.get('/library.js')
 def library_js():return send_from_directory(ROOT/'integration','library.js')
 @app.get('/api/shared')
 def listing():
  index_files();v=config()
  return jsonify(assets=c.records('assets'),jobs=c.records('jobs'),sync=SYNC,configured=bool(v.get('secret_key')),folder=str(c.DATA),bucket='product-video-studio',token=token)
 @app.post('/api/shared/storage')
 def storage():
  body=request.get_json();v=config()
  for k in ('access_key','secret_key'):
   if body.get(k):v[k]=str(body[k]).strip()
  (c.ROOT/'storage-private.json').write_text(json.dumps(v));return jsonify(ok=True)
 @app.post('/api/shared/sync')
 def shared_sync():
  if not config().get('secret_key'):raise ValueError('Configure R2 credentials first.')
  threading.Thread(target=synchronize,daemon=True).start();return jsonify(ok=True)
 @app.post('/api/shared/restore')
 def restore():
  rows=json.loads(client().get_object(Bucket='product-video-studio',Key='library.json')['Body'].read())
  for a in rows:
   c.local(a['path'])
   try:c.get('assets',a['id'])
   except ValueError:c.save('assets',a)
  return jsonify(ok=True)
 @app.post('/api/shared/<ident>/offline')
 def offline(ident):ensure(c.get('assets',ident));return jsonify(ok=True)
 @app.post('/api/shared/<ident>/attach')
 def attach(ident):
  a=c.get('assets',ident);body=request.get_json();job=c.get('jobs',body['job_id']);ensure(a)

  if a.get('role')=='portrait':
   candidates=[m for m in c.records('models') if a['path'] in m.get('references',[])]
   if candidates:job['model_id']=candidates[0]['id']
  if a.get('role') in ('costume','anime'):
   candidates=[w for w in c.records('wardrobe') if a['path'] in w.get('images',[])]
   if candidates:job.update(outfit_mode='manual',companion_id=candidates[0]['id'])
  job['shared_assets']=list(dict.fromkeys(job.get('shared_assets',[])+[ident]));c.save('jobs',job)
  return jsonify(ok=True)
 @app.post('/api/shared/import')
 def import_asset():
  body=request.get_json();url=body['url'];u=urlparse(url)
  if u.scheme!='https' or u.hostname not in ALLOWED or u.port not in (None,443):raise ValueError('Unsupported reference image host.')
  ident=uuid.uuid4().hex;folder=c.DATA/'shared';folder.mkdir(exist_ok=True);temp=folder/(ident+'.part');target=folder/(ident+'.png')
  try:
   with requests.get(url,stream=True,timeout=30,allow_redirects=False) as response:
    response.raise_for_status();size=0
    with temp.open('wb') as f:
     for chunk in response.iter_content(65536):
      size+=len(chunk)
      if size>25*1024*1024:raise ValueError('Image exceeds 25 MB.')
      f.write(chunk)
   with Image.open(temp) as image:image.convert('RGB').save(target)
  finally:temp.unlink(missing_ok=True)
  index_files();a=next(a for a in c.records('assets') if a['path']==c.relative(target));a.update(name=str(body.get('name','Reference'))[:200],prompt=str(body.get('prompt',''))[:4000],role=body.get('role','reference'),source=url);c.save('assets',a)
  if a['role']=='portrait':c.save('models',dict(id=ident,name=a['name'],references=[a['path']],created_at=c.now()))
  if a['role'] in ('costume','anime'):
   import wardrobe as w
   item=w.clean(dict(name=a['name'],notes=a['prompt'],category='unknown',reusable=True));item.update(id=ident,images=[a['path']],source='posewear',created_at=c.now());c.save('wardrobe',item)
  return jsonify(asset=a)
