"""Reusable local garments, explainable outfit matching and frozen job references."""
import hashlib
import json
import re
import shutil
import uuid
import core as c

CATEGORIES=('tops','bottoms','dresses','outerwear','shoes','accessories','unknown')
COLORS=('unknown','black','white','gray','cream','beige','brown','navy','blue','green','red','pink','purple','yellow','orange','multicolor')
NEUTRALS={'black','white','gray','cream','beige','navy','brown'}

def infer_category(title):
 text=title.lower()
 for category,pattern in [('dresses',r'\b(dress|jumpsuit|romper)\b'),('outerwear',r'\b(jacket|coat|blazer|cardigan)\b'),('bottoms',r'\b(jeans|pants|trousers|skirt|shorts|leggings|bottoms)\b'),('tops',r'\b(top|tops|tank|cami|shirt|sweater|hoodie|blouse|halter)\b'),('shoes',r'\b(shoes|boots|sneakers|sandals)\b')]:
  if re.search(pattern,text):return category
 return 'unknown'

def clean(body,old=None):
 item=dict(old or {})
 for key,limit in [('name',160),('notes',2500)]:item[key]=str(body.get(key,item.get(key,''))).strip()[:limit]
 if not item['name']:raise ValueError('Give this garment a name.')
 item['category']=body.get('category',item.get('category','unknown'))
 item['color']=body.get('color',item.get('color','unknown'))
 if item['category'] not in CATEGORIES or item['color'] not in COLORS:raise ValueError('Choose a valid category and color.')
 tags=body.get('tags',item.get('tags',[]))
 if isinstance(tags,str):tags=tags.split(',')
 if not isinstance(tags,list):raise ValueError('Style tags must be comma-separated text.')
 item['tags']=list(dict.fromkeys(str(t).strip().lower()[:40] for t in tags if str(t).strip()))[:20]
 item['reusable']=body.get('reusable',item.get('reusable',False)) in (True,'true','on','1')
 item['selected_image']=int(body.get('selected_image',item.get('selected_image',0)))
 if item.get('images') and not 0<=item['selected_image']<len(item['images']):raise ValueError('Choose a valid reference image.')
 return item

def ensure_product(product,index=0):
 if not product.get('images'):return None
 if not 0<=index<len(product['images']):raise ValueError('Product variant not found.')
 path=product['images'][index]['path']
 ident='product-'+hashlib.sha256((product['id']+'|'+path).encode()).hexdigest()[:16]
 try:return c.get('wardrobe',ident)
 except ValueError:pass
 return c.save('wardrobe',{'id':ident,'name':product.get('title','Product')+f' · image {index+1}','category':infer_category(product.get('title','')),'color':'unknown','tags':[],'notes':'Verify the garment and selected color before enabling reuse.','reusable':False,'selected_image':0,'images':[path],'source':'tiktok','product_id':product['id'],'product_image_index':index,'url':product.get('url',''),'created_at':c.now()})

def migrate():
 # Preserve one entry per selected variant, including historical jobs.
 for p in c.records('products'):
  indices={0}|{j.get('selected_image',0) for j in c.records('jobs') if j.get('product_id')==p['id']}
  for i in indices:
   if i<len(p.get('images',[])):ensure_product(p,i)

def featured(job):
 return ensure_product(c.get('products',job['product_id']),int(job.get('selected_image',0)))

