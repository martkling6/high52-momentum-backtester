"""Six partial-exit variants plus three BE-only controls; no winner selection."""
import argparse
import hashlib
import json
import statistics
from pathlib import Path
from daily import load, simulate, summary, write

VARIANTS = [(f'day{days}_{label}', days, fraction)
            for days in (3, 5, 10)
            for label, fraction in (('third', 1/3), ('half', 1/2))]
BE_VARIANTS = [(f'day{days}_be_only', days, 0) for days in (3, 5, 10)]


def run(panel, out):
    out.mkdir(parents=True, exist_ok=False)
    results = []
    for bps in (0, 10, 25):
        baseline = None
        for name, days, fraction in [('baseline', None, None), ('passive', None, None)] + VARIANTS + BE_VARIANTS:
            mode = 'passive' if name == 'passive' else 'high52'
            rows, orders, signals = simulate(panel, mode, bps, exit_days=days, exit_fraction=fraction)
            metrics = summary(rows)
            if name == 'baseline': baseline = metrics
            results.append({
                'variant': name, 'cost_bps': bps, 'exit_day': days,
                'partial_fraction': fraction, **metrics,
                'cagr_delta_vs_baseline': metrics['cagr'] - baseline['cagr'],
                'drawdown_delta_vs_baseline': metrics['max_daily_drawdown'] - baseline['max_daily_drawdown'],
                'average_gross_exposure': statistics.mean(r['gross_exposure'] for r in rows),
                'average_cash_fraction': statistics.mean(r['cash']/r['equity'] for r in rows),
                'total_costs': sum(o['fee'] for o in orders), 'order_count': len(orders),
                'partial_exits': sum(o.get('reason') == 'partial_next_open' for o in orders),
                'break_even_stops': sum(o.get('reason') == 'break_even_stop' for o in orders),
            })
            dest = out / f'{name}_{bps}bps'
            dest.mkdir()
            write(dest / 'daily.csv', rows)
            write(dest / 'orders.csv', orders)
            write(dest / 'signals.csv', signals)
    write(out / 'comparison.csv', results)
    return results


def main():
    parser = argparse.ArgumentParser()
    for key in ('data', 'manifest', 'out'): parser.add_argument('--' + key, required=True)
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text())
    if manifest.get('kind') not in ('exploratory_static_survivors', 'synthetic'):
        raise ValueError('Unreviewed daily data kind')
    results = run(load(args.data), Path(args.out))
    (Path(args.out) / 'run.json').write_text(json.dumps({
        'manifest': manifest,
        'input_sha256': hashlib.sha256(Path(args.data).read_bytes()).hexdigest(),
        'settings': {'initial': 10000, 'holding_months': 6, 'skip_months': 1,
                     'top_fraction': 0.3, 'cost_bps': [0, 10, 25],
                     'exit_days': [3, 5, 10], 'partial_fractions': [1/3, 1/2],
                     'be_only_days': [3, 5, 10], 'be_only_fraction': 0},
        'rules': [
            'Entry day is day 1. On day N close, check close > original adjusted entry price.',
            'One check only; if false, retain original six-month exit without a stop.',
            'If true, partial sale at next open, even if a gap erases the profit.',
            'Then remainder stop=original adjusted entry, not fee-adjusted.',
            'BE-only: no partial sale; activate entry-price stop on ALL units from next open.',
            'Stop fill=min(open,entry) when low<=entry, including partial-fill day.',
            'No initial stop, further partial exits or early re-entry.',
            'Cash stays in its sleeve until scheduled rotation, earning zero.',
            'Six-month rotation takes precedence over exit rules on that date.',
        ],
        'limitations': [
            'Static-survivor universe; no untouched out-of-sample validation.',
            'Adjusted total-return-unit OHLC, not physical-share dividend settlement.',
            'Daily OHLC stop approximation: threshold fills except opening gaps.',
            'Intraday gaps, halts, liquidity and exact stop slippage not observed.',
            'Generic 0/10/25bps allowance on every purchase and sale.',
            'Daily-close drawdown, no taxes or final liquidation.',
            'More cash can reduce drawdown without improving stock selection.',
            'Nine exit hypotheses on the same history; best result is not validated alpha.',
        ],
    }, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == '__main__': main()
