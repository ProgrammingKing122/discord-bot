import os
import re
import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1443765937793667194
MIDDLEMAN_ROLE_ID = 1457241934832861255
LOG_CHANNEL_ID = 1457242121009631312
ERR = '❌ **Error has happened — please contact Levi.**'

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

class BeginView(discord.ui.View):
    def __init__(self, wager, users):
        super().__init__(timeout=None)
        self.wager = wager
        self.users = set(users)
        self.ready = set()

    @discord.ui.button(label="Begin", style=discord.ButtonStyle.success, emoji="⚔️")
    async def begin(self, interaction, _):
        if interaction.user.id not in self.users:
            return await fail(interaction)
        self.ready.add(interaction.user.id)
        if self.ready == self.users:
            self.wager.status = "⚔️ IN PROGRESS"
            msg = await interaction.channel.fetch_message(self.wager.msg_id)
            await msg.edit(embed=self.wager.embed(), view=self.wager)
            await interaction.message.edit(content="⚔️ **Match started**", view=None)
        else:
            await interaction.response.send_message("Ready", ephemeral=True)

class StatsModal(discord.ui.Modal, title="Enter Stats"):
    kills = discord.ui.TextInput(label="Kills")
    deaths = discord.ui.TextInput(label="Deaths")

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
            if k < 0 or d < 0:
                raise ValueError
        except:
            return await fail(interaction)
        self.rv.stats[self.uid] = (k, d)
        await interaction.response.edit_message(embed=self.rv.results_embed(), view=self.rv)

class NotesModal(discord.ui.Modal, title="Player Notes"):
    notes = discord.ui.TextInput(style=discord.TextStyle.paragraph, max_length=800)

    def __init__(self, rv, uid):
        super().__init__()
        self.rv = rv
        self.uid = uid

    async def on_submit(self, interaction):
        if interaction.user.id not in self.rv.controllers():
            return await fail(interaction)
        self.rv.notes[self.uid] = self.notes.value.strip()
        await interaction.response.edit_message(embed=self.rv.results_embed(), view=self.rv)

class PlayerSelect(discord.ui.Select):
    def __init__(self, rv, mode):
        self.rv = rv
        self.mode = mode
        ids = list(dict.fromkeys(rv.wager.team_a_ids() + rv.wager.team_b_ids()))
        opts = []
        for uid in ids:
            name = rv.display_name(uid)
            opts.append(discord.SelectOption(label=name[:100], value=str(uid)))
        super().__init__(placeholder="Select player", options=opts)

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

    def display_name(self, uid):
        m = self.guild.get_member(uid)
        return m.display_name if m else f"<@{uid}>"

    def lines(self, ids):
        out = []
        for uid in ids:
            k, d = self.stats.get(uid, (0, 0))
            note = self.notes.get(uid)
            line = f"<@{uid}> — **K:** {k} **D:** {d} **KD:** {kd(k,d)} {dot(k,d)}"
            if note:
                line += f"\n↳ _{note}_"
            out.append(line)
        return "\n".join(out) if out else "—"

    def results_embed(self):
        ta = self.wager.team_a_ids()
        tb = self.wager.team_b_ids()
        suma = sum(self.stats.get(i, (0, 0))[0] for i in ta)
        sumb = sum(self.stats.get(i, (0, 0))[0] for i in tb)
        if suma > sumb:
            desc = f"🏆 **{self.wager.a} wins**"
            color = discord.Color.green()
        elif sumb > suma:
            desc = f"🏆 **{self.wager.b} wins**"
            color = discord.Color.green()
        else:
            desc = "🤝 **Draw**"
            color = discord.Color.gold()
        e = discord.Embed(title="MATCH RESULTS", description=desc, color=color)
        e.add_field(name=self.wager.a, value=self.lines(ta), inline=False)
        e.add_field(name=self.wager.b, value=self.lines(tb), inline=False)
        return e

    @discord.ui.button(label="Enter Stats", style=discord.ButtonStyle.primary)
    async def enter_stats(self, interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)
        await interaction.response.send_message(view=PlayerSelectView(self, "stats"), ephemeral=True)

    @discord.ui.button(label="Add Notes", style=discord.ButtonStyle.secondary)
    async def add_notes(self, interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)
        await interaction.response.send_message(view=PlayerSelectView(self, "notes"), ephemeral=True)

    @discord.ui.button(label="Finalize", style=discord.ButtonStyle.success)
    async def finalize(self, interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)
        log = bot.get_channel(LOG_CHANNEL_ID)
        if log:
            await log.send(embed=self.results_embed())
        await interaction.response.edit_message(content="✅ Logged", view=None)

