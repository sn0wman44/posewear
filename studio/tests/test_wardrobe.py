import io
import json
import zipfile
import pytest
from PIL import Image
import core
import wardrobe as w
from test_studio import library,client,job,headers,picture

def setup_product(library,title='Navy halter top'):
 j=job();p=library/'products'/'front.png';Image.new('RGB',(40,60),'navy').save(p)
 core.save('products',{'id':j['product_id'],'title':title,'images':[{'path':core.relative(p)}]})
 core.save('models',{'id':'m','name':'Model','references':[]});j['model_id']='m';core.save('jobs',j)
 return j

def upload(client,category='bottoms',color='black',tags='casual,solid',grouping='separate'):
 return client.post('/api/wardrobe',data={'category':category,'color':color,'tags':tags,'grouping':grouping,'files':[(picture(),'jeans.png'),(picture(),'trousers.png')]},headers=headers())

def test_batch_and_multiview_uploads(client):
 r=upload(client);assert r.status_code==200 and len(r.json['items'])==2
 r=upload(client,grouping='views');assert len(r.json['items'])==1 and len(r.json['items'][0]['images'])==2
 assert r.json['items'][0]['reusable'] is True

def test_invalid_batch_rolls_back(client,library):
 r=client.post('/api/wardrobe',data={'category':'bottoms','files':[(picture(),'ok.png'),(io.BytesIO(b'bad'),'bad.png')]},headers=headers())
 assert r.status_code==400 and not core.records('wardrobe') and not list((library/'wardrobe').iterdir())

def test_variant_identity_and_review_gate(client,library):
 j=setup_product(library);p=core.get('products',j['product_id']);p['images'].append({'path':p['images'][0]['path']+'-other'})
 a=w.ensure_product(p);b=w.ensure_product(p,1)
 assert a['id']!=b['id'] and not a['reusable'] and a['category']=='tops'
 assert w.ensure_product(p)['id']==a['id']

def test_matching_filters_scores_and_manual_override(client,library):
 j=setup_product(library);items=upload(client).json['items'];a,b=items
 a.update(color='black',tags=['casual','solid']);core.save('wardrobe',a)
 b.update(color='pink',tags=[]);core.save('wardrobe',b)
 main=w.featured(j);main['tags']=['casual'];core.save('wardrobe',main)
 assert w.choose(j)[0]['id']==a['id']
 j.update(outfit_mode='manual',companion_id=b['id']);assert w.choose(j)[0]['id']==b['id']
 b['category']='tops';core.save('wardrobe',b)
 with pytest.raises(ValueError):w.choose(j)
 j['outfit_mode']='none';assert w.choose(j)[0] is None
 a['reusable']=False;core.save('wardrobe',a);j['outfit_mode']='auto';assert w.choose(j)[0] is None

def test_bottom_feature_pairs_with_top_and_dress_has_no_companion(client,library):
 j=setup_product(library,'Straight jeans');upload(client,'tops');assert w.choose(j)[0]['category']=='tops'
 j['featured_category']='dresses';assert w.choose(j)[0] is None

def test_handoff_references_snapshot_and_prompts(client,library):
 j=setup_product(library);item=upload(client).json['items'][0]
 j.update(outfit_mode='manual',companion_id=item['id']);core.save('jobs',j)
 r=client.post(f"/api/jobs/{j['id']}/handoff",json={},headers=headers());assert r.status_code==200,r.json
 payload=json.loads((library/'jobs'/j['id']/'handoff.json').read_text())
 assert payload['companion_references'] and payload['reference_roles']['model_references'].startswith('Identity only')
 assert 'Keep this exact outfit in all six poses' in payload['prompts'][0]
 saved=core.get('jobs',j['id']);frozen=saved['outfit'];ref=frozen['parts'][1]['references'][0]
 before=core.local(ref).read_bytes();Image.new('RGB',(40,60),'red').save(core.local(item['images'][0]))
 item['name']='Edited item';core.save('wardrobe',item)
 assert core.get('jobs',j['id'])['outfit']==frozen and core.local(ref).read_bytes()==before
 # Preparing another handoff explicitly changes the snapshot and archives existing poses.
 poses=library/'jobs'/j['id']/'poses';poses.mkdir();Image.new('RGB',(20,30)).save(poses/'01.png')
 saved['images'][0]=core.relative(poses/'01.png');saved['video']={'path':'old.mp4'};core.save('jobs',saved)
 r=client.post(f"/api/jobs/{j['id']}/handoff",json={},headers=headers());assert r.status_code==200
 changed=core.get('jobs',j['id']);assert changed['outfit']['fingerprint']!=frozen['fingerprint']
 assert changed['images']==[None]*6 and changed['video']['stale'] and list(poses.parent.glob('poses-previous-*'))

def test_configure_manual_outfit_invalidates_and_invalid_override_rejected(client,library):
 j=setup_product(library);item=upload(client).json['items'][0]
 j['images'][0]='old.png';core.save('jobs',j)
 r=client.post(f"/api/jobs/{j['id']}/configure",json={'outfit_mode':'manual','companion_id':item['id']},headers=headers())
 assert r.status_code==200 and core.get('jobs',j['id'])['images']==[None]*6
 r=client.post(f"/api/jobs/{j['id']}/configure",json={'featured_category':'bottoms'},headers=headers())
 assert r.status_code==400 and core.get('jobs',j['id']).get('featured_category')==''

def test_bundle_contains_companion_snapshot(client,library):
 j=setup_product(library);upload(client)
 client.post(f"/api/jobs/{j['id']}/handoff",json={},headers=headers())
 r=client.get(f"/api/jobs/{j['id']}/bundle");assert r.status_code==200
 with zipfile.ZipFile(io.BytesIO(r.data)) as z:
  assert any(n.startswith('outfit/companion-') for n in z.namelist())
  assert json.loads(z.read('job.json'))['outfit']['parts'][1]['role']=='companion'

def test_library_edit_is_validated_and_product_history_is_retained(client,library):
 j=setup_product(library);w.migrate();i=core.records('wardrobe')[0]
 r=client.post('/api/wardrobe/'+i['id'],json={'category':'bottoms','color':'black','reusable':'true'},headers=headers());assert r.status_code==200
 assert core.get('products',j['product_id'])['images']
 assert client.post('/api/wardrobe/'+i['id'],json={'selected_image':99},headers=headers()).status_code==400
 assert client.get('/api/state').json['wardrobe']

def test_legacy_completed_job_needs_new_poses_when_companion_added(client,library):
 j=setup_product(library);j['images']=['legacy.png']*6;j['status']='complete';j['video']={'path':'old.mp4'};core.save('jobs',j)
 upload(client)
 r=client.post(f"/api/jobs/{j['id']}/handoff",json={},headers=headers());assert r.status_code==200
 saved=core.get('jobs',j['id']);assert saved['images']==[None]*6 and saved['video']['stale']
