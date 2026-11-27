# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
"""The service's reply, reduced to what the results window shows.

Read defensively: the service and the plugin ship separately, so a field the
plugin does not know is ignored and a missing one shows as unknown rather
than breaking the window.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

SEVERITIES = ("error", "warning", "info")


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    summary: str
    detail: str = ""
    refs: Tuple[str, ...] = ()


@dataclass
class Result:
    board_name: str
    total_net_eur: Optional[float]
    lead_time_days: Optional[int]
    valid_until: str
    auto_quotable: bool
    manual_review: List[str]
    test_points: Optional[int]
    plate_mm: Optional[Tuple[float, float]]
    findings: List[Finding] = field(default_factory=list)

    def count(self, severity: str) -> int:
        return sum(1 for f in self.findings if f.severity == severity)


def _num(value: Any) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _findings(raw: Any) -> List[Finding]:
    out: List[Finding] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        severity = item.get("severity")
        if severity not in SEVERITIES:
            continue
        raw_refs = item.get("refs")
        refs: List[Any] = raw_refs if isinstance(raw_refs, list) else []
        out.append(
            Finding(
                code=str(item.get("code") or ""),
                severity=severity,
                summary=str(item.get("summary") or item.get("code") or ""),
                detail=str(item.get("detail") or ""),
                refs=tuple(str(r) for r in refs if isinstance(r, (str, int))),
            )
        )
    # Errors first, then warnings, then notes; the reader's order within each.
    rank = {s: i for i, s in enumerate(SEVERITIES)}
    return sorted(out, key=lambda f: rank[f.severity])


def parse_result(board_name: str, reply: Dict[str, Any]) -> Result:
    quote = _dict(reply.get("quote"))
    plan = _dict(reply.get("plan"))
    analysis = _dict(reply.get("analysis"))

    total = _num(_dict(plan.get("probeCount")).get("total"))
    plate = _dict(plan.get("plate"))
    w, h = _num(plate.get("width")), _num(plate.get("height"))
    lead = _num(quote.get("leadTimeWorkingDays"))
    raw_review = quote.get("manualReview")
    review: List[Any] = raw_review if isinstance(raw_review, list) else []

    return Result(
        board_name=board_name,
        total_net_eur=_num(quote.get("totalNetEur")),
        lead_time_days=int(lead) if lead is not None else None,
        valid_until=str(quote.get("validUntil") or "")[:10],
        auto_quotable=bool(quote.get("autoQuotable", False)),
        manual_review=[str(r) for r in review],
        test_points=int(total) if total is not None else None,
        plate_mm=(w, h) if w is not None and h is not None else None,
        findings=_findings(analysis.get("findings")),
    )


def format_eur(value: Optional[float], language: str = "en") -> str:
    if value is None:
        return "–"
    text = f"{value:,.2f}"
    if language == "de":
        text = text.replace(",", "\0").replace(".", ",").replace("\0", ".")
        return f"{text} €"
    return f"€{text}"
