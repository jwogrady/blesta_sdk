"""Tests for AsyncBlestaRequest — async HTTP client."""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from blesta_sdk import AsyncBlestaRequest
from blesta_sdk._response import BlestaResponse


@pytest.fixture
def async_api():
    return AsyncBlestaRequest("https://example.com/api", "user", "key")


# --- Auth method ---


def test_async_header_auth_sets_headers():
    """auth_method='header' sets custom headers, no BasicAuth."""
    api = AsyncBlestaRequest(
        "https://example.com/api", "myuser", "mykey", auth_method="header"
    )
    assert api.auth_method == "header"
    assert api.client.headers["BLESTA-API-USER"] == "myuser"
    assert api.client.headers["BLESTA-API-KEY"] == "mykey"


def test_async_header_auth_default_is_basic():
    """Default auth_method is 'basic' (backward-compatible)."""
    api = AsyncBlestaRequest("https://example.com/api", "user", "key")
    assert api.auth_method == "basic"


async def test_async_header_auth_request_succeeds():
    """Header auth sends requests successfully."""
    api = AsyncBlestaRequest(
        "https://example.com/api", "user", "key", auth_method="header"
    )
    mock_response = Mock(text='{"response": {}}', status_code=200)
    with patch.object(
        api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        response = await api.get("clients", "getList")
    assert response.status_code == 200


# --- Constructor / repr ---


def test_async_repr():
    api = AsyncBlestaRequest("https://example.com/api", "user", "key")
    assert (
        repr(api) == "AsyncBlestaRequest(url='https://example.com/api/', user='user')"
    )


def test_async_base_url_normalization():
    api = AsyncBlestaRequest("https://example.com/api/", "u", "k")
    assert api.base_url == "https://example.com/api/"


def test_async_get_last_request_none():
    api = AsyncBlestaRequest("https://example.com/api", "u", "k")
    assert api.get_last_request() is None


# --- HTTP method dispatch ---


@pytest.mark.parametrize(
    "method_name,http_method",
    [("get", "get"), ("post", "post"), ("put", "put"), ("delete", "delete")],
)
async def test_async_http_methods(async_api, method_name, http_method):
    """Each HTTP method dispatches to the correct httpx client method."""
    mock_response = Mock(text='{"response": {"ok": true}}', status_code=200)
    with patch.object(
        async_api.client,
        http_method,
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        response = await getattr(async_api, method_name)("clients", "getList")
    assert isinstance(response, BlestaResponse)
    assert response.status_code == 200


async def test_async_get_passes_params(async_api):
    """GET passes args as query params."""
    mock_response = Mock(text='{"response": {}}', status_code=200)
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ) as mock_get:
        await async_api.get("clients", "getList", {"status": "active"})
    mock_get.assert_called_once_with(
        "https://example.com/api/clients/getList.json",
        params={"status": "active"},
    )


async def test_async_post_passes_json(async_api):
    """POST passes args as JSON body."""
    mock_response = Mock(text='{"response": {}}', status_code=200)
    with patch.object(
        async_api.client, "post", new_callable=AsyncMock, return_value=mock_response
    ) as mock_post:
        await async_api.post("clients", "create", {"name": "Test"})
    mock_post.assert_called_once_with(
        "https://example.com/api/clients/create.json",
        json={"name": "Test"},
    )


async def test_async_submit_invalid_action(async_api):
    """Invalid action raises ValueError."""
    with pytest.raises(ValueError, match="Invalid HTTP action"):
        await async_api.submit("clients", "getList", action="PATCH")


async def test_async_submit_tracks_last_request(async_api):
    """submit() updates get_last_request()."""
    mock_response = Mock(text='{"response": {}}', status_code=200)
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        await async_api.get("clients", "getList", {"page": 1})
    last = async_api.get_last_request()
    assert last["url"] == "https://example.com/api/clients/getList.json"
    assert last["args"] == {"page": 1}


# --- Error handling ---


async def test_async_network_error(async_api):
    """Network error returns BlestaResponse with status_code=0."""
    import httpx

    with patch.object(
        async_api.client,
        "get",
        new_callable=AsyncMock,
        side_effect=httpx.ConnectError("connection refused"),
    ):
        response = await async_api.get("clients", "getList")
    assert response.status_code == 0


# --- Retry ---


@patch("blesta_sdk._async_client.asyncio.sleep", new_callable=AsyncMock)
async def test_async_retry_on_500(mock_sleep):
    """Retries on 5xx, succeeds on second attempt."""
    api = AsyncBlestaRequest("https://example.com/api", "u", "k", max_retries=2)
    responses = [
        Mock(text="error", status_code=500),
        Mock(text='{"response": []}', status_code=200),
    ]
    with patch.object(api.client, "get", new_callable=AsyncMock, side_effect=responses):
        response = await api.get("clients", "getList")
    assert response.status_code == 200
    mock_sleep.assert_called_once_with(1)


@patch("blesta_sdk._async_client.asyncio.sleep", new_callable=AsyncMock)
async def test_async_retry_exhausted(mock_sleep):
    """Returns last response after all retries fail."""
    api = AsyncBlestaRequest("https://example.com/api", "u", "k", max_retries=2)
    mock_response = Mock(text="error", status_code=502)
    with patch.object(
        api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        response = await api.get("clients", "getList")
    assert response.status_code == 502
    assert mock_sleep.call_count == 2


async def test_async_no_retry_on_4xx(async_api):
    """4xx responses are not retried."""
    mock_response = Mock(text='{"errors": {"message": "not found"}}', status_code=404)
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        response = await async_api.get("clients", "get", {"id": 999})
    assert response.status_code == 404


# --- Pagination ---


async def test_async_iter_all(async_api):
    """iter_all yields items across pages and stops on empty."""
    responses = [
        Mock(text=json.dumps({"response": [{"id": 1}, {"id": 2}]}), status_code=200),
        Mock(text=json.dumps({"response": [{"id": 3}]}), status_code=200),
        Mock(text=json.dumps({"response": []}), status_code=200),
    ]
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, side_effect=responses
    ):
        result = [item async for item in async_api.iter_all("clients", "getList")]
    assert result == [{"id": 1}, {"id": 2}, {"id": 3}]


async def test_async_get_all(async_api):
    """get_all returns a flat list from all pages."""
    responses = [
        Mock(text=json.dumps({"response": [{"id": 1}]}), status_code=200),
        Mock(text=json.dumps({"response": []}), status_code=200),
    ]
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, side_effect=responses
    ):
        result = await async_api.get_all("clients", "getList")
    assert result == [{"id": 1}]


