"""Generate the static parts derived from GROUPS, POLICIES and SPOTS in index.html.

- policy/, spot/, about/: crawlable text pages. The 3D app keeps everything on
  one URL behind '#', which search engines treat as a single page, so each
  policy and landmark also gets its own page with the full text.
- share/*.html: one link-preview page per policy and landmark. Social crawlers
  never see the part of a URL after '#', so each item gets a page with its own
  Open Graph tags that redirects into the app (keeping any utm_* query so
  analytics can attribute the visit). Their canonical is the text page.
- index.html SEO blocks: JSON-LD structured data and a <noscript> text version.
- index.html district data: which official policy pages name each of the 29
  districts, taken from the official text saved by tools/check_source.py.
- updates/: the release notes, one section per day, from tools/releases.json
  (written for visitors, newest first); the latest entry is also embedded in
  index.html so returning visitors hear about what is new.
- sitemap.xml listing every indexable page.

Re-run after editing the data in index.html:

    python3 tools/build_static.py
"""
import datetime
import html
import json
import re
from pathlib import Path
from urllib.parse import quote, unquote

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://ntpc-island.github.io/"
OG_IMAGE = SITE + "og.png"
SOURCE_URL = "https://chiao.tw/policies"
GA_ID = "G-5H13CQWF3X"
TODAY = datetime.date.today().isoformat()

index_path = ROOT / "index.html"
source = index_path.read_text(encoding="utf-8")
e = lambda v: html.escape(v, quote=True)
SOURCE_DATE = re.search(r"const SOURCE_DATE = '(\d{4}-\d{2}-\d{2})'", source).group(1)


def strings(block):
    return re.findall(r"'([^']+)'", block)


groups = {k: {"name": n, "color": c} for k, n, c in re.findall(r"(\w+): \{ name: '([^']+)', color: '(#[0-9a-fA-F]+)' \}", source)}
policies = [
    {"short": m[0], "title": m[1], "slug": m[2], "group": m[3], "summary": m[4], "items": strings(m[5])}
    for m in re.findall(
        r"short: '([^']+)', title: '([^']+)', slug: '([^']+)', group: '(\w+)'.*?summary: '([^']+)',\s*items: \[(.*?)\]",
        source,
        re.S,
    )
]
spots = [
    {"name": m[0], "map": m[1], "desc": m[2]}
    for m in re.findall(r"name: '([^']+)', map: '([^']+)'.*?desc: '([^']+)'", source, re.S)
]
assert len(groups) == 5 and len(policies) == 14 and len(spots) == 12, (len(groups), len(policies), len(spots))


def og_image(key):
    """Per-item card from tools/build_og_images.py, or the shared overview image until it exists."""
    return f"{SITE}og/{key}.png" if (ROOT / "og" / f"{key}.png").exists() else OG_IMAGE


def readable_bg(hex_color):
    """Darken a colour until white text on it reaches 4.5:1 (same rule as readableBg in index.html)."""
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lum = lambda c: sum(w * (v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4) for w, v in zip((0.2126, 0.7152, 0.0722), c))
    k = 1.0
    while k > 0.4 and 1.05 / (lum([v * k for v in rgb]) + 0.05) < 4.5:
        k -= 0.03
    return "#" + "".join(f"{round(v * k * 255):02x}" for v in rgb)


def page_path(kind, name):
    return f"{kind}/{quote(name)}/"


def official_url(p):
    return f"{SOURCE_URL}/{quote(p['slug'])}"


def maps_url(s):
    return f"https://www.google.com/maps/search/?api=1&query={quote(s['map'])}"


def app_link(kind, name):
    return "/#" + quote(f"{kind}/{name}", safe="/")


# ---------- text pages ----------
GA_SNIPPET = f"""<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag() {{ dataLayer.push(arguments); }}
  gtag('js', new Date());
  gtag('config', '{GA_ID}');
</script>"""

