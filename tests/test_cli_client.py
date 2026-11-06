"""Tests for BlestaCLIRequest, the PHP CLI transport (locally or over SSH).

A fake ``php`` (a Python script) stands in for Blesta's ``index.php`` and
a fake ``ssh`` runs the remote command with a local ``sh``, so these tests
exercise the real subprocess calls and the shell quoting.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from blesta_sdk import BlestaAuthError, BlestaCLIRequest, BlestaConnectionError
from blesta_sdk.core.cli_client import encode_params

FAKE_PHP = """\
import json, os, sys, time
from urllib.parse import parse_qs

argv = sys.argv[1:]
with open(os.environ["FAKE_PHP_LOG"], "a") as log:
    log.write(json.dumps(argv) + "\\n")
index, uri, rest = argv[0], argv[1], argv[2:]
opts = dict(zip(rest[0::2], rest[1::2]))
mode = os.environ.get("FAKE_PHP_MODE", "echo")


def out(body):
    print(json.dumps(body))
    sys.exit(0)


if opts.get("-k") != "s3cret key":
    out({"message": "The authorization details given appear to be invalid.",
         "response": None})
if mode == "pages":
    page = int(parse_qs(opts.get("-p", ""))["page"][0])
    out({"response": [{"id": page * 10 + i} for i in range(2)] if page <= 2 else []})
if mode == "notice":
    print("PHP Notice:  Undefined index: x in /blesta/app/x.php on line 3")
    out({"response": "ok"})
if mode == "invalid":
    out({"message": "The request cannot be fulfilled due to bad syntax.",
         "errors": {"email": {"format": "Invalid email."}}, "response": None})
if mode == "unknown-message":
    out({"message": "Something new.", "response": None})
if mode == "crash":
    sys.stderr.write("PDOException: SQLSTATE[HY000] [2002] Connection refused\\n")
    sys.exit(1)
if mode == "garbage":
    print("<html>not json</html>")
    sys.exit(0)
if mode == "sleep":
    time.sleep(5)
out({"response": {"index": index, "uri": uri, "user": opts.get("-u"),
                  "method": opts.get("-m"), "params": opts.get("-p")}})
"""

# Skips ssh options and the destination, records its own argv, then runs
# the remote command it is given on stdin, as `ssh host sh -s` would.
FAKE_SSH = """\
#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_SSH_LOG"
if [ "${FAKE_SSH_MODE:-}" = down ]; then
  echo "ssh: connect to host billing port 22: Connection refused" >&2
  exit 255