def ranked(job):
 main=featured(job);category=job.get('featured_category') or main['category']
 target={'tops':'bottoms','bottoms':'tops'}.get(category)
 if not target:return []
 result=[]
 for item in c.records('wardrobe'):
  if not item.get('reusable') or item['category']!=target or item.get('product_id')==job['product_id'] or not item.get('images'):continue
  if not all(c.local(p).is_file() for p in item['images']):continue
  score=0;reasons=[]
  shared=set(main.get('tags',[]))&set(item.get('tags',[]))
  if shared:score+=len(shared)*4;reasons.append('shared style: '+', '.join(sorted(shared)))
  if item.get('color') in NEUTRALS:score+=3;reasons.append('versatile neutral color')
  if 'solid' in item.get('tags',[]):score+=2;reasons.append('solid garment keeps focus on featured product')
  if main.get('color') not in ('unknown',None) and item.get('color')==main['color']:score+=1;reasons.append('tonal pairing')
  result.append({'item':item,'score':score,'reason':'; '.join(reasons) or 'compatible garment category; inspect the images for styling'})
 return sorted(result,key=lambda r:(-r['score'],r['item']['id']))

def choose(job):
 mode=job.get('outfit_mode','auto')
 if mode=='none':return None,'No saved companion requested.'
 if mode=='manual':
  item=c.get('wardrobe',job.get('companion_id',''))
  main=featured(job);target={'tops':'bottoms','bottoms':'tops'}.get(job.get('featured_category') or main['category'])
  if not item.get('reusable') or item['category']!=target or item.get('product_id')==job['product_id']:raise ValueError('Choose a reusable garment from the complementary category.')
  return item,'Manually selected.'
 candidates=ranked(job)
 return (candidates[0]['item'],candidates[0]['reason']) if candidates else (None,'No reusable complementary garment found. Use the styling notes or add wardrobe items.')

def snapshot(job):
 main=featured(job);companion,reason=choose(job)
 parts=[]
 for role,item in [('featured',main),('companion',companion)]:
  if not item:continue
  # Featured references use exactly the selected product image; companions may have several garment views.
  images=item['images']
  if role=='companion':images=[images[item.get('selected_image',0)]]+[p for i,p in enumerate(images) if i!=item.get('selected_image',0)]
  parts.append({'role':role,'item_id':item['id'],'name':item['name'],'category':job.get('featured_category') or item['category'] if role=='featured' else item['category'],'color':item['color'],'tags':item['tags'],'notes':item['notes'],'source':item['source'],'product_id':item.get('product_id'),'original_images':images,'image_digests':[hashlib.sha256(c.local(p).read_bytes()).hexdigest() for p in images]})
 fingerprint=hashlib.sha256(json.dumps(parts,sort_keys=True).encode()).hexdigest()[:16]
 if job.get('outfit',{}).get('fingerprint')==fingerprint:return job['outfit']
 folder=c.DATA/'jobs'/job['id']/'outfits'/fingerprint;folder.mkdir(parents=True,exist_ok=True)
 for part in parts:
  refs=[]
  for i,p in enumerate(part['original_images']):
   source=c.local(p);dest=folder/f"{part['role']}-{i+1:02}{source.suffix}"
   shutil.copy2(source,dest);refs.append(c.relative(dest))
  part['references']=refs
 return {'fingerprint':fingerprint,'created_at':c.now(),'reason':reason,'parts':parts}

def invalidate(job):
 folder=c.DATA/'jobs'/job['id'];source=folder/'poses'
 if source.exists():source.rename(folder/('poses-previous-'+uuid.uuid4().hex[:8]))
 job['images']=[None]*6;job['prompts']=[];job['status']='ready'
 if job.get('video'):job['video']['stale']=True
 job.setdefault('events',[]).append({'time':c.now(),'message':'Outfit or reference changed. Previous poses preserved; generate six new poses.'})

def instruction(job):
 outfit=job.get('outfit')
 if not outfit:return ''
 companion=next((p for p in outfit['parts'] if p['role']=='companion'),None)
 if not companion:return ' No saved companion image is supplied; use the complementary styling notes.'
 return f" Companion garment references define {companion['name']} ({companion['category']}, {companion['color']}); preserve its cut, texture, color and details: {companion['notes']}. Wear this companion instead of any conflicting top/bottom in the styling notes or model identity photos. Feature the TikTok garment unchanged. Keep this exact outfit in all six poses."
