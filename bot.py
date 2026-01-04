import os
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1443765937793667194

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def setup_hook():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

@bot.event
async def on_ready():
    print(f"ONLINE as {bot.user}")

class ResultModal(discord.ui.Modal, title="End Wager"):
    result = discord.ui.TextInput(label="Result", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.host_id:
            await interaction.response.send_message("Only the host can end the wager.", ephemeral=True)
            return
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.set_field_at(self.view.status_index, name="Status", value="🏁 FINISHED", inline=False)
        embed.add_field(name="Result", value=self.result.value, inline=False)
        await interaction.response.edit_message(embed=embed, view=None)

class BeginView(discord.ui.View):
    def __init__(self, parent):
        super().__init__(timeout=None)
        self.parent = parent
        self.ready = set()

    @discord.ui.button(label="React to Begin", style=discord.ButtonStyle.success, emoji="⚔️")
    async def begin(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.mention not in self.parent.team_a + self.parent.team_b:
            await interaction.response.send_message("You are not part of this wager.", ephemeral=True)
            return
        self.ready.add(interaction.user.id)
        if len(self.ready) == self.parent.team_size * 2:
            embed = interaction.message.embeds[0]
            embed.set_field_at(self.parent.status_index, name="Status", value="⚔️ IN PROGRESS", inline=False)
            await interaction.message.edit(embed=embed, view=None)
        else:
            await interaction.response.send_message("Ready ✔", ephemeral=True)

class WagerView(discord.ui.View):
    def __init__(self, host_id, team_size, team_a_name, team_b_name):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.team_size = team_size
        self.team_a_name = team_a_name
        self.team_b_name = team_b_name
        self.team_a = []
        self.team_b = []
        self.status_index = 6
        self.locked = False

    def teams(self):
        return (
            "\n".join(self.team_a) if self.team_a else "—",
            "\n".join(self.team_b) if self.team_b else "—"
        )

    async def refresh(self, interaction):
        embed = interaction.message.embeds[0]
        a, b = self.teams()
        embed.set_field_at(3, name=self.team_a_name, value=a, inline=True)
        embed.set_field_at(4, name=self.team_b_name, value=b, inline=True)
        await interaction.response.edit_message(embed=embed, view=self)
        await self.check_full(interaction)

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
        user = interaction.user.mention
        if user in self.team_b:
            self.team_b.remove(user)
        if user not in self.team_a and len(self.team_a) < self.team_size:
            self.team_a.append(user)
        await self.refresh(interaction)

    @discord.ui.button(label="Join Team B", style=discord.ButtonStyle.primary)
    async def join_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user.mention
        if user in self.team_a:
            self.team_a.remove(user)
        if user not in self.team_b and len(self.team_b) < self.team_size:
            self.team_b.append(user)
        await self.refresh(interaction)

    @discord.ui.button(label="End", style=discord.ButtonStyle.danger, emoji="🏁")
    async def end(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("Only the host can end the wager.", ephemeral=True)
            return
        await interaction.response.send_modal(ResultModal(self))

@bot.tree.command(
    name="wager",
    description="Create a wager",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(
    team_size="Players per team",
    team_a_name="Clan or team A name",
    team_b_name="Clan or team B name",
    prize="Prize",
    start_time="Start time"
)
async def wager(
    interaction: discord.Interaction,
    team_size: int,
    team_a_name: str,
    team_b_name: str,
    prize: str,
    start_time: str
):
    embed = discord.Embed(
        title="💎 WAGER",
        description=(
            f"**Match:** {team_size}v{team_size}\n"
            f"**Start Time:** {start_time}\n\n"
            f"**Prize**\n{prize}"
        ),
        color=discord.Color.from_rgb(88, 101, 242)
    )
    embed.add_field(name="Host", value=interaction.user.mention, inline=False)
    embed.add_field(name=team_a_name, value="—", inline=True)
    embed.add_field(name=team_b_name, value="—", inline=True)
    embed.add_field(name="Status", value="🟢 OPEN", inline=False)
    embed.set_footer(text="Join a team • React to begin • Host ends the wager")

    view = WagerView(
        interaction.user.id,
        team_size,
        team_a_name,
        team_b_name
    )

    await interaction.response.send_message(embed=embed, view=view)

bot.run(TOKEN)
