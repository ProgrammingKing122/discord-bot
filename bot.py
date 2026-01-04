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

class RulesModal(discord.ui.Modal, title="Wager Rules"):
    rules = discord.ui.TextInput(label="Rules", style=discord.TextStyle.paragraph, required=False)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("📜 Rules saved.", ephemeral=True)

class WagerView(discord.ui.View):
    def __init__(self, team_a, team_b):
        super().__init__(timeout=None)
        self.team_a = team_a
        self.team_b = team_b

    def render(self):
        a = "\n".join(self.team_a) if self.team_a else "—"
        b = "\n".join(self.team_b) if self.team_b else "—"
        return a, b

    @discord.ui.button(label="Join Team A", style=discord.ButtonStyle.primary)
    async def join_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        name = interaction.user.mention
        if name in self.team_b:
            self.team_b.remove(name)
        if name not in self.team_a:
            self.team_a.append(name)
        await self.update(interaction)

    @discord.ui.button(label="Join Team B", style=discord.ButtonStyle.primary)
    async def join_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        name = interaction.user.mention
        if name in self.team_a:
            self.team_a.remove(name)
        if name not in self.team_b:
            self.team_b.append(name)
        await self.update(interaction)

    @discord.ui.button(label="Rules", style=discord.ButtonStyle.secondary, emoji="📜")
    async def rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RulesModal())

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.set_field_at(len(embed.fields) - 1, name="Status", value="❌ CANCELLED", inline=False)
        await interaction.message.edit(embed=embed, view=None)

    async def update(self, interaction):
        embed = interaction.message.embeds[0]
        a, b = self.render()
        embed.set_field_at(2, name="Team A", value=a, inline=True)
        embed.set_field_at(3, name="Team B", value=b, inline=True)
        await interaction.response.edit_message(embed=embed, view=self)

@bot.tree.command(
    name="wager",
    description="Create a custom wager",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(
    match_size="e.g. 2v2, 3v3",
    items="What is on the table",
    total_value="Total wager value"
)
async def wager(
    interaction: discord.Interaction,
    match_size: str,
    items: str,
    total_value: int
):
    embed = discord.Embed(
        title="💎 Wager",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Host", value=interaction.user.mention, inline=False)
    embed.add_field(name="Match", value=match_size, inline=True)
    embed.add_field(name="Team A", value="—", inline=True)
    embed.add_field(name="Team B", value="—", inline=True)
    embed.add_field(name="Items", value=items, inline=False)
    embed.add_field(name="Total Value", value=f"**{total_value:,}**", inline=True)
    embed.add_field(name="Status", value="🟢 OPEN", inline=False)

    view = WagerView([], [])

    await interaction.response.send_message(
        embed=embed,
        view=view
    )

bot.run(TOKEN)