fi
while [ "$1" != "--" ]; do shift; done
shift 2
exec "$@"
"""


@pytest.fixture
def fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    php = tmp_path / "php"
    php.write_text(f"#!{sys.executable}\n{FAKE_PHP}")
    ssh = tmp_path / "ssh"
    ssh.write_text(FAKE_SSH)
    for exe in (php, ssh):
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("FAKE_PHP_LOG", str(tmp_path / "php.log"))
    monkeypatch.setenv("FAKE_SSH_LOG", str(tmp_path / "ssh.log"))
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    return tmp_path


def php_calls(tmp_path: Path) -> list[list[str]]:
    lines = (tmp_path / "php.log").read_text().splitlines()
    return [json.loads(line) for line in lines]


def local(**kwargs) -> BlestaCLIRequest:
    return BlestaCLIRequest("/var/www/blesta/index.php", "api", "s3cret key", **kwargs)


# -- encode_params ---------------------------------------------------------


def test_encode_params_matches_php_http_build_query():
    encoded = encode_params(
        {
            "vars": {"first_name": "Jo Ann", "tags": ["a", "b&c"]},
            "send": True,
            "draft": False,
            "skip": None,
            "page": 2,
        }
    )
    assert encoded == (
        "vars%5Bfirst_name%5D=Jo+Ann&vars%5Btags%5D%5B0%5D=a"
        "&vars%5Btags%5D%5B1%5D=b%26c&send=1&draft=0&page=2"
    )


def test_encode_params_of_nothing_is_empty():
    assert encode_params({}) == ""


# -- local php -------------------------------------------------------------


def test_get_runs_index_php_with_the_api_uri(fake: Path):
    response = local().get("clients", "getList", {"status": "active"})

    assert response.status_code == 200
    assert response.data == {
        "index": "/var/www/blesta/index.php",
        "uri": "api/clients/getList.json",
        "user": "api",
        "method": "GET",
        "params": "status=active",
    }


def test_post_sends_its_method_and_params(fake: Path):
    response = local().post("plugin.model", "add", {"vars": {"a": 1}})

    assert response.data["uri"] == "api/plugin.model/add.json"
    assert response.data["method"] == "POST"
    assert response.data["params"] == "vars%5Ba%5D=1"


def test_put_and_delete_send_their_methods(fake: Path):
    api = local()

    assert api.put("clients", "edit", {"id": 1}).data["method"] == "PUT"
    assert api.delete("clients", "delete", {"id": 1}).data["method"] == "DELETE"


def test_no_args_sends_no_params_flag(fake: Path):
    local().get("companies", "getAll")

    assert "-p" not in php_calls(fake)[0]


def test_php_executable_is_configurable(fake: Path):
    api = BlestaCLIRequest(
        "/srv/blesta/index.php", "api", "s3cret key", php=str(fake / "php")
    )

    assert api.get("companies", "getAll").data["index"] == "/srv/blesta/index.php"


def test_rejected_key_maps_to_401(fake: Path):
    api = BlestaCLIRequest("/var/www/blesta/index.php", "api", "wrong")

    response = api.get("companies", "getAll")

    assert response.status_code == 401
    with pytest.raises(BlestaAuthError):
        response.raise_for_status()


def test_raise_on_error_raises(fake: Path):
    api = BlestaCLIRequest(
        "/var/www/blesta/index.php", "api", "wrong", raise_on_error=True
    )

    with pytest.raises(BlestaAuthError):
        api.get("companies", "getAll")


def test_validation_errors_map_to_400(fake: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FAKE_PHP_MODE", "invalid")

    response = local().post("clients", "create", {"vars": {"email": "x"}})

    assert response.status_code == 400
    assert response.errors() == {"email": {"format": "Invalid email."}}


def test_unknown_message_maps_to_500(fake: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FAKE_PHP_MODE", "unknown-message")

    assert local().get("clients", "getList").status_code == 500


def test_php_notices_before_the_json_are_skipped(
    fake: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("FAKE_PHP_MODE", "notice")

    response = local().get("clients", "getList")

    assert response.status_code == 200
    assert response.data == "ok"
    assert response.raw == '{"response": "ok"}'


def test_a_blesta_crash_is_a_500_with_stderr(
    fake: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("FAKE_PHP_MODE", "crash")

    response = local().get("clients", "getList")

    assert response.status_code == 500
    assert "Connection refused" in response.raw


def test_output_that_is_not_json_is_a_500(fake: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FAKE_PHP_MODE", "garbage")

    response = local().get("clients", "getList")

    assert response.status_code == 500
    assert response.raw == "<html>not json</html>"


def test_missing_php_is_a_connection_error(fake: Path):
    api = local(php=str(fake / "no-such-php"))

    response = api.get("clients", "getList")

    assert response.status_code == 0
    assert "no-such-php" in response.raw
    with pytest.raises(BlestaConnectionError):
        response.raise_for_status()


def test_timeout_is_a_connection_error(fake: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FAKE_PHP_MODE", "sleep")

    response = local(timeout=0.5).get("clients", "getList")

    assert response.status_code == 0
    assert "timed out" in response.raw


def test_get_all_paginates_through_the_cli(fake: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FAKE_PHP_MODE", "pages")

    rows = local().get_all("clients", "getList")

    assert rows == [{"id": 10}, {"id": 11}, {"id": 20}, {"id": 21}]


def test_bad_segments_are_rejected_before_running_php(fake: Path):
    with pytest.raises(ValueError):
        local().get("../clients", "getList")
    assert not (fake / "php.log").exists()


def test_last_request_names_the_uri_and_redacts(fake: Path):
    api = local()
    api.post("clients", "create", {"vars": {"password": "hunter2"}})

    last = api.get_last_request()

    assert last == {
        "url": "api/clients/create.json",
        "args": {"vars": {"password": "***"}},
    }


def test_repr_hides_the_key():
    api = local(ssh="deploy@billing")

    assert "s3cret" not in repr(api)
    assert repr(api) == (
        "BlestaCLIRequest(index_path='/var/www/blesta/index.php', "
        "user='api', ssh='deploy@billing')"
    )


def test_context_manager_and_close():
    with local() as api:
        api.close()


def test_invalid_action_is_rejected(fake: Path):
    with pytest.raises(ValueError):
        local().submit("clients", "getList", {}, "PATCH")  # type: ignore[arg-type]


# -- over ssh --------------------------------------------------------------


def test_ssh_runs_php_on_the_remote_host(fake: Path):
    api = local(ssh="deploy@billing", ssh_options=["-p", "2222"])

    response = api.post("clients", "create", {"vars": {"name": "O'Grady & Co"}})

    assert response.status_code == 200
    assert response.data["uri"] == "api/clients/create.json"
    assert response.data["params"] == "vars%5Bname%5D=O%27Grady+%26+Co"
    assert php_calls(fake)[0][2:6] == ["-u", "api", "-k", "s3cret key"]


def test_ssh_keeps_the_key_off_its_own_command_line(fake: Path):
    local(ssh="deploy@billing", ssh_options=["-p", "2222"]).get("companies", "getAll")

    ssh_argv = (fake / "ssh.log").read_text()
    assert "s3cret" not in ssh_argv
    assert ssh_argv.split() == [
        "-o",
        "BatchMode=yes",
        "-p",
        "2222",
        "--",
        "deploy@billing",
        "sh",
        "-s",
    ]


def test_ssh_that_cannot_connect_is_a_connection_error(
    fake: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("FAKE_SSH_MODE", "down")

    response = local(ssh="deploy@billing").get("companies", "getAll")

    assert response.status_code == 0
    assert "Connection refused" in response.raw


def test_ssh_executable_is_configurable(fake: Path):
    api = local(ssh="billing", ssh_command=str(fake / "ssh"))

    assert api.get("companies", "getAll").status_code == 200


def test_subprocess_gets_no_shell():
    """Local runs pass an argv list, never a shell string."""
    with patch("blesta_sdk.core.cli_client.subprocess.run") as run:
        run.return_value = subprocess.CompletedProcess([], 0, '{"response": 1}', "")
        local().get("clients", "get", {"id": "1; rm -rf /"})

    argv = run.call_args.args[0]
    assert isinstance(argv, list)
    assert run.call_args.kwargs.get("shell", False) is False
    assert argv[-1] == "id=1%3B+rm+-rf+%2F"
