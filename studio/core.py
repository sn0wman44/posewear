"""Local storage, TikTok extraction and deterministic image-video rendering."""
from __future__ import annotations
import collections
import html
import json
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import imageio_ffmpeg
from PIL import Image, ImageOps, ImageDraw

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('STUDIO_DATA_DIR', str(ROOT / 'data'))).resolve()
LOCK = threading.RLock()
POSES = [
 ('Front hero', 'Front three-quarter hero with only a slight torso turn, face toward camera, gentle head tilt, weight on back leg, soft front knee and a small foot offset.'),
 ('Side', 'Left-facing side view, torso and hips side-on; head comfortably turned toward camera, feet staggered half a shoe length, soft near knee.'),
 ('Rear look-back', 'Rear three-quarter view turned toward image left; look naturally back over the near shoulder toward camera, face visible; asymmetric weight and relaxed near knee.'),
 ('Back', 'Straight back view, head facing away and no face visible, hair over one shoulder to reveal garment; feet hip width, small heel offset, relaxed arms.'),
 ('Opposite rear', 'Opposite rear three-quarter view turned toward image right; natural look over the opposite shoulder toward camera; weight on opposite leg, near knee soft and feet slightly staggered.'),
 ('Opposite side', 'Right-facing side view, torso and hips side-on; face comfortably turned toward camera, rear leg bearing weight, near foot a few inches forward.'),
]

def now(): return datetime.now(timezone.utc).isoformat()

def init():
 DATA.mkdir(exist_ok=True)
 for name in ('jobs', 'products', 'models', 'wardrobe'): (DATA / name).mkdir(exist_ok=True)
 with connect() as db:
  db.execute('CREATE TABLE IF NOT EXISTS records(kind TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(kind,id))')
 # Busy tasks cannot survive a process restart. Keep remote task IDs for recovery.
 for j in records('jobs'):
  if j['status'] in ('extracting','preparing','generating','rendering'):
   j['status']='interrupted'; j['error']='App restarted. Review the saved job and resume; existing remote task IDs are preserved.'; save('jobs',j)

def connect():
 db=sqlite3.connect(DATA/'studio.sqlite',timeout=20)
 db.execute('PRAGMA journal_mode=WAL')
 return db

def save(kind, obj):
 with LOCK, connect() as db:
  obj['updated_at']=now()
  db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?)',(kind,obj['id'],json.dumps(obj)))
 return obj

def get(kind, ident):
 with connect() as db: row=db.execute('SELECT body FROM records WHERE kind=? AND id=?',(kind,ident)).fetchone()
 if not row: raise ValueError(f'{kind.rstrip("s").capitalize()} not found.')
 return json.loads(row[0])

def records(kind):
 with connect() as db: rows=db.execute('SELECT body FROM records WHERE kind=?',(kind,)).fetchall()
 return sorted([json.loads(r[0]) for r in rows],key=lambda x:x.get('created_at',x.get('updated_at','')),reverse=True)

def settings():
 try: return get('settings','main')
 except ValueError: return {'id':'main','channel_id':'','discord_enabled':False,'discord_post_results':False}

def local(path):
 p=Path(path)
 if not p.is_absolute():p=DATA/p
 p=p.resolve(); p.relative_to(DATA.resolve()); return p

def relative(path): return Path(path).resolve().relative_to(DATA.resolve()).as_posix()

def asset_url(path): return '/media/'+path if path else None

def product_id(url):
 parsed=urlparse(url)
 if parsed.scheme!='https' or parsed.hostname!='shop.tiktok.com' or parsed.port not in (None,443):
  raise ValueError('Use a full https://shop.tiktok.com/.../pdp/... product link.')
 match=re.search(r'/pdp/(?:[^/]+/)?(\d{15,25})/?$',parsed.path)
 if not match: raise ValueError('Could not find a product ID in that link. Open the product and copy its full Shop URL.')
 return match[1]

def run_curl(url,target):
 subprocess.run(['curl.exe' if os.name=='nt' else 'curl','--fail','--silent','--show-error','--location','--max-redirs','3','--proto','=https','--proto-redir','=https','--max-time','60','--max-filesize','25000000','-A','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',url,'-o',str(target)],capture_output=True,check=True,timeout=70,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

def extract_candidates(source):
 """Prefer Product JSON-LD; use gallery-size CDN URLs as bounded fallback."""
 text=html.unescape(source).replace('\\u002F','/').replace('\\/','/')
 title=re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)',text,re.I)
 if not title: title=re.search(r'<title[^>]*>(.*?)</title>',text,re.S|re.I)
 urls=[]; method='gallery URL pattern; verify images before generation'
 for script in re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',source,re.S|re.I):
  try:
   tree=json.loads(html.unescape(script))
   def walk(x):
    if isinstance(x,dict):
     typ=x.get('@type','')
     if typ=='Product' or (isinstance(typ,list) and 'Product' in typ):
      imgs=x.get('image',[])
      if isinstance(imgs,str): imgs=[imgs]
      for a in imgs:
       if isinstance(a,str): urls.append(a)
       elif isinstance(a,dict) and a.get('url'): urls.append(a['url'])
     for v in x.values(): walk(v)
    elif isinstance(x,list):
     for v in x: walk(v)
   walk(tree)
  except (ValueError,TypeError): pass
 if urls: method='Product structured data'
 else:
  found=re.findall(r'https?://[^\s"<>\\]+',text)
  urls=[u for u in found if re.search(r'(?:resize|crop)-webp:800:800\.webp',u)]
  if not urls:
   tag=re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)',text,re.I)
   if tag: urls=[tag[1]]; method='Open Graph preview only'
 result=[];seen=set()
 for u in urls:
  host=urlparse(u).hostname or ''
  if not (host.endswith('.ttcdn-us.com') or host.endswith('.tiktokcdn.com') or host.endswith('.ibytedtos.com') or host.endswith('.tiktokcdn-us.com')): continue
  ident=re.search(r'/([a-f0-9]{32})(?:~|\?)',u)
  key=ident[1] if ident else u.split('?')[0]
  if key in seen:continue
  seen.add(key); result.append({'source_url':u,'large_url':re.sub(r'(?:resize|crop)-webp:800:800\.webp','crop-jpeg:1800:1800.jpeg',u),'image_id':key})
 return {'title':html.unescape(title[1]).strip() if title else 'TikTok Shop product','method':method,'images':result[:24]}

def extract_product(url):
 ident=product_id(url)
 try:
  old=get('products',ident)
  if old.get('images'): return old
 except ValueError: pass
 folder=DATA/'products'/ident; folder.mkdir(exist_ok=True)
 canonical=url.split('?')[0].split('#')[0]; run_curl(canonical,folder/'page.html')
 parsed=extract_candidates((folder/'page.html').read_text(encoding='utf-8',errors='replace'))
 images=[]
 for i,record in enumerate(parsed['images']):
  target=folder/f'{i+1:02d}.jpg'
  try:
   try:run_curl(record['large_url'],target)
   except subprocess.CalledProcessError:run_curl(record['source_url'],target)
   with Image.open(target) as im:
    im.load();size=im.size;ImageOps.exif_transpose(im).convert('RGB').save(target,quality=95)
   images.append(dict(record,path=relative(target),width=size[0],height=size[1]))
  except (OSError,subprocess.SubprocessError): continue
 if not images: raise ValueError('TikTok returned no usable product gallery. Upload product images below, or retry later.')
 return save('products',{'id':ident,'url':canonical,'title':parsed['title'],'images':images,'extraction_method':parsed['method'],'created_at':now()})

def new_job(url,source='local'):
 ident=product_id(url)
 for job in records('jobs'):
  if job.get('product_id')==ident and job['status'] not in ('complete','error','interrupted'): return job,False
 models=records('models')
 job={'id':uuid.uuid4().hex[:12],'product_id':ident,'url':url,'title':'Extracting product…','status':'queued','source':source,'created_at':now(),'model_id':models[0]['id'] if models else None,'selected_image':0,'images':[None]*6,'prompts':[], 'render':{'fps':30,'hold_frames':15,'repeats':4,'width':1080,'height':1920},'styling':'Charcoal-black flared jeans and simple black shoes. No accessories.','garment_notes':'Match selected product color, print, cut, neckline and hem. Plain back is inferred unless references show otherwise.','events':[]}
 save('jobs',job);(DATA/'jobs'/job['id']).mkdir(exist_ok=True);return job,True

