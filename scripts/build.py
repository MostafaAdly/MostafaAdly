#!/usr/bin/env python3
"""Builds every SVG the profile README shows, in a dark and a light variant.

Live numbers (contributions, release tags, stars) come from the GitHub GraphQL
API when GH_TOKEN or GITHUB_TOKEN is set. Without a token, or if the API call
fails, the last good numbers in assets/data.json are reused, so a bad run never
blanks the profile.

Usage: python3 scripts/build.py
"""
import datetime as dt
import json
import os
import pathlib
import re
import urllib.request
from html import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DATA = ASSETS / "data.json"
USER = "MostafaAdly"
FIRST_YEAR = 2021

THEMES = {
    "dark": dict(bg="#0d1117", panel="#161b22", border="#30363d", ink="#e6edf3",
                 muted="#8b949e", faint="#21262d", dot="#1f2630", g1="#ff7a45",
                 g2="#ff3d77", g3="#a371f7", ok="#3fb950", bar="#ff5c7a"),
    "light": dict(bg="#ffffff", panel="#f6f8fa", border="#d0d7de", ink="#1f2328",
                  muted="#59636e", faint="#eaeef2", dot="#e4e8ec", g1="#e8590c",
                  g2="#d6336c", g3="#7048e8", ok="#1a7f37", bar="#d6336c"),
}

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
REDUCED = "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"

# Featured open-source repos. Text is hand-written; tag/stars are refreshed live.
CARDS = [
    dict(repo="talkie-promptie", title="Kalam", watermark="كلام", lang="Rust", chip="macOS",
         lines=["Mac dictation in Arabic and English,",
                "even mid-sentence. Optional Claude prompts."]),
    dict(repo="vast-cli", title="vast-cli", watermark="⇢", lang="TypeScript", chip="menu-bar app",
         lines=["Promotes a repo develop → staging →",
                "production, versioned from what's live."]),
    dict(repo="tawbah-whatsapp", title="tawbah-whatsapp", watermark="۞", lang="JavaScript", chip="WhatsApp bot",
         lines=["Posts Quran verses to a public WhatsApp",
                "group. Also on Discord and the web."]),
    dict(repo="neuralnetwork", title="neuralnetwork", watermark="∿", lang="Java", chip="machine learning",
         lines=["A simple self-learning neural network,",
                "written in Java."]),
]
LANG_COLOR = {"Rust": "#dea584", "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Java": "#b07219"}


# ---------------------------------------------------------------- data

