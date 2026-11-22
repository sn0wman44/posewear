"""Import a local background-reference folder into Scenes and private R2."""
import concurrent.futures,json,hashlib,shutil,sys,time
from pathlib import Path
from PIL import Image,ImageOps
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'studio'))
import core as c
import shared

def import_folder(source,folder='liminal'):
 source=Path(source).resolve();catalog=[];assets=[];failures=[]
 files=sorted(p for p in source.rglob('*') if p.is_file())
 for source_file in files:
  try:
   with Image.open(source_file) as im:im.verify()
   relative=source_file.relative_to(source).as_posix()
   path=f'galleries/scenes/{folder}/original/{relative}';target=c.local(path);target.parent.mkdir(parents=True,exist_ok=True)
   if not target.exists() or shared.digest(target)!=shared.digest(source_file):shutil.copy2(source_file,target)
   ident=hashlib.sha256(('scene/'+folder+'/'+relative).encode()).hexdigest()
   thumb=c.local(f'galleries/scenes/{folder}/thumbnail/{ident[:16]}.webp');thumb.parent.mkdir(parents=True,exist_ok=True)
   with Image.open(target) as im:
    width,height=im.size
    if not thumb.exists():
     image=ImageOps.exif_transpose(im).convert('RGB');image.thumbnail((640,640));image.save(thumb,format='WEBP',quality=85)
   name=source_file.stem.replace('-',' ').title()
   prompt='Use this image as a liminal-space background and environment reference only. Preserve the setting, composition, architecture, perspective, lighting and atmosphere. Do not use any person in the reference as an identity or clothing reference.'
   for kind,p in [('original',target),('thumbnail',thumb)]:
    aid=ident if kind=='original' else ident+'-thumbnail';sha=shared.digest(p)
    a=dict(id=aid,name=name if kind=='original' else name+' thumbnail',role='scene',reference_role='background',folder=folder,gallery_kind=kind,path=c.relative(p),key=c.relative(p),sha256=sha,size=p.stat().st_size,mtime=p.stat().st_mtime_ns,source=str(source_file),prompt=prompt,synced=False,created_at=c.now())
    c.save('assets',a);assets.append(a)
   original='/media/'+c.relative(target);preview='/media/'+c.relative(thumb)
   catalog.append(dict(id=folder+'-'+ident[:16],asset_id=ident,ti=name,nameEn=name,zh=prompt,en=prompt,cat=folder.title(),catEn=folder.title(),folder=folder,reference_role='background',kw='liminal space background environment reference',t=preview,m=original,i=original,o=original,ext=1,w=width,h=height,credit='User-uploaded background reference'))
  except Exception as exc:failures.append(dict(file=str(source_file),error=type(exc).__name__))
 if failures:raise ValueError(json.dumps(failures))
 destination=c.DATA/'custom-catalogs/scenes'/f'{folder}.json';destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(dict(imported=len(catalog),files=len(assets),bytes=sum(a['size'] for a in assets))),flush=True)
 s=shared.client()
 def upload(a):
  for attempt in range(3):
   try:
    s.upload_file(str(c.local(a['path'])),'product-video-studio',a['key'],ExtraArgs={'Metadata':{'sha256':a['sha256'],'reference-role':'background'}})
    head=s.head_object(Bucket='product-video-studio',Key=a['key'])
    if head['ContentLength']!=a['size'] or head.get('Metadata',{}).get('sha256')!=a['sha256']:raise ValueError('Verification failed')
    a['synced']=True;c.save('assets',a);return
   except Exception:
    if attempt==2:raise
    time.sleep(attempt+1)
 with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
  for n,_ in enumerate(pool.map(upload,assets),1):
   if n%100==0 or n==len(assets):print('R2 verified',n,'/',len(assets),flush=True)
 s.upload_file(str(destination),'product-video-studio',f'catalogs/scenes/{folder}.json')
 import local_build
 local_build.build()
 s.upload_file(str(ROOT/'local-site/scenes.json'),'product-video-studio','catalogs/scenes.json')
 s.put_object(Bucket='product-video-studio',Key='library.json',Body=json.dumps(c.records('assets')).encode(),ContentType='application/json')
 report=dict(source=str(source),scenes=len(catalog),verified_files=len(assets),bytes=sum(a['size'] for a in assets),r2_prefix=f'galleries/scenes/{folder}/',failures=failures)
 (c.DATA/f'{folder}-import-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
if __name__=='__main__':import_folder(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else 'liminal')
