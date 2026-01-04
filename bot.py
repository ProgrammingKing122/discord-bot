import os
import re
import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = 1443765937793667194
MIDDLEMAN_ROLE_ID = 1457241934832861255
LOG_CHANNEL_ID = 1457242121009631312

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def setup_hook():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

@bot.event
async def on_ready():
    print(f"ONLINE as {bot.user}")

def uid_from_mention(s):
    m = re.search(r"\d{15,21}", s or "")
    return int(m.group(0)) if m else None

def kd(k, d):
    return round(k / d, 2) if d else k

async def fail(i):
    if not i.response.is_done():
        await i.response.send_message("❌ Error", ephemeral=True)

class StatsModal(discord.ui.Modal, title="ENTER STATS"):
    kills = discord.ui.TextInput(label="Kills", required=True)
    deaths = discord.ui.TextInput(label="Deaths", required=True)

    def __init__(self, rv, uid):
        super().__init__()
        self.rv = rv
        self.uid = uid

    async def on_submit(self, interaction):
        self.rv.stats[self.uid] = (int(self.kills.value), int(self.deaths.value))
        await interaction.response.edit_message(
            embed=self.rv.results_embed(),
            view=self.rv
        )

class NotesModal(discord.ui.Modal, title="PLAYER NOTES"):
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
        self.rv.notes[self.uid] = self.notes.value
        await interaction.response.edit_message(
            embed=self.rv.results_embed(),
            view=self.rv
        )

class PlayerSelect(discord.ui.Select):
    def __init__(self, rv, mode):
        self.rv = rv
        self.mode = mode

        ids = list(dict.fromkeys(
            rv.wager.team_a_ids() + rv.wager.team_b_ids()
        ))

        options = [
            discord.SelectOption(
                label=f"{i+1}.",
                description=f"<@{uid}>",
                value=str(uid)
            )
            for i, uid in enumerate(ids)
        ]

        super().__init__(
            placeholder="SELECT PLAYER",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction):
        uid = int(self.values[0])
        if self.mode == "stats":
            await interaction.response.send_modal(
                StatsModal(self.rv, uid)
            )
        else:
            await interaction.response.send_modal(
                NotesModal(self.rv, uid)
            )

class PlayerSelectView(discord.ui.View):
    def __init__(self, rv, mode):
        super().__init__(timeout=60)
        self.add_item(PlayerSelect(rv, mode))

class ResultsView(discord.ui.View):
    def __init__(self, wager):
        super().__init__(timeout=None)
        self.wager = wager
        self.stats = {}
        self.notes = {}

    def controllers(self):
        s = {self.wager.host_id}
        if self.wager.middleman_id:
            s.add(self.wager.middleman_id)
        return s

    def player_block(self, uid):
        k, d = self.stats.get(uid, (0, 0))
        note = self.notes.get(uid)
        text = (
            f"👤 **<@{uid}>**\n"
            f"━━━━━━━━━━━━━━\n"
            f"💥 **Kills:** {k}\n"
            f"☠️ **Deaths:** {d}\n"
            f"📊 **KD:** {kd(k,d)}"
        )
        if note:
            text += f"\n📝 _{note}_"
        return text

    def results_embed(self):
        ta = self.wager.team_a_ids()
        tb = self.wager.team_b_ids()

        sa = sum(self.stats.get(i,(0,0))[0] for i in ta)
        sb = sum(self.stats.get(i,(0,0))[0] for i in tb)

        if sa > sb:
            title = f"🏆 {self.wager.a} WINS"
            color = discord.Color.green()
        elif sb > sa:
            title = f"🏆 {self.wager.b} WINS"
            color = discord.Color.green()
        else:
            title = "🤝 DRAW"
            color = discord.Color.gold()

        e = discord.Embed(
            title=title,
            description="━━━━━━━━━━━━━━━━━━",
            color=color
        )

        e.add_field(
            name=f"🔥 {self.wager.a} — {sa} Kills",
            value="\n\n".join(self.player_block(u) for u in ta) or "—",
            inline=False
        )

        e.add_field(
            name=f"🔥 {self.wager.b} — {sb} Kills",
            value="\n\n".join(self.player_block(u) for u in tb) or "—",
            inline=False
        )

        return e

    @discord.ui.button(label="ENTER STATS", style=discord.ButtonStyle.primary)
    async def enter_stats(self, interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)
        await interaction.response.send_message(
            view=PlayerSelectView(self, "stats"),
            ephemeral=True
        )

    @discord.ui.button(label="ADD NOTES", style=discord.ButtonStyle.secondary)
    async def add_notes(self, interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)
        await interaction.response.send_message(
            view=PlayerSelectView(self, "notes"),
            ephemeral=True
        )

    @discord.ui.button(label="FINALIZE", style=discord.ButtonStyle.success)
    async def finalize(self, interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)

        log = bot.get_channel(LOG_CHANNEL_ID)
        if log:
            await log.send(embed=self.results_embed())

        await interaction.response.edit_message(
            embed=self.results_embed(),
            view=None
        )