def graphql(query, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-readme-build"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]


def fetch_live(token):
    today = dt.date.today()
    years = range(FIRST_YEAR, today.year + 1)
    parts = [
        f'y{y}: contributionsCollection(from:"{y}-01-01T00:00:00Z", to:"{y}-12-31T23:59:59Z")'
        "{ contributionCalendar{ totalContributions } }" for y in years
    ]
    u = graphql(f'{{ user(login:"{USER}"){{ last: contributionsCollection{{ contributionCalendar{{ totalContributions }} }} '
                + " ".join(parts) + " } }", token)["user"]
    data = {
        "as_of": today.isoformat(),
        "last_year": u["last"]["contributionCalendar"]["totalContributions"],
        "years": {str(y): u[f"y{y}"]["contributionCalendar"]["totalContributions"] for y in years},
        "repos": {},
    }
    # Repos are fetched one by one so a renamed or private repo only loses its own chips.
    for c in CARDS:
        try:
            r = graphql(f'{{ repository(owner:"{USER}", name:"{c["repo"]}"){{ stargazerCount latestRelease{{ tagName }} }} }}',
                        token)["repository"]
            data["repos"][c["repo"]] = {"stars": r["stargazerCount"], "tag": (r["latestRelease"] or {}).get("tagName")}
        except Exception as e:
            print(f"repo {c['repo']}: {e}; keeping cached chips")
    return data


def load_data():
    """Returns (data, ok). ok is False when a live read was attempted and rejected."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    cached = json.loads(DATA.read_text()) if DATA.exists() else None
    if token:
        try:
            data = fetch_live(token)
            # A token that cannot see private contributions returns a tiny count.
            # A real halving in one week is implausible, so treat it as a bad read.
            for repo, v in (cached or {}).get("repos", {}).items():
                data["repos"].setdefault(repo, v)
            if cached and data["last_year"] < cached["last_year"] / 2:
                raise RuntimeError(f"last_year dropped {cached['last_year']} -> {data['last_year']}")
            for y, v in (cached or {}).get("years", {}).items():
                # Past years are final and the current year only grows, so any drop
                # in a year we already have means the token sees less than before.
                # A few contributions can legitimately vanish (a deleted repo), so allow 2%.
                if data["years"].get(y, 0) < v - max(5, v * 0.02):
                    raise RuntimeError(f"year {y} dropped {v} -> {data['years'].get(y)}")
            DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            return data, True
        except Exception as e:  # keep the last good numbers on the page, but report failure
            print(f"live fetch failed, using cached data: {e}")
            return cached, False
    return cached, True


# ---------------------------------------------------------------- helpers

def defs(t, glow=True):
    g = f"""
    <linearGradient id="brand" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{t['g1']}"/><stop offset=".5" stop-color="{t['g2']}"/>
      <stop offset="1" stop-color="{t['g3']}"/>
    </linearGradient>
    <pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">
      <circle cx="2" cy="2" r="1.1" fill="{t['dot']}"/>
    </pattern>"""
    if glow:
        g += f"""
    <radialGradient id="glowA"><stop offset="0" stop-color="{t['g2']}" stop-opacity=".22"/>
      <stop offset="1" stop-color="{t['g2']}" stop-opacity="0"/></radialGradient>
    <radialGradient id="glowB"><stop offset="0" stop-color="{t['g3']}" stop-opacity=".2"/>
      <stop offset="1" stop-color="{t['g3']}" stop-opacity="0"/></radialGradient>"""
    return f"<defs>{g}</defs>"


def frame(w, h, t, rx=12):
    return (f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="{rx}" fill="{t["bg"]}" stroke="{t["border"]}"/>'
            f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="{rx}" fill="url(#dots)"/>')


def svg(w, h, label, body, style=""):
    return dict(w=w, h=h, label=label, body=body, style=style)


IDS = ("brand", "dots", "glowA", "glowB", "card")


def dual(light, dark):
    """One SVG that carries both themes and picks one from the OS color scheme.

    Used only for the phone layouts: a <source media="(max-width: ...)"> cannot
    also carry a color-scheme query on GitHub, so the image themes itself.
    """
    body = dark["body"]
    for i in IDS:
        body = body.replace(f'id="{i}"', f'id="{i}-d"').replace(f"url(#{i})", f"url(#{i}-d)")
    style = (light["style"] + ".thD{display:none}"
             "@media (prefers-color-scheme: dark){.thL{display:none}.thD{display:inline}}")
    return render(dict(light, style=style,
                       body=f'<g class="thL">{light["body"]}</g><g class="thD">{body}</g>'))


def render(p):
    w, h, label, body, style = p["w"], p["h"], p["label"], p["body"], p["style"]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{escape(label)}"><title>{escape(label)}</title>'
            f"<style>{style}{REDUCED}</style>{body}</svg>\n")


# ---------------------------------------------------------------- hero
# Type sizes are in SVG units. Desktop images are 1200 wide and render at ~0.69x
# in GitHub's column; phone images are 600 wide at ~0.6x. Small text is kept at
# >= 16 / 18 units so nothing lands below ~11px on screen.

TERMINAL = [
    ("p", "vast status --all"),
    ("o", "  VastPayPwa    staging ✓   prod ✓"),
    ("o", "  VastMenuPwa   staging ✓   prod ✓"),
    ("p", "vast release VastPayPwa"),
    ("o", "  ▸ version derived from what's live"),
    ("o", "  ▸ develop → staging, deployed"),
    ("k", "  ✓ confirmed live"),
]


def terminal(t, ox, oy, w, size, step):
    """The animated terminal: lines type in one after another, hold, then reset."""
    period = 15.0
    kf, out = [], []
    tx, ty = ox + 20, oy + 40 + step + 6
    n = len(TERMINAL)
    for i in range(n + 1):
        on = (0.6 + i * 0.9) / period * 100
        kf.append(f"@keyframes l{i}{{0%,{on:.1f}%{{opacity:0}}{on+1.5:.1f}%,94%{{opacity:1}}100%{{opacity:0}}}}"
                  f".l{i}{{animation:l{i} {period}s infinite}}")
    for i, (kind, text) in enumerate(TERMINAL):
        y = ty + i * step
        if kind == "p":
            out.append(f'<text class="l{i}" x="{tx}" y="{y}" font-family="{MONO}" font-size="{size}">'
                       f'<tspan fill="{t["g2"]}">$</tspan><tspan fill="{t["ink"]}"> {escape(text)}</tspan></text>')
        else:
            fill = t["ok"] if kind == "k" else t["muted"]
            out.append(f'<text class="l{i}" x="{tx}" y="{y}" font-family="{MONO}" font-size="{size}" '
                       f'fill="{fill}" xml:space="preserve">{escape(text)}</text>')
    cy = ty + n * step
    out.append(f'<g class="l{n}"><text x="{tx}" y="{cy}" font-family="{MONO}" font-size="{size}" fill="{t["g2"]}">$</text>'
               f'<rect class="cur" x="{tx + size*1.1:.0f}" y="{cy - size*0.85:.0f}" width="{size*0.6:.0f}" '
               f'height="{size*1.1:.0f}" fill="{t["ink"]}"/></g>')
    h = cy - oy + step
    box = f"""
      <rect x="{ox}" y="{oy}" width="{w}" height="{h}" rx="10" fill="{t['panel']}" stroke="{t['border']}"/>
      <path d="M{ox} {oy+40}h{w}" stroke="{t['border']}"/>
      <circle cx="{ox+22}" cy="{oy+20}" r="6" fill="#ff5f57"/><circle cx="{ox+42}" cy="{oy+20}" r="6" fill="#febc2e"/>
      <circle cx="{ox+62}" cy="{oy+20}" r="6" fill="#28c840"/>
      <text x="{ox + w/2:.0f}" y="{oy+26}" text-anchor="middle" font-family="{MONO}" font-size="15" fill="{t['muted']}">~/vast — zsh</text>"""
    return "".join(kf), f"<g>{box}{''.join(out)}</g>", h


def hero(t, mobile=False):
    phrases = ["shipping VastPay &amp; VastMenu", "automating the release train",
               "building Kallm Agent, solo"]
    cycle = 9
    style = f"""
    .ph{{opacity:0;animation:ph {cycle}s infinite}} .ph0{{opacity:1}}
    .ph1{{animation-delay:{cycle/3}s}} .ph2{{animation-delay:{2*cycle/3}s}}
    @keyframes ph{{0%{{opacity:0;transform:translateY(8px)}}4%,29%{{opacity:1;transform:none}}33%,100%{{opacity:0}}}}
    .cur{{animation:blink 1.1s steps(1) infinite}}
    @keyframes blink{{50%{{opacity:0}}}}
    .pulse{{animation:pulse 3s ease-in-out infinite}}
    @keyframes pulse{{50%{{opacity:.35}}}}
    """
    if mobile:
        W, lx = 600, 32
        eyebrow, eb_y, eb_size = "CAIRO · SOFTWARE ENGINEER @ VAST GROUP", 64, 17
        name_y, name_size, ar_y = 146, 62, 194
        tag = ["I ship restaurant ordering and",
               "payments, the tooling that releases",
               "them, and AI agents that do real work."]
        tag_y, tag_size, tag_step, now_y, now_size = 246, 25, 34, 362, 20
        kf, term, th = terminal(t, 32, 394, 536, 18, 30)
        H = 394 + th + 34
    else:
        W, lx = 1200, 58
        eyebrow, eb_y, eb_size = "CAIRO, EGYPT · SOFTWARE ENGINEER @ VAST GROUP", 82, 16
        name_y, name_size, ar_y = 162, 74, 208
        tag = ["I ship restaurant ordering and payments,",
               "the tooling that releases them,",
               "and AI agents that do real work."]
        tag_y, tag_size, tag_step, now_y, now_size = 256, 25, 34, 372, 20
        kf, term, th = terminal(t, 680, 52, 472, 17, 30)
        H = 420
    style += kf
    px = lx + now_size * 3.6
    ph = "".join(f'<text class="ph ph{i}" x="{px:.0f}" y="{now_y}" font-family="{MONO}" font-size="{now_size}" '
                 f'fill="{t["ink"]}">{p}</text>' for i, p in enumerate(phrases))
    tagline = "".join(f'<text x="{lx}" y="{tag_y + i*tag_step}" font-size="{tag_size}" fill="{t["ink"]}">{l}</text>'
                      for i, l in enumerate(tag))
    body = f"""{defs(t)}{frame(W, H, t)}
    <circle cx="{W*0.18:.0f}" cy="70" r="330" fill="url(#glowA)"/>
    <circle cx="{W*0.9:.0f}" cy="{H-20}" r="320" fill="url(#glowB)"/>
    <g font-family="{SANS}">
      <circle class="pulse" cx="{lx+4}" cy="{eb_y-6}" r="5" fill="{t['ok']}"/>
      <text x="{lx+18}" y="{eb_y}" font-family="{MONO}" font-size="{eb_size}" letter-spacing="1.5" fill="{t['muted']}">{eyebrow}</text>
      <text x="{lx-4}" y="{name_y}" font-size="{name_size}" font-weight="800" letter-spacing="-2" fill="url(#brand)">Mostafa Adly</text>
      <text x="{lx}" y="{ar_y}" font-size="30" fill="{t['muted']}">مصطفى عدلي</text>
      {tagline}
      <text x="{lx}" y="{now_y}" font-family="{MONO}" font-size="{now_size}" font-weight="700" fill="url(#brand)">now ▸</text>
      {ph}
    </g>
    {term}
    <rect x="{lx-4}" y="{H-22}" width="{W-2*(lx-4)}" height="3" rx="1.5" fill="url(#brand)" opacity=".85"/>"""
    return svg(W, H, "Mostafa Adly, software engineer at Vast Group in Cairo. "
               "I ship restaurant ordering and payments, the tooling that releases them, "
               "and AI agents that do real work.", body, style)


# ---------------------------------------------------------------- stats

def stats(t, data, mobile=False):
    years = sorted(data["years"].items())
    vals = [v for _, v in years]
    as_of = dt.date.fromisoformat(data["as_of"])
    cur = str(as_of.year)
    if mobile:
        W, H = 600, 670
        x0, x1, base, top = 40, 560, 600, 392
        s = dict(cap=18, sub=28, small=21, asof=18, val=20, year=18)
        ys = dict(cap=70, num=166, sub=212, small=248, asof=292)
    else:
        W, H = 1200, 350
        x0, x1, base, top = 520, 1144, 280, 104
        s = dict(cap=16, sub=26, small=19, asof=16, val=17, year=16)
        ys = dict(cap=80, num=176, sub=220, small=254, asof=306)
    slot = (x1 - x0) / len(years)
    bw = min(62, slot - 18)
    peak = max(vals) or 1
    bars, labels = [], []
    # Bars are static on purpose: GitHub can freeze animations in off-screen
    # images at frame 0, which would leave a grow-in bar invisible.
    for i, (y, v) in enumerate(years):
        cx = x0 + slot * i + slot / 2
        h = 0 if v == 0 else max(5, (base - top) * v / peak)
        r = min(4, h / 2)
        x = cx - bw / 2
        if h:
            bars.append(f'<path fill="{t["bar"]}" d="M{x:.1f} {base}V{base-h+r:.1f}q0-{r:.1f} {r:.1f}-{r:.1f}'
                        f'h{bw-2*r:.1f}q{r:.1f} 0 {r:.1f} {r:.1f}V{base}z"/>')
        labels.append(f'<text x="{cx:.1f}" y="{base-h-10:.1f}" text-anchor="middle" font-family="{MONO}" '
                      f'font-size="{s["val"]}" fill="{t["ink"]}">{v:,}</text>')
        labels.append(f'<text x="{cx:.1f}" y="{base+30}" text-anchor="middle" font-family="{MONO}" '
                      f'font-size="{s["year"]}" fill="{t["muted"]}">{f"{y}*" if y == cur else y}</text>')
    nice = as_of.strftime("%b %-d, %Y")
    body = f"""{defs(t, glow=True)}{frame(W, H, t)}
    <circle cx="180" cy="{200 if mobile else 300}" r="320" fill="url(#glowA)"/>
    <g font-family="{SANS}">
      <text x="56" y="{ys['cap']}" font-family="{MONO}" font-size="{s['cap']}" letter-spacing="2" fill="{t['muted']}">LAST 12 MONTHS</text>
      <text x="50" y="{ys['num']}" font-size="100" font-weight="800" letter-spacing="-3" fill="url(#brand)">{data['last_year']:,}</text>
      <text x="56" y="{ys['sub']}" font-size="{s['sub']}" fill="{t['ink']}">contributions on GitHub</text>
      <text x="56" y="{ys['small']}" font-size="{s['small']}" fill="{t['muted']}">public and private</text>
      <text x="56" y="{ys['asof']}" font-family="{MONO}" font-size="{s['asof']}" fill="{t['muted']}">as of {nice}</text>
      <text x="{x0}" y="{top-40}" font-family="{MONO}" font-size="{s['cap']}" letter-spacing="2" fill="{t['muted']}">CONTRIBUTIONS PER YEAR</text>
      <text x="{x1}" y="{top-40}" text-anchor="end" font-family="{MONO}" font-size="{s['cap']}" fill="{t['muted']}">* {cur} so far</text>
      <path d="M{x0} {base}.5H{x1}" stroke="{t['border']}"/>
      {''.join(bars)}{''.join(labels)}
    </g>"""
    label = (f"{data['last_year']:,} GitHub contributions in the last 12 months. Per year: "
             + ", ".join(f"{y}: {v:,}" for y, v in years) + f" ({cur} so far).")
    return svg(W, H, label, body)


# ---------------------------------------------------------------- cards
# One full-width card per repo. Side-by-side cards can't be made readable on a
# phone (GitHub fixes the <img> width for every <source>), so each card gets a
# stacked phone variant instead.

CARD_GAP = 18  # transparent space under each card except the last


def card(t, c, live, mobile=False, last=False):
    if mobile:
        W, CH, pad = 600, 222, 32
        title_y, title_size, slug_size = 56, 32, 20
        desc_y, desc_size, desc_step = 100, 23, 32
        chip_y, chip_size = 164, 18
        wm_x, wm_y, wm_size = W - 18, 214, 104
    else:
        W, CH, pad = 1200, 176, 40
        title_y, title_size, slug_size = 60, 34, 20
        desc_y, desc_size, desc_step = 102, 24, 32
        chip_y, chip_size = 122, 19
        wm_x, wm_y, wm_size = W + 10, 214, 170
    H = CH + (0 if last else CARD_GAP)
    chips = [(c["lang"], LANG_COLOR.get(c["lang"], t["muted"]))]
    if live.get("tag"):
        chips.append((live["tag"], None))
    if live.get("stars"):
        chips.append((f"★ {live['stars']}", None))
    chips.append((c["chip"], None))
    cx, out, ch = pad, [], chip_size * 2
    for text, dot in chips:
        tw = len(text) * chip_size * 0.6 + (chip_size * 2.4 if dot else chip_size * 1.6)
        out.append(f'<rect x="{cx:.0f}" y="{chip_y}" width="{tw:.0f}" height="{ch}" rx="{ch/2:.0f}" '
                   f'fill="{t["bg"]}" stroke="{t["border"]}"/>')
        tx = cx + chip_size * 0.8
        if dot:
            out.append(f'<circle cx="{cx + chip_size*1.1:.0f}" cy="{chip_y + ch/2:.0f}" r="{chip_size*0.35:.1f}" fill="{dot}"/>')
            tx = cx + chip_size * 1.9
        out.append(f'<text x="{tx:.0f}" y="{chip_y + ch/2 + chip_size*0.35:.1f}" font-family="{MONO}" '
                   f'font-size="{chip_size}" fill="{t["ink"]}">{escape(text)}</text>')
        cx += tw + 10
    lines = c["lines"] if mobile else [" ".join(c["lines"])]
    desc = "".join(f'<text x="{pad}" y="{desc_y + i*desc_step}" font-size="{desc_size}" fill="{t["muted"]}">'
                   f'{escape(l)}</text>' for i, l in enumerate(lines))
    slug = (f'<tspan dx="14" font-size="{slug_size}" font-weight="400" fill="{t["muted"]}">{c["repo"]}</tspan>'
            if c["repo"] != c["title"] else "")
    body = f"""{defs(t, glow=False)}
    <clipPath id="card"><rect x=".5" y=".5" width="{W-1}" height="{CH-1}" rx="12"/></clipPath>
    <rect x=".5" y=".5" width="{W-1}" height="{CH-1}" rx="12" fill="{t['panel']}" stroke="{t['border']}"/>
    <g clip-path="url(#card)">
      <rect x="0" y="0" width="{W}" height="4" fill="url(#brand)"/>
      <text x="{wm_x}" y="{wm_y}" text-anchor="end" font-family="{SANS}" font-size="{wm_size}" font-weight="700" fill="{t['g2']}" fill-opacity="{0.09 if t is THEMES['dark'] else 0.08}">{c['watermark']}</text>
    </g>
    <g font-family="{SANS}">
      <text x="{pad}" y="{title_y}" font-size="{title_size}" font-weight="700" fill="{t['ink']}">{escape(c['title'])}{slug}</text>
      <text x="{W-pad}" y="{title_y-2}" text-anchor="end" font-size="26" fill="{t['muted']}">↗</text>
      {desc}
    </g>
    {''.join(out)}"""
    return svg(W, H, f"{c['title']}: " + " ".join(c["lines"]), body)


# ---------------------------------------------------------------- links

LINKS = [  # (file id, label, brand color for the dot)
    ("linkedin", "LinkedIn", "#0a66c2"), ("devto", "dev.to", None),
    ("stackoverflow", "Stack Overflow", "#f48024"), ("kaggle", "Kaggle", "#20beff"),
    ("leetcode", "LeetCode", "#f5c518"),
]


def pill(t, label, color):
    w = int(len(label) * 8.6 + 64)
    dot = color or t["ink"]
    body = f"""<g transform="translate(0 16)">
    <rect x=".5" y=".5" width="{w-1}" height="35" rx="18" fill="{t['panel']}" stroke="{t['border']}"/>
    <circle cx="20" cy="18" r="5" fill="{dot}"/>
    <text x="34" y="23" font-family="{MONO}" font-size="14" fill="{t['ink']}">{escape(label)}</text>
    <text x="{w-16}" y="23" text-anchor="end" font-family="{SANS}" font-size="13" fill="{t['muted']}">↗</text></g>"""
    return svg(w, 52, label, body)


# ---------------------------------------------------------------- footer

def footer(t, mobile=False):
    W, H = (600, 130) if mobile else (1200, 130)
    style = ".w{animation:drift 8s linear infinite}@keyframes drift{to{transform:translateX(-300px)}}"
    wave = "M0 104 " + " ".join(f"q75 -26 150 0 t150 0" for _ in range(6))
    body = f"""{defs(t, glow=False)}
    <g class="w"><path d="{wave}" fill="none" stroke="url(#brand)" stroke-width="2.5" opacity=".6"/></g>
    <text x="{W//2}" y="56" text-anchor="middle" font-family="{SANS}" font-size="{30 if mobile else 28}" fill="{t['ink']}">شكراً للزيارة · thanks for stopping by</text>"""
    return svg(W, H, "Thanks for stopping by", body, style)


def main():
    data, ok = load_data()
    ASSETS.mkdir(exist_ok=True)
    for name, t in THEMES.items():
        (ASSETS / f"hero-{name}.svg").write_text(render(hero(t)))
        (ASSETS / f"stats-{name}.svg").write_text(render(stats(t, data)))
        (ASSETS / f"footer-{name}.svg").write_text(render(footer(t)))
        for i, c in enumerate(CARDS):
            (ASSETS / f"card-{c['repo']}-{name}.svg").write_text(
                render(card(t, c, data["repos"].get(c["repo"], {}), last=i == len(CARDS) - 1)))
        for lid, label, color in LINKS:
            (ASSETS / f"link-{lid}-{name}.svg").write_text(render(pill(t, label, color)))
    # Mirror the chart's numbers into the README alt text: GitHub ignores an
    # <img> SVG's own aria-label, so this is what screen readers get.
    readme = ROOT / "README.md"
    alt = stats(THEMES["light"], data)["label"]
    readme.write_text(re.sub(r'alt="[^"]*"( src="assets/stats-light.svg")', f'alt="{escape(alt)}"\\1',
                             readme.read_text()))
    L, D = THEMES["light"], THEMES["dark"]
    (ASSETS / "hero-mobile.svg").write_text(dual(hero(L, True), hero(D, True)))
    (ASSETS / "footer-mobile.svg").write_text(dual(footer(L, True), footer(D, True)))
    (ASSETS / "stats-mobile.svg").write_text(dual(stats(L, data, True), stats(D, data, True)))
    for i, c in enumerate(CARDS):
        live, last = data["repos"].get(c["repo"], {}), i == len(CARDS) - 1
        (ASSETS / f"card-{c['repo']}-mobile.svg").write_text(
            dual(card(L, c, live, True, last), card(D, c, live, True, last)))
    print(f"built assets as of {data['as_of']}: {data['last_year']:,} contributions")
    if not ok:
        raise SystemExit(1)  # the page still has the cached numbers; the failed run alerts the owner


if __name__ == "__main__":
    main()