async def test_async_iter_all_stops_on_error(async_api):
    """iter_all stops on non-200 status."""
    responses = [
        Mock(text=json.dumps({"response": [{"id": 1}]}), status_code=200),
        Mock(text="error", status_code=500),
    ]
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, side_effect=responses
    ):
        result = [item async for item in async_api.iter_all("clients", "getList")]
    assert result == [{"id": 1}]


async def test_async_iter_all_single_object(async_api):
    """iter_all yields a single object and stops."""
    mock_response = Mock(
        text=json.dumps({"response": {"id": 1, "name": "test"}}), status_code=200
    )
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        result = [item async for item in async_api.iter_all("clients", "get")]
    assert result == [{"id": 1, "name": "test"}]


# --- count() ---


async def test_async_count(async_api):
    """count() returns integer from API response."""
    mock_response = Mock(text=json.dumps({"response": 22376}), status_code=200)
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        result = await async_api.count("transactions")
    assert result == 22376


async def test_async_count_returns_zero_on_error(async_api):
    """count() returns 0 on non-200."""
    mock_response = Mock(text="error", status_code=500)
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        assert await async_api.count("transactions") == 0


# --- extract() ---


async def test_async_extract(async_api):
    """extract() fetches multiple targets and returns dict."""
    responses = [
        # clients: 1 page + empty
        Mock(text=json.dumps({"response": [{"id": 1}]}), status_code=200),
        Mock(text=json.dumps({"response": []}), status_code=200),
        # invoices: 1 page + empty
        Mock(text=json.dumps({"response": [{"id": 10}]}), status_code=200),
        Mock(text=json.dumps({"response": []}), status_code=200),
    ]
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, side_effect=responses
    ):
        result = await async_api.extract(
            [
                ("clients", "getList"),
                ("invoices", "getList"),
            ]
        )
    assert "clients.getList" in result
    assert "invoices.getList" in result


