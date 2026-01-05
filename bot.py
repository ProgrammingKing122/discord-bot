import os
import json
import math
import time
import asyncio
from io import BytesIO
from typing import Optional, Dict, Tuple, List, Set

import discord
import aiohttp
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont


TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1443765937793667194
MIDDLEMAN_ROLE_ID = 1457241934832861255
LOG_CHANNEL_ID = 1457242121009631312

BASE = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE, "fonts", "Inter_24pt-ExtraBoldItalic.ttf")
RANKED_DB_PATH = os.path.join(BASE, "ranked_stats.json")


intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)


def _i(x, d=0):
    try:
        return int(x)
    except:
        return d


def _f(x, d=0.0):
    try:
        return float(x)
    except:
        return d


def _clamp(v, a, b):
    return a if v < a else b if v > b else v


def F(size: int):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except:
        return ImageFont.load_default()


def TL(d: ImageDraw.ImageDraw, text: str, font) -> float:
    try:
        return float(d.textlength(text, font=font))
    except:
        return float(len(text) * 10)


def ELLIPSIZE(d: ImageDraw.ImageDraw, text: str, font, max_w: float) -> str:
    if TL(d, text, font) <= max_w:
        return text
    t = text
    while t and TL(d, t + "…", font) > max_w:
        t = t[:-1]
    return (t + "…") if t else "…"


def FIT(d: ImageDraw.ImageDraw, text: str, start: int, min_size: int, max_w: float):
    s = start
    while s >= min_size:
        f = F(s)
        if TL(d, text, f) <= max_w:
            return f, text
        s -= 2
    f = F(min_size)
    return f, ELLIPSIZE(d, text, f, max_w)


def FIT_CENTER_X(d: ImageDraw.ImageDraw, text: str, font, center_x: int) -> int:
    return int(center_x - TL(d, text, font) / 2)


def fmt_num(n):
    try:
        x = float(n)
    except:
        return str(n)
    if x >= 1_000_000_000:
        return f"{x/1_000_000_000:.1f}B"
    if x >= 1_000_000:
        return f"{x/1_000_000:.1f}M"
    if x >= 10_000:
        return f"{x/1_000:.1f}K"
    if x.is_integer():
        return str(int(x))
    return f"{x:.2f}".rstrip("0").rstrip(".")


def SAFE_TEAM(name: str, fallback: str) -> str:
    if not isinstance(name, str):
        return fallback
    s = name.strip()
    if not s:
        return fallback
    lowered = s.lower()
    banned = [
        "nigger", "nigga", "faggot", "fag", "kike", "retard", "tranny",
        "hitler", "nazi", "gas the", "kill all", "genocide", "white power",
    ]
    for b in banned:
        if b in lowered:
            return fallback
    return s


def allowed_mentions_users_only():
    return discord.AllowedMentions(users=True, roles=False, everyone=False)


async def fetch_avatar(session: aiohttp.ClientSession, url: str, size: int):
    async with session.get(url) as r:
        b = await r.read()
    im = Image.open(BytesIO(b)).convert("RGBA")
    if im.size != (size, size):
        im = im.resize((size, size))
    return im


def draw_bg(img):
    W, H = img.size
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, H], fill=(8, 10, 15))
    for y in range(0, H, 2):
        shade = int(12 + (y / H) * 22)
        d.line([(0, y), (W, y)], fill=(shade, shade, shade))
    step = 7
    for x in range(0, W + H, step):
        d.line([(x, 0), (x - H, H)], fill=(10, 10, 16))
    d.rectangle([24, 24, W - 24, H - 24], outline=(35, 40, 54), width=2)


def win_phrase(a_name: str, b_name: str, a_k: int, b_k: int):
    diff = abs(a_k - b_k)
    if a_k == b_k:
        return "DRAW", "#ffd24c"
    w = a_name if a_k > b_k else b_name
    l = b_name if a_k > b_k else a_name
    if diff >= 25:
        return f"{w} OBLITERATED {l}", "#ff3b3b"
    if diff >= 15:
        return f"{w} DESTROYED {l}", "#ff4c4c"
    if diff >= 10:
        return f"{w} SLAMMED {l}", "#ff6a4c"
    if diff >= 6:
        return f"{w} DOMINATED {l}", "#ff9c4c"
    if diff >= 3:
        return f"{w} DEFEATED {l}", "#ffd24c"
    return f"{w} WINS NARROWLY", "#4cff7a"


def pick_mvp(stats: Dict[int, Tuple[int, int]], team: List[int]) -> Optional[int]:
    rows = []
    for uid in team:
        if uid not in stats:
            continue
        k, dth = stats[uid]
        kd = (k / dth) if dth else float(k)
        rows.append((uid, k, kd))
    if len(rows) < 2:
        return None
    rows.sort(key=lambda x: (x[1], x[2]), reverse=True)
    if rows[0][1] == rows[1][1] and abs(rows[0][2] - rows[1][2]) < 1e-9:
        return None
    return rows[0][0]


def status_strip(k: int, dth: int, is_mvp: bool):
    if k == 0 and dth >= 2:
        return "#ff4c4c", "☠"
    if is_mvp:
        return "#ffd700", "👑"
    if k > dth:
        return "#4cff7a", ""
    if k == dth:
        return "#ffd24c", ""
    return "#ff4c4c", ""


