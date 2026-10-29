"""Run from the balance-trees repository root: python run_v3_report.py."""
import argparse
import csv
import html
import json
import math
from pathlib import Path
from balance_trees.benchmark import run_benchmarks
from balance_trees.sequences import ORDERS


def chart(rows, metric, title, reference=False):
    good = sorted((r for r in rows if r['status'] == 'complete' and metric in r), key=lambda r:r['n'])
    W,H=850,360
    left,right,top,bottom=80,825,40,295
    maximum=max([float(r[metric])+float(r.get(metric+'_se',0)) for r in good]+([math.log(2**17)**2] if reference else [1]))*1.08
    def x(n): return left+(math.log2(n)-1)/16*(right-left)
    def y(v): return bottom-float(v)/maximum*(bottom-top)
    parts=[f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(title)}"><rect width="100%" height="100%" fill="white"/>',f'<text x="80" y="22">{html.escape(title)}</text>']
    for i in range(6):
        value=maximum*i/5
        parts.append(f'<path d="M {left} {y(value)} H {right}" stroke="#ddd"/><text x="5" y="{y(value)+4}" font-size="12">{value:.2f}</text>')
    for exponent in range(1,18,2):
        parts.append(f'<text x="{x(2**exponent)-12}" y="320" font-size="12">2^{exponent}</text>')
    parts.append('<text x="380" y="345">Number of inserted vertices n (log2 axis)</text>')
    if reference:
        points=' '.join(f'{x(2**(1+i/8))},{y(math.log(2**(1+i/8))**2)}' for i in range(129))
        parts.append(f'<polyline points="{points}" fill="none" stroke="#777" stroke-dasharray="7 5"/><text x="550" y="22" font-size="12">Dashed: (ln n)^2, coefficient 1</text>')
    for a,b in zip(good,good[1:]):
        if b['n']==2*a['n']:
            parts.append(f'<path d="M {x(a["n"])} {y(a[metric])} L {x(b["n"])} {y(b[metric])}" stroke="#166ac1" fill="none"/>')
    for row in good:
        xx,yy=x(row['n']),y(row[metric]); se=float(row.get(metric+'_se',0))
        parts.append(f'<path d="M {xx} {y(float(row[metric])-se)} V {y(float(row[metric])+se)}" stroke="#166ac1"/><circle cx="{xx}" cy="{yy}" r="3" fill="#166ac1"><title>n={row["n"]}; mean={row[metric]}; SE={se}</title></circle>')
    return ''.join(parts)+'</svg>'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('benchmarks/random-level-v3-large'))
    parser.add_argument('--trials',type=int,default=5)
    parser.add_argument('--timeout',type=float,default=300)
    parser.add_argument('--seed',type=int,default=2026)
    parser.add_argument('--orders',nargs='+',choices=ORDERS,default=list(ORDERS))
    parser.add_argument('--report-only',action='store_true')
    args=parser.parse_args()
    if args.report_only:
        results=json.loads((args.output/'results.json').read_text(encoding='utf-8'))
    else:
        results=run_benchmarks(args.output,sizes=[2**p for p in range(1,18)],trials=args.trials,seed=args.seed,strategies=['random-level-v3'],orders=args.orders,timeout=args.timeout)
    meta=results['metadata']; summaries=results['summaries']
    parts=['<!doctype html><meta charset="utf-8"><title>Random-level v3 large tests</title><style>body{font:16px system-ui;max-width:1100px;margin:30px auto;padding:15px}svg{width:100%;border:1px solid #ccc}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:6px}section{margin:40px 0}</style><h1>Random-level v3: measured large tests</h1>']
    parts.append('<p>Sizes 2^1 through 2^17. Depth and height count edges. Blue: measured trial mean; whiskers: +/-1 standard error. Dashed: (ln n)^2 with coefficient 1, an expected-growth reference, not a proved bound or fitted curve. Only fully completed groups are plotted; gaps are not interpolated.</p>')
    parts.append('<p>V3 configuration expected: c=2, epsilon=1, 10% no rotation on non-root insertion, targets 0..d-1, no record-minimum override. Run against the intended repository revision; this script uses the installed implementation.</p>')
    parts.append('<p>Machine and method: '+html.escape(json.dumps(meta,ensure_ascii=False))+'</p>')
    for order in meta['orders']:
        rows=[r for r in summaries if r['order']==order]
        parts.append('<section><h2>'+html.escape(order)+'</h2>')
        for metric,title in [('mean_depth','Final mean vertex depth'),('height','Final tree height'),('mean_rotations','Mean rotations per insertion'),('mean_visits','Mean rebalancing visits per insertion')]:
            svg=chart(rows,metric,title,metric in ('mean_depth','height'))
            name=f'{order}-{metric}.svg'
            (args.output/name).write_text(svg,encoding='utf-8')
            parts.append(svg)
        columns=['n','status','completed_trials','requested_trials','mean_depth','mean_depth_se','height','height_se','mean_rotations','mean_visits']
        parts.append('<details><summary>Measurements and incomplete groups</summary><table><tr>'+''.join('<th>'+c+'</th>' for c in columns)+'</tr>')
        for row in rows:
            parts.append('<tr>'+''.join('<td>'+html.escape(str(row.get(c,'')))+'</td>' for c in columns)+'</tr>')
        parts.append('</table></details></section>')
    parts.append('<p>Data: <a href="results.json">results.json</a> | <a href="summary.csv">summary.csv</a> | <a href="trials.csv">trials.csv</a> | <a href="config.json">config.json</a></p>')
    (args.output/'random-level-v3.html').write_text(''.join(parts),encoding='utf-8')
    print('Report:',(args.output/'random-level-v3.html').resolve())


if __name__=='__main__':
    main()
