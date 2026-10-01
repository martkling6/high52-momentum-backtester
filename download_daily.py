"""Download daily adjusted total-return units; NOT physical-share settlement."""
import argparse,csv,json,hashlib,math
from pathlib import Path
from datetime import date
from data_audit import request

def adjusted_bar(row):
 o,h,l,c,ac=(float(row[k]) for k in ('open','high','low','close','adjusted_close'))
 if any(not math.isfinite(v) or v<=0 for v in (o,h,l,c,ac)) or l>min(o,c) or h<max(o,c):raise ValueError('Invalid OHLC price')
 ao=o*ac/c
 # Raw OHLC was validated above; clamp only floating-point boundary roundoff.
 return {'open':ao,'high':max(h*ac/c,ao,ac),'low':min(l*ac/c,ao,ac),'close':ac}

def main():
 p=argparse.ArgumentParser()
 for k in ('symbols','start','end','out'):p.add_argument('--'+k,required=True)
 a=p.parse_args();start=date.fromisoformat(a.start);end=date.fromisoformat(a.end)
 if start>=end:raise SystemExit('Invalid dates')
 symbols=Path(a.symbols).read_text().split()
 if not 20<=len(symbols)<=200 or len(set(symbols))!=len(symbols):raise SystemExit('20..200 unique symbols required')
 series={};hashes={}
 for s in symbols:
  data,err=request('eod/'+s,{'from':a.start,'to':a.end,'period':'d','order':'a'})
  if err or not isinstance(data,list) or not data:raise SystemExit('Failed '+s+': '+str(err))
  hashes[s]=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
  daily={}
  for row in data:
   d=date.fromisoformat(row['date'])
   if d in daily:raise SystemExit('Duplicate date '+s)
   daily[d]=adjusted_bar(row)
  series[s]=daily
 # Same calendar, no dropping interior missing bars by intersection.
 lo=max(min(v) for v in series.values());hi=min(max(v) for v in series.values())
 calendar=sorted(set.union(*(set(v) for v in series.values())))
 calendar=[d for d in calendar if lo<=d<=hi]
 if not calendar:raise SystemExit('No common date range')
 for s,v in series.items():
  missing=[str(d) for d in calendar if d not in v]
  if missing:raise SystemExit('Missing daily bars for '+s+': '+','.join(missing[:5]))
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('w',newline='') as f:
  w=csv.writer(f);w.writerow(['date','symbol','open','close','high','low'])
  for d in calendar:
   for s in symbols:w.writerow([d,s,series[s][d]['open'],series[s][d]['close'],series[s][d]['high'],series[s][d]['low']])
 out.with_suffix('.manifest.json').write_text(json.dumps({'kind':'exploratory_static_survivors','source':'EODHD daily','price_model':'adjusted total-return units; open/high/low = raw value * adjusted_close / raw_close','symbols':symbols,'first':str(lo),'last':str(hi),'raw_response_hashes':hashes,'limitations':['Not physical shares: dividend reinvestment/corporate-action settlement relies on provider adjustment.','Total-return closing-high proxy, not original price-high score.','Static survivors, no historical membership.','Common date range may shorten history.']},indent=2))
 print('Downloaded daily total-return-unit dataset; exploratory only')
if __name__=='__main__':main()
