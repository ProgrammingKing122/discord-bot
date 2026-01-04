import os
import discord
from discord.ext import commands

TOKEN = os.getenv("MTQ1NzI0NDcwNjA0NzEzMTc2MQ.GZ5SPa.CFrMQnPxrexrE7HhGUHIYo2r6ZykFXtYltWhDw")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Online as {bot.user}")

@bot.tree.command(name="ping", description="Ping test")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("All set up!")

@bot.event
async def setup_hook():
    await bot.tree.sync()

bot.run(TOKEN)
