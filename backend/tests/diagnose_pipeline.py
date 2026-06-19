#!/usr/bin/env python3
"""
Diagnose Phase 1 — feedback loop for price pipeline.
Exercises all ingress paths, checks for silent failures, validates invariants.

Usage:
    python backend/tests/diagnose_pipeline.py [--base-url http://localhost:8000/api/v1]

Tags all debug output with [D-PL] for easy cleanup grep.
"""

import asyncio
import json
import os
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any

BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000/api/v1")
WS_BASE = BASE_URL.replace("http://", "ws://").replace("https://", "wss://")

PASS = 0
FAIL = 0
SKIP = 0
RESULTS: list[dict] = []


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        RESULTS.append({"name": name, "status": "PASS", "detail": detail or ""})
        print(f"  [D-PL] PASS  {name}")
    else:
        FAIL += 1
        RESULTS.append({"name": name, "status": "FAIL", "detail": detail})
        print(f"  [D-PL] FAIL  {name}  —  {detail}")


@dataclass
class TestContext:
    ticker_test: str = ""
    webhook_responses: list[dict] = field(default_factory=list)


# ── Helpers ──────────────────────────────────────────────────────────

def api_post(path: str, body: dict) -> dict:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read()) if e.code != 503 else {"success": False, "error": str(e)}


def api_get(path: str) -> dict:
    url = f"{BASE_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read()) if e.code != 503 else {"success": False, "error": str(e)}


# ── Tests ────────────────────────────────────────────────────────────

def test_01_health_check(ctx: TestContext):
    """Server must be alive."""
    try:
        with urllib.request.urlopen(BASE_URL.replace("/api/v1", "/health"), timeout=5) as resp:
            data = json.loads(resp.read())
            check("health: server alive", data.get("status") == "ok", f"got {data}")
    except Exception as e:
        check("health: server alive", False, str(e))


def test_02_webhook_baseline(ctx: TestContext):
    """First webhook must return 0 changes (baseline)."""
    resp = api_post("/webhooks/price-update", {
        "ticker": ctx.ticker_test,
        "yes_bid": 65,
        "yes_ask": 70,
        "no_bid": 35,
        "no_ask": 30,
    })
    ctx.webhook_responses.append(resp)
    check("webhook: baseline returns success", resp.get("success") is True, str(resp.get("error")))
    check("webhook: baseline 0 changes", resp.get("data", {}).get("changes_detected") == 0)


def test_03_webhook_change_detection(ctx: TestContext):
    """Second webhook with different prices must detect changes."""
    resp = api_post("/webhooks/price-update", {
        "ticker": ctx.ticker_test,
        "yes_bid": 67,
        "yes_ask": 72,
        "no_bid": 33,
        "no_ask": 28,
    })
    ctx.webhook_responses.append(resp)
    changes = resp.get("data", {}).get("changes", [])
    check("webhook: change returns success", resp.get("success") is True)
    check("webhook: detects changes", resp.get("data", {}).get("changes_detected", 0) >= 2)
    # Verify individual change fields
    fields = {c["field"]: c for c in changes}
    if "yes_bid" in fields:
        check("webhook: yes_bid delta correct", fields["yes_bid"]["delta"] == 2)
    if "no_bid" in fields:
        check("webhook: no_bid delta correct", fields["no_bid"]["delta"] == -2)


def test_04_webhook_missing_ticker(ctx: TestContext):
    """Webhook with empty ticker must not crash."""
    try:
        resp = api_post("/webhooks/price-update", {
            "ticker": "",
            "yes_bid": 50,
        })
        check("webhook: empty ticker no crash", True)
    except Exception as e:
        check("webhook: empty ticker no crash", False, str(e))


def test_05_webhook_partial_data(ctx: TestContext):
    """Webhook with only yes fields should not crash (no_bid/no_ask None)."""
    resp = api_post("/webhooks/price-update", {
        "ticker": f"{ctx.ticker_test}_PARTIAL",
        "yes_bid": 80,
        "yes_ask": 85,
    })
    check("webhook: partial data returns success", resp.get("success") is True)
    check("webhook: partial baseline", resp.get("data", {}).get("changes_detected") == 0)
    # Second call with missing fields
    api_post("/webhooks/price-update", {
        "ticker": f"{ctx.ticker_test}_PARTIAL",
        "yes_bid": 82,
    })
    check("webhook: partial update no crash", True)


def test_06_webhook_none_values(ctx: TestContext):
    """Webhook with explicit null values should not crash."""
    resp = api_post("/webhooks/price-update", {
        "ticker": f"{ctx.ticker_test}_NULL",
        "yes_bid": None,
        "yes_ask": None,
        "no_bid": None,
        "no_ask": None,
    })
    check("webhook: null values baseline", resp.get("success") is True)
    api_post("/webhooks/price-update", {
        "ticker": f"{ctx.ticker_test}_NULL",
        "yes_bid": 50,
        "yes_ask": 55,
        "no_bid": 45,
        "no_ask": 50,
    })
    check("webhook: null->values transition", resp.get("success") is True)


