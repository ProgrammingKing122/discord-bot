import os
import re
import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = 1443765937793667194
MIDDLEMAN_ROLE_ID = 1457241934832861255
LOG_CHANNEL_ID = 1457242121009631312

ERR = "❌ Error occurred. Contact Levi."

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def setup_hook():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

@bot.event
async def on_ready():
    print(f"ONLINE as {bot.user}")

@bot.tree.error
async def on_app_command_error(interaction, error):
    if isinstance(error, app_commands.CommandNotFound):
        return
    raise error

async def fail(i):
    try:
        if i.response.is_done():
            await i.followup.send(ERR, ephemeral=True)
        else:
            await i.response.send_message(ERR, ephemeral=True)
    except:
        pass

def _id_from_mention(s):
    m = re.search(r"\d{15,21}", s or "")
    return int(m.group(0)) if m else None

def kd(k, d):
    return round(k / d, 2) if d else float(k)

def dot(k, d):
    return "🟢" if k > d else "🟡" if k == d else "🔴"

class StatsModal(discord.ui.Modal, title="Enter Stats"):
    kills = discord.ui.TextInput(label="Kills", required=True)
    deaths = discord.ui.TextInput(label="Deaths", required=True)

    def __init__(self, rv, uid):
        super().__init__()
        self.rv = rv
        self.uid = uid

    async def on_submit(self, interaction):
        if interaction.user.id not in self.rv.controllers():
            return await fail(interaction)
        try:
            k = int(self.kills.value)
            d = int(self.deaths.value)
        except:
            return await fail(interaction)
        self.rv.stats[self.uid] = (k, d)
        await interaction.response.edit_message(embed=self.rv.results_embed(), view=self.rv)

class NotesModal(discord.ui.Modal, title="Player Notes"):
    notes = discord.ui.TextInput(
        label="Notes",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=800
    )

    def __init__(self, rv, uid):
        super().__init__()
        self.rv = rv
        self.uid = uid

    async def on_submit(self, interaction):
        if interaction.user.id not in self.rv.controllers():
            return await fail(interaction)
        self.rv.notes[self.uid] = self.notes.value
        await interaction.response.edit_message(embed=self.rv.results_embed(), view=self.rv)

class PlayerSelect(discord.ui.Select):
    def __init__(self, rv, mode):
        self.rv = rv
        self.mode = mode

        ids = list(dict.fromkeys(rv.wager.team_a_ids() + rv.wager.team_b_ids()))
        options = []

        for uid in ids:
            member = rv.guild.get_member(uid)
            name = member.display_name if member else "Player"
            options.append(discord.SelectOption(label=name, value=str(uid)))

        super().__init__(
            placeholder="Select player",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction):
        if interaction.user.id not in self.rv.controllers():
            return await fail(interaction)
        uid = int(self.values[0])
        if self.mode == "stats":
            await interaction.response.send_modal(StatsModal(self.rv, uid))
        else:
            await interaction.response.send_modal(NotesModal(self.rv, uid))

class PlayerSelectView(discord.ui.View):
    def __init__(self, rv, mode):
        super().__init__(timeout=60)
        self.add_item(PlayerSelect(rv, mode))

class ResultsView(discord.ui.View):
    def __init__(self, wager, guild):
        super().__init__(timeout=None)
        self.wager = wager
        self.guild = guild
        self.stats = {}
        self.notes = {}

    def controllers(self):
        s = {self.wager.host_id}
        if self.wager.middleman_id:
            s.add(self.wager.middleman_id)
        return s

    def lines(self, ids):
        out = []
        for uid in ids:
            k, d = self.stats.get(uid, (0, 0))
            note = self.notes.get(uid)
            line = f"<@{uid}> — K:{k} D:{d} KD:{kd(k,d)} {dot(k,d)}"
            if note:
                line += f"\n_{note}_"
            out.append(line)
        return "\n".join(out) if out else "—"

    def results_embed(self):
        ta = self.wager.team_a_ids()
        tb = self.wager.team_b_ids()
        suma = sum(self.stats.get(i, (0, 0))[0] for i in ta)
        sumb = sum(self.stats.get(i, (0, 0))[0] for i in tb)

        e = discord.Embed(
            title="MATCH RESULTS",
            color=discord.Color.green() if suma != sumb else discord.Color.gold()
        )

        e.add_field(name=self.wager.a, value=self.lines(ta), inline=False)
        e.add_field(name=self.wager.b, value=self.lines(tb), inline=False)
        return e

    @discord.ui.button(label="Enter Stats", style=discord.ButtonStyle.primary)
    async def enter_stats(self, interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)
        await interaction.response.send_message(
            view=PlayerSelectView(self, "stats"),
            ephemeral=True
        )

    @discord.ui.button(label="Add Notes", style=discord.ButtonStyle.secondary)
    async def add_notes(self, interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)
        await interaction.response.send_message(
            view=PlayerSelectView(self, "notes"),
            ephemeral=True
        )

    @discord.ui.button(label="Finalize", style=discord.ButtonStyle.success)
    async def finalize(self, interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)
        log = bot.get_channel(LOG_CHANNEL_ID)
        if log:
            await log.send(embed=self.results_embed())
        await interaction.response.edit_message(content="Logged", view=None)
