import os
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

def clamp_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int):
    if draw.textlength(text, font=font) <= max_w:
        return text
    t = text
    while len(t) > 3 and draw.textlength(t + "…", font=font) > max_w:
        t = t[:-1]
    return t + "…"

def fit_font(draw: ImageDraw.ImageDraw, text: str, max_w: int, start: int, min_size: int):
    size = start
    ft = f(size)
    while size > min_size and draw.textlength(text, font=ft) > max_w:
        size -= 2
        ft = f(size)
    return ft

async def avatar(session: aiohttp.ClientSession, url: str, s: int = 56):
    async with session.get(url) as r:
        return Image.open(BytesIO(await r.read())).convert("RGBA").resize((s, s))

def bg_style(img):
    W, H = img.size
    d = ImageDraw.Draw(img)
    for y in range(0, H, 2):
        shade = int(12 + y * 0.03)
        d.line([(0, y), (W, y)], fill=(shade, shade, shade))
    for x in range(0, W, 6):
        d.line([(x, 0), (x - H, H)], fill=(10, 10, 16))
    d.rectangle([0, 0, W, H], outline="#11131a", width=2)

def status_strip(k: int, dth: int, mvp: bool):
    if k == 0 and dth >= 1:
        return "#ff4c4c", "☠"
    if mvp:
        return "#ffd700", "👑"
    if k > dth:
        return "#4cff7a", ""
    if k == dth:
        return "#ffd24c", ""
    return "#ff4c4c", ""

def win_line(v, ta_k: int, tb_k: int):
    diff = abs(ta_k - tb_k)
    if ta_k == tb_k:
        return "DRAW", "#ffd24c"
    w = v.a if ta_k > tb_k else v.b
    l = v.b if ta_k > tb_k else v.a
    if diff >= 15:
        return f"{w} DESTROYED {l}", "#ff4c4c"
    if diff >= 10:
        return f"{w} SLAMMED {l}", "#ff6a4c"
    if diff >= 6:
        return f"{w} DOMINATED {l}", "#ff9c4c"
    if diff >= 3:
        return f"{w} DEFEATED {l}", "#ffd24c"
    return f"{w} WINS NARROWLY", "#4cff7a"

async def render_wager(v):
    img = Image.new("RGB", (1280, 720), "#07090d")
    bg_style(img)
    d = ImageDraw.Draw(img)

    title = f"WAGER {v.size}v{v.size}"
    d.text((40, 28), title, fill="white", font=f(64))
    d.text((40, 120), f"Prize: {v.prize}", fill="#b5b9c7", font=f(36))
    d.text((40, 165), f"Host: {v.host}", fill="#b5b9c7", font=f(36))
    mm = "None" if v.no_middleman else (v.middleman_name or "Pending")
    d.text((40, 210), f"Middleman: {mm}", fill="#b5b9c7", font=f(36))

    d.text((150, 280), v.a, fill="#4cc2ff", font=f(48))
    d.text((820, 280), v.b, fill="#ffb84c", font=f(48))
    d.text((600, 350), "VS", fill="white", font=f(96))

    ay = by = 400

    async with aiohttp.ClientSession() as s:
        for uid in v.team_a:
            m = v.guild.get_member(uid) or await v.guild.fetch_member(uid)
            av = await avatar(s, m.display_avatar.url, 64)
            img.paste(av, (110, ay), av)
            name = m.display_name
            name = clamp_text(d, name, f(32), 420)
            d.text((190, ay + 18), name, fill="white", font=f(32))
            ay += 88

        for uid in v.team_b:
            m = v.guild.get_member(uid) or await v.guild.fetch_member(uid)
            av = await avatar(s, m.display_avatar.url, 64)
            img.paste(av, (780, by), av)
            name = m.display_name
            name = clamp_text(d, name, f(32), 420)
            d.text((860, by + 18), name, fill="white", font=f(32))
            by += 88

    if not v.team_a:
        d.text((150, ay), "No players yet", fill="#555", font=f(32))
    if not v.team_b:
        d.text((820, by), "No players yet", fill="#555", font=f(32))

    return img