HEADER = """<header class="site-header">
  <a class="brand" href="/">新北政見島</a>
  <nav><a href="/">3D 地圖</a><a href="/policy/">政見一覽</a><a href="/vote/">投票資訊</a><a href="/updates/">更新紀錄</a><a href="/about/">關於本站</a></nav>
  <div class="textsize" role="group" aria-label="字級">
    <span>字級</span><button type="button" data-size-btn="m">標準</button><button type="button" data-size-btn="l">大</button><button type="button" data-size-btn="xl">特大</button>
  </div>
</header>"""

# ?size=l (from the app's 大字文字版 link) wins, then the remembered choice
SIZE_HEAD = """<script>
  (() => {
    let size = new URLSearchParams(location.search).get('size');
    try { size = size || localStorage.getItem('textSize'); } catch { /* storage blocked */ }
    document.documentElement.dataset.size = ['m', 'l', 'xl'].includes(size) ? size : 'm';
  })();
</script>"""

SIZE_BODY = """<script>
  (() => {
    const root = document.documentElement, buttons = document.querySelectorAll('[data-size-btn]');
    const show = () => buttons.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.sizeBtn === root.dataset.size)));
    buttons.forEach((b) => b.addEventListener('click', () => {
      root.dataset.size = b.dataset.sizeBtn;
      try { localStorage.setItem('textSize', b.dataset.sizeBtn); } catch { /* storage blocked */ }
      show();
    }));
    show();
  })();
</script>"""

FOOTER = f"""<footer class="site-footer">
  非官方整理 · 政見內容摘錄自 <a href="{SOURCE_URL}">{SOURCE_URL}</a>（{SOURCE_DATE}），以官方網站為準 · 本站使用 Google Analytics 統計瀏覽情形
</footer>"""


def text_page(path, title, description, body, crumbs, og_title=None, image=OG_IMAGE):
    """crumbs: [(name, path or None)] after 首頁; the last one is the current page."""
    url = SITE + path
    breadcrumb_ld = {
        "@type": "BreadcrumbList",
        "itemListElement": [{"@type": "ListItem", "position": 1, "name": "新北政見島", "item": SITE}]
        + [
            {"@type": "ListItem", "position": n, "name": name, "item": SITE + (p if p is not None else path)}
            for n, (name, p) in enumerate(crumbs, 2)
        ],
    }
    page_ld = {
        "@type": "WebPage",
        "url": url,
        "name": title,
        "description": description,
        "inLanguage": "zh-TW",
        "dateModified": TODAY,
        "isPartOf": {"@type": "WebSite", "name": "新北政見島", "url": SITE},
    }
    ld = json.dumps({"@context": "https://schema.org", "@graph": [page_ld, breadcrumb_ld]}, ensure_ascii=False)
    crumb_html = " › ".join(
        ['<a href="/">首頁</a>']
        + [f'<a href="/{p}">{e(name)}</a>' if p is not None else e(name) for name, p in crumbs]
    )
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{url}">
<meta name="theme-color" content="#f7f4ee">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Cpath fill='%23e0663d' d='M16 1l13 7.5v15L16 31 3 23.5v-15z'/%3E%3C/svg%3E">
<link rel="stylesheet" href="/pages.css">
<meta property="og:type" content="article">
<meta property="og:locale" content="zh_TW">
<meta property="og:site_name" content="新北政見島">
<meta property="og:title" content="{e(og_title or title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{ld}</script>
{SIZE_HEAD}
{GA_SNIPPET}
</head>
<body>
{HEADER}
<main>
<p class="breadcrumb">{crumb_html}</p>
{body}
</main>
{FOOTER}
{SIZE_BODY}
</body>
</html>
"""


def summarize(text, limit=150):
    return text if len(text) <= limit else text[: limit - 1] + "…"


def write(path, content):
    # URLs carry percent-encoded names; the folders on disk use the plain names the server decodes them to
    target = ROOT / unquote(path) / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


written = []
for n, p in enumerate(policies):
    grp = groups[p["group"]]
    prev_p, next_p = policies[n - 1], policies[(n + 1) % len(policies)]
    path = page_path("policy", p["short"])
    body = f"""<span class="tag" style="background:{readable_bg(grp['color'])}">{e(grp['name'])}</span>
