import os
import discord
import aiohttp
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1443765937793667194
MIDDLEMAN_ROLE_ID = 1457241934832861255

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "fonts", "Inter_24pt-ExtraBoldItalic.ttf")

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def setup_hook():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

def font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except:
        return ImageFont.load_default()

async def fetch_avatar(session, url, size=120):
    async with session.get(url) as r:
        data = await r.read()
    return Image.open(BytesIO(data)).convert("RGBA").resize((size, size))

async def render_wager(view, results=False, winner=None):
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), "#0b0d12")
    d = ImageDraw.Draw(img)

    title = font(64)
    header = font(48)
    body = font(36)
    vs_font = font(96)

    if not results:
        d.text((40, 30), f"WAGER {view.size}v{view.size}", fill="white", font=title)
    else:
        d.text((40, 30), "MATCH RESULTS", fill="white", font=title)

    d.text((40, 110), f"Prize: {view.prize}", fill="#b5b9c7", font=body)
    d.text((40, 155), f"Host: {view.host_name}", fill="#b5b9c7", font=body)

    if view.no_middleman:
        mm = "None"
    else:
        mm = view.middleman_name or "Pending"

    d.text((40, 200), f"Middleman: {mm}", fill="#b5b9c7", font=body)

    d.text((160, 270), view.a, fill="#4cc2ff", font=header)
    d.text((820, 270), view.b, fill="#ffb84c", font=header)

    d.text((610, 330), "VS", fill="#ffffff", font=vs_font)

    ay = 360
    by = 360

    async with aiohttp.ClientSession() as session:
        for uid in view.team_a:
            m = view.guild.get_member(uid) or await view.guild.fetch_member(uid)
            av = await fetch_avatar(session, m.display_avatar.url)
            img.paste(av, (120, ay), av)
            d.text((270, ay + 40), m.display_name, fill="white", font=body)
            ay += 150

        for uid in view.team_b:
            m = view.guild.get_member(uid) or await view.guild.fetch_member(uid)
            av = await fetch_avatar(session, m.display_avatar.url)
            img.paste(av, (780, by), av)
            d.text((930, by + 40), m.display_name, fill="white", font=body)
            by += 150

    if not view.team_a:
        d.text((160, ay), "No players yet", fill="#555", font=body)
    if not view.team_b:
        d.text((820, by), "No players yet", fill="#555", font=body)

    if results and winner:
        d.text((450, 620), f"🏆 {winner} WINS", fill="#4cff7a", font=header)

    return img

class JoinButton(discord.ui.Button):
    def __init__(self, label, side):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.side = side

    async def callback(self, interaction):
        await interaction.response.defer()
        v = self.view
        uid = interaction.user.id

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

        await v.update()

class NoMiddlemanButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="No Middleman", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction):
        if interaction.user.id != self.view.host_id:
            return
        self.view.no_middleman = True
        self.view.middleman_id = None
        await interaction.response.defer()
        await self.view.update()

class MiddlemanButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Pick Middleman", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction):
        if interaction.user.id != self.view.host_id:
            return
        await interaction.response.send_message(
            view=MiddlemanSelectView(self.view),
            ephemeral=True
        )

class EndButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="End Match", style=discord.ButtonStyle.danger)

    async def callback(self, interaction):
        v = self.view
        winner = v.a if len(v.team_a) > len(v.team_b) else v.b if len(v.team_b) > len(v.team_a) else "DRAW"
        img = await render_wager(v, results=True, winner=winner)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        file = discord.File(buf, filename="results.png")
        embed = discord.Embed()
        embed.set_image(url="attachment://results.png")

        await interaction.response.edit_message(embed=embed, attachments=[file], view=None)

class MiddlemanSelect(discord.ui.UserSelect):
    def __init__(self, view):
        super().__init__(min_values=1, max_values=1)
        self.view = view

    async def callback(self, interaction):
        m = interaction.guild.get_member(self.values[0].id)
        if not m or not any(r.id == MIDDLEMAN_ROLE_ID for r in m.roles):
            return await interaction.response.send_message("Invalid middleman", ephemeral=True)
        self.view.middleman_id = m.id
        self.view.no_middleman = False
        await interaction.response.defer()
        await self.view.update()

class MiddlemanSelectView(discord.ui.View):
    def __init__(self, view):
        super().__init__(timeout=60)
        self.add_item(MiddlemanSelect(view))

class WagerView(discord.ui.View):
    def __init__(self, interaction, size, a, b, prize):
        super().__init__(timeout=None)
        self.guild = interaction.guild
        self.host_id = interaction.user.id
        self.host_name = interaction.user.display_name
        self.size = size
        self.a = a
        self.b = b
        self.prize = prize
        self.team_a = []
        self.team_b = []
        self.middleman_id = None
        self.no_middleman = False
        self.message = None

        self.add_item(JoinButton(f"Join {a}", "A"))
        self.add_item(JoinButton(f"Join {b}", "B"))
        self.add_item(MiddlemanButton())
        self.add_item(NoMiddlemanButton())
        self.add_item(EndButton())

    @property
    def middleman_name(self):
        m = self.guild.get_member(self.middleman_id)
        return m.display_name if m else None

    async def update(self):
        img = await render_wager(self)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        file = discord.File(buf, filename="wager.png")
        embed = discord.Embed()
        embed.set_image(url="attachment://wager.png")

        await self.message.edit(embed=embed, attachments=[file], view=self)

@bot.tree.command(name="wager", guild=discord.Object(id=GUILD_ID))
async def wager(interaction, team_size: int, team_a: str, team_b: str, prize: str):
    view = WagerView(interaction, team_size, team_a, team_b, prize)
    img = await render_wager(view)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    file = discord.File(buf, filename="wager.png")
    embed = discord.Embed()
    embed.set_image(url="attachment://wager.png")

    await interaction.response.send_message(embed=embed, file=file, view=view)
    view.message = await interaction.original_response()

bot.run(TOKEN)
