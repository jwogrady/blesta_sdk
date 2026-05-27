"""Tests for BlestaEnvConfig (#14)."""

from __future__ import annotations

import pytest

from blesta_sdk import BlestaEnvConfig, BlestaRequest

# ---------------------------------------------------------------------------
# Environment selection
# ---------------------------------------------------------------------------


def test_dev_env_selected(monkeypatch):
    monkeypatch.setenv("BLESTA_DEV_URL", "https://dev.example.com/api")
    monkeypatch.setenv("BLESTA_DEV_USER", "dev_user")
    monkeypatch.setenv("BLESTA_DEV_KEY", "dev_key")
    cfg = BlestaEnvConfig("dev")
    assert cfg.env == "dev"
    assert cfg.url == "https://dev.example.com/api"
    assert cfg.user == "dev_user"


def test_stage_env_selected(monkeypatch):
    monkeypatch.setenv("BLESTA_STAGE_URL", "https://stage.example.com/api")
    monkeypatch.setenv("BLESTA_STAGE_USER", "stage_user")
    monkeypatch.setenv("BLESTA_STAGE_KEY", "stage_key")
    cfg = BlestaEnvConfig("stage")
    assert cfg.env == "stage"
    assert cfg.url == "https://stage.example.com/api"


def test_live_env_selected(monkeypatch):
    monkeypatch.setenv("BLESTA_LIVE_URL", "https://live.example.com/api")
    monkeypatch.setenv("BLESTA_LIVE_USER", "live_user")
    monkeypatch.setenv("BLESTA_LIVE_KEY", "live_key")
    cfg = BlestaEnvConfig("live")
    assert cfg.env == "live"
    assert cfg.url == "https://live.example.com/api"


# ---------------------------------------------------------------------------
# Invalid env raises
# ---------------------------------------------------------------------------


def test_invalid_env_raises():
    with pytest.raises(ValueError, match="must be one of"):
        BlestaEnvConfig("prod")


def test_empty_env_raises():
    with pytest.raises(ValueError, match="must be one of"):
        BlestaEnvConfig("")


# ---------------------------------------------------------------------------
# Missing credentials raise with variable names in message
# ---------------------------------------------------------------------------


def test_missing_url_raises(monkeypatch):
    monkeypatch.delenv("BLESTA_DEV_URL", raising=False)
    monkeypatch.setenv("BLESTA_DEV_USER", "u")
    monkeypatch.setenv("BLESTA_DEV_KEY", "k")
    with pytest.raises(ValueError, match="BLESTA_DEV_URL"):
        BlestaEnvConfig("dev")


def test_missing_user_raises(monkeypatch):
    monkeypatch.setenv("BLESTA_DEV_URL", "https://dev.example.com/api")
    monkeypatch.delenv("BLESTA_DEV_USER", raising=False)
    monkeypatch.setenv("BLESTA_DEV_KEY", "k")
    with pytest.raises(ValueError, match="BLESTA_DEV_USER"):
        BlestaEnvConfig("dev")


def test_missing_key_raises(monkeypatch):
    monkeypatch.setenv("BLESTA_DEV_URL", "https://dev.example.com/api")
    monkeypatch.setenv("BLESTA_DEV_USER", "u")
    monkeypatch.delenv("BLESTA_DEV_KEY", raising=False)
    with pytest.raises(ValueError, match="BLESTA_DEV_KEY"):
        BlestaEnvConfig("dev")


