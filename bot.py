import os
import re
import discord
import aiohttp
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1443765937793667194
MIDDLEMAN_ROLE_ID = 1457241934832861255

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def setup_hook():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

def uid_from_mention(s):
    m = re.search(r"\d{15,21}", s or "")
    return int(m.group(0)) if m else None

async def fetch_avatar(session, url, size=140):
    async with session.get(url) as r:
        data = await r.read()
    return Image.open(BytesIO(data)).convert("RGBA").resize((size, size))

async def render_wager_image(view):
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), "#0b0d12")
    d = ImageDraw.Draw(img)

    title = ImageFont.load_default()
    body = ImageFont.load_default()

    d.text((40, 30), f"WAGER {view.size}v{view.size}", fill="white", font=title)
    d.text((40, 70), f"Prize: {view.prize}", fill="#aab", font=body)
    d.text((40, 100), f"Host: {view.host_name}", fill="#aab", font=body)
    d.text((40, 130), f"Middleman: {view.middleman_name or 'None'}", fill="#aab", font=body)

    d.text((160, 180), view.a, fill="#4cc2ff", font=title)
    d.text((820, 180), view.b, fill="#ffb84c", font=title)

    ay = 230
    by = 230

    async with aiohttp.ClientSession() as session:
        for uid in view.team_a_ids():
            m = view.guild.get_member(uid)
            if not m:
                continue
            av = await fetch_avatar(session, m.display_avatar.url)
            img.paste(av, (120, ay), av)
            d.text((280, ay + 50), m.display_name, fill="white", font=body)
            ay += 170

        for uid in view.team_b_ids():
            m = view.guild.get_member(uid)
            if not m:
                continue
            av = await fetch_avatar(session, m.display_avatar.url)
            img.paste(av, (780, by), av)
            d.text((940, by + 50), m.display_name, fill="white", font=body)
            by += 170

    return img

class JoinButton(discord.ui.Button):
    def __init__(self, label, side):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.side = side

    async def callback(self, interaction):
        await interaction.response.defer()
        v = self.view
        u = interaction.user.mention

        if self.side == "A":
            if u in v.team_b:
                v.team_b.remove(u)
            if u not in v.team_a:
                v.team_a.append(u)
        else:
            if u in v.team_a:
                v.team_a.remove(u)
            if u not in v.team_b:
