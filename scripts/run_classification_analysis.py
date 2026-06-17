#!/Users/pastry/.pyenv/versions/3.11.1/bin/python
"""
Final classification analysis: overtime events, progress fractions, edge cases.
"""
import httpx, json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from collections import Counter, defaultdict

ET = ZoneInfo("America/New_York")

def parse_dt(s):
    if not s: return None
    try: return datetime.fromisoformat(s.replace('Z','+00:00'))
    except: return None

def day_key_et(dt):
    return dt.astimezone(ET).strftime("%Y-%m-%d")

def same_et_day(a, b):
    return day_key_et(a) == day_key_et(b)

def progress_pct(open_time, close_time, expected_exp, latest_exp, now):
    """Calculate progress as % of time elapsed between open and expected_exp."""
    start = parse_dt(open_time)
    end = parse_dt(expected_exp) or parse_dt(latest_exp) or parse_dt(close_time)
    if not start or not end: return 0.0, "no_times"
    total = (end - start).total_seconds()
    if total <= 0: return 100.0, "already_expired"
    elapsed = (now - start).total_seconds()
    pct = max(0.0, min(100.0, elapsed / total * 100))
    if elapsed > total:
        return pct, "past_expected"
    return pct, "ongoing"

def classify_overtime_aware(market, now, max_overtime_hours=48):
    """Overtime-aware classification with reasonableness check."""
    reasons = []
    status = market.get('status')
    open_t = parse_dt(market.get('open_time'))
    close_t = parse_dt(market.get('close_time'))
    expected_exp = parse_dt(market.get('expected_expiration_time'))
    latest_exp = parse_dt(market.get('latest_expiration_time'))

    # Rule 1: Active and within trading window
    live_now = (status == 'active' and open_t and close_t and open_t <= now and close_t > now)
    if not live_now: reasons.append('Not currently trading')

    # Rule 2: Expected expiration is today ET
    expected_today = (expected_exp is not None and same_et_day(expected_exp, now))
    if not expected_today:
        reasons.append(f'Expected expiration not today ET')
        return False, 'past', 0, 0, reasons

    # Rule 3: Check overtime gap
    overtime = False
    ot_hours = 0
    ot_status = 'standard'
    
    if latest_exp:
        latest_today = same_et_day(latest_exp, now)
        if not latest_today and expected_exp:
            ot_hours = (latest_exp - expected_exp).total_seconds() / 3600
            overtime = True
            
            if ot_hours <= 6:
                ot_status = 'overtime_short'
                reasons.append(f'Short overtime window ({ot_hours:.1f}h) — game may run late')
            elif ot_hours <= 24:
                ot_status = 'overtime_medium'
                reasons.append(f'Medium overtime window ({ot_hours:.1f}h) — multi-day event')
            elif ot_hours <= max_overtime_hours:
                ot_status = 'overtime_long'
                reasons.append(f'Long overtime window ({ot_hours:.1f}h) — extended event')
            else:
                ot_status = 'composite'
                reasons.append(f'Composite event (gap={ot_hours:.0f}h) — not same-day')
                return False, ot_status, ot_hours, 0, reasons
        elif latest_today:
            reasons.append('Latest expiration also today — standard same-day')
    
    # Classification: expected today + reasonable overtime = same-day-live
    return True, ot_status, ot_hours, (latest_exp.timestamp() - expected_exp.timestamp())/3600 if latest_exp and expected_exp else 0, reasons


