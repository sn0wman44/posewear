import io,subprocess
import pytest
import imageio_ffmpeg
from PIL import Image
import core
from test_studio import library,client,headers,picture

@pytest.fixture
def video_file(tmp_path):
 p=tmp_path/'source.mp4'
 subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-f','lavfi','-i','color=c=blue:s=64x96:r=30','-t','4','-c:v','libx264','-pix_fmt','yuv420p',str(p)],check=True,capture_output=True)
 return p

def test_append_model_photos_preserves_existing(client,library):
 r=client.post('/api/models',data={'name':'Model','files':(picture(),'first.png')},headers=headers());assert r.status_code==200
 m=r.json;first=m['references'][0];original=core.local(first).read_bytes()
 r=client.post('/api/models/'+m['id']+'/photos',data={'files':[(picture(),'side.png'),(picture(),'back.png')]},headers=headers())
 assert r.status_code==200 and len(r.json['references'])==3
 assert r.json['references'][0]==first and core.local(first).read_bytes()==original

def test_model_append_invalid_batch_preserves_library(client,library):
 m=client.post('/api/models',data={'name':'Model','files':(picture(),'first.png')},headers=headers()).json
 before=list(core.local('models/'+m['id']).iterdir())
 r=client.post('/api/models/'+m['id']+'/photos',data={'files':[(picture(),'valid.png'),(io.BytesIO(b'broken'),'invalid.png')]},headers=headers())
 assert r.status_code==400 and core.get('models',m['id'])['references']==m['references']
 assert list(core.local('models/'+m['id']).iterdir())==before

def test_model_reference_limit_and_unknown_model(client,library):
 core.save('models',{'id':'full','name':'Full','references':['existing.png']*20})
 assert client.post('/api/models/full/photos',data={'files':(picture(),'new.png')},headers=headers()).status_code==400
 assert client.post('/api/models/missing/photos',data={'files':(picture(),'new.png')},headers=headers()).status_code==400

def test_reference_video_upload_preview_and_range(client,library,video_file):
 original=video_file.read_bytes()
 r=client.post('/api/reference-videos',data={'name':'Walk','notes':'Keep motion','file':(io.BytesIO(original),'../source.mp4')},headers=headers())
 assert r.status_code==200,r.json
 v=r.json;assert v['name']=='Walk' and v['original_name']=='source.mp4' and v['revana_clip_ready'] is True
 assert core.local(v['path']).read_bytes()==original
 assert core.local(v['preview']).stat().st_size>0 and core.local(v['poster']).is_file()
 res=client.get('/media/'+v['preview'],headers={'Range':'bytes=0-31'})
 assert res.status_code==206 and len(res.data)==32;res.close()
 assert client.get('/api/state').json['reference_videos'][0]['id']==v['id']
 assert core.settings().get('publishing_paused') is not False

def test_invalid_video_is_rejected_and_cleaned(client,library):
 r=client.post('/api/reference-videos',data={'file':(io.BytesIO(b'not a movie'),'bad.mp4')},headers=headers())
 assert r.status_code==400 and not core.records('reference_videos')
 assert not list((library/'reference-videos').iterdir())
 assert client.post('/api/reference-videos',data={'file':(io.BytesIO(b'text'),'wrong.txt')},headers=headers()).status_code==400
 assert client.post('/api/reference-videos',data={},headers=headers()).status_code==400


def test_delete_model_photo_preserves_other_refs_and_history(client,library):
 m=client.post('/api/models',data={'name':'Model','files':[(picture(),'first.png'),(picture(),'second.png')]},headers=headers()).json
 path=m['references'][0]
 assert client.delete('/api/models/'+m['id']+'/photos',json={'path':path}).status_code==403
 r=client.delete('/api/models/'+m['id']+'/photos',json={'path':path},headers=headers())
 assert r.status_code==200 and r.json['references']==m['references'][1:]
 assert core.local(path).is_file()
 assert client.delete('/api/models/'+m['id']+'/photos',json={'path':'../outside'},headers=headers()).status_code==400
 assert client.delete('/api/models/'+m['id']+'/photos',json={'path':path},headers=headers()).status_code==400
 last=m['references'][1]
 assert client.delete('/api/models/'+m['id']+'/photos',json={'path':last},headers=headers()).json['references']==[]
