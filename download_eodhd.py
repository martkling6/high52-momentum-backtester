"""Exploratory survivor-list adapter; adjusted-close high proxy, not original CRSP score."""
import argparse,csv,json,os,urllib.request,urllib.parse,calendar
from datetime import date,timedelta
from pathlib import Path
p=argparse.ArgumentParser()
for k in ('symbols','start','end','out'):p.add_argument('--'+k,required=True)
a=p.parse_args();token=os.environ.get('EODHD_API_TOKEN')
if not token:raise SystemExit('Set EODHD_API_TOKEN')
end=date.fromisoformat(a.end)
if end.day!=calendar.monthrange(end.year,end.month)[1]:raise SystemExit('End must be last calendar day of a completed month')
symbols=[s.strip() for s in Path(a.symbols).read_text().splitlines() if s.strip() and not s.startswith('#')]
if len(set(symbols))!=len(symbols) or len(symbols)<20:raise SystemExit('Provide at least 20 unique symbols')
monthly={};raw_hashes={}
import hashlib
for s in symbols:
 q=urllib.parse.urlencode({'api_token':token,'fmt':'json','from':a.start,'to':a.end,'period':'d'})
 try:
  with urllib.request.urlopen('https://eodhd.com/api/eod/'+urllib.parse.quote(s,safe='')+'?'+q,timeout=60) as response:blob=response.read()
 except Exception:raise SystemExit('EODHD request failed for '+s+'; secret/URL suppressed') from None
 raw_hashes[s]=hashlib.sha256(blob).hexdigest();data=json.loads(blob)
 if not isinstance(data,list) or not data:raise SystemExit('No history for '+s)
 daily=sorted((date.fromisoformat(r['date']),float(r['adjusted_close'])) for r in data)
 if any(v<=0 for d,v in daily):raise SystemExit('Invalid adjusted price')
 ends={}
 for i,(d,v) in enumerate(daily):ends[(d.year,d.month)]=i
 previous=None
 for (y,m),i in ends.items():
  d,v=daily[i];month=y*12+m-1
  if previous is not None and month==previous[0]+1:
   cutoff=d-timedelta(days=365);window=[value for day,value in daily[:i+1] if cutoff<day<=d]
   score=v/max(window) if len(window)>=240 and daily[0][0]<=cutoff else None
   monthly.setdefault(month,{})[s]={'score':score,'return':v/previous[1]-1}
  previous=(month,v)
# Strict balanced sample: fail instead of removing a delisted held security silently.
complete=[m for m,rows in monthly.items() if len(rows)==len(symbols)]
if not complete:raise SystemExit('No common complete history')
first,last=min(complete),max(complete)
for m in range(first,last+1):
 if len(monthly.get(m,{}))!=len(symbols):raise SystemExit('Missing monthly data inside common sample; resolve before testing')
out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
with out.open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['date','symbol','score','return'])
 for m in range(first,last+1):
  for s,row in monthly[m].items():w.writerow([f'{m//12:04}-{m%12+1:02}-01',s,row['score'] if row['score'] is not None else '',row['return']])
out.with_suffix('.manifest.json').write_text(json.dumps({'kind':'exploratory_static_survivors','source':'EODHD adjusted_close','score':'current adjusted_close / highest daily adjusted_close over past 365 days; total-return closing-high proxy','symbols':symbols,'raw_sha256':raw_hashes,'delistings_reviewed':False,'warnings':['Static surviving stocks: selection and survivorship bias.','Adjusted close includes dividends: score differs from original price-high definition.','IPO and missing histories restrict sample; not original universe.']},indent=2))
print('Saved EXPLORATORY static-survivor dataset; no original-study replication')
