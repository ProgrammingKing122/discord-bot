import os
import math
import discord
import aiohttp
from io import BytesIO
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands


TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1443765937793667194
MIDDLEMAN_ROLE_ID = 1457241934832861255

BASE = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE, "fonts", "Inter_24pt-ExtraBoldItalic.ttf")

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def setup_hook():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

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

def pick_mvp(stats: dict[int, tuple[int, int]], team: list[int]) -> int | None:
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

async def render_wager(v) -> Image.Image:
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H))
    draw_bg(img)
    d = ImageDraw.Draw(img)

    a_name = SAFE_TEAM(v.a, "TEAM A")
    b_name = SAFE_TEAM(v.b, "TEAM B")

    t_font, t_text = FIT(d, f"WAGER {v.size}v{v.size}", 96, 72, W - 160)
    d.text((80, 54), t_text, fill="white", font=t_font)

    p_font, p_text = FIT(d, f"Prize: {v.prize}", 52, 34, W - 160)
    d.text((80, 170), p_text, fill="#b5b9c7", font=p_font)

    h_font, h_text = FIT(d, f"Host: {v.host}", 52, 34, W - 160)
    d.text((80, 234), h_text, fill="#b5b9c7", font=h_font)

    mm = "None" if v.no_middleman else (v.middleman_name or "Pending")
    m_font, m_text = FIT(d, f"Middleman: {mm}", 52, 34, W - 160)
    d.text((80, 298), m_text, fill="#b5b9c7", font=m_font)

    margin = 120
    table_w = (W - margin * 3) // 2
    lx = margin
    rx = lx + table_w + margin

    la_font, la_text = FIT(d, a_name, 72, 46, table_w)
    lb_font, lb_text = FIT(d, b_name, 72, 46, table_w)

    d.text((lx, 390), la_text, fill="#4cc2ff", font=la_font)
    d.text((rx, 390), lb_text, fill="#ffb84c", font=lb_font)

    vs = "VS"
    vs_font, vs_text = FIT(d, vs, 120, 84, 260)
    d.text((FIT_CENTER_X(d, vs_text, vs_font, W // 2), 430), vs_text, fill="white", font=vs_font)

    line_y = 470
    d.line([(lx, line_y), (lx + table_w, line_y)], fill=(76, 194, 255), width=5)
    d.line([(rx, line_y), (rx + table_w, line_y)], fill=(255, 184, 76), width=5)

    ay = 520
    by = 520
    avatar_size = 88
    row_h = 112

    async with aiohttp.ClientSession() as s:
        for uid in v.team_a:
            m = v.guild.get_member(uid) or await v.guild.fetch_member(uid)
            av = await fetch_avatar(s, m.display_avatar.url, avatar_size)
            img.paste(av, (lx, ay), av)
            nf, nt = FIT(d, m.display_name, 50, 34, table_w - avatar_size - 40)
            d.text((lx + avatar_size + 22, ay + 18), nt, fill="white", font=nf)
            ay += row_h
            if ay > H - 220:
                break

        for uid in v.team_b:
            m = v.guild.get_member(uid) or await v.guild.fetch_member(uid)
            av = await fetch_avatar(s, m.display_avatar.url, avatar_size)
            img.paste(av, (rx, by), av)
            nf, nt = FIT(d, m.display_name, 50, 34, table_w - avatar_size - 40)
            d.text((rx + avatar_size + 22, by + 18), nt, fill="white", font=nf)
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

async def render_results(v) -> Image.Image:
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H))
    draw_bg(img)
    d = ImageDraw.Draw(img)

    margin = 120
    table_w = (W - margin * 3) // 2
    lx = margin
    rx = lx + table_w + margin

    a_name = SAFE_TEAM(v.a, "TEAM A")
    b_name = SAFE_TEAM(v.b, "TEAM B")

    ta_k = sum(v.stats[u][0] for u in v.team_a if u in v.stats)
    tb_k = sum(v.stats[u][0] for u in v.team_b if u in v.stats)

    title, title_col = win_phrase(a_name, b_name, ta_k, tb_k)
    title_font, title_txt = FIT(d, title, 110, 64, W - 200)
    d.text((FIT_CENTER_X(d, title_txt, title_font, W // 2), 44), title_txt, fill=title_col, font=title_font)

    head_left = f"{a_name} — {ta_k} KILLS"
    head_right = f"{b_name} — {tb_k} KILLS"
    hl_font, hl_txt = FIT(d, head_left, 62, 40, table_w)
    hr_font, hr_txt = FIT(d, head_right, 62, 40, table_w)
    d.text((lx, 190), hl_txt, fill="#4cc2ff", font=hl_font)
    d.text((rx, 190), hr_txt, fill="#ffb84c", font=hr_font)

    mvp_a = pick_mvp(v.stats, v.team_a)
    mvp_b = pick_mvp(v.stats, v.team_b)

    header_y = 290
    row_start = header_y + 84

    avatar_size = 92
    row_h = 126

    hdr_font = F(42)

    name_x = avatar_size + 26
    name_w = table_w - 520

    k_edge = table_w - 360
    d_edge = table_w - 220
    kd_edge = table_w - 40

    for bx in (lx, rx):
        d.text((bx + name_x, header_y), "NAME", fill="#b5b9c7", font=hdr_font)
        d.text((bx + k_edge - TL(d, "K", hdr_font), header_y), "K", fill="#b5b9c7", font=hdr_font)
        d.text((bx + d_edge - TL(d, "D", hdr_font), header_y), "D", fill="#b5b9c7", font=hdr_font)
        d.text((bx + kd_edge - TL(d, "KD", hdr_font), header_y), "KD", fill="#b5b9c7", font=hdr_font)

    d.line([(lx, header_y + 64), (lx + table_w, header_y + 64)], fill=(76, 194, 255), width=5)
    d.line([(rx, header_y + 64), (rx + table_w, header_y + 64)], fill=(255, 184, 76), width=5)

    async with aiohttp.ClientSession() as s:
        for base_x, team, mvp_u in ((lx, v.team_a, mvp_a), (rx, v.team_b, mvp_b)):
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

                num_font = nf

                d.text((base_x + k_edge - TL(d, k_txt, num_font), y + 22), k_txt, fill="white", font=num_font)
                d.text((base_x + d_edge - TL(d, d_txt, num_font), y + 22), d_txt, fill="white", font=num_font)
                d.text((base_x + kd_edge - TL(d, kd_txt, num_font), y + 22), kd_txt, fill="white", font=num_font)

                y += row_h
                if y > H - 160:
                    break

    footer = "Brought to you by levi"
    ff = F(28)
    d.text((FIT_CENTER_X(d, footer, ff, W // 2), H - 68), footer, fill="#d0d0d0", font=ff)
    return img

class Join(discord.ui.Button):
    def __init__(self, label: str, side: str):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.side = side

    async def callback(self, i: discord.Interaction):
        v = self.view
        uid = i.user.id

        if self.side == "A":
            if uid in v.team_b:
                v.team_b.remove(uid)
            if uid not in v.team_a:
                v.team_a.append(uid)
        else:
            if uid in v.team_a:
                v.team_a.remove(uid)
            if uid not in v.team_b:
                v.team_b.append(uid)

        await i.response.defer()
        await v.update()

class PickMM(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Pick Middleman", style=discord.ButtonStyle.secondary)

    async def callback(self, i: discord.Interaction):
        if i.user.id != self.view.host_id:
            return await i.response.send_message("Host only", ephemeral=True)
        await i.response.defer(ephemeral=True)
        await i.followup.send("Select middleman", view=MMView(self.view), ephemeral=True)

class NoMM(discord.ui.Button):
    def __init__(self):
        super().__init__(label="No Middleman", style=discord.ButtonStyle.secondary)

    async def callback(self, i: discord.Interaction):
        if i.user.id != self.view.host_id:
            return await i.response.send_message("Host only", ephemeral=True)
        self.view.middleman_id = None
        self.view.no_middleman = True
        await i.response.defer()
        await self.view.update()

class End(discord.ui.Button):
    def __init__(self):
        super().__init__(label="End Match", style=discord.ButtonStyle.danger)

    async def callback(self, i: discord.Interaction):
        if i.user.id not in {self.view.host_id, self.view.middleman_id}:
            return await i.response.send_message("Not allowed", ephemeral=True)
        await i.response.edit_message(view=StatsView(self.view))

class Cancel(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Cancel", style=discord.ButtonStyle.danger)

    async def callback(self, i: discord.Interaction):
        if i.user.id not in {self.view.host_id, self.view.middleman_id}:
            return await i.response.send_message("Not allowed", ephemeral=True)
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
        picked = self.values[0].id
        m = i.guild.get_member(picked) or await i.guild.fetch_member(picked)
        if not any(r.id == MIDDLEMAN_ROLE_ID for r in getattr(m, "roles", [])):
            return await i.response.send_message("Invalid middleman", ephemeral=True)

        self.v.middleman_id = m.id
        self.v.no_middleman = False
        await i.response.send_message("Middleman set", ephemeral=True)
        await self.v.update()

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
        if i.user.id not in {self.v.host_id, self.v.middleman_id}:
            return await i.response.send_message("Not allowed", ephemeral=True)

        try:
            k = int(str(self.kills.value).strip())
            dth = int(str(self.deaths.value).strip())
        except:
            return await i.response.send_message("Invalid numbers", ephemeral=True)

        if k < 0:
            k = 0
        if dth < 0:
            dth = 0

        self.v.stats[self.uid] = (k, dth)
        await i.response.send_message("Saved", ephemeral=True)

class PlayerPick(discord.ui.Select):
    def __init__(self, v):
        self.v = v
        opts = []
        seen = set()

        ids = []
        for uid in v.team_a:
            ids.append(uid)
        for uid in v.team_b:
            ids.append(uid)

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
        if i.user.id not in {self.v.host_id, self.v.middleman_id}:
            return await i.response.send_message("Not allowed", ephemeral=True)

        if self.values[0] == "0":
            return await i.response.send_message("No players in match", ephemeral=True)

        uid = int(self.values[0])
        if uid not in self.v.team_a and uid not in self.v.team_b:
            return await i.response.send_message("Player not in match", ephemeral=True)

        await i.response.send_modal(StatsModal(self.v, uid))

class Finalize(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Finalize", style=discord.ButtonStyle.success)

    async def callback(self, i: discord.Interaction):
        v = self.view.v
        if i.user.id not in {v.host_id, v.middleman_id}:
            return await i.response.send_message("Not allowed", ephemeral=True)

        img = await render_results(v)
        buf = BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)

        file = discord.File(buf, "results.png")
        e = discord.Embed()
        e.set_image(url="attachment://results.png")
        await i.response.edit_message(embed=e, attachments=[file], view=None)

class StatsView(discord.ui.View):
    def __init__(self, v):
        super().__init__(timeout=None)
        self.v = v
        self.add_item(PlayerPick(v))
        self.add_item(Finalize())
        self.add_item(Cancel())

class WagerView(discord.ui.View):
    def __init__(self, i: discord.Interaction, size: int, a: str, b: str, prize: str):
        super().__init__(timeout=None)

        self.guild = i.guild
        self.host_id = i.user.id
        self.host = i.user.display_name

        self.middleman_id = None
        self.no_middleman = False

        self.size = size
        self.a = a
        self.b = b
        self.prize = prize

        self.team_a: list[int] = []
        self.team_b: list[int] = []
        self.stats: dict[int, tuple[int, int]] = {}

        self.message: discord.Message | None = None

        self.add_item(Join(f"Join {SAFE_TEAM(a, 'TEAM A')}", "A"))
        self.add_item(Join(f"Join {SAFE_TEAM(b, 'TEAM B')}", "B"))
        self.add_item(PickMM())
        self.add_item(NoMM())
        self.add_item(End())
        self.add_item(Cancel())

    @property
    def middleman_name(self):
        if not self.middleman_id:
            return None
        m = self.guild.get_member(self.middleman_id)
        return m.display_name if m else None

    async def update(self):
        if not self.message:
            return
        img = await render_wager(self)
        buf = BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        file = discord.File(buf, "wager.png")
        e = discord.Embed()
        e.set_image(url="attachment://wager.png")
        await self.message.edit(embed=e, attachments=[file], view=self)

@bot.tree.command(name="wager", guild=discord.Object(id=GUILD_ID))
@app_commands.default_permissions()


async def wager(i: discord.Interaction, size: int, team_a: str, team_b: str, prize: str):
    v = WagerView(i, size, team_a, team_b, prize)
    img = await render_wager(v)
    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    file = discord.File(buf, "wager.png")
    e = discord.Embed()
    e.set_image(url="attachment://wager.png")
    await i.response.send_message(embed=e, file=file, view=v)
    v.message = await i.original_response()

bot.run(TOKEN)