async def test_async_extract_with_args(async_api):
    """extract() passes args through to get_all."""
    responses = [
        Mock(text=json.dumps({"response": [{"id": 1}]}), status_code=200),
        Mock(text=json.dumps({"response": []}), status_code=200),
    ]
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, side_effect=responses
    ):
        result = await async_api.extract(
            [
                ("transactions", "getList", {"status": "approved"}),
            ]
        )
    assert "transactions.getList" in result


# --- Context manager ---


async def test_async_context_manager():
    """async with closes the client."""
    api = AsyncBlestaRequest("https://example.com/api", "user", "key")
    with patch.object(api.client, "aclose", new_callable=AsyncMock) as mock_close:
        async with api as ctx:
            assert ctx is api
            mock_close.assert_not_called()
        mock_close.assert_called_once()


# --- Report methods ---


async def test_async_get_report(async_api):
    """get_report builds correct vars[] args."""
    mock_response = Mock(text="Package,Revenue\nPkg1,100", status_code=200)
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ) as mock_get:
        await async_api.get_report("package_revenue", "2025-01-01", "2025-01-31")
    call_args = mock_get.call_args
    assert "vars[start_date]" in call_args.kwargs["params"]
    assert "vars[end_date]" in call_args.kwargs["params"]


async def test_async_get_report_series(async_api):
    """get_report_series returns flat list with _period keys."""
    csv_text = "Package,Revenue\nPkg1,100"
    mock_response = Mock(text=csv_text, status_code=200)
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        rows = await async_api.get_report_series(
            "package_revenue", "2025-01", "2025-02"
        )
    assert len(rows) == 2
    assert rows[0]["_period"] == "2025-01"
    assert rows[1]["_period"] == "2025-02"


async def test_async_get_report_with_extra_vars(async_api):
    """get_report wraps extra_vars keys in vars[]."""
    mock_response = Mock(text="Package,Revenue\nPkg1,100", status_code=200)
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ) as mock_get:
        await async_api.get_report(
            "pkg_rev", "2025-01-01", "2025-01-31", {"currency": "USD"}
        )
    params = mock_get.call_args.kwargs["params"]
    assert params["vars[currency]"] == "USD"


async def test_async_get_report_series_skips_http_errors(async_api):
    """get_report_series skips months with non-200 status."""
    responses = [
        Mock(text="Package,Revenue\nPkg1,100", status_code=200),
        Mock(text="error", status_code=500),
    ]
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, side_effect=responses
    ):
        rows = await async_api.get_report_series(
            "package_revenue", "2025-01", "2025-02"
        )
    assert len(rows) == 1
    assert rows[0]["_period"] == "2025-01"


async def test_async_get_report_series_skips_non_csv(async_api):
    """get_report_series skips months with non-CSV responses."""
    responses = [
        Mock(text='{"response": "not csv"}', status_code=200),
        Mock(text="Package,Revenue\nPkg1,100", status_code=200),
    ]
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, side_effect=responses
    ):
        rows = await async_api.get_report_series(
            "package_revenue", "2025-01", "2025-02"
        )
    assert len(rows) == 1
    assert rows[0]["_period"] == "2025-02"


# --- get_report_series_concurrent() ---


async def test_async_get_report_series_concurrent(async_api):
    """Concurrent report series returns flat list with _period keys."""
    csv_text = '"Package","Revenue"\n"Hosting","100"\n'
    mock_response = Mock(text=csv_text, status_code=200)
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        rows = await async_api.get_report_series_concurrent(
            "package_revenue", "2025-01", "2025-03"
        )
    assert len(rows) == 3
    periods = [r["_period"] for r in rows]
    assert periods == ["2025-01", "2025-02", "2025-03"]


async def test_async_get_report_series_concurrent_skips_errors(async_api):
    """Concurrent report series skips months with non-200 status."""
    csv_ok = Mock(text='"Package","Revenue"\n"Hosting","100"\n', status_code=200)
    csv_err = Mock(text='{"errors": {"msg": "fail"}}', status_code=500)
    with patch.object(
        async_api.client,
        "get",
        new_callable=AsyncMock,
        side_effect=[csv_ok, csv_err, csv_ok],
    ):
        rows = await async_api.get_report_series_concurrent(
            "package_revenue", "2025-01", "2025-03"
        )
    assert len(rows) == 2
    assert rows[0]["_period"] == "2025-01"
    assert rows[1]["_period"] == "2025-03"


