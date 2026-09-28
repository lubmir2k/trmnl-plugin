# WebUntis timetable on TRMNL (Serverless)

Shows a pupil's WebUntis timetable for the next two school days (from 15:00 on, starting
tomorrow). Cancelled lessons are struck through; substitutions and room changes are bold
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
3. Turn on Debug Logs, Force Refresh, and check the logs: `took_ms` in the variables says
   how close the run is to TRMNL's 5 s limit.

WebUntis calls per run: `authenticate`, `getTimetable`, `logout` (JSON-RPC). The refresh
rate decides how often that happens; Hourly is plenty for a timetable.
