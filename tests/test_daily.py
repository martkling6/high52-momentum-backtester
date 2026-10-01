import copy,unittest
from datetime import date,timedelta
from daily import simulate,summary

class DailyTests(unittest.TestCase):
 def setUp(self):
  self.panel={};d=date(2000,1,1)
  for i in range(1500):
   if d.weekday()<5:self.panel[d]={s:{'open':100.0,'close':100.0} for s in ('A','B','C')}
   d+=timedelta(days=1)
 def run_model(self,panel=None,mode='high52',bps=10):return simulate(panel or self.panel,mode,bps,minimum=3)
 def test_flat_prices_no_cost_no_profit(self):
  rows,_,_=self.run_model(bps=0)
  self.assertAlmostEqual(rows[-1]['equity'],10000)
 def test_costs_reduce_equity(self):
  zero,_,_=self.run_model(bps=0);cost,_,_=self.run_model(bps=25)
  self.assertLess(cost[-1]['equity'],zero[-1]['equity'])
 def test_no_negative_cash_or_shorts(self):
  rows,orders,_=self.run_model()
  self.assertTrue(all(x['cash']>=0 and x['gross_exposure']<=1.000000001 for x in rows))
  self.assertTrue(all(x['units']>0 for x in orders))
 def test_future_prices_do_not_change_past(self):
  rows,orders,signals=self.run_model();cutoff=sorted(self.panel)[650];p=copy.deepcopy(self.panel)
  for d in p:
   if d>cutoff:
    for x in p[d].values():x['open']=200;x['close']=200
  later,lo,ls=self.run_model(panel=p)
  self.assertEqual([x for x in rows if x['date']<=str(cutoff)],[x for x in later if x['date']<=str(cutoff)])
  self.assertEqual([x for x in signals if x['execution_date']<=str(cutoff)],[x for x in ls if x['execution_date']<=str(cutoff)])
 def test_fills_at_open(self):
  rows,orders,_=self.run_model();execution=date.fromisoformat(orders[0]['date']);p=copy.deepcopy(self.panel)
  for x in p[execution].values():x['open']=120
  _,updated,_=self.run_model(panel=p)
  self.assertEqual(updated[0]['price'],120)
 def test_units_do_not_reset_daily(self):
  _,orders,_=self.run_model();dates=sorted(self.panel)
  self.assertTrue(all(dates[dates.index(date.fromisoformat(x['date']))-1].month!=date.fromisoformat(x['date']).month for x in orders))
 def test_same_start_and_no_selection_uses_today(self):
  active,_,signals=self.run_model();passive,_,_=self.run_model(mode='passive')
  self.assertEqual(active[0]['date'],passive[0]['date'])
  d=date.fromisoformat(signals[0]['execution_date'])
  self.assertEqual(signals[0]['formation_month'],d.year*12+d.month-3)
 def test_attribution_reconciles(self):
  ledger=[]
  rows,_,_=simulate(self.panel,'high52',25,minimum=3,attribution=ledger)
  self.assertAlmostEqual(sum(x['net_pnl'] for x in ledger),rows[-1]['equity']-10000,places=6)
 def test_attribution_open_gap(self):
  _,orders,_=self.run_model();d=date.fromisoformat(orders[0]['date']);p=copy.deepcopy(self.panel)
  for x in p[d].values():x['open']=120
  ledger=[]
  rows,_,_=simulate(p,'high52',10,minimum=3,attribution=ledger)
  self.assertAlmostEqual(sum(x['net_pnl'] for x in ledger if x['date']==str(d)),rows[0]['equity']-10000,places=6)
 def test_position_weights_sum_to_exposure(self):
  ledger=[];rows,_,_=simulate(self.panel,'passive',10,minimum=3,attribution=ledger)
  for row in rows[::50]:
   self.assertAlmostEqual(sum(x['weight'] for x in ledger if x['date']==row['date']),row['gross_exposure'])
