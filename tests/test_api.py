# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import ssl

import pytest
from fixtureservice_kicad import config
from fixtureservice_kicad.api import Client, ServiceError


def test_analyze_sends_the_board_as_the_web_page_does(service):
    reply = Client(service.url, "de").analyze('my "board".kicad_pcb', b"(kicad_pcb)")
    assert reply["seal"] == "s3al"
    path, headers, body = service.requests[0]
    assert path == "/api/analyze"
    assert headers["content-type"].startswith("multipart/form-data; boundary=")
    assert b'name="board"; filename="my board.kicad_pcb"' in body
    assert b"(kicad_pcb)" in body
    # The service's CSRF check compares the Origin to its own; no path in it.
    assert headers["origin"] == service.url.rsplit("/fixture", 1)[0]
    assert headers["accept-language"] == "de"
    assert headers["x-fixture-client"].startswith("fixtureservice-kicad/")


def test_a_reply_without_the_seal_is_refused_not_guessed_at(service):
    service.reply("/api/analyze", 200, {"analysis": {}, "quote": {}})
    with pytest.raises(ServiceError, match="missing .*seal"):
        Client(service.url).analyze("b.kicad_pcb", b"x")


def test_a_board_over_the_limit_is_not_sent(service, monkeypatch):
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 10)
    with pytest.raises(ServiceError, match="accepts up to"):
        Client(service.url).analyze("b.kicad_pcb", b"x" * 11)
    assert service.requests == []


@pytest.mark.parametrize(
    "status,body,headers,expect,retry",
    [
        (413, {"message": "the board file is larger than 25 MB"}, {}, "larger than 25 MB", None),
        (429, {"message": "Too many uploads."}, {"Retry-After": "300"}, "Too many uploads.", 300),
        (422, {"message": "No outline on Edge.Cuts."}, {}, "No outline on Edge.Cuts.", None),
        (403, b"Cross-site POST form submissions are forbidden", {}, "origin", None),
        (426, {"message": "Update the plugin."}, {}, "Update the plugin.", None),
        (500, {"message": "Internal Error"}, {}, "try again later", None),
    ],
)
def test_errors_reach_the_user_in_words(service, status, body, headers, expect, retry):
    service.reply("/api/analyze", status, body, headers)
    with pytest.raises(ServiceError) as caught:
        Client(service.url).analyze("b.kicad_pcb", b"x")
    assert expect in caught.value.message
    assert caught.value.status == status
    assert caught.value.retry_after == retry


def test_an_unreachable_service_says_so():
    with pytest.raises(ServiceError, match="Could not reach"):
        Client("http://127.0.0.1:9/fixture").analyze("b.kicad_pcb", b"x")


def test_the_board_is_handed_off_with_the_analysis_and_seal_untouched(service):
    client = Client(service.url, "de")
    analyzed = client.analyze("b.kicad_pcb", b"x")
    code = client.hand_off(analyzed)
    path, headers, body = service.requests[-1]
    assert path == "/api/handoff"
    assert headers["content-type"] == "application/json"
    assert json.loads(body) == {
        "analysis": analyzed["analysis"],
        "options": analyzed["options"],
        "boardDocument": analyzed["boardDocument"],
        "seal": "s3al",
    }
    # The quote page, not the checkout; the code in the fragment, never sent to a server.
    assert client.board_page_url(code) == f"{service.url}/?lang=de#board=c0de_-x"


def test_a_handoff_reply_without_a_code_is_an_error(service):
    service.reply("/api/handoff", 200, {"expiresInSeconds": 900})
    client = Client(service.url)
    with pytest.raises(ServiceError, match="could not be handed to the browser"):
        client.hand_off(client.analyze("b.kicad_pcb", b"x"))


def test_https_trusts_the_public_roots_even_where_python_brings_none():
    # KiCad's own Python on macOS loads zero roots by default; certifi's are added.
    pytest.importorskip("certifi")
    from fixtureservice_kicad.api import tls_context

    assert tls_context().cert_store_stats()["x509_ca"] > 100
    assert tls_context().verify_mode == ssl.CERT_REQUIRED and tls_context().check_hostname


def test_a_certificate_that_fails_verification_is_explained_not_just_reported():
    from urllib.error import URLError

    def opener(req, timeout):
        raise URLError(ssl.SSLCertVerificationError(1, "certificate verify failed"))

    with pytest.raises(ServiceError, match="certificate could not be verified, so nothing was sent"):
        Client("https://staging.bitcrushtesting.com", "en", opener=opener).analyze("b.kicad_pcb", b"(kicad_pcb)")


@pytest.mark.network
def test_the_default_service_answers_over_verified_https():
    """Through the plugin's own opener, as KiCad's Python will make the request."""
    from urllib.request import Request

    from fixtureservice_kicad.api import _urlopen

    with _urlopen(Request(config.DEFAULT_BASE_URL + "/api/health"), timeout=20) as res:
        assert res.status == 200 and json.loads(res.read())["ok"] is True
