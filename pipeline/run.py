"""Juniper Resilience live intelligence pipeline (free tier).

Pulls free public sources, turns every item into one event format, tags location
and category, scores severity (1 to 5) and confidence (Admiralty grade), merges
duplicate reports of the same event, and writes:

  docs/data/events.json   current events, read by the dashboard
  docs/data/brief.json    last-24-hour brief (top events by region)
  docs/data/status.json   run log: which sources worked
  docs/data/archive/YYYY-MM.jsonl   every event ever seen, for later analysis

Run:  python pipeline/run.py            (live, needs internet)
      python pipeline/run.py --offline  (uses tests/fixtures, for testing)
"""
import json, re, sys, os, time, hashlib, html, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
REF = ROOT / "pipeline"
UTC = dt.timezone.utc
NOW = dt.datetime.now(UTC)
OFFLINE = "--offline" in sys.argv

# ---------------------------------------------------------------- reference data
COUNTRIES = json.load(open(REF / "countries.json", encoding="utf-8"))
CITIES = json.load(open(REF / "cities.json", encoding="utf-8"))
CMAP = {c["name"]: c for c in COUNTRIES}

ALIASES = {
    "United States": ["united states", "u.s.", "usa", "america", "american", "washington"],
    "United Kingdom": ["united kingdom", "britain", "british", "uk", "england", "scotland", "wales"],
    "UAE": ["uae", "united arab emirates", "emirati", "emirates"],
    "DRC": ["drc", "dr congo", "democratic republic of congo", "democratic republic of the congo", "congo-kinshasa", "congolese"],
    "Congo Republic": ["republic of congo", "congo-brazzaville", "republic of the congo"],
    "Cote d'Ivoire": ["ivory coast", "cote d'ivoire", "côte d'ivoire", "ivorian"],
    "Myanmar": ["myanmar", "burma", "burmese"],
    "Turkey": ["turkey", "türkiye", "turkiye", "turkish"],
    "Czech Republic": ["czech", "czechia"],
    "North Korea": ["north korea", "dprk", "pyongyang", "north korean"],
    "South Korea": ["south korea", "south korean", "seoul"],
    "Palestine": ["palestine", "palestinian", "gaza", "west bank"],
    "CAR": ["central african republic"],
    "Bosnia & Herzegovina": ["bosnia", "bosnian"],
    "Trinidad & Tobago": ["trinidad"],
    "Saudi Arabia": ["saudi"],
    "Sao Tome & Principe": ["sao tome"],
    "Vatican City": ["vatican"],
    "Timor-Leste": ["timor-leste", "east timor"],
    "Cabo Verde": ["cabo verde", "cape verde"],
    "Eswatini": ["eswatini", "swaziland"],
}
DEMONYMS = {
    "Iran": "iranian", "Israel": "israeli", "Russia": "russian", "Ukraine": "ukrainian", "Sudan": "sudanese",
    "South Sudan": "south sudanese", "Pakistan": "pakistani", "Afghanistan": "afghan", "Syria": "syrian",
    "Lebanon": "lebanese", "Iraq": "iraqi", "Yemen": "yemeni", "Mali": "malian", "Nigeria": "nigerian",
    "Niger": "nigerien", "Kenya": "kenyan", "Mexico": "mexican", "Venezuela": "venezuelan", "Haiti": "haitian",
    "China": "chinese", "India": "indian", "Colombia": "colombian", "Ecuador": "ecuadorian", "Peru": "peruvian",
    "Brazil": "brazilian", "Argentina": "argentine", "Chile": "chilean", "Egypt": "egyptian", "Libya": "libyan",
    "Somalia": "somali", "Ethiopia": "ethiopian", "Burkina Faso": "burkinabe", "Bangladesh": "bangladeshi",
    "Philippines": "filipino", "Indonesia": "indonesian", "Thailand": "thai", "Vietnam": "vietnamese",
    "Japan": "japanese", "Germany": "german", "France": "french", "Spain": "spanish", "Italy": "italian",
    "Poland": "polish", "Georgia": "georgian", "Serbia": "serbian", "Belarus": "belarusian", "Kazakhstan": "kazakh",
    "Jordan": "jordanian", "Qatar": "qatari", "Kuwait": "kuwaiti", "Bahrain": "bahraini", "Oman": "omani",
    "Morocco": "moroccan", "Algeria": "algerian", "Tunisia": "tunisian", "Cameroon": "cameroonian",
    "Mozambique": "mozambican", "Uganda": "ugandan", "Tanzania": "tanzanian", "Zimbabwe": "zimbabwean",
    "South Africa": "south african", "Ghana": "ghanaian", "Senegal": "senegalese", "Madagascar": "malagasy",
    "Cuba": "cuban", "Nicaragua": "nicaraguan", "Honduras": "honduran", "Guatemala": "guatemalan",
    "El Salvador": "salvadoran", "Nepal": "nepali", "Sri Lanka": "sri lankan", "Canada": "canadian",
    "Australia": "australian", "Taiwan": "taiwanese", "Azerbaijan": "azerbaijani", "Armenia": "armenian",
    "Chad": "chadian", "Rwanda": "rwandan", "Burundi": "burundian", "Eritrea": "eritrean",
}
LOC_TERMS = []  # (compiled regex, country, city or None)
for c in COUNTRIES:
    n = c["name"]
    terms = {n.lower()} | set(ALIASES.get(n, []))
    if n in DEMONYMS: terms.add(DEMONYMS[n])
    for t in terms:
        if len(t) < 3 and t not in ("uk",): continue
        LOC_TERMS.append((re.compile(r"(?<![\w-])" + re.escape(t) + r"(?![\w-])", re.I), n, None))
