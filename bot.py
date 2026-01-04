import os
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

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

class BeginView(discord.ui.View):
    def __init__(self, mentions):
        super().__init__(timeout=None)
        self.mentions = mentions
        self.ready = set()

    @discord.ui.button(label="React to Begin", style=discord.ButtonStyle.success, emoji="⚔️")
    async def begin(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.mentions:
            await interaction.response.send_message("You are not part of this wager.", ephemeral=True)
            return
        self.ready.add(interaction.user.id)
        if self.ready == self.mentions:
            await interaction.message.edit(content="⚔️ **Wager started!**", view=None)
        else:
            await interaction.response.send_message("Ready ✔", ephemeral=True)

class WagerView(discord.ui.View):
    def __init__(self, host_id, team_size, team_a_name, team_b_name, start_time):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.team_size = team_size
        self.team_a_name = team_a_name
        self.team_b_name = team_b_name
        self.team_a = []
        self.team_b = []
        self.start_time = start_time
        self.started = False

    def render_teams(self):
        return (
            "\n".join(self.team_a) if self.team_a else "—",
            "\n".join(self.team_b) if self.team_b else "—"
        )

    async def update(self, interaction):
        embed = interaction.message.embeds[0]
        a, b = self.render_teams()
        embed.set_field_at(3, name=self.team_a_name, value=a, inline=True)
        embed.set_field_at(4, name=self.team_b_name, value=b, inline=True)
        await interaction.response.edit_message(embed=embed, view=self)
        await self.check_full(interaction)

    async def check_full(self, interaction):
        if self.started:
            return
        if len(self.team_a) == self.team_size and len(self.team_b) == self.team_size:
            self.started = True
            users = {int(u.strip("<@>")) for u in self.team_a + self.team_b}
            mentions = " ".join(self.team_a + self.team_b)
            await interaction.followup.send(
                f"{mentions}\n⚔️ **Teams are full!**\nReact to begin.",
                view=BeginView(users)
            )

    @discord.ui.button(label="Join Team A", style=discord.ButtonStyle.primary)
    async def join_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user.mention
        if user in self.team_b:
            self.team_b.remove(user)
        if user not in self.team_a and len(self.team_a) < self.team_size:
            self.team_a.append(user)
        await self.update(interaction)

    @discord.ui.button(label="Join Team B", style=discord.ButtonStyle.primary)
    async def join_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user.mention
        if user in self.team_a:
            self.team_a.remove(user)
        if user not in self.team_b and len(self.team_b) < self.team_size:
            self.team_b.append(user)
        await self.update(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("Only the host can cancel.", ephemeral=True)
            return
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.set_field_at(len(embed.fields) - 1, name="Status", value="❌ CANCELLED", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)

@bot.tree.command(
    name="wager",
    description="Create a wager",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(
    team_size="Players per team (e.g. 1 for 1v1, 2 for 2v2)",
    team_a_name="Team or clan name for Team A",
    team_b_name="Team or clan name for Team B",
    prize="What is being wagered",
    start_time="Start time (e.g. 18:30)"
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
        title="💎 Wager",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Host", value=interaction.user.mention, inline=False)
    embed.add_field(name="Match", value=f"{team_size}v{team_size}", inline=True)
    embed.add_field(name="Start Time", value=start_time, inline=True)
    embed.add_field(name=team_a_name, value="—", inline=True)
    embed.add_field(name=team_b_name, value="—", inline=True)
    embed.add_field(name="Prize", value=prize, inline=False)
    embed.add_field(name="Status", value="🟢 OPEN", inline=False)

    view = WagerView(
        interaction.user.id,
        team_size,
        team_a_name,
        team_b_name,
        start_time
    )

    await interaction.response.send_message(
        embed=embed,
        view=view
    )

bot.run(TOKEN)
