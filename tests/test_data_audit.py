import unittest
from datetime import date
from unittest.mock import patch
from data_audit import members,price_check,request

class AuditTests(unittest.TestCase):
 def test_membership_schema(self):
  self.assertEqual(len(members({'0':{'Code':'A','StartDate':'2013-01-01','EndDate':None}})),1)
 def test_invalid_membership_date(self):
  with self.assertRaises(ValueError):members([{'Code':'A','StartDate':'invalid'}])
 def test_missing_trading_date(self):
  rows=[{'date':'2020-01-02','adjusted_close':10},{'date':'2020-01-06','adjusted_close':11}]
  r=price_check(rows,{date(2020,1,d) for d in (2,3,6)})
  self.assertEqual(r['internal_missing_spy_dates'],1)
  self.assertEqual(r['status'],'REVIEW')
 def test_invalid_price(self):
  self.assertEqual(price_check([{'date':'2020-01-01','adjusted_close':-1}],set())['status'],'NO_VALID_PRICES')
 def test_no_secret_no_network(self):
  with patch.dict('os.environ',{},clear=True):
   self.assertEqual(request('anything',{}),(None,'MISSING_SECRET'))
