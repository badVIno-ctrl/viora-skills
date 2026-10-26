import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from shortskit.engine.banner import AnimatedBanner,keyframe
from shortskit.engine.captions import to_srt
from shortskit.release import parse_srt,srt_issues,speech_issues,chapters_issues,description_issues
from shortskit.recovery import resolve
from shortskit.util import ShortsError

FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
def brand():
    from shortskit.engine.brand import load_font
    from shortskit.config import asset
    # Use the actual bundled typeface, not environment-specific paths.
    f=next((asset('fonts')).rglob('*.ttf'))
    return SimpleNamespace(body=SimpleNamespace(path=f),display=SimpleNamespace(path=f),logo_text='')

URLS=['https://telegram.me/QuattroVPN_BOT?start=r_O0Xa5v9BEFVvRioY','https://t.me/bobvpn_robot?start=ref_5771810401']
@pytest.mark.parametrize('variant,url',list(zip(['quattro','bob'],URLS)))
def test_independent_banner_tracks_and_still_qr(variant,url):
    b=AnimatedBanner(1080,384,brand(),{'name':'QuattroVPN' if variant=='quattro' else 'Боб VPN','handle':'QuattroVPN_BOT' if variant=='quattro' else 'bobvpn_robot','qr_url':url,'animation':{'variant':variant}})
    arr=[np.asarray(b(t)) for t in [.1,.6,1.1,1.8,2.9,3.8,5,8]]
    x,y,w,h=b.qr_box
    assert all(np.array_equal(arr[0][y:y+h,x:x+w],a[y:y+h,x:x+w]) for a in arr)
    for k in ['logo','title','message','cta']:
        x,y,w,h=b.rois[k]
        assert max(np.abs(a[y:y+h,x:x+w].astype(float)-z[y:y+h,x:x+w]).mean() for a,z in zip(arr,arr[1:]))>1
    assert np.array_equal(np.asarray(b(5)),np.asarray(b(8))) # quiet QR hold, no constant shake
    import cv2
    assert cv2.QRCodeDetector().detectAndDecode(np.asarray(b(5).convert('RGB')))[0]==url

def test_keyframes_easing_and_hold():
    keys=[{'t':0,'value':0},{'t':1,'value':1,'ease':'out_cubic'}]
    assert keyframe(keys,.5)==.875 and keyframe(keys,2)==1

@pytest.mark.parametrize('value',[0,1,2])
def test_speech_boundary_regressions(value):
    e={k:True for k in ['context_before_reviewed','context_after_reviewed','first_word_complete','last_word_complete','thought_complete','answer_complete','natural_reaction_preserved','audio_listened']}
    e.update(start=2,end=5)
    if value==0:e['continuation_after_end']=True
    if value==1:e['context_words']=[{'s':4.8,'e':5.2}]
    if value==2:e['answer_complete']=False # grammar is complete, answer is not
    assert speech_issues(e)

def test_missing_listening_never_passes():
    assert speech_issues({})

def test_srt_padding_is_clamped_to_next_cue():
    words=[{'s':0,'e':1,'w':'Привет.'},{'s':1.05,'e':2,'w':'Ответ.'}]
    assert not srt_issues(parse_srt(to_srt(words)),2.2)
    assert parse_srt(to_srt(words))[0]['e']==1.05

def test_final_timestamps():
    assert not chapters_issues(['00:00 - Вход','00:12 - Ответ'],20)
    assert chapters_issues(['00:00 - Вход','00:20 - Ответ'],20)
    assert chapters_issues(['00:00 - Вход','00:12 - Ответ','00:10 - Повтор'],20)

@pytest.mark.parametrize('text',['Агент должен исправить обложку','Полное видео - на канале.','{{SUMMARY}}','00:00:01,200 --> 00:00:02,200'])
def test_dirty_copy_rejected(text):
    assert description_issues(text)

