#!/usr/bin/env python3
"""One-off source verification probe, round 2: miseleccion.mx static JSON."""
import json
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except Exception as e:  # noqa: BLE001
        return None, str(e).encode()


def show(label, url, limit=3500):
    print(f"\n=== {label}\n    {url}")
    status, body = get(url)
    print(f"  HTTP {status}, {len(body)} bytes")
    if status != 200:
        print(f"  body[:300]: {body[:300]!r}")
        return
    try:
        data = json.loads(body)
    except Exception as e:  # noqa: BLE001
        print(f"  not JSON: {e}")
        return
    if isinstance(data, list):
        print(f"  list of {len(data)} items; first items:")
        print("  " + json.dumps(data[:4], ensure_ascii=False)[:limit])
    elif isinstance(data, dict):
        print(f"  dict keys: {sorted(data.keys())}")
        print("  " + json.dumps(data, ensure_ascii=False)[:limit])


show("calendario", "https://miseleccion.mx/json/calendario.json")
show("resultados-anio", "https://miseleccion.mx/json/resultados-anio.json")
show("selecciones", "https://miseleccion.mx/json/selecciones.json", limit=1500)
print("\nPROBE DONE")