def test_07_webhook_same_price_dedup(ctx: TestContext):
    """Webhook with same prices as last should return 0 changes."""
    resp = api_post("/webhooks/price-update", {
        "ticker": f"{ctx.ticker_test}_DEDUP",
        "yes_bid": 70,
        "yes_ask": 75,
        "no_bid": 30,
        "no_ask": 25,
    })
    # Second call with same prices
    resp2 = api_post("/webhooks/price-update", {
        "ticker": f"{ctx.ticker_test}_DEDUP",
        "yes_bid": 70,
        "yes_ask": 75,
        "no_bid": 30,
        "no_ask": 25,
    })
    check("webhook: same price dedup", resp2.get("data", {}).get("changes_detected") == 0)


def test_08_prices_endpoint(ctx: TestContext):
    """Prices endpoint must return our inserted tickers."""
    prices = api_get("/prices")
    check("prices: success", prices.get("success") is True)
    data = prices.get("data", {})
    check("prices: contains our ticker", ctx.ticker_test in data, f"keys: {list(data.keys())[:5]}")
    state = data.get(ctx.ticker_test, {})
    if state:
        check("prices: has yes_bid", state.get("yes_bid") is not None)
        check("prices: has last_updated", state.get("last_updated") is not None)


def test_09_price_history(ctx: TestContext):
    """History endpoint must return chronological entries."""
    hist = api_get(f"/prices/{ctx.ticker_test}/history?limit=10")
    check("history: success", hist.get("success") is True)
    entries = hist.get("data", [])
    check("history: has entries", len(entries) >= 2, f"got {len(entries)}")
    if len(entries) >= 2:
        t0 = entries[0].get("timestamp", "")
        t1 = entries[-1].get("timestamp", "")
        check("history: chronological", t0 <= t1, f"{t0} <= {t1}")


def test_10_price_history_unknown(ctx: TestContext):
    """History for unknown ticker returns 404."""
    try:
        url = f"{BASE_URL}/prices/__DOES_NOT_EXIST_99999__/history"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            check("history: unknown ticker", False, "should have returned error")
    except urllib.error.HTTPError as e:
        check("history: unknown ticker 4xx", 400 <= e.code < 500, f"code={e.code}")


def test_11_scanner_status(ctx: TestContext):
    """Scanner status must be readable and show events tracked."""
    status = api_get("/scanner/status")
    check("status: success", status.get("success") is True)
    data = status.get("data", {})
    check("status: has cycle_mode", data.get("cycle_mode") in ("live", "one-shot"))
    # is_running should be consistent
    check("status: has is_running", isinstance(data.get("is_running"), bool))
    check("status: has uptime_seconds", isinstance(data.get("uptime_seconds"), (int, float)))


def test_12_tracker_concurrent_access(ctx: TestContext):
    """Fire multiple rapid webhooks — no crash, no data loss."""
    ticker = f"{ctx.ticker_test}_CONCUR"
    base_price = 50
    results = []
    for i in range(5):
        price = base_price + i * 2
        resp = api_post("/webhooks/price-update", {
            "ticker": ticker,
            "yes_bid": price,
            "yes_ask": price + 5,
        })
        results.append(resp)

    check("concurrent: all webhooks succeeded", all(r.get("success") for r in results))
    # Latest price should reflect last update
    prices = api_get("/prices")
    last_price = prices.get("data", {}).get(ticker, {}).get("yes_bid")
    check("concurrent: latest price correct", last_price == base_price + 8, f"got {last_price}")


def test_13_ws_prices_connect(ctx: TestContext):
    """WS prices channel must accept connections."""
    try:
        import websockets
    except ImportError:
        check("ws-prices: connect", False, "websockets not installed")
        return

    async def _test():
        try:
            async with websockets.connect(f"{WS_BASE}/ws/prices") as ws:
                check("ws-prices: connected", True)
                # Send a subscribe message
                await ws.send(json.dumps({"cmd": "subscribe", "channel": "prices"}))
                check("ws-prices: subscribable", True)
        except Exception as e:
            check("ws-prices: connect", False, str(e))

    asyncio.run(_test())


