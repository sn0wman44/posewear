"""Prepare source-video edits without creating pose images or spending credits."""
import json,uuid,shutil
import core as c

def prepare(job,reference_id,resolution='720p'):
 if resolution not in ('480p','720p','1080p'):raise ValueError('Choose 480p, 720p or 1080p.')
 video=c.get('reference_videos',reference_id)
 if not 2<=video['duration']<=30:raise ValueError('Wan 3.0 needs a reference clip between 2 and 30 seconds. Upload a trimmed clip.')
 product=c.get('products',job['product_id']);model=c.get('models',job['model_id'])
 selected=int(job['selected_image'])
 if not model['references'] or not 0<=selected<len(product['images']):raise ValueError('Choose a model and a product image first.')
 if len(model['references'])+1>10:raise ValueError('Wan 3.0 accepts 10 reference images total: up to 9 model photos plus 1 product photo. All photos must fit; none will be silently omitted.')
 run=uuid.uuid4().hex[:12];folder=c.DATA/'jobs'/job['id']/'revana'/run;folder.mkdir(parents=True)
 refs=[]
 # Freeze every saved model photo, followed by the product image in API order.
 for i,source in enumerate(model['references']):
  p=c.local(source);target=folder/f'person-{i+1:02}{p.suffix}';shutil.copy2(p,target);refs.append(c.relative(target))
 p=c.local(product['images'][selected]['path']);target=folder/('product'+p.suffix);shutil.copy2(p,target);garment=c.relative(target)
 source=c.local(video['path']);target=folder/('source'+source.suffix);shutil.copy2(source,target)
 roles={'reference_video_1':'Source motion, timing, camera and background; replace its person and top.','reference_images':[{'index':i+1,'role':'model_identity','path':path} for i,path in enumerate(refs)]+[{'index':len(refs)+1,'role':'featured_product','path':garment}]}
 role_prompt=f'Reference video 1 is the source clip to edit. Reference images 1 through {len(refs)} are ALL identity references for the same replacement model. Use them together for face and body identity only; ignore their outfits, backgrounds, poses and any sheet labels. Reference image {len(refs)+1} is the PRODUCT reference only: reproduce that garment, not the person wearing it. '
 prompt=role_prompt+f'''Edit the supplied reference video, keeping its full original duration, 9:16 framing, camera movement, indoor background, lighting, performance, walking and hand gestures. Replace the single woman's identity with the model in the person-reference photographs: preserve that model's face, freckles, skin tone, long dark hair and bangs. Person references define identity and proportions only; do not copy their clothes, studio backdrop or poses. Replace only the source woman's upper garment with the exact product in the product reference. Product details: {job['garment_notes']} Preserve lettering exactly, with correct spelling, white Gothic font, three-line layout and placement on the front. The new top is sleeveless with a high round neck: remove the source long sleeves and off-shoulder neckline, render natural bare arms and shoulders. Keep the original source jeans and lower-body styling. Keep one person, natural anatomy and consistent identity throughout. Preserve the source clip's existing ootd overlay, with no new captions, product graphics, collage panels or watermarks. Preserve the original motion and timing rather than turning still poses into a slideshow.'''
 request={'run_id':run,'job_id':job['id'],'provider':'revana','model':'wan-3.0','task':'video_edit','status':'needs_mcp_reload','reference_video_id':reference_id,'reference_video_name':video['name'],'duration':video['duration'],'resolution':resolution,'aspect_ratio':'9:16','audio':False,'source_video':c.relative(target),'person_references':refs,'reference_roles':roles,'product_reference':garment,'prompt':prompt,'preserve_original_audio_in_final':False,'created_at':c.now(),'quoted_cost_usd':None,'generation_id':None,'note':'Upload the local source and references with Revana upload_file; quote with the live tool schema before spending. Do not substitute Nemesis, Seedance or another model.'}
 path=folder/'request.json';path.write_text(json.dumps(request,indent=2,ensure_ascii=False),encoding='utf-8')
 job.update(generation_mode='reference_video_edit',reference_video_id=reference_id,video_edit={k:request[k]for k in ('run_id','provider','model','status','reference_video_id','reference_video_name','duration','resolution','created_at')})
 job['video_edit']['request_path']=c.relative(path)
 job.setdefault('events',[]).append({'time':c.now(),'message':f"Prepared Wan 3.0 reference-video edit using {video['name']} ({video['duration']:.2f}s). Awaiting live Revana MCP and price quote. Existing pose video preserved."})
 c.save('jobs',job);return request


def build_remote_args(request,source_url,person_urls,product_url):
 if len(person_urls)!=len(request['person_references']):
  raise ValueError('Upload every saved model reference before quoting or generating.')
 if not source_url or not product_url or not all(person_urls):
  raise ValueError('Source, model and product upload links are required.')
 return {'model':request['model'],'mode':'edit','resolution':request['resolution'],
         'aspect_ratio':request['aspect_ratio'],'audio':False,'prompt':request['prompt'],
         'reference_videos':[source_url],'reference_images':list(person_urls)+[product_url]}