def test_all_missing_raises_all_var_names(monkeypatch):
    for var in ("BLESTA_STAGE_URL", "BLESTA_STAGE_USER", "BLESTA_STAGE_KEY"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(ValueError, match="BLESTA_STAGE_URL") as exc_info:
        BlestaEnvConfig("stage")
    msg = str(exc_info.value)
    assert "BLESTA_STAGE_USER" in msg
    assert "BLESTA_STAGE_KEY" in msg


# ---------------------------------------------------------------------------
# No fallback between environments
# ---------------------------------------------------------------------------


def test_stage_does_not_fall_back_to_live(monkeypatch):
    """Stage credentials must not bleed into a live config request."""
    for var in ("BLESTA_LIVE_URL", "BLESTA_LIVE_USER", "BLESTA_LIVE_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("BLESTA_STAGE_URL", "https://stage.example.com/api")
    monkeypatch.setenv("BLESTA_STAGE_USER", "su")
    monkeypatch.setenv("BLESTA_STAGE_KEY", "sk")
    with pytest.raises(ValueError, match="BLESTA_LIVE"):
        BlestaEnvConfig("live")


def test_live_does_not_fall_back_to_dev(monkeypatch):
    for var in ("BLESTA_DEV_URL", "BLESTA_DEV_USER", "BLESTA_DEV_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("BLESTA_LIVE_URL", "https://live.example.com/api")
    monkeypatch.setenv("BLESTA_LIVE_USER", "lu")
    monkeypatch.setenv("BLESTA_LIVE_KEY", "lk")
    with pytest.raises(ValueError, match="BLESTA_DEV"):
        BlestaEnvConfig("dev")


def test_dev_does_not_fall_back_to_stage(monkeypatch):
    for var in ("BLESTA_STAGE_URL", "BLESTA_STAGE_USER", "BLESTA_STAGE_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("BLESTA_DEV_URL", "https://dev.example.com/api")
    monkeypatch.setenv("BLESTA_DEV_USER", "du")
    monkeypatch.setenv("BLESTA_DEV_KEY", "dk")
    with pytest.raises(ValueError, match="BLESTA_STAGE"):
        BlestaEnvConfig("stage")


# ---------------------------------------------------------------------------
# Credential resolution: env vars vs explicit kwargs
# ---------------------------------------------------------------------------


def test_credentials_resolved_from_env_vars(monkeypatch):
    monkeypatch.setenv("BLESTA_LIVE_URL", "https://live.example.com/api")
    monkeypatch.setenv("BLESTA_LIVE_USER", "live_u")
    monkeypatch.setenv("BLESTA_LIVE_KEY", "live_k")
    cfg = BlestaEnvConfig("live")
    assert cfg.url == "https://live.example.com/api"
    assert cfg.user == "live_u"


def test_explicit_kwargs_override_env_vars(monkeypatch):
    monkeypatch.setenv("BLESTA_DEV_URL", "https://env.example.com/api")
    monkeypatch.setenv("BLESTA_DEV_USER", "env_user")
    monkeypatch.setenv("BLESTA_DEV_KEY", "env_key")
    cfg = BlestaEnvConfig(
        "dev",
        url="https://override.example.com/api",
        user="explicit_user",
        key="explicit_key",
    )
    assert cfg.url == "https://override.example.com/api"
    assert cfg.user == "explicit_user"


# ---------------------------------------------------------------------------
# client() construction
# ---------------------------------------------------------------------------


def test_client_returns_blesta_request(monkeypatch):
    monkeypatch.setenv("BLESTA_DEV_URL", "https://dev.example.com/api")
    monkeypatch.setenv("BLESTA_DEV_USER", "u")
    monkeypatch.setenv("BLESTA_DEV_KEY", "k")
    cfg = BlestaEnvConfig("dev")
    client = cfg.client()
    assert isinstance(client, BlestaRequest)


def test_client_kwargs_forwarded(monkeypatch):
    monkeypatch.setenv("BLESTA_DEV_URL", "https://dev.example.com/api")
    monkeypatch.setenv("BLESTA_DEV_USER", "u")
    monkeypatch.setenv("BLESTA_DEV_KEY", "k")
    cfg = BlestaEnvConfig("dev")
    client = cfg.client(retry_mutations=True)
    assert client.retry_mutations is True


# ---------------------------------------------------------------------------
# repr
# ---------------------------------------------------------------------------


def test_repr_shows_env_and_url(monkeypatch):
    monkeypatch.setenv("BLESTA_STAGE_URL", "https://stage.example.com/api")
    monkeypatch.setenv("BLESTA_STAGE_USER", "su")
    monkeypatch.setenv("BLESTA_STAGE_KEY", "sk")
    cfg = BlestaEnvConfig("stage")
    r = repr(cfg)
    assert "stage" in r
    assert "https://stage.example.com/api" in r


# ---------------------------------------------------------------------------
# auth_method resolution
# ---------------------------------------------------------------------------


def test_auth_method_defaults_to_basic(monkeypatch):
    monkeypatch.setenv("BLESTA_DEV_URL", "https://dev.example.com/api")
    monkeypatch.setenv("BLESTA_DEV_USER", "u")
    monkeypatch.setenv("BLESTA_DEV_KEY", "k")
    monkeypatch.delenv("BLESTA_DEV_AUTH_METHOD", raising=False)
    cfg = BlestaEnvConfig("dev")
    assert cfg.auth_method == "basic"


def test_auth_method_kwarg_header(monkeypatch):
    monkeypatch.setenv("BLESTA_DEV_URL", "https://dev.example.com/api")
    monkeypatch.setenv("BLESTA_DEV_USER", "u")
    monkeypatch.setenv("BLESTA_DEV_KEY", "k")
    cfg = BlestaEnvConfig("dev", auth_method="header")
    assert cfg.auth_method == "header"


def test_auth_method_from_env_var(monkeypatch):
    monkeypatch.setenv("BLESTA_DEV_URL", "https://dev.example.com/api")
    monkeypatch.setenv("BLESTA_DEV_USER", "u")
    monkeypatch.setenv("BLESTA_DEV_KEY", "k")
    monkeypatch.setenv("BLESTA_DEV_AUTH_METHOD", "header")
    cfg = BlestaEnvConfig("dev")
    assert cfg.auth_method == "header"


def test_auth_method_kwarg_overrides_env_var(monkeypatch):
    monkeypatch.setenv("BLESTA_DEV_URL", "https://dev.example.com/api")
    monkeypatch.setenv("BLESTA_DEV_USER", "u")
    monkeypatch.setenv("BLESTA_DEV_KEY", "k")
    monkeypatch.setenv("BLESTA_DEV_AUTH_METHOD", "header")
    cfg = BlestaEnvConfig("dev", auth_method="basic")
    assert cfg.auth_method == "basic"


def test_invalid_auth_method_raises(monkeypatch):
    monkeypatch.setenv("BLESTA_DEV_URL", "https://dev.example.com/api")
    monkeypatch.setenv("BLESTA_DEV_USER", "u")
    monkeypatch.setenv("BLESTA_DEV_KEY", "k")
    with pytest.raises(ValueError, match="auth_method must be one of"):
        BlestaEnvConfig("dev", auth_method="digest")  # type: ignore[arg-type]


def test_invalid_auth_method_from_env_var_raises(monkeypatch):
    monkeypatch.setenv("BLESTA_DEV_URL", "https://dev.example.com/api")
    monkeypatch.setenv("BLESTA_DEV_USER", "u")
    monkeypatch.setenv("BLESTA_DEV_KEY", "k")
    monkeypatch.setenv("BLESTA_DEV_AUTH_METHOD", "token")
    with pytest.raises(ValueError, match="auth_method must be one of"):
        BlestaEnvConfig("dev")


def test_client_passes_auth_method_to_request(monkeypatch):
    monkeypatch.setenv("BLESTA_DEV_URL", "https://dev.example.com/api")
    monkeypatch.setenv("BLESTA_DEV_USER", "u")
    monkeypatch.setenv("BLESTA_DEV_KEY", "k")
    cfg = BlestaEnvConfig("dev", auth_method="header")
    client = cfg.client()
    assert client.auth_method == "header"


def test_client_auth_method_kwarg_overrides_config(monkeypatch):
    monkeypatch.setenv("BLESTA_DEV_URL", "https://dev.example.com/api")
    monkeypatch.setenv("BLESTA_DEV_USER", "u")
    monkeypatch.setenv("BLESTA_DEV_KEY", "k")
    cfg = BlestaEnvConfig("dev", auth_method="header")
    client = cfg.client(auth_method="basic")
    assert client.auth_method == "basic"