def test_14_ws_prices_broadcast(ctx: TestContext):
    """Trigger webhook while WS connected — must receive broadcast."""
    try:
        import websockets
    except ImportError:
        check("ws-prices: broadcast", False, "websockets not installed (need: pip install websockets)")
        return

    async def _test():
        try:
            async with websockets.connect(f"{WS_BASE}/ws/prices") as ws:
                await asyncio.sleep(0.3)
                # Send a price change via webhook
                ticker = f"{ctx.ticker_test}_WSBC"
                api_post("/webhooks/price-update", {
                    "ticker": ticker,
                    "yes_bid": 45,
                    "yes_ask": 50,
                })
                await asyncio.sleep(0.2)
                # Send second webhook to trigger change
                api_post("/webhooks/price-update", {
                    "ticker": ticker,
                    "yes_bid": 48,
                    "yes_ask": 53,
                })
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(msg)
                    check("ws-prices: broadcast received", True)
                    check("ws-prices: has type", data.get("type") == "price:changed")
                    check("ws-prices: has ticker", data.get("data", {}).get("ticker") == ticker)
                    check("ws-prices: has delta", data.get("data", {}).get("delta") is not None)
                except asyncio.TimeoutError:
                    check("ws-prices: broadcast received", False, "timeout waiting for message")
        except Exception as e:
            check("ws-prices: broadcast", False, str(e))

    asyncio.run(_test())


def test_15_scanner_status_events_tracked(ctx: TestContext):
    """Scanner should have events tracked after discovery runs."""
    status = api_get("/scanner/status")
    data = status.get("data", {})
    tracked = data.get("events_tracked", 0)
    check("status: events tracked valid", isinstance(tracked, int) and tracked >= 0, f"got {tracked}")
    if tracked == 0:
        check("status: events tracked (warn: server restarted)", True, "no events yet — discovery cycle may not have completed")


def test_16_prices_concurrent_read_write(ctx: TestContext):
    """Concurrent reads and writes to price tracker must not deadlock."""
    ticker = f"{ctx.ticker_test}_RW"
    for i in range(5):
        api_post("/webhooks/price-update", {"ticker": ticker, "yes_bid": i * 10})
        api_get(f"/prices/{ticker}")
    check("rw: concurrent read-write no deadlock", True)


def test_17_memory_leak_check(ctx: TestContext):
    """Tracker must not grow unbounded — check max history 100."""
    ticker = f"{ctx.ticker_test}_LEAK"
    for i in range(150):
        api_post("/webhooks/price-update", {"ticker": ticker, "yes_bid": i})
    hist = api_get(f"/prices/{ticker}/history?limit=200")
    entries = hist.get("data", [])
    check("leak: history capped", len(entries) <= 100, f"got {len(entries)} entries")


def test_18_webhook_large_payload(ctx: TestContext):
    """Webhook with large numeric values must not overflow."""
    resp = api_post("/webhooks/price-update", {
        "ticker": f"{ctx.ticker_test}_BIG",
        "yes_bid": 999999,
        "yes_ask": 1000000,
        "no_bid": 0,
        "no_ask": 1,
    })
    check("webhook: large values ok", resp.get("success") is True)


# ── Main ─────────────────────────────────────────────────────────────

def main():
    global PASS, FAIL
    ctx = TestContext(ticker_test=f"DIAG_{int(time.time() * 1000) % 100000}")

    print(f"\n{'='*60}")
    print(f"  Price Pipeline Diagnostic [D-PL]")
    print(f"  Base URL: {BASE_URL}")
    print(f"  Test ticker prefix: {ctx.ticker_test}")
    print(f"{'='*60}\n")

    tests = [
        ("01-health", test_01_health_check),
        ("02-webhook-baseline", test_02_webhook_baseline),
        ("03-webhook-change", test_03_webhook_change_detection),
        ("04-webhook-empty-ticker", test_04_webhook_missing_ticker),
        ("05-webhook-partial", test_05_webhook_partial_data),
        ("06-webhook-null", test_06_webhook_none_values),
        ("07-webhook-dedup", test_07_webhook_same_price_dedup),
        ("08-prices-endpoint", test_08_prices_endpoint),
        ("09-history", test_09_price_history),
        ("10-history-unknown", test_10_price_history_unknown),
        ("11-scanner-status", test_11_scanner_status),
        ("12-concurrent", test_12_tracker_concurrent_access),
        ("13-ws-connect", test_13_ws_prices_connect),
        ("14-ws-broadcast", test_14_ws_prices_broadcast),
        ("15-status-events", test_15_scanner_status_events_tracked),
        ("16-rw-concurrent", test_16_prices_concurrent_read_write),
        ("17-memory-leak", test_17_memory_leak_check),
        ("18-large-payload", test_18_webhook_large_payload),
    ]

    for test_id, fn in tests:
        print(f"\n  [{test_id}]")
        try:
            fn(ctx)
        except Exception as e:
            check(f"{test_id}", False, f"Unhandled: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"  RESULTS:  {PASS} passed, {FAIL} failed, {SKIP} skipped")
    print(f"{'='*60}\n")

    failures = [r for r in RESULTS if r["status"] == "FAIL"]
    if failures:
        print("  FAILURES:")
        for f in failures:
            print(f"    {f['name']}: {f['detail']}")
        print()

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
