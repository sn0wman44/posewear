import io
import json
from pathlib import Path
import pytest
from PIL import Image
import core
import app as studio

@pytest.fixture
def library(tmp_path,monkeypatch):
 monkeypatch.setattr(core,'DATA',tmp_path/'data');core.init()
 studio.BUSY.clear()
 return core.DATA

@pytest.fixture
def client(library):return studio.app.test_client()

def picture():
 b=io.BytesIO();Image.new('RGB',(90,160),'white').save(b,format='PNG');b.seek(0);return b

def job():return core.new_job('https://shop.tiktok.com/us/pdp/sample/1731255108565177086')[0]

def headers():return {'X-Studio-Token':studio.SESSION}

def test_product_id_and_reject_other_hosts():
 assert core.product_id('https://shop.tiktok.com/us/pdp/name/1731255108565177086?color=black')=='1731255108565177086'
 for u in ['https://example.com/us/pdp/name/1731255108565177086','http://shop.tiktok.com/us/pdp/name/1731255108565177086','https://shop.tiktok.com:8000/us/pdp/name/1731255108565177086','https://shop.tiktok.com/us/pdp/name/no-id']:
  with pytest.raises(ValueError):core.product_id(u)

def test_gallery_deduplicates_and_excludes_review_thumbnails():
 url='https://p16-oec-general-useast5.ttcdn-us.com/tos-useast5-i-omjb5zjo8w-tx/'+'a'*32+'~tplv-fhlh96nyum-resize-webp:800:800.webp'
 source='<title>Test tank</title>'+json.dumps({'urls':[url,url,url.replace('800:800','300:300'),url.replace('ttcdn-us.com','example.com')]})
 result=core.extract_candidates(source)
 assert result['title']=='Test tank' and len(result['images'])==1
 assert 'crop-jpeg:1800:1800.jpeg'in result['images'][0]['large_url']

def test_jsonld_product_images_are_preferred():
 url='https://p16-oec-general-useast5.ttcdn-us.com/product.jpg'
 source='<script type="application/ld+json">'+json.dumps({'@type':'Product','image':[url,url]})+'</script>'
 assert core.extract_candidates(source)['method']=='Product structured data'
 assert len(core.extract_candidates(source)['images'])==1

def test_storage_path_traversal(library):
 assert core.local('jobs/ok')==library/'jobs/ok'
 with pytest.raises(ValueError):core.local('../outside')
 with pytest.raises(ValueError):core.local(Path('C:/Windows/system.ini'))

def test_duplicate_intake(library):
 first,fresh=core.new_job('https://shop.tiktok.com/us/pdp/sample/1731255108565177086')
 second,fresh2=core.new_job(first['url'])
 assert fresh and not fresh2 and first['id']==second['id']

def test_csrf_host_and_origin(client):
 assert client.post('/api/settings',json={}).status_code==403
 assert client.post('/api/settings',json={},headers={**headers(),'Origin':'https://evil.example'}).status_code==403
 assert client.get('/api/state',headers={'Host':'evil.example'}).status_code==403
 assert client.post('/api/settings',json={},headers=headers()).status_code==200

def test_model_upload_and_pose_assignment(client):
 result=client.post('/api/models',data={'name':'Test model','files':(picture(),'face.png')},headers=headers())
 assert result.status_code==200
 j=job()
 result=client.post(f'/api/jobs/{j["id"]}/pose/0',data={'file':(picture(),'pose.png')},headers=headers())
 assert result.status_code==200 and core.get('jobs',j['id'])['images'][0].endswith('01.png')
 assert client.post(f'/api/jobs/{j["id"]}/pose/6',data={'file':(picture(),'pose.png')},headers=headers()).status_code==400

def test_handoff_is_chat_only_and_no_generation(client,library):
 j=job();m=core.save('models',{'id':'m','references':[],'name':'Model'})
 Image.new('RGB',(20,30)).save(library/'products'/'photo.png')
 core.save('products',{'id':j['product_id'],'images':[{'path':'products/photo.png'}]})
 j['model_id']=m['id'];core.save('jobs',j)
 result=client.post(f'/api/jobs/{j["id"]}/handoff',json={},headers=headers())
 assert result.status_code==200
 assert 'do not use a paid API' in result.json['text']
 assert len(result.json['prompts'])==6 and core.get('jobs',j['id'])['status']=='awaiting_images'

def test_renderer_validates_total_and_loop(library):
 j=job();folder=library/'jobs'/j['id']/'poses';folder.mkdir()
 for i in range(6):
  f=folder/f'{i+1:02}.png';Image.new('RGB',(90,160),(i*30,60,100)).save(f);j['images'][i]=core.relative(f)
 j['render']['hold_frames']=6;j['render']['repeats']=1
 video=core.render_video(j)
 assert video['frames']==36 and video['seconds']==1.2 and core.local(video['path']).stat().st_size>0
 timeline=json.loads((folder.parent/'timeline.json').read_text())
 assert [s['pose']for s in timeline['shots']]==list(range(6))
 assert [s['start_frame']for s in timeline['shots']]==[0,6,12,18,24,30]

def test_discord_secret_never_returned(client,monkeypatch):
 monkeypatch.setattr(studio,'DISCORD_TOKEN','private-test-token')
 result=client.get('/api/state')
 assert result.json['discord']['token_configured'] is True
 assert b'private-test-token' not in result.data

def test_nonmedia_is_not_served(client):
 assert client.get('/media/studio.sqlite').status_code==404

def test_invalid_pose_upload_is_recoverable(client):
 j=job();res=client.post(f'/api/jobs/{j["id"]}/pose/0',data={'file':(io.BytesIO(b'not image'),'bad.png')},headers=headers())
 assert res.status_code==400 and 'error'in res.json

def test_changed_variant_invalidates_old_poses(client,library):
 j=job();folder=library/'jobs'/j['id']/'poses';folder.mkdir();image=folder/'01.png';Image.new('RGB',(10,10)).save(image)
 j['images'][0]=core.relative(image);j['video']={'path':'jobs/old.mp4'};core.save('jobs',j)
 core.save('products',{'id':j['product_id'],'images':[{'path':'products/1.jpg'},{'path':'products/2.jpg'}]})
 res=client.post(f'/api/jobs/{j["id"]}/configure',json={'selected_image':1},headers=headers())
 assert res.status_code==200
 updated=core.get('jobs',j['id']);assert updated['images']==[None]*6 and updated['video']['stale']
 assert len(list(folder.parent.glob('poses-previous-*')))==1

def test_video_settings_do_not_invalidate_poses(client,library):
 j=job();j['images'][0]='jobs/pose.png';core.save('jobs',j)
 core.save('products',{'id':j['product_id'],'images':[{'path':'products/1.jpg'}]})
 res=client.post(f'/api/jobs/{j["id"]}/configure',json={'render':{'hold_frames':12,'repeats':5}},headers=headers())
 assert res.status_code==200 and core.get('jobs',j['id'])['images'][0]=='jobs/pose.png'
