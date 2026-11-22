"""Build the upstream UI with on-demand source images (no multi-GB prerequisite)."""
import json, shutil, re, pathlib, importlib.util
ROOT=pathlib.Path(__file__).resolve().parent
def build():
 d=ROOT/'local-site'; d.mkdir(exist_ok=True)
 for p in (ROOT/'src').iterdir():
  if p.is_file(): shutil.copy2(p,d/p.name)
 catalogs={}
 translations={line.split('|')[0]:line.split('|')[1:] for line in (ROOT/'tr_pose.txt').read_text(encoding='utf-8').strip().splitlines()}
 for kind,output,base in [('pose','poses','https://ai-pose-gallery.pages.dev/'),('costume','costumes','https://ai-costume-gallery.pages.dev/'),('anime','anime','https://ai-costume-anime-gallery.pages.dev/')]:
  raw=json.loads((ROOT/'assets-raw'/kind/'data.json').read_text(encoding='utf-8'))['D']; items=[]
  for row in raw:
   name=row.get('ポーズ名') or row.get('キーワード') or row['id']
   if kind=='pose':name=translations.get(name,['',name])[-1]
   image=base+(row.get('原寸') or row.get('画像') or row['サムネ']).lstrip('/')
   thumb=base+row['サムネ'].lstrip('/')
   adult=any(x in str(row) for x in ['セクシー','ランジェリー','2人絡み','胸寄せ'])
   it=dict(id=row['id'],ti=name,zh=name,en=name,t=thumb,m=image,i=image,o=image,cat=row.get('分類',row.get('カテゴリ','')),catEn='',kw=name,a=int(adult),ext=1)
   if kind=='pose':it.update(no=row.get('ポーズ番号',''),line=row.get('系統',''),lineEn='',angles=[dict(zh=row.get('アングル',''),en=row.get('アングル',''),t=thumb,i=image,o=image)])
   items.append(it)
  if kind=='pose':
   grouped={}
   for it in items:
    key=it['id'].rsplit('_',1)[0]
    if key not in grouped:grouped[key]=dict(it,id=key,angles=[])
    grouped[key]['angles'].extend(it['angles'])
   items=list(grouped.values())
  catalogs[output]=items
 text=(ROOT/'assets-raw/portrait/images.js').read_text(encoding='utf-8'); rows=json.loads(text[text.index('['):text.rindex(']')+1])
 catalogs['portraits']=[dict(id=r['id'],ti=r.get('style') or r['id'],zh=r.get('style',''),en=r.get('style',''),sec=r['section'],len=r['hair'],st=r.get('style',''),t='https://ai-portrait-gallery.pages.dev/'+r['thumb'].lstrip('/'),m='https://ai-portrait-gallery.pages.dev/'+r['full'].lstrip('/'),i='https://ai-portrait-gallery.pages.dev/'+r['full'].lstrip('/'),o='',ext=1) for r in rows]
 spec=importlib.util.spec_from_file_location('depthpack',ROOT/'depthpack.py'); mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 catalogs['depths']=mod.catalog()['payload']
 for name in ['expressions','hair','dynasties','scenes','lights','props','furniture']:catalogs[name]=[]
 for name in catalogs:
  custom=ROOT/'studio/data/custom-catalogs'/name
  if custom.is_dir():
   for file in sorted(custom.glob('*.json')):
    catalogs[name].extend(json.loads(file.read_text(encoding='utf-8')))
 vocab=dict(line.split('\t',1) for line in (ROOT/'src/vocabulary.tsv').read_text(encoding='utf-8').splitlines() if '\t' in line)
 portrait_tr={line.split('|')[0]:line.split('|')[-1] for line in (ROOT/'tr_portrait.txt').read_text(encoding='utf-8').splitlines() if '|' in line}
 (d/'portrait-english.tsv').write_text('\n'.join(k+'\t'+v for k,v in portrait_tr.items()),encoding='utf-8')
 for category,entries in catalogs.items():
  entries=entries.get('items',[]) if isinstance(entries,dict) else entries
  for entry in entries:
   entry['catEn']=vocab.get(entry.get('cat',''),entry.get('catEn',''))
   entry['lineEn']=vocab.get(entry.get('line',''),entry.get('lineEn',''))
   if category=='portraits':
    style=portrait_tr.get(entry.get('st',''),'')
    entry['nameEn']=style or ('Face portrait' if entry['sec']=='face' else 'Lifestyle portrait')+' '+entry['id']
    entry['en']=', '.join(filter(None,[style,vocab.get(entry['len'],entry['len']),'adult fictional person','face reference' if entry['sec']=='face' else 'lifestyle photo']))
   for angle in entry.get('angles',[]):angle['en']=vocab.get(angle['zh'],angle.get('en',angle['zh']))
 language_pairs=dict(portrait_tr)
 for entries in catalogs.values():
  for entry in entries.get('items',[]) if isinstance(entries,dict) else entries:
   if entry.get('en'):
    for field in ('zh','ja'):
     if entry.get(field):language_pairs[entry[field]]=entry['en']
 (d/'portrait-english.tsv').write_text('\n'.join(k+'\t'+v for k,v in language_pairs.items()),encoding='utf-8')
 for name,rows in catalogs.items():(d/(name+'.json')).write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8')
 html=(d/'index.html').read_text(encoding='utf-8').replace('<title>姿势库 · 衣姿 PoseWear</title>','<title>Product Video Studio</title>').replace('<body>','<body><div class="studio-links"><a href="/">Product Video Studio</a> · <a href="/video-studio">Video Studio</a> · <a href="/library">Shared library & storage</a></div>')
 html=html.replace('<head>','<head><script src="/language-default.js"></script><link rel="stylesheet" href="/app-navigation.css">',1).replace('lang="zh-CN"','lang="en"',1).replace('localStorage.lang||\'"zh"\'','localStorage.lang||\'"en"\'')
 html=html.replace('</head>', '<style>.studio-links{padding:10px 24px;background:#f6f6f6;border-bottom:1px solid #ddd;font:14px system-ui}.studio-links a{color:inherit;text-decoration:none;margin-right:12px}#ann{display:none}</style></head>')
 html=html.replace('</body>','<script src="/english.js" defer></script><script src="/integration.js" defer></script></body>')
 (d/'index.html').write_text(html,encoding='utf-8')
 app=(d/'app.js').read_text(encoding='utf-8').replace("LS('lang')||'zh'","LS('lang')||'en'").replace("LS('tl')||'zh'","LS('tl')||'en'")
 app=app.replace("+' · 衣姿 PoseWear'","+' · Product Video Studio'")
 if catalogs['scenes']:
  app=app.replace('场景来自 Shisei（作者 wquguru），图片与数据 CC0 1.0，可自由使用。空景中央留空，方便把人物放进去。','User-uploaded background references. Choose Liminal in the category filter to browse the imported folder. Use these images for environments, lighting and atmosphere; identity and clothing come from separate references.')
 app=app.replace("const ath=u=>u.startsWith('http')?u:AH+u;", "const ath=u=>u.startsWith('http')?'/reference-image?url='+encodeURIComponent(u):AH+u;")
 app=app.replace('src=big(it),D=', 'src=ath(big(it)),D=').replace('${it.m} 1080w, ${it.i} 1366w','${ath(it.m)} 1080w, ${ath(it.i)} 1366w')
 app=app.replace("const title=it=>", "const title=it=>st.lang=='en'?(it.nameEn||it.en||it.id):")
 app=app.replace("st.lang=='en'?en+zh:zh+en", "st.lang=='en'?en:zh+en")
 app=app.replace("esc(it.ja)","esc(st.lang=='en'?it.en:it.ja)").replace("esc(it.lineJa)","esc(st.lang=='en'?it.lineEn:it.lineJa)").replace("esc(it.catJa)","esc(st.lang=='en'?it.catEn:it.catJa)").replace("esc(it.angles[it.ai].ja)","esc(st.lang=='en'?it.angles[it.ai].en:it.angles[it.ai].ja)")
 app=app.replace("if(!quiet)toast(l==", "if(!$('#lb').hidden)lbDraw();if(!quiet)toast(l==")
 app=re.sub(r"if\('serviceWorker'in navigator&&location.protocol!='file:'\).*?;",'',app)
 (d/'app.js').write_text(app,encoding='utf-8')
 print({k:len(v.get('items',[])) if isinstance(v,dict) else len(v) for k,v in catalogs.items()})
if __name__=='__main__':build()
