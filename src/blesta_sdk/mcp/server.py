"""MCP server entry point for the Blesta SDK.

Start the server with::

    blesta-mcp

or directly::

    python -m blesta_sdk.mcp.server

The server exposes all Blesta API capabilities as MCP tools, resources,
and prompts.  Credentials are resolved from environment variables
(``BLESTA_API_URL``, ``BLESTA_API_USER``, ``BLESTA_API_KEY``) at call
time.

Requires ``pip install blesta_sdk[mcp]``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_SERVER_NAME = "blesta-sdk"
_SERVER_VERSION = "0.8.0"
_INSTRUCTIONS = """\
You are connected to a Blesta billing platform via the Blesta SDK.

Available capabilities:
- blesta_call: invoke any API method
- blesta_get_all: paginate list endpoints
- blesta_extract: fetch multiple endpoints at once
- blesta_count: fetch record counts
- blesta_get_report / blesta_get_report_series: fetch billing reports
- blesta_list_models / blesta_list_methods / blesta_get_method_spec: schema
- blesta_capabilities_report: full API surface overview

Credentials are configured via environment variables. This SDK is a
transport layer only — it does not provide idempotency for billing writes.
For mutating operations, verify the method spec and confirm the action.
"""


def _build_server() -> object:
    """Build and configure the MCP server instance.

    :return: Configured :class:`mcp.server.fastmcp.FastMCP` instance.
    :raises ImportError: If the ``mcp`` package is not installed.
    """
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
    except ImportError as err:
        raise ImportError(
            "blesta-mcp requires the mcp package. "
            "Install it with: pip install blesta_sdk[mcp]"
        ) from err

    from blesta_sdk.mcp.prompts import register_prompts
    from blesta_sdk.mcp.resources import register_resources
    from blesta_sdk.mcp.tools import register_tools

    mcp_server = FastMCP(
        _SERVER_NAME,
        version=_SERVER_VERSION,
        instructions=_INSTRUCTIONS,
    )

    register_tools(mcp_server)
    register_resources(mcp_server)
    register_prompts(mcp_server)

    return mcp_server


def main() -> None:
    """Entry point for the ``blesta-mcp`` console script.

    Starts the MCP server over stdio transport (the default for local
    AI-agent integrations).
    """
    import sys

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    try:
        mcp_server = _build_server()
    except ImportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    logger.info("Starting %s MCP server v%s", _SERVER_NAME, _SERVER_VERSION)
    mcp_server.run()


if __name__ == "__main__":
    main()
