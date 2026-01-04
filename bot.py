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

class RulesModal(discord.ui.Modal, title="Edit Wager Rules"):
    rules = discord.ui.TextInput(label="Rules", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.host_id:
            await interaction.response.send_message("Only the host can edit rules.", ephemeral=True)
            return
        self.view.rules = self.rules.value
        embed = interaction.message.embeds[0]
        embed.set_field_at(
            self.view.rules_index,
            name="Rules",
            value=self.view.rules,
            inline=False
        )
        await interaction.response.edit_message(embed=embed, view=self.view)

class WagerView(discord.ui.View):
    def __init__(self, host_id, rules):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.team_a = []
        self.team_b = []
        self.rules = rules
        self.rules_index = 4

    def teams(self):
        return (
            "\n".join(self.team_a) if self.team_a else "—",
            "\n".join(self.team_b) if self.team_b else "—"
        )

    async def refresh(self, interaction):
        embed = interaction.message.embeds[0]
        a, b = self.teams()
        embed.set_field_at(2, name="Team A", value=a, inline=True)
        embed.set_field_at(3, name="Team B", value=b, inline=True)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Join Team A", style=discord.ButtonStyle.primary)
    async def join_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user.mention
        if user in self.team_b:
            self.team_b.remove(user)
        if user not in self.team_a:
            self.team_a.append(user)
        await self.refresh(interaction)

    @discord.ui.button(label="Join Team B", style=discord.ButtonStyle.primary)
    async def join_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user.mention
        if user in self.team_a:
            self.team_a.remove(user)
        if user not in self.team_b:
            self.team_b.append(user)
        await self.refresh(interaction)

    @discord.ui.button(label="Rules", style=discord.ButtonStyle.secondary, emoji="📜")
    async def rules_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RulesModal(self))

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
    match_size="e.g. 3v3",
    prize="What is being wagered",
    rules="Wager rules"
)
async def wager(
    interaction: discord.Interaction,
    match_size: str,
    prize: str,
    rules: str
):
    embed = discord.Embed(
        title="💎 Wager",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Host", value=interaction.user.mention, inline=False)
    embed.add_field(name="Match", value=match_size, inline=True)
    embed.add_field(name="Team A", value="—", inline=True)
    embed.add_field(name="Team B", value="—", inline=True)
    embed.add_field(name="Rules", value=rules, inline=False)
    embed.add_field(name="Prize", value=prize, inline=False)
    embed.add_field(name="Status", value="🟢 OPEN", inline=False)

    view = WagerView(interaction.user.id, rules)

    await interaction.response.send_message(
        embed=embed,
        view=view
    )

bot.run(TOKEN)