async def test_async_get_report_series_concurrent_with_semaphore(async_api):
    """max_concurrency limits parallel requests via semaphore."""
    csv_text = '"Package","Revenue"\n"Hosting","100"\n'
    mock_response = Mock(text=csv_text, status_code=200)
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        rows = await async_api.get_report_series_concurrent(
            "package_revenue", "2025-01", "2025-06", max_concurrency=2
        )
    assert len(rows) == 6


async def test_async_get_report_series_concurrent_invalid_range(async_api):
    """Invalid range raises ValueError."""
    with pytest.raises(ValueError):
        await async_api.get_report_series_concurrent(
            "package_revenue", "2025-06", "2025-01"
        )


# --- get_all_fast ---


async def test_async_get_all_fast(async_api):
    """get_all_fast fetches pages in parallel after count."""
    count_resp = Mock(text=json.dumps({"response": 50}), status_code=200)
    page1 = [{"id": i} for i in range(1, 26)]
    page2 = [{"id": i} for i in range(26, 51)]
    page1_resp = Mock(text=json.dumps({"response": page1}), status_code=200)
    page2_resp = Mock(text=json.dumps({"response": page2}), status_code=200)

    with patch.object(
        async_api.client,
        "get",
        new_callable=AsyncMock,
        side_effect=[count_resp, page1_resp, page2_resp],
    ):
        result = await async_api.get_all_fast("transactions", "getList", page_size=25)

    assert len(result) == 50
    assert result[0]["id"] == 1
    assert result[-1]["id"] == 50


async def test_async_get_all_fast_fallback_on_zero_count(async_api):
    """get_all_fast falls back to get_all when count is 0."""
    count_resp = Mock(text=json.dumps({"response": 0}), status_code=200)
    page1 = [{"id": 1}, {"id": 2}]
    page1_resp = Mock(text=json.dumps({"response": page1}), status_code=200)
    empty_resp = Mock(text=json.dumps({"response": None}), status_code=200)

    with patch.object(
        async_api.client,
        "get",
        new_callable=AsyncMock,
        side_effect=[count_resp, page1_resp, empty_resp],
    ):
        result = await async_api.get_all_fast("transactions", "getList")

    assert len(result) == 2
    assert result[0]["id"] == 1


async def test_async_get_all_fast_fallback_on_count_error(async_api):
    """get_all_fast falls back to get_all when count returns HTTP error."""
    count_resp = Mock(text='{"errors": {}}', status_code=500)
    page1 = [{"id": 1}]
    page1_resp = Mock(text=json.dumps({"response": page1}), status_code=200)
    empty_resp = Mock(text=json.dumps({"response": None}), status_code=200)

    with patch.object(
        async_api.client,
        "get",
        new_callable=AsyncMock,
        side_effect=[count_resp, page1_resp, empty_resp],
    ):
        result = await async_api.get_all_fast("transactions", "getList")

    assert len(result) == 1
    assert result[0]["id"] == 1


async def test_async_get_all_fast_batch_size(async_api):
    """get_all_fast respects batch_size for parallel fetching."""
    count_resp = Mock(text=json.dumps({"response": 75}), status_code=200)
    pages = []
    for p in range(3):
        items = [{"id": p * 25 + i} for i in range(1, 26)]
        pages.append(Mock(text=json.dumps({"response": items}), status_code=200))

    with patch.object(
        async_api.client,
        "get",
        new_callable=AsyncMock,
        side_effect=[count_resp] + pages,
    ):
        result = await async_api.get_all_fast(
            "transactions", "getList", page_size=25, batch_size=2
        )

    assert len(result) == 75


# --- close() ---


async def test_async_close():
    """close() calls aclose on the httpx client."""
    api = AsyncBlestaRequest("https://example.com/api", "user", "key")
    with patch.object(api.client, "aclose", new_callable=AsyncMock) as mock_close:
        await api.close()
    mock_close.assert_called_once()


# --- count() edge cases ---


async def test_async_count_none_data(async_api):
    """count() returns 0 when response has no 'response' key."""
    mock_response = Mock(text='{"other": "data"}', status_code=200)
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        assert await async_api.count("transactions") == 0


