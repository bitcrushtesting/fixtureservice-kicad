# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
import json

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


def test_the_quote_goes_back_with_the_analysis_and_seal_untouched(service):
    client = Client(service.url)
    analyzed = client.analyze("b.kicad_pcb", b"x")
    stored = client.store_quote(analyzed)
    path, headers, body = service.requests[-1]
    assert path == "/api/quote"
    assert headers["content-type"] == "application/json"
    sent = json.loads(body)
    assert sent == {
        "analysis": analyzed["analysis"],
        "options": analyzed["options"],
        "boardDocument": analyzed["boardDocument"],
        "seal": "s3al",
    }
    assert client.checkout_url(stored["id"], stored["token"]) == f"{service.url}/checkout?quote=q1&token=t%2F1"


def test_a_quote_reply_without_a_token_is_an_error(service):
    service.reply("/api/quote", 200, {"id": "q1"})
    client = Client(service.url)
    with pytest.raises(ServiceError, match="could not be saved"):
        client.store_quote(client.analyze("b.kicad_pcb", b"x"))
