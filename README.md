# Bin day → TickTick reminder

Every Monday morning, this scrapes your South Lanarkshire bin collection page
and adds a TickTick task (with a reminder) for the exact day your bin is
collected that week.

## How it works
1. `scrape_and_add_task.py` fetches the page, finds "This week's collection"
   and the featured bin type(s), then cross-references the schedule table to
   work out which weekday (e.g. Tuesday) each bin type is collected on.
2. It uses a TickTick access token to create a task titled e.g.
   "Bin day: Black/green bin - non-recyclable waste" due on that date, with
   a reminder.
3. GitHub Actions runs this automatically every Monday at 7am (UK time-ish).

## One-time setup

### 1. Register a TickTick app
- Go to https://developer.ticktick.com/manage and create an app.
- **App Service URL**: any URL is fine (e.g. a GitHub repo link) - it's just a
  required field, not something TickTick actually calls.
- **OAuth Redirect URL**: `http://localhost:8000/callback`
- Copy the **Client ID** and **Client Secret**.

### 2. Get an access token (run locally, once)
```bash
pip install requests
```
Edit `get_ticktick_refresh_token.py`, paste in your Client ID and Client
Secret, then run:
```bash
python get_ticktick_refresh_token.py
```
This opens your browser, you approve access, and it prints a
`TICKTICK_ACCESS_TOKEN`. Copy it.

**Note:** TickTick doesn't issue a refresh token for this flow - instead you
get one access token valid for around 180 days. There's no way to silently
renew it in the background, so roughly every 6 months you'll need to re-run
this script and update the GitHub secret with the new token. (You'll notice
it's time to do this if the Action starts failing with an auth error.)

### 3. Create a GitHub repo and push these files
```bash
git init
git add .
git commit -m "Bin day reminder"
git branch -M main
git remote add origin <your-new-github-repo-url>
git push -u origin main
```

### 4. Add repository secrets
In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**.
Add:
- `TICKTICK_ACCESS_TOKEN`
- `TICKTICK_PROJECT_ID` *(optional — if you want the task to land in a specific
  TickTick list rather than your default list; get an ID by calling
  `GET https://api.ticktick.com/open/v1/project` with your access token)*

### 5. Test it
Go to the **Actions** tab in your repo → "Weekly bin reminder" → **Run workflow**
to trigger it manually and check a task appears in TickTick. After that, it
runs automatically every Monday.

## Notes / things to double check
- The scraper matches the bin type name against the schedule table by shared
  keywords (e.g. "black", "green") — this should work for South Lanarkshire's
  page layout, but if the council ever redesigns the page, the script may need
  small tweaks. Run it manually first to confirm the printed output looks right.
- If your address URL is different from the one you gave me, just change
  `BIN_PAGE_URL` in the workflow file.
- Set a calendar reminder for yourself every ~6 months to refresh the
  `TICKTICK_ACCESS_TOKEN`, since it will silently stop working once it expires.