for ct in CITIES:
    LOC_TERMS.append((re.compile(r"(?<![\w-])" + re.escape(ct["name"]) + r"(?![\w-])", re.I), ct["country"], ct["name"]))
# Ambiguous names that are usually not the country
AMBIG = {"Georgia": ["georgia state", "atlanta", "georgia, us", "u.s. state of georgia"], "Jordan": ["michael jordan", "jordan river"],
         "Chad": [], "Niger": ["niger delta"], "Guinea": ["papua new guinea", "equatorial guinea", "guinea-bissau"]}

PREP = re.compile(r"(?:\b(?:in|on|near|at|across|into|outside|hit|hits|struck|strikes?|southern|northern|eastern|western|central|south|north|east|west)\s+)$", re.I)

def locate(text):
    """Return (primary country, city, all countries). Prefers the place an event happens in
    (cities, and names after 'in', 'near', 'hit' and similar) over nationality words."""
    low = text.lower(); cand = {}
    for rx, country, cityname in LOC_TERMS:
        m = rx.search(text)
        if not m: continue
        if country in AMBIG and any(a in low for a in AMBIG[country]): continue
        word = m.group(0).lower()
        demonym = word == DEMONYMS.get(country)
        score = 3 if cityname else 0 if demonym else 2
        if PREP.search(text[max(0, m.start() - 14):m.start()]): score += 2
        prev = cand.get(country)
        key = (score, -m.start())
        if not prev or key > prev[0]: cand[country] = (key, cityname or (prev[1] if prev else None))
        elif cityname and not prev[1]: cand[country] = (prev[0], cityname)
    if not cand: return None, None, []
    order = sorted(cand, key=lambda c: cand[c][0], reverse=True)
    return order[0], cand[order[0]][1], order