def prompt_for(job,index):
 import wardrobe
 outfit_notes=wardrobe.instruction(job)
 return f'''Create ONE standalone full-body 9:16 realistic clothing-model studio photograph. References are explicitly labeled featured garment, optional companion garment, and model identity in handoff.json. Use model photos for identity only, never their clothing. Preserve recognizable face, freckles, skin tone, hairstyle and natural body proportions. Garment: {job['garment_notes']} Complementary styling: {job['styling']}{outfit_notes} Pose: {POSES[index][1]} Pure white background and floor, soft even neutral lighting, tiny shoe contact shadow. Full head and both shoes uncropped, top of head at 3% frame and shoes at 97%, centered, fixed level camera and consistent scale. Natural hands and anatomy. Preserve exact spelling, font and placement of garment lettering; print belongs only on the referenced garment surface. No text overlays, borders, collage, watermarks or extra people. Natural professional fashion pose.'''

def render_video(job):
 config=job['render']; fps=int(config['fps']);hold=int(config['hold_frames']);repeats=int(config['repeats'])
 if not 1<=repeats<=10 or not 6<=hold<=60 or fps!=30:raise ValueError('Use 30 fps, 6–60 frames per pose, and 1–10 repeats.')
 if len(job.get('images',[]))!=6 or not all(job['images']):raise ValueError('Add all six pose images before rendering.')
 folder=DATA/'jobs'/job['id']; normalized=folder/'normalized';normalized.mkdir(exist_ok=True)
 width,height=1080,1920; images=[]
 for i,p in enumerate(job['images']):
  with Image.open(local(p)) as source: im=ImageOps.exif_transpose(source).convert('RGB')
  im.thumbnail((width,height),Image.Resampling.LANCZOS)
  canvas=Image.new('RGB',(width,height),'white');canvas.paste(im,((width-im.width)//2,(height-im.height)//2))
  canvas.save(normalized/f'{i+1:02d}.jpg',quality=95);images.append(canvas)
 seq=list(range(6))*repeats;total=len(seq)*hold
 manifest={'job_id':job['id'],'product_id':job['product_id'],'fps':fps,'width':width,'height':height,'frames':total,'seconds':total/fps,'shots':[{'pose':n,'image':job['images'][n],'start_frame':i*hold,'duration_frames':hold}for i,n in enumerate(seq)],'source':job['url'],'notes':job['garment_notes'],'outfit':job.get('outfit')}
 (folder/'timeline.json').write_text(json.dumps(manifest,indent=2))
 # Version exports so a browser preview is never replaced under an active read.
 stamp=datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:4];target=folder/f'video-{stamp}.mp4'
 with (folder/'render.log').open('wb') as log:
  proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}','-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(target)],stdin=subprocess.PIPE,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  try:
   for n in seq:
    raw=images[n].tobytes()
    for _ in range(hold):proc.stdin.write(raw)
   proc.stdin.close()
   if proc.wait(timeout=180)!=0: raise ValueError('Video encoder failed. See the job render.log.')
  except BaseException:
   proc.kill();proc.wait();raise
 validation=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-i',str(target),'-f','null','-'],capture_output=True,text=True,timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 counts=re.findall(r'frame=\s*(\d+)',validation.stderr)
 if validation.returncode or not counts or int(counts[-1])!=total:raise ValueError('Rendered video did not pass frame-count validation.')
 (folder/'validation.txt').write_text(validation.stderr)
 sheet=Image.new('RGB',(1200,400),'white');draw=ImageDraw.Draw(sheet)
 for i,im in enumerate(images):
  thumb=im.copy();thumb.thumbnail((195,350));sheet.paste(thumb,(i*200,25));draw.text((i*200+3,5),POSES[i][0],fill='black')
 sheet.save(folder/'poses.jpg');return {'path':relative(target),'sheet':relative(folder/'poses.jpg'),'frames':total,'seconds':total/fps,'bytes':target.stat().st_size,'created_at':now(),'outfit':job.get('outfit')}
