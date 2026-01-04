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
    while text and draw.textlength(text + "…", font=font) > w:
        text = text[:-1]
    return text + "…"

async def avatar(session, url, s=56):
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

def bg(img):
    W, H = img.size
    d = ImageDraw.Draw(img)
    for y in range(0, H, 2):
        s = int(12 + y * 0.03)
        d.line([(0, y), (W, y)], fill=(s, s, s))
    for x in range(0, W, 6):
        d.line([(x, 0), (x - H, H)], fill=(10, 10, 16))

async def render_results(v):
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), "#07090d")
    bg(img)
    d = ImageDraw.Draw(img)

    ta_k = sum(v.stats[u][0] for u in v.team_a if u in v.stats)
    tb_k = sum(v.stats[u][0] for u in v.team_b if u in v.stats)
    diff = abs(ta_k - tb_k)

    if ta_k == tb_k:
        win = "DRAW"
        col = "#ffd24c"
    else:
        w = v.a if ta_k > tb_k else v.b
        l = v.b if ta_k > tb_k else v.a
        if diff >= 15:
            win, col = f"{w} DESTROYED {l}", "#ff4c4c"
        elif diff >= 10:
            win, col = f"{w} SLAMMED {l}", "#ff6a4c"
        elif diff >= 6:
            win, col = f"{w} DOMINATED {l}", "#ff9c4c"
        elif diff >= 3:
            win, col = f"{w} DEFEATED {l}", "#ffd24c"
        else:
            win, col = f"{w} WINS NARROWLY", "#4cff7a"

    win = clamp(d, win, f(54), 1180)
    d.text((W//2 - d.textlength(win, font=f(54))//2, 28), win, fill=col, font=f(54))

    d.text((60, 110), f"{v.a} — {ta_k} KILLS", fill="#4cc2ff", font=f(34))
    d.text((720, 110), f"{v.b} — {tb_k} KILLS", fill="#ffb84c", font=f(34))

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

    table_w = 520
    lx, rx = 60, 700
    y = 180

    name_x = 80
    k_x = table_w - 170
    d_x = table_w - 110
    kd_x = table_w - 40

    d.text((lx + name_x, y), "NAME", fill="#b5b9c7", font=f(22))
    d.text((lx + k_x, y), "K", fill="#b5b9c7", font=f(22))
    d.text((lx + d_x, y), "D", fill="#b5b9c7", font=f(22))
    d.text((lx + kd_x - 20, y), "KD", fill="#b5b9c7", font=f(22))

    d.text((rx + name_x, y), "NAME", fill="#b5b9c7", font=f(22))
    d.text((rx + k_x, y), "K", fill="#b5b9c7", font=f(22))
    d.text((rx + d_x, y), "D", fill="#b5b9c7", font=f(22))
    d.text((rx + kd_x - 20, y), "KD", fill="#b5b9c7", font=f(22))

    y += 44

    async with aiohttp.ClientSession() as s:
        for side, base_x, team, mvp_u in [
            (v.team_a, lx, v.team_a, mvp_a),
            (v.team_b, rx, v.team_b, mvp_b),
        ]:
            ry = y
            for uid in team:
                if uid not in v.stats:
                    continue
                m = v.guild.get_member(uid)
                if not m:
                    continue
                k, dth = v.stats[uid]
                kd = round(k / dth, 2) if dth else round(float(k), 2)
                is_mvp = uid == mvp_u
                strip, badge = status_strip(k, dth, is_mvp)

                av = await avatar(s, m.display_avatar.url)
                img.paste(av, (base_x, ry), av)

                d.rectangle([base_x + table_w - 8, ry, base_x + table_w, ry + 56], fill=strip)
                if badge:
                    d.text((base_x + table_w - 32, ry + 14), badge, fill=strip, font=f(26))

                name = clamp(d, m.display_name, f(26), table_w - 240)
                d.text((base_x + name_x, ry + 14), name, fill="#ffd700" if is_mvp else "white", font=f(26))

                d.text((base_x + k_x, ry + 14), str(k), fill="white", font=f(26))
                d.text((base_x + d_x, ry + 14), str(dth), fill="white", font=f(26))

                kd_text = str(kd)
                d.text(
                    (base_x + kd_x - d.textlength(kd_text, font=f(26)), ry + 14),
                    kd_text,
                    fill="white",
                    font=f(26)
                )

                ry += 68

    footer = "Brought to you by levi"
    d.text(
        (W//2 - d.textlength(footer, font=f(18))//2, H - 30),
        footer,
        fill="#cccccc",
        font=f(18)
    )

    return img

bot.run(TOKEN)
