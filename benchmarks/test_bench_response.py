"""Benchmarks for BlestaResponse parsing — pure CPU, no network.

Measures JSON parsing, CSV parsing, DataFrame conversion, and
the is_json/is_csv detection overhead. These are the SDK's local
hot paths that don't depend on network latency.

Run:
    uv run pytest benchmarks/test_bench_response.py -v --benchmark-sort=mean
"""

from benchmarks.conftest import make_csv_payload, make_json_payload
from blesta_sdk import BlestaResponse

# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


class TestJsonParsing:
    """Benchmark .data property — json.loads + dict key lookup."""

    def test_data_access_10(self, benchmark):
        payload = make_json_payload(10)
        benchmark(lambda: BlestaResponse(payload, 200).data)

    def test_data_access_100(self, benchmark):
        payload = make_json_payload(100)
        benchmark(lambda: BlestaResponse(payload, 200).data)

    def test_data_access_1000(self, benchmark):
        payload = make_json_payload(1000)
        benchmark(lambda: BlestaResponse(payload, 200).data)

    def test_data_cached_access(self, benchmark):
        """Second .data access uses cached _parsed — should be near-zero."""
        resp = BlestaResponse(make_json_payload(1000), 200)
        _ = resp.data  # prime the cache
        benchmark(lambda: resp.data)

    def test_is_json_true(self, benchmark):
        payload = make_json_payload(100)
        benchmark(lambda: BlestaResponse(payload, 200).is_json)

    def test_is_json_false(self, benchmark):
        csv = make_csv_payload(100)
        benchmark(lambda: BlestaResponse(csv, 200).is_json)


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


class TestCsvParsing:
    """Benchmark .csv_data — csv.DictReader parse of raw text."""

    def test_csv_data_50(self, benchmark):
        payload = make_csv_payload(50)
        benchmark(lambda: BlestaResponse(payload, 200).csv_data)

    def test_csv_data_500(self, benchmark):
        payload = make_csv_payload(500)
        benchmark(lambda: BlestaResponse(payload, 200).csv_data)

    def test_csv_data_5000(self, benchmark):
        payload = make_csv_payload(5000)
        benchmark(lambda: BlestaResponse(payload, 200).csv_data)

    def test_is_csv_on_csv(self, benchmark):
        """is_csv calls is_json internally — measures redundant json.loads."""
        csv = make_csv_payload(100)
        benchmark(lambda: BlestaResponse(csv, 200).is_csv)

    def test_is_csv_on_json(self, benchmark):
        """is_csv on JSON should short-circuit at is_json check."""
        payload = make_json_payload(100)
        benchmark(lambda: BlestaResponse(payload, 200).is_csv)

    def test_csv_data_cached_access(self, benchmark):
        """Second .csv_data access uses cache — should be near-zero."""
        resp = BlestaResponse(make_csv_payload(500), 200)
        _ = resp.csv_data  # prime the cache
        benchmark(lambda: resp.csv_data)


# ---------------------------------------------------------------------------
# DataFrame conversion
# ---------------------------------------------------------------------------


class TestDataFrame:
    """Benchmark .to_dataframe() for CSV and JSON responses."""

    def test_to_dataframe_csv_50(self, benchmark):
        resp = BlestaResponse(make_csv_payload(50), 200)
        benchmark(resp.to_dataframe)

    def test_to_dataframe_csv_500(self, benchmark):
        resp = BlestaResponse(make_csv_payload(500), 200)
        benchmark(resp.to_dataframe)

    def test_to_dataframe_json_10(self, benchmark):
        resp = BlestaResponse(make_json_payload(10), 200)
        benchmark(resp.to_dataframe)

    def test_to_dataframe_json_100(self, benchmark):
        resp = BlestaResponse(make_json_payload(100), 200)
        benchmark(resp.to_dataframe)


# ---------------------------------------------------------------------------
# Error extraction
# ---------------------------------------------------------------------------


class TestErrors:
    """Benchmark .errors() on success and failure responses."""

    def test_errors_on_success(self, benchmark):
        resp = BlestaResponse(make_json_payload(100), 200)
        benchmark(resp.errors)

    def test_errors_on_failure(self, benchmark):
        resp = BlestaResponse('{"errors": {"field": "bad"}}', 400)
        benchmark(resp.errors)

    def test_errors_on_csv(self, benchmark):
        resp = BlestaResponse(make_csv_payload(100), 200)
        benchmark(resp.errors)
