import os
import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1443765937793667194
MIDDLEMAN_ROLE_ID = 1457241934832861255
ERR = '❌ **Error has happened — please contact "Levi" for fixes.**'

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def setup_hook():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

@bot.event
async def on_ready():
    print(f"ONLINE as {bot.user}")

async def fail(i):
    if i.response.is_done():
        await i.followup.send(ERR, ephemeral=True)
    else:
        await i.response.send_message(ERR, ephemeral=True)

class BeginView(discord.ui.View):
    def __init__(self, wager, users):
        super().__init__(timeout=None)
        self.wager = wager
        self.users = set(users)
        self.ready = set()

    @discord.ui.button(label="React to Begin", style=discord.ButtonStyle.success, emoji="⚔️")
    async def begin(self, interaction, _):
        if interaction.user.id not in self.users:
            return await fail(interaction)
        self.ready.add(interaction.user.id)
        if self.ready == self.users:
            self.wager.status = "⚔️ IN PROGRESS"
            msg = await interaction.channel.fetch_message(self.wager.msg_id)
            await msg.edit(embed=self.wager.embed(), view=self.wager)
            await interaction.message.edit(content="⚔️ **Wager started!**", view=None)
        else:
            await interaction.response.send_message("Ready ✔", ephemeral=True)

class EndModal(discord.ui.Modal, title="End Wager"):
    winner = discord.ui.TextInput(label="Winner (Team A / Team B)", required=True)
    score = discord.ui.TextInput(label="Score", required=True)
    notes = discord.ui.TextInput(label="Notes", required=False, style=discord.TextStyle.paragraph)

    def __init__(self, wager):
        super().__init__()
        self.wager = wager

    async def on_submit(self, interaction):
        if interaction.user.id not in self.wager.controllers():
            return await fail(interaction)
        self.wager.status = "🏁 FINISHED"
        self.wager.result = f"**Winner:** {self.winner.value}\n**Score:** {self.score.value}\n{self.notes.value}"
        await interaction.response.edit_message(embed=self.wager.embed(), view=None)

class MiddlemanAcceptView(discord.ui.View):
    def __init__(self, wager, user_id):
        super().__init__(timeout=120)
        self.wager = wager
        self.user_id = user_id

    @discord.ui.button(label="Accept Middleman", style=discord.ButtonStyle.success)
    async def accept(self, interaction, _):
        if interaction.user.id != self.user_id:
            return await fail(interaction)
        self.wager.middleman_id = self.user_id
        await interaction.message.delete()
        await self.wager.try_start(interaction.channel)

class MiddlemanPick(discord.ui.UserSelect):
    def __init__(self, wager):
        super().__init__(min_values=1, max_values=1)
        self.wager = wager

    async def callback(self, interaction):
        if interaction.user.id != self.wager.host_id:
            return await fail(interaction)

        member = interaction.guild.get_member(self.values[0].id)
        if not member or not any(r.id == MIDDLEMAN_ROLE_ID for r in member.roles):
            return await interaction.response.send_message(
                "❌ That user does not have the Middleman role.",
                ephemeral=True
            )

        await interaction.response.send_message(
            f"<@{member.id}> you were selected as **Middleman**.",
            view=MiddlemanAcceptView(self.wager, member.id)
        )

class MiddlemanView(discord.ui.View):
    def __init__(self, wager):
        super().__init__(timeout=60)
        self.add_item(MiddlemanPick(wager))

class WagerView(discord.ui.View):
    def __init__(self, host_id, size, a, b, prize, time, rules):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.middleman_id = None
        self.size = size
        self.a = a
        self.b = b
        self.prize = prize
        self.time = time
        self.rules = rules
        self.team_a = []
        self.team_b = []
        self.status = "🟢 OPEN"
        self.result = None
        self.msg_id = None
        self.begin_sent = False

    def controllers(self):
        s = {self.host_id}
        if self.middleman_id:
            s.add(self.middleman_id)
        return s

    def embed(self):
        e = discord.Embed(
            title="💎 WAGER",
            description=f"**Match:** {self.size}v{self.size} • **Start:** {self.time}\n**Prize:** {self.prize}",
            color=discord.Color.blurple()
        )
        e.add_field(name="Host", value=f"<@{self.host_id}>", inline=True)
        e.add_field(name="Middleman", value=f"<@{self.middleman_id}>" if self.middleman_id else "—", inline=True)
        e.add_field(name="\u200b", value="\u200b", inline=True)
        e.add_field(name=self.a, value="\n".join(self.team_a) or "—", inline=True)
        e.add_field(name=self.b, value="\n".join(self.team_b) or "—", inline=True)
        e.add_field(name="\u200b", value="\u200b", inline=True)
        e.add_field(name="Rules", value=self.rules, inline=False)
        if self.result:
            e.add_field(name="Result", value=self.result, inline=False)
        e.add_field(name="Status", value=self.status, inline=False)
        return e

    async def redraw(self, interaction):
        if interaction.response.is_done():
            await interaction.message.edit(embed=self.embed(), view=self)
        else:
            await interaction.response.edit_message(embed=self.embed(), view=self)

    async def try_start(self, channel):
        if self.begin_sent:
            return
        if len(self.team_a) == self.size and len(self.team_b) == self.size:
            self.begin_sent = True
            users = {int(m[2:-1]) for m in self.team_a + self.team_b}
            mentions = " ".join(self.team_a + self.team_b)
            msg = await channel.fetch_message(self.msg_id)
            await msg.edit(embed=self.embed(), view=self)
            await channel.send(
                f"{mentions}\n⚔️ **Teams are full. React to begin.**",
                view=BeginView(self, users)
            )

    @discord.ui.button(label="Join Team A", style=discord.ButtonStyle.primary)
    async def join_a(self, interaction, _):
        u = interaction.user.mention
        if u in self.team_b:
            self.team_b.remove(u)
        if u not in self.team_a and len(self.team_a) < self.size:
            self.team_a.append(u)
        await self.redraw(interaction)
        if not self.middleman_id:
            await self.try_start(interaction.channel)

    @discord.ui.button(label="Join Team B", style=discord.ButtonStyle.primary)
    async def join_b(self, interaction, _):
        u = interaction.user.mention
        if u in self.team_a:
            self.team_a.remove(u)
        if u not in self.team_b and len(self.team_b) < self.size:
            self.team_b.append(u)
        await self.redraw(interaction)
        if not self.middleman_id:
            await self.try_start(interaction.channel)

    @discord.ui.button(label="Middleman", style=discord.ButtonStyle.secondary, emoji="🧑‍⚖️")
    async def mm(self, interaction, _):
        if interaction.user.id != self.host_id:
            return await fail(interaction)
        await interaction.response.send_message("Select middleman:", view=MiddlemanView(self), ephemeral=True)

    @discord.ui.button(label="End", style=discord.ButtonStyle.danger)
    async def end(self, interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)
        await interaction.response.send_modal(EndModal(self))

@bot.tree.command(name="wager", guild=discord.Object(id=GUILD_ID))
async def wager(
    interaction: discord.Interaction,
    team_size: int,
    team_a_name: str,
    team_b_name: str,
    prize: str,
    start_time: str,
    rules: str
):
    view = WagerView(
        interaction.user.id,
        team_size,
        team_a_name,
        team_b_name,
        prize,
        start_time,
        rules
    )
    await interaction.response.send_message(embed=view.embed(), view=view)
    msg = await interaction.original_response()
    view.msg_id = msg.id

bot.run(TOKEN)
