"""Local reference-video ingestion and browser preview preparation."""
from pathlib import Path
import subprocess,uuid
import imageio_ffmpeg
from PIL import Image
import core as c

MAX_BYTES=250*1024*1024

def ingest(file,name='',notes=''):
 suffix=Path(file.filename or '').suffix.lower()
 if suffix not in ('.mp4','.mov','.webm'):raise ValueError('Choose an MP4, MOV or WebM video.')
 ident=uuid.uuid4().hex[:12];folder=c.local(c.DATA/'reference-videos'/ident);folder.mkdir(parents=True)
 try:
  original=folder/('original'+suffix);file.save(original)
  if not 0<original.stat().st_size<=MAX_BYTES:raise ValueError('Reference videos must be non-empty and at most 250 MB.')
  reader=imageio_ffmpeg.read_frames(str(original),pix_fmt='rgb24')
  try:
   meta=next(reader);frame=next(reader)
  finally:reader.close()
  duration=float(meta.get('duration',0));width,height=meta['size']
  if not 0<duration<=600:raise ValueError('Use a video up to 10 minutes long. Revana edits use a 4-30 second clip.')
  poster=Image.frombytes('RGB',(width,height),frame);poster.thumbnail((480,480));poster.save(folder/'poster.jpg',quality=90)
  preview=folder/'preview.mp4'
  # Keep the original untouched; prepare an H.264/AAC preview browsers can play.
  proc=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-i',str(original),'-map','0:v:0','-map','0:a?','-vf',"scale=w='min(720,iw)':h='min(1280,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1",'-r','30','-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(preview)],capture_output=True,text=True,timeout=300,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  if proc.returncode:raise ValueError('Could not decode this video. Export a playable MP4 and try again.')
  return c.save('reference_videos',{'id':ident,'name':str(name).strip()[:160] or Path(file.filename).stem[:160],'original_name':Path(file.filename.replace('\\','/')).name,'notes':str(notes)[:2500],'path':c.relative(original),'preview':c.relative(preview),'poster':c.relative(folder/'poster.jpg'),'bytes':original.stat().st_size,'duration':duration,'width':width,'height':height,'fps':meta.get('fps'),'has_audio':meta.get('audio_codec')not in (None,'','none'),'revana_clip_ready':4<=duration<=30,'created_at':c.now(),'status':'saved_locally'})
 except Exception:
  import shutil
  shutil.rmtree(c.local(folder),ignore_errors=True)
  raise
