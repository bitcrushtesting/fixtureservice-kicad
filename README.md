<!--
SPDX-FileCopyrightText: 2026 Bitcrush Testing
SPDX-License-Identifier: GPL-3.0-or-later
-->

# Bitcrush Fixture Service for KiCad

A KiCad plugin that checks the board open in the PCB editor for bed-of-nails
testability and returns a binding quote for a test fixture, without leaving
KiCad. Fix what the check finds, re-check, then open the quote in your
browser to order.

- **Read only.** The plugin reads the board and selects footprints. It never
  changes the board and never saves it.
- **Nothing kept.** The board goes over HTTPS to
  [bitcrushtesting.com](https://bitcrushtesting.com), which reads it, answers
  and deletes the file. Nothing is stored unless you save a quote in the
  browser. See the [privacy page](https://bitcrushtesting.com/privacy).
- **Staging for now.** Until the service launches, the plugin talks to
  `https://staging.bitcrushtesting.com`, where payments run in test mode and
  no order is real. The launch release switches `DEFAULT_BASE_URL` in
  `config.py` to production.

## Requirements

- KiCad 9.0 or later.
- The IPC API server enabled: **Preferences → Plugins → Enable KiCad API**.
- An internet connection.

## Install

**From the Bitcrush repository** (until the plugin is in KiCad's official
repository): in the Plugin and Content Manager, **Manage → Add**, enter
`https://bitcrushtesting.com/kicad/repository.json`, then install
*Bitcrush Fixture Service*.

**From a file:** download the `.zip` from the
[releases](https://github.com/bitcrushtesting/fixtureservice-kicad/releases)
and use **Install from File…** in the Plugin and Content Manager.

On first use KiCad builds the plugin's Python environment, which takes a
minute. On Linux, `wxPython` may have to build from source; install your
distribution's `python3-wxgtk4.0` package first if it does.

## Use

1. Open the board in the PCB editor and press the fixture button on the
   toolbar.
2. The first time, confirm the notice about what is sent.
3. The window shows the fixture price, lead time, how many test points are
   probed, the probe plate size, and the DFT findings by severity.
4. Click a finding to select the footprints it names on the board.
5. Change the board, then **Re-check**.
6. **Open in browser** opens the board on the quote page, as if you had
   uploaded it there: the fixture drawing, the options and the price. Order
   from there.

## How it works

```
plugin/
  plugin.json              the IPC plugin: one toolbar action
  fixture_check.py         what KiCad runs
  requirements.txt         installed by KiCad into the plugin's environment
  fixtureservice_kicad/
    config.py              service URL (HTTPS only), language
    api.py                 POST /api/analyze and /api/quote, errors in words
    board_source.py        the open board as .kicad_pcb text, via the IPC API
    model.py               the reply, reduced to what the window shows
    locator.py             finding references -> footprints -> selection
    session.py             one run: check, re-check, one stored quote per board
    consent.py             the one-time notice
    ui.py, app.py          the window, and the wiring (the only code needing wx/KiCad)
```

The board is taken from the editor with the IPC API's `get_as_string()`, so
unsaved edits are checked too and the file on disk is not touched. The
analysis comes back with a seal from the service; the plugin returns it
unchanged when it saves the quote, so it cannot alter what is priced.

## Develop

```sh
uv venv --python /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 .venv
uv pip install --python .venv/bin/python pytest jsonschema kicad-python wxPython
.venv/bin/python -m pytest              # unit tests, a fake service on a local socket
uvx ruff check plugin tests tools
```

Live tests, never against production:

```sh
FIXTURESERVICE_URL=http://127.0.0.1:5173 \
FIXTURE_TEST_BOARD=/path/to/board.kicad_pcb \
    .venv/bin/python -m pytest -m service     # the real service
.venv/bin/python -m pytest -m kicad           # KiCad running, API on, a board open
```

`FIXTURESERVICE_URL` also points the plugin itself at a development or
staging service. It accepts HTTPS, or HTTP to this machine only.

HTTPS is verified against the system's roots plus certifi's. KiCad's own
Python on macOS loads no roots at all, so without certifi every request fails
with `CERTIFICATE_VERIFY_FAILED`; `pytest -m network` checks the real thing.

The service rejects multipart uploads whose `Origin` is not its own (its
CSRF check), so the client sends the service's origin, as a browser would.

To try the plugin in KiCad without packaging it, link `plugin/` into
KiCad's plugin folder (on macOS `~/Documents/KiCad/<version>/plugins/`)
and reload plugins in the PCB editor's preferences.

## Release

1. Raise the version in `pcm/metadata.json`, `pyproject.toml` and
   `plugin/fixtureservice_kicad/__init__.py` (a test checks they agree).
2. `python tools/make_icons.py` if the icon changed.
3. Tag `vX.Y.Z` and push the tag. CI tests, builds the package and drafts a
   GitHub release with the `.zip`, `metadata.json` and the repository files.
4. Publish the release. Copy `packages.json` and `repository.json` to
   `https://bitcrushtesting.com/kicad/`.
5. For KiCad's official repository: a merge request to
   [kicad/addons/metadata](https://gitlab.com/kicad/addons/metadata) adding
   or updating `packages/com.bitcrushtesting.fixture-service/metadata.json`.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
