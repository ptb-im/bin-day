#!/usr/bin/env python3
"""
Scrapes the South Lanarkshire bin collection page for a given address,
works out which day(s) this week's featured bin(s) fall on, and creates
a TickTick task (with a reminder) for each.

Environment variables required (set as GitHub Actions secrets):
  BIN_PAGE_URL          e.g. https://www.southlanarkshire.gov.uk/directory_record/574625/craigwell_avenue_cambuslang
  TICKTICK_ACCESS_TOKEN   from get_ticktick_refresh_token.py (TickTick issues a single
                          long-lived access token, ~180 days, rather than a refresh token -
                          re-run that script periodically to get a fresh one)
  TICKTICK_PROJECT_ID   (optional - defaults to your first TickTick project/list)
"""

import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

BIN_PAGE_URL = os.environ["BIN_PAGE_URL"]
TICKTICK_ACCESS_TOKEN = os.environ["TICKTICK_ACCESS_TOKEN"]
TICKTICK_PROJECT_ID = os.environ.get("TICKTICK_PROJECT_ID")  # optional

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def scrape_bin_info():
    resp = requests.get(BIN_PAGE_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # The bin info lives inside <div class="bin-snip">
    bin_snip = soup.find("div", class_="bin-snip")
    if not bin_snip:
        raise RuntimeError("Could not find the 'bin-snip' section on the page")

    snip_text = bin_snip.get_text(" ", strip=True)

    # 1. Get the Monday date of "This week's collection: Monday DD Month YYYY to Friday DD Month YYYY"
    m = re.search(r"Monday (\d{1,2} \w+ \d{4}) to Friday (\d{1,2} \w+ \d{4})", snip_text)
    if not m:
        raise RuntimeError("Could not find the collection week's date range")
    week_monday = datetime.strptime(m.group(1), "%d %B %Y").date()

    # 2. Get every featured bin this week - each is an <li> containing an <h4><a title="...">
    bin_names = []
    for li in bin_snip.find_all("li"):
        a = li.find("a")
        if a:
            name = (a.get("title") or a.get_text(strip=True)).strip()
            if name:
                bin_names.append(name)

    if not bin_names:
        raise RuntimeError("Found the bin-snip section but no bin types inside it")

    # 3. Cross-reference the schedule table (elsewhere on the page) to find which
    #    weekday each bin type is collected on.
    schedule = {}  # label (lowercase) -> weekday name
    table = soup.find("table")
    if table:
        for row in table.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if not th or not td:
                continue
            label = th.get_text(" ", strip=True)
            value = td.get_text(" ", strip=True)
            for wd in WEEKDAYS:
                if wd.lower() in value.lower():
                    schedule[label.lower()] = wd
                    break

    results = []  # list of (bin_name, date)
    for bin_name in bin_names:
        bin_words = set(re.findall(r"[a-zA-Z]+", bin_name.lower()))
        weekday_name = None
        for label, wd in schedule.items():
            label_words = set(re.findall(r"[a-zA-Z]+", label))
            if label_words & bin_words:
                weekday_name = wd
                break
        if weekday_name:
            offset = WEEKDAYS.index(weekday_name)
            collection_date = week_monday + timedelta(days=offset)
        else:
            print(f"Warning: could not match a weekday for '{bin_name}', defaulting to Monday", file=sys.stderr)
            collection_date = week_monday
        results.append((bin_name, collection_date))

    return results


def short_bin_name(full_name):
    """Turn e.g. 'Black/green bin - non-recyclable waste' into 'Black/green bin'."""
    name = full_name.split(" - ")[0].strip()
    if "bin" not in name.lower():
        name = f"{name} bin"
    return name


def join_bin_names(names):
    if len(names) == 1:
        return names[0]
    return " and ".join(names)  # max 2 bins per week for this address


def create_ticktick_task(access_token, project_id, title, collection_date):
    # Fire the reminder the evening before collection, at 22:00 (10pm) UK time.
    # Built with zoneinfo so it correctly accounts for BST/GMT - a naive
    # "+0000" offset was being read as literal UTC, which showed up an hour
    # off (11pm) during British Summer Time.
    from zoneinfo import ZoneInfo

    notify_date = collection_date - timedelta(days=1)
    local_dt = datetime(notify_date.year, notify_date.month, notify_date.day, 22, 0, 0,
                         tzinfo=ZoneInfo("Europe/London"))
    utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
    due_date_str = utc_dt.strftime("%Y-%m-%dT%H:%M:%S+0000")

    payload = {
        "title": title,
        "dueDate": due_date_str,
        "isAllDay": False,
        "timeZone": "Europe/London",
        "reminders": ["TRIGGER:PT0S"],  # remind exactly at the due time (22:00 local)
        "priority": 5,  # 0=None, 1=Low, 3=Medium, 5=High
    }
    if project_id:
        payload["projectId"] = project_id  # omit entirely to default to your Inbox

    resp = requests.post(
        "https://api.ticktick.com/open/v1/task",
        headers={"Authorization": f"Bearer {access_token}"},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    bins = scrape_bin_info()

    # Group bins by date, in case several bin types fall on the same day -
    # that way you get one task per collection day, not one per bin type.
    by_date = defaultdict(list)
    for bin_name, collection_date in bins:
        by_date[collection_date].append(bin_name)

    for collection_date, names in by_date.items():
        print(f"{collection_date.strftime('%A %d %B %Y')}: {', '.join(names)}")

    access_token = TICKTICK_ACCESS_TOKEN

    for collection_date, names in by_date.items():
        short_names = [short_bin_name(n) for n in names]
        title = f"Bin day - {join_bin_names(short_names)}"
        task = create_ticktick_task(access_token, TICKTICK_PROJECT_ID, title, collection_date)
        print(f"Created TickTick task: {task.get('id')} ({title})")


if __name__ == "__main__":
    main()
