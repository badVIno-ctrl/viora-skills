import copy,json,subprocess
from pathlib import Path
import pytest
from shortskit.plan import check, errors
from shortskit.engine.render import render
from shortskit.qa.gate import run_gate
from shortskit import memory as M
from shortskit.planner import skeleton

def lp(path,seconds=1):
 return {'schema_version':'1.4','video':{'format':'long','width':1280,'height':720},'meta':{'name':'long-test','language':'ru','platforms':['youtube'],'fps':30,'loop':False,'duration_target':[seconds-.1,seconds+.1]},'layout':{'mode':'center_only'},'brand':{'preset':'mono'},'captions':{'enabled':False},'audio':{'sfx_auto':False,'target_lufs':-14},'scenes':[{'id':'one','source':{'type':'video','ref':str(path),'in':0,'out':seconds,'keep_audio':True},'duration':seconds}]}
@pytest.fixture
def media(tmp_path):
 p=tmp_path/'media.mp4';subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','testsrc2=s=320x180:r=30:d=2','-f','lavfi','-i','sine=frequency=440:duration=2','-c:v','libx264','-preset','ultrafast','-threads','2','-c:a','aac','-shortest',str(p)],check=True);return p

def test_long_schema_and_migration(media,tmp_path):
 p=lp(media);assert not errors(check(p,tmp_path));p['schema_version']='1.3';assert errors(check(p,tmp_path))
@pytest.mark.parametrize('field,value',[('fx',{'punch':[1]}),('audio',{'music':{'source':'x'}}),('overlays',{'arrow':True})])
def test_reject_unsupported(media,tmp_path,field,value):
 p=lp(media);p[field]=value;assert errors(check(p,tmp_path))
def test_reject_long_layout_and_scene_effect(media,tmp_path):
 p=lp(media);p['layout']['cta_in_center']=[];assert errors(check(p,tmp_path))
 p=lp(media);p['scenes'][0]['trans']='dissolve';assert errors(check(p,tmp_path))
def test_long_public_render_qa_all(tmp_path,media):
 p=tmp_path/'plan.json';p.write_text(json.dumps(lp(media)))
 m=render(p,tmp_path/'out');assert m['format']=='long';assert (tmp_path/'out/result.json').exists()
 rep=run_gate(tmp_path/'out');assert rep['passed'];assert next(c for c in rep['checks'] if c['id']=='motion_audio')['status']=='manual'
 assert (tmp_path/'out/contact.png').exists();assert rep['video_sha256']
def test_short_source_cannot_freeze(tmp_path,media):
 plan=lp(media,3);p=tmp_path/'p.json';p.write_text(json.dumps(plan))
 with pytest.raises(Exception,match='shorter'):render(p,tmp_path/'out')
def test_niche_persist_reuse(tmp_path):
 M.set_value('brand.niche','учебный монтаж');profile={'audience':'начинающие','language':['результат'],'hypotheses':['ранний результат'],'updated_at':'2026-10-18'}
 M.set_value('brand.niche_profile',profile);p=skeleton('text',[],topic='тест');assert p['metadata']['niche_context']['niche_profile']==profile
 assert 'niche_profile' not in p['brand'];assert M.load()['brand']['niche_profile']==profile

def test_new_optional_pacing_version(tmp_path):
 from conftest import mini_plan
 p=mini_plan();p['meta']['pacing']='meaning';assert errors(check(p,tmp_path))


def test_genre_does_not_make_interview_a_film_edit():
 from shortskit.qa.edit import is_edit
 m={'schema_version':'1.4','genre':'interview','scenes':[{'id':'one','type':'video','skipped':None}]}
 assert not is_edit(m)
 m['schema_version']='1.3'
 assert is_edit(m)

def test_long_labels_images_narration(tmp_path,media):
 import subprocess
 audio=tmp_path/'a.wav';subprocess.run(['ffmpeg','-y','-v','error','-i',str(media),'-t','1',str(audio)],check=True)
 p=lp(media);p['scenes'][0]['narration']=str(audio);p['scenes'][0]['on_screen_text']='ПРОВЕРКА'
 path=tmp_path/'plan.json';path.write_text(json.dumps(p));out=tmp_path/'out'
 m=render(path,out);assert (out/m['video']).exists()
 p['scenes'][0]['source']={'type':'text','ref':'Текстовая карточка'};path.write_text(json.dumps(p))
 assert render(path,tmp_path/'text')['format']=='long'

def test_strict_long_requires_packaging(tmp_path,media):
 p=tmp_path/'plan.json';p.write_text(json.dumps(lp(media)))
 render(p,tmp_path/'out');rep=run_gate(tmp_path/'out',strict=True)
 assert not rep['passed']
 assert next(c for c in rep['checks'] if c['id']=='metadata')['status']=='fail'

def test_long_actual_cli_all(tmp_path,media):
 import sys
 from conftest import ROOT
 p=tmp_path/'p.json';p.write_text(json.dumps(lp(media)))
 completed=subprocess.run([sys.executable,str(ROOT/'tools/shorts.py'),'all',str(p),'--out',str(tmp_path/'all')],capture_output=True,text=True)
 assert completed.returncode==0,completed.stdout+completed.stderr
 assert json.loads((tmp_path/'all/all.json').read_text())['qa_passed']
 assert (tmp_path/'all/ПАКЕТ.txt').exists()
