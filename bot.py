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

async def avatar(session, url, s=64):
    async with session.get(url) as r:
        return Image.open(BytesIO(await r.read())).convert("RGBA").resize((s, s))

def status_strip(k, d, mvp=False):
    if mvp:
        return "#ffd700", "👑"
    if k == 0 and d >= 1:
        return "#ff4c4c", "☠"
    if k > d:
        return "#4cff7a", ""
    if k == d:
        return "#ffd24c", ""
    return "#ff4c4c", ""

async def render_wager(v):
    img = Image.new("RGB", (1280, 720), "#07090d")
    bg = ImageDraw.Draw(img)
    for i in range(0, 720, 2):
        shade = int(18 + i * 0.025)
        bg.line([(0, i), (1280, i)], fill=(shade, shade, shade))
    for i in range(0, 1280, 6):
        bg.line([(i, 0), (i - 720, 720)], fill=(12, 12, 18))

    d = ImageDraw.Draw(img)
    d.text((40, 30), f"WAGER {v.size}v{v.size}", fill="white", font=f(64))
    d.text((40, 120), f"Prize: {v.prize}", fill="#b5b9c7", font=f(36))
    d.text((40, 165), f"Host: {v.host}", fill="#b5b9c7", font=f(36))
    mm = "None" if v.no_middleman else (v.middleman_name or "Pending")
    d.text((40, 210), f"Middleman: {mm}", fill="#b5b9c7", font=f(36))

    d.text((160, 270), v.a, fill="#4cc2ff", font=f(48))
    d.text((820, 270), v.b, fill="#ffb84c", font=f(48))
    d.text((600, 340), "VS", fill="white", font=f(96))

    ay = by = 380

    async with aiohttp.ClientSession() as s:
        for uid in v.team_a:
            m = v.guild.get_member(uid)
            if not m:
                continue
            av = await avatar(s, m.display_avatar.url)
            img.paste(av, (120, ay), av)
            d.text((240, ay + 18), m.display_name, fill="white", font=f(32))
            ay += 90

        for uid in v.team_b:
            m = v.guild.get_member(uid)
            if not m:
                continue
            av = await avatar(s, m.display_avatar.url)
            img.paste(av, (780, by), av)
            d.text((900, by + 18), m.display_name, fill="white", font=f(32))
            by += 90

    return img