async def test_async_count_non_numeric(async_api):
    """count() returns 0 for non-numeric response data."""
    mock_response = Mock(
        text=json.dumps({"response": {"unexpected": "dict"}}), status_code=200
    )
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        assert await async_api.count("transactions") == 0


# --- retry edge cases ---


@patch("blesta_sdk._async_client.asyncio.sleep", new_callable=AsyncMock)
async def test_async_retry_on_network_error(mock_sleep):
    """Retries on network error, succeeds on second attempt."""
    import httpx

    api = AsyncBlestaRequest("https://example.com/api", "u", "k", max_retries=1)
    mock_response = Mock(text='{"response": []}', status_code=200)
    with patch.object(
        api.client,
        "get",
        new_callable=AsyncMock,
        side_effect=[httpx.ConnectError("refused"), mock_response],
    ):
        response = await api.get("clients", "getList")
    assert response.status_code == 200
    mock_sleep.assert_called_once()


# --- Pagination edge cases ---


async def test_async_iter_all_forwards_args(async_api):
    """iter_all passes args through to get."""
    responses = [
        Mock(text=json.dumps({"response": []}), status_code=200),
    ]
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, side_effect=responses
    ) as mock_get:
        _ = [
            item
            async for item in async_api.iter_all(
                "invoices", "getList", {"status": "active"}
            )
        ]
    mock_get.assert_called_once_with(
        "https://example.com/api/invoices/getList.json",
        params={"status": "active", "page": 1},
    )


async def test_async_iter_all_start_page(async_api):
    """iter_all respects start_page parameter."""
    responses = [
        Mock(text=json.dumps({"response": []}), status_code=200),
    ]
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, side_effect=responses
    ) as mock_get:
        _ = [
            item
            async for item in async_api.iter_all("invoices", "getList", start_page=5)
        ]
    mock_get.assert_called_once_with(
        "https://example.com/api/invoices/getList.json",
        params={"page": 5},
    )


async def test_async_iter_all_stops_on_falsy_data(async_api):
    """iter_all treats falsy data (0, False) as end-of-pages."""
    mock_response = Mock(text=json.dumps({"response": 0}), status_code=200)
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        result = [item async for item in async_api.iter_all("invoices", "getList")]
    assert result == []


# --- extract() edge cases ---


async def test_async_extract_empty_targets(async_api):
    """extract([]) returns empty dict."""
    result = await async_api.extract([])
    assert result == {}


# --- count() edge cases ---


async def test_async_count_custom_method(async_api):
    """count() respects custom method name."""
    mock_response = Mock(text=json.dumps({"response": 5}), status_code=200)
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ) as mock_get:
        result = await async_api.count(
            "clients", "getStatusCount", {"status": "active"}
        )
    mock_get.assert_called_once_with(
        "https://example.com/api/clients/getStatusCount.json",
        params={"status": "active"},
    )
    assert result == 5


async def test_async_count_handles_string_number(async_api):
    """count() converts string '100' to int 100."""
    mock_response = Mock(text=json.dumps({"response": "100"}), status_code=200)
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        assert await async_api.count("transactions") == 100


async def test_async_count_returns_zero_for_zero(async_api):
    """count() returns 0 when API returns 0."""
    mock_response = Mock(text=json.dumps({"response": 0}), status_code=200)
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        assert await async_api.count("transactions") == 0


# --- get_report_series_pages ---


async def test_async_get_report_series_pages(async_api):
    """get_report_series_pages yields (period, response) tuples."""
    csv_text = "Package,Revenue\nPkg1,100"
    responses = [
        Mock(text=csv_text, status_code=200),
        Mock(text=csv_text, status_code=200),
        Mock(text=csv_text, status_code=200),
    ]
    with patch.object(
        async_api.client, "get", new_callable=AsyncMock, side_effect=responses
    ):
        result = [
            (period, resp)
            async for period, resp in async_api.get_report_series_pages(
                "package_revenue", "2025-01", "2025-03"
            )
        ]
    assert len(result) == 3
    assert result[0][0] == "2025-01"
    assert result[1][0] == "2025-02"
    assert result[2][0] == "2025-03"
    assert all(isinstance(r[1], BlestaResponse) for r in result)