# ---------------------------------------------------------------- classification
CATS = {
    "conflict":  [r"air ?strikes?", r"missiles?", r"drone (strike|attack)s?", r"shelling", r"artillery", r"offensive", r"clashes", r"troops", r"invasion", r"ceasefire", r"bombard", r"frappes?", r"fighting", r"rocket fire", r"interceptors?", r"military operation"],
    "terrorism": [r"terror", r"suicide bomb", r"\bied\b", r"gunmen", r"jihadist", r"islamic state", r"\bisis\b", r"al[- ]shabaab", r"\bjnim\b", r"boko haram", r"militants? (attack|kill)"],
    "unrest":    [r"protest", r"demonstrat", r"riots?", r"general strike", r"workers'? strike", r"tear gas", r"curfew", r"manifestation", r"manifestaci", r"protesta", r"bloqueo", r"émeute", r"couvre-feu", r"unrest", r"rally"],
    "crime":     [r"shooting", r"homicide", r"murder", r"robbery", r"carjack", r"cartel", r"gangs?", r"kidnap", r"abduct", r"hostage"],
    "political": [r"\bcoup\b", r"martial law", r"state of emergency", r"impeach", r"election (violence|dispute|results?)", r"parliament dissolved", r"resigns?", r"junta", r"sanctions?"],
    "hazard":    [r"earthquake", r"flood", r"cyclone", r"hurricane", r"typhoon", r"wildfire", r"volcan", r"tsunami", r"landslide", r"severe storm", r"heatwave"],
    "health":    [r"outbreak", r"ebola", r"cholera", r"mpox", r"marburg", r"dengue", r"measles", r"epidemic", r"bird flu", r"h5n1"],
    "transport": [r"airport (closed|closure|shut)", r"airspace", r"flights? (cancel|suspend|divert)", r"port (closed|closure)", r"border (closed|closure|crossing)", r"roadblock", r"rail strike", r"grounded"],
    "cyber":     [r"cyber ?attack", r"ransomware", r"data breach", r"\bddos\b", r"hack(ed|ers)", r"internet (shutdown|blackout)"],
}
CAT_RX = {k: re.compile("|".join(v), re.I) for k, v in CATS.items()}
BASE = {"conflict": 3, "terrorism": 4, "unrest": 2, "crime": 2, "political": 3, "hazard": 2, "health": 2, "transport": 2, "cyber": 2, "advisory": 2}
TTL_H = {"conflict": 72, "terrorism": 96, "unrest": 48, "crime": 48, "political": 168, "hazard": 120, "health": 336, "transport": 48, "cyber": 72, "advisory": 720}
ESCALATORS = re.compile(r"state of emergency|curfew|\bcoup\b|airport (closed|shut)|evacuat|martial law|mass casualt|embassy (closed|attacked)", re.I)
DEATHS = re.compile(r"(\d{1,5})\s+(?:people\s+)?(?:killed|dead|deaths|died|killing)", re.I)
WORDNUM = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "dozens": 24, "scores": 40, "hundreds": 200}
WDEATHS = re.compile(r"\b(" + "|".join(WORDNUM) + r")\s+(?:people\s+)?(?:killed|dead)", re.I)

def classify(text, hint=None):
    hits = [(k, len(rx.findall(text))) for k, rx in CAT_RX.items()]
    hits = [h for h in hits if h[1]]
    if hint: return hint
    if not hits: return None
    pri = ["terrorism", "conflict", "political", "unrest", "health", "hazard", "transport", "cyber", "crime"]
    hits.sort(key=lambda h: (-h[1], pri.index(h[0])))
    return hits[0][0]

def deaths_in(text):
    n = [int(x) for x in DEATHS.findall(text)]
    n += [WORDNUM[w.lower()] for w in WDEATHS.findall(text)]
    return max(n) if n else 0

def severity(cat, text, extra=0):
    s = BASE.get(cat, 2) + extra
    d = deaths_in(text)
    if d >= 50: s += 3
    elif d >= 10: s += 2
    elif d >= 1: s += 1
    if ESCALATORS.search(text): s += 1
    return max(1, min(5, s))

# ---------------------------------------------------------------- fetching
def get(url, as_json=False):
    import requests
    r = requests.get(url, timeout=25, headers={"User-Agent": "JuniperResilience-LiveIntel/1.0 (+https://juniperresilience.com)"})
    r.raise_for_status()
    return r.json() if as_json else r.content

def fixture(src):
    p = ROOT / "tests" / "fixtures" / (src["id"] + (".json" if src["type"] in ("usgs", "gdelt", "bluesky") else ".xml"))
    if not p.exists(): return None
    return json.load(open(p, encoding="utf-8")) if p.suffix == ".json" else p.read_bytes()

def parse_time(entry):
    for k in ("published_parsed", "updated_parsed"):
        t = entry.get(k)
        if t: return dt.datetime(*t[:6], tzinfo=UTC)
    return NOW

def clean(t):
    t = html.unescape(re.sub(r"<[^>]+>", " ", t or ""))
    return re.sub(r"\s+", " ", t).strip()

def item(*a, **k):
    try: return _item(*a, **k)
    except Exception: return None

def _item(src, title, summary, url, when, cat=None, extra_sev=0, lat=None, lon=None, country=None, city=None, sev=None):
    text = f"{title}. {summary}"
    if not country:
        country, city2, _ = locate(text)
        city = city or city2
    if country not in CMAP: return None
    cat = cat or classify(text, src.get("category_hint"))
    if not cat: return None
    # Copyright: for news and social sources keep only the headline and link, never article text.
    keep_summary = summary[:400] if src["tier"] == "A" else ""
    return {"title": title[:240], "summary": keep_summary, "url": url, "time": when.isoformat(), "source": src["name"],
            "source_id": src["id"], "tier": src["tier"], "category": cat, "country": country, "city": city,
            "lat": lat, "lon": lon, "severity": sev or severity(cat, text, extra_sev)}

