"""Post the next Bhagavad-gita poster to Instagram (Instagram Graph API).

Runs inside GitHub Actions. Needs two repository secrets:
  IG_USER_ID       - the Instagram Business/Creator account ID
  IG_ACCESS_TOKEN  - a long-lived (non-expiring Page) access token
Posters are served from this public repo via raw.githubusercontent.com.
"""
import json, os, sys, time, urllib.parse, urllib.request, urllib.error, datetime

GRAPH = "https://graph.facebook.com/" + os.environ.get("GRAPH_VERSION", "v23.0")
IG = os.environ.get("IG_USER_ID", "").strip()
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "").strip()
REPO = os.environ.get("GITHUB_REPOSITORY", "")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
DRY = os.environ.get("DRY_RUN", "false").lower() == "true"
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/posters/"


def call(method, path, **params):
    params["access_token"] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    url = f"{GRAPH}/{path}"
    if method == "GET":
        req = urllib.request.Request(url + "?" + data.decode())
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        sys.exit(f"Instagram API error on {path}: {e.code} {body}")


def wait_ready(cid):
    for _ in range(30):
        st = call("GET", cid, fields="status_code").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            sys.exit(f"Container {cid} failed: {st}")
        time.sleep(5)
    sys.exit(f"Container {cid} not ready in time")


def url_ok(u):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, method="HEAD"), timeout=30) as r:
            return r.status == 200
    except Exception:
        return False


def main():
    if not IG or not TOKEN:
        sys.exit("Missing IG_USER_ID or IG_ACCESS_TOKEN secret.")
    queue = json.load(open("schedule.json", encoding="utf-8"))
    posted = json.load(open("posted.json", encoding="utf-8"))
    done = {p["verse"] for p in posted}
    nxt = next((q for q in queue if q["verse"] not in done), None)
    if not nxt:
        print("All verses already posted. Hare Krishna!")
        return
    urls = [BASE + urllib.parse.quote(f) for f in nxt["files"]]
    print("Next verse:", nxt["verse"], urls)
    for u in urls:
        if not url_ok(u):
            sys.exit(f"Image not reachable (is the repo public and the file uploaded to posters/?): {u}")

    if DRY:
        me = call("GET", IG, fields="username,media_count")
        print(f"DRY RUN OK - token works for @{me.get('username')}; images reachable. Nothing posted.")
        return

    if len(urls) == 1:
        cid = call("POST", f"{IG}/media", image_url=urls[0], caption=nxt["caption"])["id"]
    else:
        kids = [call("POST", f"{IG}/media", image_url=u, is_carousel_item="true")["id"] for u in urls]
        for k in kids:
            wait_ready(k)
        cid = call("POST", f"{IG}/media", media_type="CAROUSEL", children=",".join(kids), caption=nxt["caption"])["id"]
    wait_ready(cid)
    mid = call("POST", f"{IG}/media_publish", creation_id=cid)["id"]
    posted.append({"verse": nxt["verse"], "media_id": mid,
                   "posted_at": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"})
    json.dump(posted, open("posted.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Posted {nxt['verse']} -> media {mid} ({len(posted)}/{len(queue)})")


if __name__ == "__main__":
    main()
