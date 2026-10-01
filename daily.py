"""Six self-financing cash sleeves, long only, daily marks, next-open fills."""
import argparse,csv,json,math,statistics,hashlib
from pathlib import Path
from datetime import date,timedelta

def load(path):
 panel={}
 with open(path,newline='') as f:
  for x in csv.DictReader(f):
   d=date.fromisoformat(x['date']);s=x['symbol'];o=float(x['open']);c=float(x['close'])
   if not all(math.isfinite(v) and v>0 for v in (o,c)):raise ValueError('Invalid daily price')
   if s in panel.setdefault(d,{}):raise ValueError('Duplicate daily bar')
   panel[d][s]={'open':o,'close':c}
 if not panel:raise ValueError('Empty panel')
 symbols=set.union(*(set(v) for v in panel.values()))
 if any(set(v)!=symbols for v in panel.values()):raise ValueError('Incomplete daily panel')
 return panel

def simulate(panel,mode='high52',bps=10,initial=10000,holding=6,skip=1,minimum=20):
 if mode not in ('high52','passive') or bps<0 or initial<=0 or holding<1 or skip<0:raise ValueError('Invalid settings')
 sleeves=[{'cash':initial/holding,'units':{}} for _ in range(holding)]
 dates=sorted(panel);symbols=sorted(panel[dates[0]]);history=[];formations={}
 rows=[];orders=[];signals=[];started=False;peak=previous=initial;rate=bps/10000
 for i,d in enumerate(dates):
  month=d.year*12+d.month-1
  newmonth=i>0 and (d.year,d.month)!=(dates[i-1].year,dates[i-1].month)
  if newmonth:
   prev=dates[i-1];pm=prev.year*12+prev.month-1;cutoff=prev-timedelta(days=365)
   window=[(hd,v) for hd,v in history if hd>cutoff]
   scores=[]
   if dates[0]<=cutoff and len(window)>=240:
    scores=[(panel[prev][s]['close']/max(v[s]['close'] for hd,v in window),s) for s in symbols]
   formations[pm]=sorted(scores,key=lambda x:(x[0],x[1]))
   rank=formations.get(month-1-skip,[])
   sleeve=sleeves[month%holding]
   # Rotate one sleeve at the current open; costs charged on actual turnover.
   for s,units in sleeve['units'].items():
    price=panel[d][s]['open'];notional=units*price;fee=notional*rate
    sleeve['cash']+=notional-fee
    orders.append({'date':str(d),'sleeve':month%holding,'symbol':s,'side':'SELL','units':units,'price':price,'fee':fee})
   sleeve['units']={}
   if len(rank)>=minimum:
    selected=[s for score,s in (rank[-max(1,math.floor(len(rank)*0.3)):] if mode=='high52' else rank)]
    budget=sleeve['cash']/(1+rate);per=budget/len(selected)
    for s in selected:
     price=panel[d][s]['open'];units=per/price;fee=per*rate
     sleeve['units'][s]=units;sleeve['cash']-=per+fee
     orders.append({'date':str(d),'sleeve':month%holding,'symbol':s,'side':'BUY','units':units,'price':price,'fee':fee})
    if sleeve['cash']<-1e-7:raise ValueError('Negative cash')
    sleeve['cash']=max(0,sleeve['cash']);started=True
    signals.append({'execution_date':str(d),'formation_month':month-1-skip,'selected':','.join(selected)})
  cash=sum(x['cash'] for x in sleeves)
  holdings=sum(units*panel[d][s]['close'] for x in sleeves for s,units in x['units'].items())
  equity=cash+holdings
  if started:
   peak=max(peak,equity)
   rows.append({'date':str(d),'equity':equity,'net_return':equity/previous-1,'drawdown':equity/peak-1,'cash':cash,'holdings':holdings,'gross_exposure':holdings/equity})
  previous=equity;history.append((d,panel[d]))
 if not rows:raise ValueError('No daily portfolios after warmup')
 return rows,orders,signals

def summary(rows,initial=10000):
 r=[x['net_return'] for x in rows];years=((date.fromisoformat(rows[-1]['date'])-date.fromisoformat(rows[0]['date'])).days+1)/365.25
 sd=statistics.stdev(r) if len(r)>1 else 0
 return {'start':rows[0]['date'],'end':rows[-1]['date'],'days':len(rows),'cagr':(rows[-1]['equity']/initial)**(1/years)-1,'max_daily_drawdown':min(x['drawdown'] for x in rows),'sharpe_zero_rf':statistics.mean(r)/sd*math.sqrt(252) if sd else None,'ending_equity':rows[-1]['equity']}

def write(path,rows):
 if not rows:return
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
 p=argparse.ArgumentParser()
 for key in ('data','manifest','out'):p.add_argument('--'+key,required=True)
 a=p.parse_args();manifest=json.loads(Path(a.manifest).read_text())
 if manifest.get('kind') not in ('exploratory_static_survivors','synthetic'):raise ValueError('Unreviewed daily data kind')
 panel=load(a.data);out=Path(a.out);out.mkdir(parents=True,exist_ok=False);results=[]
 for bps in (0,10,25):
  for mode in ('high52','passive'):
   rows,orders,signals=simulate(panel,mode,bps)
   results.append({'mode':mode,'cost_bps':bps,**summary(rows)})
   dest=out/f'{mode}_{bps}bps';dest.mkdir();write(dest/'daily.csv',rows);write(dest/'orders.csv',orders);write(dest/'signals.csv',signals)
 write(out/'comparison.csv',results)
 (out/'run.json').write_text(json.dumps({'manifest':manifest,'input_sha256':hashlib.sha256(Path(a.data).read_bytes()).hexdigest(),'settings':{'initial':10000,'holding_months':6,'skip_months':1,'top_fraction':0.3,'cost_bps':[0,10,25]},'limitations':['Adjusted-unit holdings, not physical-share cash dividend settlement.','Provider adjusted opening prices are reconstructed, not exchange execution quotes.','Six independent sleeves drift in value; no monthly equal-capital reset.','Uninvested cash earns zero; no taxes or minimum fees.','No final liquidation; ending equity includes marked positions.','Daily-close drawdown is not intraday drawdown.','Static surviving universe; no claim of validated alpha.']},indent=2))
 print(json.dumps(results,indent=2))
if __name__=='__main__':main()