def from_rss(src, raw):
    import feedparser
    out = []
    for e in feedparser.parse(raw).entries:
        it = item(src, clean(e.get("title")), clean(e.get("summary", e.get("description", ""))), e.get("link"), parse_time(e))
        if it: out.append(it)
    return out

def from_state(src, raw):
    import feedparser
    out = []
    for e in feedparser.parse(raw).entries:
        title = clean(e.get("title")); when = parse_time(e)
        if (NOW - when).days > 14: continue          # only recent changes, not the standing list
        m = re.match(r"(.+?)\s*-\s*Level (\d)", title)
        if not m: continue
        lvl = int(m.group(2)); name = m.group(1).strip()
        country, city, _ = locate(name)
        if not country: continue
        out.append(item(src, title, clean(e.get("summary", ""))[:400], e.get("link"), when, cat="advisory", country=country, sev={1: 1, 2: 2, 3: 4, 4: 5}[lvl]))
    return [o for o in out if o]

def from_fcdo(src, raw):
    import feedparser
    out = []
    for e in feedparser.parse(raw).entries:
        title = clean(e.get("title")); summ = clean(e.get("summary", ""))
        country, city, _ = locate(title.replace("travel advice", ""))
        if not country: continue
        sev = 4 if re.search(r"against all travel", summ, re.I) else 3 if re.search(r"all but essential", summ, re.I) else 2
        it = item(src, title, summ, e.get("link"), parse_time(e), cat="advisory", country=country, sev=sev)
        if it: out.append(it)
    return out

def from_usgs(src, data):
    out = []
    for f in data.get("features", []):
        p = f["properties"]; lon, lat = f["geometry"]["coordinates"][:2]
        mag = p.get("mag") or 0; place = p.get("place") or ""
        country, city, _ = locate(place)
        if not country: continue
        sev = 5 if mag >= 7 else 4 if mag >= 6 else 3 if mag >= 5.5 else 2
        if p.get("tsunami"): sev = min(5, sev + 1)
        when = dt.datetime.fromtimestamp(p["time"] / 1000, UTC)
        it = item(src, f"M{mag:.1f} earthquake, {place}", f"Depth {f['geometry']['coordinates'][2]:.0f} km. Alert: {p.get('alert') or 'none'}.", p.get("url"), when, cat="hazard", lat=lat, lon=lon, country=country, sev=sev)
        if it: out.append(it)
    return out

def from_gdacs(src, raw):
    import feedparser
    out = []
    for e in feedparser.parse(raw).entries:
        lvl = (e.get("gdacs_alertlevel") or "").lower()
        c = e.get("gdacs_country") or ""
        title = clean(e.get("title")); text = c + " " + title
        country, city, _ = locate(text)
        if not country: continue
        sev = {"red": 5, "orange": 4, "green": 2}.get(lvl, 2)
        lat = e.get("geo_lat"); lon = e.get("geo_long")
        it = item(src, title, clean(e.get("summary", "")), e.get("link"), parse_time(e), cat="hazard", country=country,
                  lat=float(lat) if lat else None, lon=float(lon) if lon else None, sev=sev)
        if it: out.append(it)
    return out

