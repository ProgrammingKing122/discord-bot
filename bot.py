import os
import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1443765937793667194

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def setup_hook():
    guild = discord.Object(id=GUILD_ID)
    bot.tree.clear_commands(guild=guild)
    await bot.tree.sync(guild=guild)
    print("SLASH COMMANDS FORCE-SYNCED")

@bot.event
async def on_ready():
    print(f"ONLINE as {bot.user}")

@bot.tree.command(name="ping", description="Ping test", guild=discord.Object(id=GUILD_ID))
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong! All set up.")

@bot.tree.command(name="developerpanel", description="Developer debug panel", guild=discord.Object(id=GUILD_ID))
async def developerpanel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Developer Panel",
        color=discord.Color.orange()
    )
    embed.add_field(
        name="Latency",
        value=f"{round(bot.latency * 1000)} ms",
        inline=False
    )
    embed.add_field(
        name="Guild ID",
        value=str(interaction.guild_id),
        inline=False
    )
    embed.add_field(
        name="Commands Loaded",
        value=", ".join(c.name for c in bot.tree.get_commands()),
        inline=False
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="wager", description="Create a wager", guild=discord.Object(id=GUILD_ID))
async def wager(
    interaction: discord.Interaction,
    size: int,
    team_a: str,
    team_b: str,
    prize: str,
    start_time: str,
    rules: str
):
    embed = discord.Embed(
        title="💎 WAGER CREATED",
        description=f"**{size}v{size}**\n🕒 {start_time}\n🎁 {prize}",
        color=discord.Color.blurple()
    )
    embed.add_field(name="🅰️ Team A", value=team_a, inline=True)
    embed.add_field(name="🅱️ Team B", value=team_b, inline=True)
    embed.add_field(name="📜 Rules", value=rules, inline=False)
    embed.add_field(name="👑 Host", value=interaction.user.mention, inline=False)
    embed.set_footer(text="System online • UI modules loading")

    await interaction.response.send_message(embed=embed)

bot.run(TOKEN)
