import json,subprocess
from pathlib import Path
import numpy as np
import pytest
from shortskit.engine.banner import AnimatedBanner
from shortskit.qa.banner import inspect_video
from types import SimpleNamespace
from shortskit.config import asset
URLS=["https://telegram.me/QuattroVPN_BOT?start=r_O0Xa5v9BEFVvRioY","https://t.me/bobvpn_robot?start=ref_5771810401"]
def brand():
    f=next(asset("fonts").rglob("*.ttf"));return SimpleNamespace(body=SimpleNamespace(path=f),display=SimpleNamespace(path=f),logo_text="")

@pytest.mark.parametrize('variant,url',list(zip(['quattro','bob'],URLS)))
def test_compressed_banner_motion_and_exact_referral(tmp_path,variant,url):
    b=AnimatedBanner(1080,384,brand(),{'name':'QuattroVPN' if variant=='quattro' else 'Боб VPN','handle':'QuattroVPN_BOT' if variant=='quattro' else 'bobvpn_robot','qr_url':url,'animation':{'variant':variant}})
    p=tmp_path/'ad.mp4'
    proc=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','1080x384','-r','15','-i','-','-c:v','libx264','-threads','2','-preset','fast','-crf','23','-pix_fmt','yuv420p',str(p)],stdin=subprocess.PIPE)
    for k in range(135):proc.stdin.write(b(k/15).convert('RGB').tobytes())
    proc.stdin.close();assert proc.wait()==0
    rep=inspect_video(p,b.manifest(),[0,0,1080,384]);assert rep['motion_verified'],rep
    assert rep['qr_exact_all_samples'],rep
