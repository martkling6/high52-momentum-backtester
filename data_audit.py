"""Read-only provider-access and coverage diagnostic; never certifies a backtest."""
import argparse,csv,json,math,os,urllib.request,urllib.parse,urllib.error
from pathlib import Path
from datetime import date

def request(endpoint,params):
 token=os.environ.get('EODHD_API_TOKEN')
 if not token:return None,'MISSING_SECRET'
 query=urllib.parse.urlencode({**params,'api_token':token,'fmt':'json'})
 try:
  with urllib.request.urlopen('https://eodhd.com/api/'+endpoint+'?'+query,timeout=60) as response:
   return json.load(response),None
 except urllib.error.HTTPError as e:return None,'HTTP_'+str(e.code)
 except Exception:return None,'NETWORK_OR_RESPONSE_ERROR'

def records(data):
 if isinstance(data,list):return data
 if isinstance(data,dict):return list(data.values())
 return []

def members(data):
 result=[]
 for x in records(data):
  if not isinstance(x,dict) or not x.get('Code'):continue
  for field in ('StartDate','EndDate'):
   if x.get(field):date.fromisoformat(x[field])
  result.append(x)
 return result

def price_check(rows,calendar):
 if not isinstance(rows,list) or not rows:return {'status':'EMPTY_OR_INVALID','rows':0}
 dates=[];invalid=0;duplicates=0;seen=set();large_moves=0;previous=None
 for x in rows:
  try:
   d=date.fromisoformat(x['date']);p=float(x['adjusted_close'])
   if not math.isfinite(p) or p<=0:raise ValueError()
   if d in seen:duplicates+=1
   seen.add(d);dates.append(d)
   if previous and abs(p/previous-1)>0.5:large_moves+=1
   previous=p
  except (KeyError,TypeError,ValueError):invalid+=1
 if not dates:return {'status':'NO_VALID_PRICES','rows':len(rows)}
 lo,hi=min(dates),max(dates)
 gaps=sum(lo<=d<=hi and d not in seen for d in calendar)
 return {'status':'REVIEW' if invalid or duplicates or gaps or large_moves else 'BASIC_CHECKS_OK',
         'rows':len(rows),'first':str(lo),'last':str(hi),'invalid':invalid,'duplicate_dates':duplicates,
         'internal_missing_spy_dates':gaps,'adjusted_moves_over_50pct':large_moves}

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--sample-size',type=int,default=12)
 a=p.parse_args()
 if not 1<=a.sample_size<=25:raise SystemExit('Sample size must be 1..25')
 out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
 report={'status':'INCOMPLETE_DIAGNOSTIC','backtest_ready':False,'checks':{},'unresolved':[
  'Sample only: full-universe price coverage is not checked.',
  '2012-2015 membership snapshots may be incomplete according to provider documentation.',
  'Null join dates, re-entry intervals and ticker identities need reconciliation.',
  'Delisting settlements, merger proceeds and bankruptcies require event-level review.',
  'Splits/dividends and split-only ranking prices not yet verified.',
  'Publication timing and trade execution not yet modeled.']}
 history,error=request('fundamentals/GSPC.INDX',{'filter':'HistoricalTickerComponents'})
 report['checks']['membership_access']=error or 'HTTP_OK'
 if error:
  report['status']='BLOCKED_MEMBERSHIP_ACCESS'
 else:
  try:log=members(history)
  except Exception:log=[];report['checks']['membership_schema']='INVALID_DATES'
  report['membership_rows']=len(log)
  (out/'membership_log.json').write_text(json.dumps(history,indent=2))
  if not log:report['status']='BLOCKED_MEMBERSHIP_SCHEMA'
  else:
   report['unknown_start_dates']=sum(not x.get('StartDate') for x in log)
   report['delisted_members']=sum(str(x.get('IsDelisted'))=='1' for x in log)
   report['removed_members']=sum(bool(x.get('EndDate')) for x in log)
   # Snapshot counts are descriptive only; an HTTP 200 does not certify completeness.
   for year in (2013,2016,2020,2025):
    data,err=request('fundamentals/GSPC.INDX',{'historical':1,'from':f'{year}-01-01','to':f'{year}-12-31','filter':'HistoricalComponents'})
    (out/f'snapshots_{year}.json').write_text(json.dumps(data,indent=2))
    counts={k:len(records(v)) for k,v in data.items()} if isinstance(data,dict) and not err else {}
    report['checks'][f'snapshots_{year}']={'error':err,'snapshot_count':len(counts),'min_members':min(counts.values()) if counts else None,'max_members':max(counts.values()) if counts else None}
   spy,err=request('eod/SPY.US',{'from':'2012-01-01','to':'2025-12-31','period':'d','order':'a'})
   calendar={date.fromisoformat(x['date']) for x in spy} if isinstance(spy,list) and not err else set()
   report['checks']['calendar_access']=err or ('OK' if calendar else 'EMPTY')
   # Deterministic, intentionally includes removals/delistings; not a strategy universe.
   unique={}
   for x in sorted(log,key=lambda x:(str(x.get('IsDelisted'))!='1',not bool(x.get('EndDate')),x['Code'])):
    unique.setdefault(x['Code'],x)
   selected=list(unique.values())[:a.sample_size];checks=[]
   for x in selected:
    code=x['Code'];symbol=code if code.endswith('.US') else code+'.US'
    data,err=request('eod/'+urllib.parse.quote(symbol,safe=''),{'from':'2012-01-01','to':'2025-12-31','period':'d','order':'a'})
    check={'symbol':symbol,'membership_end':x.get('EndDate'),'is_delisted':x.get('IsDelisted'),'error':err,**price_check(data,calendar)}
    # Audit absence of six-month post-removal coverage; this may be a valid acquisition,
    # but must be resolved rather than deleting an open cohort position.
    check['terminal_event_review_required']=bool(x.get('EndDate')) or str(x.get('IsDelisted'))=='1'
    checks.append(check)
   report['price_sample']=checks
   rename,err=request('symbol-change-history',{'from':'2012-01-01','to':'2025-12-31','ex':'US'})
   report['checks']['rename_history_access']=err or 'HTTP_OK'
   if not err:(out/'symbol_changes.json').write_text(json.dumps(rename,indent=2))
 (out/'audit.json').write_text(json.dumps(report,indent=2))
 (out/'README.txt').write_text('Diagnostic only, no backtest certification. Inspect audit.json. Access failures are recorded without leaking tokens. No purchases or upgrades performed. Estimated request count: membership + 4 snapshots + SPY calendar + sample + rename, at most 32 requests; provider billing units may differ.\n')
 print(json.dumps({'status':report['status'],'backtest_ready':False,'membership_access':report['checks']['membership_access']},indent=2))
if __name__=='__main__':main()
