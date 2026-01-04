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
        return interaction.followup.send(
            '❌ **Error has happened — please contact "Levi" for fixes.**',
            ephemeral=True
        )
    return interaction.response.send_message(
        '❌ **Error has happened — please contact "Levi" for fixes.**',
        ephemeral=True
    )

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
        if interaction.user.id != self.view.host_id:
            return await fail(interaction)
        try:
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.set_field_at(self.view.status_i, name="Status", value="🏁 FINISHED", inline=False)
            embed.add_field(name="Result", value=self.result.value, inline=False)
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
            uid = interaction.user.id
            if uid not in self.parent.ids:
                return await fail(interaction)
            self.ready.add(uid)
            if len(self.ready) == self.parent.team_size * 2:
                embed = interaction.message.embeds[0]
                embed.set_field_at(self.parent.status_i, name="Status", value="⚔️ IN PROGRESS", inline=False)
                await interaction.message.edit(embed=embed, view=None)
            else:
                await interaction.response.send_message("Ready ✔", ephemeral=True)
        except Exception:
            await fail(interaction)

class WagerView(discord.ui.View):
    def __init__(self, host_id, team_size, a_name, b_name, field_map):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.team_size = team_size
        self.a_name = a_name
        self.b_name = b_name
        self.team_a = []
        self.team_b = []
        self.field_map = field_map
        self.status_i = field_map["status"]
        self.ids = set()
        self.locked = False

    def render(self):
        return (
            "\n".join(self.team_a) if self.team_a else "—",
            "\n".join(self.team_b) if self.team_b else "—"
        )

    async def refresh(self, interaction):
        try:
            embed = interaction.message.embeds[0]
            a, b = self.render()
            embed.set_field_at(self.field_map["a"], name=self.a_name, value=a, inline=True)
            embed.set_field_at(self.field_map["b"], name=self.b_name, value=b, inline=True)
            await interaction.response.edit_message(embed=embed, view=self)
            await self.check_full(interaction)
        except Exception:
            await fail(interaction)

    async def check_full(self, interaction):
        if self.locked:
            return
        if len(self.team_a) == self.team_size and len(self.team_b) == self.team_size:
            self.locked = True
            self.ids = {
                int(u.strip("<@>")) for u in self.team_a + self.team_b
            }
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
    embed.set_footer(text="Join teams • React to begin • Host ends the wager")

    field_map = {
        "a": 1,
        "b": 2,
        "status": 3
    }

    view = WagerView(
        interaction.user.id,
        team_size,
        team_a_name,
        team_b_name,
        field_map
    )

    await interaction.response.send_message(embed=embed, view=view)

bot.run(TOKEN)
