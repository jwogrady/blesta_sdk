"""PHP CLI client for the Blesta API, run locally or over SSH.

This module is not part of the public API. Import
:class:`~blesta_sdk.BlestaCLIRequest` from ``blesta_sdk`` directly.

Blesta answers API requests from the command line as well as over HTTP::

    php index.php api/users/get.json -u USER -k KEY -m GET -p "user_id=1"

The CLI prints the same JSON body the HTTP API returns, but no status code.
:class:`BlestaCLIRequest` runs that command and works out the status from
the body's ``message``, so callers get the same
:class:`~blesta_sdk.BlestaResponse` as from :class:`~blesta_sdk.BlestaRequest`.
"""

from __future__ import annotations

import json
import logging
import shlex
import subprocess
from collections.abc import Mapping, Sequence
from typing import Any, Literal
from urllib.parse import urlencode

from blesta_sdk.core.client import DEFAULT_TIMEOUT, BlestaRequest
from blesta_sdk.core.response import BlestaResponse

logger = logging.getLogger(__name__)

_ACTIONS = frozenset({"GET", "POST", "PUT", "DELETE"})

# The ``message`` Blesta's API controller sends with each non-200 response
# (``app/controllers/api.php``), and the status code it would send over HTTP.
_MESSAGE_STATUS = {
    "The request cannot be fulfilled due to bad syntax.": 400,
    "The authorization details given appear to be invalid.": 401,
    "The requested resource is not accessible.": 403,
    "The requested resource does not exist.": 404,
    "The format requested is not supported by the server.": 415,
    "An unexpected error occurred.": 500,
    "An unexpected error occured.": 500,
    "The requested resource is currently unavailable due to maintenance.": 503,
}

# ssh exits 255 when it cannot connect or authenticate.
_SSH_FAILED = 255


def encode_params(args: Mapping[str, Any]) -> str:
    """Encode parameters the way PHP's ``http_build_query`` does.

    Blesta reads ``-p`` with ``parse_str``, so nested mappings and lists
    become ``vars[name]=...`` and ``tags[0]=...``, booleans become ``1``
    and ``0``, and ``None`` values are left out.

    :param args: Request parameters.
    :return: The URL-encoded query string.
    """
    pairs: list[tuple[str, str]] = []

    def add(key: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, Mapping):
            for k, v in value.items():
                add(f"{key}[{k}]", v)
        elif isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                add(f"{key}[{i}]", v)
        elif isinstance(value, bool):
            pairs.append((key, "1" if value else "0"))
        else:
            pairs.append((key, str(value)))

    for key, value in args.items():
        add(str(key), value)
    return urlencode(pairs)


def _parse_body(stdout: str) -> tuple[str, dict[str, Any]] | None:
    """Find Blesta's JSON body in the CLI output.

    PHP may print notices or warnings ahead of it, so when the whole output
    is not JSON, the last non-empty line is tried.
    """
    text = stdout.strip()
    lines = text.splitlines()
    for candidate in (text, lines[-1].strip() if lines else ""):
        try:
            body = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(body, dict):
            return candidate, body
    return None


