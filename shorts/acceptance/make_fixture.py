"""Reproducible educational AV fixtures, no external material or asserted audience metrics.
Run from project root: python3 acceptance/make_fixture.py [--long]
Audio is synthetic tones, not speech. Actual listening cannot be inferred from this script.
"""
from pathlib import Path
import json, math, subprocess, sys
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter
R=Path(__file__).resolve().parents[1]; D=R/'acceptance/fixture';D.mkdir(exist_ok=True)
fontpath=R/'assets/fonts/Manrope-Bold.ttf'
def save(name,x): (D/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def ff(args): subprocess.run(['ffmpeg','-y','-v','error',*map(str,args)],check=True)
def raw_movie():
 w,h,fps=540,960,15;dur=36
 p=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','veryfast','-threads','2','-pix_fmt','yuv420p',str(D/'raw-silent.mp4')],stdin=subprocess.PIPE)
 stages=[('ПОДОЖДИ...', 'ЗАСТАВКА'),('1. УБЕРИ ВОДУ', 'ДУБЛЬ A: МЕЛКО'),('1. УБЕРИ ВОДУ','ШАГ 1'),('2. ПОКАЖИ ШАГИ','ШАГ 2'),('РЕЗУЛЬТАТ СРАЗУ','ГОТОВАЯ СТРУКТУРА'),('НУ ВОТ И ВСЁ','ХВОСТ')]
 for k in range(dur*fps):
  t=k/fps;j=int(t//6);im=Image.new('RGB',(w,h),'#15191E');d=ImageDraw.Draw(im)
  f=ImageFont.truetype(str(fontpath),26 if j!=1 else 13);small=ImageFont.truetype(str(fontpath),16)
  d.text((32,180),stages[j][1],font=small,fill='#F4F2EA');d.text((32,230),stages[j][0],font=f,fill='#F4F2EA')
  if j not in (0,5):
   # Editorial timeline diagram, deliberately code-native instructional geometry.
   for a in range(6):
    x=40+a*76;y=365+int(20*math.sin(t*1.6+a));d.rectangle((x,y,x+58,y+70),outline='#42D6B3',width=3)
    d.text((x+13,y+23),str(a+1),font=small,fill='#F4F2EA')
   x=40+int((t%6)/6*440);d.line((x,350,x,480),fill='#F4F2EA',width=4)
   d.text((32,505),'ХУК  >  ШАГИ  >  ИТОГ',font=small,fill='#F4F2EA')
  if j==1: im=im.filter(ImageFilter.GaussianBlur(1.4))
  p.stdin.write(np.asarray(im).tobytes())
 p.stdin.close();assert p.wait()==0
 # Intro and tail are silent; weak A has much louder tone. Content has changing tones.
 ff(['-i',D/'raw-silent.mp4','-f','lavfi','-i',r"aevalsrc=if(between(t\,6\,12)\,0.7*sin(2*PI*300*t)\,if(between(t\,12\,30)\,0.12*sin(2*PI*(440+55*floor(t/6))*t)\,0)):s=48000:d=36",'-c:v','copy','-c:a','aac','-shortest',D/'weak-before.mp4'])
 (D/'raw-silent.mp4').unlink()
base={'schema_version':'1.4','meta':{'name':'take-rebuild','language':'ru','platforms':['youtube_shorts'],'duration_target':[17,19],'fps':30,'loop':False,'pacing':'meaning','genre':'tutorial'},'layout':{'mode':'center_only','cta_in_center':[]},'brand':{'preset':'mono'},'captions':{'enabled':False},'audio':{'target_lufs':-14,'sfx_auto':False},'author_layer':[{'kind':'own_footage','note':'generated educational timeline'},{'kind':'thesis','note':'result then useful steps'}], 'metadata':{'topic':'Как убрать заставку и показать результат первым','cover_text':'РЕЗУЛЬТАТ СРАЗУ','hashtags':['#монтаж']}}
sc=[]
for id,a,z,why in [('result',24,30,'реальный результат вместо заставки'),('step1',12,18,'убрать воду'),('step2',18,24,'показать шаги')]:
 sc.append({'id':id,'why':why,'duration':z-a,'source':{'type':'video','ref':'weak-before.mp4','in':a,'out':z,'keep_audio':True}})
base['scenes']=sc
if not (D/'weak-before.mp4').exists():raw_movie()
save('short.plan.json',base)
# Long technical fixture: four different 120-second source blocks, time counter, motion, tone.
if '--long' in sys.argv:
 for i in range(4):
  file=D/f'block-{i+1}.mp4'
  if not file.exists():
   w,h,fps=640,360,15
   silent=D/f'block-{i+1}-silent.mp4'
   pipe=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','640x360','-r','15','-i','-','-an','-c:v','libx264','-preset','veryfast','-threads','2','-pix_fmt','yuv420p',str(silent)],stdin=subprocess.PIPE)
   title=['РЕЗУЛЬТАТ И ПЛАН','ПОШАГОВАЯ ПРОВЕРКА','СРАВНЕНИЕ БЛОКОВ','ИТОГ И ОГРАНИЧЕНИЯ'][i]
   f=ImageFont.truetype(str(fontpath),26);small=ImageFont.truetype(str(fontpath),17)
   for frame in range(120*fps):
    t=frame/fps; im=Image.new('RGB',(w,h),'#15191E');draw=ImageDraw.Draw(im)
    draw.text((32,30),title,font=f,fill='#F4F2EA')
    draw.text((32,76),f'УЧЕБНЫЙ ТЕСТ | БЛОК {i+1} | {t:06.2f} с',font=small,fill='#F4F2EA')
    for k in range(8):
     x=40+k*72;y=170+int(25*math.sin(t*.8+k+i));draw.rectangle((x,y,x+52,y+65),outline='#42D6B3',width=3)
     draw.text((x+17,y+22),str(k+1),font=small,fill='#F4F2EA')
    x=int(40+(t%20)/20*560);draw.line((x,145,x,280),fill='#F4F2EA',width=3)
    draw.text((32,310),'Движение + счётчик времени + синтетический тон',font=small,fill='#F4F2EA')
    pipe.stdin.write(np.asarray(im).tobytes())
   pipe.stdin.close();assert pipe.wait()==0
   ff(['-i',silent,'-f','lavfi','-i',f'sine=frequency={440+i*110}:sample_rate=48000:duration=120','-c:v','copy','-c:a','aac','-shortest',file]);silent.unlink()
 long={'schema_version':'1.4','video':{'format':'long','width':1280,'height':720,'fit':'contain'},'meta':{'name':'long-8min-training','language':'ru','platforms':['youtube'],'fps':30,'loop':False,'duration_target':[479,481]},'layout':{'mode':'center_only'},'brand':{'preset':'mono'},'captions':{'enabled':False},'audio':{'target_lufs':-14,'sfx_auto':False},'metadata':{'topic':'Учебная проверка длинного экспорта','cover_text':'8 МИНУТ ЭКСПОРТА','hashtags':['#проверка']},'scenes':[{'id':f'chapter-{i+1}','why':'учебная техническая проверка, не готовый урок','duration':120,'source':{'type':'video','ref':f'block-{i+1}.mp4','in':0,'out':120,'keep_audio':True}} for i in range(4)]}
 save('long.plan.json',long)
print('Fixtures ready:',D)
