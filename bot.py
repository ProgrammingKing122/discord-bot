import os
import discord
import aiohttp
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands
from textwrap import shorten

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

def status_strip(k, d, mvp):
    if k == 0 and d >= 1:
        return "#ff4c4c", "☠"
    if mvp:
        return "#ffd700", "👑"
    if k > d:
        return "#4cff7a", ""
    if k == d:
        return "#ffd24c", ""
    return "#ff4c4c", ""

async def render_results(v):
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), "#07090d")
    bg = ImageDraw.Draw(img)
    for i in range(0, H, 2):
        s = int(18 + i * 0.025)
        bg.line([(0, i), (W, i)], fill=(s, s, s))
    for i in range(0, W, 6):
        bg.line([(i, 0), (i - H, H)], fill=(12, 12, 18))

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

    win_text = shorten(win_text, width=28, placeholder="…")
    d.text((W//2 - d.textlength(win_text, font=f(48))//2, 36), win_text, fill=win_col, font=f(48))

    d.text((90, 110), f"{v.a} — {ta_k} KILLS", fill="#4cc2ff", font=f(32))
    d.text((760, 110), f"{v.b} — {tb_k} KILLS", fill="#ffb84c", font=f(32))

    def mvp(team):
        rows = []
        for u in team:
            if u not in v.stats:
                continue
            k, dth = v.stats[u]
            kd = k / dth if dth else k
            rows.append((u, k, kd))
        if len(rows) < 2:
            return None
        rows.sort(key=lambda x: (x[1], x[2]), reverse=True)
        if rows[0][1:] == rows[1][1:]:
            return None
        return rows[0][0]

    mvp_a = mvp(v.team_a)
    mvp_b = mvp(v.team_b)

    lx, rx = 60, 460
    px = 860
    row_h = 70
    start_y = 190

    d.text((lx + 90, start_y - 30), "NAME", fill="#b5b9c7", font=f(20))
    d.text((lx + 320, start_y - 30), "K", fill="#b5b9c7", font=f(20))
    d.text((lx + 370, start_y - 30), "D", fill="#b5b9c7", font=f(20))
    d.text((lx + 420, start_y - 30), "KD", fill="#b5b9c7", font=f(20))

    d.text((rx + 90, start_y - 30), "NAME", fill="#b5b9c7", font=f(20))
    d.text((rx + 320, start_y - 30), "K", fill="#b5b9c7", font=f(20))
    d.text((rx + 370, start_y - 30), "D", fill="#b5b9c7", font=f(20))
    d.text((rx + 420, start_y - 30), "KD", fill="#b5b9c7", font=f(20))

    d.rectangle([px, start_y - 40, W - 40, H - 40], outline="#2a2d36", width=2)
    d.text((px + 20, start_y - 32), "PROMO", fill="#ffd700", font=f(24))
    d.text((px + 20, start_y + 10), "• Ranked wagers\n• Middleman secured\n• Auto results\n• MVP tracking", fill="#b5b9c7", font=f(22))

    async with aiohttp.ClientSession() as s:
        y = start_y
        for uid in v.team_a:
            if uid not in v.stats:
                continue
            m = v.guild.get_member(uid)
            if not m:
                continue
            k, dth = v.stats[uid]
            kd = round(k / dth, 2) if dth else round(float(k), 2)
            is_mvp = uid == mvp_a
            col, badge = status_strip(k, dth, is_mvp)

            av = await avatar(s, m.display_avatar.url)
            img.paste(av, (lx, y), av)
            d.rectangle([lx + 450, y, lx + 458, y + 64], fill=col)
            if badge:
                d.text((lx + 465, y + 16), badge, fill=col, font=f(24))

            name = shorten(m.display_name, width=14, placeholder="…")
            d.text((lx + 78, y + 14), name, fill="#ffd700" if is_mvp else "white", font=f(24))
            d.text((lx + 320, y + 14), str(k), fill="white", font=f(24))
            d.text((lx + 370, y + 14), str(dth), fill="white", font=f(24))
            d.text((lx + 420, y + 14), str(kd), fill="white", font=f(24))
            y += row_h

        y = start_y
        for uid in v.team_b:
            if uid not in v.stats:
                continue
            m = v.guild.get_member(uid)
            if not m:
                continue
            k, dth = v.stats[uid]
            kd = round(k / dth, 2) if dth else round(float(k), 2)
            is_mvp = uid == mvp_b
            col, badge = status_strip(k, dth, is_mvp)

            av = await avatar(s, m.display_avatar.url)
            img.paste(av, (rx, y), av)
            d.rectangle([rx + 450, y, rx + 458, y + 64], fill=col)
            if badge:
                d.text((rx + 465, y + 16), badge, fill=col, font=f(24))

            name = shorten(m.display_name, width=14, placeholder="…")
            d.text((rx + 78, y + 14), name, fill="#ffd700" if is_mvp else "white", font=f(24))
            d.text((rx + 320, y + 14), str(k), fill="white", font=f(24))
            d.text((rx + 370, y + 14), str(dth), fill="white", font=f(24))
            d.text((rx + 420, y + 14), str(kd), fill="white", font=f(24))
            y += row_h

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

class Cancel(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Cancel", style=discord.ButtonStyle.danger)
    async def callback(self, i):
        if i.user.id not in {self.view.host_id, self.view.middleman_id}:
            return
        await self.view.message.delete()

class WagerView(discord.ui.View):
    def __init__(self, i, size, a, b, prize):
        super().__init__(timeout=None)
        self.guild = i.guild
        self.host_id = i.user.id
        self.middleman_id = None
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
        self.add_item(Cancel())
    async def update(self):
        img = await render_results(self)
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
    img = await render_results(v)
    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    file = discord.File(buf, "wager.png")
    e = discord.Embed()
    e.set_image(url="attachment://wager.png")
    await i.response.send_message(embed=e, file=file, view=v)
    v.message = await i.original_response()

bot.run(TOKEN)
