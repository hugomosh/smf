# smf — Calendario de la Selección Mexicana Femenil 🇲🇽

Subscribable calendar for the Mexico women's senior national team.
Página con instrucciones: **https://hugomosh.github.io/smf/**

## Suscríbete (español)

```
https://hugomosh.github.io/smf/smf.ics
```

Copia esa liga y pégala en tu app de calendario:

- **iPhone / iPad**: Ajustes → Apps → Calendario → Cuentas → Añadir cuenta →
  Otra → **Añadir calendario suscrito** → pega la liga → Siguiente → Guardar.
- **Mac**: app Calendario → Archivo → **Nueva suscripción a calendario** →
  pega la liga → Actualizar: cada hora.
- **Google Calendar**: desde una computadora en calendar.google.com, junto a
  "Otros calendarios" haz clic en **+** → **Desde URL** → pega la liga.
  (No se puede desde la app del celular.)
- **Outlook web**: Calendario → Agregar calendario → **Suscribirse desde la web**.

Incluye solo partidos de la **selección mayor femenil** — no Sub-17, Sub-20,
Sub-23 ni la rama varonil. Los partidos sin horario confirmado aparecen como
evento de todo el día y se convierten solos en evento con hora. Los horarios se
publican en UTC y tu teléfono los convierte a tu zona. En iPhone/Mac se
actualiza cada hora; Google revisa los calendarios externos cuando quiere
(8–24 h), así que ahí los marcadores llegan tarde.

## Subscribe (English)

```
https://hugomosh.github.io/smf/smf.ics
```

- **Apple Calendar** (iOS): Settings → Calendar → Accounts → Add Account →
  Other → Add Subscribed Calendar → paste the URL. (macOS: File → New
  Calendar Subscription.) Apple honors the 1-hour refresh hint, so scores
  land in the event title shortly after full time.
- **Google Calendar**: Other calendars → `+` → From URL → paste the URL.
  Google refreshes external calendars on its own schedule (8–24 h), so
  scores show up late there. Fixtures themselves are fine.

## How it works

```
fetch.py  →  docs/fixtures.json  →  ics.py  →  docs/smf.ics
```

- `fetch.py` pulls from ESPN's unofficial API (team **2812** = senior
  women's team, slug `mex.w`), normalizes into `docs/fixtures.json`, and
  tracks per-match `seq`/`fingerprint`/`last_modified_utc` so calendar
  clients see updates (score changes, time confirmations) as replacements,
  never duplicates.
- `ics.py` renders `fixtures.json` to `docs/smf.ics`. No network. A future
  Google Calendar API writer can consume the same `fixtures.json`.
- `.github/workflows/update.yml` runs hourly (plus manual
  `workflow_dispatch`, e.g. from the GitHub mobile app) and commits `docs/`
  only when content actually changed.

Matches with a confirmed kickoff are timed events in UTC; matches where
Concacaf has only announced the date are all-day events that flip to timed
(same UID) once the time confirms. Finished/live matches carry the score in
the title: `🇲🇽 México 2-0 Costa Rica (FT)`.

### Senior-team filter

The main correctness risk is youth/men's matches leaking in. Two explicit
guards in `fetch.py` (`is_senior_femenil`):

1. Every event must include team id **2812** among its competitors — ESPN
   gives the senior femenil its own id (the men are 203, youth teams have
   their own ids).
2. Any event whose league/name/round mentions U-17/U-20/U-23/Sub-* is
   dropped and logged with an `EXCLUDED:` line in the workflow log.

## Data sources (verified 2026-07-25)

Primary — ESPN unofficial API:

- Upcoming: `https://site.web.api.espn.com/apis/site/v2/sports/soccer/all/teams/2812/schedule?fixture=true`
- Results (with scores): `https://site.api.espn.com/apis/site/v2/sports/soccer/all/teams/2812/schedule`
- League-scoped codes (`concacaf.w_championship`, `concacaf.w_qualifiers`)
  return HTTP 400; the `all` pseudo-league works and spans every competition.

Fallback / cross-check — official FMF (server-rendered Angular app backed by
static JSON, no auth):

- `https://miseleccion.mx/json/calendario.json` (upcoming, all teams; filter
  `categoria == "Femenil Mayor"`)
- `https://miseleccion.mx/json/resultados-anio.json` (results by year, with
  scores)
- Caveat: times are venue-local (`hora`) / Mexico City (`hora_centro`)
  without UTC offsets, so it's the fallback, not the primary.

If ESPN fails, the workflow keeps the last good `fixtures.json` and exits
green — the published calendar never disappears on a bad fetch.

## Run locally

```sh
python3 fetch.py   # network: writes docs/fixtures.json
python3 ics.py     # offline: renders docs/smf.ics
```

Python 3 stdlib only, nothing to install.

## Repo settings (one-time)

- [x] **Pages** → Source: Deploy from a branch → `main` / `docs` folder —
  the feed is served by GitHub Pages.
- [x] **Actions → General → Workflow permissions**: "Read and write" — the
  workflow also declares `permissions: contents: write`, which is scoped per
  workflow and works even if the repo default stays read-only.

## Known gotchas

- **Scheduled workflows auto-disable after 60 days without repo activity**,
  and commits by `github-actions[bot]` don't reset that timer. Workaround
  when it becomes a problem: create a fine-grained PAT (contents: write),
  add it as a repo secret, and have the workflow commit with it — those
  commits count as user activity. Not set up yet; a re-enable click in the
  Actions tab also works.
- ESPN's API is unofficial and can change shape without notice. `fetch.py`
  retries with backoff, never crashes the workflow, and the probe script
  used for source verification lives in git history
  (`git show 85160d9:probe.py`) if you need to re-inspect the feeds.
