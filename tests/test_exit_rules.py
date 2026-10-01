import copy
import unittest
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import date, timedelta
from daily import simulate
from download_daily import adjusted_bar
from exit_rules import process_exits, validate_exit_panel
from exit_study import VARIANTS


class ExitRulesTests(unittest.TestCase):
    def setUp(self):
        self.sleeves = [{'cash': 0., 'units': {'A': 9.}, 'positions': {
            'A': {'entry': 100., 'entry_index': 0, 'pending': False, 'armed': False}}}]
        self.orders = []
        self.flows = {'A': 0.}

    def step(self, index, o=110., h=115., l=105., c=110., days=3, fraction=1/3, rate=0.):
        process_exits(self.sleeves, {'A': {'open': o, 'high': h, 'low': l, 'close': c}},
                      index, date(2020, 1, 1) + timedelta(days=index), days, fraction,
                      rate, self.orders, self.flows)

    def test_grid_exactly_six(self):
        self.assertEqual(len(VARIANTS), 6)
        self.assertEqual({(d, f) for _, d, f in VARIANTS},
                         {(d, f) for d in (3, 5, 10) for f in (1/3, 1/2)})

    def test_each_variant_waits_until_next_open(self):
        for _, days, fraction in VARIANTS:
            self.setUp()
            for i in range(days):
                self.step(i, days=days, fraction=fraction)
                self.assertEqual(self.orders, [])
            self.step(days, o=112, days=days, fraction=fraction)
            self.assertEqual(len(self.orders), 1)
            self.assertAlmostEqual(self.orders[0]['units'], 9*fraction)
            self.assertEqual(self.orders[0]['price'], 112)
            self.assertAlmostEqual(self.sleeves[0]['units']['A'], 9*(1-fraction))

    def test_no_profit_no_stop_and_no_late_retry(self):
        self.step(2, o=99, h=100, l=90, c=100)
        for i in range(3, 15): self.step(i)
        self.assertEqual(self.orders, [])
        self.assertFalse(self.sleeves[0]['positions']['A']['armed'])

    def test_no_initial_stop(self):
        self.step(0, o=100, h=101, l=50, c=60)
        self.assertEqual(self.orders, [])

    def test_same_day_partial_then_stop(self):
        self.step(2)
        self.step(3, o=110, h=120, l=99, c=115)
        self.assertEqual([o['price'] for o in self.orders], [110, 100])
        self.assertEqual([o['units'] for o in self.orders], [3, 6])
        self.assertEqual(self.sleeves[0]['cash'], 930)
        self.assertEqual(self.sleeves[0]['units'], {})

    def test_partial_gap_below_entry_sells_all_at_open(self):
        self.step(2)
        self.step(3, o=90, h=110, l=85, c=105, rate=.001)
        self.assertEqual([o['price'] for o in self.orders], [90, 90])
        self.assertAlmostEqual(self.sleeves[0]['cash'], 810*.999)
        self.assertAlmostEqual(sum(o['fee'] for o in self.orders), .81)

    def test_later_gap_stop(self):
        self.step(2); self.step(3)
        self.step(4, o=80, h=90, l=70, c=85)
        self.assertEqual(self.orders[-1]['price'], 80)
        self.assertEqual(self.orders[-1]['reason'], 'break_even_stop')

    def test_low_exactly_entry_triggers(self):
        self.step(2); self.step(3, l=100)
        self.assertEqual(self.sleeves[0]['units'], {})

    def test_no_second_partial(self):
        for i in range(15): self.step(i)
        self.assertEqual(len(self.orders), 1)

    def test_pending_order_needs_a_following_bar(self):
        self.step(2)
        self.assertTrue(self.sleeves[0]['positions']['A']['pending'])
        self.assertEqual(self.orders, [])

    def test_adjusted_ohlc(self):
        self.assertEqual(adjusted_bar({'open': 100, 'high': 120, 'low': 90,
                                      'close': 110, 'adjusted_close': 55}),
                         {'open': 50, 'high': 60, 'low': 45, 'close': 55})

    def test_invalid_or_missing_ohlc_rejected(self):
        for bar in ({'open': 100, 'close': 100},
                    {'open': 100, 'close': 100, 'high': 90, 'low': 80}):
            with self.assertRaises(ValueError): validate_exit_panel({date(2020,1,1): {'A': bar}})


class ExitIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.panel = {}
        day = date(2000, 1, 1)
        for i in range(1000):
            if day.weekday() < 5:
                price = 100 + i*.1
                self.panel[day] = {s: {'open': price, 'high': price+2,
                                      'low': price-2, 'close': price+1} for s in ('A','B','C')}
            day += timedelta(days=1)

    def test_attribution_cash_and_future_independence(self):
        ledger = []
        rows, orders, _ = simulate(self.panel, minimum=3, exit_days=3,
                                  exit_fraction=1/3, attribution=ledger)
        self.assertAlmostEqual(sum(x['net_pnl'] for x in ledger), rows[-1]['equity']-10000, places=6)
        self.assertTrue(all(r['cash'] >= 0 and 0 <= r['gross_exposure'] <= 1.00000001 for r in rows))
        self.assertTrue(any(o['reason']=='partial_next_open' for o in orders))
        self.assertTrue(any(o['reason']=='break_even_stop' for o in orders))
        cut = sorted(self.panel)[450]
        changed = copy.deepcopy(self.panel)
        for d in changed:
            if d > cut:
                for bar in changed[d].values():
                    for key in bar: bar[key] *= 2
        later, later_orders, _ = simulate(changed, minimum=3, exit_days=3, exit_fraction=1/3)
        self.assertEqual([r for r in rows if r['date']<=str(cut)], [r for r in later if r['date']<=str(cut)])
        self.assertEqual([o for o in orders if o['date']<=str(cut)], [o for o in later_orders if o['date']<=str(cut)])

    def test_baseline_ignores_high_low(self):
        without = {d: {s: {'open': b['open'], 'close': b['close']} for s,b in bars.items()}
                   for d,bars in self.panel.items()}
        self.assertEqual(simulate(self.panel, minimum=3), simulate(without, minimum=3))

    def test_cash_not_reinvested_before_rotation(self):
        rows, orders, _ = simulate(self.panel, minimum=3, exit_days=3, exit_fraction=1/2)
        buys = [o for o in orders if o['side']=='BUY']
        for sleeve in range(6):
            dates = sorted({date.fromisoformat(o['date']) for o in buys if o['sleeve']==sleeve})
            for first, second in zip(dates, dates[1:]):
                self.assertEqual((second.year-first.year)*12 + second.month-first.month, 6)
        self.assertTrue(any(r['cash']/r['equity'] > .5 for r in rows[150:]))

    def test_full_cli_exports_all_scenarios(self):
        with tempfile.TemporaryDirectory(prefix='high52-exit-test-') as tmp:
            root = Path(tmp)
            with (root/'data.csv').open('w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['date','symbol','open','high','low','close'])
                for day, bars in self.panel.items():
                    bar = bars['A']
                    for i in range(20):
                        w.writerow([day, f'S{i:02}', bar['open'],bar['high'],bar['low'],bar['close']])
            (root/'manifest.json').write_text(json.dumps({'kind':'synthetic'}))
            result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/'exit_study.py'),
                                     '--data', str(root/'data.csv'), '--manifest', str(root/'manifest.json'),
                                     '--out', str(root/'results')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with (root/'results/comparison.csv').open() as f: rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 24)
            self.assertEqual(len(list((root/'results').glob('*/orders.csv'))), 24)
            self.assertEqual(len(json.loads((root/'results/run.json').read_text())['settings']['exit_days']), 3)
            self.assertTrue(all(float(r['total_costs'])==0 for r in rows if r['cost_bps']=='0'))
