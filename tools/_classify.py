"""Classify Blesta API methods by HTTP verb and category.

Provides prefix-based inference for ``http_method`` (GET/POST/PUT/DELETE)
and ``category`` (api/internal) used by both schema extractors.

All rules are deterministic and based on method name patterns observed
across Blesta's 63 core models and 8 plugin models.
"""

from __future__ import annotations

INFERENCE_SOURCE = "prefix_rules_v1"

# ---------------------------------------------------------------------------
# Internal method detection
# ---------------------------------------------------------------------------

_INTERNAL_PREFIXES: tuple[str, ...] = (
    "validate",
    "format",
    "build",
)

# Predicate prefixes — short names that need word-boundary matching
# to avoid false positives (e.g., "issue" starts with "is").
_PREDICATE_PREFIXES: tuple[str, ...] = (
    "is",
    "has",
    "can",
)

# Specific method names that are internal utilities despite not matching
# a prefix rule.
_INTERNAL_OVERRIDES: frozenset[str] = frozenset(
    {
        "creditCardType",
        "luhnValid",
        "hashPassword",
        "getDataPresenter",
        "getExchangeRateProcessor",
        "getExchangeRateProcessors",
        "getFieldRules",
        "getHtmlTemplate",
        "getInstance",
        "getMethods",
        "getObservers",
        "getPresenter",
        "getCacheMethods",
    }
)


def classify_category(method_name: str) -> str:
    """Return ``'api'`` or ``'internal'`` for a Blesta model method.

    :param method_name: The method name (e.g. ``"getList"``, ``"validateCreation"``).
    :return: ``"api"`` or ``"internal"``.
    """
    if method_name in _INTERNAL_OVERRIDES:
        return "internal"

    if method_name.startswith(_INTERNAL_PREFIXES):
        return "internal"

    # Predicate prefixes need word-boundary check: "isInstalled" is internal
    # but "import" is not (does not start with "is" + uppercase).
    for prefix in _PREDICATE_PREFIXES:
        if method_name.startswith(prefix) and len(method_name) > len(prefix):
            next_char = method_name[len(prefix)]
            if next_char.isupper() or next_char == "_":
                return "internal"

    return "api"


# ---------------------------------------------------------------------------
# HTTP method inference
# ---------------------------------------------------------------------------

_GET_PREFIXES: tuple[str, ...] = (
    "get",
    "count",
    "search",
    "fetch",
    "query",
    "check",
)

_POST_PREFIXES: tuple[str, ...] = (
    "add",
    "create",
    "generate",
    "make",
    "send",
    "trigger",
    "execute",
    "process",
    "register",
    "login",
    "import",
    "clone",
    "duplicate",
    "log",
    "invite",
)

_PUT_PREFIXES: tuple[str, ...] = (
    "edit",
    "update",
    "set",
    "enable",
    "disable",
    "suspend",
    "unsuspend",
    "apply",
    "assign",
    "move",
    "upgrade",
    "renew",
    "change",
    "merge",
    "save",
    "reset",
    "increment",
    "decrement",
    "grant",
    "order",
)

_DELETE_PREFIXES: tuple[str, ...] = (
    "delete",
    "remove",
    "clear",
    "unset",
    "revoke",
)


def infer_http_method(method_name: str) -> str | None:
    """Infer the HTTP method for a Blesta API method from its name.

    :param method_name: The method name (e.g. ``"getList"``, ``"addAch"``).
    :return: ``"GET"``, ``"POST"``, ``"PUT"``, ``"DELETE"``, or ``None``
        if the method is internal or ambiguous.
    """
    if classify_category(method_name) == "internal":
        return None

    if method_name.startswith(_GET_PREFIXES):
        return "GET"

    if method_name.startswith(_POST_PREFIXES):
        return "POST"

    if method_name.startswith(_PUT_PREFIXES):
        return "PUT"

    if method_name.startswith(_DELETE_PREFIXES):
        return "DELETE"

    # Ambiguous — e.g., "accept", "decline", "auth", "errors"
    return None
