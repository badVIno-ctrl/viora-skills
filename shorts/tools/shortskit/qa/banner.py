"""Measure only banner and independent track ROIs in the compressed deliverable."""
from pathlib import Path
import cv2, numpy as np

def inspect_video(path, spec, panel_box):
    cap=cv2.VideoCapture(str(path));fps=cap.get(cv2.CAP_PROP_FPS);n=cap.get(cv2.CAP_PROP_FRAME_COUNT)
    if fps<=0 or n<=0:raise ValueError('Cannot decode video')
    dur=n/fps;x,y,w,h=map(int,panel_box)
    times=[t for t in [.1,.5,1.1,1.8,2.9,3.8,4.6,6.,8.] if t<dur]
    frames=[];qr=[];det=cv2.QRCodeDetector()
    for t in times:
        cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,f=cap.read()
        if not ok:raise ValueError('Cannot decode banner phase')
        roi=f[y:y+h,x:x+w]
        if roi.shape[:2]!=(h,w):raise ValueError('Panel box outside video')
        frames.append(roi)
        if spec.get('qr_box'):
            qx,qy,qw,qh=map(int,spec['qr_box']);q=roi[qy:qy+qh,qx:qx+qw]
            value=det.detectAndDecode(q)[0];qr.append({'t':t,'decoded':value,'exact':value==spec.get('qr_url')})
    cap.release();elements={}
    for name,b in spec.get('element_boxes',{}).items():
        bx,by,bw,bh=map(int,b);arr=[a[by:by+bh,bx:bx+bw].astype(float) for a in frames]
        delta=max([float(np.mean(np.abs(a-b))) for a,b in zip(arr,arr[1:])] or [0])
        elements[name]={'max_mean_abs_delta':delta,'changed':delta>1.0}
    motion=all(elements.get(k,{}).get('changed',False) for k in ('logo','title','message','cta'))
    return {'motion_verified':motion,'elements':elements,'qr_samples':qr,
            'qr_exact_all_samples':bool(qr) and all(x['exact'] for x in qr),
            'quiet_hold_s':spec.get('quiet_phase',[0,0])[1]-spec.get('quiet_phase',[0,0])[0],
            'human_phone_readability':'required','ui_overlay':'required'}
