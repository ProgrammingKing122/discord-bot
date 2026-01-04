import os
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1443765937793667194

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

def fail(interaction):
    if interaction.response.is_done():
        return interaction.followup.send('❌ **Error has happened — please contact "Levi" for fixes.**', ephemeral=True)
    return interaction.response.send_message('❌ **Error has happened — please contact "Levi" for fixes.**', ephemeral=True)

@bot.event
async def setup_hook():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

@bot.event
async def on_ready():
    print(f"ONLINE as {bot.user}")

class ResultModal(discord.ui.Modal, title="End Wager"):
    result = discord.ui.TextInput(label="Result", style=discord.TextStyle.paragraph)

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.view.host_id:
                return await fail(interaction)
            embed = self.view.build_embed(status="🏁 FINISHED", result=self.result.value)
            await interaction.response.edit_message(embed=embed, view=None)
        except Exception:
            await fail(interaction)

class BeginView(discord.ui.View):
    def __init__(self, parent):
        super().__init__(timeout=None)
        self.parent = parent
        self.ready = set()

    @discord.ui.button(label="React to Begin", style=discord.ButtonStyle.success, emoji="⚔️")
    async def begin(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if interaction.user.id not in self.parent.player_ids():
                return await fail(interaction)
            self.ready.add(interaction.user.id)
            if len(self.ready) == self.parent.team_size * 2:
                embed = self.parent.build_embed(status="⚔️ IN PROGRESS")
                await interaction.message.edit(embed=embed, view=None)
            else:
                await interaction.response.send_message("Ready ✔", ephemeral=True)
        except Exception:
            await fail(interaction)

class WagerView(discord.ui.View):
    def __init__(self, host_id, team_size, a_name, b_name, prize, start_time):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.team_size = team_size
        self.a_name = a_name
        self.b_name = b_name
        self.prize = prize
        self.start_time = start_time
        self.team_a = []
        self.team_b = []
        self.locked = False

    def player_ids(self):
        return {int(u.strip("<@>")) for u in self.team_a + self.team_b}

    def build_embed(self, status="🟢 OPEN", result=None):
        embed = discord.Embed(
            title="💎 WAGER",
            description=(
                f"**Match:** {self.team_size}v{self.team_size}\n"
                f"**Start Time:** {self.start_time}\n\n"
                f"**Prize**\n{self.prize}"
            ),
            color=discord.Color.from_rgb(88, 101, 242)
        )
        embed.add_field(name="Host", value=f"<@{self.host_id}>", inline=False)
        embed.add_field(name=self.a_name, value="\n".join(self.team_a) if self.team_a else "—", inline=True)
        embed.add_field(name=self.b_name, value="\n".join(self.team_b) if self.team_b else "—", inline=True)
        embed.add_field(name="Status", value=status, inline=False)
        if result:
            embed.add_field(name="Result", value=result, inline=False)
        embed.set_footer(text="Join teams • React to begin • Host ends the wager")
        return embed

    async def refresh(self, interaction):
        try:
            embed = self.build_embed()
            await interaction.response.edit_message(embed=embed, view=self)
            await self.check_full(interaction)
        except Exception:
            await fail(interaction)

    async def check_full(self, interaction):
        if self.locked:
            return
        if len(self.team_a) == self.team_size and len(self.team_b) == self.team_size:
            self.locked = True
            mentions = " ".join(self.team_a + self.team_b)
            await interaction.followup.send(
                f"{mentions}\n⚔️ **Teams are full — react to begin**",
                view=BeginView(self)
            )

    @discord.ui.button(label="Join Team A", style=discord.ButtonStyle.primary)
    async def join_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            u = interaction.user.mention
            if u in self.team_b:
                self.team_b.remove(u)
            if u not in self.team_a and len(self.team_a) < self.team_size:
                self.team_a.append(u)
            await self.refresh(interaction)
        except Exception:
            await fail(interaction)

    @discord.ui.button(label="Join Team B", style=discord.ButtonStyle.primary)
    async def join_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            u = interaction.user.mention
            if u in self.team_a:
                self.team_a.remove(u)
            if u not in self.team_b and len(self.team_b) < self.team_size:
                self.team_b.append(u)
            await self.refresh(interaction)
        except Exception:
            await fail(interaction)

    @discord.ui.button(label="End", style=discord.ButtonStyle.danger, emoji="🏁")
    async def end(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            return await fail(interaction)
        await interaction.response.send_modal(ResultModal(self))

@bot.tree.command(
    name="wager",
    description="Create a wager",
    guild=discord.Object(id=GUILD_ID)
)
async def wager(
    interaction: discord.Interaction,
    team_size: int,
    team_a_name: str,
    team_b_name: str,
    prize: str,
    start_time: str
):
    view = WagerView(
        interaction.user.id,
        team_size,
        team_a_name,
        team_b_name,
        prize,
        start_time
    )
    embed = view.build_embed()
    await interaction.response.send_message(embed=embed, view=view)

bot.run(TOKEN)
