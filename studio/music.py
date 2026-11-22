"""Saved official TikTok music links and stable, local publishing drafts."""
import json
import re
import secrets
from urllib.parse import urlparse,unquote
import core as c

def parse_url(url):
 p=urlparse(str(url).strip())
 if p.scheme!='https' or p.hostname not in ('www.tiktok.com','tiktok.com') or p.port not in (None,443) or p.username or p.password:raise ValueError('Use an official https://www.tiktok.com/music/... sound URL.')
 match=re.fullmatch(r'/music/(.+)-(\d{15,25})/?',p.path)
 if not match:raise ValueError('The sound URL must end with its numeric TikTok music ID.')
 return match[2],f'https://www.tiktok.com{p.path.rstrip("/")}',unquote(match[1]).replace('-',' ')

def save_links(urls):
 if isinstance(urls,str):urls=urls.splitlines()
 if not isinstance(urls,list) or not 1<=len(urls)<=50:raise ValueError('Paste 1-50 music URLs, one per line.')
 parsed=[parse_url(u) for u in urls if str(u).strip()]
 if not parsed:raise ValueError('Paste at least one official TikTok music URL.')
 result=[]
 for ident,url,title in parsed:
  try:item=c.get('music',ident)
  except ValueError:item={'id':ident,'title':title,'enabled':True,'resolutions':{},'created_at':c.now()}
  item['url']=url;c.save('music',item);result.append(item)
 return result

def store_resolution(ident,connection,result):
 item=c.get('music',ident);error=result.get('error') or {};metadata=(result.get('data') or {}).get('resolved_music')
 valid=result.get('ok') and isinstance(metadata,dict) and str(metadata.get('id'))==ident
 if valid:
  selected={k:metadata[k] for k in ('id','title','author','duration','cover_url','play_url') if metadata.get(k) is not None}
  selected['id']=str(selected['id'])
  if 'duration'in selected:selected['duration']=str(selected['duration'])
  record={'status':'resolved','selected_music':selected,'checked_at':c.now(),'request_id':result.get('request_id')}
  item.update(title=selected.get('title',item['title']),author=selected.get('author',''))
 else:
  record={'status':'lookup_failed','checked_at':c.now(),'reason':error.get('reason','no_matching_music'),'message':error.get('message','No matching music returned.'),'request_id':error.get('request_id') or result.get('request_id'),'stage':error.get('stage'),'retryable':error.get('retryable',False)}
 item.setdefault('resolutions',{})[connection]=record
 return c.save('music',item)

def available(connection):
 return [i for i in c.records('music') if i.get('enabled') and i.get('resolutions',{}).get(connection,{}).get('status')=='resolved']

def read_draft(job):
 if not job.get('publishing_draft'):return None
 try:return json.loads(c.local(job['publishing_draft']).read_text(encoding='utf-8'))
 except (ValueError,OSError):return None

def prepare_draft(job,connection,account,repick=False):
 if not job.get('video') or job['video'].get('stale'):raise ValueError('Render the current outfit video before preparing publishing.')
 with c.LOCK:
  draft=read_draft(job) or {}
  video_path=str(c.local(job['video']['path']))
  if not c.local(job['video']['path']).is_file():raise ValueError('The rendered video file is missing.')
  same_video=draft.get('video_path')==video_path
  same_connection=draft.get('connection_uid',connection)==connection
  if not same_video or not same_connection:draft={}
  if not draft.get('selected_music') or repick:
   pool=available(connection)
   if not pool:raise ValueError('No enabled music has been resolved for this TikTok account. Ask Codex to check the saved URLs through CreatOK.')
   if repick and len(pool)>1:pool=[i for i in pool if i['id']!=draft.get('selected_music',{}).get('id')]
   chosen=secrets.choice(pool)
   draft.update(selected_music=dict(chosen['resolutions'][connection]['selected_music']),music_url=chosen['url'],music_chosen_at=c.now())
  draft.update(status='draft_not_submitted',job_id=job['id'],product_id=job['product_id'],video_path=video_path,connection_uid=connection,account=account,connection_confirmed=True,is_ai_generated=True,timezone='PST')
  draft['precheck_enabled']=c.settings().get('publish_precheck_enabled',False)
  draft['requested_destination']=c.settings().get('publish_destination','tiktok_draft')
  draft['delivery_status']='not_delivered'
  draft['public_posting_authorized']=False
  if draft['requested_destination']=='tiktok_draft':draft['delivery_blocked_reason']='CreatOK Shop publishing has no exposed TikTok draft destination. Keep this prepared package local; do not submit a public Shop post.'
  draft.setdefault('product_link_title',job['title'][:30])
  draft.setdefault('caption',f"{job['title']} | Outfit inspiration. Tap the product link to shop. #Fashion #OOTD #OutfitInspo #aigc #tiktokshop")
  draft.setdefault('created_at',c.now());draft['updated_at']=c.now()
  folder=c.DATA/'jobs'/job['id']/'publishing';folder.mkdir(exist_ok=True)
  target=folder/'draft.json'
  # Keep the previous draft when a new rendered video starts a new publishing draft.
  if target.exists() and (not same_video or not same_connection):
   import shutil,uuid
   shutil.copy2(target,folder/('draft-previous-'+uuid.uuid4().hex[:8]+'.json'))
  target.write_text(json.dumps(draft,indent=2,ensure_ascii=False),encoding='utf-8')
  job['publishing_draft']=c.relative(target);c.save('jobs',job)
  return draft
