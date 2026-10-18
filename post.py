"""Post the next Bhagavad-gita poster (photo) to Instagram accounts - once per day.

Runs inside GitHub Actions. Each account needs two repository secrets (empty = skipped):
  temple:          IG_USER_ID            + IG_ACCESS_TOKEN
  Ratikanta Das:   IG_USER_ID_RATIKANTA  + IG_ACCESS_TOKEN_RATIKANTA
  GITA For YOUth:  IG_USER_ID_GFY        + IG_ACCESS_TOKEN_GFY
LinkedIn personal profile:  LI_ACCESS_TOKEN  (60-day token from LinkedIn's token generator)
Each account keeps its own progress in posted.json. A second run on the same day
(IST) does nothing unless FORCE is set, so extra triggers never double-post.
"""
import json, os, re, sys, time, urllib.parse, urllib.request, urllib.error, datetime

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
    ("linkedin", "li", "LI_ACCESS_TOKEN", "LI_ACCESS_TOKEN"),
]
LI_VERSION = os.environ.get("LI_VERSION") or "202508"
WA_LINK = "https://chat.whatsapp.com/KlP6IdSn2dE2ZZ3wHsaXau"


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


# ---------------- LinkedIn ----------------
def li_req(token, method, url, body=None, raw=None, ctype="application/json"):
    headers = {"Authorization": f"Bearer {token}", "LinkedIn-Version": LI_VERSION,
               "X-Restli-Protocol-Version": "2.0.0"}
    data = None
    if body is not None:
        data = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
    elif raw is not None:
        data = raw; headers["Content-Type"] = ctype
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            txt = r.read().decode() or "{}"
            return json.loads(txt), dict(r.headers)
    except urllib.error.HTTPError as e:
        raise ApiError(f"LinkedIn {url.split('?')[0]}: {e.code} {e.read().decode(errors='replace')}")


def li_who(token):
    me, _ = li_req(token, "GET", "https://api.linkedin.com/v2/userinfo")
    return f"urn:li:person:{me['sub']}", me.get("name", "?")


def li_text(caption):
    caption = caption.replace("(link in bio / scan QR on post)", WA_LINK)
    out = []
    for tok in re.split(r"(#[A-Za-z0-9_]+)", caption):
        if tok.startswith("#") and len(tok) > 1:
            out.append("{hashtag|\\#|" + tok[1:] + "}")
        else:
            out.append(re.sub(r"([\\|{}@\[\]()<>*_~#])", r"\\\1", tok))
    return "".join(out)


def publish_li(owner, token, item):
    ids = []
    for f in item["files"]:
        init, _ = li_req(token, "POST", "https://api.linkedin.com/rest/images?action=initializeUpload",
                         body={"initializeUploadRequest": {"owner": owner}})
        v = init["value"]
        li_req(token, "PUT", v["uploadUrl"], raw=open(os.path.join("posters", f), "rb").read(),
               ctype="image/jpeg")
        ids.append(v["image"])
    content = ({"media": {"id": ids[0]}} if len(ids) == 1
               else {"multiImage": {"images": [{"id": i} for i in ids]}})
    body = {"author": owner, "commentary": li_text(item["caption"]), "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                             "thirdPartyDistributionChannels": []},
            "content": content, "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False}
    _, hdr = li_req(token, "POST", "https://api.linkedin.com/rest/posts", body=body)
    return hdr.get("x-restli-id") or hdr.get("X-RestLi-Id") or "ok"


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
            if platform == "li":
                target, name = li_who(token)
                who = f"LinkedIn {name}"
            else:
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
            mid = (publish_li if platform == "li" else publish_ig)(target, token, nxt)
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
