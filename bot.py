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

def f(size):
    try:
        return ImageFont.truetype(FONT, size)
    except:
        return ImageFont.load_default()

def clamp(draw, text, font, w):
    if draw.textlength(text, font=font) <= w:
        return text
    t = text
    while t and draw.textlength(t + "…", font=font) > w:
        t = t[:-1]
    return (t + "…") if t else "…"

def fmt_num(n):
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

async def avatar(session, url, s=72):
    async with session.get(url) as r:
        return Image.open(BytesIO(await r.read())).convert("RGBA").resize((s, s))

def bg(img):
    W, H = img.size
    d = ImageDraw.Draw(img)
    for y in range(0, H, 2):
        shade = int(14 + y * 0.025)
        d.line([(0, y), (W, y)], fill=(shade, shade, shade))
    for x in range(0, W, 6):
        d.line([(x, 0), (x - H, H)], fill=(10, 10, 16))

def status_strip(k, dth, mvp):
    if k == 0 and dth >= 1:
        return "#ff4c4c", "☠"
    if mvp:
        return "#ffd700", "👑"
    if k > dth:
        return "#4cff7a", ""
    if k == dth:
        return "#ffd24c", ""
    return "#ff4c4c", ""

def win_line(v, ta_k, tb_k):
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
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), "#07090d")
    bg(img)
    d = ImageDraw.Draw(img)

    d.text((40, 30), f"WAGER {v.size}v{v.size}", fill="white", font=f(64))
    d.text((40, 120), f"Prize: {v.prize}", fill="#b5b9c7", font=f(36))
    d.text((40, 165), f"Host: {v.host}", fill="#b5b9c7", font=f(36))
    mm = "None" if v.no_middleman else (v.middleman_name or "Pending")
    d.text((40, 210), f"Middleman: {mm}", fill="#b5b9c7", font=f(36))

    d.text((160, 270), v.a, fill="#4cc2ff", font=f(48))
    d.text((820, 270), v.b, fill="#ffb84c", font=f(48))

    vs = "VS"
    vs_font = f(96)
    vs_x = (W - d.textlength(vs, font=vs_font)) // 2
    d.text((vs_x, 340), vs, fill="white", font=vs_font)

    ay = by = 380

    async with aiohttp.ClientSession() as s:
        for uid in v.team_a:
            m = v.guild.get_member(uid) or await v.guild.fetch_member(uid)
            av = await avatar(s, m.display_avatar.url, 64)
            img.paste(av, (120, ay), av)
            name = clamp(d, m.display_name, f(32), 420)
            d.text((240, ay + 18), name, fill="white", font=f(32))
            ay += 90

        for uid in v.team_b:
            m = v.guild.get_member(uid) or await v.guild.fetch_member(uid)
            av = await avatar(s, m.display_avatar.url, 64)
            img.paste(av, (780, by), av)
            name = clamp(d, m.display_name, f(32), 420)
            d.text((900, by + 18), name, fill="white", font=f(32))
            by += 90

    if not v.team_a:
        d.text((160, ay), "No players yet", fill="#555", font=f(32))
    if not v.team_b:
        d.text((820, by), "No players yet", fill="#555", font=f(32))

    return img

async def render_results(v):
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), "#07090d")
    bg(img)
    d = ImageDraw.Draw(img)

    ta_k = sum(v.stats[u][0] for u in v.team_a if u in v.stats)
    tb_k = sum(v.stats[u][0] for u in v.team_b if u in v.stats)

    wl, wc = win_line(v, ta_k, tb_k)
    wl = clamp(d, wl, f(68), 1200)
    d.text((W // 2 - d.textlength(wl, font=f(68)) // 2, 24), wl, fill=wc, font=f(68))

    table_w = 680
    lx, rx = 60, 760

    left_head = clamp(d, f"{v.a} — {ta_k} KILLS", f(38), table_w)
    right_head = clamp(d, f"{v.b} — {tb_k} KILLS", f(38), table_w)
    d.text((lx, 120), left_head, fill="#4cc2ff", font=f(38))
    d.text((rx, 120), right_head, fill="#ffb84c", font=f(38))

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

    header_y = 200
    row_start = header_y + 52

    name_x = 90
    name_w = table_w - 320

    k_w = 80
    d_w = 80
    kd_w = 90

    k_x = table_w - (k_w + d_w + kd_w)
    d_x = table_w - (d_w + kd_w)
    kd_x = table_w - kd_w

    for bx in (lx, rx):
        d.text((bx + name_x, header_y), "NAME", fill="#b5b9c7", font=f(26))
        d.text((bx + k_x, header_y), "K", fill="#b5b9c7", font=f(26))
        d.text((bx + d_x, header_y), "D", fill="#b5b9c7", font=f(26))
        d.text((bx + kd_x + kd_w - 26, header_y), "KD", fill="#b5b9c7", font=f(26))

    async with aiohttp.ClientSession() as s:
        for base_x, team, mvp_u in ((lx, v.team_a, mvp_a), (rx, v.team_b, mvp_b)):
            y = row_start
            for uid in team:
                if uid not in v.stats:
                    continue
                m = v.guild.get_member(uid) or await v.guild.fetch_member(uid)
                k, dth = v.stats[uid]
                kd = (k / dth) if dth else float(k)

                is_mvp = uid == mvp_u
                strip_col, badge = status_strip(k, dth, is_mvp)

                av = await avatar(s, m.display_avatar.url)
                img.paste(av, (base_x, y), av)

                d.rectangle([base_x + table_w - 10, y, base_x + table_w, y + 72], fill=strip_col)
                if badge:
                    d.text((base_x + table_w - 42, y + 20), badge, fill=strip_col, font=f(30))

                name = clamp(d, m.display_name, f(32), name_w)
                d.text((base_x + name_x, y + 20), name, fill="#ffd700" if is_mvp else "white", font=f(32))

                k_txt = fmt_num(k)
                d_txt = fmt_num(dth)
                kd_txt = "∞" if dth == 0 and k > 0 else fmt_num(kd)

                d.text((base_x + k_x + k_w - d.textlength(k_txt, font=f(32)), y + 20), k_txt, fill="white", font=f(32))
                d.text((base_x + d_x + d_w - d.textlength(d_txt, font=f(32)), y + 20), d_txt, fill="white", font=f(32))
                d.text((base_x + kd_x + kd_w - d.textlength(kd_txt, font=f(32)), y + 20), kd_txt, fill="white", font=f(32))

                y += 84
                if y > H - 90:
                    break

    footer = "Brought to you by levi"
    d.text((W // 2 - d.textlength(footer, font=f(18)) // 2, H - 28), footer, fill="#d0d0d0", font=f(18))
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
        picked = self.values[0].id
        m = i.guild.get_member(picked) or await i.guild.fetch_member(picked)
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
