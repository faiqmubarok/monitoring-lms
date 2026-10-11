import json
from datetime import datetime, timezone, timedelta
from src.moodle_api import MoodleClient
from src.quiz_schedule import parse_class_day, compute_expected_dates
from src import config

WIB = timezone(timedelta(hours=7))

client = MoodleClient()
sections = client.get_course_contents(328)
client.close()

quizzes = []
for s in sections:
    for m in s.get("modules", []):
        if m.get("modname") == "quiz":
            cdata = {}
            try:
                cdata = json.loads(m.get("customdata", "{}"))
            except Exception:
                pass
            to = int(cdata.get("timeopen", 0)) or None
            tc = int(cdata.get("timeclose", 0)) or None
            open_str  = datetime.fromtimestamp(to,  tz=WIB).strftime("%a %d %b %Y %H:%M") if to else None
            close_str = datetime.fromtimestamp(tc, tz=WIB).strftime("%a %d %b %Y %H:%M") if tc else None
            quizzes.append({"name": m.get("name"), "section": s.get("section"), "timeopen": to, "timeclose": tc, "open_wib": open_str, "close_wib": close_str})

print("=== QUIZ LIST (Course 328, 3 pertama) ===")
for q in quizzes[:3]:
    print(q["name"], "| open:", q["open_wib"], "| close:", q["close_wib"])

print()
p1 = quizzes[0] if quizzes else None
class_day = parse_class_day("Rabu19:00:00-21:00:00")
exp_open, exp_close = compute_expected_dates(class_day, 1, config.SEMESTER_START_WEEK)
print("Class day:", class_day, "(2=Rabu/Wed)")
print("Expected open :", exp_open.date())
print("Expected close:", exp_close.date())
if p1 and p1["timeopen"]:
    print("Actual   open :", datetime.fromtimestamp(p1["timeopen"],  tz=WIB).date())
    print("Actual   close:", datetime.fromtimestamp(p1["timeclose"], tz=WIB).date())
else:
    print("P1 timeopen/timeclose: None")
