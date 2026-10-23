import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--comparisons',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
limits={'alpha':{'max_abs':.02,'mean_abs':.0005},'color':{'max_abs':.05,'mean_abs':.001}}
rows=[]
for path in sorted(a.comparisons.glob('*.json')):
 report=json.loads(path.read_text());failures=[];examined=0;video=[];maxima={}
 for file in report.get('files',[]):
  if 'missing' in file:failures.append({'path':file['path'],'reason':'missing output'});continue
  px=file.get('pixels')
  if px is None:continue
  if file['path'].endswith('.exr'):
   if not px.get('same_shape') or not px.get('finite'):failures.append({'path':file['path'],'reason':'shape mismatch or nonfinite'});continue
   components=px.get('components')
   if not components:failures.append({'path':file['path'],'reason':'component comparison missing'});continue
   for component,metric in components.items():
    mean=metric['sum_abs']/metric['samples'];threshold=limits[component];examined+=1
    stat=maxima.setdefault(component,{'max_abs':0,'max_frame_mean_abs':0})
    stat['max_abs']=max(stat['max_abs'],metric['max_abs']);stat['max_frame_mean_abs']=max(stat['max_frame_mean_abs'],mean)
    if metric['max_abs']>threshold['max_abs'] or mean>threshold['mean_abs']:
     failures.append({'path':file['path'],'component':component,'max_abs':metric['max_abs'],'mean_abs':mean,'reason':'accepted tolerance exceeded'})
  else:
   video.append({'path':file['path'],'frames':px.get('frames'),'exact':px.get('exact'),'max_abs_normalized':px.get('max_abs',0)/65535,'mean_abs_normalized':px.get('sum_abs',0)/max(px.get('samples',1),1)/65535,'error':px.get('error')})
   if px.get('error'):failures.append({'path':file['path'],'reason':px['error']})
 rows.append({'case':path.stem,'exr_components':examined,'exr_limits_pass':not failures if examined else None,'maxima':maxima,'failures':failures,'decoded_video':video,'all_media_pixels_equal':report.get('all_media_pixels_equal')})
result={'limits':limits,'scope':'Raw EXR comparisons, each frame and each color/alpha component. Encoded video metrics are reported separately.','cases':rows,'failed_cases':[r['case'] for r in rows if r['failures']]}
a.output.write_text(json.dumps(result,indent=2));print(json.dumps({'cases':len(rows),'failed_cases':result['failed_cases']}))