<h1>{e(p['title'])}</h1>
<p class="lead">{e(p['summary'])}</p>
<h2>政見重點</h2>
<ul class="points">
{''.join(f'<li>{e(i)}</li>' for i in p['items'])}
</ul>
<div class="actions">
  <a class="button primary" href="{app_link('policy', p['short'])}">在 3D 政見島查看</a>
  <a class="button" href="{official_url(p)}" rel="noopener">閱讀官方完整政見 ↗</a>
</div>
<nav class="pager" aria-label="上一項與下一項">
  <a href="/{page_path('policy', prev_p['short'])}">← {e(prev_p['short'])}</a>
  <a href="/{page_path('policy', next_p['short'])}">{e(next_p['short'])} →</a>
</nav>
<p class="note">本頁為非官方整理，內容節錄自蘇巧慧 2026 新北市長競選網站（擷取日期 {SOURCE_DATE}），若有出入請以<a href="{official_url(p)}">官方原文</a>為準。</p>"""
    description = summarize(f"{p['summary']}重點：{'；'.join(p['items'])}")
    write(path, text_page(path, f"{p['title']}｜蘇巧慧 2026 新北市長政見｜新北政見島", description, body, [("政見一覽", "policy/"), (p["short"], None)], og_title=f"{p['title']}｜新北政見島", image=og_image(f"policy-{n + 1:02d}")))
    written.append(path)

for n, s in enumerate(spots):
    prev_s, next_s = spots[n - 1], spots[(n + 1) % len(spots)]
    path = page_path("spot", s["name"])
    body = f"""<span class="tag" style="background:#0f766e">新北景點</span>
<h1>{e(s['name'])}</h1>
<p class="lead">{e(s['desc'])}</p>
<div class="actions">
  <a class="button primary" href="{app_link('spot', s['name'])}">在 3D 地圖查看</a>
  <a class="button" href="{maps_url(s)}" rel="noopener">在 Google 地圖開啟 ↗</a>
</div>
<nav class="pager" aria-label="上一個與下一個景點">
  <a href="/{page_path('spot', prev_s['name'])}">← {e(prev_s['name'])}</a>
  <a href="/{page_path('spot', next_s['name'])}">{e(next_s['name'])} →</a>
</nav>"""
    write(path, text_page(path, f"{s['name']}｜新北景點｜新北政見島", s["desc"], body, [("政見一覽", "policy/"), (s["name"], None)], image=og_image(f"spot-{n + 1:02d}")))
    written.append(path)

# Overview of every policy and landmark
policy_items = "\n".join(
    f'<li><a href="/{page_path("policy", p["short"])}"><span class="t">{e(p["title"])}</span><span class="s">{e(groups[p["group"]]["name"])} · {e(p["summary"])}</span></a></li>'
    for p in policies
)
spot_items = "\n".join(
    f'<li><a href="/{page_path("spot", s["name"])}"><span class="t">{e(s["name"])}</span><span class="s">{e(s["desc"])}</span></a></li>'
    for s in spots
)
overview_body = f"""<h1>蘇巧慧 2026 新北市長政見一覽</h1>
<p class="lead">{len(policies)} 項政見的重點整理，每一項都附官方原文連結。想用地圖瀏覽，可以到 <a href="/">3D 政見島</a>。</p>
<h2>政見</h2>
<ul class="list">
{policy_items}
</ul>
<h2>新北景點</h2>
<ul class="list">
{spot_items}
</ul>"""
write("policy/", text_page("policy/", "蘇巧慧 2026 新北市長 14 項政見一覽｜新北政見島", f"蘇巧慧 2026 新北市長 {len(policies)} 項政見重點整理：{'、'.join(p['short'] for p in policies)}。非官方整理，附官方原文連結。", overview_body, [("政見一覽", None)]))
written.append("policy/")

about_body = f"""<h1>關於新北政見島</h1>
<p class="lead">新北政見島把蘇巧慧 2026 新北市長競選網站公布的 {len(policies)} 項政見，整理成一張 3D 互動地圖和文字頁，讓大家更容易瀏覽、搜尋和分享。</p>
<h2>非官方網站</h2>
<p>本站並非蘇巧慧競選團隊的官方網站。政見內容以<a href="{SOURCE_URL}">官方網站</a>為準。</p>
<h2>資料來源</h2>
<ul class="points">
  <li>政見的標題、摘要與重點條列，節錄自 <a href="{SOURCE_URL}">{SOURCE_URL}</a>，擷取日期 {SOURCE_DATE}。</li>
  <li>每一項政見都附上官方原文連結，本站不加入評論或立場說明。</li>
  <li>新北景點的介紹由本站撰寫，地點連結到 Google 地圖。</li>
