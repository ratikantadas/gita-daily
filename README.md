# Every day with Bhagavad Gita — Instagram auto-posting

Posts one Bhagavad-gītā As It Is poster to Instagram every day at 6:30 AM IST, in order
from 1.1 to 18.78 (657 posts; long verses go out as a 2-image carousel).
Runs free on GitHub Actions. Do the setup once on a computer (about 30–40 minutes).

---------------------------------------------------------------------------------------
## Part A — Instagram account (5 min)

1. In the Instagram app: Settings → Account type and tools → **Switch to professional account**
   (Creator or Business). Skip if already done.
2. Link it to a **Facebook Page**: Instagram → Edit profile → Page → connect a Page
   (create a simple Page, e.g. "Ratikanta Das", if you don't have one).

## Part B — GitHub repository (15 min)

1. Create a free account at github.com (if you don't have one).
2. Click **+ → New repository**. Name: `gita-daily`. Select **Public** (Instagram must be able
   to download the images). Click **Create repository**.
3. Click **uploading an existing file**. Drag in everything from this folder:
   `post.py`, `schedule.json`, `posted.json`, `README.md`, and the `posters` folder.
   Commit.
   - The `.github` folder is hidden on some computers. If it doesn't upload, use
     **Add file → Create new file**, type the name `.github/workflows/post.yml`,
     paste the contents of post.yml, and commit.
4. Open the `posters` folder in GitHub → **Add file → Upload files** → drag in all JPGs from
   `Gita_Chapter_01.zip` (unzip first). Commit. Repeat for chapters 02 … 18
   (one chapter per upload; each is under 100 files).

## Part C — Instagram access token (15 min)

1. Go to **developers.facebook.com** → log in with the Facebook account that manages the Page
   → **My Apps → Create App** → choose "Other" → type **Business** → name it "Gita Daily".
2. In the app dashboard, add the product **Instagram** (Instagram API with Facebook login).
3. Open **Tools → Graph API Explorer**:
   - Meta App: *Gita Daily*. User or Page: *Get User Access Token*.
   - Tick permissions: `instagram_basic`, `instagram_content_publish`, `pages_show_list`,
     `pages_read_engagement`, `business_management`. Click **Generate Access Token** and allow.
4. Make it long-lived: click the (i) next to the token → **Open in Access Token Tool** →
   **Extend Access Token** → copy the new (60-day) token. Paste it back into Graph API Explorer.
5. In Graph API Explorer run: `me/accounts` → find your Page → copy its **access_token**
   (this Page token does not expire) and its **id**.
6. Paste the Page token in the token box and run:
   `<PAGE_ID>?fields=instagram_business_account` → copy the `instagram_business_account.id`.
   This is your **IG_USER_ID**.

## Part D — Connect and test (5 min)

1. In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**:
   - `IG_USER_ID` = the number from C6
   - `IG_ACCESS_TOKEN` = the Page token from C5
2. **Actions** tab → enable workflows if asked → **Daily Gita post** → **Run workflow**
   (leave "Test only" ticked). It should end green with
   `DRY RUN OK - token works for @ratikantadas.official`.
3. To post 1.1 right away: Run workflow again with "Test only" **unticked**.
   After that it posts automatically every day at 6:30 AM IST.

---------------------------------------------------------------------------------------
## Good to know
- Progress is kept in `posted.json`. If a day is missed, the next run posts the next verse —
  nothing is skipped or posted twice.
- To pause: Actions → Daily Gita post → "…" → **Disable workflow**. Enable to resume.
- To change the time: edit the `cron` line in `.github/workflows/post.yml`
  (UTC time; 6:30 AM IST = `0 1 * * *`, 7:00 PM IST = `30 13 * * *`).
- GitHub may run scheduled jobs 5–30 minutes late at busy times. That's normal.
- If a run fails with "deprecated version", change `GRAPH_VERSION` (e.g. to v24.0) by adding a
  repository **variable** or editing the default in post.py.
- Never paste the token anywhere public — only in GitHub Secrets.
