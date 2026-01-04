import os
import re
import discord
import requests
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

def fetch_avatar(url, size=128):
    r = requests.get(url)
    img = Image.open(BytesIO(r.content)).convert("RGBA")
    return img.resize((size, size))

def render_wager_image(view):
    W, H = 1600, 900
    img = Image.new("RGB", (W, H), "#0f1115")
    d = ImageDraw.Draw(img)

    title = ImageFont.truetype("arial.ttf", 64)
    body = ImageFont.truetype("arial.ttf", 36)
    small = ImageFont.truetype("arial.ttf", 28)

    d.text((60, 40), f"WAGER — {view.size}v{view.size}", font=title, fill="white")
    d.text((60, 120), f"Prize: {view.prize}", font=body, fill="#aab")
    d.text((60, 170), f"Host: @{view.host_name}", font=body, fill="#aab")

    if view.middleman_id:
        d.text((60, 220), f"Middleman: @{view.middleman_name}", font=body, fill="#aab")
    else:
        d.text((60, 220), "Middleman: None", font=body, fill="#aab")

    col_y = 320
    d.text((200, col_y - 60), view.a, font=title, fill="#6cf")
    d.text((1000, col_y - 60), view.b, font=title, fill="#fc6")

    ay = col_y
    by = col_y

    for uid in view.team_a_ids():
        m = view.guild.get_member(uid)
        if not m:
            continue
        av = fetch_avatar(m.display_avatar.url)
        img.paste(av, (120, ay), av)
        d.text((280, ay + 40), m.display_name, font=body, fill="white")
        ay += 160

    for uid in view.team_b_ids():
        m = view.guild.get_member(uid)
        if not m:
            continue
        av = fetch_avatar(m.display_avatar.url)
        img.paste(av, (920, by), av)
        d.text((1080, by + 40), m.display_name, font=body, fill="white")
        by += 160

    return img

class JoinButton(discord.ui.Button):
    def __init__(self, label, side):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.side = side

    async def callback(self, interaction):
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
                v.team_b.append(u)

        await v.update_message(interaction)

class MiddlemanButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Pick Middleman", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction):
        v = self.view
        if interaction.user.id != v.host_id:
            return
        await interaction.response.send_message(
            view=MiddlemanSelectView(v),
            ephemeral=True
        )

class EndButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="End Match", style=discord.ButtonStyle.danger)

    async def callback(self, interaction):
        await interaction.response.send_message("Match ended.", ephemeral=True)

class MiddlemanSelect(discord.ui.UserSelect):
    def __init__(self, view):
        super().__init__(min_values=1, max_values=1)
        self.view = view

    async def callback(self, interaction):
        m = interaction.guild.get_member(self.values[0].id)
        if not m or not any(r.id == MIDDLEMAN_ROLE_ID for r in m.roles):
            return await interaction.response.send_message("Invalid middleman", ephemeral=True)
        self.view.middleman_id = m.id
        await interaction.response.send_message("Middleman set", ephemeral=True)

class MiddlemanSelectView(discord.ui.View):
    def __init__(self, view):
        super().__init__(timeout=60)
        self.add_item(MiddlemanSelect(view))

class WagerView(discord.ui.View):
    def __init__(self, interaction, size, a, b, prize):
        super().__init__(timeout=None)
        self.host_id = interaction.user.id
        self.host_name = interaction.user.display_name
        self.guild = interaction.guild
        self.size = size
        self.a = a
        self.b = b
        self.prize = prize
        self.team_a = []
        self.team_b = []
        self.middleman_id = None
        self.message = None

        self.add_item(JoinButton(f"Join {a}", "A"))
        self.add_item(JoinButton(f"Join {b}", "B"))
        self.add_item(MiddlemanButton())
        self.add_item(EndButton())

    @property
    def middleman_name(self):
        m = self.guild.get_member(self.middleman_id)
        return m.display_name if m else ""

    def team_a_ids(self):
        return [uid_from_mention(m) for m in self.team_a if uid_from_mention(m)]

    def team_b_ids(self):
        return [uid_from_mention(m) for m in self.team_b if uid_from_mention(m)]

    async def update_message(self, interaction):
        img = render_wager_image(self)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        file = discord.File(buf, filename="wager.png")

        if interaction.response.is_done():
            await self.message.edit(attachments=[file], view=self)
        else:
            await interaction.response.edit_message(attachments=[file], view=self)

@bot.tree.command(name="wager", guild=discord.Object(id=GUILD_ID))
async def wager(interaction: discord.Interaction, team_size: int, team_a: str, team_b: str, prize: str):
    view = WagerView(interaction, team_size, team_a, team_b, prize)
    img = render_wager_image(view)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    file = discord.File(buf, filename="wager.png")
    await interaction.response.send_message(file=file, view=view)
    view.message = await interaction.original_response()

bot.run(TOKEN)
