import pytest
import core,revana_workflow
from test_studio import library,client,headers,job

def ready(library):
 j=job();p=library/'products'/'item.png';p.write_bytes(b'product fixture')
 m=library/'models'/'face.png';m.write_bytes(b'face fixture')
 v=library/'source.mp4';v.write_bytes(b'video fixture')
 core.save('products',{'id':j['product_id'],'images':[{'path':core.relative(p)}]})
 core.save('models',{'id':'model','references':[core.relative(m)]})
 core.save('reference_videos',{'id':'clip','name':'OOTD','path':core.relative(v),'duration':6.92})
 j.update(model_id='model',status='complete',images=['old-pose.png']*6,video={'path':'old.mp4'});core.save('jobs',j)
 return j

def test_reference_edit_uses_wan_and_freezes_inputs(client,library):
 j=ready(library)
 r=client.post('/api/jobs/'+j['id']+'/reference-edit',json={'reference_video_id':'clip','resolution':'720p'},headers=headers())
 assert r.status_code==200,r.json
 request=r.json
 assert request['model']=='wan-3.0' and request['task']=='video_edit' and request['generation_id'] is None
 assert core.local(request['source_video']).read_bytes()==b'video fixture'
 assert core.local(request['product_reference']).read_bytes()==b'product fixture'
 saved=core.get('jobs',j['id']);assert saved['video']==j['video'] and saved['images']==j['images']
 assert saved['generation_mode']=='reference_video_edit'
 assert request['status']=='needs_mcp_reload' and core.settings().get('publish_enabled') is not True

def test_invalid_edit_request_does_not_change_job(client,library):
 j=ready(library)
 for body in [{'reference_video_id':'missing'},{'reference_video_id':'clip','resolution':'4k'}]:
  r=client.post('/api/jobs/'+j['id']+'/reference-edit',json=body,headers=headers());assert r.status_code==400
 assert 'video_edit' not in core.get('jobs',j['id'])
 v=core.get('reference_videos','clip');v['duration']=31;core.save('reference_videos',v)
 with pytest.raises(ValueError):revana_workflow.prepare(j,'clip')


def test_all_model_refs_and_explicit_product_roles(library):
 j=ready(library);m=core.get('models','model')
 for i in range(4):
  p=library/'models'/f'extra-{i}.png';p.write_bytes(b'extra');m['references'].append(core.relative(p))
 core.save('models',m)
 r=revana_workflow.prepare(j,'clip')
 assert len(r['person_references'])==5
 assert len(r['reference_roles']['reference_images'])==6
 assert r['reference_roles']['reference_images'][-1]['role']=='featured_product'
 assert 'Reference image 6 is the PRODUCT reference only' in r['prompt']
 urls=[f'https://example.com/model-{i}.png' for i in range(5)]
 args=revana_workflow.build_remote_args(r,'https://example.com/source.mp4',urls,'https://example.com/product.png')
 assert args['reference_images']==urls+['https://example.com/product.png'] and args['audio'] is False
 with pytest.raises(ValueError):revana_workflow.build_remote_args(r,'source',urls[:2],'product')
 m['references']*=2;core.save('models',m)
 with pytest.raises(ValueError,match='none will be silently omitted'):revana_workflow.prepare(j,'clip')
