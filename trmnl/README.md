# WebUntis timetable on TRMNL (Serverless)

Shows a pupil's WebUntis timetable for the next school day (from 15:00 on, tomorrow's)
and open homework. Cancelled lessons are struck through; substitutions and room changes are bold
with an asterisk and show the teacher. Runs entirely on TRMNL: no server, no Mac.

| File | Where it goes in TRMNL |
|---|---|
| `form_fields.yml` | Plugin settings → Form Fields |
| `serverless.py` | Edit Markup → Serverless tab, language Python |
| `markup_full.liquid` | Edit Markup → Full |

Setup:

1. Paste `form_fields.yml` into Form Fields and save, then fill in the fields.
   Server and school are in the WebUntis URL
   (`https://<server>/WebUntis/...?school=<school>`); the student id is the `entityId` in
   the timetable URL. The password is a password field, not stored in this repo.
2. Paste `serverless.py` into the Serverless tab and `markup_full.liquid` into Full.
3. Strategy: **Polling**, with any small URL that always answers 200 - the fetched data
   is ignored, the poll only exists to trigger the function. We use
   `https://api.open-meteo.com/v1/forecast?latitude=48.2&longitude=16.37&daily=sunrise&forecast_days=1`.
   The response may be constant: measured 28.09.2026 over four scheduled hourly refreshes,
   two with a changing response (`current_weather=true`) and two with this constant one -
   all four ran the function and redrew the screen, none logged "Skipping: No change in
   data". (The output always differs anyway: it carries the `updated` time.)
   Not Webhook: Serverless transforms data that *arrives*, so with Webhook and nobody
   posting it never runs (tried 28.09.2026 on this advice - only `{{ trmnl }}` existed and
   the screen said "Kein Stundenplan" with no reason).
4. Turn on Debug Logs, Force Refresh (it asks "Are you sure?"), and check the logs: the
   `[TransformRuntime]` line shows `duration_ms` and the returned JSON. First real run:
   267 ms.

WebUntis calls per run: `authenticate`, `getTimetable`, `logout` (JSON-RPC). The refresh
rate decides how often that happens; Hourly is plenty for a timetable.