async def render_results(v):
    img = Image.new("RGB", (1280, 720), "#07090d")
    bg = ImageDraw.Draw(img)
    for i in range(0, 720, 2):
        shade = int(18 + i * 0.025)
        bg.line([(0, i), (1280, i)], fill=(shade, shade, shade))
    for i in range(0, 1280, 6):
        bg.line([(i, 0), (i - 720, 720)], fill=(12, 12, 18))

    d = ImageDraw.Draw(img)

    ta_k = sum(v.stats[u][0] for u in v.team_a if u in v.stats)
    tb_k = sum(v.stats[u][0] for u in v.team_b if u in v.stats)
    diff = abs(ta_k - tb_k)

    if ta_k == tb_k:
        win_text = "DRAW"
        win_col = "#ffd24c"
    else:
        w = v.a if ta_k > tb_k else v.b
        l = v.b if ta_k > tb_k else v.a
        if diff >= 15:
            win_text = f"{w} DESTROYED {l}"
            win_col = "#ff4c4c"
        elif diff >= 10:
            win_text = f"{w} SLAMMED {l}"
            win_col = "#ff6a4c"
        elif diff >= 6:
            win_text = f"{w} DOMINATED {l}"
            win_col = "#ff9c4c"
        elif diff >= 3:
            win_text = f"{w} DEFEATED {l}"
            win_col = "#ffd24c"
        else:
            win_text = f"{w} WINS NARROWLY"
            win_col = "#4cff7a"

    d.text((460, 40), win_text, fill=win_col, font=f(52))
    d.text((100, 120), f"{v.a} — {ta_k} KILLS", fill="#4cc2ff", font=f(36))
    d.text((760, 120), f"{v.b} — {tb_k} KILLS", fill="#ffb84c", font=f(36))

    def mvp(team):
        best = None
        for u in team:
            if u not in v.stats:
                continue
            k, dth = v.stats[u]
            kd = k / dth if dth else k
            score = (k, kd)
            if not best or score > best[1]:
                best = (u, score)
        return best[0] if best else None

    mvp_a = mvp(v.team_a)
    mvp_b = mvp(v.team_b)

    lx, rx = 80, 700
    hy = 180
    ry_a = ry_b = 220

    d.text((lx + 90, hy), "NAME", fill="#b5b9c7", font=f(22))
    d.text((lx + 360, hy), "K", fill="#b5b9c7", font=f(22))
    d.text((lx + 420, hy), "D", fill="#b5b9c7", font=f(22))
    d.text((lx + 480, hy), "KD", fill="#b5b9c7", font=f(22))

    d.text((rx + 90, hy), "NAME", fill="#b5b9c7", font=f(22))
    d.text((rx + 360, hy), "K", fill="#b5b9c7", font=f(22))
    d.text((rx + 420, hy), "D", fill="#b5b9c7", font=f(22))
    d.text((rx + 480, hy), "KD", fill="#b5b9c7", font=f(22))

    async with aiohttp.ClientSession() as s:
        for uid in v.team_a:
            if uid not in v.stats:
                continue
            m = v.guild.get_member(uid)
            if not m:
                continue
            k, dth = v.stats[uid]
            kd = round((k / dth), 2) if dth else round(float(k), 2)
            is_mvp = uid == mvp_a
            strip_col, badge = status_strip(k, dth, is_mvp)

            av = await avatar(s, m.display_avatar.url)
            img.paste(av, (lx, ry_a), av)
            d.rectangle([lx + 560, ry_a, lx + 570, ry_a + 64], fill=strip_col)
            if badge:
                d.text((lx + 578, ry_a + 16), badge, fill=strip_col, font=f(28))

            d.text((lx + 85, ry_a + 14), m.display_name, fill="#ffd700" if is_mvp else "white", font=f(28))
            d.text((lx + 360, ry_a + 14), str(k), fill="white", font=f(28))
            d.text((lx + 420, ry_a + 14), str(dth), fill="white", font=f(28))
            d.text((lx + 480, ry_a + 14), str(kd), fill="white", font=f(28))
            ry_a += 74

        for uid in v.team_b:
            if uid not in v.stats:
                continue
            m = v.guild.get_member(uid)
            if not m:
                continue
            k, dth = v.stats[uid]
            kd = round((k / dth), 2) if dth else round(float(k), 2)
            is_mvp = uid == mvp_b
            strip_col, badge = status_strip(k, dth, is_mvp)

            av = await avatar(s, m.display_avatar.url)
            img.paste(av, (rx, ry_b), av)
            d.rectangle([rx + 560, ry_b, rx + 570, ry_b + 64], fill=strip_col)
            if badge:
                d.text((rx + 578, ry_b + 16), badge, fill=strip_col, font=f(28))

            d.text((rx + 85, ry_b + 14), m.display_name, fill="#ffd700" if is_mvp else "white", font=f(28))
            d.text((rx + 360, ry_b + 14), str(k), fill="white", font=f(28))
            d.text((rx + 420, ry_b + 14), str(dth), fill="white", font=f(28))
            d.text((rx + 480, ry_b + 14), str(kd), fill="white", font=f(28))
            ry_b += 74

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
            return
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
            await self.view.message.delete()
        except:
            pass

class MMSelect(discord.ui.UserSelect):
    def __init__(self, v):
        super().__init__(min_values=1, max_values=1)
        self.v = v

    async def callback(self, i):
        m = i.guild.get_member(self.values[0].id)
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
        self.v.stats[self.uid] = (int(self.kills.value), int(self.deaths.value))
        await i.response.send_message("Saved", ephemeral=True)

class PlayerPick(discord.ui.Select):
    def __init__(self, v):
        self.v = v
        opts = []
        for uid in dict.fromkeys(v.team_a + v.team_b):
            m = v.guild.get_member(uid)
            if m:
                opts.append(discord.SelectOption(label=m.display_name, value=str(uid)))
        super().__init__(placeholder="Select war player", min_values=1, max_values=1, options=opts[:25])

    async def callback(self, i):
        if i.user.id not in {self.v.host_id, self.v.middleman_id}:
            return await i.response.send_message("Not allowed", ephemeral=True)
        await i.response.send_modal(StatsModal(self.v, int(self.values[0])))

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
