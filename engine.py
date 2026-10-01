"""Monthly overlapping cohorts; a research model, not broker execution."""
import argparse,csv,json,math,hashlib,statistics
from pathlib import Path
from datetime import date

def month_index(s):
 d=date.fromisoformat(s);return d.year*12+d.month-1

def load(path):
 panel={}
 with open(path,newline='') as f:
  for x in csv.DictReader(f):
   m=month_index(x['date']);s=x['symbol']
   if s in panel.setdefault(m,{}):raise ValueError('Duplicate month/symbol')
   score=float(x['score']) if x['score'] else None
   r=float(x['return'])
   if not math.isfinite(r) or r<=-1:raise ValueError('Invalid monthly return')
   if score is not None and (not math.isfinite(score) or not 0<score<=1.000001):raise ValueError('Invalid high ratio')
   panel[m][s]={'score':score,'return':r}
 months=sorted(panel)
 if not months or any(b!=a+1 for a,b in zip(months,months[1:])):raise ValueError('Missing calendar month')
 return panel

def weights_for(cohorts,mode,holding):
 w={}
 for cohort in cohorts:
  for basket,sign in ((cohort['winners'],1),(cohort['losers'],-1)):
   if mode=='long_only' and sign<0:continue
   for s in basket:w[s]=w.get(s,0)+sign/len(basket)/holding
 return {s:v for s,v in w.items() if abs(v)>1e-12}

def simulate(panel,cfg):
 if cfg['holding_months']<1 or cfg['skip_months']<0 or not 0<cfg['quantile']<=0.5:raise ValueError('Invalid cohort settings')
 if cfg['cost_bps']<0 or cfg['borrow_rate']<0:raise ValueError('Invalid costs')
 if cfg['mode'] not in ('long_only','long_short'):raise ValueError('Invalid mode')
 cohorts=[];previous={};records=[];selections=[];equity=peak=cfg['initial_capital']
 months=sorted(panel);holding=cfg['holding_months'];started=False
 for m in months:
  cohorts=[c for c in cohorts if c['end']>=m]
  formation=m-1-cfg['skip_months']
  ranking=sorted(((v['score'],s) for s,v in panel.get(formation,{}).items() if v['score'] is not None),key=lambda x:(x[0],x[1]))
  n=math.floor(len(ranking)*cfg['quantile'])
  if len(ranking)>=cfg['minimum_universe'] and n>=1:
   winners=[s for score,s in ranking[-n:]];losers=[s for score,s in ranking[:n]]
   cohorts.append({'start':m,'end':m+holding-1,'winners':winners,'losers':losers})
   for score,s in ranking:selections.append({'formation_month':formation,'holding_start':m,'symbol':s,'score':score,'basket':'winner' if s in winners else 'loser' if s in losers else 'middle'})
  w=weights_for(cohorts,cfg['mode'],holding)
  missing=set(w)-set(panel[m])
  if missing:raise ValueError('Missing held-stock return; delisting must be resolved: '+','.join(sorted(missing)))
  turnover=sum(abs(w.get(s,0)-previous.get(s,0)) for s in set(w)|set(previous))
  gross=sum(v*panel[m][s]['return'] for s,v in w.items())
  cost=turnover*cfg['cost_bps']/10000
  borrow=sum(-v for v in w.values() if v<0)*cfg['borrow_rate']/12
  net=gross-cost-borrow
  started=started or bool(w)
  if started:
   if net<=-1:raise ValueError('Insolvent portfolio')
   equity*=1+net;peak=max(peak,equity)
   # Equally weighted available universe is an exploratory benchmark, not an index.
   benchmark=statistics.mean(x['return'] for x in panel[m].values())
   records.append({'month':m,'date':f'{m//12:04}-{m%12+1:02}-01','gross_return':gross,'trading_cost':cost,'borrow_cost':borrow,'net_return':net,'equity':equity,'drawdown':equity/peak-1,'gross_exposure':sum(map(abs,w.values())),'cohorts':len(cohorts),'universe_equal_return':benchmark})
  previous=w
 if not records:raise ValueError('No eligible portfolios')
 return records,selections

def write_csv(path,rows):
 if not rows:return
 with open(path,'w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def summary(rows):
 r=[x['net_return'] for x in rows];sd=statistics.stdev(r) if len(r)>1 else 0
 return {'months':len(r),'total_return':math.prod(1+x for x in r)-1,'cagr':math.prod(1+x for x in r)**(12/len(r))-1,'max_drawdown':min(x['drawdown'] for x in rows),'sharpe_zero_rf':statistics.mean(r)/sd*math.sqrt(12) if sd else None,'monthly_win_rate':sum(x>0 for x in r)/len(r)}

def main():
 p=argparse.ArgumentParser()
 for k in ('data','manifest','config','out'):p.add_argument('--'+k,required=True)
 a=p.parse_args();cfg=json.loads(Path(a.config).read_text());manifest=json.loads(Path(a.manifest).read_text())
 if manifest.get('kind') not in ('exploratory_static_survivors','point_in_time_reviewed','synthetic'):raise ValueError('Missing dataset kind')
 if manifest.get('kind')=='point_in_time_reviewed' and not manifest.get('delistings_reviewed'):raise ValueError('Delistings must be reviewed')
 panel=load(a.data);rows,selections=simulate(panel,cfg)
 out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
 write_csv(out/'monthly.csv',rows);write_csv(out/'selections.csv',selections)
 (out/'summary.json').write_text(json.dumps(summary(rows),indent=2))
 (out/'run.json').write_text(json.dumps({'config':cfg,'manifest':manifest,'input_sha256':hashlib.sha256(Path(a.data).read_bytes()).hexdigest(),'limitations':['Constant research weights within months; no execution prices.','Ranking by supplied score; score source and adjustments must be reviewed.','Short proceeds, funding and cash interest omitted.','Not an exact CRSP study replication.']},indent=2))
 print(json.dumps(summary(rows),indent=2))
if __name__=='__main__':main()
