#!/usr/bin/env python3
"""One-off source verification probe. Run in GitHub Actions (open internet).

Hits candidate ESPN endpoints for team 2812 and miseleccion.mx/calendario,
prints bounded summaries so we can pick primary + fallback sources.
"""
import json
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except Exception as e:  # noqa: BLE001
        return None, str(e).encode()


def summarize_espn_schedule(data):
    team = data.get("team", {})
    print(f"  team: id={team.get('id')} name={team.get('displayName')!r} slug={team.get('slug')!r}")
    events = data.get("events", [])
    print(f"  events: {len(events)}")
    for ev in events[:4]:
        comps = ev.get("competitions", [{}])
        c = comps[0] if comps else {}
        venue = (c.get("venue") or {}).get("fullName")
        status = ((c.get("status") or {}).get("type") or {}).get("name")
        date_valid = (c.get("status") or {}).get("type", {})
        competitors = c.get("competitors", [])
        sides = []
        for cp in competitors:
            t = cp.get("team", {})
            score = cp.get("score")
            if isinstance(score, dict):
                score = score.get("displayValue")
            sides.append(f"{t.get('displayName')}({t.get('id')}) score={score}")
        league = (ev.get("league") or {}).get("name") or (ev.get("seasonType") or {}).get("name")
        print(f"    id={ev.get('id')} date={ev.get('date')} timeValid={c.get('timeValid')} "
              f"status={status} league={league!r} venue={venue!r}")
        print(f"      {' | '.join(sides)}")
        print(f"      keys(event)={sorted(ev.keys())}")
        print(f"      seasonType={ev.get('seasonType')}")


def probe_espn(label, url):
    print(f"\n=== {label}\n    {url}")
    status, body = get(url)
    print(f"  HTTP {status}, {len(body)} bytes")
    if status != 200:
        print(f"  body[:300]: {body[:300]!r}")
        return
    try:
        data = json.loads(body)
    except Exception as e:  # noqa: BLE001
        print(f"  not JSON: {e}; body[:300]: {body[:300]!r}")
        return
    if "events" in data or "team" in data:
        summarize_espn_schedule(data)
    else:
        print(f"  top-level keys: {sorted(data.keys())}")
        print(f"  body[:500]: {body[:500]!r}")


def probe_miseleccion():
    url = "https://miseleccion.mx/calendario"
    print(f"\n=== miseleccion.mx\n    {url}")
    status, body = get(url)
    print(f"  HTTP {status}, {len(body)} bytes")
    if status != 200:
        print(f"  body[:300]: {body[:300]!r}")
        return
    html = body.decode("utf-8", "replace")
    for needle in ["__NEXT_DATA__", "wp-json", "api/", ".json", "femenil", "Femenil", "graphql"]:
        idxs = [m.start() for m in re.finditer(re.escape(needle), html)]
        print(f"  {needle!r}: {len(idxs)} hits")
    # candidate fetch/XHR URLs embedded in the page
    urls = sorted(set(re.findall(r'https?://[^"\'\s\\]+(?:json|api)[^"\'\s\\]*', html)))[:20]
    print(f"  candidate api urls: {urls}")
    # show context around first Femenil hit
    m = re.search(r"[Ff]emenil", html)
    if m:
        s = max(0, m.start() - 400)
        print("  context around first 'femenil' hit:")
        print("  " + html[s:m.start() + 800].replace("\n", " ")[:1200])


LEAGUES = ["fifa.friendly.w", "concacaf.w_qualifiers", "concacaf.w_championship",
           "fifa.wwc", "concacaf.womens.gold", "all"]

for lg in LEAGUES:
    probe_espn(
        f"site.api schedule league={lg}",
        f"https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/teams/2812/schedule",
    )

probe_espn("site.web.api all fixture=true",
           "https://site.web.api.espn.com/apis/site/v2/sports/soccer/all/teams/2812/schedule?fixture=true")
probe_espn("site.web.api all fixture=false (results)",
           "https://site.web.api.espn.com/apis/site/v2/sports/soccer/all/teams/2812/schedule?fixture=false")
probe_espn("team identity check",
           "https://site.api.espn.com/apis/site/v2/sports/soccer/all/teams/2812")

probe_miseleccion()
print("\nPROBE DONE")
