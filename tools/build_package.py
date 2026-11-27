# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the PCM package and the metadata to publish it with.

    python tools/build_package.py [--repo-url https://bitcrushtesting.com/kicad]

Writes to dist/:

  com.bitcrushtesting.fixture-service-<version>.zip
      The archive KiCad installs: metadata.json, plugins/, resources/.
  metadata.json
      The same metadata with download_url, sha256 and sizes filled in: the
      file a merge request to gitlab.com/kicad/addons/metadata carries.
  repository/packages.json, repository/repository.json
      A self-hosted PCM repository; users add the repository.json URL in the
      Plugin and Content Manager.

The archive is deterministic (fixed timestamps, sorted entries), so the same
source gives the same sha256.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterator, Tuple

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugin"
SOURCE = "https://github.com/bitcrushtesting/fixtureservice-kicad"
FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def plugin_files() -> Iterator[Tuple[str, Path]]:
    for path in sorted(PLUGIN.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts or path.suffix == ".pyc" or path.name == ".DS_Store":
            continue
        yield "plugins/" + path.relative_to(PLUGIN).as_posix(), path


def load_metadata() -> Dict[str, Any]:
    return json.loads((ROOT / "pcm" / "metadata.json").read_text(encoding="utf-8"))


def version_of(meta: Dict[str, Any]) -> str:
    return meta["versions"][0]["version"]


def build_zip(meta: Dict[str, Any]) -> Tuple[bytes, int]:
    """The archive's bytes and its extracted size."""
    inner = json.loads(json.dumps(meta))
    for v in inner["versions"]:  # the archive's copy never carries download_*
        for k in [k for k in v if k.startswith("download_") or k == "install_size"]:
            del v[k]
    entries = [("metadata.json", (json.dumps(inner, indent=2) + "\n").encode("utf-8"))]
    entries += [(name, path.read_bytes()) for name, path in plugin_files()]
    entries.append(("resources/icon.png", (ROOT / "resources" / "icon.png").read_bytes()))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(entries):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
    return buf.getvalue(), sum(len(d) for _n, d in entries)


def build(out: Path, repo_url: str) -> Dict[str, Any]:
    meta = load_metadata()
    version = version_of(meta)
    archive, install_size = build_zip(meta)
    name = f"{meta['identifier']}-{version}.zip"
    out.mkdir(parents=True, exist_ok=True)
    (out / name).write_bytes(archive)

    published = json.loads(json.dumps(meta))
    published["versions"][0].update(
        download_url=f"{SOURCE}/releases/download/v{version}/{name}",
        download_sha256=hashlib.sha256(archive).hexdigest(),
        download_size=len(archive),
        install_size=install_size,
    )
    (out / "metadata.json").write_text(json.dumps(published, indent=2) + "\n", encoding="utf-8")

    repo = out / "repository"
    repo.mkdir(exist_ok=True)
    packages = (json.dumps({"packages": [published]}, indent=2) + "\n").encode("utf-8")
    (repo / "packages.json").write_bytes(packages)
    now = int(time.time())
    repository = {
        "$schema": "https://go.kicad.org/pcm/schemas/v1#/definitions/Repository",
        "name": "Bitcrush Testing",
        "maintainer": {"name": "Bitcrush Testing", "contact": {"web": "https://bitcrushtesting.com"}},
        "packages": {
            "url": f"{repo_url.rstrip('/')}/packages.json",
            "sha256": hashlib.sha256(packages).hexdigest(),
            "update_timestamp": now,
            "update_time_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(now)),
        },
    }
    (repo / "repository.json").write_text(json.dumps(repository, indent=2) + "\n", encoding="utf-8")
    return published


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument("--repo-url", default="https://bitcrushtesting.com/kicad")
    args = parser.parse_args()
    published = build(args.out, args.repo_url)
    v = published["versions"][0]
    print(f"{published['identifier']} {v['version']}: {v['download_size']} bytes, sha256 {v['download_sha256']}")


if __name__ == "__main__":
    main()