def test_single_fetch_failure_tries_browser(tmp_path):
    p=tmp_path/'ok.mp4';p.write_bytes(b'fixture')
    seen=[]
    def bad(u):seen.append('download');raise ShortsError('loader failed')
    def good(u):seen.append('browser');return p
    path,log=resolve({'url':'https://example.com/original'},bad,good,journal=tmp_path/'log.json')
    assert path==p and seen==['download','browser']
    assert log[0]['state']=='downloader_failed'

def test_next_verified_copy_and_no_masquerade(tmp_path):
    p=tmp_path/'ok.mp4';p.write_bytes(b'fixture');seen=[]
    def fetch(u):
        seen.append(u)
        if u.endswith('original'):raise ShortsError('failed')
        return p
    req={'url':'https://example.com/original','copies':[{'url':'https://example.com/similar','relation':'replacement','identity_verified':True},{'url':'https://example.com/copy','relation':'same_material','identity_verified':True,'identity_evidence':'same speaker, scene, line, episode and audio verified'}]}
    path,log=resolve(req,fetch)
    assert seen==['https://example.com/original','https://example.com/copy']
    assert any(x['state']=='identity_unverified' for x in log)

def test_unverified_discovery_does_not_become_original(tmp_path):
    def fail(u):raise ShortsError('failed')
    with pytest.raises(ShortsError):resolve({'url':'https://example.com/a','title':'a'},fail,discovery=lambda _: [{'url':'https://example.com/lookalike'}],journal=tmp_path/'journal.json')
    log=json.loads((tmp_path/'journal.json').read_text());assert log[-1]['state']=='no_verified_copy'

def test_bpm_alone_cannot_validate_a_music_edit():
    from shortskit.editorial import check_cut
    rep=check_cut({'music_required':True,'bpm':150,'music_listened':False})
    assert not rep['ready'] and any('BPM' in i for i in rep['issues'])

def test_effect_role_not_effect_count():
    from shortskit.editorial import check_cut
    rep=check_cut({'shot_bank':[{'id':'a'}],'timeline':[{'shot':'a','effect':'mask'}]})
    assert any('motivated role' in i for i in rep['issues'])

def test_legacy_layout_preserved_and_reserved_area_is_explicit():
    from shortskit.engine.layout import compute
    a=compute({'mode':'center_bottom','bottom':{'height_pct':20}},['youtube_shorts'])
    b=compute({'mode':'center_bottom','bottom':{'height_pct':20,'reserve_bottom_pct':16}},['youtube_shorts'])
    assert a.bottom.y==1536 and b.bottom.y<a.bottom.y
    assert b.center.h<a.center.h and b.center_pct>=55

def test_no_cross_job_advertising_and_qr_link_keeps_case():
    from shortskit.meta.packaging import _links
    prefs={'links':{'old':'https://t.me/OTHER_AD'}}
    assert _links({'scenes':[{'source':{'type':'film'}}]},prefs)==[]
    plan={'layout':{'bottom':{'qr_url':URLS[0]}}}
    assert _links(plan,prefs)==[('',URLS[0])]

def test_download_wrapper_reaches_verified_copy(tmp_path,monkeypatch):
    from shortskit.adapters import media
    import shortskit.recovery as recovery
    p=tmp_path/'copy.mp4';p.write_bytes(b'ok');seen=[]
    def fetch(url,*args):
        seen.append(url)
        if 'original' in url:raise ShortsError('single loader failure')
        return p
    monkeypatch.setattr(media,'_ytdlp_section',fetch)
    monkeypatch.setattr(recovery,'registry_request',lambda url:{'url':url,'copies':[{'url':'https://example.com/copy','relation':'same_material','identity_verified':True,'identity_evidence':'verified scene and speaker'}]})
    from shortskit.adapters import ytbrowser
    monkeypatch.setattr(ytbrowser,'available',lambda:False)
    assert media.download_section('https://example.com/original',0,1)==p
    assert seen==['https://example.com/original','https://example.com/copy']


def test_banner_manifest_before_first_frame_has_cta():
    b=AnimatedBanner(1080,384,brand(),{'name':'VPN','animation':{}})
    b(0)
    assert all(k in b.manifest()['element_boxes'] for k in ('logo','title','message','cta'))
