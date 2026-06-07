import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urljoin
import re
import hashlib

BASE = "https://borasps.se"
YEAR = 2026
MONTHS = range(1, 13)
TZ = ZoneInfo("Europe/Stockholm")

cal = Calendar()
seen = set()

months_sv = {
    "januari": 1, "februari": 2, "mars": 3, "april": 4,
    "maj": 5, "juni": 6, "juli": 7, "augusti": 8,
    "september": 9, "oktober": 10, "november": 11, "december": 12
}

def parse_date(text):
    m = re.search(
        r"(\d{1,2})\s+([A-Za-zÅÄÖåäö]+)\s+(\d{4}),\s*(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})",
        text
    )

    if m:
        day, month_name, year, start_time, end_time = m.groups()
    else:
        m = re.search(
            r"(\d{1,2})\s+([A-Za-zÅÄÖåäö]+)\s+(\d{4}),\s*(\d{2}:\d{2})",
            text
        )

        if not m:
            return None, None

        day, month_name, year, start_time = m.groups()
        end_time = None

    month = months_sv.get(month_name.lower())

    if not month:
        return None, None

    start = datetime.strptime(
        f"{year}-{month}-{day} {start_time}",
        "%Y-%m-%d %H:%M"
    ).replace(tzinfo=TZ)

    if end_time:
        end = datetime.strptime(
            f"{year}-{month}-{day} {end_time}",
            "%Y-%m-%d %H:%M"
        ).replace(tzinfo=TZ)
    else:
        end = start + timedelta(hours=2)

    return start, end

def title_from_url(event_url, fallback_title):
    slug = event_url.rstrip("/").split("/")[-1]

    if slug and slug != "-":
        title = slug.replace("-", " ")

        title = title.replace("traening", "träning")
        title = title.replace("soendag", "söndag")
        title = title.replace("oe", "ö")
        title = title.replace("ae", "ä")
        title = title.replace("aa", "å")

        return title.title().replace("Sm ", "SM ").replace("Ipsc", "IPSC")

    title = fallback_title
    title = re.sub(r"^\d{2}:\d{2}\s*", "", title)
    title = title.replace("...", "").strip()

    return title

for month in MONTHS:
    url = f"{BASE}/index.php/kalender/manadskalender/{YEAR}/{month}/-"
    print("Läser:", url)

    html = requests.get(url, timeout=20).text
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if "/kalender/handelsedetaljer/" not in href:
            continue

        event_url = urljoin(BASE, href)

        detail_html = requests.get(event_url, timeout=20).text
        detail_soup = BeautifulSoup(detail_html, "html.parser")
        detail_text = detail_soup.get_text("\n", strip=True)

        start, end = parse_date(detail_text)

        if not start or not end:
            print("Hoppar över, kunde inte tolka datum:", event_url)
            continue

        fallback_title = a.get_text(" ", strip=True)
        title = title_from_url(event_url, fallback_title)

        unique_key = f"{event_url}|{title}|{start.isoformat()}|{end.isoformat()}"

        if unique_key in seen:
            continue

        seen.add(unique_key)

        event = Event()
        event.uid = hashlib.md5(unique_key.encode("utf-8")).hexdigest() + "@borasps-kalender"
        event.name = title
        event.begin = start
        event.end = end
        event.url = event_url
        event.description = f"Källa: {event_url}"

        cal.events.add(event)

with open("borasps-kalender.ics", "w", encoding="utf-8") as f:
    f.writelines(cal)

print(f"Skapade {len(cal.events)} händelser.")
