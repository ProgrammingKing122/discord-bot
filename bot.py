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

def uid_from_mention(s: str):
    m = re.search(r"\d{15,21}", s or "")
    return int(m.group(0)) if m else None

def kd(k: int, d: int):
    return round(k / d, 2) if d else k

async def fail(i: discord.Interaction):
    if not i.response.is_done():
        await i.response.send_message("❌ Error", ephemeral=True)

class StatsModal(discord.ui.Modal, title="Enter Player Stats"):
    kills = discord.ui.TextInput(label="Kills", required=True)
    deaths = discord.ui.TextInput(label="Deaths", required=True)

    def __init__(self, rv, uid: int):
        super().__init__()
        self.rv = rv
        self.uid = uid

    async def on_submit(self, interaction: discord.Interaction):
        try:
            k = int(self.kills.value)
            d = int(self.deaths.value)
            if k < 0 or d < 0:
                return await fail(interaction)
        except:
            return await fail(interaction)

        self.rv.stats[self.uid] = (k, d)
        await interaction.response.edit_message(embed=self.rv.results_embed(), view=self.rv)

class PlayerSelect(discord.ui.Select):
    def __init__(self, rv):
        self.rv = rv
        ids = list(dict.fromkeys(rv.wager.team_a_ids() + rv.wager.team_b_ids()))
        opts = []
        for uid in ids:
            m = rv.guild.get_member(uid) if rv.guild else None
            label = (m.display_name if m else f"Player {uid}")[:100]
            opts.append(discord.SelectOption(label=label, value=str(uid)))
        super().__init__(placeholder="Select player", min_values=1, max_values=1, options=opts)

    async def callback(self, interaction: discord.Interaction):
        uid = int(self.values[0])
        await interaction.response.send_modal(StatsModal(self.rv, uid))

class PlayerSelectView(discord.ui.View):
    def __init__(self, rv):
        super().__init__(timeout=60)
        self.add_item(PlayerSelect(rv))

class ResultsView(discord.ui.View):
    def __init__(self, wager, guild: discord.Guild):
        super().__init__(timeout=None)
        self.wager = wager
        self.guild = guild
        self.stats = {}

    def controllers(self):
        s = {self.wager.host_id}
        if self.wager.middleman_id:
            s.add(self.wager.middleman_id)
        return s

    def player_block(self, uid: int):
        k, d = self.stats.get(uid, (0, 0))
        return (
            f"👤 <@{uid}>\n"
            f"💥 Kills: **{k}**\n"
            f"☠️ Deaths: **{d}**\n"
            f"📊 KD: **{kd(k,d)}**"
        )

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

        e = discord.Embed(title=title, color=color)
        e.add_field(name=f"{self.wager.a} — {sa} Kills", value="\n\n".join(self.player_block(u) for u in ta) or "—", inline=False)
        e.add_field(name=f"{self.wager.b} — {sb} Kills", value="\n\n".join(self.player_block(u) for u in tb) or "—", inline=False)
        return e

    @discord.ui.button(label="Enter Stats", style=discord.ButtonStyle.primary)
    async def enter_stats(self, interaction: discord.Interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)
        await interaction.response.send_message(view=PlayerSelectView(self), ephemeral=True)

    @discord.ui.button(label="Finalize", style=discord.ButtonStyle.success)
    async def finalize(self, interaction: discord.Interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)
        log = bot.get_channel(LOG_CHANNEL_ID)
        if log:
            await log.send(embed=self.results_embed())
        await interaction.response.edit_message(embed=self.results_embed(), view=None)

class MiddlemanPick(discord.ui.UserSelect):
    def __init__(self, wager):
        super().__init__(min_values=1, max_values=1)
        self.wager = wager

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.wager.host_id:
            return await fail(interaction)
        member = interaction.guild.get_member(self.values[0].id)
        if not member or not any(r.id == MIDDLEMAN_ROLE_ID for r in member.roles):
            return await interaction.response.send_message("❌ User lacks Middleman role.", ephemeral=True)
        self.wager.middleman_id = member.id
        self.wager.no_middleman = False
        await interaction.response.edit_message(embed=self.wager.embed(), view=self.wager)

class MiddlemanView(discord.ui.View):
    def __init__(self, wager):
        super().__init__(timeout=60)
        self.add_item(MiddlemanPick(wager))

class JoinButton(discord.ui.Button):
    def __init__(self, label: str, which: str):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.which = which

    async def callback(self, interaction: discord.Interaction):
        view: "WagerView" = self.view
        u = interaction.user.mention

        if self.which == "A":
            if u in view.team_b:
                view.team_b.remove(u)
            if u not in view.team_a and len(view.team_a) < view.size:
                view.team_a.append(u)
        else:
            if u in view.team_a:
                view.team_a.remove(u)
            if u not in view.team_b and len(view.team_b) < view.size:
                view.team_b.append(u)

        await interaction.response.edit_message(embed=view.embed(), view=view)
        await view.try_start(interaction.channel)

class MiddlemanButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Pick Middleman", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: "WagerView" = self.view
        if interaction.user.id != view.host_id:
            return await fail(interaction)
        await interaction.response.send_message("Select middleman:", view=MiddlemanView(view), ephemeral=True)

class NoMiddlemanButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="No Middleman", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: "WagerView" = self.view
        if interaction.user.id != view.host_id:
            return await fail(interaction)
        view.no_middleman = True
        view.middleman_id = None
        await interaction.response.edit_message(embed=view.embed(), view=view)
        await view.try_start(interaction.channel)

class EndMatchButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="End Match", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        view: "WagerView" = self.view
        if interaction.user.id not in {view.host_id, view.middleman_id}:
            return await fail(interaction)
        rv = ResultsView(view, interaction.guild)
        await interaction.response.edit_message(embed=rv.results_embed(), view=rv)

class BeginView(discord.ui.View):
    def __init__(self, wager, users):
        super().__init__(timeout=None)
        self.wager = wager
        self.users = set(users)
        self.ready = set()

    @discord.ui.button(label="Begin", style=discord.ButtonStyle.success, emoji="⚔️")
    async def begin(self, interaction: discord.Interaction, _):
        if interaction.user.id not in self.users:
            return await fail(interaction)
        self.ready.add(interaction.user.id)
        if self.ready == self.users:
            self.wager.status = "⚔️ IN PROGRESS"
            msg = await interaction.channel.fetch_message(self.wager.msg_id)
            await msg.edit(embed=self.wager.embed(), view=self.wager)
            await interaction.response.send_message("⚔️ Match started", ephemeral=True)
        else:
            await interaction.response.send_message("Ready", ephemeral=True)

class WagerView(discord.ui.View):
    def __init__(self, host_id, size, a, b, prize, time, rules, guild):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.size = max(1, min(int(size), 8))
        self.a = str(a)[:40]
        self.b = str(b)[:40]
        self.prize = str(prize)[:1800]
        self.time = str(time)[:80]
        self.rules = str(rules)[:1200]
        self.guild = guild

        self.middleman_id = None
        self.no_middleman = False
        self.team_a = []
        self.team_b = []
        self.status = "🟢 OPEN"
        self.msg_id = None
        self.begin_sent = False

        self.add_item(JoinButton(f"Join {self.a}", "A"))
        self.add_item(JoinButton(f"Join {self.b}", "B"))
        self.add_item(MiddlemanButton())
        self.add_item(NoMiddlemanButton())
        self.add_item(EndMatchButton())

    def team_a_ids(self):
        return [uid_from_mention(m) for m in self.team_a if uid_from_mention(m)]

    def team_b_ids(self):
        return [uid_from_mention(m) for m in self.team_b if uid_from_mention(m)]

    def team_list(self, team):
        if not team:
            return "—"
        lines = []
        for m in team:
            uid = uid_from_mention(m)
            if uid:
                lines.append(f"• <@{uid}>")
        return "\n".join(lines) or "—"

    def embed(self):
        e = discord.Embed(
            title="💎 WAGER",
            description=f"**Match:** {self.size}v{self.size} • **Start:** {self.time}\n**Prize:** {self.prize}",
            color=discord.Color.blurple()
        )

        e.add_field(name="Host", value=f"<@{self.host_id}>", inline=True)
        mm = "🚫 None" if self.no_middleman else (f"<@{self.middleman_id}>" if self.middleman_id else "—")
        e.add_field(name="Middleman", value=mm, inline=True)
        e.add_field(name="Status", value=self.status, inline=True)

        e.add_field(name=self.a, value=self.team_list(self.team_a), inline=True)
        e.add_field(name=self.b, value=self.team_list(self.team_b), inline=True)
        e.add_field(name="\u200b", value="\u200b", inline=True)

        e.add_field(name="Rules", value=self.rules or "—", inline=False)
        return e

    async def try_start(self, channel: discord.abc.Messageable):
        if self.begin_sent:
            return
        if len(self.team_a) == self.size and len(self.team_b) == self.size:
            if self.middleman_id or self.no_middleman:
                self.begin_sent = True
                users = set(self.team_a_ids() + self.team_b_ids())
                mentions = " ".join([f"<@{u}>" for u in users])
                await channel.send(f"{mentions}\n⚔️ Teams full. Click Begin.", view=BeginView(self, users))

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
    await interaction.response.send_message(embed=view.embed(), view=view)
    msg = await interaction.original_response()
    view.msg_id = msg.id

bot.run(TOKEN)
