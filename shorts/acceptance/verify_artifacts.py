"""Verify observed timeline and AV properties; not perceptual listening or publication proof."""
from pathlib import Path
import json,subprocess,hashlib
import numpy as np
R=Path(__file__).resolve().parents[1];A=R/'acceptance'
def probe(p):return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]))
def frame(p,t,w,h):
 b=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(p),'-frames:v','1','-vf',f'scale={w}:{h}','-pix_fmt','rgb24','-f','rawvideo','-']);return np.frombuffer(b,np.uint8).reshape(h,w,3)
def tone(p,t):
 b=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(p),'-t','1','-ac','1','-ar','16000','-f','f32le','-']);x=np.frombuffer(b,'<f4');y=np.abs(np.fft.rfft(x));return float(np.fft.rfftfreq(len(x),1/16000)[int(y.argmax())])
out={}
for kind in ('short','long'):
 d=A/f'out-{kind}';m=json.loads((d/'manifest.json').read_text());video=d/m['video'];z=probe(video);obs=[]
 for sc in m['scenes']:
  src=Path(m['plan_dir'])/sc['source']['ref'];st=float(sc['source']['in'])+1;t=sc['start']+1
  # Match at source-native aspect, long/short tests intentionally use same aspect for source and export.
  a=frame(src,st,320,180 if kind=='long' else 568);b=frame(video,t,320,180 if kind=='long' else 568)
  mae=float(np.abs(a.astype(float)-b.astype(float)).mean());hz=tone(video,t)
  obs.append({'scene':sc['id'],'output_t':t,'source_t':st,'frame_mae':mae,'dominant_hz':hz})
  assert mae<8,(kind,sc['id'],mae)
 # Actual full decode with errors treated as errors; not listening.
 subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(video),'-f','null','-'],check=True)
 v=next(s for s in z['streams'] if s['codec_type']=='video');au=next(s for s in z['streams'] if s['codec_type']=='audio')
 out[kind]={'duration':float(z['format']['duration']),'width':v['width'],'height':v['height'],'video_codec':v['codec_name'],'audio_codec':au['codec_name'],'observations':obs,'full_decode':True,'movement_listened_review':False,'sha256':hashlib.sha256(video.read_bytes()).hexdigest()}
assert abs(out['short']['duration']-18)<.1
assert abs(out['long']['duration']-480)<.1
(A/'observed-changes.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print('Observed timelines, duration, source frames, tones and full decode verified; no perceptual playback claim.')
