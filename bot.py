import os
import re
import math
import discord
import aiohttp
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1443765937793667194
MIDDLEMAN_ROLE_ID = 1457241934832861255

BASE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(BASE, "fonts", "Inter_24pt-ExtraBoldItalic.ttf")

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def setup_hook():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

def f(size: int):
    try:
        return ImageFont.truetype(FONT, size)
    except:
        return ImageFont.load_default()

def tl(d: ImageDraw.ImageDraw, text: str, font) -> int:
    try:
        return int(d.textlength(text, font=font))
    except:
        return len(text) * 10

def clamp_text(d: ImageDraw.ImageDraw, text: str, font, max_w: int) -> str:
    if tl(d, text, font) <= max_w:
        return text
    t = text
    while t and tl(d, t + "…", font) > max_w:
        t = t[:-1]
    return (t + "…") if t else "…"

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

def safe_team_name(name: str, fallback: str) -> str:
    if not isinstance(name, str) or not name.strip():
        return fallback
    s = name.strip()
    lowered = s.lower()
    banned = [
        "nigger", "nigga", "faggot", "fag", "kike", "retard", "tranny",
        "hitler", "nazi", "gas the", "kill all", "genocide", "white power",
    ]
    for b in banned:
        if b in lowered:
            return fallback
    return s

async def fetch_avatar(session: aiohttp.ClientSession, url: str, size: int = 88) -> Image.Image:
    async with session.get(url) as r:
        b = await r.read()
    im = Image.open(BytesIO(b)).convert("RGBA")
    if im.size != (size, size):
        im = im.resize((size, size))
    return im

def draw_bg(img: Image.Image):
    W, H = img.size
    d = ImageDraw.Draw(img)
    base = (9, 11, 16)
    d.rectangle([0, 0, W, H], fill=base)
    for y in range(0, H, 2):
        shade = int(12 + (y / H) * 18)
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