</ul>
<h2>隱私與統計</h2>
<ul class="points">
  <li>本站使用 Google Analytics 統計瀏覽、分享與搜尋的次數，用來了解哪些內容較受關注。</li>
  <li>使用 LINE 分享卡片時，會經過 LINE 的登入與授權，授權只用來傳送你選擇的卡片，本站不儲存你的 LINE 帳號資料。</li>
</ul>
<p class="note">最後更新：{TODAY}</p>"""
write("about/", text_page("about/", "關於新北政見島｜資料來源與非官方聲明", "新北政見島是非官方整理的蘇巧慧 2026 新北市長政見 3D 地圖。說明資料來源、擷取日期、隱私與統計方式。", about_body, [("關於本站", None)]))
written.append("about/")


# ---------- voting information ----------
election = {k: v for k, v in json.loads((ROOT / "tools" / "election.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
vd = datetime.date.fromisoformat(election["date"])
vote_body = f"""<h1>投票資訊</h1>
<p class="lead">{e(election["name"])}</p>
<div class="vote-day">
  <span class="vote-date">{vd.month} 月 {vd.day} 日（{e(election["weekday"])}）</span>
  <span class="vote-hours">{e(election["hours"])}</span>
  <span class="vote-count" id="vote-count" data-date="{election["date"]}"></span>
</div>
<h2>要帶什麼</h2>
<ul class="points">{''.join(f"<li>{e(x)}</li>" for x in election["bring"])}</ul>
<h2>在哪裡投票</h2>
<ul class="points">{''.join(f"<li>{e(x)}</li>" for x in election["notes"])}</ul>
<div class="actions"><a class="button primary" href="https://web.cec.gov.tw/tpcec" rel="noopener">新北市選舉委員會 ↗</a></div>
<h2>資料來源</h2>
<ul class="points">{''.join(f'<li><a href="{e(x["url"])}" rel="noopener">{e(x["title"])}</a></li>' for x in election["sources"])}</ul>
<p class="note">以上內容整理自中央選舉委員會與新北市選舉委員會公告，若有更新以官方公告為準。</p>
<script>
  (() => {{
    // Whole days left, counted in Taipei time
    const el = document.getElementById('vote-count');
    const today = new Intl.DateTimeFormat('sv-SE', {{ timeZone: 'Asia/Taipei' }}).format(new Date());
    const days = Math.round((Date.parse(el.dataset.date) - Date.parse(today)) / 86400000);
    el.textContent = days > 0 ? `距離投票還有 ${{days}} 天` : days === 0 ? '今天投票，記得出門！' : '';
  }})();
</script>"""
write("vote/", text_page("vote/", f"投票資訊｜{vd.month}/{vd.day} 新北市長選舉｜新北政見島", f"{election['name']}：{vd.month} 月 {vd.day} 日（{election['weekday']}）{election['hours']}投票，記得攜帶{'、'.join(election['bring'])}。", vote_body, [("投票資訊", None)]))
written.append("vote/")


# ---------- release notes ----------
releases = json.loads((ROOT / "tools" / "releases.json").read_text(encoding="utf-8"))
releases.sort(key=lambda r: r["date"], reverse=True)


def zh_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.year} 年 {d.month} 月 {d.day} 日"


def release_item(it):
    # Optional "credit": {"name", "url"} thanks the person who built the feature
    credit = it.get("credit")
    thanks = f'<span class="credit">感謝 <a href="{e(credit["url"])}" rel="noopener">@{e(credit["name"])}</a> 貢獻</span>' if credit else ""
    return f'<li><b>{e(it["title"])}</b>{e(it["desc"])}{thanks}</li>'


release_sections = "\n".join(
    f"""<section class="release" id="{r['date']}">