class BeginView(discord.ui.View):
    def __init__(self, wager, users):
        super().__init__(timeout=None)
        self.wager = wager
        self.users = set(users)
        self.ready = set()

    @discord.ui.button(label="BEGIN", style=discord.ButtonStyle.success)
    async def begin(self, interaction, _):
        if interaction.user.id not in self.users:
            return await fail(interaction)

        self.ready.add(interaction.user.id)

        if self.ready == self.users:
            self.wager.status = "⚔️ IN PROGRESS"
            msg = await interaction.channel.fetch_message(self.wager.msg_id)
            await msg.edit(
                embed=self.wager.embed(),
                view=self.wager
            )
            await interaction.response.send_message("⚔️ Match started", ephemeral=True)
        else:
            await interaction.response.send_message("Ready", ephemeral=True)

class WagerView(discord.ui.View):
    def __init__(self, host_id, size, a, b, prize, time, rules):
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

    def team_a_ids(self):
        return [uid_from_mention(m) for m in self.team_a if uid_from_mention(m)]

    def team_b_ids(self):
        return [uid_from_mention(m) for m in self.team_b if uid_from_mention(m)]

    def embed(self):
        e = discord.Embed(
            title="💎 WAGER",
            description=f"**{self.size}v{self.size}** • {self.time}\n**Prize:** {self.prize}",
            color=discord.Color.blurple()
        )
        e.add_field(name="Host", value=f"<@{self.host_id}>", inline=True)
        e.add_field(
            name="Middleman",
            value="🚫 None" if self.no_middleman else (f"<@{self.middleman_id}>" if self.middleman_id else "—"),
            inline=True
        )
        e.add_field(name=self.a, value="\n".join(self.team_a) or "—", inline=True)
        e.add_field(name=self.b, value="\n".join(self.team_b) or "—", inline=True)
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
                mentions = " ".join(self.team_a + self.team_b)
                await channel.send(
                    f"{mentions}\n⚔️ Teams full. Click begin.",
                    view=BeginView(self, users)
                )

    @discord.ui.button(label="Join Team A", style=discord.ButtonStyle.primary)
    async def join_a(self, interaction, _):
        u = interaction.user.mention
        if u in self.team_b:
            self.team_b.remove(u)
        if u not in self.team_a and len(self.team_a) < self.size:
            self.team_a.append(u)
        await interaction.response.edit_message(
            embed=self.embed(),
            view=self
        )
        await self.try_start(interaction.channel)

    @discord.ui.button(label="Join Team B", style=discord.ButtonStyle.primary)
    async def join_b(self, interaction, _):
        u = interaction.user.mention
        if u in self.team_a:
            self.team_a.remove(u)
        if u not in self.team_b and len(self.team_b) < self.size:
            self.team_b.append(u)
        await interaction.response.edit_message(
            embed=self.embed(),
            view=self
        )
        await self.try_start(interaction.channel)

    @discord.ui.button(label="No Middleman", style=discord.ButtonStyle.secondary)
    async def no_mm(self, interaction, _):
        if interaction.user.id != self.host_id:
            return await fail(interaction)
        self.no_middleman = True
        await interaction.response.edit_message(
            embed=self.embed(),
            view=self
        )
        await self.try_start(interaction.channel)

    @discord.ui.button(label="End Match", style=discord.ButtonStyle.danger)
    async def end(self, interaction, _):
        if interaction.user.id not in {self.host_id, self.middleman_id}:
            return await fail(interaction)

        rv = ResultsView(self)
        await interaction.response.edit_message(
            embed=rv.results_embed(),
            view=rv
        )

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
    await interaction.response.send_message(
        embed=view.embed(),
        view=view
    )
    msg = await interaction.original_response()
    view.msg_id = msg.id

bot.run(TOKEN)