def pick_mvp(stats: dict, team: list[int]) -> int | None:
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

    title_font = f(96)
    sub_font = f(52)
    meta_font = f(44)
    name_font = f(46)

    a_name = safe_team_name(v.a, "TEAM A")
    b_name = safe_team_name(v.b, "TEAM B")

    title = f"WAGER {v.size}v{v.size}"
    d.text((80, 54), title, fill="white", font=title_font)

    d.text((80, 170), clamp_text(d, f"Prize: {v.prize}", sub_font, W - 160), fill="#b5b9c7", font=sub_font)
    d.text((80, 234), clamp_text(d, f"Host: {v.host}", sub_font, W - 160), fill="#b5b9c7", font=sub_font)

    mm = "None" if v.no_middleman else (v.middleman_name or "Pending")
    d.text((80, 298), clamp_text(d, f"Middleman: {mm}", sub_font, W - 160), fill="#b5b9c7", font=sub_font)

    table_margin = 120
    table_w = (W - table_margin * 3) // 2
    lx = table_margin
    rx = lx + table_w + table_margin

    d.text((lx, 390), clamp_text(d, a_name, f(72), table_w), fill="#4cc2ff", font=f(72))
    d.text((rx, 390), clamp_text(d, b_name, f(72), table_w), fill="#ffb84c", font=f(72))

    vs = "VS"
    vs_font = f(120)
    vs_x = (W - tl(d, vs, vs_font)) // 2
    d.text((vs_x, 430), vs, fill="white", font=vs_font)

    line_y = 470
    d.line([(lx, line_y), (lx + table_w, line_y)], fill=(76, 194, 255), width=5)
    d.line([(rx, line_y), (rx + table_w, line_y)], fill=(255, 184, 76), width=5)

    left_y = 520
    right_y = 520
    avatar_size = 88
    row_h = 112

    async with aiohttp.ClientSession() as s:
        for uid in v.team_a:
            m = v.guild.get_member(uid) or await v.guild.fetch_member(uid)
            av = await fetch_avatar(s, m.display_avatar.url, avatar_size)
            img.paste(av, (lx, left_y), av)
            d.text((lx + avatar_size + 22, left_y + 18), clamp_text(d, m.display_name, name_font, table_w - avatar_size - 40), fill="white", font=name_font)
            left_y += row_h
            if left_y > H - 220:
                break

        for uid in v.team_b:
            m = v.guild.get_member(uid) or await v.guild.fetch_member(uid)
            av = await fetch_avatar(s, m.display_avatar.url, avatar_size)
            img.paste(av, (rx, right_y), av)
            d.text((rx + avatar_size + 22, right_y + 18), clamp_text(d, m.display_name, name_font, table_w - avatar_size - 40), fill="white", font=name_font)
            right_y += row_h
            if right_y > H - 220:
                break

    if not v.team_a:
        d.text((lx, left_y + 8), "No players yet", fill="#666", font=meta_font)
    if not v.team_b:
        d.text((rx, right_y + 8), "No players yet", fill="#666", font=meta_font)

    footer = "Brought to you by levi"
    d.text(((W - tl(d, footer, f(26))) // 2, H - 60), footer, fill="#d0d0d0", font=f(26))

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

    a_name = safe_team_name(v.a, "TEAM A")
    b_name = safe_team_name(v.b, "TEAM B")

    ta_k = sum(v.stats[u][0] for u in v.team_a if u in v.stats)
    tb_k = sum(v.stats[u][0] for u in v.team_b if u in v.stats)

    title, title_col = win_phrase(a_name, b_name, ta_k, tb_k)
    title_font = f(110)
    title = clamp_text(d, title, title_font, W - 200)
    d.text(((W - tl(d, title, title_font)) // 2, 44), title, fill=title_col, font=title_font)

    head_font = f(62)
    d.text((lx, 190), clamp_text(d, f"{a_name} — {ta_k} KILLS", head_font, table_w), fill="#4cc2ff", font=head_font)
    d.text((rx, 190), clamp_text(d, f"{b_name} — {tb_k} KILLS", head_font, table_w), fill="#ffb84c", font=head_font)

    mvp_a = pick_mvp(v.stats, v.team_a)
    mvp_b = pick_mvp(v.stats, v.team_b)

    header_y = 290
    row_start = header_y + 84

    avatar_size = 92
    row_h = 126

    hdr_font = f(42)
    row_font = f(48)

    name_x = avatar_size + 26
    name_w = table_w - (name_x + 360)

    k_w, d_w, kd_w = 130, 130, 180
    k_x = table_w - (k_w + d_w + kd_w)
    d_x = table_w - (d_w + kd_w)
    kd_x = table_w - kd_w

    for bx in (lx, rx):
        d.text((bx + name_x, header_y), "NAME", fill="#b5b9c7", font=hdr_font)
        d.text((bx + k_x, header_y), "K", fill="#b5b9c7", font=hdr_font)
        d.text((bx + d_x, header_y), "D", fill="#b5b9c7", font=hdr_font)
        d.text((bx + kd_x + kd_w - tl(d, "KD", hdr_font), header_y), "KD", fill="#b5b9c7", font=hdr_font)

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
                    d.text((base_x + table_w - 54, y + 22), badge, fill=strip_col, font=f(44))

                nm = clamp_text(d, m.display_name, row_font, name_w)
                d.text((base_x + name_x, y + 22), nm, fill="#ffd700" if is_mvp else "white", font=row_font)

                k_txt = fmt_num(k)
                d_txt = fmt_num(dth)

                d.text((base_x + k_x + k_w - tl(d, k_txt, row_font), y + 22), k_txt, fill="white", font=row_font)
                d.text((base_x + d_x + d_w - tl(d, d_txt, row_font), y + 22), d_txt, fill="white", font=row_font)
                d.text((base_x + kd_x + kd_w - tl(d, kd_txt, row_font), y + 22), kd_txt, fill="white", font=row_font)

                y += row_h
                if y > H - 160:
                    break

    footer = "Brought to you by levi"
    d.text(((W - tl(d, footer, f(28))) // 2, H - 68), footer, fill="#d0d0d0", font=f(28))
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
            k = int(self.kills.value.strip())
            dth = int(self.deaths.value.strip())
        except:
            return await i.response.send_message("Invalid numbers", ephemeral=True)
        if k < 0: k = 0
        if dth < 0: dth = 0
        self.v.stats[self.uid] = (k, dth)
        await i.response.send_message("Saved", ephemeral=True)

class PlayerPick(discord.ui.Select):
    def __init__(self, v):
        self.v = v
        opts = []
        seen = set()
        for uid in (v.team_a + v.team_b):
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

        self.add_item(Join(f"Join {safe_team_name(a,'TEAM A')}", "A"))
        self.add_item(Join(f"Join {safe_team_name(b,'TEAM B')}", "B"))
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