<h2><time datetime="{r['date']}">{zh_date(r['date'])}</time><span>{e(r['title'])}</span></h2>
<ul class="release-items">
{''.join(release_item(it) for it in r['items'])}
</ul>
</section>"""
    for r in releases
)
updates_body = f"""<h1>更新紀錄</h1>
<p class="lead">新北政見島每天的新功能與改進，最新的在最上面。</p>
{release_sections}
<p class="note">本站為非官方整理，政見內容以<a href="{SOURCE_URL}">官方網站</a>為準。</p>"""
latest = releases[0]
write("updates/", text_page("updates/", "更新紀錄｜新北政見島", f"新北政見島的新功能與改進。最新更新（{latest['date']}）：{latest['title']}。", updates_body, [("更新紀錄", None)]))
written.append("updates/")
release_block = '<script type="application/json" id="release-data">' + json.dumps(
    {"date": latest["date"], "title": latest["title"]}, ensure_ascii=False) + "</script>"


# ---------- share pages ----------
def share_page(slug, kind, name, title, description):
    target = "../#" + quote(f"{kind}/{name}", safe="/")
    base, frag = target.split("#")
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>{e(name)}｜新北政見島</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{SITE}{page_path(kind, name)}">
<meta property="og:type" content="website">
<meta property="og:locale" content="zh_TW">
<meta property="og:site_name" content="新北政見島">
<meta property="og:title" content="{e(title)}｜新北政見島">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{SITE}share/{slug}.html">
<meta property="og:image" content="{og_image(slug)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta http-equiv="refresh" content="0; url={target}">
<script>location.replace({base!r} + location.search + {("#" + frag)!r});</script>
</head>
<body><a href="{target}">前往「{e(name)}」</a></body>
</html>
"""


out = ROOT / "share"
out.mkdir(exist_ok=True)
for n, p in enumerate(policies, 1):
    (out / f"policy-{n:02d}.html").write_text(share_page(f"policy-{n:02d}", "policy", p["short"], p["title"], p["summary"]), encoding="utf-8")
for n, s in enumerate(spots, 1):
    (out / f"spot-{n:02d}.html").write_text(share_page(f"spot-{n:02d}", "spot", s["name"], f"新北景點：{s['name']}", s["desc"]), encoding="utf-8")


# ---------- index.html SEO blocks ----------
jsonld = {
    "@context": "https://schema.org",
    "@graph": [
        {
            "@type": "WebSite",
            "@id": SITE + "#website",
            "url": SITE,
            "name": "新北政見島",
            "inLanguage": "zh-TW",
            "description": "蘇巧慧 2026 新北市長 14 項政見的 3D 互動地圖（非官方整理）",
        },
        {
            "@type": "ItemList",
            "name": "蘇巧慧 2026 新北市長政見",
            "numberOfItems": len(policies),
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": n,
                    "item": {
                        "@type": "CreativeWork",
                        "name": p["title"],
                        "description": p["summary"],
                        "url": SITE + page_path("policy", p["short"]),
                        "isBasedOn": official_url(p),
                    },
                }
                for n, p in enumerate(policies, 1)
            ],
        },
    ],
}
jsonld_block = '<script type="application/ld+json">\n' + json.dumps(jsonld, ensure_ascii=False, indent=1) + "\n</script>"

noscript_lines = [
    "<noscript>",
    '<div class="noscript">',
    '<p>這個網站需要 JavaScript 才能顯示 3D 地圖。也可以看<a href="policy/">文字版政見一覽</a>。</p>',
    "<h2>蘇巧慧 2026 新北市長政見（非官方整理）</h2>",
]
for p in policies:
    noscript_lines += [
        f'<h3><a href="{page_path("policy", p["short"])}">{e(p["title"])}</a></h3>',
        f"<p>{e(p['summary'])}</p>",
        "<ul>" + "".join(f"<li>{e(i)}</li>" for i in p["items"]) + "</ul>",
        f'<p><a href="{official_url(p)}">閱讀官方完整政見</a></p>',
    ]
