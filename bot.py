import os
import discord
import aiohttp
import math
from io import BytesIO
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

# ---------------- FONT + TEXT UTILS ----------------

def F(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except:
        return ImageFont.load_default()

def TL(d, t, f):
    try:
        return d.textlength(t, font=f)
    except:
        return len(t) * 10

def FIT(d, t, start, min_s, max_w):
    s = start
    while s >= min_s:
        f = F(s)
        if TL(d, t, f) <= max_w:
            return f, t
        s -= 2
    f = F(min_s)
    while t and TL(d, t + "…", f) > max_w:
        t = t[:-1]
    return f, (t + "…") if t else "…"

def fmt(n):
    try:
        n = float(n)
    except:
        return str(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n/1_000:.1f}K"
    if n.is_integer():
        return str(int(n))
    return f"{n:.2f}".rstrip("0").rstrip(".")

# ---------------- IMAGE HELPERS ----------------

async def avatar(session, url, size):
    async with session.get(url) as r:
        img = Image.open(BytesIO(await r.read())).convert("RGBA")
    return img.resize((size, size))

def draw_bg(img):
    W, H = img.size
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, H), fill=(8, 10, 15))
    for y in range(0, H, 2):
        shade = int(12 + y * 0.02)
        d.line([(0, y), (W, y)], fill=(shade, shade, shade))

# ---------------- GAME LOGIC ----------------

def win_phrase(a, b, ak, bk):
    diff = abs(ak - bk)
    if ak == bk:
        return "DRAW", "#ffd24c"
    w = a if ak > bk else b
    l = b if ak > bk else a
    if diff >= 15:
        return f"{w} DESTROYED {l}", "#ff4c4c"
    if diff >= 8:
        return f"{w} DOMINATED {l}", "#ff9c4c"
    return f"{w} WINS NARROWLY", "#4cff7a"

def pick_mvp(stats, team):
    rows = []
    for uid in team:
        if uid in stats:
            k, d = stats[uid]
            kd = k / d if d else k
            rows.append((uid, k, kd))
    if len(rows) < 2:
        return None
    rows.sort(key=lambda x: (x[1], x[2]), reverse=True)
    if rows[0][1] == rows[1][1]:
        return None
    return rows[0][0]

# ---------------- RENDER WAGER CARD ----------------

