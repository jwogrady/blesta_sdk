#!/usr/bin/env python3
"""Live benchmark: three approaches to fetching all transactions.

Requires valid .env credentials. Run directly:

    uv run python benchmarks/bench_transactions_live.py
"""

import os
import time

from dotenv import load_dotenv

from blesta_sdk import BlestaRequest

load_dotenv()


def get_api() -> BlestaRequest:
    url = os.environ["BLESTA_API_URL"]
    user = os.environ["BLESTA_API_USER"]
    key = os.environ["BLESTA_API_KEY"]
    return BlestaRequest(url, user, key)


def bench_global_getlist(api: BlestaRequest) -> dict:
    """Approach 1: transactions/getList (no client_id) — paginated 20/page."""
    start = time.perf_counter()
    txns = api.get_all("transactions", "getList")
    elapsed = time.perf_counter() - start
    return {"method": "global getList", "count": len(txns), "seconds": elapsed}


def bench_per_client_getlist(api: BlestaRequest) -> dict:
    """Approach 2: get all client IDs, then getList per client (20/page)."""
    t0 = time.perf_counter()
    clients = api.get_all("clients", "getList")
    client_time = time.perf_counter() - t0

    t1 = time.perf_counter()
    all_txns = []
    for client in clients:
        client_id = client.get("id") or client.get("client_id")
        if not client_id:
            continue
        txns = api.get_all("transactions", "getList", {"client_id": client_id})
        all_txns.extend(txns)
    txn_time = time.perf_counter() - t1

    total = time.perf_counter() - t0
    return {
        "method": "per-client getList",
        "clients": len(clients),
        "count": len(all_txns),
        "client_fetch_seconds": client_time,
        "txn_fetch_seconds": txn_time,
        "total_seconds": total,
    }


def bench_per_client_simplelist(api: BlestaRequest) -> dict:
    """Approach 3: get all client IDs, then getSimpleList per client.

    getSimpleList returns ALL transactions for a client in one request
    (no pagination), with a lighter payload (14 vs 24 fields), and
    includes all statuses (not just approved).
    """
    t0 = time.perf_counter()
    clients = api.get_all("clients", "getList")
    client_time = time.perf_counter() - t0

    t1 = time.perf_counter()
    all_txns = []
    for client in clients:
        client_id = client.get("id") or client.get("client_id")
        if not client_id:
            continue
        txns = api.get_all("transactions", "getSimpleList", {"client_id": client_id})
        all_txns.extend(txns)
    txn_time = time.perf_counter() - t1

    total = time.perf_counter() - t0
    return {
        "method": "per-client getSimpleList",
        "clients": len(clients),
        "count": len(all_txns),
        "client_fetch_seconds": client_time,
        "txn_fetch_seconds": txn_time,
        "total_seconds": total,
    }


def print_per_client_result(label: str, r: dict) -> None:
    print(f"  Clients:      {r['clients']}")
    print(f"  Transactions: {r['count']}")
    print(f"  Client fetch: {r['client_fetch_seconds']:.2f}s")
    print(f"  Txn fetch:    {r['txn_fetch_seconds']:.2f}s")
    print(f"  Total:        {r['total_seconds']:.2f}s")


def main():
    api = get_api()
    print(f"API: {api.base_url}\n")

    # --- Approach 1: global getList ---
    print("=" * 60)
    print("Approach 1: transactions/getList (no client_id, 20/page)")
    print("=" * 60)
    r1 = bench_global_getlist(api)
    print(f"  Transactions: {r1['count']}")
    print(f"  Time:         {r1['seconds']:.2f}s")

    # --- Approach 2: per-client getList ---
    print()
    print("=" * 60)
    print("Approach 2: per-client getList (status=approved, 20/page)")
    print("=" * 60)
    r2 = bench_per_client_getlist(api)
    print_per_client_result("per-client getList", r2)

    # --- Approach 3: per-client getSimpleList ---
    print()
    print("=" * 60)
    print("Approach 3: per-client getSimpleList (all statuses, no paging)")
    print("=" * 60)
    r3 = bench_per_client_simplelist(api)
    print_per_client_result("per-client getSimpleList", r3)

    # --- Comparison ---
    print()
    print("=" * 60)
    print("Comparison")
    print("=" * 60)
    results = [
        ("global getList", r1["seconds"], r1["count"]),
        ("per-client getList", r2["total_seconds"], r2["count"]),
        ("per-client getSimpleList", r3["total_seconds"], r3["count"]),
    ]
    fastest = min(results, key=lambda x: x[1])
    for name, secs, count in results:
        ratio = secs / fastest[1] if fastest[1] > 0 else 0
        marker = " <-- fastest" if name == fastest[0] else ""
        print(f"  {name:30s} {secs:7.2f}s  ({count:,} txns)  {ratio:.1f}x{marker}")

    # Note about count differences
    counts = {r[2] for r in results}
    if len(counts) > 1:
        print()
        print("  Note: count differences are expected:")
        print("    - getList defaults to status='approved'")
        print("    - getSimpleList returns all statuses")


if __name__ == "__main__":
    main()
