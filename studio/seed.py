"""Import this chat's real model, product and six generated poses. Idempotent."""
from pathlib import Path
import json
import shutil
import core as c

def seed():
 c.init()
 if c.records('jobs'):return
 source=Path(r'C:/Users/chazb/Documents/Codex/tiktok-product-test/outputs')
 old=Path(r'C:/Users/chazb/Documents/Codex/2026-11-20/i-want/outputs')
 if not (source/'product.json').exists():return
 product=json.loads((source/'product.json').read_text());pid=product['product_id'];folder=c.DATA/'products'/pid;folder.mkdir(exist_ok=True)
 images=[]
 for r in product['images']:
  src=source/r['file'];dst=folder/src.name;shutil.copy2(src,dst)
  images.append({'path':c.relative(dst),'source_url':r['url'],'width':r['dimensions'][0],'height':r['dimensions'][1]})
 c.save('products',{'id':pid,'title':'Black sleeveless tank · white Gothic lettering','url':product['source_url'],'images':images,'extraction_method':'Imported verified gallery from this chat','created_at':c.now()})
 modelfolder=c.DATA/'models'/'default-model';modelfolder.mkdir(exist_ok=True)
 originals=[Path(r'C:/Users/chazb/AppData/Local/Temp/codex-clipboard-83cb809f-a513-4a8d-9990-23b64284e014.png'),old/'green-eye-sweater-front.png']
 refs=[]
 for i,src in enumerate(originals):
  if src.exists():
   dst=modelfolder/f'{i+1:02}.png';shutil.copy2(src,dst);refs.append(c.relative(dst))
 c.save('models',{'id':'default-model','name':'Your model','references':refs,'created_at':c.now()})
 job,_=c.new_job(product['source_url']);job['model_id']='default-model';job['title']='Black tank · six-pose video';job['status']='complete'
 job['garment_notes']='Black sleeveless high round-neck tank with white Gothic lettering in three lines: tattoos / are / trashy. Plain back is inferred from the product front.'
 jobfolder=c.DATA/'jobs'/job['id'];poses=jobfolder/'poses';poses.mkdir(exist_ok=True)
 for i,src in enumerate(sorted((source/'tank-video/images').glob('*.png'))):
  dst=poses/f'{i+1:02}.png';shutil.copy2(src,dst);job['images'][i]=c.relative(dst)
 video=source/'tank-video'/f'black-tank-{pid}.mp4'
 if video.exists():
  dst=jobfolder/'video-imported.mp4';shutil.copy2(video,dst)
  sheet=jobfolder/'poses.jpg';shutil.copy2(source/'tank-video/six-pose-sheet.jpg',sheet)
  job['video']={'path':c.relative(dst),'sheet':c.relative(sheet),'frames':360,'seconds':12,'bytes':dst.stat().st_size,'created_at':c.now()}
  job['exports']=[job['video']]
 job['events']=[{'time':c.now(),'message':'Imported your verified product gallery, model reference and six-pose video from this chat.'}]
 c.save('jobs',job)
 print(f'Imported product {pid} and completed job {job["id"]}.')

if __name__=='__main__':seed()
