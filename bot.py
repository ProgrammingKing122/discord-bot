import os, re, discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1443765937793667194
LOG_CHANNEL_ID = 1457242121009631312

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def setup_hook():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

def _id(m):
    x = re.search(r"\d{15,21}", m or "")
    return int(x.group()) if x else None

def kd(k, d):
    return round(k / d, 2) if d else k

class StatsModal(discord.ui.Modal, title="ENTER PLAYER STATS"):
    kills = discord.ui.TextInput(label="KILLS", required=True)
    deaths = discord.ui.TextInput(label="DEATHS", required=True)

    def __init__(self, rv, uid):
        super().__init__()
        self.rv = rv
        self.uid = uid

    async def on_submit(self, interaction):
        self.rv.stats[self.uid] = (int(self.kills.value), int(self.deaths.value))
        await interaction.response.edit_message(embed=self.rv.embed(), view=self.rv)

class NotesModal(discord.ui.Modal, title="PLAYER NOTES"):
    notes = discord.ui.TextInput(label="NOTES", style=discord.TextStyle.paragraph)

    def __init__(self, rv, uid):
        super().__init__()
        self.rv = rv
        self.uid = uid

    async def on_submit(self, interaction):
        self.rv.notes[self.uid] = self.notes.value
        await interaction.response.edit_message(embed=self.rv.embed(), view=self.rv)

class PlayerPick(discord.ui.Select):
    def __init__(self, rv, mode):
        self.rv = rv
        self.mode = mode
        ids = list(dict.fromkeys(rv.wager.a_ids + rv.wager.b_ids))
        opts = [
            discord.SelectOption(
                label=f"PLAYER {i+1}",
                description=f"<@{uid}>",
                value=str(uid)
            ) for i, uid in enumerate(ids)
        ]
        super().__init__(placeholder="SELECT PLAYER", options=opts)

    async def callback(self, interaction):
        uid = int(self.values[0])
        if self.mode == "stats":
            await interaction.response.send_modal(StatsModal(self.rv, uid))
        else:
            await interaction.response.send_modal(NotesModal(self.rv, uid))

class PickView(discord.ui.View):
    def __init__(self, rv, mode):
        super().__init__(timeout=60)
        self.add_item(PlayerPick(rv, mode))

class ResultsView(discord.ui.View):
    def __init__(self, wager):
        super().__init__(timeout=None)
        self.wager = wager
        self.stats = {}
        self.notes = {}

    def block(self, uid):
        k, d = self.stats.get(uid, (0, 0))
        note = self.notes.get(uid)
        s = (
            f"👤 **<@{uid}>**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💥 **KILLS:** `{k}`\n"
            f"☠️ **DEATHS:** `{d}`\n"
            f"📊 **K/D:** `{kd(k,d)}`"
        )
        if note:
            s += f"\n📝 _{note}_"
        return s

    def embed(self):
        ta = self.wager.a_ids
        tb = self.wager.b_ids
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
            description="━━━━━━━━━━━━━━━━━━━",
            color=color
        )

        e.add_field(
            name=f"🔥 {self.wager.a} — {sa} KILLS",
            value="\n\n".join(self.block(u) for u in ta) or "—",
            inline=False
        )
        e.add_field(
            name=f"🔥 {self.wager.b} — {sb} KILLS",
            value="\n\n".join(self.block(u) for u in tb) or "—",
            inline=False
        )
        return e

    @discord.ui.button(label="ENTER STATS", style=discord.ButtonStyle.primary)
    async def stats(self, interaction, _):
        await interaction.response.send_message(view=PickView(self, "stats"), ephemeral=True)

    @discord.ui.button(label="ADD NOTES", style=discord.ButtonStyle.secondary)
    async def notes_btn(self, interaction, _):
        await interaction.response.send_message(view=PickView(self, "notes"), ephemeral=True)

    @discord.ui.button(label="FINALIZE", style=discord.ButtonStyle.success)
    async def finalize(self, interaction, _):
        ch = bot.get_channel(LOG_CHANNEL_ID)
        if ch:
            await ch.send(embed=self.embed())
        await interaction.response.edit_message(content="✅ RESULT LOGGED", view=None)

class WagerView(discord.ui.View):
    def __init__(self, a, b):
        super().__init__(timeout=None)
        self.a = a
        self.b = b
        self.a_ids = []
        self.b_ids = []

    @discord.ui.button(label="END MATCH", style=discord.ButtonStyle.danger)
    async def end(self, interaction, _):
        rv = ResultsView(self)
        await interaction.response.edit_message(embed=rv.embed(), view=rv)

@bot.tree.command(name="wager", guild=discord.Object(id=GUILD_ID))
async def wager(interaction, team_a: str, team_b: str):
    v = WagerView(team_a, team_b)
    await interaction.response.send_message("MATCH STARTED", view=v)

bot.run(TOKEN)