noscript_lines.append("<h2>新北景點</h2>")
noscript_lines.append(
    "<ul>" + "".join(f'<li><a href="{page_path("spot", s["name"])}"><strong>{e(s["name"])}</strong></a>：{e(s["desc"])}</li>' for s in spots) + "</ul>"
)
noscript_lines.append(f'<p>內容摘錄自 <a href="{SOURCE_URL}">{SOURCE_URL}</a>，以官方網站為準。</p>')
noscript_lines += ["</div>", "</noscript>"]
noscript_block = "\n".join(noscript_lines)


def fill(text, name, block):
    pattern = re.compile(rf"(<!-- seo:{name}:start -->\n).*?(<!-- seo:{name}:end -->)", re.S)
    assert pattern.search(text), name
    return pattern.sub(lambda m: m.group(1) + block + "\n" + m.group(2), text)


DISTRICTS = "板橋 三重 中和 永和 新莊 新店 樹林 鶯歌 三峽 淡水 汐止 瑞芳 土城 蘆洲 五股 泰山 林口 深坑 石碇 坪林 三芝 石門 八里 平溪 雙溪 貢寮 金山 萬里 烏來".split()


def clip(sentence, word, width=72):
    """Keep about `width` characters of the sentence, centred on the district name."""
    if len(sentence) <= width:
        return sentence
    at = sentence.index(word)
    start = max(0, min(at - width // 3, len(sentence) - width))
    return ("…" if start else "") + sentence[start:start + width] + ("…" if start + width < len(sentence) else "")


snapshot = json.loads((ROOT / "tools" / "source_snapshot.json").read_text(encoding="utf-8"))
short_by_slug = {p["slug"]: p["short"] for p in policies}
district_data = {}
for name in DISTRICTS:
    hits = []
    for official in snapshot["policies"]:
        short = short_by_slug.get(official["slug"])
        sentences = [x.strip() for line in official["text"].split("\n") for x in re.split(r"(?<=[。！？；])", line) if name in x]
        if short and sentences:
            hits.append({"short": short, "snippets": [clip(x, name) for x in dict.fromkeys(sentences)][:2]})
    if hits:
        district_data[name] = hits
district_block = '<script type="application/json" id="district-data">' + json.dumps(district_data, ensure_ascii=False) + "</script>"

source = fill(source, "jsonld", jsonld_block)
source = fill(source, "noscript", noscript_block)
election_block = '<script type="application/json" id="election-data">' + json.dumps({"date": election["date"], "quiet_dates": election["quiet_dates"]}, ensure_ascii=False) + "</script>"
source = re.sub(r"(<!-- data:election:start -->\n).*?(<!-- data:election:end -->)", lambda m: m.group(1) + election_block + "\n" + m.group(2), source, flags=re.S)
source = re.sub(r"(<!-- data:release:start -->\n).*?(<!-- data:release:end -->)", lambda m: m.group(1) + release_block + "\n" + m.group(2), source, flags=re.S)
source = re.sub(r"(<!-- data:districts:start -->\n).*?(<!-- data:districts:end -->)", lambda m: m.group(1) + district_block + "\n" + m.group(2), source, flags=re.S)
index_path.write_text(source, encoding="utf-8")


# ---------- sitemap ----------
TOP = ["policy/", "vote/", "updates/", "about/"]
urls = [SITE] + [SITE + p for p in TOP + [w for w in written if w not in TOP]]
(ROOT / "sitemap.xml").write_text(
    '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + "".join(f"  <url><loc>{u}</loc><lastmod>{TODAY}</lastmod></url>\n" for u in urls)
    + "</urlset>\n",
    encoding="utf-8",
)
print(f"wrote {len(written)} text pages, {len(policies) + len(spots)} share pages, SEO blocks, district data ({len(district_data)}/29 districts), sitemap ({len(urls)} urls)")
