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

class WagerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"✅ **{interaction.user.mention} accepted the wager!**",
            ephemeral=True
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.set_field_at(
            index=len(embed.fields) - 1,
            name="Status",
            value="❌ CANCELLED",
            inline=False
        )
        await interaction.message.edit(embed=embed, view=None)

    @discord.ui.button(label="Skin List", style=discord.ButtonStyle.secondary, emoji="🎒")
    async def skins(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "**Skins**\n• Firework Bag (575)\n• Skull Bag (1,400)",
            ephemeral=True
        )

@bot.tree.command(
    name="wager",
    description="Create a wager",
    guild=discord.Object(id=GUILD_ID)
)
async def wager(interaction: discord.Interaction):
    embed = discord.Embed(
        title="💎 Wager #08",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Clan", value="Salvo", inline=True)
    embed.add_field(name="Match", value="2v2", inline=True)
    embed.add_field(name="Host", value=f"{interaction.user.mention}", inline=False)
    embed.add_field(
        name="Items",
        value="Firework Bag — **575**\nSkull Bag — **1,400**",
        inline=False
    )
    embed.add_field(name="Total Value", value="**1,975**", inline=True)
    embed.add_field(name="Status", value="🟢 OPEN", inline=False)
    embed.set_footer(text="Click a button to proceed")

    await interaction.response.send_message(
        embed=embed,
        view=WagerView()
    )

bot.run(TOKEN)
