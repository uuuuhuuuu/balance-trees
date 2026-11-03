import argparse, csv, json, subprocess
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from balance_trees import TreeFlavor
from balance_trees.sequences import insertion_order
from balance_trees.strategies import create_strategy

JS = r'''
import {LargeTree} from './src/balance_trees/showcase/site/dist/large-model.mjs';
let text=''; for await(const chunk of process.stdin) text+=chunk;
const {keys,seed}=JSON.parse(text);
const t=new LargeTree({strategy:'treap',sequence:keys,seed});
const depths=[]; let comparisons=0;
while(t.advance()){
 if(t.current.kind==='compare') comparisons++;
 if(t.current.kind==='insert'){
  let id=t.focusId,d=0; while(t.parent[id]>=0){id=t.parent[id];d++;}
  if(d!==comparisons) throw Error('Initial depth mismatch');
  depths.push(d); comparisons=0;
 }
}
const seen=new Set(), stack=[[t.root,-Infinity,Infinity,-1,0]];
let total=0,height=0;
while(stack.length){
 const [id,lo,hi,parent,d]=stack.pop(); if(id<0)continue;
 if(seen.has(id)||t.parent[id]!==parent||!(lo<t.keys[id]&&t.keys[id]<hi))throw Error('Structural invariant failed');
 seen.add(id);total+=d;height=Math.max(height,d);
 if(parent>=0&&t.higher(id,parent))throw Error('Heap invariant failed');
 stack.push([t.left[id],lo,t.keys[id],id,d+1],[t.right[id],t.keys[id],hi,id,d+1]);
}
if(seen.size!==keys.length||depths.length!==keys.length)throw Error('Lost keys');
process.stdout.write(JSON.stringify({depths,rotations:t.rotations,mean_depth:total/keys.length,height}));
'''

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--size',type=int,default=20000)
 p.add_argument('--runs',type=int,default=10)
 p.add_argument('--seed',type=int,default=2026)
 p.add_argument('--output',type=Path,default=Path('benchmarks/results/treap-v21-fresh'))
 a=p.parse_args()
 if a.size<2 or a.runs<2:p.error('Use size >= 2 and runs >= 2')
 root=Path(__file__).resolve().parent
 try:subprocess.run(['node','--version'],check=True,capture_output=True)
 except (OSError,subprocess.CalledProcessError):p.error('Node.js is required. In PowerShell: $env:Path = "C:\\Program Files\\nodejs;" + $env:Path')
 a.output.mkdir(parents=True,exist_ok=False)
 metrics=[]; curves={'UI Treap':[],'v2.1':[]}; window=max(1,a.size//200)
 ends=np.arange(window,a.size+1,window)
 with (a.output/'insertions.csv').open('w',newline='',encoding='utf-8') as f:
  writer=csv.writer(f);writer.writerow(['run','insertion','key','treap_depth_before_balance','v21_depth_before_balance'])
  for run in range(a.runs):
   order_seed=a.seed+2*run; priority_seed=a.seed+2*run+1
   keys=list(insertion_order('random',a.size,order_seed))
   print(f'Run {run+1}/{a.runs}: UI Treap',flush=True)
   result=subprocess.run(['node','--input-type=module','-e',JS],cwd=root,input=json.dumps({'keys':keys,'seed':priority_seed}),text=True,capture_output=True)
   if result.returncode:raise RuntimeError(result.stderr)
   treap=json.loads(result.stdout)
   print(f'Run {run+1}/{a.runs}: v2.1',flush=True)
   flavor=TreeFlavor(create_strategy('random-level-v2-1'),seed=priority_seed)
   ds=[];rotations=0
   for key in keys:
    stats=flavor.insert(key)
    if not stats.inserted:raise AssertionError('Missing insertion')
    ds.append(stats.insertion_depth);rotations+=stats.rotations
   final=flavor.tree.depths()
   if set(final)!=set(keys):raise AssertionError('Lost keys')
   v21={'depths':ds,'rotations':rotations,'mean_depth':sum(final.values())/a.size,'height':max(final.values())}
   writer.writerows((run,i+1,k,x,y) for i,(k,x,y) in enumerate(zip(keys,treap['depths'],ds)))
   for name,data in [('UI Treap',treap),('v2.1',v21)]:
    d=np.asarray(data['depths'])
    metrics.append({'run':run,'order_seed':order_seed,'priority_seed':priority_seed,'strategy':name,'mean_initial_depth':float(d.mean()),'p95_initial_depth':float(np.percentile(d,95)),'max_initial_depth':int(d.max()),'rotations_per_insertion':data['rotations']/a.size,'final_mean_depth':data['mean_depth'],'final_height':data['height']})
    curves[name].append([float(d[e-window:e].mean()) for e in ends])
 with (a.output/'trials.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(metrics[0]));w.writeheader();w.writerows(metrics)
 fields=['mean_initial_depth','p95_initial_depth','max_initial_depth','rotations_per_insertion','final_mean_depth','final_height']
 fig,axes=plt.subplots(2,2,figsize=(13,9))
 for name,values in curves.items():
  arr=np.asarray(values);mean=arr.mean(axis=0);se=arr.std(axis=0,ddof=1)/np.sqrt(a.runs)
  axes[0,0].plot(ends,mean,label=name);axes[0,0].fill_between(ends,mean-2*se,mean+2*se,alpha=.15)
 axes[0,0].set(title='Pre-balancing depth: block means across runs',xlabel='Insertion number',ylabel='Depth (edges)');axes[0,0].legend()
 delta=np.asarray(curves['v2.1'])-np.asarray(curves['UI Treap'])
 mean=delta.mean(axis=0);se=delta.std(axis=0,ddof=1)/np.sqrt(a.runs)
 axes[0,1].plot(ends,mean);axes[0,1].fill_between(ends,mean-2*se,mean+2*se,alpha=.2);axes[0,1].axhline(0,color='black',linewidth=1)
 axes[0,1].set(title='Paired difference: v2.1 minus Treap',xlabel='Insertion number',ylabel='Negative means shallower v2.1')
 for ax,field,title in [(axes[1,0],'mean_initial_depth','Mean pre-balancing depth per run'),(axes[1,1],'rotations_per_insertion','Rotations per insertion per run')]:
  for name in curves:
   vals=[r[field] for r in metrics if r['strategy']==name];ax.plot(range(1,a.runs+1),vals,'o-',label=name)
  ax.set(title=title,xlabel='Run');ax.legend()
 for ax in axes.flat:ax.grid(alpha=.25)
 fig.tight_layout();fig.savefig(a.output/'comparison.png',dpi=160);plt.close(fig)
 summary=[]
 for field in fields:
  t=np.array([r[field] for r in metrics if r['strategy']=='UI Treap']);v=np.array([r[field] for r in metrics if r['strategy']=='v2.1']);d=v-t
  summary.append({'metric':field,'treap_mean':float(t.mean()),'v21_mean':float(v.mean()),'paired_difference':float(d.mean()),'difference_standard_error':float(d.std(ddof=1)/np.sqrt(a.runs))})
 with (a.output/'summary.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
 rows=''.join('<tr>'+''.join(f'<td>{r[k]:.4f}</td>' if isinstance(r[k],float) else f'<td>{r[k]}</td>' for k in r)+'</tr>' for r in summary)
 page='<html><meta charset="utf-8"><title>Treap vs v2.1</title><body style="font:16px sans-serif;max-width:1300px;margin:auto"><h1>UI Treap vs v2.1</h1>'+f'<p>{a.runs} paired runs; {a.size:,} keys per random permutation. Depth measured before balancing. Root depth = 0.</p>'+'<img src="comparison.png" style="width:100%"><h2>Summary</h2><table border="1" cellpadding="8"><tr><th>Metric</th><th>Treap mean</th><th>v2.1 mean</th><th>v2.1 minus Treap</th><th>Paired difference SE</th></tr>'+rows+'</table><p>Lower is better for each listed metric, but fewer rotations may trade off against deeper trees. Bands show mean +/- 2 standard errors across runs, not guaranteed confidence intervals. This is not a runtime comparison or an asymptotic proof. JavaScript and Python use different priority generators; matching seeds do not produce matching random draws. Final tree invariants checked each run; Treap initial depth checked against search comparisons.</p></body></html>'
 (a.output/'report.html').write_text(page,encoding='utf-8')
 (a.output/'config.json').write_text(json.dumps({'size':a.size,'runs':a.runs,'seed':a.seed,'window':window,'treap':'Existing UI LargeTree treap, stored 32-bit priorities','v21':'Python random-level-v2-1','sampling':'Fresh shared permutation per run; distinct order and balancing seeds'},indent=2))
 print(f'Open {a.output / "report.html"}')
if __name__=='__main__':main()
