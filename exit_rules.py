"""Per-sleeve partial exits with next-open fills and subsequent entry-price stops."""
import math


def validate_exit_panel(panel):
    for bars in panel.values():
        for bar in bars.values():
            if any(k not in bar for k in ('open', 'high', 'low', 'close')):
                raise ValueError('Exit variants require complete OHLC bars')
            o, h, l, c = (bar[k] for k in ('open', 'high', 'low', 'close'))
            if not all(math.isfinite(v) and v > 0 for v in (o, h, l, c)) or l > min(o, c) or h < max(o, c):
                raise ValueError('Invalid OHLC range')


def process_exits(sleeves, bars, index, day, exit_days, fraction, rate, orders, flows):
    for sleeve_id, sleeve in enumerate(sleeves):
        for symbol, position in list(sleeve['positions'].items()):
            bar = bars[symbol]

            def sell(units, price, reason):
                notional = units * price
                fee = notional * rate
                sleeve['cash'] += notional - fee
                sleeve['units'][symbol] -= units
                flows[symbol] += notional - fee
                orders.append({'date': str(day), 'sleeve': sleeve_id, 'symbol': symbol,
                               'side': 'SELL', 'units': units, 'price': price,
                               'fee': fee, 'reason': reason})

            # The previous close is the only source of a pending partial order.
            # A gap can turn the intended profit-taking fill into a loss.
            if position['pending']:
                sell(sleeve['units'][symbol] * fraction, bar['open'], 'partial_next_open')
                position['pending'] = False
                position['armed'] = True

            # Stop is active immediately after the partial open fill. A gap below
            # entry liquidates the remainder at that same open, never at entry.
            if position['armed'] and bar['low'] <= position['entry']:
                price = min(bar['open'], position['entry'])
                sell(sleeve['units'][symbol], price, 'break_even_stop')
                del sleeve['units'][symbol]
                del sleeve['positions'][symbol]
                continue

            # Entry day counts as day 1. One opportunity only, not a recurring
            # check on later profitable days. No stop if this check fails.
            if index - position['entry_index'] + 1 == exit_days:
                position['pending'] = bar['close'] > position['entry']