def main():
    print("=" * 72)
    print("KALSHI CLASSIFICATION — ENGINE 2 VERIFICATION")
    print(f"Run: {datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("=" * 72)

    # Fetch markets
    all_markets = []
    cursor = None
    while len(all_markets) < 2000:
        params = {'status': 'open', 'limit': 1000}
        if cursor: params['cursor'] = cursor
        r = httpx.get('https://external-api.kalshi.com/trade-api/v2/markets', params=params, timeout=30)
        data = r.json()
        all_markets.extend(data.get('markets', []))
        cursor = data.get('cursor')
        if not cursor: break
    
    now = datetime.now(timezone.utc)
    print(f"\nDataset: {len(all_markets)} open markets at {now.isoformat()[:19]}Z")
    
    # ─── 1. CLASSIFICATION WITH OVERTIME AWARENESS ───
    print("\n" + "─" * 72)
    print("1. CLASSIFICATION WITH OVERTIME AWARENESS")
    print("─" * 72)
    
    categories = Counter()
    examples_by_category = defaultdict(list)
    
    for m in all_markets:
        is_sdl, ot_status, ot_hours, gap, reasons = classify_overtime_aware(m, now)
        if is_sdl:
            categories[ot_status] += 1
            if len(examples_by_category[ot_status]) < 3:
                examples_by_category[ot_status].append(m)
        else:
            categories[ot_status] += 1

    print(f"\n  Same-day-live markets by overtime category:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        pct = count / len(all_markets) * 100
        print(f"    {cat:25s}: {count:5d} ({pct:5.1f}%)")
    
    total_sdl = sum(count for cat, count in categories.items() if cat != "past")
    print(f"\n  Total same-day-live candidates: {total_sdl}")
    
    # ─── 2. OVERTIME EXAMPLES ───
    print("\n" + "─" * 72)
    print("2. OVERTIME EXAMPLES (expected today, latest later)")
    print("─" * 72)
    
    for category in ['overtime_short', 'overtime_medium']:
        markets = examples_by_category.get(category, [])
        if markets:
            print(f"\n  Category: {category}")
            for m in markets[:3]:
                exp = parse_dt(m.get('expected_expiration_time'))
                lat = parse_dt(m.get('latest_expiration_time'))
                close = parse_dt(m.get('close_time'))
                gap_h = (lat - exp).total_seconds() / 3600 if exp and lat else 0
                pct, _ = progress_pct(m.get('open_time'), m.get('close_time'), m.get('expected_expiration_time'), m.get('latest_expiration_time'), now)
                print(f"    Event:      {m['event_ticker'][:45]}")
                print(f"    Title:      {m.get('title','')[:70]}")
                print(f"    Expected:   {exp.astimezone(ET).strftime('%m/%d %H:%M %Z') if exp else 'N/A'}")
                print(f"    Latest:     {lat.astimezone(ET).strftime('%m/%d %H:%M %Z') if lat else 'N/A'}")
                print(f"    Close:      {close.astimezone(ET).strftime('%m/%d %H:%M %Z') if close else 'N/A'}")
                print(f"    OT window:  {gap_h:.1f}h | Progress: {pct:.1f}%")

    # ─── 3. PROGRESS CALCULATION ───
    print("\n" + "─" * 72)
    print("3. PROGRESS CALCULATION (fractions of event completion)")
    print("─" * 72)
    
    # Take a same-day-live market and show progress at different reference points
    print("\n  Progress uses: start=open_time, end=expected_expiration_time")
    print("  Shows progress at: now, 30min ago, 30min ahead, and at key milestones\n")
    
    # Find a market with reasonable time window
    target_market = None
    for m in all_markets:
        exp = parse_dt(m.get('expected_expiration_time'))
        open_t = parse_dt(m.get('open_time'))
        if exp and open_t and same_et_day(exp, now):
            window = (exp - open_t).total_seconds() / 3600
            if 2 < window < 24:  # Between 2-24 hours — perfect for example
                target_market = m
                break
    
    if target_market:
        m = target_market
        exp = parse_dt(m.get('expected_expiration_time'))
        open_t = parse_dt(m.get('open_time'))
        close_t = parse_dt(m.get('close_time'))
        lat = parse_dt(m.get('latest_expiration_time'))
        
        print(f"  Event:        {m['event_ticker'][:45]}")
        print(f"  Title:        {m.get('title','')[:60]}")
        print(f"  Open:         {open_t.astimezone(ET).strftime('%m/%d %H:%M %Z')}")
        print(f"  Close:        {close_t.astimezone(ET).strftime('%m/%d %H:%M %Z') if close_t else 'N/A'}")
        print(f"  Expected exp: {exp.astimezone(ET).strftime('%m/%d %H:%M %Z') if exp else 'N/A'}")
        print(f"  Latest exp:   {lat.astimezone(ET).strftime('%m/%d %H:%M %Z') if lat else 'N/A'}")
        print(f"\n  Progress snapshots:")
        
        # Window size
        total = (exp - open_t).total_seconds()
        print(f"  Window:       {total/3600:.1f}h ({open_t.astimezone(ET).strftime('%H:%M')} → {exp.astimezone(ET).strftime('%H:%M')})")
        
        # Show progress at various points
        for label, ref_time in [
            ('At opening         ', open_t),
            ('At 25% complete    ', open_t + (exp - open_t) * 0.25),
            ('At 50% complete    ', open_t + (exp - open_t) * 0.50),
            ('At 65% complete    ', open_t + (exp - open_t) * 0.65),
            ('At 90% complete    ', open_t + (exp - open_t) * 0.90),
            ('At expected_exp    ', exp),
            ('Now                ', now),
        ]:
            elapsed = max(0, (ref_time - open_t).total_seconds())
            pct = min(100.0, elapsed / total * 100) if total > 0 else 0
            print(f"    {label}:  {ref_time.astimezone(ET).strftime('%H:%M %Z')}  →  {pct:.1f}%")
        
        # Show threshold crossing
        print(f"\n  Threshold analysis (default: 65%):")
        threshold_65 = open_t + (exp - open_t) * 0.65
        remaining = (exp - now).total_seconds() / 3600
        print(f"    65% threshold at: {threshold_65.astimezone(ET).strftime('%H:%M %Z')}")
        print(f"    Now:             {now.astimezone(ET).strftime('%H:%M %Z')}")
        print(f"    Time to expected resolution: {remaining:.1f}h")
        
        if now >= threshold_65:
            print(f"    ✅ THRESHOLD PASSED")
        else:
            time_to_threshold = (threshold_65 - now).total_seconds() / 3600
            print(f"    ❌ Below threshold (hits in {time_to_threshold:.1f}h)")
    
    # ─── 4. EDGE CASES ───
    print("\n" + "─" * 72)
    print("4. EDGE CASES")
    print("─" * 72)
    
    # Edge case 1: Markets with negative latest-expected gap
    neg_gap = []
    for m in all_markets:
        exp = parse_dt(m.get('expected_expiration_time'))
        lat = parse_dt(m.get('latest_expiration_time'))
        if exp and lat and lat < exp:
            neg_gap.append(m)
    print(f"\n  a) Markets where latest < expected (negative gap): {len(neg_gap)}")
    if neg_gap:
        m = neg_gap[0]
        exp = parse_dt(m.get('expected_expiration_time'))
        lat = parse_dt(m.get('latest_expiration_time'))
        print(f"     Example: expected={exp.astimezone(ET).strftime('%m/%d %H:%M') if exp else 'N/A'}, "
              f"latest={lat.astimezone(ET).strftime('%m/%d %H:%M') if lat else 'N/A'}")
        # These pass classification fine since only expected is checked
    
    # Edge case 2: Markets already past expected_exp but still active
    past_exp = []
    for m in all_markets:
        exp = parse_dt(m.get('expected_expiration_time'))
        if exp and now > exp and m.get('status') == 'active':
            close = parse_dt(m.get('close_time'))
            if close and close > now:
                past_exp.append(m)
    print(f"\n  b) Markets past expected_exp but still trading (overdue): {len(past_exp)}")
    if past_exp:
        for m in past_exp[:3]:
            exp = parse_dt(m.get('expected_expiration_time'))
            close = parse_dt(m.get('close_time'))
            lat = parse_dt(m.get('latest_expiration_time'))
            print(f"     {m['event_ticker'][:45]}: exp={exp.astimezone(ET).strftime('%H:%M') if exp else 'N/A'}, "
                  f"close={close.astimezone(ET).strftime('%m/%d %H:%M') if close else 'N/A'}, "
                  f"latest={lat.astimezone(ET).strftime('%m/%d %H:%M') if lat else 'N/A'}")
    
    # Edge case 3: Event has multiple markets, some pass, some don't
    print(f"\n  c) Markets with zero volume but still same-day-live:")
    zero_vol_sdl = 0
    for m in all_markets:
        is_sd, ot_status, _, _, _ = classify_overtime_aware(m, now)
        if is_sd:
            vol = float(m.get('volume_fp', 0) or 0)
            if vol == 0:
                zero_vol_sdl += 1
    print(f"     {zero_vol_sdl} same-day-live markets have zero trading volume")
    
    # Edge case 4: Event boundary at midnight ET
    print(f"\n  d) Midnight ET boundary check:")
    # Check if any markets have expected_exp exactly at 00:00 ET boundary
    midnight_markets = []
    for m in all_markets:
        exp = parse_dt(m.get('expected_expiration_time'))
        if exp and exp.astimezone(ET).hour == 0 and exp.astimezone(ET).minute == 0:
            midnight_markets.append(m)
    print(f"     Markets with expected_exp at midnight ET: {len(midnight_markets)}")
    if midnight_markets:
        m = midnight_markets[0]
        exp = parse_dt(m.get('expected_expiration_time'))
        print(f"     Example: exp={exp.astimezone(ET).strftime('%m/%d %H:%M %Z')} — "
              f"same_et_day check: {same_et_day(exp, now)}")

    print("\n" + "=" * 72)
    print("ANALYSIS COMPLETE")
    print("=" * 72)

if __name__ == '__main__':
    main()
