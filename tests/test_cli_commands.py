"""Tests for blesta_sdk.cli command handlers and formatters."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def test_print_json(capsys):
    from blesta_sdk.cli.formatters import print_json

    print_json({"key": "value"})
    out = capsys.readouterr().out
    assert '"key": "value"' in out


def test_print_jsonl(capsys):
    from blesta_sdk.cli.formatters import print_jsonl

    print_jsonl([{"a": 1}, {"b": 2}])
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"a": 1}


def test_print_csv(capsys):
    from blesta_sdk.cli.formatters import print_csv

    rows = [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]
    print_csv(rows)
    out = capsys.readouterr().out
    assert "name,age" in out
    assert "Alice" in out


def test_print_csv_empty(capsys):
    from blesta_sdk.cli.formatters import print_csv

    print_csv([])
    out = capsys.readouterr().out
    assert out == ""


def test_print_error_exits(capsys):
    from blesta_sdk.cli.formatters import print_error

    with pytest.raises(SystemExit) as exc_info:
        print_error("something went wrong")
    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "something went wrong" in out


# ---------------------------------------------------------------------------
# _build_cli_client helper
# ---------------------------------------------------------------------------

_CREDS = {
    "BLESTA_API_URL": "https://example.com/api",
    "BLESTA_API_USER": "user",
    "BLESTA_API_KEY": "key",
}


def test_build_cli_client_returns_blesta_request():
    from blesta_sdk.cli.formatters import _build_cli_client
    from blesta_sdk.core.client import BlestaRequest

    with patch.dict(os.environ, _CREDS):
        client = _build_cli_client()
    assert isinstance(client, BlestaRequest)


def test_build_cli_client_missing_creds(capsys):
    from blesta_sdk.cli.formatters import _build_cli_client

    with (
        patch.dict(os.environ, {}, clear=True),
        pytest.raises(SystemExit),
    ):
        _build_cli_client()
    out = capsys.readouterr().out
    assert "BLESTA_API_URL" in out


def test_build_cli_client_invalid_auth_method(capsys):
    from blesta_sdk.cli.formatters import _build_cli_client

    creds = {**_CREDS, "BLESTA_AUTH_METHOD": "digest"}
    with (
        patch.dict(os.environ, creds),
        pytest.raises(SystemExit),
    ):
        _build_cli_client()
    out = capsys.readouterr().out
    assert "BLESTA_AUTH_METHOD" in out


def test_build_cli_client_allow_http():
    from blesta_sdk.cli.formatters import _build_cli_client
    from blesta_sdk.core.client import BlestaRequest

    creds = {**_CREDS, "BLESTA_ALLOW_HTTP": "true"}
    with patch.dict(os.environ, creds):
        client = _build_cli_client()
    assert isinstance(client, BlestaRequest)


def test_build_cli_client_header_auth():
    from blesta_sdk.cli.formatters import _build_cli_client
    from blesta_sdk.core.client import BlestaRequest

    creds = {**_CREDS, "BLESTA_AUTH_METHOD": "header"}
    with patch.dict(os.environ, creds):
        client = _build_cli_client()
    assert isinstance(client, BlestaRequest)
    assert client.auth_method == "header"


# ---------------------------------------------------------------------------
# blesta call
# ---------------------------------------------------------------------------


def _mock_response(data=None, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.data = data
    resp.errors.return_value = {"error": "bad"} if status_code != 200 else None
    return resp


def test_call_run_get(capsys):
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import call

    mock_resp = _mock_response(data=[{"id": 1}])
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.cli.commands.call._build_cli_client") as MockBuild,
    ):
        MockBuild.return_value.submit.return_value = mock_resp
        args = _build_parser().parse_args(
            [
                "call",
                "clients",
                "getList",
                "--action",
                "GET",
                "--param",
                "status=active",
            ]
        )
        call.run(args)

    out = capsys.readouterr().out
    assert "id" in out


def test_call_run_inferred_method(capsys):
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import call

    mock_resp = _mock_response(data={"id": 5})
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.cli.commands.call._build_cli_client") as MockBuild,
    ):
        MockBuild.return_value.call.return_value = mock_resp
        args = _build_parser().parse_args(["call", "clients", "getList"])
        call.run(args)

    out = capsys.readouterr().out
    assert "id" in out


def test_call_run_missing_creds():
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import call

    with (
        patch.dict(os.environ, {}, clear=True),
        pytest.raises(SystemExit),
    ):
        args = _build_parser().parse_args(["call", "clients", "getList"])
        call.run(args)


def test_call_run_non200(capsys):
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import call

    mock_resp = _mock_response(status_code=403)
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.cli.commands.call._build_cli_client") as MockBuild,
        pytest.raises(SystemExit) as exc_info,
    ):
        MockBuild.return_value.submit.return_value = mock_resp
        args = _build_parser().parse_args(
            ["call", "clients", "getList", "--action", "GET"]
        )
        call.run(args)

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "error" in data


def test_call_run_invalid_param():
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import call

    with (
        patch.dict(os.environ, _CREDS),
        pytest.raises(SystemExit),
    ):
        args = _build_parser().parse_args(
            ["call", "clients", "getList", "--action", "GET", "--param", "noequalssign"]
        )
        call.run(args)


# ---------------------------------------------------------------------------
# blesta extract
# ---------------------------------------------------------------------------


def test_extract_run_json(capsys):
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import extract

    rows = [{"id": 1}, {"id": 2}]
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.cli.commands.extract._build_cli_client") as MockBuild,
    ):
        MockBuild.return_value.get_all.return_value = rows
        args = _build_parser().parse_args(["extract", "clients", "getList"])
        extract.run(args)

    out = capsys.readouterr().out
    data = json.loads(out)
    assert len(data) == 2


def test_extract_run_jsonl(capsys):
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import extract

    rows = [{"id": 1}, {"id": 2}]
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.cli.commands.extract._build_cli_client") as MockBuild,
    ):
        MockBuild.return_value.get_all.return_value = rows
        args = _build_parser().parse_args(
            ["extract", "clients", "getList", "--format", "jsonl"]
        )
        extract.run(args)

    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 2


def test_extract_run_csv(capsys):
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import extract

    rows = [{"name": "Alice"}, {"name": "Bob"}]
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.cli.commands.extract._build_cli_client") as MockBuild,
    ):
        MockBuild.return_value.get_all.return_value = rows
        args = _build_parser().parse_args(
            ["extract", "clients", "getList", "--format", "csv"]
        )
        extract.run(args)

    out = capsys.readouterr().out
    assert "name" in out
    assert "Alice" in out


def test_extract_run_missing_creds():
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import extract

    with (
        patch.dict(os.environ, {}, clear=True),
        pytest.raises(SystemExit),
    ):
        args = _build_parser().parse_args(["extract", "clients", "getList"])
        extract.run(args)


# ---------------------------------------------------------------------------
# blesta report
# ---------------------------------------------------------------------------


def test_report_run_csv_response(capsys):
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import report

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_csv = True
    mock_resp.csv_data = [{"col": "val"}]

    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.cli.commands.report._build_cli_client") as MockBuild,
    ):
        MockBuild.return_value.get_report.return_value = mock_resp
        args = _build_parser().parse_args(
            [
                "report",
                "package_revenue",
                "--start",
                "2025-01-01",
                "--end",
                "2025-01-31",
            ]
        )
        report.run(args)

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data == [{"col": "val"}]


def test_report_run_json_response(capsys):
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import report

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_csv = False
    mock_resp.data = {"total": 42}

    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.cli.commands.report._build_cli_client") as MockBuild,
    ):
        MockBuild.return_value.get_report.return_value = mock_resp
        args = _build_parser().parse_args(
            [
                "report",
                "package_revenue",
                "--start",
                "2025-01-01",
                "--end",
                "2025-01-31",
            ]
        )
        report.run(args)

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data == {"total": 42}


def test_report_run_error_response():
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import report

    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.cli.commands.report._build_cli_client") as MockBuild,
        pytest.raises(SystemExit),
    ):
        MockBuild.return_value.get_report.return_value = mock_resp
        args = _build_parser().parse_args(
            [
                "report",
                "package_revenue",
                "--start",
                "2025-01-01",
                "--end",
                "2025-01-31",
            ]
        )
        report.run(args)


def test_report_run_missing_creds():
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import report

    with (
        patch.dict(os.environ, {}, clear=True),
        pytest.raises(SystemExit),
    ):
        args = _build_parser().parse_args(
            [
                "report",
                "package_revenue",
                "--start",
                "2025-01-01",
                "--end",
                "2025-01-31",
            ]
        )
        report.run(args)


# ---------------------------------------------------------------------------
# blesta discover
# ---------------------------------------------------------------------------


def test_discover_models(capsys):
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import discover

    args = _build_parser().parse_args(["discover", "models"])
    discover.run(args)
    out = capsys.readouterr().out
    models = json.loads(out)
    assert isinstance(models, list)
    assert len(models) > 0


def test_discover_methods(capsys):
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import discover

    args = _build_parser().parse_args(["discover", "methods", "Clients"])
    discover.run(args)
    out = capsys.readouterr().out
    methods = json.loads(out)
    assert isinstance(methods, list)
    assert "getList" in methods


def test_discover_methods_unknown_model():
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import discover

    with pytest.raises(SystemExit):
        args = _build_parser().parse_args(
            ["discover", "methods", "NonExistentModel999"]
        )
        discover.run(args)


def test_discover_spec(capsys):
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import discover

    args = _build_parser().parse_args(["discover", "spec", "Clients", "getList"])
    discover.run(args)
    out = capsys.readouterr().out
    spec = json.loads(out)
    assert spec["model"] == "Clients"
    assert spec["method"] == "getList"


def test_discover_spec_unknown_method():
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import discover

    with pytest.raises(SystemExit):
        args = _build_parser().parse_args(
            ["discover", "spec", "Clients", "nonExistentMethod999"]
        )
        discover.run(args)


# ---------------------------------------------------------------------------
# blesta app legacy mode
# ---------------------------------------------------------------------------


def test_app_main_legacy_mode(capsys):
    """Test main() routes --model/--method to the legacy handler."""
    import sys

    from blesta_sdk.cli.app import main

    mock_resp = _mock_response(data={"id": 1})
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.cli.app._build_cli_client") as MockBuild,
        patch.object(
            sys, "argv", ["blesta", "--model", "clients", "--method", "getList"]
        ),
    ):
        MockBuild.return_value.submit.return_value = mock_resp
        main()

    out = capsys.readouterr().out
    assert "id" in out


def test_app_main_no_args_prints_help(capsys):
    import sys

    from blesta_sdk.cli.app import main

    with (
        patch.object(sys, "argv", ["blesta"]),
        pytest.raises(SystemExit) as exc_info,
    ):
        main()
    assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Additional coverage tests
# ---------------------------------------------------------------------------


def test_app_main_subcommand_dispatch(capsys):
    """Test main() dispatches to subcommand handler via args.func."""
    import sys

    from blesta_sdk.cli.app import main

    with (patch.object(sys, "argv", ["blesta", "discover", "models"]),):
        main()

    out = capsys.readouterr().out
    models = json.loads(out)
    assert isinstance(models, list)


def test_app_legacy_missing_creds():
    import sys

    from blesta_sdk.cli.app import main

    with (
        patch.dict(os.environ, {}, clear=True),
        patch("dotenv.load_dotenv"),
        patch.object(
            sys, "argv", ["blesta", "--model", "clients", "--method", "getList"]
        ),
        pytest.raises(SystemExit),
    ):
        main()


def test_app_legacy_invalid_auth_method():
    import sys

    from blesta_sdk.cli.app import main

    creds = {**_CREDS, "BLESTA_AUTH_METHOD": "oauth"}
    with (
        patch.dict(os.environ, creds),
        patch.object(
            sys, "argv", ["blesta", "--model", "clients", "--method", "getList"]
        ),
        pytest.raises(SystemExit),
    ):
        main()


def test_app_legacy_non200_exits_1(capsys):
    import sys

    from blesta_sdk.cli.app import main

    mock_resp = _mock_response(status_code=404)
    mock_resp.errors.return_value = {"error": "not found"}
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.cli.app._build_cli_client") as MockBuild,
        patch.object(
            sys,
            "argv",
            ["blesta", "--model", "clients", "--method", "getList", "--action", "GET"],
        ),
        pytest.raises(SystemExit) as exc_info,
    ):
        MockBuild.return_value.submit.return_value = mock_resp
        main()
    assert exc_info.value.code == 1


def test_app_legacy_last_request(capsys):
    import sys

    from blesta_sdk.cli.app import main

    mock_resp = _mock_response(data={"id": 1})
    last_req = {"url": "https://example.com/api/clients/getList.json", "args": {}}
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.cli.app._build_cli_client") as MockBuild,
        patch.object(
            sys,
            "argv",
            ["blesta", "--model", "clients", "--method", "getList", "--last-request"],
        ),
    ):
        MockBuild.return_value.submit.return_value = mock_resp
        MockBuild.return_value.get_last_request.return_value = last_req
        main()

    out = capsys.readouterr().out
    assert "Last Request URL" in out


def test_call_run_duplicate_param(capsys):
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import call

    mock_resp = _mock_response(data=[])
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.cli.commands.call._build_cli_client") as MockBuild,
    ):
        MockBuild.return_value.submit.return_value = mock_resp
        args = _build_parser().parse_args(
            [
                "call",
                "clients",
                "getList",
                "--action",
                "GET",
                "--param",
                "status=active",
                "status=inactive",
            ]
        )
        call.run(args)

    out = capsys.readouterr().out
    assert json.loads(out) == []


def test_extract_missing_creds_param():
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import extract

    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.cli.commands.extract._build_cli_client") as MockBuild,
        pytest.raises(SystemExit),
    ):
        MockBuild.return_value.get_all.return_value = []
        args = _build_parser().parse_args(
            ["extract", "clients", "getList", "--param", "badparam"]
        )
        extract.run(args)


def test_extract_run_csv_non_dict(capsys):
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import extract

    rows = [1, 2, 3]
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.cli.commands.extract._build_cli_client") as MockBuild,
    ):
        MockBuild.return_value.get_all.return_value = rows
        args = _build_parser().parse_args(
            ["extract", "clients", "getList", "--format", "csv"]
        )
        extract.run(args)

    out = capsys.readouterr().out
    assert json.loads(out) == [1, 2, 3]


def test_report_run_with_extra_params(capsys):
    from blesta_sdk.cli.app import _build_parser
    from blesta_sdk.cli.commands import report

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_csv = False
    mock_resp.data = {"rows": []}

    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.cli.commands.report._build_cli_client") as MockBuild,
    ):
        MockBuild.return_value.get_report.return_value = mock_resp
        args = _build_parser().parse_args(
            [
                "report",
                "package_revenue",
                "--start",
                "2025-01-01",
                "--end",
                "2025-01-31",
                "--param",
                "currency=USD",
            ]
        )
        report.run(args)

    _, kwargs = MockBuild.return_value.get_report.call_args
    assert kwargs.get("extra_vars") == {"currency": "USD"} or (
        MockBuild.return_value.get_report.call_args[0][-1] == {"currency": "USD"}
    )
