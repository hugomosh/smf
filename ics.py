#!/usr/bin/env python3
"""Render docs/fixtures.json -> docs/smf.ics. Pure renderer, no network.

Rules:
  - UID is stable per match: espn-{eventId}@smf.hugomosh.dev
  - time_valid=False (kickoff TBD) -> all-day event; flips to timed later, same UID
  - SUMMARY carries the score once live/finished, Mexico's goals always first
  - DTSTAMP/LAST-MODIFIED/SEQUENCE come from fixtures.json so output only
    changes when match data changed (keeps CI commits meaningful)

Stdlib only.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DOCS = Path(__file__).parent / "docs"
FIXTURES_PATH = DOCS / "fixtures.json"
ICS_PATH = DOCS / "smf.ics"

UID_DOMAIN = "smf.hugomosh.dev"
MEXICO_ID = "2812"
MATCH_HOURS = 2  # assumed duration for timed events


def parse_utc(s):
    for fmt in ("%Y-%m-%dT%H:%MZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"unparseable date: {s!r}")


def ics_escape(text):
    return (text.replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\n", "\\n"))


def fold(line):
    """RFC 5545 folding: max 75 octets per line, continuation lines start with a space."""
    out = []
    raw = line.encode("utf-8")
    while len(raw) > 75:
        cut = 75
        while cut > 0 and (raw[cut] & 0xC0) == 0x80:  # don't split UTF-8 sequences
            cut -= 1
        out.append(raw[:cut].decode("utf-8"))
        raw = b" " + raw[cut:]
    out.append(raw.decode("utf-8"))
    return "\r\n".join(out)


def summary_for(match):
    mex, opp = ((match["home"], match["away"])
                if match["home"]["id"] == MEXICO_ID
                else (match["away"], match["home"]))
    if match["state"] in ("in", "post") and mex["score"] is not None and opp["score"] is not None:
        tag = match.get("status_detail") or ("FT" if match["state"] == "post" else "En vivo")
        return f"🇲🇽 México {mex['score']}-{opp['score']} {opp['name']} ({tag})"
    return f"🇲🇽 México vs {opp['name']}"


def event_lines(match):
    dt = parse_utc(match["date_utc"])
    stamp = parse_utc(match["last_modified_utc"]).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VEVENT",
             f"UID:{match['id']}@{UID_DOMAIN}",
             f"SEQUENCE:{match.get('seq', 0)}",
             f"DTSTAMP:{stamp}",
             f"LAST-MODIFIED:{stamp}"]
    if match.get("time_valid", True):
        lines.append("DTSTART:" + dt.strftime("%Y%m%dT%H%M%SZ"))
        lines.append("DTEND:" + (dt + timedelta(hours=MATCH_HOURS)).strftime("%Y%m%dT%H%M%SZ"))
    else:
        # Kickoff TBD: all-day event on the (UTC) match date until the time confirms.
        lines.append("DTSTART;VALUE=DATE:" + dt.strftime("%Y%m%d"))
        lines.append("DTEND;VALUE=DATE:" + (dt + timedelta(days=1)).strftime("%Y%m%d"))
    lines.append("SUMMARY:" + ics_escape(summary_for(match)))
    location = ", ".join(x for x in (match.get("venue"), match.get("venue_city")) if x)
    if location:
        lines.append("LOCATION:" + ics_escape(location))
    desc = [x for x in (match.get("competition"), match.get("round")) if x]
    if not match.get("time_valid", True):
        desc.append("Hora por confirmar")
    if match.get("broadcast"):
        desc.append("TV: " + match["broadcast"])
    if desc:
        lines.append("DESCRIPTION:" + ics_escape(" · ".join(desc)))
    lines.append("STATUS:CONFIRMED")
    lines.append("END:VEVENT")
    return lines


def render(matches):
    lines = ["BEGIN:VCALENDAR",
             "VERSION:2.0",
             "PRODID:-//hugomosh//smf//ES",
             "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH",
             "X-WR-CALNAME:🇲🇽 Selección Mexicana Femenil",
             "X-WR-CALDESC:Partidos de la selección mayor femenil de México",
             "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
             "X-PUBLISHED-TTL:PT1H"]
    for match in matches:
        lines.extend(event_lines(match))
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(l) for l in lines) + "\r\n"


def main():
    data = json.loads(FIXTURES_PATH.read_text())
    matches = data["matches"]
    ICS_PATH.write_text(render(matches))
    print(f"wrote {ICS_PATH}: {len(matches)} events")
    return 0


if __name__ == "__main__":
    sys.exit(main())
