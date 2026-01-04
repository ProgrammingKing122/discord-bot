import os
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1443765937793667194

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

def dot(k, d):
    if k > d:
        return "🟢"
    if k == d:
        return "🟡"
    return "🔴"

def kd(k, d):
    return f"{(k / d) if d else float(k):.2f}"

@bot.event
async def setup_hook():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

@bot.event
async def on_ready():
    print(f"ONLINE as {bot.user}")

class StatsModal(discord.ui.Modal, title="Enter Player Stats"):
    kills = discord.ui.TextInput(label="Kills", required=True)
    deaths = discord.ui.TextInput(label="Deaths", required=True)

    def __init__(self, view, user_id):
        super().__init__()
        self.view = view
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id not in self.view.controllers:
            return await interaction.response.send_message('❌ **Error has happened — please contact "Levi" for fixes.**', ephemeral=True)
        k = int(self.kills.value)
        d = int(self.deaths.value)
        self.view.stats[self.user_id] = (k, d)
        await interaction.response.edit_message(embed=self.view.build_results(), view=self.view)

class MiddlemanSelect(discord.ui.UserSelect):
    def __init__(self, view):
        super().__init__(placeholder="Select middleman", min_values=1, max_values=1)
        self.view = view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.host_id:
            return await interaction.response.send_message('❌ **Error has happened — please contact "Levi" for fixes.**', ephemeral=True)
        self.view.middleman = self.values[0].id
        self.view.controllers.add(self.view.middleman)
        await interaction.response.edit_message(embed=self.view.build_results(), view=self.view)

class ResultsView(discord.ui.View):
    def __init__(self, host_id, team_a, team_b, a_name, b_name):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.middleman = None
        self.controllers = {host_id}
        self.team_a = team_a
        self.team_b = team_b
        self.a_name = a_name
        self.b_name = b_name
        self.stats = {}

        self.add_item(MiddlemanSelect(self))

    def column(self, team):
        out = []
        for uid in team:
            k, d = self.stats.get(uid, (0, 0))
            out.append(
                f"<@{uid}>\n"
                f"**K:** {k}  **D:** {d}\n"
                f"**K/D:** {kd(k,d)} {dot(k,d)}"
            )
        return "\n\n".join(out) if out else "—"

    def build_results(self):
        embed = discord.Embed(
            title="🏁 MATCH RESULTS",
            color=discord.Color.green()
        )
        embed.add_field(name=self.a_name, value=self.column(self.team_a), inline=True)
        embed.add_field(name=self.b_name, value=self.column(self.team_b), inline=True)
        embed.add_field(
            name="Controllers",
            value=" ".join(f"<@{u}>" for u in self.controllers),
            inline=False
        )
        return embed

    @discord.ui.button(label="Enter Stats", style=discord.ButtonStyle.primary)
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.controllers:
            return await interaction.response.send_message('❌ **Error has happened — please contact "Levi" for fixes.**', ephemeral=True)
        await interaction.response.send_modal(StatsModal(self, interaction.user.id))

class EndModal(discord.ui.Modal, title="End Wager"):
    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.host_id:
            return await interaction.response.send_message('❌ **Error has happened — please contact "Levi" for fixes.**', ephemeral=True)
        rv = ResultsView(
            self.view.host_id,
            [int(u.strip("<@>")) for u in self.view.team_a],
            [int(u.strip("<@>")) for u in self.view.team_b],
            self.view.a_name,
            self.view.b_name
        )
        await interaction.response.edit_message(embed=rv.build_results(), view=rv)

class WagerView(discord.ui.View):
    def __init__(self, host_id, team_size, a_name, b_name):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.team_size = team_size
        self.a_name = a_name
        self.b_name = b_name
        self.team_a = []
        self.team_b = []

    def build(self):
        embed = discord.Embed(
            title="💎 WAGER",
            color=discord.Color.blurple()
        )
        embed.add_field(name=self.a_name, value="\n".join(self.team_a) or "—", inline=True)
        embed.add_field(name=self.b_name, value="\n".join(self.team_b) or "—", inline=True)
        embed.add_field(name="Status", value="🟢 OPEN", inline=False)
        return embed

    async def refresh(self, interaction):
        await interaction.response.edit_message(embed=self.build(), view=self)

    @discord.ui.button(label="Join Team A", style=discord.ButtonStyle.primary)
    async def a(self, interaction: discord.Interaction, button: discord.ui.Button):
        u = interaction.user.mention
        if u in self.team_b:
            self.team_b.remove(u)
        if u not in self.team_a and len(self.team_a) < self.team_size:
            self.team_a.append(u)
        await self.refresh(interaction)

    @discord.ui.button(label="Join Team B", style=discord.ButtonStyle.primary)
    async def b(self, interaction: discord.Interaction, button: discord.ui.Button):
        u = interaction.user.mention
        if u in self.team_a:
            self.team_a.remove(u)
        if u not in self.team_b and len(self.team_b) < self.team_size:
            self.team_b.append(u)
        await self.refresh(interaction)

    @discord.ui.button(label="End", style=discord.ButtonStyle.danger)
    async def end(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            return await interaction.response.send_message('❌ **Error has happened — please contact "Levi" for fixes.**', ephemeral=True)
        await interaction.response.send_modal(EndModal(self))

@bot.tree.command(name="wager", guild=discord.Object(id=GUILD_ID))
async def wager(interaction: discord.Interaction, team_size: int, team_a_name: str, team_b_name: str):
    view = WagerView(interaction.user.id, team_size, team_a_name, team_b_name)
    await interaction.response.send_message(embed=view.build(), view=view)

bot.run(TOKEN)
