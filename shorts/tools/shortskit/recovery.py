"""Bounded, auditable acquisition. Downloader failure != absent material.
Registry records are explicit verified copies, not replacements. Discovery is untrusted.
"""
from __future__ import annotations
import json, os, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from pathlib import Path
from .util import ShortsError

STATES=('downloader_failed','playback_failed','no_verified_copy','authorization_required','quality_unusable','identity_unverified')

def discover(title, limit=5):
    # Public search; does not execute third-party binaries, use proxies, cookies or DRM workarounds.
    query='"'+title+'" официальный видео rutube vk dzen'
    url='https://www.bing.com/search?format=rss&q='+urllib.parse.quote(query)
    try:
        root=ET.fromstring(urllib.request.urlopen(url,timeout=15).read())
        return [{'url':e.findtext('link'),'title':e.findtext('title'),'relation':'unverified','identity_verified':False}
                for e in root.findall('./channel/item')[:limit]]
    except Exception as e:
        return [{'discovery_error':str(e)[:250]}]

def resolve(request, fetch, browser=None, discovery=discover, journal=None, max_attempts=6):
    log=[];attempts=0;seen=set()
    def save():
        if journal:
            p=Path(journal);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(log,ensure_ascii=False,indent=2))
    original=request['url'];queue=[{'url':original,'relation':'original','identity_verified':True}]+request.get('copies',[])
    for c in queue[:max_attempts]:
        u=c.get('url');relation=c.get('relation','unverified')
        if not u or u in seen:continue
        seen.add(u)
        if relation not in ('original','same_material') or (relation=='same_material' and not (c.get('identity_verified') and c.get('identity_evidence'))):
            log.append({'url':u,'state':'identity_unverified','relation':relation,'reason':'Not a verified identical copy; no silent substitution'});continue
        if c.get('authorization_required'):
            log.append({'url':u,'state':'authorization_required'});continue
        if c.get('quality_usable') is False:
            log.append({'url':u,'state':'quality_unusable'});continue
        for method,fn in [('download',fetch),('browser',browser)]:
            if fn is None or attempts>=max_attempts:continue
            attempts+=1
            try:
                path=fn(u)
                if not Path(path).is_file() or Path(path).stat().st_size==0:raise ShortsError('empty/missing file')
                log.append({'url':u,'method':method,'state':'acquired','relation':relation,'path':str(path),
                            'quality_review':'required','identity_evidence':c.get('identity_evidence')});save();return Path(path),log
            except (ShortsError, OSError, ValueError) as e:
                log.append({'url':u,'method':method,'state':'downloader_failed' if method=='download' else 'playback_failed','reason':str(e)[-700:]})
    if request.get('title'):
        log.append({'state':'discovery','candidates':discovery(request['title'])})
    log.append({'state':'no_verified_copy','reason':'Bounded paths exhausted; unverified discovery is not proof that no copy exists'});save()
    raise ShortsError('No acquired verified copy. Review discovery and journal; do not substitute. '+str(journal or ''))

def registry_request(url):
    path=os.environ.get('SHORTS_SOURCE_REGISTRY')
    entries=json.loads(Path(path).read_text()) if path else {}
    return {'url':url,**entries.get(url,{})}
