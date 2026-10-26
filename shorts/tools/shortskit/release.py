"""Publication checks independent of technical decoding. Missing evidence blocks ready status."""
from __future__ import annotations
import re, json
from pathlib import Path

def parse_srt(text):
    cues=[]
    def sec(s):
        h,m,s=s.replace(',','.').split(':');return int(h)*3600+int(m)*60+float(s)
    for block in re.split(r'\n\s*\n',text.strip()):
        ls=block.splitlines()
        if not ls:continue
        i=next((j for j,l in enumerate(ls) if '-->' in l),None)
        if i is None:raise ValueError('SRT cue missing time interval')
        a,b=ls[i].split('-->');cues.append({'s':sec(a.strip()),'e':sec(b.strip()),'text':' '.join(ls[i+1:])})
    return cues

def srt_issues(cues,duration):
    issues=[]
    for i,c in enumerate(cues):
        if not 0<=c['s']<c['e']<=duration+.001:issues.append(f'cue {i+1}: invalid bounds')
        if i and cues[i-1]['e']>c['s']+.0005:issues.append(f'cue {i+1}: unintended overlap')
        if not c['text'].strip():issues.append(f'cue {i+1}: empty text')
    return issues

def speech_issues(evidence):
    if not evidence:return ['speech boundary evidence missing']
    errors=[]
    for key in ('context_before_reviewed','context_after_reviewed','first_word_complete','last_word_complete','thought_complete','answer_complete','natural_reaction_preserved','audio_listened'):
        if evidence.get(key) is not True:errors.append(key+' not confirmed')
    a,b=evidence.get('start',0),evidence.get('end',0)
    for w in evidence.get('context_words',[]):
        if w['s']<a<w['e'] or w['s']<b<w['e']:errors.append('word crosses boundary')
    if evidence.get('continuation_after_end'):errors.append('thought continues beyond selected window')
    return errors

def chapters_issues(lines,duration):
    last=-1;issues=[]
    for line in lines:
        m=re.fullmatch(r'(\d{2,}):(\d{2})(?::(\d{2}))? - (\S.*)',line)
        if not m:issues.append('invalid chapter format: '+line);continue
        a,b,c=m.group(1,2,3);t=int(a)*60+int(b) if c is None else int(a)*3600+int(b)*60+int(c)
        if int(b)>=60 or (c is not None and int(c)>=60):issues.append('invalid timestamp')
        if t<=last or not 0<=t<duration:issues.append('timestamp outside final timeline/order')
        if last<0 and t!=0:issues.append('first timestamp must be 00:00')
        last=t
    return issues

def description_issues(text,full_video_url=None):
    errors=[]
    for pattern in [r'агент.{0,40}(исправ|провери)',r'TODO|TBD|\{\{.+?\}\}',r'незаполненн',r'заменить обложку',r'-->',r'\d{2}:\d{2}:\d{2},\d{3}']:
        if re.search(pattern,text,re.I):errors.append('internal note/template/SRT in publication copy')
    if re.search(r'полное видео.{0,8}на канале|full video.{0,8}channel',text,re.I) and not full_video_url:errors.append('unverified full-video claim')
    return errors

AD_MARKERS=re.compile(r'промокод|promo[\s-]?code|партн[её]рск|affiliate|utm_[a-z]+=|[?&]ref=|реферал|referral|скидк|#ad\b|#реклама|реклама|на правах рекламы|спонсор|sponsored|paid partnership|по моей ссылке',re.I)

def unrecognised_ad_issues(d,m):
    """Heuristic: wording that usually means promotion, with no campaign.json and no explicit advertising=false + reason.
    A hit proves nothing; it only forces an explicit human decision. Absence of hits does not prove the video is not an ad."""
    if m.get('advertising') is True or (d/'campaign.json').exists():
        return []
    chunks=[]
    p=d/'ОПИСАНИЕ.txt'
    if p.exists():chunks.append(p.read_text(errors='replace'))
    for k,v in m.items():
        if isinstance(v,str) and k!='advertising_reason':chunks.append(v)
    hits=sorted({x.group(0).lower() for x in AD_MARKERS.finditer('\n'.join(chunks))})
    if not hits:
        return []
    reason=(m.get('advertising_reason') or '').strip()
    if m.get('advertising') is False and len(reason)>=10:
        return []
    return ['possible advertising wording ('+', '.join(hits[:5])+') without campaign.json: create it with ad-init and run ad-check, or set advertising=false with advertising_reason (10+ characters) after a human decision']

def audit(directory):
    d=Path(directory);m=json.loads((d/'release.json').read_text());duration=m['duration'];issues=[]
    for p in d.glob('*.srt'):issues+=srt_issues(parse_srt(p.read_text()),duration)
    desc=(d/'ОПИСАНИЕ.txt').read_text() if (d/'ОПИСАНИЕ.txt').exists() else ''
    issues+=description_issues(desc,m.get('full_video_url'))
    if not desc:issues.append('publication description missing')
    issues+=chapters_issues(m.get('chapters',[]),duration)
    if m.get('contains_speech'):issues+=speech_issues(m.get('speech'))
    for k in ['motion_reviewed','audio_listened','editorial_accepted','sources_verified','ui_overlay_reviewed']:
        if m.get(k) is not True:issues.append(k+' not confirmed')
    if m.get('music_required') and m.get('exact_music_verified') is not True:issues.append('exact music not verified')
    if m.get('qr_required') and m.get('final_qr_verified') is not True:issues.append('final QR not verified')
    issues+=unrecognised_ad_issues(d,m)
    advertising = None
    if m.get('advertising') is True or (d/'campaign.json').exists():
        from .advertising import audit as ad_audit
        advertising = ad_audit(d, 'launch')
        issues += ['advertising: ' + item for item in advertising['issues']]
    result = {'ready':not issues,'issues':issues,'technical_qa':'separate','publication_performance':'not predicted'}
    if advertising is not None:
        result['advertising'] = advertising
    return result