class RankedStore:
    def __init__(self, path: str):
        self.path = path
        self.data: Dict[str, dict] = {}
        self.lock = asyncio.Lock()

    async def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, dict):
                self.data = obj
            else:
                self.data = {}
        except:
            self.data = {}

    async def save(self):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            os.replace(tmp, self.path)
        except:
            pass

    def _row(self, uid: int) -> dict:
        k = str(uid)
        r = self.data.get(k)
        if not isinstance(r, dict):
            r = {"kills": 0, "deaths": 0, "matches": 0, "wins": 0, "losses": 0, "draws": 0}
            self.data[k] = r
        for kk in ("kills", "deaths", "matches", "wins", "losses", "draws"):
            r[kk] = _i(r.get(kk, 0), 0)
            if r[kk] < 0:
                r[kk] = 0
        return r

    async def get(self, uid: int) -> dict:
        async with self.lock:
            return dict(self._row(uid))

    async def record_match(self, uid: int, kills: int, deaths: int, outcome: str):
        async with self.lock:
            r = self._row(uid)
            r["kills"] += max(0, _i(kills, 0))
            r["deaths"] += max(0, _i(deaths, 0))
            r["matches"] += 1
            if outcome == "W":
                r["wins"] += 1
            elif outcome == "L":
                r["losses"] += 1
            else:
                r["draws"] += 1
        await self.save()

    async def win_likelihood(self, uid: int) -> int:
        async with self.lock:
            r = self._row(uid)
            k = r["kills"]
            d = max(1, r["deaths"])
            m = max(1, r["matches"])
            wins = r["wins"]
            draws = r["draws"]
        kd = k / d
        wr = (wins + 0.5 * draws) / m
        kd_score = _clamp((math.log(max(0.08, kd)) / math.log(2.0)) * 0.18, -0.45, 0.55)
        wr_score = _clamp((wr - 0.5) * 0.90, -0.40, 0.40)
        conf = _clamp(math.sqrt(m / 20.0), 0.15, 1.0)
        base = 0.5 + (kd_score + wr_score) * conf
        return int(round(_clamp(base, 0.05, 0.95) * 100))


RANKED = RankedStore(RANKED_DB_PATH)


class Layout:
    def __init__(self):
        self.W = 1920
        self.H = 1080
        self.margin = 120
        self.header_top_y = 54
        self.header_line_1_y = 170
        self.header_line_2_y = 234
        self.header_line_3_y = 298
        self.header_line_4_y = 360
        self.teams_title_y = 390
        self.vs_y = 430
        self.divider_y = 470
        self.wager_rows_y = 520
        self.wager_row_h = 112
        self.avatar_wager = 88
        self.results_title_y = 44
        self.results_head_y = 190
        self.results_header_y = 290
        self.results_row_start_y = 374
        self.results_row_h = 126
        self.avatar_results = 92


LAY = Layout()


def compute_tables():
    W = LAY.W
    m = LAY.margin
    table_w = (W - m * 3) // 2
    lx = m
    rx = lx + table_w + m
    return table_w, lx, rx


def phase_label(p: str):
    if p == "LOBBY":
        return "LOBBY"
    if p == "WAIT_MM":
        return "MIDDLEMAN REQUIRED"
    if p == "READY":
        return "READY UP"
    if p == "LIVE":
        return "LIVE"
    if p == "STATS":
        return "ENTER STATS"
    if p == "ENDED":
        return "ENDED"
    return p


class PrizeConfirmView(discord.ui.View):
    def __init__(self, winner_id: int):
        super().__init__(timeout=None)
        self.winner_id = winner_id
        self.confirmed = False
        btn = discord.ui.Button(label="Prize Received", style=discord.ButtonStyle.success)
        btn.callback = self._confirm
        self.add_item(btn)

    async def _confirm(self, i: discord.Interaction):
        if i.user.id != self.winner_id:
            return await i.response.send_message("Winner only", ephemeral=True)
        if self.confirmed:
            return await i.response.send_message("Already confirmed", ephemeral=True)
        self.confirmed = True
        await i.response.edit_message(content="✅ Prize confirmed as received.", view=None)



async def post_match_logs(
    *,
    guild: discord.Guild,
    team_a_name: str,
    team_b_name: str,
    team_a_ids: List[int],
    team_b_ids: List[int],
    stats: Dict[int, Tuple[int, int]],
    middleman_id: Optional[int],
    winner_id: Optional[int],
    results_image: discord.File
):
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if not channel:
        return

    ta_k = sum(stats[u][0] for u in team_a_ids if u in stats)
    tb_k = sum(stats[u][0] for u in team_b_ids if u in stats)

    if ta_k > tb_k:
        win_text = team_a_name
    elif tb_k > ta_k:
        win_text = team_b_name
    else:
        win_text = "DRAW"

    mm_name = "None"
    if middleman_id:
        m = guild.get_member(middleman_id)
        if m:
            mm_name = m.display_name

    embed = discord.Embed(
        title="Match Results",
        description=f"**{team_a_name} {ta_k} - {tb_k} {team_b_name}**",
        colour=discord.Colour.orange()
    )

    embed.add_field(
        name="Winner",
        value=win_text,
        inline=False
    )

    embed.add_field(
        name="Middleman",
        value=mm_name,
        inline=False
    )

    embed.add_field(
        name="Evidence",
        value="Reply to this log message with a video attachment as evidence.",
        inline=False
    )

    embed.set_image(url="attachment://results.png")

    view = PrizeConfirmView(winner_id) if winner_id else None

    try:
        await channel.send(
            embed=embed,
            file=results_image,
            view=view
        )
    except Exception:
        pass


