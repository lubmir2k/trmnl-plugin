"""
TRMNL Serverless function: a pupil's WebUntis timetable for the next two school days.

Paste this into the plugin's markup editor -> Serverless tab (language: Python).
TRMNL calls run(input) and exposes the returned dict's top-level keys to the markup
(trmnl/markup_full.liquid). Limits per the TRMNL docs: 128 MB, 5 seconds.

Nothing school- or pupil-specific lives here (this repo is public): school, login and
student id come from the plugin's form fields (trmnl/form_fields.yml).

Only the timetable is fetched - three JSON-RPC calls (authenticate, getTimetable,
logout), the same ones amadeus/tools/webuntis_fetch.py makes. Homework needs a second,
web-form login and is left out until the timing from TRMNL's servers is known.
"""
import datetime
import time

import requests

UA = "trmnl-webuntis/1 (private household use)"
DEADLINE_S = 4.0     # TRMNL kills the run at 5 s; leave room to return an error instead
LOOKAHEAD_DAYS = 10  # far enough to jump a weekend plus a short holiday
SWITCH_HOUR = 15     # from 15:00 on, today is over: start the display at tomorrow
DAY_NAMES = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


# ----------------------------------------------------------------------------- input

def field(inp, key):
    """A form field value. The docs say form values are passed to run() but not under
    which key, so accept both the top level and the markup's trmnl.plugin_settings path."""
    if inp.get(key) not in (None, ""):
        return str(inp[key]).strip()
    trmnl = inp.get("trmnl") or {}
    values = (trmnl.get("plugin_settings") or {}).get("custom_fields_values") or {}
    v = values.get(key)
    return str(v).strip() if v not in (None, "") else ""


# ----------------------------------------------------------------------------- time

def vienna_now():
    """Local time in Vienna. zoneinfo may lack tzdata in the sandbox, so fall back to the
    EU rule: CEST from the last Sunday of March 01:00 UTC to the last Sunday of October."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Europe/Vienna")).replace(tzinfo=None)
    except Exception:
        pass
    utc = datetime.datetime.utcnow()

    def last_sunday(month):
        d = datetime.datetime(utc.year, month, 31, 1)
        return d - datetime.timedelta(days=(d.weekday() + 1) % 7)

    summer = last_sunday(3) <= utc < last_sunday(10)
    return utc + datetime.timedelta(hours=2 if summer else 1)


# ----------------------------------------------------------------------------- webuntis

class WebUntis(object):
    def __init__(self, server, school, deadline):
        self.url = "https://%s/WebUntis/jsonrpc.do" % server
        self.school = school
        self.deadline = deadline
        self.http = requests.Session()  # keeps the JSESSIONID cookie between calls

    def rpc(self, method, params):
        left = self.deadline - time.monotonic()
        if left <= 0.2:
            raise RuntimeError("time budget used up before %s" % method)
        r = self.http.post(self.url, params={"school": self.school}, timeout=left,
                           headers={"User-Agent": UA},
                           json={"id": "trmnl", "method": method, "params": params,
                                 "jsonrpc": "2.0"})
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError("%s: %s" % (method, data["error"].get("message", data["error"])))
        return data["result"]

    def timetable(self, student_id, start, end):
        fields = ["id", "name", "longname"]
        return self.rpc("getTimetable", {"options": {
            "element": {"id": student_id, "type": 5},
            "startDate": int(start.strftime("%Y%m%d")),
            "endDate": int(end.strftime("%Y%m%d")),
            "showInfo": True, "showSubstText": True, "showLsText": True,
            "showStudentgroup": True,
            "roomFields": fields, "subjectFields": fields, "teacherFields": fields,
        }})


# ----------------------------------------------------------------------------- shaping

def hhmm(t):
    t = int(t)
    return "%d:%02d" % (t // 100, t % 100)


def names(items):
    """'REIT', or 'BAUER statt OLIWA' when the entry carries its original (orgname)."""
    out = []
    for it in items or []:
        n = it.get("name") or ""
        org = it.get("orgname")
        if org and org != n:
            n = "%s statt %s" % (n or "-", org)
        if n:
            out.append(n)
    return ", ".join(out)


def lesson(p):
    code = p.get("code", "")
    subject = names(p.get("su"))
    changed = code == "irregular" or any(
        it.get("orgname") for k in ("su", "ro", "te") for it in p.get(k) or [])
    if not subject:
        # a school event (Wandertag etc.): no subject, the description is in lstext
        subject, changed = (p.get("lstext") or "Veranstaltung").strip(), False
    notes = [p.get(k) for k in ("substText", "info", "lstext")]
    notes = [n.strip() for n in notes if n and n.strip() and n.strip() != subject]
    return {
        "start": hhmm(p["startTime"]),
        "end": hhmm(p["endTime"]),
        "subject": subject,
        "room": names(p.get("ro")),
        "teacher": names(p.get("te")),
        "note": "; ".join(dict.fromkeys(notes)),
        "cancelled": code == "cancelled",
        "changed": changed and code != "cancelled",
    }


def pick_days(periods, now, count=2):
    by_date = {}
    for p in periods:
        by_date.setdefault(int(p["date"]), []).append(p)
    first = now.date() if now.hour < SWITCH_HOUR else now.date() + datetime.timedelta(days=1)
    days = []
    for key in sorted(by_date):
        d = datetime.date(key // 10000, key // 100 % 100, key % 100)
        if d < first:
            continue
        ps = sorted(by_date[key], key=lambda p: (int(p["startTime"]), names(p.get("su"))))
        lessons = [lesson(p) for p in ps]
        # compare the raw HHMM ints: max() over the "9:45"-style strings picked 9:45
        # over 12:50 (caught by the first test run against real data)
        live = [p for p in ps if p.get("code") != "cancelled"]
        days.append({
            "label": "%s %s" % (DAY_NAMES[d.weekday()], d.strftime("%d.%m.")),
            "relative": {0: "Heute", 1: "Morgen"}.get((d - now.date()).days, ""),
            "ends": hhmm(max(int(p["endTime"]) for p in live)) if live else "frei",
            "lessons": lessons,
        })
        if len(days) == count:
            break
    return days


# ----------------------------------------------------------------------------- entry

def run(input):
    started = time.monotonic()
    now = vienna_now()
    out = {"updated": now.strftime("%H:%M"), "title": field(input, "title") or "Stundenplan",
           "days": [], "error": ""}
    need = ["server", "school", "username", "password", "student_id"]
    cfg = {k: field(input, k) for k in need}
    missing = [k for k in need if not cfg[k]]
    if missing:
        out["error"] = "Formularfelder fehlen: " + ", ".join(missing)
        return out

    wu = WebUntis(cfg["server"], cfg["school"], started + DEADLINE_S)
    try:
        wu.rpc("authenticate", {"user": cfg["username"], "password": cfg["password"],
                                "client": UA})
        try:
            periods = wu.timetable(int(cfg["student_id"]), now.date(),
                                   now.date() + datetime.timedelta(days=LOOKAHEAD_DAYS))
        finally:
            try:
                wu.rpc("logout", {})
            except Exception:
                pass
        out["days"] = pick_days(periods, now)
    except Exception as e:
        # show it on the screen rather than failing the plugin; the password never
        # appears here, WebUntis errors only name the method and the reason
        out["error"] = "WebUntis: %s" % e
    out["took_ms"] = int((time.monotonic() - started) * 1000)
    return out
