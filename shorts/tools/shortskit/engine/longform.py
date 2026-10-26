"""Schema 1.4 long export. Local media, bounded-memory FFmpeg, no vertical QA assumptions."""
from __future__ import annotations
import hashlib
import json
import math
import shutil
import subprocess
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from ..util import ShortsError, ffprobe, read_json, write_json, run, has_long_dash, count_emoji
from ..config import skill_root
from .. import contract as K


def lint_long(p, base):
    from ..plan import Issue, resolve_ref
    out = []
    def err(msg): out.append(Issue('error', 'long', msg))
    v = p['video']; w,h = v.get('width',1920), v.get('height',1080)
    if (w,h) not in ((1280,720),(1920,1080)): err('long requires 1280x720 or 1920x1080')
    if p.get('schema_version') != '1.4': err('long requires schema_version 1.4')
    if p['layout'] != {'mode':'center_only'}: err('long layout supports only {"mode":"center_only"}')
    if p['meta'].get('loop'): err('long does not support automatic loop')
    if p['meta'].get('fps',30) not in (30,60): err('long fps must be 30 or 60')
    if p['meta'].get('platforms') != ['youtube']: err('long supports platforms ["youtube"]')
    for k in ('fx','edit','overlays'):
        if p.get(k): err(f'long does not implement {k}; remove it or use short format')
    au=p.get('audio') or {}
    mu = au.get('music')
    msrc = (mu.get('source') if isinstance(mu, dict) else mu) or ''
    if str(msrc).strip().lower() == 'auto':
        err('long: music "auto" is for shorts; find a track with `shorts.py music-find --length N`, pre-mix it into the narration, '
            'and set audio.music to {"source": "none"}')
    elif (mu and str(msrc).strip().lower() not in ('none', 'off')) or au.get('sfx_auto') or au.get('export','with_music')!='with_music':
        err('long: pre-mix music/sfx into source or narration; audio.export not implemented')
    cap=p.get('captions') or {}
    if cap.get('enabled',False) and any(cap.get(k) for k in ('style','anim','kinetic')):
        err('long captions are SRT sidecar only; kinetic/animation not implemented')
    ids=set()
    for s in p['scenes']:
        if s['id'] in ids: err('duplicate scene id')
        ids.add(s['id']); src=s['source']; kind=src['type']
        if kind not in ('video','film','images','text'): err(f'{s["id"]}: long source {kind} not implemented')
        if s.get('speed') or s.get('edit') or s.get('sfx') or s.get('trans') not in (None,'cut'):
            err(f'{s["id"]}: long supports cuts at normal speed only')
        if s.get('duration_hint'): err('long uses duration, not duration_hint')
        if any(src.get(k) for k in ('actions','crop_x','focus','zoom_on_click','mode','viewport')): err('long source modifiers not implemented; use video.fit')
        if s.get('say') and s.get('narration'): err('say and narration are mutually exclusive')
        if s.get('narration') and not resolve_ref(s['narration'],base): err('narration media_missing')
        refs=src.get('images',[]) if kind=='images' else ([src.get('ref','')] if kind in ('video','film') else [])
        if kind=='images' and len(refs)!=1: err('long images requires exactly one image per scene')
        for ref in refs:
            if not resolve_ref(ref,base): err(f'media_missing: {ref}; long needs local media')
        if kind not in ('video','film') and not s.get('duration') and not s.get('say'):
            err(f'{s["id"]}: duration required')
        if kind in ('video','film') and (src.get('out') is None or src['out']<=src.get('in',0)):
            err(f'{s["id"]}: explicit source.in/out required, out > in')
        text=s.get('say','')+s.get('on_screen_text','')+(src.get('ref','') if kind=='text' else '')
        if has_long_dash(text): err('long dash in scene text')
        if count_emoji(s.get('on_screen_text','')+(src.get('ref','') if kind=='text' else '')): err('emoji in frame')
    return out


def _probe(path):
    z=ffprobe(path); return z,float(z['format']['duration'])


def _ff(args):
    return run(['ffmpeg','-y','-v','error','-nostdin','-threads','2',*args])


def _font(size):
    return ImageFont.truetype(str(skill_root()/'assets/fonts/Manrope-Bold.ttf'),size)