async def render_wager_image(v) -> Image.Image:
    W, H = LAY.W, LAY.H
    img = Image.new("RGB", (W, H))
    draw_bg(img)
    d = ImageDraw.Draw(img)

    a_name = SAFE_TEAM(v.a, "TEAM A")
    b_name = SAFE_TEAM(v.b, "TEAM B")

    top = f"WAGER {v.size}v{v.size} — {phase_label(v.phase)}"
    t_font, t_text = FIT(d, top, 96, 68, W - 160)
    d.text((80, LAY.header_top_y), t_text, fill="white", font=t_font)

    p_font, p_text = FIT(d, f"Prize: {v.prize}", 52, 34, W - 160)
    d.text((80, LAY.header_line_1_y), p_text, fill="#b5b9c7", font=p_font)

    h_font, h_text = FIT(d, f"Host: {v.host}", 52, 34, W - 160)
    d.text((80, LAY.header_line_2_y), h_text, fill="#b5b9c7", font=h_font)

    mm_text = "None" if v.no_middleman else (v.middleman_name or "Pending")
    m_font, m_text = FIT(d, f"Middleman: {mm_text}", 52, 34, W - 160)
    d.text((80, LAY.header_line_3_y), m_text, fill="#b5b9c7", font=m_font)

    if v.phase == "WAIT_MM":
        warn = "Host must pick a middleman or press No Middleman."
        wf, wt = FIT(d, warn, 46, 30, W - 160)
        d.text((80, LAY.header_line_4_y), wt, fill="#ffd24c", font=wf)
    elif v.phase in ("READY", "LIVE", "STATS"):
        fighters = list(v.fighters_set)
        ready_cnt = sum(1 for u in fighters if v.ready.get(u, False))
        line = f"Ready: {ready_cnt}/{len(fighters)}"
        rf, rt = FIT(d, line, 52, 34, W - 160)
        d.text((80, LAY.header_line_4_y), rt, fill="#d8dbe6", font=rf)

    table_w, lx, rx = compute_tables()

    la_font, la_text = FIT(d, a_name, 72, 46, table_w)
    lb_font, lb_text = FIT(d, b_name, 72, 46, table_w)

    d.text((lx, LAY.teams_title_y), la_text, fill="#4cc2ff", font=la_font)
    d.text((rx, LAY.teams_title_y), lb_text, fill="#ffb84c", font=lb_font)

    vs_font, vs_text = FIT(d, "VS", 120, 84, 260)
    d.text((FIT_CENTER_X(d, vs_text, vs_font, W // 2), LAY.vs_y), vs_text, fill="white", font=vs_font)

    d.line([(lx, LAY.divider_y), (lx + table_w, LAY.divider_y)], fill=(76, 194, 255), width=5)
    d.line([(rx, LAY.divider_y), (rx + table_w, LAY.divider_y)], fill=(255, 184, 76), width=5)

    ay = LAY.wager_rows_y
    by = LAY.wager_rows_y
    avatar_size = LAY.avatar_wager
    row_h = LAY.wager_row_h

    name_max = table_w - avatar_size - 40 - 240

    async with aiohttp.ClientSession() as s:
        for uid in v.team_a[: v.size]:
            m = v.guild.get_member(uid) or await v.guild.fetch_member(uid)
            av = await fetch_avatar(s, m.display_avatar.url, avatar_size)
            img.paste(av, (lx, ay), av)
            nf, nt = FIT(d, m.display_name, 50, 34, name_max)
            d.text((lx + avatar_size + 22, ay + 18), nt, fill="white", font=nf)

            if v.phase in ("READY", "LIVE", "STATS"):
                st = "READY" if v.ready.get(uid, False) else "NOT READY"
                sf, stext = FIT(d, st, 34, 24, 220)
                scol = "#4cff7a" if v.ready.get(uid, False) else "#ff4c4c"
                d.text((lx + table_w - 12 - TL(d, stext, sf), ay + 26), stext, fill=scol, font=sf)

            ay += row_h
            if ay > H - 220:
                break

        for uid in v.team_b[: v.size]:
            m = v.guild.get_member(uid) or await v.guild.fetch_member(uid)
            av = await fetch_avatar(s, m.display_avatar.url, avatar_size)
            img.paste(av, (rx, by), av)
            nf, nt = FIT(d, m.display_name, 50, 34, name_max)
            d.text((rx + avatar_size + 22, by + 18), nt, fill="white", font=nf)

            if v.phase in ("READY", "LIVE", "STATS"):
                st = "READY" if v.ready.get(uid, False) else "NOT READY"
                sf, stext = FIT(d, st, 34, 24, 220)
                scol = "#4cff7a" if v.ready.get(uid, False) else "#ff4c4c"
                d.text((rx + table_w - 12 - TL(d, stext, sf), by + 26), stext, fill=scol, font=sf)

            by += row_h
            if by > H - 220:
                break

    if not v.team_a:
        d.text((lx, ay + 8), "No players yet", fill="#666", font=F(44))
    if not v.team_b:
        d.text((rx, by + 8), "No players yet", fill="#666", font=F(44))

    footer = "Brought to you by levi"
    ff = F(26)
    d.text((FIT_CENTER_X(d, footer, ff, W // 2), H - 60), footer, fill="#d0d0d0", font=ff)
    return img


async def render_results_image(v) -> Image.Image:
    W, H = LAY.W, LAY.H
    img = Image.new("RGB", (W, H))
    draw_bg(img)
    d = ImageDraw.Draw(img)

    table_w, lx, rx = compute_tables()

    a_name = SAFE_TEAM(v.a, "TEAM A")
    b_name = SAFE_TEAM(v.b, "TEAM B")

    ta_k = sum(v.stats[u][0] for u in v.team_a[: v.size] if u in v.stats)
    tb_k = sum(v.stats[u][0] for u in v.team_b[: v.size] if u in v.stats)

    title, title_col = win_phrase(a_name, b_name, ta_k, tb_k)
    title_font, title_txt = FIT(d, title, 110, 64, W - 200)
    d.text((FIT_CENTER_X(d, title_txt, title_font, W // 2), LAY.results_title_y), title_txt, fill=title_col, font=title_font)

    head_left = f"{a_name} — {ta_k} KILLS"
    head_right = f"{b_name} — {tb_k} KILLS"
    hl_font, hl_txt = FIT(d, head_left, 62, 40, table_w)
    hr_font, hr_txt = FIT(d, head_right, 62, 40, table_w)
    d.text((lx, LAY.results_head_y), hl_txt, fill="#4cc2ff", font=hl_font)
    d.text((rx, LAY.results_head_y), hr_txt, fill="#ffb84c", font=hr_font)

    mvp_a = pick_mvp(v.stats, v.team_a[: v.size])
    mvp_b = pick_mvp(v.stats, v.team_b[: v.size])

    header_y = LAY.results_header_y
    row_start = LAY.results_row_start_y

    avatar_size = LAY.avatar_results
    row_h = LAY.results_row_h

    hdr_font = F(42)

    name_x = avatar_size + 26

    name_left = name_x
    name_right_edge = table_w - 420
    name_w = max(120, (name_right_edge - name_left) - 10)

    k_col_left = table_w - 360
    k_col_right = table_w - 290
    d_col_left = table_w - 220
    d_col_right = table_w - 150
    kd_col_left = table_w - 90
    kd_col_right = table_w - 10

    for bx in (lx, rx):
        d.text((bx + name_x, header_y), "NAME", fill="#b5b9c7", font=hdr_font)
        d.text((bx + k_col_left, header_y), "K", fill="#b5b9c7", font=hdr_font)
        d.text((bx + d_col_left, header_y), "D", fill="#b5b9c7", font=hdr_font)
        d.text((bx + kd_col_left, header_y), "KD", fill="#b5b9c7", font=hdr_font)

    d.line([(lx, header_y + 64), (lx + table_w, header_y + 64)], fill=(76, 194, 255), width=5)
    d.line([(rx, header_y + 64), (rx + table_w, header_y + 64)], fill=(255, 184, 76), width=5)

    async with aiohttp.ClientSession() as s:
        for base_x, team, mvp_u in ((lx, v.team_a[: v.size], mvp_a), (rx, v.team_b[: v.size], mvp_b)):
            y = row_start
            for uid in team:
                if uid not in v.stats:
                    continue

                m = v.guild.get_member(uid) or await v.guild.fetch_member(uid)
                k, dth = v.stats[uid]
                kd_val = (k / dth) if dth else float(k)
                kd_txt = "∞" if (dth == 0 and k > 0) else fmt_num(kd_val)

                is_mvp = (uid == mvp_u)
                strip_col, badge = status_strip(int(k), int(dth), is_mvp)

                av = await fetch_avatar(s, m.display_avatar.url, avatar_size)
                img.paste(av, (base_x, y), av)

                d.rectangle([base_x + table_w - 12, y, base_x + table_w, y + avatar_size], fill=strip_col)

                if badge:
                    bfont, btxt = FIT(d, badge, 52, 40, 60)
                    d.text((base_x + table_w - 62, y + 18), btxt, fill=strip_col, font=bfont)

                nf, nt = FIT(d, m.display_name, 50, 32, name_w)
                name_fill = "#ffd700" if is_mvp else "white"
                d.text((base_x + name_x, y + 22), nt, fill=name_fill, font=nf)

                k_txt = fmt_num(k)
                d_txt = fmt_num(dth)

                kf, kt = FIT(d, k_txt, 42, 18, (k_col_right - k_col_left))
                df, dt = FIT(d, d_txt, 42, 18, (d_col_right - d_col_left))
                kdf, kdt = FIT(d, kd_txt, 42, 18, (kd_col_right - kd_col_left))

                d.text((base_x + k_col_left, y + 22), kt, fill="white", font=kf)
                d.text((base_x + d_col_left, y + 22), dt, fill="white", font=df)
                d.text((base_x + kd_col_left, y + 22), kdt, fill="white", font=kdf)

                y += row_h
                if y > H - 160:
                    break

    footer = "Brought to you by levi"
    ff = F(28)
    d.text((FIT_CENTER_X(d, footer, ff, W // 2), H - 68), footer, fill="#d0d0d0", font=ff)
    return img


async def render_rankedstats_image(member: discord.Member, row: dict, winp: int) -> Image.Image:
    W, H = 1200, 700
    img = Image.new("RGB", (W, H))
    draw_bg(img)
    d = ImageDraw.Draw(img)

    kills = _i(row.get("kills", 0), 0)
    deaths = _i(row.get("deaths", 0), 0)
    matches = _i(row.get("matches", 0), 0)
    wins = _i(row.get("wins", 0), 0)
    losses = _i(row.get("losses", 0), 0)
    draws = _i(row.get("draws", 0), 0)

    kd = kills / max(1, deaths)

    title_f, title_t = FIT(d, "RANKED STATS", 86, 62, W - 80)
    d.text((60, 46), title_t, fill="white", font=title_f)

    async with aiohttp.ClientSession() as s:
        av = await fetch_avatar(s, member.display_avatar.url, 180)
    img.paste(av, (60, 160), av)

    name_f, name_t = FIT(d, member.display_name, 58, 40, W - 300)
    d.text((270, 170), name_t, fill="white", font=name_f)

    line_x = 270
    line_y = 250
    row_gap = 58

    def stat_line(label, value, col):
        nonlocal line_y
        lf, lt = FIT(d, label, 38, 30, 220)
        vf, vt = FIT(d, value, 44, 34, 520)
        d.text((line_x, line_y), lt, fill="#b5b9c7", font=lf)
        d.text((line_x + 230, line_y - 4), vt, fill=col, font=vf)
        line_y += row_gap

    stat_line("Kills", fmt_num(kills), "#4cff7a")
    stat_line("Deaths", fmt_num(deaths), "#ff4c4c")
    stat_line("KD", f"{kd:.2f}".rstrip("0").rstrip("."), "#ffd24c")
    stat_line("Matches", fmt_num(matches), "#d8dbe6")
    stat_line("W / L / D", f"{wins} / {losses} / {draws}", "#d8dbe6")
    stat_line("Win chance", f"{winp}%", "#4cc2ff")

    footer = "Brought to you by levi"
    ff = F(26)
    d.text((FIT_CENTER_X(d, footer, ff, W // 2), H - 60), footer, fill="#d0d0d0", font=ff)
    return img


def is_controller(v, uid: int) -> bool:
    if uid == v.host_id:
        return True
    if v.middleman_id and uid == v.middleman_id:
        return True
    return False


class TeamManager:
    def __init__(self, size: int):
        self.size = max(1, _i(size, 1))
        self.team_a: List[int] = []
        self.team_b: List[int] = []

    def fighters_set(self) -> Set[int]:
        return set(self.team_a[: self.size] + self.team_b[: self.size])

    def is_full(self) -> bool:
        return len(self.team_a) >= self.size and len(self.team_b) >= self.size

    def join(self, uid: int, side: str) -> Tuple[bool, str]:
        if side == "A":
            if uid in self.team_b:
                self.team_b.remove(uid)
            if uid in self.team_a:
                return True, "Already in Team A."
            if len(self.team_a) >= self.size:
                return False, "Team A is full."
            self.team_a.append(uid)
            return True, "Joined Team A."
        else:
            if uid in self.team_a:
                self.team_a.remove(uid)
            if uid in self.team_b:
                return True, "Already in Team B."
            if len(self.team_b) >= self.size:
                return False, "Team B is full."
            self.team_b.append(uid)
            return True, "Joined Team B."


class MiddlemanManager:
    def __init__(self):
        self.middleman_id: Optional[int] = None
        self.no_middleman: bool = False
        self.locked: bool = False

    def decided(self) -> bool:
        return self.no_middleman or (self.middleman_id is not None)

    def set_no_mm(self) -> bool:
        if self.locked:
            return False
        self.middleman_id = None
        self.no_middleman = True
        return True

    def set_mm(self, uid: int) -> bool:
        if self.locked:
            return False
        self.middleman_id = uid
        self.no_middleman = False
        return True

    def lock(self):
        self.locked = True


class ReadyManager:
    def __init__(self):
        self.ready: Dict[int, bool] = {}

    def init_for(self, fighters: Set[int]):
        for uid in fighters:
            if uid not in self.ready:
                self.ready[uid] = False
        gone = [u for u in list(self.ready.keys()) if u not in fighters]
        for u in gone:
            self.ready.pop(u, None)

    def set_ready(self, uid: int, val: bool):
        if uid in self.ready:
            self.ready[uid] = bool(val)

    def all_ready(self, fighters: Set[int]) -> bool:
        if not fighters:
            return False
        for u in fighters:
            if not self.ready.get(u, False):
                return False
        return True


class StatsManager:
    def __init__(self):
        self.stats: Dict[int, Tuple[int, int]] = {}

    def set(self, uid: int, kills: int, deaths: int):
        k = max(0, _i(kills, 0))
        d = max(0, _i(deaths, 0))
        self.stats[uid] = (k, d)

    def ensure(self, uid: int):
        if uid not in self.stats:
            self.stats[uid] = (0, 0)

    def total_kills(self, team: List[int], size: int) -> int:
        s = 0
        for u in team[: size]:
            if u in self.stats:
                s += _i(self.stats[u][0], 0)
        return s


class WagerState:
    def __init__(self):
        self.phase = "LOBBY"
        self.pinged_ready = False
        self.ending = False
        self.created_at = int(time.time())

    def set_phase(self, p: str):
        self.phase = p


class JoinButton(discord.ui.Button):
    def __init__(self, label: str, side: str):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.side = side

    async def callback(self, i: discord.Interaction):
        v = self.view
        async with v.lock:
            if v.state.ending:
                return await i.response.send_message("Ending...", ephemeral=True)
            if v.phase not in ("LOBBY", "WAIT_MM"):
                return await i.response.send_message("Match locked.", ephemeral=True)
            ok, msg = v.teams.join(i.user.id, self.side)
            if not ok:
                return await i.response.send_message(msg, ephemeral=True)
        try:
            await i.response.defer()
        except:
            pass
        await v.update_state_and_card()


class PickMiddlemanButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Pick Middleman", style=discord.ButtonStyle.secondary)

    async def callback(self, i: discord.Interaction):
        v = self.view
        if i.user.id != v.host_id:
            return await i.response.send_message("Host only", ephemeral=True)
        async with v.lock:
            if v.state.ending:
                return await i.response.send_message("Ending...", ephemeral=True)
            if v.mm.locked:
                return await i.response.send_message("Middleman locked.", ephemeral=True)
            if v.phase not in ("LOBBY", "WAIT_MM"):
                return await i.response.send_message("Not allowed now.", ephemeral=True)
        await i.response.defer(ephemeral=True)
        await i.followup.send("Select middleman", view=MMView(v), ephemeral=True)


class NoMiddlemanButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="No Middleman", style=discord.ButtonStyle.secondary)

    async def callback(self, i: discord.Interaction):
        v = self.view
        if i.user.id != v.host_id:
            return await i.response.send_message("Host only", ephemeral=True)
        async with v.lock:
            if v.state.ending:
                return await i.response.send_message("Ending...", ephemeral=True)
            if v.mm.locked:
                return await i.response.send_message("Middleman locked.", ephemeral=True)
            v.mm.set_no_mm()
        try:
            await i.response.defer()
        except:
            pass
        await v.update_state_and_card()


class ReadyUpButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Ready Up", style=discord.ButtonStyle.success)

    async def callback(self, i: discord.Interaction):
        v = self.view
        async with v.lock:
            if v.state.ending:
                return await i.response.send_message("Ending...", ephemeral=True)
            if v.phase != "READY":
                return await i.response.send_message("Not ready phase.", ephemeral=True)
            if i.user.id not in v.fighters_set:
                return await i.response.send_message("Only fighters can ready.", ephemeral=True)
            v.ready_mgr.set_ready(i.user.id, True)
        try:
            await i.response.defer()
        except:
            pass
        await v.update_state_and_card()


class UnreadyButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Unready", style=discord.ButtonStyle.secondary)

    async def callback(self, i: discord.Interaction):
        v = self.view
        async with v.lock:
            if v.state.ending:
                return await i.response.send_message("Ending...", ephemeral=True)
            if v.phase != "READY":
                return await i.response.send_message("Not ready phase.", ephemeral=True)
            if i.user.id not in v.fighters_set:
                return await i.response.send_message("Only fighters can unready.", ephemeral=True)
            v.ready_mgr.set_ready(i.user.id, False)
        try:
            await i.response.defer()
        except:
            pass
        await v.update_state_and_card()


class EndMatchButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="End Match", style=discord.ButtonStyle.danger)

    async def callback(self, i: discord.Interaction):
        v = self.view
        async with v.lock:
            if v.phase in ("STATS", "ENDED"):
                return await i.response.send_message("Already ended.", ephemeral=True)
            if v.state.ending:
                return await i.response.send_message("Finalizing...", ephemeral=True)
            if not is_controller(v, i.user.id):
                return await i.response.send_message("Not allowed", ephemeral=True)
        try:
            await i.response.defer()
        except:
            pass
        await v.hard_end_to_stats()

class CancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Cancel", style=discord.ButtonStyle.danger)

    async def callback(self, i: discord.Interaction):
        v = self.view
        async with v.lock:
            if v.state.ending:
                return await i.response.send_message("Ending...", ephemeral=True)
            if not is_controller(v, i.user.id):
                return await i.response.send_message("Not allowed", ephemeral=True)
            v.state.ending = True
            v.state.set_phase("ENDED")
            v._rebuild_items()
        try:
            await i.message.delete()
        except:
            try:
                await i.response.edit_message(view=None)
            except:
                pass


class MMSelect(discord.ui.UserSelect):
    def __init__(self, v):
        super().__init__(min_values=1, max_values=1, placeholder="Select middleman")
        self.v = v

    async def callback(self, i: discord.Interaction):
        v = self.v
        if i.user.id != v.host_id:
            return await i.response.send_message("Host only", ephemeral=True)

        picked = self.values[0].id
        m = i.guild.get_member(picked) or await i.guild.fetch_member(picked)

        if not any(r.id == MIDDLEMAN_ROLE_ID for r in getattr(m, "roles", [])):
            return await i.response.send_message("Invalid middleman", ephemeral=True)

        async with v.lock:
            if v.state.ending:
                return await i.response.send_message("Ending...", ephemeral=True)
            if v.mm.locked:
                return await i.response.send_message("Middleman locked.", ephemeral=True)
            v.mm.set_mm(m.id)

        await i.response.send_message("Middleman set.", ephemeral=True)
        await v.update_state_and_card()


class MMView(discord.ui.View):
    def __init__(self, v):
        super().__init__(timeout=60)
        self.add_item(MMSelect(v))


class StatsModal(discord.ui.Modal, title="Enter Stats"):
    kills = discord.ui.TextInput(label="Kills", placeholder="0", required=True, max_length=12)
    deaths = discord.ui.TextInput(label="Deaths", placeholder="0", required=True, max_length=12)

    def __init__(self, v, uid: int):
        super().__init__()
        self.v = v
        self.uid = uid

    async def on_submit(self, i: discord.Interaction):
        v = self.v
        if not is_controller(v, i.user.id):
            return await i.response.send_message("Not allowed", ephemeral=True)

        k = _i(str(self.kills.value).strip(), 0)
        dth = _i(str(self.deaths.value).strip(), 0)
        if k < 0:
            k = 0
        if dth < 0:
            dth = 0

        async with v.lock:
            if v.phase != "STATS":
                return await i.response.send_message("Not accepting stats right now.", ephemeral=True)
            v.stats_mgr.set(self.uid, k, dth)

        await i.response.send_message("Saved.", ephemeral=True)


class PlayerPick(discord.ui.Select):
    def __init__(self, v):
        self.v = v
        opts = []
        seen = set()
        ids = list(v.team_a[: v.size] + v.team_b[: v.size])

        for uid in ids:
            if uid in seen:
                continue
            seen.add(uid)
            m = v.guild.get_member(uid)
            if m:
                opts.append(discord.SelectOption(label=m.display_name, value=str(uid)))

        if not opts:
            opts = [discord.SelectOption(label="No players in match", value="0")]

        super().__init__(min_values=1, max_values=1, placeholder="Select war player", options=opts[:25])

    async def callback(self, i: discord.Interaction):
        v = self.v
        if not is_controller(v, i.user.id):
            return await i.response.send_message("Not allowed", ephemeral=True)

        if self.values[0] == "0":
            return await i.response.send_message("No players in match", ephemeral=True)

        uid = _i(self.values[0], 0)
        if uid not in v.fighters_set:
            return await i.response.send_message("Player not in match", ephemeral=True)

        await i.response.send_modal(StatsModal(v, uid))


class FinalizeButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Finalize", style=discord.ButtonStyle.success)

    async def callback(self, i: discord.Interaction):
        v = self.view.v
        if not is_controller(v, i.user.id):
            return await i.response.send_message("Not allowed", ephemeral=True)
        await i.response.defer()
        await v.finalize_results(i)


class StatsCancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Cancel", style=discord.ButtonStyle.danger)

    async def callback(self, i: discord.Interaction):
        v = self.view.v
        if not is_controller(v, i.user.id):
            return await i.response.send_message("Not allowed", ephemeral=True)

        async with v.lock:
            v.state.set_phase("ENDED")

        try:
            await i.message.delete()
        except:
            try:
                await i.response.edit_message(view=None)
            except:
                pass


class StatsView(discord.ui.View):
    def __init__(self, v):
        super().__init__(timeout=None)
        self.v = v
        self.add_item(PlayerPick(v))
        self.add_item(FinalizeButton())
        self.add_item(StatsCancelButton())


class WagerView(discord.ui.View):
    def __init__(self, i: discord.Interaction, size: int, a: str, b: str, prize: str):
        super().__init__(timeout=None)

        self.guild = i.guild
        self.host_id = i.user.id
        self.host = i.user.display_name

        self.teams = TeamManager(size)
        self.mm = MiddlemanManager()
        self.ready_mgr = ReadyManager()
        self.stats_mgr = StatsManager()
        self.state = WagerState()

        self.size = self.teams.size
        self.a = SAFE_TEAM(a, "TEAM A")
        self.b = SAFE_TEAM(b, "TEAM B")
        self.prize = prize

        self.message: Optional[discord.Message] = None
        self.lock = asyncio.Lock()

        self.btn_join_a = JoinButton(f"Join {self.a}", "A")
        self.btn_join_b = JoinButton(f"Join {self.b}", "B")
        self.btn_pick_mm = PickMiddlemanButton()
        self.btn_no_mm = NoMiddlemanButton()
        self.btn_ready = ReadyUpButton()
        self.btn_unready = UnreadyButton()
        self.btn_end = EndMatchButton()
        self.btn_cancel = CancelButton()

        self._rebuild_items()

    @property
    def phase(self):
        return self.state.phase

    @property
    def team_a(self):
        return self.teams.team_a

    @property
    def team_b(self):
        return self.teams.team_b

    @property
    def middleman_id(self):
        return self.mm.middleman_id

    @property
    def no_middleman(self):
        return self.mm.no_middleman

    @property
    def ready(self):
        return self.ready_mgr.ready

    @property
    def stats(self):
        return self.stats_mgr.stats

    @property
    def fighters_set(self):
        return self.teams.fighters_set()

    @property
    def middleman_name(self):
        if not self.middleman_id:
            return None
        m = self.guild.get_member(self.middleman_id)
        return m.display_name if m else None

    def _rebuild_items(self):
        self.clear_items()

        if self.phase == "LOBBY":
            self.add_item(self.btn_join_a)
            self.add_item(self.btn_join_b)
            self.add_item(self.btn_pick_mm)
            self.add_item(self.btn_no_mm)
            self.add_item(self.btn_end)
            self.add_item(self.btn_cancel)
            return

        if self.phase == "WAIT_MM":
            self.add_item(self.btn_pick_mm)
            self.add_item(self.btn_no_mm)
            self.add_item(self.btn_end)
            self.add_item(self.btn_cancel)
            return

        if self.phase == "READY":
            self.add_item(self.btn_ready)
            self.add_item(self.btn_unready)
            self.add_item(self.btn_end)
            self.add_item(self.btn_cancel)
            return

        if self.phase == "LIVE":
            self.add_item(self.btn_end)
            self.add_item(self.btn_cancel)
            return

        if self.phase == "STATS":
            return

        if self.phase == "ENDED":
            return

    async def _edit_card(self):
        if not self.message:
            return
        img = await render_wager_image(self)
        buf = BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        file = discord.File(buf, "wager.png")
        e = discord.Embed()
        e.set_image(url="attachment://wager.png")
        try:
            await self.message.edit(embed=e, attachments=[file], view=self)
        except:
            try:
                await self.message.edit(embed=e, view=self)
            except:
                pass

    async def _ping_fighters_ready(self):
        if not self.message:
            return
        fighters = list(self.fighters_set)
        if not fighters:
            return
        mentions = " ".join(f"<@{u}>" for u in fighters)
        try:
            await self.message.reply(
                f"{mentions}\nTeams are full. Ready up to start.",
                allowed_mentions=allowed_mentions_users_only(),
            )
        except:
            pass

    async def update_state_and_card(self):
        ping = False

        async with self.lock:
            fighters = self.fighters_set
            self.ready_mgr.init_for(fighters)

            if self.phase in ("LOBBY", "WAIT_MM"):
                if self.teams.is_full():
                    if not self.mm.decided():
                        self.state.set_phase("WAIT_MM")
                    else:
                        self.mm.lock()
                        self.state.set_phase("READY")
                        if not self.state.pinged_ready:
                            self.state.pinged_ready = True
                            ping = True
                else:
                    self.state.set_phase("LOBBY")
                    self.state.pinged_ready = False

            elif self.phase == "READY":
                if self.ready_mgr.all_ready(fighters):
                    self.state.set_phase("LIVE")

            self._rebuild_items()

        await self._edit_card()
        if ping:
            await self._ping_fighters_ready()

    async def hard_end_to_stats(self):
        async with self.lock:
            if self.phase in ("STATS", "ENDED"):
                return False
            self.state.set_phase("STATS")
            self._rebuild_items()
        return True

    async def _cleanup_lobby_after(self, seconds: int):
        await asyncio.sleep(seconds)

    async def finalize_results(self, interaction: discord.Interaction):
                async with self.lock:
            if self.state.ending:
                return
            if self.phase != "STATS":
                try:
                    if interaction.response.is_done():
                        await interaction.followup.send("Not in stats phase.", ephemeral=True)
                    else:
                        await interaction.response.send_message("Not in stats phase.", ephemeral=True)
                except:
                    pass
                return
            self.state.ending = True
            self.state.set_phase("ENDED")

        fighters = list(self.fighters_set)
        for u in fighters:
            self.stats_mgr.ensure(u)

        ta_k = self.stats_mgr.total_kills(self.team_a, self.size)
        tb_k = self.stats_mgr.total_kills(self.team_b, self.size)

        if ta_k > tb_k:
            out_a = "W"
            out_b = "L"
        elif tb_k > ta_k:
            out_a = "L"
            out_b = "W"
        else:
            out_a = "D"
            out_b = "D"

        for u in self.team_a[: self.size]:
            k, dth = self.stats_mgr.stats.get(u, (0, 0))
            await RANKED.record_match(u, k, dth, out_a)

        for u in self.team_b[: self.size]:
            k, dth = self.stats_mgr.stats.get(u, (0, 0))
            await RANKED.record_match(u, k, dth, out_b)

        img = await render_results_image(self)
        buf = BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        results_file = discord.File(buf, "results.png")

        winner_id = None
        if ta_k > tb_k and self.team_a:
            winner_id = self.team_a[0]
        elif tb_k > ta_k and self.team_b:
            winner_id = self.team_b[0]

        await post_match_logs(
            guild=self.guild,
            team_a_name=self.a,
            team_b_name=self.b,
            team_a_ids=self.team_a[: self.size],
            team_b_ids=self.team_b[: self.size],
            stats=self.stats_mgr.stats,
            middleman_id=self.middleman_id if not self.no_middleman else None,
            winner_id=winner_id,
            results_image=results_file
        )

        try:
            await interaction.followup.send(embed=e, file=results_file)
        except:
            pass

        try:
            if self.message:
                await self.message.delete()
        except:
            pass

        e = discord.Embed()
        e.set_image(url="attachment://results.png")

        

        try:
            if interaction.response.is_done():
                await interaction.followup.send("Match finalized.", ephemeral=True)
            else:
                await interaction.response.send_message("Match finalized.", ephemeral=True)
        except:
            pass

        asyncio.create_task(self._cleanup_lobby_after(20))


@bot.tree.command(name="wager", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(size="Team size (1 = 1v1, 2 = 2v2, etc)", team_a="Team A name", team_b="Team B name", prize="Prize text")
async def wager(i: discord.Interaction, size: int, team_a: str, team_b: str, prize: str):
    size = max(1, min(25, _i(size, 1)))
    v = WagerView(i, size, team_a, team_b, prize)
    img = await render_wager_image(v)
    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    file = discord.File(buf, "wager.png")
    e = discord.Embed()
    e.set_image(url="attachment://wager.png")
    await i.response.send_message(embed=e, file=file, view=v)
    v.message = await i.original_response()


@bot.tree.command(name="rankedstats", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(player="Player (optional)")
async def rankedstats(i: discord.Interaction, player: Optional[discord.Member] = None):
    m = player or i.user
    row = await RANKED.get(m.id)
    winp = await RANKED.win_likelihood(m.id)
    img = await render_rankedstats_image(m, row, winp)
    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    file = discord.File(buf, "rankedstats.png")
    e = discord.Embed()
    e.set_image(url="attachment://rankedstats.png")
    await i.response.send_message(embed=e, file=file)


async def _sync_commands():
    try:
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        return True
    except Exception as e:
        print("SYNC ERROR:", e)
        return False


@bot.event
async def setup_hook():
    await RANKED.load()
    await _sync_commands()
    await asyncio.sleep(1)
    await _sync_commands()


@bot.event
async def on_ready():
    await _sync_commands()
    await asyncio.sleep(1)
    await _sync_commands()
    try:
        cmds = bot.tree.get_commands(guild=discord.Object(id=GUILD_ID))
        print("REGISTERED:", [c.name for c in cmds])
    except Exception as e:
        print("CMD LIST ERROR:", e)
    print("READY:", bot.user)


_BIG_BODY_PAD = """
""" + ("\n" * 850)


bot.run(TOKEN)