def from_gdelt(src, data):
    out = []
    for a in data.get("articles", []):
        try: when = dt.datetime.strptime(a.get("seendate", ""), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        except ValueError: when = NOW
        s2 = dict(src, name=f"{a.get('domain','GDELT')} (via GDELT)")
        it = item(s2, clean(a.get("title")), "", a.get("url"), when)
        if it: out.append(it)
    return out

def from_telegram(src, raw):
    text = raw.decode("utf-8", "ignore")
    out = []
    for m in re.finditer(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', text, re.S):
        msg = clean(m.group(1))
        it = item(dict(src, name=f"Telegram @{src['channel']}"), msg[:160], msg, f"https://t.me/s/{src['channel']}", NOW)
        if it: out.append(it)
    return out

def from_bluesky(src, data):
    out = []
    for p in data.get("posts", []):
        txt = clean(p.get("record", {}).get("text", ""))
        it = item(dict(src, name="Bluesky (unverified)"), txt[:160], txt, "https://bsky.app", NOW)
        if it: out.append(it)
    return out

def fetch(src):
    t = src["type"]
    if OFFLINE:
        raw = fixture(src)
        if raw is None: return [], "no fixture"
    else:
        if t == "gdelt":
            from urllib.parse import quote
            url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={quote(src['query'])}&mode=ArtList&format=json&maxrecords={src.get('max',100)}&timespan={src.get('timespan','3h')}&sort=DateDesc"
            raw = get(url, as_json=True)
        elif t == "telegram": raw = get(f"https://t.me/s/{src['channel']}")
        elif t == "bluesky":
            from urllib.parse import quote
            raw = get(f"https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q={quote(src['query'])}&limit=50", as_json=True)
        else: raw = get(src["url"], as_json=(t == "usgs"))
    fn = {"rss": from_rss, "state_dept": from_state, "fcdo": from_fcdo, "usgs": from_usgs, "gdacs": from_gdacs,
          "gdelt": from_gdelt, "telegram": from_telegram, "bluesky": from_bluesky}[t]
    return fn(src, raw), "ok"

# ---------------------------------------------------------------- merge, grade, decay
STOP = set("the a an of in on at to for and or with from by as is are was were after over new says said amid into".split())
def tokens(t): return {w for w in re.findall(r"[a-z0-9]+", t.lower()) if w not in STOP and len(w) > 2}
def eid(e): return hashlib.sha1((e["country"] + e["category"] + e["title"]).encode()).hexdigest()[:12]

def cluster(events):
    events.sort(key=lambda e: e["time"])
    merged = []
    for e in events:
        tk = tokens(e["title"]); t = dt.datetime.fromisoformat(e["time"])
        home = None
        for m in merged:
            if m["country"] != e["country"] or m["category"] != e["category"]: continue
            if abs((dt.datetime.fromisoformat(m["time"]) - t).total_seconds()) > 12 * 3600: continue
            if m["url"] == e["url"]: home = m; break
            j = len(tk & m["_tk"]) / max(1, len(tk | m["_tk"]))
            same_city = e["city"] and e["city"] == m["city"]
            if j >= 0.3 or (same_city and j >= 0.15): home = m; break
        if home:
            if e["source"] not in [s["name"] for s in home["sources"]]:
                home["sources"].append({"name": e["source"], "url": e["url"], "tier": e["tier"]})
            home["severity"] = max(home["severity"], e["severity"])
            home["city"] = home["city"] or e["city"]
            if home["lat"] is None and e["lat"] is not None: home["lat"], home["lon"] = e["lat"], e["lon"]
            if "ABCD".index(e["tier"]) < "ABCD".index(home["tier"]): home["tier"] = e["tier"]
            home["_tk"] |= tk
        else:
            e = dict(e); e["sources"] = [{"name": e["source"], "url": e["url"], "tier": e["tier"]}]; e["_tk"] = tk; e["first_seen"] = NOW.isoformat()
            merged.append(e)
    return merged

def grade(e):
    """Admiralty-style grade: letter = best source reliability, number = how well corroborated."""
    n = len({s["name"] for s in e["sources"]})
    official = e["tier"] == "A"
    cred = 1 if (n >= 3 or official) else 2 if n == 2 else 3 if e["tier"] == "B" else 4 if e["tier"] == "C" else 5
    e["confidence"] = f"{e['tier']}{cred}"
    e["corroboration"] = n
    return e

def merge_state(new):
    p = DATA / "events.json"
    prev = json.load(open(p, encoding="utf-8")) if p.exists() else {}
    old = [] if (prev.get("sample") and not OFFLINE) else prev.get("events", [])   # never carry sample data into live runs
    by = {e["id"]: e for e in old}
    for e in new:
        if e["id"] in by:
            o = by[e["id"]]
            names = {s["name"] for s in o["sources"]}
            o["sources"] += [s for s in e["sources"] if s["name"] not in names]
            o["severity"] = max(o["severity"], e["severity"]); grade(o)
        else: by[e["id"]] = e
    keep = []
    for e in by.values():
        age_h = (NOW - dt.datetime.fromisoformat(e["time"])).total_seconds() / 3600
        if age_h <= TTL_H.get(e["category"], 72): keep.append(e)
    keep.sort(key=lambda e: e["time"], reverse=True)
    keep.sort(key=lambda e: -e["severity"])
    return keep

def main():
    cfg = json.load(open(ROOT / "config" / "sources.json", encoding="utf-8"))
    watch = json.load(open(ROOT / "config" / "watchlist.json", encoding="utf-8")) if (ROOT / "config" / "watchlist.json").exists() else {"locations": []}
    status, raw_events = [], []
    for src in cfg["sources"]:
        if not src.get("enabled"): continue
        t0 = time.time()
        try:
            evs, msg = fetch(src)
            evs = [e for e in evs if (NOW - dt.datetime.fromisoformat(e["time"])).total_seconds() <= cfg["lookback_hours"] * 3600 or e["category"] == "advisory"]
            raw_events += evs
            status.append({"id": src["id"], "name": src["name"], "ok": True, "items": len(evs), "note": msg, "secs": round(time.time() - t0, 1)})
        except Exception as ex:
            status.append({"id": src["id"], "name": src["name"], "ok": False, "items": 0, "note": str(ex)[:160]})
    merged = [grade(e) for e in cluster(raw_events)]
    for e in merged:
        e["id"] = eid(e); e.pop("_tk", None); e.pop("source", None); e.pop("source_id", None)
        c = CMAP[e["country"]]; e["flag"] = c["flag"]; e["region"] = c["region"]; e["baseline"] = c["cx"]
    events = merge_state(merged)
    # watchlist hits
    W = [(w.get("label", w.get("city") or w.get("country")), w.get("country"), w.get("city")) for w in watch.get("locations", [])]
    for e in events:
        e["watch"] = [lab for lab, c, ct in W if (c == e["country"] and (not ct or ct == e.get("city")))]
    DATA.mkdir(parents=True, exist_ok=True)
    json.dump({"generated": NOW.isoformat(), "sample": OFFLINE, "count": len(events), "events": events}, open(DATA / "events.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"generated": NOW.isoformat(), "sources": status}, open(DATA / "status.json", "w", encoding="utf-8"), indent=1)
    # brief: last 24h
    recent = [e for e in events if (NOW - dt.datetime.fromisoformat(e["time"])).total_seconds() <= 86400]
    regions = {}
    for e in sorted(recent, key=lambda e: (-e["severity"], -e["corroboration"])):
        regions.setdefault(e["region"], []).append({k: e[k] for k in ("id", "title", "country", "city", "category", "severity", "confidence", "time")})
    counts = {s: sum(1 for e in recent if e["severity"] == s) for s in range(1, 6)}
    json.dump({"generated": NOW.isoformat(), "sample": OFFLINE, "window_hours": 24, "counts": counts, "watch_hits": [e["id"] for e in recent if e["watch"]],
               "regions": {r: v[:8] for r, v in regions.items()}}, open(DATA / "brief.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # archive
    arch = DATA / "archive"; arch.mkdir(exist_ok=True)
    seen_p = arch / "seen_ids.txt"; seen = set(seen_p.read_text().split()) if seen_p.exists() else set()
    with open(arch / f"{NOW:%Y-%m}.jsonl", "a", encoding="utf-8") as f:
        for e in merged:
            if e["id"] not in seen: f.write(json.dumps(e, ensure_ascii=False) + "\n"); seen.add(e["id"])
    seen_p.write_text("\n".join(sorted(seen)))
    # optional alert webhook (Slack, Discord or Teams incoming webhook) for severe watchlist hits
    hook = os.environ.get("ALERT_WEBHOOK_URL")
    if hook and not OFFLINE:
        import requests
        sent_p = arch / "alerted_ids.txt"; sent = set(sent_p.read_text().split()) if sent_p.exists() else set()
        for e in events:
            if e["watch"] and e["severity"] >= 4 and e["id"] not in sent:
                msg = f"JR alert S{e['severity']} {e['confidence']} | {e['flag']} {e.get('city') or e['country']} | {e['title']} ({', '.join(e['watch'])}) {e['sources'][0]['url']}"
                try: requests.post(hook, json={"text": msg, "content": msg}, timeout=15); sent.add(e["id"])
                except Exception: pass
        sent_p.write_text("\n".join(sorted(sent)))
    ok = sum(s["ok"] for s in status)
    print(f"{len(events)} live events from {ok}/{len(status)} sources ({len(raw_events)} raw items)")

if __name__ == "__main__":
    main()
