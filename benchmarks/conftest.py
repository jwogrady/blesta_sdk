"""Shared fixtures for benchmarks — synthetic payloads at realistic sizes."""

import json

import pytest


def make_json_payload(n_items: int) -> str:
    """Simulate a paginated JSON response with n_items."""
    items = [
        {
            "id": i,
            "firstname": f"User{i}",
            "lastname": "Test",
            "email": f"user{i}@example.com",
            "status": "active",
            "company": f"Company {i}",
            "address1": f"{i} Main St",
            "city": "Springfield",
            "state": "IL",
            "zip": "62701",
            "country": "US",
        }
        for i in range(n_items)
    ]
    return json.dumps({"response": items})


def make_csv_payload(n_rows: int) -> str:
    """Simulate a CSV report with n_rows."""
    header = "Package,Revenue,Tax,Total,Date,Client,Status"
    rows = [
        f"Package_{i},{i * 10.5},{i * 1.2},{i * 11.7},"
        f"2025-01-{(i % 28) + 1:02d},Client_{i},active"
        for i in range(n_rows)
    ]
    return header + "\n" + "\n".join(rows)


@pytest.fixture(params=[10, 100, 1000], ids=["10items", "100items", "1000items"])
def json_payload(request):
    """Parametrized JSON payload fixture."""
    return make_json_payload(request.param)


@pytest.fixture(params=[50, 500, 5000], ids=["50rows", "500rows", "5000rows"])
def csv_payload(request):
    """Parametrized CSV payload fixture."""
    return make_csv_payload(request.param)
