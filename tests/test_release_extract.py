"""Tests for extracting schemas from a local Blesta release.

Covers the release resolver (directory / zip / URL), version detection, and
the ``--source`` builders in both extractors, using a tiny fake release tree.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from tools._release import (
    find_blesta_root,
    read_php_class,
    read_plugin_version,
    read_release_version,
    resolve_release,
)
from tools.extract_plugin_schema import (
    build_plugin_schema_from_release,
    parse_php_file,
)
from tools.extract_schema import build_schema_from_release

CLIENTS_PHP = """\
<?php
namespace Blesta\\App\\Models;

class Clients extends AppModel
{
    /**
     * Fetches a client
     *
     * @param int $client_id The client ID
     * @return mixed The client
     */
    public function get($client_id)
    {
    }

    /**
     * Fetches a list of clients
     *
     * @param int $page The page
     * @return array Clients
     */
    public function getList($page = 1)
    {
    }

    /**
     * Counts clients
     *
     * @return int The count
     */
    public function getListCount()
    {
    }
}
"""

LICENSE_MANAGER_PHP = """\
<?php
final class LicenseManager
{
    /**
     * Validates a license
     *
     * @return bool
     */
    public function validate()
    {
    }
}
"""

ENCODED_PHP = "<?php //0046b\nencoded-bytes-here\n"

TICKETS_PHP = """\
<?php
class SupportManagerTickets extends SupportManagerModel
{
    /**
     * Fetches a ticket
     *
     * @param int $ticket_id The ticket ID
     * @return mixed The ticket
     */
    public function get($ticket_id)
    {
    }
}
"""

TLDS_PHP = TICKETS_PHP.replace("SupportManagerTickets", "DomainsTlds")


def _make_release(base: Path) -> Path:
    """Build a minimal release tree under ``base/blesta`` and return ``base``."""
    root = base / "blesta"
    models = root / "app" / "models"
    models.mkdir(parents=True)
    (models / "clients.php").write_text(CLIENTS_PHP)
    (models / "license_manager.php").write_text(LICENSE_MANAGER_PHP)
    (models / "license.php").write_text(ENCODED_PHP)
    (root / "manifest.json").write_text(json.dumps({"version": "6.0.4"}))

    sm = root / "plugins" / "support_manager"
    (sm / "models").mkdir(parents=True)
    (sm / "models" / "support_manager_tickets.php").write_text(TICKETS_PHP)
    (sm / "config.json").write_text(json.dumps({"version": "3.3.11"}))

    domains = root / "plugins" / "domains"
    (domains / "models").mkdir(parents=True)
    (domains / "models" / "domains_tlds.php").write_text(TLDS_PHP)
    (domains / "config.json").write_text(json.dumps({"version": "2.0.7"}))

    # A plugin without models is ignored.
    (root / "plugins" / "shared_login").mkdir()
    return base


@pytest.fixture
def release(tmp_path):
    return _make_release(tmp_path / "release")


# ---------------------------------------------------------------------------
# Release resolution
# ---------------------------------------------------------------------------


class TestResolveRelease:
    def test_directory_with_nested_root(self, release):
        assert resolve_release(str(release)) == release / "blesta"

    def test_root_directory_itself(self, release):
        assert find_blesta_root(release / "blesta") == release / "blesta"

    def test_zip(self, release, tmp_path):
        zip_path = tmp_path / "blesta-6.0.4.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for f in release.rglob("*"):
                zf.write(f, f.relative_to(release))
        root = resolve_release(str(zip_path))
        assert (root / "app" / "models" / "clients.php").is_file()
        assert read_release_version(root) == "6.0.4"

    def test_zip_rejects_path_traversal(self, tmp_path):
        zip_path = tmp_path / "evil.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../escape.txt", "x")
        with pytest.raises(ValueError, match="Unsafe path"):
            resolve_release(str(zip_path))

    def test_url_uses_fetch_bytes(self, release, tmp_path):
        zip_path = tmp_path / "r.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for f in release.rglob("*"):
                zf.write(f, f.relative_to(release))
        fetched = []

        def fetch_bytes(url):
            fetched.append(url)
            return zip_path.read_bytes()

        root = resolve_release("https://example.com/blesta.zip", fetch_bytes)
        assert fetched == ["https://example.com/blesta.zip"]
        assert (root / "app" / "models").is_dir()

    def test_url_requires_fetch_bytes(self):
        with pytest.raises(ValueError):
            resolve_release("https://example.com/blesta.zip")

    def test_missing_root(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            resolve_release(str(tmp_path))


class TestReadVersions:
    def test_release_version(self, release):
        assert read_release_version(release / "blesta") == "6.0.4"

    def test_release_version_missing_manifest(self, tmp_path):
        assert read_release_version(tmp_path) is None

    def test_release_version_non_string(self, tmp_path):
        (tmp_path / "manifest.json").write_text(json.dumps({"version": 6}))
        assert read_release_version(tmp_path) is None

    def test_plugin_version(self, release):
        plugin_dir = release / "blesta" / "plugins" / "domains"
        assert read_plugin_version(plugin_dir) == "2.0.7"

    def test_plugin_version_missing(self, tmp_path):
        assert read_plugin_version(tmp_path) is None


class TestReadPhpClass:
    def test_class_name(self, release):
        name, source = read_php_class(
            release / "blesta" / "app" / "models" / "clients.php"
        )
        assert name == "Clients"
        assert "getList" in source

    def test_final_class(self, release):
        name, _ = read_php_class(
            release / "blesta" / "app" / "models" / "license_manager.php"
        )
        assert name == "LicenseManager"

    def test_encoded_file(self, release):
        name, _ = read_php_class(release / "blesta" / "app" / "models" / "license.php")
        assert name is None


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


class TestBuildSchemaFromRelease:
    @pytest.fixture
    def schema(self, release):
        return build_schema_from_release(release / "blesta")

    def test_only_app_models(self, schema):
        assert list(schema["models"]) == ["Clients"]

    def test_metadata(self, schema):
        meta = schema["metadata"]
        assert meta["blesta_version"] == "6.0.4"
        assert meta["source_type"] == "release_php_docblocks"
        assert meta["model_count"] == 1
        assert meta["total_methods"] == 3

    def test_model_entry(self, schema):
        clients = schema["models"]["Clients"]
        assert clients["source"] == "app/models/clients.php"
        assert clients["pagination"] == {"getList": "getListCount"}
        assert clients["methods"]["get"]["http_method"] == "GET"


class TestBuildPluginSchemaFromRelease:
    @pytest.fixture
    def schema(self, release):
        return build_plugin_schema_from_release(release / "blesta")

    def test_models(self, schema):
        assert sorted(schema["models"]) == [
            "domains.domains_tlds",
            "support_manager.support_manager_tickets",
        ]

    def test_metadata(self, schema):
        meta = schema["metadata"]
        assert meta["blesta_version"] == "6.0.4"
        assert meta["plugins"] == ["domains", "support_manager"]
        assert meta["plugin_versions"] == {
            "domains": "2.0.7",
            "support_manager": "3.3.11",
        }
        assert meta["total_methods"] == 2

    def test_github_plugins_link_to_github(self, schema):
        source = schema["models"]["domains.domains_tlds"]["source"]
        assert source.startswith("https://github.com/blesta/plugin-domains/")

    def test_bundled_plugins_use_release_path(self, schema):
        source = schema["models"]["support_manager.support_manager_tickets"]["source"]
        assert source == "plugins/support_manager/models/support_manager_tickets.php"

    def test_skips_unreadable_model(self, release):
        root = release / "blesta"
        (root / "plugins" / "domains" / "models" / "encoded.php").write_text(
            ENCODED_PHP
        )
        schema = build_plugin_schema_from_release(root)
        assert "domains.encoded" not in schema["models"]

    def test_skips_model_without_methods(self, release):
        root = release / "blesta"
        (root / "plugins" / "domains" / "models" / "empty.php").write_text(
            "<?php\nclass Empty extends AppModel {}\n"
        )
        schema = build_plugin_schema_from_release(root)
        assert "domains.empty" not in schema["models"]


class TestBuildSchemaSkipsEmptyModel:
    def test_skips_model_without_methods(self, release):
        root = release / "blesta"
        (root / "app" / "models" / "empty.php").write_text(
            "<?php\nclass Empty extends AppModel {}\n"
        )
        assert "Empty" not in build_schema_from_release(root)["models"]


# ---------------------------------------------------------------------------
# Docblock pairing regression (private docblock bleeding into public method)
# ---------------------------------------------------------------------------

DOCBLOCK_BLEED_PHP = """\
<?php
class Example extends AppModel
{
    /**
     * Partially constructs a query
     *
     * @param array $filters Filters
     * @return Record
     */
    private function getQuery(array $filters)
    {
        /* inline comment */
        return $this->Record;
    }

    /**
     * Fetches a list of records
     *
     * @param int $page The page
     * @return array Records
     */
    public function getList($page = 1)
    {
    }

    /**
     * Implicitly public method
     *
     * @return array
     */
    function appendDetails()
    {
    }

    /**
     * A static helper
     *
     * @return string
     */
    #[\\ReturnTypeWillChange]
    public static function format()
    {
    }

    /**
     * A protected static helper
     */
    protected static function hidden()
    {
    }
}
"""


class TestDocblockPairing:
    @pytest.fixture
    def methods(self):
        return parse_php_file(DOCBLOCK_BLEED_PHP)

    def test_private_docblock_not_attached_to_next_method(self, methods):
        assert methods["getList"]["description"] == "Fetches a list of records"
        assert [p["name"] for p in methods["getList"]["params"]] == ["page"]

    def test_private_method_skipped(self, methods):
        assert "getQuery" not in methods

    def test_implicit_public(self, methods):
        assert methods["appendDetails"]["description"] == "Implicitly public method"

    def test_static_with_attribute(self, methods):
        assert methods["format"]["description"] == "A static helper"

    def test_protected_static_skipped(self, methods):
        assert "hidden" not in methods
