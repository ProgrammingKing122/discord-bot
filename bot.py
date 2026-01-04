import os
import re
import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = 1443765937793667194
MIDDLEMAN_ROLE_ID = 1457241934832861255
LOG_CHANNEL_ID = 1457242121009631312

ERR = '❌ **Error has happened — please contact "Levi" for fixes.**'

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
    except Exception:
        pass


def _id_from_mention(s: str):
    m = re.search(r"\d{15,21}", s or "")
    return int(m.group(0)) if m else None


def kd(k, d):
    return round(k / d, 2) if d else float(k)


def dot(k, d):
    return "🟢" if k > d else "🟡" if k == d else "🔴"


# ───────────────────────── BEGIN VIEW ─────────────────────────

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


# ───────────────────────── STATS MODAL ─────────────────────────

class StatsModal(discord.ui.Modal, title="Enter Player Stats"):
    kills = discord.ui.TextInput(label="Kills", required=True)
    deaths = discord.ui.TextInput(label="Deaths", required=True)

    def __init__(self, view, target_uid):
        super().__init__()
        self.view = view
        self.target_uid = target_uid

    async def on_submit(self, interaction):
        if interaction.user.id not in self.view.controllers():
            return await fail(interaction)

        try:
            k = int(self.kills.value)
            d = int(self.deaths.value)
            if k < 0 or d < 0:
                raise ValueError
        except Exception:
            return await fail(interaction)

        self.view.stats[self.target_uid] = (k, d)
        await interaction.response.edit_message(
            embed=self.view.results_embed(),
            view=self.view
        )


# ───────────────────────── NOTES MODAL ─────────────────────────

class NotesModal(discord.ui.Modal, title="Add Notes"):
    notes = discord.ui.TextInput(
        label="Notes",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1200
    )

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction):
        if interaction.user.id not in self.view.controllers():
            return await fail(interaction)

        self.view.notes = self.notes.value.strip()
        await interaction.response.edit_message(
            embed=self.view.results_embed(),
            view=self.view
        )


# ───────────────────────── PLAYER PICK ─────────────────────────

class PlayerPick(discord.ui.UserSelect):
    def __init__(self, view):
        super().__init__(min_values=1, max_values=1, placeholder="Select player")
        self.view = view

    async def callback(self, interaction):
        if interaction.user.id not in self.view.controllers():
            return await fail(interaction)

        target = self.values[0]
        await interaction.response.send_modal(
            StatsModal(self.view, target.id)
        )


# ───────────────────────── RESULTS VIEW ─────────────────────────

class ResultsView(discord.ui.View):
    def __init__(self, wager, guild):
        super().__init__(timeout=None)
        self.wager = wager
        self.guild = guild
        self.stats: dict[int, tuple[int, int]] = {}
        self.notes = None

    def controllers(self):
        s = {self.wager.host_id}
        if self.wager.middleman_id:
            s.add(self.wager.middleman_id)
        return s

    def _name(self, uid):
        m = self.guild.get_member(uid)
        return m.display_name if m else f"User{uid}"

    def table(self, team_ids):
        rows = []
        for uid in team_ids:
            k, d = self.stats.get(uid, (0, 0))
            rows.append(
                f"{self._name(uid):<16} {k:>5} {d:>6} {kd(k,d):>7} {dot(k,d)}"
            )
        header = f"{'PLAYER':<16} {'K':>5} {'D':>6} {'KD':>7}"
        return f"```{header}\n" + "\n".join(rows) + "```"

    def results_embed(self):
        ta = self.wager.team_a_ids()
        tb = self.wager.team_b_ids()

        suma = sum(self.stats.get(i, (0, 0))[0] for i in ta)
        sumb = sum(self.stats.get(i, (0, 0))[0] for i in tb)

        if suma > sumb:
            win = f"🏆 **Winner: {self.wager.a}**"
        elif sumb > suma:
            win = f"🏆 **Winner: {self.wager.b}**"
        else:
            win = "🤝 **Draw**"

        e = discord.Embed(title="🏁 MATCH RESULTS", description=win)
        e.add_field(name=self.wager.a, value=self.table(ta), inline=False)
        e.add_field(name=self.wager.b, value=self.table(tb), inline=False)

        if self.notes:
            e.add_field(name="Notes", value=self.notes, inline=False)

        return e

    @discord.ui.button(label="Enter Stats", style=discord.ButtonStyle.primary)
    async def enter(self, interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)

        v = discord.ui.View(timeout=30)
        v.add_item(PlayerPick(self))
        await interaction.response.send_message(
            "Select player:",
            view=v,
            ephemeral=True
        )

    @discord.ui.button(label="Add Notes", style=discord.ButtonStyle.secondary)
    async def add_notes(self, interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)

        await interaction.response.send_modal(NotesModal(self))

    @discord.ui.button(label="Finalize", style=discord.ButtonStyle.success)
    async def finalize(self, interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)

        log = bot.get_channel(LOG_CHANNEL_ID)
        if log:
            await log.send(embed=self.results_embed())

        await interaction.response.edit_message(
            content="✅ **Results logged.**",
            view=None
        )


# ───────────────────────── WAGER VIEW ─────────────────────────

class WagerView(discord.ui.View):
    def __init__(self, host_id, size, a, b, prize, time, rules, guild):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.middleman_id = None
        self.no_middleman = False
        self.size = max(1, min(int(size), 8))
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
        e = discord.Embed(
            title="💎 WAGER",
            description=f"{self.size}v{self.size} • {self.time}\nPrize: {self.prize}"
        )
        e.add_field(name=self.a, value="\n".join(self.team_a) or "—")
        e.add_field(name=self.b, value="\n".join(self.team_b) or "—")
        e.add_field(name="Rules", value=self.rules, inline=False)
        e.add_field(name="Status", value=self.status, inline=False)
        return e

    async def try_start(self, channel):
        if self.begin_sent:
            return
        if len(self.team_a) == self.size and len(self.team_b) == self.size:
            self.begin_sent = True
            users = set(self.team_a_ids() + self.team_b_ids())
            await channel.send(
                "⚔️ Teams full — react to begin",
                view=BeginView(self, users)
            )

    @discord.ui.button(label="Join Team A")
    async def join_a(self, interaction, _):
        m = interaction.user.mention
        if m in self.team_b:
            self.team_b.remove(m)
        if m not in self.team_a and len(self.team_a) < self.size:
            self.team_a.append(m)
        await interaction.response.edit_message(embed=self.embed(), view=self)
        await self.try_start(interaction.channel)

    @discord.ui.button(label="Join Team B")
    async def join_b(self, interaction, _):
        m = interaction.user.mention
        if m in self.team_a:
            self.team_a.remove(m)
        if m not in self.team_b and len(self.team_b) < self.size:
            self.team_b.append(m)
        await interaction.response.edit_message(embed=self.embed(), view=self)
        await self.try_start(interaction.channel)

    @discord.ui.button(label="End", style=discord.ButtonStyle.danger)
    async def end(self, interaction, _):
        if interaction.user.id not in {self.host_id, self.middleman_id}:
            return await fail(interaction)

        rv = ResultsView(self, interaction.guild)
        await interaction.response.edit_message(
            embed=rv.results_embed(),
            view=rv
        )


# ───────────────────────── COMMAND ─────────────────────────

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
        rules,
        interaction.guild
    )

    await interaction.response.send_message(
        embed=view.embed(),
        view=view
    )

    msg = await interaction.original_response()
    view.msg_id = msg.id


bot.run(TOKEN)
