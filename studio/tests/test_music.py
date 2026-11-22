import json
import pytest
import core,music
from test_studio import library,client,job,headers
URLS=['https://www.tiktok.com/music/song-7699389004822645511','https://www.tiktok.com/music/other-7636089480688651015']
CONNECTION='connection-one'

def resolved(ident):return {'ok':True,'data':{'resolved_music':{'id':ident,'title':'Saved sound','author':'Artist','duration':'26','play_url':'https://example.com/audio'}}}
def setup(library):
 j=job();v=library/'jobs'/j['id']/'video.mp4';v.write_bytes(b'video fixture')
 j['video']={'path':core.relative(v)};core.save('jobs',j)
 for item in music.save_links(URLS):music.store_resolution(item['id'],CONNECTION,resolved(item['id']))
 return j

def test_music_urls_are_official_and_deduplicated(library):
 music.save_links(URLS);music.save_links(URLS)
 assert len(core.records('music'))==2
 for url in ['http://www.tiktok.com/music/song-7699389004822645511','https://evil.com/music/song-7699389004822645511','https://www.tiktok.com:9000/music/song-7699389004822645511','https://www.tiktok.com/not-music/7699389004822645511']:
  with pytest.raises(ValueError):music.save_links([url])

def test_failed_and_disabled_music_excluded_per_connection(library):
 items=music.save_links(URLS)
 music.store_resolution(items[0]['id'],CONNECTION,resolved(items[0]['id']))
 music.store_resolution(items[1]['id'],CONNECTION,{'ok':False,'error':{'reason':'PROVIDER_UNAVAILABLE','request_id':'req-failure'}})
 assert len(music.available(CONNECTION))==1 and not music.available('other-account')
 item=core.get('music',items[0]['id']);item['enabled']=False;core.save('music',item);assert not music.available(CONNECTION)
 assert core.get('music',items[1]['id'])['resolutions'][CONNECTION]['request_id']=='req-failure'

def test_random_selection_is_frozen_and_explicit_repick_changes_it(library):
 j=setup(library);first=music.prepare_draft(j,CONNECTION,'Creator')
 second=music.prepare_draft(core.get('jobs',j['id']),CONNECTION,'Creator')
 assert first['selected_music']==second['selected_music']
 new=music.prepare_draft(core.get('jobs',j['id']),CONNECTION,'Creator',repick=True)
 assert first['selected_music']['id']!=new['selected_music']['id']
 assert new['is_ai_generated'] is True and new['status']=='draft_not_submitted'
 assert music.read_draft(core.get('jobs',j['id']))['music_url'] in URLS

def test_new_render_archives_old_draft(library):
 j=setup(library);music.prepare_draft(j,CONNECTION,'Creator')
 j=core.get('jobs',j['id']);v=library/'jobs'/j['id']/'new.mp4';v.write_bytes(b'new')
 j['video']['path']=core.relative(v);core.save('jobs',j)
 music.prepare_draft(j,CONNECTION,'Creator')
 assert len(list((v.parent/'publishing').glob('draft-previous-*')))==1
 j['video']['stale']=True
 with pytest.raises(ValueError):music.prepare_draft(j,CONNECTION,'Creator')

def test_music_import_and_draft_endpoints(client,library):
 r=client.post('/api/music',json={'urls':'\n'.join(URLS)},headers=headers());assert r.status_code==200
 j=setup(library);config=core.settings();config.update(publish_connection_uid=CONNECTION,publish_account='Creator');core.save('settings',config)
 r=client.post('/api/jobs/'+j['id']+'/publish-draft',json={},headers=headers());assert r.status_code==200 and r.json['selected_music']
 ident=r.json['selected_music']['id']
 assert client.post('/api/music/'+ident,json={'enabled':False},headers=headers()).status_code==200
 r=client.get('/api/state');assert len(r.json['music'])==2 and r.json['jobs'][0]['publishing']['selected_music']['id']==ident

def test_wrong_resolved_id_is_never_selected(library):
 i=music.save_links([URLS[0]])[0];music.store_resolution(i['id'],CONNECTION,resolved('7636089480688651015'))
 assert not music.available(CONNECTION)

def test_precheck_preference_is_preserved_in_local_drafts(library):
 j=setup(library);config=core.settings();config['publish_precheck_enabled']=False;core.save('settings',config)
 d=music.prepare_draft(j,CONNECTION,'Creator')
 assert d['precheck_enabled'] is False
 assert music.read_draft(core.get('jobs',j['id']))['precheck_enabled'] is False
