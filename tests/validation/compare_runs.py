"""Compare file bytes and every decoded image/video sample without tolerance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR','1')
import cv2
import numpy as np

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def diff(a,b):
    if a.shape != b.shape:
        return {'same_shape':False,'left_shape':list(a.shape),'right_shape':list(b.shape),'exact':False}
    d=np.abs(a.astype(np.float64)-b.astype(np.float64))
    finite=bool(np.isfinite(a).all() and np.isfinite(b).all())
    return {'same_shape':True,'samples':a.size,'different_samples':int(np.count_nonzero(a != b)),
            'finite':finite,'exact':bool(np.array_equal(a,b)),
            'max_abs':float(d.max()) if finite else None,'sum_abs':float(d.sum()) if finite else None,
            'sum_squared':float((d*d).sum()) if finite else None}

def image_diff(left,right):
    a=cv2.imread(str(left),cv2.IMREAD_UNCHANGED)
    b=cv2.imread(str(right),cv2.IMREAD_UNCHANGED)
    if a is None or b is None: return {'exact':False,'error':'decode failed'}
    result=diff(a,b)
    if result.get('same_shape'):
        if a.ndim == 2:
            result['components']={'alpha':diff(a,b)}
        elif a.shape[-1] == 4:
            result['components']={'color':diff(a[:,:,:3],b[:,:,:3]),'alpha':diff(a[:,:,3],b[:,:,3])}
        else:
            result['components']={'color':diff(a,b)}
    return result

def video_diff(left,right):
    def probe(path):
        return json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,pix_fmt','-of','json',str(path)]))['streams'][0]
    la,rb=probe(left),probe(right)
    if (la['width'],la['height']) != (rb['width'],rb['height']): return {'exact':False,'error':'different dimensions'}
    alpha=any(v.startswith(('yuva','gbrap','rgba','bgra','argb','abgr','ya')) for v in (la['pix_fmt'],rb['pix_fmt']))
    channels=4 if alpha else 3
    pix='rgba64le' if alpha else 'rgb48le'
    frame_size=la['width']*la['height']*channels*2
    procs=[subprocess.Popen(['ffmpeg','-v','error','-i',str(p),'-f','rawvideo','-pix_fmt',pix,'-'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL) for p in [left,right]]
    result={'frames':0,'exact':True,'samples':0,'different_samples':0,'max_abs':0,'sum_abs':0,'sum_squared':0}
    try:
        while True:
            blocks=[p.stdout.read(frame_size) for p in procs]
            if not any(blocks): break
            if any(len(b)!=frame_size for b in blocks):
                result.update(exact=False,error='different frame counts or incomplete frame'); break
            d=diff(*[np.frombuffer(b,dtype='<u2') for b in blocks])
            result['frames']+=1
            result['exact'] &= d['exact']
            result['max_abs']=max(result['max_abs'],d['max_abs'])
            for key in ['samples','different_samples','sum_abs','sum_squared']: result[key]+=d[key]
    finally:
        for p in procs:
            p.stdout.close()
            p.wait()
    if any(p.returncode for p in procs): result.update(exact=False,error='decoder failed')
    return result

p=argparse.ArgumentParser()
p.add_argument('left',type=Path)
p.add_argument('right',type=Path)
p.add_argument('--output',required=True,type=Path)
a=p.parse_args()
left={f.relative_to(a.left).as_posix():f for f in a.left.rglob('*') if f.is_file()}
right={f.relative_to(a.right).as_posix():f for f in a.right.rglob('*') if f.is_file()}
records=[]
for name in sorted(set(left)|set(right)):
    record={'path':name}
    if name not in left or name not in right:
        record['missing']='left' if name not in left else 'right'
    else:
        l,r=left[name],right[name]
        record['bytes_equal']=sha(l)==sha(r)
        if l.suffix.lower() in ['.exr','.png','.jpg','.jpeg']:
            record['pixels']=image_diff(l,r)
        elif l.suffix.lower() in ['.mp4','.mov','.mkv']:
            record['pixels']=video_diff(l,r)
    records.append(record)
report={'left':str(a.left),'right':str(a.right),'files':records,
        'all_file_bytes_equal':bool(records) and all(r.get('bytes_equal',False) for r in records),
        'all_media_pixels_equal':any('pixels' in r for r in records) and all(r.get('pixels',{}).get('exact',True) and 'missing' not in r for r in records)}
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='files'}))
