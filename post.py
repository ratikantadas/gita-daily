"""Post the next Bhagavad-gita poster (photo) to Instagram accounts - once per day.

Runs inside GitHub Actions. Each account needs two repository secrets (empty = skipped):
  temple:          IG_USER_ID            + IG_ACCESS_TOKEN
  Ratikanta Das:   IG_USER_ID_RATIKANTA  + IG_ACCESS_TOKEN_RATIKANTA
  GITA For YOUth:  IG_USER_ID_GFY        + IG_ACCESS_TOKEN_GFY
Each account keeps its own progress in posted.json. A second run on the same day
(IST) does nothing unless FORCE is set, so extra triggers never double-post.
"""
import json, os, sys, time, urllib.parse, urllib.request, urllib.error, datetime

GRAPH = "https://graph.facebook.com/" + (os.environ.get("GRAPH_VERSION") or "v23.0")
REPO = os.environ.get("GITHUB_REPOSITORY", "")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
DRY = os.environ.get("DRY_RUN", "false").lower() == "true"
FORCE = os.environ.get("FORCE", "false").lower() == "true"
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
TODAY = datetime.datetime.now(IST).date()


def posted_today(hist):
    if not hist or "posted_at" not in hist[-1]:
        return False
    t = datetime.datetime.fromisoformat(hist[-1]["posted_at"].replace("Z", "+00:00"))
    return t.astimezone(IST).date() == TODAY
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/posters/"

DESTINATIONS = [  # (progress key, platform, id env, token env)
    ("main", "ig", "IG_USER_ID", "IG_ACCESS_TOKEN"),
    ("ratikanta", "ig", "IG_USER_ID_RATIKANTA", "IG_ACCESS_TOKEN_RATIKANTA"),
    ("gfy", "ig", "IG_USER_ID_GFY", "IG_ACCESS_TOKEN_GFY"),
]


class ApiError(Exception):
    pass


def call(token, method, path, **params):
    params["access_token"] = token
    data = urllib.parse.urlencode(params).encode()
    url = f"{GRAPH}/{path}"
    req = (urllib.request.Request(url + "?" + data.decode()) if method == "GET"
           else urllib.request.Request(url, data=data, method="POST"))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise ApiError(f"{path}: {e.code} {e.read().decode(errors='replace')}")


def wait_ready(token, cid):
    for _ in range(30):
        st = call(token, "GET", cid, fields="status_code").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise ApiError(f"container {cid} failed: {st}")
        time.sleep(5)
    raise ApiError(f"container {cid} not ready in time")


def url_ok(u):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, method="HEAD"), timeout=30) as r:
            return r.status == 200
    except Exception:
        return False


def image_urls(item):
    urls = [BASE + urllib.parse.quote(f) for f in item["files"]]
    for u in urls:
        if not url_ok(u):
            raise ApiError(f"image not reachable: {u}")
    return urls


def publish_ig(ig, token, item):
    urls = image_urls(item)
    if len(urls) == 1:
        cid = call(token, "POST", f"{ig}/media", image_url=urls[0], caption=item["caption"])["id"]
    else:
        kids = [call(token, "POST", f"{ig}/media", image_url=u, is_carousel_item="true")["id"] for u in urls]
        for k in kids:
            wait_ready(token, k)
        cid = call(token, "POST", f"{ig}/media", media_type="CAROUSEL",
                   children=",".join(kids), caption=item["caption"])["id"]
    wait_ready(token, cid)
    return call(token, "POST", f"{ig}/media_publish", creation_id=cid)["id"]


def main():
    queue = json.load(open("schedule.json", encoding="utf-8"))
    posted = json.load(open("posted.json", encoding="utf-8"))
    if isinstance(posted, list):          # old single-account format
        posted = {"main": posted}
    failures, active = [], 0
    for key, platform, id_env, tok_env in DESTINATIONS:
        target, token = os.environ.get(id_env, "").strip(), os.environ.get(tok_env, "").strip()
        if not target or not token:
            print(f"[{key}] not configured - skipped")
            continue
        active += 1
        try:
            who = "@" + call(token, "GET", target, fields="username").get("username", "?")
            hist = posted.setdefault(key, [])
            done = {p["verse"] for p in hist}
            nxt = next((q for q in queue if q["verse"] not in done), None)
            if not nxt:
                print(f"[{key}] {who}: all verses posted. Hare Krishna!")
                continue
            if posted_today(hist) and not FORCE and not DRY:
                print(f"[{key}] {who}: already posted today ({hist[-1]['verse']}) - skipped")
                continue
            if DRY:
                print(f"[{key}] DRY RUN OK - token works for {who}; next verse {nxt['verse']}")
                continue
            mid = publish_ig(target, token, nxt)
            hist.append({"verse": nxt["verse"], "media_id": mid,
                         "posted_at": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"})
            print(f"[{key}] {who}: posted {nxt['verse']} -> {mid} ({len(hist)}/{len(queue)})")
        except ApiError as e:
            print(f"[{key}] FAILED: {e}")
            failures.append(key)
    json.dump(posted, open("posted.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not active:
        sys.exit("Nothing configured (check repository secrets).")
    if failures:
        sys.exit(f"Failed for: {', '.join(failures)} (the others were posted).")


if __name__ == "__main__":
    main()
