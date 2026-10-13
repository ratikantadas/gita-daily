"""Post the next Bhagavad-gita poster to one or more Instagram accounts.

Runs inside GitHub Actions. Each account needs two repository secrets:
  temple (existing):  IG_USER_ID            + IG_ACCESS_TOKEN
  Ratikanta Das:      IG_USER_ID_RATIKANTA  + IG_ACCESS_TOKEN_RATIKANTA
  GITA For YOUth:     IG_USER_ID_GFY        + IG_ACCESS_TOKEN_GFY
Accounts whose secrets are empty are skipped. Each account keeps its own
progress in posted.json, so a newly added account starts from 1.1.
"""
import json, os, sys, time, urllib.parse, urllib.request, urllib.error, datetime

GRAPH = "https://graph.facebook.com/" + (os.environ.get("GRAPH_VERSION") or "v23.0")
REPO = os.environ.get("GITHUB_REPOSITORY", "")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
DRY = os.environ.get("DRY_RUN", "false").lower() == "true"
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/posters/"

ACCOUNTS = [  # (key in posted.json, user-id env, token env)
    ("main", "IG_USER_ID", "IG_ACCESS_TOKEN"),
    ("ratikanta", "IG_USER_ID_RATIKANTA", "IG_ACCESS_TOKEN_RATIKANTA"),
    ("gfy", "IG_USER_ID_GFY", "IG_ACCESS_TOKEN_GFY"),
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


def publish(ig, token, item):
    urls = [BASE + urllib.parse.quote(f) for f in item["files"]]
    for u in urls:
        if not url_ok(u):
            raise ApiError(f"image not reachable: {u}")
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
    for key, id_env, tok_env in ACCOUNTS:
        ig, token = os.environ.get(id_env, "").strip(), os.environ.get(tok_env, "").strip()
        if not ig or not token:
            print(f"[{key}] not configured - skipped")
            continue
        active += 1
        try:
            who = call(token, "GET", ig, fields="username").get("username")
            hist = posted.setdefault(key, [])
            done = {p["verse"] for p in hist}
            nxt = next((q for q in queue if q["verse"] not in done), None)
            if not nxt:
                print(f"[{key}] @{who}: all verses posted. Hare Krishna!")
                continue
            if DRY:
                print(f"[{key}] DRY RUN OK - token works for @{who}; next verse {nxt['verse']}")
                continue
            mid = publish(ig, token, nxt)
            hist.append({"verse": nxt["verse"], "media_id": mid,
                         "posted_at": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"})
            print(f"[{key}] @{who}: posted {nxt['verse']} -> {mid} ({len(hist)}/{len(queue)})")
        except ApiError as e:
            print(f"[{key}] FAILED: {e}")
            failures.append(key)
    json.dump(posted, open("posted.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not active:
        sys.exit("No Instagram account configured (check repository secrets).")
    if failures:
        sys.exit(f"Failed for: {', '.join(failures)} (other accounts were posted).")


if __name__ == "__main__":
    main()
