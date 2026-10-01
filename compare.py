"""Paired long-only and lagged passive cohort comparison, no parameter search."""
import argparse,csv,json,statistics,math
from pathlib import Path
from engine import summary,write_csv

def read(path):
 with open(path,newline='') as f:
  return [{k:(v if k=='date' else float(v)) for k,v in row.items()} for row in csv.DictReader(f)]

def rebase(rows):
 equity=peak=10000.0;result=[]
 for row in rows:
  x=dict(row);equity*=1+x['net_return'];peak=max(peak,equity)
  x['equity']=equity;x['drawdown']=equity/peak-1;result.append(x)
 return result

def main():
 p=argparse.ArgumentParser()
 for k in ('active','passive','out'):p.add_argument('--'+k,required=True)
 a=p.parse_args();active=read(a.active);passive=read(a.passive)
 if [x['month'] for x in active]!=[x['month'] for x in passive]:raise ValueError('Different evaluation months')
 if any(abs(x['gross_exposure']-y['gross_exposure'])>1e-9 for x,y in zip(active,passive)):raise ValueError('Unequal exposure schedules')
 paired=[{'date':x['date'],'active_net':x['net_return'],'passive_net':y['net_return'],'difference':x['net_return']-y['net_return'],'active_cost':x['trading_cost'],'passive_cost':y['trading_cost']} for x,y in zip(active,passive)]
 periods=[('full',None,None),('2001-2009','2001','2009'),('2010-2019','2010','2019'),('2020-2025','2020','2025')]
 reports=[]
 for name,lo,hi in periods:
  sel=[i for i,x in enumerate(active) if (lo is None or lo<=x['date'][:4]<=hi)]
  if not sel:continue
  for mode,rows in [('high52_long_only',active),('passive_same_universe',passive)]:
   segment=rebase([rows[i] for i in sel]);m=summary(segment)
   reports.append({'period':name,'mode':mode,'start_month':segment[0]['date'][:7],'end_month':segment[-1]['date'][:7],**m})
 out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
 write_csv(out/'periods.csv',reports);write_csv(out/'paired_monthly.csv',paired)
 delta=summary(active)['cagr']-summary(passive)['cagr']
 result={'cagr_difference_percentage_points':delta*100,'mean_monthly_return_difference':statistics.mean(x['difference'] for x in paired),'fraction_months_active_beats_passive':sum(x['difference']>0 for x in paired)/len(paired),'limitations':['No independent holdout; retrospective comparison.','Same exposure schedule and cost rate, not same realized portfolio risk or turnover.','Costs charged on net target-weight changes; intra-month weight drift not modeled.','Both inherit the dataset survivorship bias; no broad-market alpha inference.','Monthly drawdown only; no daily execution simulation.']}
 (out/'comparison.json').write_text(json.dumps(result,indent=2))
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
