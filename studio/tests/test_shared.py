import json
from pathlib import Path
import pytest
import core, shared
from test_studio import library,client,headers,picture,job

def test_shared_requires_token(client):
 assert client.post('/api/shared/sync',json={}).status_code==403
 assert client.post('/api/shared/import',json={'url':'http://127.0.0.1/a'},headers=headers()).status_code==400

def test_downloaded_gallery_served_without_network(client,library,monkeypatch):
 p=library/'galleries/poses/sample/original/front.png';p.parent.mkdir(parents=True);p.write_bytes(picture().getvalue())
 url='https://ai-pose-gallery.pages.dev/img/sample.png'
 (library/'gallery-sources.json').write_text(json.dumps({url:core.relative(p)}))
 monkeypatch.setattr(shared.requests,'get',lambda *a,**kw:pytest.fail('Cached image must not request the upstream host'))
 r=client.get('/reference-image',query_string={'url':url})
 assert r.status_code==200 and r.data==p.read_bytes()

def test_index_freeze_and_attach(client,library):
 p=library/'source.png';p.write_bytes(picture().getvalue())
 shared.index_files();asset=core.records('assets')[0]
 asset.update(role='pose',prompt='side view');core.save('assets',asset)
 j=job()
 r=client.post('/api/shared/'+asset['id']+'/attach',json={'job_id':j['id']},headers=headers());assert r.status_code==200
 frozen=shared.freeze(core.get('jobs',j['id']))
 assert Path(frozen[0]['path']).read_bytes()==p.read_bytes()
 p.write_bytes(b'changed');assert Path(frozen[0]['path']).read_bytes()!=p.read_bytes()

def test_scene_handoff_uses_background_instead_of_white_studio(client,library):
 from test_wardrobe import setup_product
 j=setup_product(library);p=library/'background.png';p.write_bytes(picture().getvalue())
 shared.index_files();a=next(a for a in core.records('assets') if a['path']=='background.png')
 a.update(role='scene',reference_role='background',prompt='Liminal hallway; environment only.');core.save('assets',a)
 client.post('/api/shared/'+a['id']+'/attach',json={'job_id':j['id']},headers=headers())
 r=client.post('/api/jobs/'+j['id']+'/handoff',json={},headers=headers());assert r.status_code==200,r.json
 payload=json.loads((library/'jobs'/j['id']/'handoff.json').read_text())
 assert payload['shared_references'][0]['role']=='scene'
 assert all('Liminal hallway' in prompt and 'Pure white background and floor' not in prompt for prompt in payload['prompts'])
 assert 'selected scene background' in r.json['text']

def test_verified_r2_roundtrip(library,monkeypatch):
 p=library/'asset.png';p.write_bytes(picture().getvalue());shared.index_files();objects={}
 class S3:
  def upload_file(self,path,bucket,key,ExtraArgs=None):objects[key]=(Path(path).read_bytes(),(ExtraArgs or {}).get('Metadata',{}))
  def head_object(self,Bucket,Key):return dict(ContentLength=len(objects[Key][0]),Metadata=objects[Key][1])
  def put_object(self,Bucket,Key,Body,**kw):objects[Key]=(Body,{})
  def download_file(self,bucket,key,path):Path(path).write_bytes(objects[key][0])
 monkeypatch.setattr(shared,'client',lambda:S3())
 shared.synchronize();assert not shared.SYNC['error']
 a=core.records('assets')[0];assert a['synced'];expected=p.read_bytes();p.unlink();shared.ensure(a);assert p.read_bytes()==expected
 assert 'backups/studio.sqlite' in objects and 'library.json' in objects