class BlestaCLIRequest(BlestaRequest):
    """Blesta API client that runs Blesta's PHP CLI, locally or over SSH.

    Use it where the HTTP API is unreachable or unwanted: on the Blesta
    server itself, or from a machine that can SSH to it. It has the same
    methods as :class:`~blesta_sdk.BlestaRequest` (``get``, ``post``,
    ``call``, ``get_all``, reports, ...) and returns the same
    :class:`~blesta_sdk.BlestaResponse`.

    Locally::

        api = BlestaCLIRequest("/var/www/blesta/index.php", user, key)

    Over SSH (the remote command is sent on stdin, so the key stays off
    the local command line)::

        api = BlestaCLIRequest(
            "/var/www/blesta/index.php", user, key,
            ssh="deploy@billing.example.com", ssh_options=["-p", "2222"],
        )

    Blesta reads the API key only from its command line, so while a
    request runs, the key is visible to other users of the machine that
    runs ``php`` (in ``ps``, for example).

    Status codes are inferred from the body's ``message``, since the CLI
    prints none. A run that cannot start, times out, or whose SSH
    connection fails gives ``status_code=0``; a Blesta crash or output
    that is not JSON gives ``500``. There are no retries.

    :param index_path: Path to Blesta's ``index.php`` on the machine that
        runs ``php``.
    :param user: API username.
    :param key: API key.
    :param php: The PHP executable. Defaults to ``"php"``.
    :param ssh: SSH destination (``user@host`` or a ``~/.ssh/config``
        alias). ``None`` runs ``php`` locally.
    :param ssh_options: Extra ``ssh`` arguments, such as
        ``["-p", "2222", "-i", "~/.ssh/blesta"]``. ``-o BatchMode=yes``
        is always passed so ssh never stops to ask for a password.
    :param ssh_command: The ssh executable. Defaults to ``"ssh"``.
    :param timeout: Seconds to wait for each request.
    :param raise_on_error: When ``True``, :meth:`submit` raises a
        :class:`~blesta_sdk.BlestaError` subclass on non-success responses.
    :param discovery: Optional :class:`~blesta_sdk.BlestaDiscovery` instance.
    """

    def __init__(
        self,
        index_path: str,
        user: str,
        key: str,
        *,
        php: str = "php",
        ssh: str | None = None,
        ssh_options: Sequence[str] = (),
        ssh_command: str = "ssh",
        timeout: int | float = DEFAULT_TIMEOUT,
        raise_on_error: bool = False,
        discovery: Any = None,
    ):
        # The HTTP session BlestaRequest.__init__ builds is not needed.
        self.index_path = index_path
        self.user = user
        self.key = key
        self.php = php
        self.ssh = ssh
        self.ssh_options = list(ssh_options)
        self.ssh_command = ssh_command
        self.timeout = timeout
        self.raise_on_error = raise_on_error
        self.max_retries = 0
        self.retry_mutations = False
        self._discovery = discovery
        self._last_request: dict[str, Any] | None = None

    def __enter__(self) -> BlestaCLIRequest:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"BlestaCLIRequest(index_path={self.index_path!r}, "
            f"user={self.user!r}, ssh={self.ssh!r})"
        )

    def close(self) -> None:
        """Nothing to close; each request is its own process."""

    def submit(
        self,
        model: str,
        method: str,
        args: dict[str, Any] | None = None,
        action: Literal["GET", "POST", "PUT", "DELETE"] = "POST",
    ) -> BlestaResponse:
        """Run one API request through Blesta's PHP CLI.

        :param model: API model (e.g., ``"clients"``), or ``"plugin.model"``.
        :param method: API method (e.g., ``"getList"``).
        :param args: Request parameters, sent with ``-p``.
        :param action: ``"GET"``, ``"POST"``, ``"PUT"``, or ``"DELETE"``.
        :return: Parsed API response.
        :raises ValueError: If *action* is not one of those methods.
        """
        if action not in _ACTIONS:
            raise ValueError("Invalid HTTP action specified.")
        if args is None:
            args = {}
        self._validate_segment(model, "model")
        self._validate_segment(method, "method")
        uri = f"api/{model}/{method}.json"
        self._last_request = {"url": uri, "args": args.copy()}

        command = [self.php, self.index_path, uri]
        command += ["-u", self.user, "-k", self.key, "-m", action]
        params = encode_params(args)
        if params:
            command += ["-p", params]

        response = self._run(command)
        if self.raise_on_error:
            response.raise_for_status()
        return response

    def _run(self, command: list[str]) -> BlestaResponse:
        if self.ssh is None:
            argv = command
            program = self.php
            run_input: dict[str, Any] = {"stdin": subprocess.DEVNULL}
        else:
            argv = [self.ssh_command, "-o", "BatchMode=yes", *self.ssh_options]
            argv += ["--", self.ssh, "sh", "-s"]
            program = self.ssh_command
            run_input = {"input": shlex.join(command) + "\n"}

        try:
            done = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                **run_input,
            )
        except subprocess.TimeoutExpired:
            # The exception's own message would repeat the command, key and all.
            message = f"{program} timed out after {self.timeout} seconds"
            logger.error("Request failed: %s", message)
            return BlestaResponse(message, 0)
        except OSError as e:
            logger.error("Request failed: %s", e)
            return BlestaResponse(str(e), 0)

        parsed = _parse_body(done.stdout)
        if parsed is not None:
            raw, body = parsed
            message = body.get("message")
            status = 200 if message is None else _MESSAGE_STATUS.get(message, 500)
            return BlestaResponse(raw, status)

        detail = (done.stderr or done.stdout).strip()
        if self.ssh is not None and done.returncode == _SSH_FAILED:
            logger.error("SSH to %s failed: %s", self.ssh, detail)
            return BlestaResponse(detail or "ssh failed", 0)
        logger.error("Blesta CLI exited %d: %s", done.returncode, detail)
        return BlestaResponse(detail, 500)