class MiddlemanAcceptView(discord.ui.View):
    def __init__(self, wager, uid):
        super().__init__(timeout=120)
        self.wager = wager
        self.uid = uid

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction, _):
        if interaction.user.id != self.uid:
            return await fail(interaction)
        self.wager.middleman_id = self.uid
        await self.wager.try_start(interaction.channel)
        try:
            await interaction.message.delete()
        except:
            pass

class MiddlemanPick(discord.ui.UserSelect):
    def __init__(self, wager):
        super().__init__(min_values=1, max_values=1)
        self.wager = wager

    async def callback(self, interaction):
        if interaction.user.id != self.wager.host_id:
            return await fail(interaction)
        m = interaction.guild.get_member(self.values[0].id)
        if not m or not any(r.id == MIDDLEMAN_ROLE_ID for r in m.roles):
            return await interaction.response.send_message("Invalid middleman", ephemeral=True)
        await interaction.response.send_message(f"<@{m.id}> selected", view=MiddlemanAcceptView(self.wager, m.id))

class MiddlemanView(discord.ui.View):
    def __init__(self, wager):
        super().__init__(timeout=60)
        self.add_item(MiddlemanPick(wager))

class WagerView(discord.ui.View):
    def __init__(self, host_id, size, a, b, prize, time, rules, guild):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.middleman_id = None
        self.no_middleman = False
        self.size = size
        self.a = a
        self.b = b
        self.prize = prize
        self.time = time
        self.rules = rules
        self.team_a = []
        self.team_b = []
        self.status = "🟢 OPEN"
        self.msg_id = None
        self.begin_sent = False
        self.guild = guild

    def team_a_ids(self):
        return [_id_from_mention(m) for m in self.team_a if _id_from_mention(m)]

    def team_b_ids(self):
        return [_id_from_mention(m) for m in self.team_b if _id_from_mention(m)]

    def embed(self):
        e = discord.Embed(title="WAGER", color=discord.Color.blurple())
        e.add_field(name="Host", value=f"<@{self.host_id}>")
        e.add_field(name="Middleman", value=f"<@{self.middleman_id}>" if self.middleman_id else "—")
        e.add_field(name=self.a, value="\n".join(self.team_a) or "—")
        e.add_field(name=self.b, value="\n".join(self.team_b) or "—")
        e.add_field(name="Prize", value=self.prize, inline=False)
        e.add_field(name="Rules", value=self.rules, inline=False)
        e.add_field(name="Status", value=self.status, inline=False)
        return e

    async def try_start(self, channel):
        if self.begin_sent:
            return
        if len(self.team_a) == self.size and len(self.team_b) == self.size:
            if self.middleman_id or self.no_middleman:
                self.begin_sent = True
                users = set(self.team_a_ids() + self.team_b_ids())
                await channel.send("Teams ready", view=BeginView(self, users))

    @discord.ui.button(label="Join A")
    async def join_a(self, interaction, _):
        m = interaction.user.mention
        if m in self.team_b:
            self.team_b.remove(m)
        if m not in self.team_a and len(self.team_a) < self.size:
            self.team_a.append(m)
        await interaction.response.edit_message(embed=self.embed(), view=self)
        await self.try_start(interaction.channel)

    @discord.ui.button(label="Join B")
    async def join_b(self, interaction, _):
        m = interaction.user.mention
        if m in self.team_a:
            self.team_a.remove(m)
        if m not in self.team_b and len(self.team_b) < self.size:
            self.team_b.append(m)
        await interaction.response.edit_message(embed=self.embed(), view=self)
        await self.try_start(interaction.channel)

    @discord.ui.button(label="Middleman")
    async def mm(self, interaction, _):
        if interaction.user.id != self.host_id:
            return await fail(interaction)
        await interaction.response.send_message(view=MiddlemanView(self), ephemeral=True)

    @discord.ui.button(label="End", style=discord.ButtonStyle.danger)
    async def end(self, interaction, _):
        if interaction.user.id not in {self.host_id, self.middleman_id}:
            return await fail(interaction)
        await interaction.response.edit_message(embed=ResultsView(self, interaction.guild).results_embed(), view=ResultsView(self, interaction.guild))

@bot.tree.command(name="wager", guild=discord.Object(id=GUILD_ID))
async def wager(interaction, team_size: int, team_a_name: str, team_b_name: str, prize: str, start_time: str, rules: str):
    v = WagerView(interaction.user.id, team_size, team_a_name, team_b_name, prize, start_time, rules, interaction.guild)
    await interaction.response.send_message(embed=v.embed(), view=v)
    msg = await interaction.original_response()
    v.msg_id = msg.id

bot.run(TOKEN)