def _text_image(path,text,w,h):
    im=Image.new('RGB',(w,h),'#15191E'); d=ImageDraw.Draw(im); f=_font(int(h*.065))
    lines=[]; line=''
    for word in text.split():
        test=(line+' '+word).strip()
        if d.textbbox((0,0),test,font=f)[2]>w*.82 and line: lines.append(line); line=word
        else: line=test
    if line: lines.append(line)
    if len(lines)>10: raise ShortsError('long text card too long; split into scenes')
    y=h*.5-len(lines)*h*.085/2
    for line in lines: d.text((w*.09,y),line,font=f,fill='#F4F2EA'); y+=h*.085
    im.save(path)


def _srt(words,path):
    def ts(t):
        ms=round(t*1000); s,ms=divmod(ms,1000); m,s=divmod(s,60); h,m=divmod(m,60)
        return f'{h:02}:{m:02}:{s:02},{ms:03}'
    lines=[]
    for i in range(0,len(words),8):
        a=words[i:i+8]; lines += [str(i//8+1),f'{ts(a[0]["s"])} --> {ts(a[-1]["e"])}',' '.join(x['w'] for x in a),'']
    path.write_text('\n'.join(lines),encoding='utf-8')


def render_long(p,base,out,keep_work=False):
    from ..plan import check,errors,resolve_ref
    from . import tts
    bad=errors(check(p,base))
    if bad: raise ShortsError('\n'.join(map(str,bad)))
    out=out.resolve();out.mkdir(parents=True,exist_ok=True); work=out/'work-long'
    if work.exists(): shutil.rmtree(work)
    work.mkdir(); t0=time.monotonic(); v=p['video']; w,h=v.get('width',1920),v.get('height',1080)
    fps=p['meta'].get('fps',30); total=0.; scenes=[]; words=[]; files=[]
    for i,s in enumerate(p['scenes']):
        src=s['source']; kind=src['type']; start=float(src.get('in',0)); notes=[]
        duration=float(s.get('duration') or (float(src.get('out',0))-start))
        narr=None; ws=s.get('transcript',[])
        if s.get('narration'): narr=resolve_ref(s['narration'],base)
        if s.get('say'):
            voice=p.get('audio',{}).get('voice',{}); speech=tts.synth(s['say'],lang=p['meta'].get('language','ru'),**{k:voice[k] for k in ('engine','voice','speed') if k in voice})
            narr=speech.wav; ws=speech.words; notes.append(f'TTS {speech.engine}, estimated={speech.estimated}')
            duration=max(duration,speech.duration+.35)
        if narr:
            _,nd=_probe(narr)
            if nd>duration+.05: raise ShortsError(f'{s["id"]}: narration longer than scene; extend duration')
        if duration<=0: raise ShortsError('nonpositive long scene duration')
        duration=round(duration*fps)/fps
        args=[]; has_audio=False
        if kind in ('video','film'):
            path=resolve_ref(src['ref'],base); info,sd=_probe(path)
            available=min(float(src['out']),sd)-start
            if start<0 or duration>available+1/fps: raise ShortsError(f'{s["id"]}: source shorter than requested scene; no silent freeze/loop allowed')
            args=['-ss',str(start),'-i',str(path)]; has_audio=any(x['codec_type']=='audio' for x in info['streams']) and src.get('keep_audio',True)
        else:
            path=work/f'card-{i}.png'
            if kind=='text': _text_image(path,src.get('ref',''),w,h)
            else: path=resolve_ref(src['images'][0],base)
            args=['-loop','1','-i',str(path)]
        if narr: args+=['-i',str(narr)]; audio_map='1:a:0'
        elif has_audio: audio_map='0:a:0'
        else: args+=['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']; audio_map='1:a:0'; notes.append('intentional silence')
        mode=v.get('fit','contain')
        vf=(f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x15191E' if mode=='contain' else f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}')
        vf+=f',setsar=1,fps={fps}'
        v_args=['-vf',vf]; video_map='0:v:0'
        if s.get('on_screen_text'):
            label=work/f'label-{i}.png';im=Image.new('RGBA',(w,h),(0,0,0,0));draw=ImageDraw.Draw(im)
            txt=s['on_screen_text'];font=_font(int(h*.045));box=draw.textbbox((0,0),txt,font=font)
            if box[2]-box[0]>w*.88: raise ShortsError('long on_screen_text too wide; shorten it')
            x,y=int(w*.06),int(h*.08);draw.rectangle((x-12,y-12,x+box[2]+12,y+box[3]+12),fill='#15191E')
            draw.text((x,y),txt,font=font,fill='#F4F2EA');im.save(label)
            idx=2 if narr or not has_audio else 1
            args+=['-loop','1','-i',str(label)]
            v_args=['-filter_complex',f'[0:v]{vf}[base];[base][{idx}:v]overlay=0:0[v]'];video_map='[v]'
        seg=work/f'{i:05}.mp4'
        _ff([*args,'-t',str(duration),'-map',video_map,'-map',audio_map,*v_args,'-af','apad,aresample=48000','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-ac','2','-ar','48000','-threads','2',str(seg)])
        files.append(seg)
        for x in ws:
            if not (0<=x['s']<x['e']<=duration+.05): raise ShortsError('transcript timing outside scene')
            words.append({'w':x['w'],'s':total+x['s'],'e':total+x['e']})
        scenes.append(dict(id=s['id'],type=kind,start=total,length=duration,skipped=None,notes=notes,source=src,say=s.get('say',''),on_screen_text=s.get('on_screen_text',''),why=s.get('why','')))
        total+=duration
    concat=work/'concat.txt';concat.write_text(''.join(f"file '{x.name}'\n" for x in files))
    name=p['meta'].get('name','long'); name=''.join(c if c.isalnum() or c in '-_' else '-' for c in name) or 'long'
    joined=work/'joined.mp4';_ff(['-f','concat','-safe','1','-i',str(concat),'-c','copy',str(joined)])
    dest=out/f'{name}.mp4'; target=p.get('audio',{}).get('target_lufs',-14)
    from .audio import loudnorm
    norm=work/'normal.wav'; audio_rep=loudnorm(joined,norm,target)
    _ff(['-i',str(joined),'-i',str(norm),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-ar','48000','-t',str(total),'-movflags','+faststart',str(dest)])
    m=dict(engine='shorts',version=(skill_root()/'VERSION').read_text().strip(),format='long',schema_version='1.4',name=name,video=dest.name,plan_dir=str(base),fps=fps,duration=total,width=w,height=h,language=p['meta'].get('language','ru'),platforms=['youtube'],duration_target=p['meta'].get('duration_target'),loop=False,scenes=scenes,captions={'words_spoken':words,'enabled':bool(words)},brand={'palette':{'bg':'#15191E','fg':'#F4F2EA','accent':'#42D6B3'}},render_seconds=round(time.monotonic()-t0,2),audio=audio_rep,author_layer={'credits':[]})
    write_json(out/'manifest.json',m);write_json(out/'plan.resolved.json',p);K.write_render_output(out,m,'1.4');_srt(words,out/f'{name}.srt')
    (out/'chapters.txt').write_text('\n'.join(f'{int(s["start"])//60:02}:{int(s["start"])%60:02} {s["id"]}' for s in scenes)+'\n')
    if not keep_work: shutil.rmtree(work)
    return m


def qa_long(d,strict=False):
    from .audio import measure
    m=read_json(d/'manifest.json'); video=d/m['video']; z,dur=_probe(video);checks=[]
    def add(id,status,detail='',data=None): checks.append(dict(id=id,item=0,title=id,status=status,ok=status!='fail',detail=detail,data=data or {}))
    v=next(x for x in z['streams'] if x['codec_type']=='video');a=next((x for x in z['streams'] if x['codec_type']=='audio'),{})
    fps=eval_rate(v['avg_frame_rate'])
    good=(v['width'],v['height'])==(m['width'],m['height']) and v['codec_name']=='h264' and a.get('codec_name')=='aac' and abs(fps-m['fps'])<.01 and abs(dur-m['duration'])<.15
    tgt=m.get('duration_target'); good=good and (not tgt or tgt[0]-.15<=dur<=tgt[1]+.15)
    add('format','pass' if good else 'fail',data={'duration':dur,'w':v['width'],'h':v['height'],'fps':fps})
    proc=subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(video),'-f','null','-'],capture_output=True)
    add('decode','pass' if proc.returncode==0 else 'fail',proc.stderr.decode()[-500:])
    measured=measure(video); val=measured.get('integrated_lufs',measured.get('lufs'))
    target=read_json(d/'plan.resolved.json').get('audio',{}).get('target_lufs',-14)
    peak=measured.get('true_peak')
    add('audio_loudness','pass' if val is not None and math.isfinite(val) and abs(val-target)<=1.5 and (peak is None or peak<=0) else 'warn','silence/outside target requires listening',measured)
    # Streaming detectors report candidates, not editorial defects.
    det=subprocess.run(['ffmpeg','-hide_banner','-i',str(video),'-vf','blackdetect=d=0.3:pix_th=0.10','-af','silencedetect=noise=-45dB:d=1','-f','null','-'],capture_output=True)
    hits=[x for x in det.stderr.decode().splitlines() if 'black_start:' in x or 'silence_start:' in x or 'silence_end:' in x]
    add('black_silence','warn' if hits else 'pass','candidates only',{'events':hits[:200],'truncated':len(hits)>200})
    q=d/'qa-frames';q.mkdir(exist_ok=True); thumbs=[]
    # No all-video frame array: <=32 samples, 320x180 thumbnails.
    for i in range(min(32,max(2,math.ceil(dur/20)))):
        t=min(dur-.05,i*dur/min(32,max(2,math.ceil(dur/20))))
        f=q/f'{i:03}.jpg';_ff(['-ss',str(t),'-i',str(video),'-frames:v','1','-vf','scale=320:180',str(f)])
        with Image.open(f) as im: thumbs.append(im.copy())
    sheet=Image.new('RGB',(1280,math.ceil(len(thumbs)/4)*205),'#15191E');draw=ImageDraw.Draw(sheet)
    for i,im in enumerate(thumbs):
        x,y=(i%4)*320,(i//4)*205;sheet.paste(im,(x,y));draw.text((x+5,y+181),str(i),fill='white')
    sheet.save(d/'contact-001.png');shutil.copyfile(d/'contact-001.png',d/'contact.png')
    for id,rel in (('metadata','metadata.json'),('covers','cover/cover.json')):
        path=d/rel
        if not path.exists(): add(id,'fail' if strict else 'warn',f'{rel} missing')
        else:
            data=read_json(path); errs=data.get('errors') or []
            add(id,'fail' if errs and strict else ('warn' if errs else 'pass'),'; '.join(map(str,errs)))
    add('eyes','manual','Review framing, text and transitions',{'contact_sheets':['contact-001.png']})
    add('silent','manual','Retell without sound')
    add('motion_audio','manual','Watch whole video with movement and sound; contact sheet does not satisfy this')
    passed=all(x['ok'] for x in checks); rep=dict(ok=passed,passed=passed,checks=checks,summary='QA PASSED (technical only)' if passed else 'QA FAILED',video_sha256=file_hash(video),**K.qa_extras(checks))
    write_json(d/'qa.json',rep);(d/'qa.md').write_text('# Long QA\n\n'+rep['summary']+'\n\n'+'\n'.join(f'- {x["id"]}: {x["status"]} {x["detail"]}' for x in checks)+'\n')
    return rep


def eval_rate(s):
    a,b=s.split('/');return float(a)/float(b)


def cover_long(d,image=None,text=None):
    m=read_json(d/'manifest.json');p=read_json(d/'plan.resolved.json');out=d/'cover';out.mkdir(exist_ok=True)
    meta=read_json(d/'metadata.json') if (d/'metadata.json').exists() else {}
    text=text or meta.get('cover_text') or p.get('metadata',{}).get('cover_text') or m['name']
    if has_long_dash(text) or count_emoji(text): raise ShortsError('invalid cover text')
    src=out/'source.jpg'
    if image: Image.open(image).convert('RGB').resize((1280,720)).save(src)
    else: _ff(['-ss',str(min(2,m['duration']/3)),'-i',str(d/m['video']),'-frames:v','1','-vf','scale=1280:720',str(src)])
    variants=[]; errors=[]
    for k in ('A','B','C'):
        im=Image.open(src).convert('RGB');draw=ImageDraw.Draw(im);font=_font(110)
        lines=[];line=''
        for word in text.split():
            test=(line+' '+word).strip()
            if draw.textbbox((0,0),test,font=font)[2]>1080 and line: lines.append(line);line=word
            else: line=test
        if line: lines.append(line)
        if len(lines)>3: errors.append('cover text too long')
        line_h=128
        y={'A':45,'B':max(30,680-line_h*len(lines)),'C':max(30,(720-line_h*len(lines))//2)}[k]
        draw.rectangle((50,y-15,1230,min(710,y+line_h*len(lines))),fill='#15191E')
        for line in lines[:3]: draw.text((75,y),line,font=font,fill='#F4F2EA');y+=line_h
        f=out/f'cover-{k}-16x9.png';im.save(f);im.resize((150,84)).save(out/f'cover-{k}-16x9-150.png')
        variants.append({'variant':'long_text','format':'16x9','file':f.name,'text':text,'errors':[]})
    result={'variants':variants,'errors':errors,'generated':False,'note':'Text layout variants, not proven separate creative concepts; review 150 px manually'}
    write_json(out/'cover.json',result);return result


def file_hash(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()