async def render_wager(v):
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H))
    draw_bg(img)
    d = ImageDraw.Draw(img)

    title_f, title_t = FIT(d, f"WAGER {v.size}v{v.size}", 96, 64, W - 200)
    d.text((80, 50), title_t, fill="white", font=title_f)

    info_y = 160
    for txt in (f"Prize: {v.prize}", f"Host: {v.host}"):
        fnt, t = FIT(d, txt, 48, 32, W - 200)
        d.text((80, info_y), t, fill="#b5b9c7", font=fnt)
        info_y += 56

    margin = 120
    table_w = (W - margin * 3) // 2
    lx = margin
    rx = lx + table_w + margin

    af, at = FIT(d, v.a, 72, 48, table_w)
    bf, bt = FIT(d, v.b, 72, 48, table_w)

    d.text((lx, 360), at, fill="#4cc2ff", font=af)
    d.text((rx, 360), bt, fill="#ffb84c", font=bf)

    vsf, vst = FIT(d, "VS", 120, 90, 300)
    d.text(((W - TL(d, vst, vsf)) // 2, 380), vst, fill="white", font=vsf)

    ay = by = 460
    async with aiohttp.ClientSession() as s:
        for uid in v.team_a:
            m = v.guild.get_member(uid)
            if not m:
                continue
            av = await avatar(s, m.display_avatar.url, 88)
            img.paste(av, (lx, ay), av)
            nf, nt = FIT(d, m.display_name, 44, 30, table_w - 120)
            d.text((lx + 110, ay + 22), nt, fill="white", font=nf)
            ay += 110

        for uid in v.team_b:
            m = v.guild.get_member(uid)
            if not m:
                continue
            av = await avatar(s, m.display_avatar.url, 88)
            img.paste(av, (rx, by), av)
            nf, nt = FIT(d, m.display_name, 44, 30, table_w - 120)
            d.text((rx + 110, by + 22), nt, fill="white", font=nf)
            by += 110

    footer = "Brought to you by levi"
    ff = F(26)
    d.text(((W - TL(d, footer, ff)) // 2, H - 60), footer, fill="#d0d0d0", font=ff)
    return img

# ---------------- RENDER RESULTS ----------------

async def render_results(v):
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H))
    draw_bg(img)
    d = ImageDraw.Draw(img)

    margin = 120
    table_w = (W - margin * 3) // 2
    lx = margin
    rx = lx + table_w + margin

    ak = sum(v.stats[u][0] for u in v.team_a if u in v.stats)
    bk = sum(v.stats[u][0] for u in v.team_b if u in v.stats)

    title, col = win_phrase(v.a, v.b, ak, bk)
    tf, tt = FIT(d, title, 110, 64, W - 200)
    d.text(((W - TL(d, tt, tf)) // 2, 40), tt, fill=col, font=tf)

    mvp_a = pick_mvp(v.stats, v.team_a)
    mvp_b = pick_mvp(v.stats, v.team_b)

    async with aiohttp.ClientSession() as s:
        for bx, team, mvp in ((lx, v.team_a, mvp_a), (rx, v.team_b, mvp_b)):
            y = 260
            for uid in team:
                if uid not in v.stats:
                    continue
                m = v.guild.get_member(uid)
                if not m:
                    continue
                k, dth = v.stats[uid]
                kd = "∞" if dth == 0 and k > 0 else fmt(k / dth if dth else k)

                av = await avatar(s, m.display_avatar.url, 88)
                img.paste(av, (bx, y), av)

                nf, nt = FIT(d, m.display_name, 44, 28, table_w - 360)
                d.text((bx + 110, y + 10), nt, fill="#ffd700" if uid == mvp else "white", font=nf)

                d.text((bx + table_w - 260, y + 10), fmt(k), fill="white", font=nf)
                d.text((bx + table_w - 180, y + 10), fmt(dth), fill="white", font=nf)
                d.text((bx + table_w - 90, y + 10), kd, fill="white", font=nf)

                y += 110

    footer = "Brought to you by levi"
    ff = F(26)
    d.text(((W - TL(d, footer, ff)) // 2, H - 60), footer, fill="#d0d0d0", font=ff)
    return img

# ---------------- DISCORD UI ----------------

class Join(discord.ui.Button):
    def __init__(self, label, side):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.side = side

    async def callback(self, i):
        v = self.view
        uid = i.user.id
        if self.side == "A":
            if uid not in v.team_a:
                v.team_a.append(uid)
            if uid in v.team_b:
                v.team_b.remove(uid)
        else:
            if uid not in v.team_b:
                v.team_b.append(uid)
            if uid in v.team_a:
                v.team_a.remove(uid)
        await i.response.defer()
        await v.update()

class End(discord.ui.Button):
    def __init__(self):
        super().__init__(label="End Match", style=discord.ButtonStyle.danger)

    async def callback(self, i):
        await i.response.edit_message(view=StatsView(self.view))

class StatsModal(discord.ui.Modal, title="Enter Stats"):
    kills = discord.ui.TextInput(label="Kills")
    deaths = discord.ui.TextInput(label="Deaths")

    def __init__(self, v, uid):
        super().__init__()
        self.v = v
        self.uid = uid

    async def on_submit(self, i):
        self.v.stats[self.uid] = (int(self.kills.value), int(self.deaths.value))
        await i.response.send_message("Saved", ephemeral=True)

class PlayerPick(discord.ui.Select):
    def __init__(self, v):
        self.v = v
        opts = []
        for uid in (v.team_a + v.team_b):
            m = v.guild.get_member(uid)
            if m:
                opts.append(discord.SelectOption(label=m.display_name, value=str(uid)))
        super().__init__(options=opts[:25])

    async def callback(self, i):
        await i.response.send_modal(StatsModal(self.v, int(self.values[0])))

class Finalize(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Finalize", style=discord.ButtonStyle.success)

    async def callback(self, i):
        img = await render_results(self.view.v)
        buf = BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        await i.response.edit_message(
            embed=discord.Embed().set_image(url="attachment://results.png"),
            attachments=[discord.File(buf, "results.png")],
            view=None
        )

class StatsView(discord.ui.View):
    def __init__(self, v):
        super().__init__()
        self.v = v
        self.add_item(PlayerPick(v))
        self.add_item(Finalize())

class WagerView(discord.ui.View):
    def __init__(self, i, size, a, b, prize):
        super().__init__(timeout=None)
        self.guild = i.guild
        self.host = i.user.display_name
        self.a = a
        self.b = b
        self.size = size
        self.prize = prize
        self.team_a = []
        self.team_b = []
        self.stats = {}
        self.message = None
        self.add_item(Join(f"Join {a}", "A"))
        self.add_item(Join(f"Join {b}", "B"))
        self.add_item(End())

    async def update(self):
        img = await render_wager(self)
        buf = BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        await self.message.edit(
            embed=discord.Embed().set_image(url="attachment://wager.png"),
            attachments=[discord.File(buf, "wager.png")],
            view=self
        )

@bot.tree.command(
    name="wager",
    guild=discord.Object(id=GUILD_ID),
    default_permissions=discord.Permissions.none()
)
async def wager(i, size: int, team_a: str, team_b: str, prize: str):
    v = WagerView(i, size, team_a, team_b, prize)
    img = await render_wager(v)
    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    await i.response.send_message(
        embed=discord.Embed().set_image(url="attachment://wager.png"),
        attachments=[discord.File(buf, "wager.png")],
        view=v
    )
    v.message = await i.original_response()

bot.run(TOKEN)
