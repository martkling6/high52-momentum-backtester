import unittest,copy
from engine import simulate,weights_for
class Tests(unittest.TestCase):
 def setUp(self):
  self.cfg={'holding_months':6,'skip_months':1,'quantile':0.3,'minimum_universe':20,'cost_bps':10,'borrow_rate':0.02,'initial_capital':10000,'mode':'long_only'}
  self.panel={m:{f'S{i:02}':{'score':0.3+i/50,'return':0.001*i} for i in range(30)} for m in range(24000,24036)}
 def test_ranking(self):
  rows,sel=simulate(self.panel,self.cfg)
  self.assertEqual(rows[0]['month'],24002)
  self.assertEqual({x['symbol'] for x in sel if x['formation_month']==24000 and x['basket']=='winner'},{f'S{i:02}' for i in range(21,30)})
 def test_cohort_cap_and_ramp(self):
  rows,_=simulate(self.panel,self.cfg)
  self.assertAlmostEqual(rows[0]['gross_exposure'],1/6)
  self.assertAlmostEqual(rows[5]['gross_exposure'],1)
  self.assertTrue(all(x['cohorts']<=6 for x in rows))
 def test_future_mutations(self):
  a,_=simulate(self.panel,self.cfg);p=copy.deepcopy(self.panel)
  for m in range(24020,24036):
   for x in p[m].values():x['score']=0.7;x['return']=-0.5
  b,_=simulate(p,self.cfg)
  self.assertEqual([x for x in a if x['month']<24020],[x for x in b if x['month']<24020])
 def test_missing_held_return(self):
  p=copy.deepcopy(self.panel);del p[24005]['S29']
  with self.assertRaises(ValueError):simulate(p,self.cfg)
 def test_cost_effect(self):
  a,_=simulate(self.panel,self.cfg);b,_=simulate(self.panel,{**self.cfg,'cost_bps':0})
  self.assertLess(a[-1]['equity'],b[-1]['equity'])
 def test_short_borrow(self):
  a,_=simulate(self.panel,{**self.cfg,'mode':'long_short'})
  self.assertTrue(all(x['borrow_cost']>0 for x in a))
if __name__=='__main__':unittest.main()