async def render_results(v):
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), "#07090d")
    bg_style(img)
    d = ImageDraw.Draw(img)

    ta_k = sum(v.stats[u][0] for u in v.team_a if u in v.stats)
    tb_k = sum(v.stats[u][0] for u in v.team_b if u in v.stats)

    wl, wc = win_line(v, ta_k, tb_k)
    wl = clamp_text(d, wl, f(52), 1180)
    win_font = fit_font(d, wl, 1180, 56, 34)
    d.text((W // 2 - int(d.textlength(wl, font=win_font)) // 2, 26), wl, fill=wc, font=win_font)

    left_title = f"{v.a} — {ta_k} KILLS"
    right_title = f"{v.b} — {tb_k} KILLS"
    left_title = clamp_text(d, left_title, f(34), 520)
    right_title = clamp_text(d, right_title, f(34), 520)
    d.text((40, 102), left_title, fill="#4cc2ff", font=f(34))
    d.text((640, 102), right_title, fill="#ffb84c", font=f(34))

    def mvp(team):
        rows = []
        for u in team:
            if u not in v.stats:
                continue
            k, dth = v.stats[u]
            kd = (k / dth) if dth else float(k)
            rows.append((u, k, kd))
        if len(rows) < 2:
            return None
        rows.sort(key=lambda x: (x[1], x[2]), reverse=True)
        if rows[0][1] == rows[1][1] and rows[0][2] == rows[1][2]:
            return None
        return rows[0][0]

    mvp_a = mvp(v.team_a)
    mvp_b = mvp(v.team_b)

    margin = 40
    gap = 20
    promo_w = 300
    table_w = (W - margin * 2 - gap * 2 - promo_w) // 2

    lx = margin
    rx = margin + table_w + gap
    px = margin + table_w * 2 + gap * 2

    top_y = 160
    header_y = top_y
    row_y_a = header_y + 44
    row_y_b = header_y + 44

    name_x = 72
    k_x = table_w - 140
    d_x = table_w - 92
    kd_x = table_w - 28

    def headers(x, accent):
        d.text((x + name_x, header_y), "NAME", fill="#b5b9c7", font=f(22))
        d.text((x + k_x, header_y), "K", fill="#b5b9c7", font=f(22))
        d.text((x + d_x, header_y), "D", fill="#b5b9c7", font=f(22))
        d.text((x + kd_x - 26, header_y), "KD", fill="#b5b9c7", font=f(22))
        d.rectangle([x, header_y + 30, x + table_w, header_y + 33], fill=accent)

    headers(lx, "#4cc2ff")
    headers(rx, "#ffb84c")

    d.rectangle([px, top_y - 6, px + promo_w, H - 40], outline="#2a2d36", width=2)
    d.text((px + 18, top_y + 6), "PROMO", fill="#ffd700", font=f(28))
    promo_lines = [
        "• Ranked wagers",
        "• Middleman secured",
        "• Auto results",
        "• MVP crowns",
        "• Clean stat cards",
    ]
    py = top_y + 56
    for line in promo_lines:
        d.text((px + 18, py), line, fill="#b5b9c7", font=f(24))
        py += 34

    async with aiohttp.ClientSession() as s:
        for uid in v.team_a:
            if uid not in v.stats:
                continue
            m = v.guild.get_member(uid) or await v.guild.fetch_member(uid)
            k, dth = v.stats[uid]
            kd = round((k / dth), 2) if dth else round(float(k), 2)
            is_mvp = (uid == mvp_a)
            strip_col, badge = status_strip(k, dth, is_mvp)

            av = await avatar(s, m.display_avatar.url, 56)
            img.paste(av, (lx + 8, row_y_a), av)

            d.rectangle([lx + table_w - 14, row_y_a, lx + table_w - 6, row_y_a + 56], fill=strip_col)
            if badge:
                d.text((lx + table_w - 34, row_y_a + 14), badge, fill=strip_col, font=f(26))

            name = clamp_text(d, m.display_name, f(26), table_w - 210)
            d.text((lx + name_x, row_y_a + 14), name, fill="#ffd700" if is_mvp else "white", font=f(26))
            d.text((lx + k_x, row_y_a + 14), str(k), fill="white", font=f(26))
            d.text((lx + d_x, row_y_a + 14), str(dth), fill="white", font=f(26))
            d.text((lx + kd_x - int(d.textlength(str(kd), font=f(26))), row_y_a + 14), str(kd), fill="white", font=f(26))

            row_y_a += 68
            if row_y_a > H - 80:
                break

        for uid in v.team_b:
            if uid not in v.stats:
                continue
            m = v.guild.get_member(uid) or await v.guild.fetch_member(uid)
            k, dth = v.stats[uid]
            kd = round((k / dth), 2) if dth else round(float(k), 2)
            is_mvp = (uid == mvp_b)
            strip_col, badge = status_strip(k, dth, is_mvp)

            av = await avatar(s, m.display_avatar.url, 56)
            img.paste(av, (rx + 8, row_y_b), av)

            d.rectangle([rx + table_w - 14, row_y_b, rx + table_w - 6, row_y_b + 56], fill=strip_col)
            if badge:
                d.text((rx + table_w - 34, row_y_b + 14), badge, fill=strip_col, font=f(26))

            name = clamp_text(d, m.display_name, f(26), table_w - 210)
            d.text((rx + name_x, row_y_b + 14), name, fill="#ffd700" if is_mvp else "white", font=f(26))
            d.text((rx + k_x, row_y_b + 14), str(k), fill="white", font=f(26))
            d.text((rx + d_x, row_y_b + 14), str(dth), fill="white", font=f(26))
            d.text((rx + kd_x - int(d.textlength(str(kd), font=f(26))), row_y_b + 14), str(kd), fill="white", font=f(26))

            row_y_b += 68
            if row_y_b > H - 80:
                break

    return img

class Join(discord.ui.Button):
    def __init__(self, label, side):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.side = side

    async def callback(self, i):
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

    async def callback(self, i):
        if i.user.id != self.view.host_id:
            return await i.response.send_message("Host only", ephemeral=True)
        await i.response.defer(ephemeral=True)
        await i.followup.send("Select middleman", view=MMView(self.view), ephemeral=True)

class NoMM(discord.ui.Button):
    def __init__(self):
        super().__init__(label="No Middleman", style=discord.ButtonStyle.secondary)

    async def callback(self, i):
        if i.user.id != self.view.host_id:
            return await i.response.send_message("Host only", ephemeral=True)
        self.view.middleman_id = None
        self.view.no_middleman = True
        await i.response.defer()
        await self.view.update()

class End(discord.ui.Button):
    def __init__(self):
        super().__init__(label="End Match", style=discord.ButtonStyle.danger)

    async def callback(self, i):
        if i.user.id not in {self.view.host_id, self.view.middleman_id}:
            return await i.response.send_message("Not allowed", ephemeral=True)
        await i.response.edit_message(view=StatsView(self.view))

class Cancel(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Cancel", style=discord.ButtonStyle.danger)

    async def callback(self, i):
        if i.user.id not in {self.view.host_id, self.view.middleman_id}:
            return await i.response.send_message("Not allowed", ephemeral=True)
        await i.response.defer()
        try:
            await i.message.delete()
        except:
            pass

class MMSelect(discord.ui.UserSelect):
    def __init__(self, v):
        super().__init__(min_values=1, max_values=1)
        self.v = v

    async def callback(self, i):
        m = i.guild.get_member(self.values[0].id) or await i.guild.fetch_member(self.values[0].id)
        if not any(r.id == MIDDLEMAN_ROLE_ID for r in m.roles):
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
    kills = discord.ui.TextInput(label="Kills")
    deaths = discord.ui.TextInput(label="Deaths")

    def __init__(self, v, uid):
        super().__init__()
        self.v = v
        self.uid = uid

    async def on_submit(self, i):
        if i.user.id not in {self.v.host_id, self.v.middleman_id}:
            return await i.response.send_message("Not allowed", ephemeral=True)
        try:
            k = int(self.kills.value)
            dth = int(self.deaths.value)
        except:
            return await i.response.send_message("Invalid numbers", ephemeral=True)
        self.v.stats[self.uid] = (max(0, k), max(0, dth))
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

    async def callback(self, i):
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

    async def callback(self, i):
        if i.user.id not in {self.view.v.host_id, self.view.v.middleman_id}:
            return await i.response.send_message("Not allowed", ephemeral=True)
        img = await render_results(self.view.v)
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
    def __init__(self, i, size, a, b, prize):
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
        self.team_a = []
        self.team_b = []
        self.stats = {}
        self.message = None

        self.add_item(Join(f"Join {a}", "A"))
        self.add_item(Join(f"Join {b}", "B"))
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
        img = await render_wager(self)
        buf = BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        file = discord.File(buf, "wager.png")
        e = discord.Embed()
        e.set_image(url="attachment://wager.png")
        await self.message.edit(embed=e, attachments=[file], view=self)

@bot.tree.command(name="wager", guild=discord.Object(id=GUILD_ID))
async def wager(i, size: int, team_a: str, team_b: str, prize: str):
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
