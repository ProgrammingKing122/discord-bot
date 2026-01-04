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

class StatsModal(discord.ui.Modal, title="Enter Player Stats"):
    kills = discord.ui.TextInput(label="Kills", required=True)
    deaths = discord.ui.TextInput(label="Deaths", required=True)

    def __init__(self, rv, uid):
        super().__init__()
        self.rv = rv
        self.uid = uid

    async def on_submit(self, interaction):
        self.rv.stats[self.uid] = (int(self.kills.value), int(self.deaths.value))
        await interaction.response.edit_message(embed=self.rv.results_embed(), view=self.rv)

class PlayerSelect(discord.ui.Select):
    def __init__(self, rv):
        self.rv = rv

        ids = list(dict.fromkeys(
            rv.wager.team_a_ids() + rv.wager.team_b_ids()
        ))

        options = []
        for uid in ids:
            m = rv.guild.get_member(uid)
            name = m.display_name if m else f"Player {uid}"
            options.append(
                discord.SelectOption(
                    label=name,
                    value=str(uid)
                )
            )

        super().__init__(
            placeholder="Select player",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction):
        uid = int(self.values[0])
        await interaction.response.send_modal(StatsModal(self.rv, uid))

class PlayerSelectView(discord.ui.View):
    def __init__(self, rv):
        super().__init__(timeout=60)
        self.add_item(PlayerSelect(rv))

class ResultsView(discord.ui.View):
    def __init__(self, wager, guild):
        super().__init__(timeout=None)
        self.wager = wager
        self.guild = guild
        self.stats = {}

    def controllers(self):
        s = {self.wager.host_id}
        if self.wager.middleman_id:
            s.add(self.wager.middleman_id)
        return s

    def player_row(self, uid):
        m = self.guild.get_member(uid)
        name = m.display_name if m else f"<@{uid}>"
        avatar = m.display_avatar.url if m else None
        k, d = self.stats.get(uid, (0, 0))

        value = (
            f"💥 **Kills:** {k}\n"
            f"☠️ **Deaths:** {d}\n"
            f"📊 **KD:** {kd(k,d)}"
        )

        return name, value, avatar

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

        e.add_field(
            name=f"🔥 {self.wager.a} — {sa} Kills",
            value="\u200b",
            inline=False
        )

        for uid in ta:
            name, value, avatar = self.player_row(uid)
            e.add_field(name=name, value=value, inline=True)
            if avatar:
                e.set_thumbnail(url=avatar)

        e.add_field(
            name=f"🔥 {self.wager.b} — {sb} Kills",
            value="\u200b",
            inline=False
        )

        for uid in tb:
            name, value, avatar = self.player_row(uid)
            e.add_field(name=name, value=value, inline=True)
            if avatar:
                e.set_thumbnail(url=avatar)

        return e

    @discord.ui.button(label="Enter Stats", style=discord.ButtonStyle.primary)
    async def enter_stats(self, interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)
        await interaction.response.send_message(
            view=PlayerSelectView(self),
            ephemeral=True
        )

    @discord.ui.button(label="Finalize", style=discord.ButtonStyle.success)
    async def finalize(self, interaction, _):
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

    async def callback(self, interaction):
        if interaction.user.id != self.wager.host_id:
            return await fail(interaction)
        member = interaction.guild.get_member(self.values[0].id)
        if not member or not any(r.id == MIDDLEMAN_ROLE_ID for r in member.roles):
            return await interaction.response.send_message("User lacks Middleman role.", ephemeral=True)
        self.wager.middleman_id = member.id
        await interaction.response.edit_message(embed=self.wager.embed(), view=self.wager)

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
        self.guild = guild
        self.msg_id = None

    def team_a_ids(self):
        return [uid_from_mention(m) for m in self.team_a if uid_from_mention(m)]

    def team_b_ids(self):
        return [uid_from_mention(m) for m in self.team_b if uid_from_mention(m)]

    def team_block(self, team):
        out = []
        for m in team:
            uid = uid_from_mention(m)
            member = self.guild.get_member(uid)
            name = member.display_name if member else m
            out.append(name)
        return "\n".join(out) or "—"

    def embed(self):
        e = discord.Embed(
            title="💎 WAGER",
            description=f"**{self.size}v{self.size}** • {self.time}\n**Prize:** {self.prize}",
            color=discord.Color.blurple()
        )
        e.add_field(name="Host", value=f"<@{self.host_id}>", inline=True)
        e.add_field(
            name="Middleman",
            value=f"<@{self.middleman_id}>" if self.middleman_id else "None",
            inline=True
        )
        e.add_field(name=self.a, value=self.team_block(self.team_a), inline=True)
        e.add_field(name=self.b, value=self.team_block(self.team_b), inline=True)
        e.add_field(name="Rules", value=self.rules, inline=False)
        return e

    @discord.ui.button(label="Join Team A", style=discord.ButtonStyle.primary)
    async def join_a(self, interaction, _):
        m = interaction.user.mention
        if m in self.team_b:
            self.team_b.remove(m)
        if m not in self.team_a:
            self.team_a.append(m)
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Join Team B", style=discord.ButtonStyle.primary)
    async def join_b(self, interaction, _):
        m = interaction.user.mention
        if m in self.team_a:
            self.team_a.remove(m)
        if m not in self.team_b:
            self.team_b.append(m)
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Middleman", style=discord.ButtonStyle.secondary)
    async def mm(self, interaction, _):
        if interaction.user.id != self.host_id:
            return await fail(interaction)
        await interaction.response.send_message(
            view=MiddlemanView(self),
            ephemeral=True
        )

    @discord.ui.button(label="End Match", style=discord.ButtonStyle.danger)
    async def end(self, interaction, _):
        rv = ResultsView(self, interaction.guild)
        await interaction.response.edit_message(embed=rv.results_embed(), view=rv)

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
