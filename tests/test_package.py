# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
"""The package KiCad installs, checked against KiCad's own schemas.

The schemas are vendored in tests/schemas from go.kicad.org, so the test
runs offline and a schema change upstream shows up as a diff.
"""

import io
import json
import os
import re
import zipfile
from pathlib import Path

import pytest
from fixtureservice_kicad import __version__, config

from tools import build_package

jsonschema = pytest.importorskip("jsonschema")

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = Path(__file__).parent / "schemas"


def schema(name):
    return json.loads((SCHEMAS / name).read_text())


def test_plugin_json_is_valid_and_its_files_exist():
    manifest = json.loads((ROOT / "plugin" / "plugin.json").read_text())
    jsonschema.validate(manifest, schema("api-plugin-v1.json"))
    assert manifest["identifier"] == config.PLUGIN_ID
    for action in manifest["actions"]:
        assert (ROOT / "plugin" / action["entrypoint"]).is_file()
        for icon in action["icons-light"] + action["icons-dark"]:
            assert (ROOT / "plugin" / icon).is_file(), icon


def test_one_version_everywhere():
    meta = build_package.load_metadata()
    assert build_package.version_of(meta) == __version__
    assert re.search(rf'^version = "{re.escape(__version__)}"', (ROOT / "pyproject.toml").read_text(), re.M)


def test_the_built_package(tmp_path):
    published = build_package.build(tmp_path, "https://example.com/kicad")
    pcm = schema("pcm-v1.json")
    jsonschema.validate(published, pcm)
    assert published["identifier"] == config.PLUGIN_ID
    assert published["versions"][0]["runtime"] == "ipc"

    archive = (tmp_path / f"{config.PLUGIN_ID}-{__version__}.zip").read_bytes()
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        names = set(z.namelist())
        inner = json.loads(z.read("metadata.json"))
    # KiCad's layout: metadata.json, plugins/ with plugin.json, resources/icon.png. Nothing else.
    assert {"metadata.json", "plugins/plugin.json", "plugins/fixture_check.py",
            "plugins/requirements.txt", "resources/icon.png"} <= names
    assert all(n == "metadata.json" or n.startswith(("plugins/", "resources/")) for n in names)
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)
    # The archive's own metadata never carries the download keys.
    assert not any(k.startswith("download_") or k == "install_size" for k in inner["versions"][0])
    # Deterministic: the same source, the same checksum.
    again = build_package.build(tmp_path / "again", "https://example.com/kicad")
    assert again["versions"][0]["download_sha256"] == published["versions"][0]["download_sha256"]

    repo = json.loads((tmp_path / "repository" / "repository.json").read_text())
    jsonschema.validate(repo, {**pcm, "$ref": "#/definitions/Repository"})
    assert repo["packages"]["url"] == "https://example.com/kicad/packages.json"


def test_nothing_internal_is_named_in_what_ships():
    """The plugin is public source; the service's internals are not.

    The words to look for are themselves internal, so they come from the
    environment (comma-separated) rather than from this file.
    """
    words = [w.strip() for w in os.environ.get("FIXTURESERVICE_PRIVATE_WORDS", "").split(",") if w.strip()]
    if not words:
        pytest.skip("FIXTURESERVICE_PRIVATE_WORDS is not set")
    banned = re.compile("|".join(re.escape(w) for w in words), re.I)
    for path in [p for p in ROOT.rglob("*") if p.is_file() and ".venv" not in p.parts and ".git" not in p.parts
                 and "dist" not in p.parts and p.suffix in {".py", ".json", ".txt", ".md", ".toml", ".yml"}]:
        assert not banned.search(path.read_text(encoding="utf-8")), path
