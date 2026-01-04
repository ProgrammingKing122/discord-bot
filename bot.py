import os
import re
import math
import discord
from discord.ext import commands
from discord import app_commands
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

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

async def fail(i):
    try:
        if i.response.is_done():
            await i.followup.send(ERR, ephemeral=True)
        else:
            await i.response.send_message(ERR, ephemeral=True)
    except Exception:
        pass

def kd(k, d):
    if d <= 0:
        return float(k)
    return round(k / d, 2)

def dot(k, d):
    return "🟢" if k > d else "🟡" if k == d else "🔴"

def clamp(n, a, b):
    return a if n < a else b if n > b else n

def safe_int(s, lo=0, hi=999):
    try:
        v = int(str(s).strip())
    except Exception:
        return None
    if v < lo or v > hi:
        return None
    return v

def try_font(size):
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()

def shorten(s, n):
    s = str(s)
    return s if len(s) <= n else s[: max(0, n - 1)] + "…"

def scoreboard_image(guild, title, team_a_name, team_b_name, team_a_ids, team_b_ids, stats, notes, winner_text):
    W = 1100
    pad = 36
    header_h = 130
    card_w = (W - pad * 2 - 26) // 2
    row_h = 54
    max_rows = max(len(team_a_ids), len(team_b_ids), 1)
    body_h = 170 + max_rows * row_h + 120
    H = header_h + body_h

    img = Image.new("RGB", (W, H), (18, 18, 22))
    d = ImageDraw.Draw(img)

    f_title = try_font(46)
    f_sub = try_font(24)
    f_hdr = try_font(26)
    f_row = try_font(22)
    f_small = try_font(18)

    d.rounded_rectangle([pad, 22, W - pad, header_h - 18], radius=22, fill=(28, 28, 36))
    d.text((pad + 26, 34), shorten(title, 40), font=f_title, fill=(240, 240, 255))
    d.text((pad + 28, 92), winner_text, font=f_sub, fill=(190, 220, 255))

    y0 = header_h + 10
    xA = pad
    xB = pad + card_w + 26

    def team_card(x, y, name, ids, accent):
        d.rounded_rectangle([x, y, x + card_w, y + 110 + max_rows * row_h], radius=22, fill=(26, 26, 32))
        d.rounded_rectangle([x, y, x + card_w, y + 10], radius=22, fill=accent)
        d.text((x + 22, y + 20), shorten(name, 26), font=f_hdr, fill=(240, 240, 255))

        hdr_y = y + 62
        d.text((x + 22, hdr_y), "Player", font=f_small, fill=(160, 170, 190))
        d.text((x + card_w - 260, hdr_y), "K", font=f_small, fill=(160, 170, 190))
        d.text((x + card_w - 200, hdr_y), "D", font=f_small, fill=(160, 170, 190))
        d.text((x + card_w - 140, hdr_y), "KD", font=f_small, fill=(160, 170, 190))
        d.text((x + card_w - 64, hdr_y), "", font=f_small, fill=(160, 170, 190))

        total_k = 0
        for i, uid in enumerate(ids):
            ry = y + 96 + i * row_h
            bg = (30, 30, 38) if i % 2 == 0 else (28, 28, 36)
            d.rounded_rectangle([x + 14, ry, x + card_w - 14, ry + row_h - 8], radius=16, fill=bg)

            mem = guild.get_member(uid) if guild else None
            nm = mem.display_name if mem else None
            if not nm:
                u = bot.get_user(uid)
                nm = u.name if u else f"User{uid}"
            nm = shorten(nm, 16)

            k, de = stats.get(uid, (0, 0))
            total_k += k
            ratio = kd(k, de)
            status = dot(k, de)

            d.text((x + 26, ry + 12), nm, font=f_row, fill=(235, 235, 255))
            d.text((x + card_w - 270, ry + 12), str(k), font=f_row, fill=(235, 235, 255))
            d.text((x + card_w - 210, ry + 12), str(de), font=f_row, fill=(235, 235, 255))
            d.text((x + card_w - 155, ry + 12), str(ratio), font=f_row, fill=(235, 235, 255))
            d.text((x + card_w - 70, ry + 10), status, font=try_font(26), fill=(235, 235, 255))

        d.text((x + 22, y + 110 + max_rows * row_h + 18), f"Total Kills: {total_k}", font=f_sub, fill=(190, 220, 255))
        return total_k

    kills_a = team_card(xA, y0, team_a_name, team_a_ids, (90, 110, 255))
    kills_b = team_card(xB, y0, team_b_name, team_b_ids, (130, 90, 255))

    ny = y0 + 130 + max_rows * row_h + 36
    d.rounded_rectangle([pad, ny, W - pad, ny + 88], radius=20, fill=(28, 28, 36))
    d.text((pad + 22, ny + 16), "Notes", font=f_hdr, fill=(240, 240, 255))
    d.text((pad + 22, ny + 52), shorten(notes or "—", 120), font=f_small, fill=(190, 200, 220))

    out = BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out

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

class NotesModal(discord.ui.Modal, title="Add Notes"):
    notes = discord.ui.TextInput(label="Notes", style=discord.TextStyle.paragraph, required=True, max_length=1200)

    def __init__(self, results_view):
        super().__init__()
        self.rv = results_view

    async def on_submit(self, interaction):
        if interaction.user.id not in self.rv.controllers():
            return await fail(interaction)
        self.rv.notes = str(self.notes.value).strip()
        await interaction.response.edit_message(embed=self.rv.results_embed(), view=self.rv)

class StatsModal(discord.ui.Modal, title="Set Player Stats"):
    kills = discord.ui.TextInput(label="Kills", required=True)
    deaths = discord.ui.TextInput(label="Deaths", required=True)

    def __init__(self, results_view, target_uid):
        super().__init__()
        self.rv = results_view
        self.uid = target_uid

    async def on_submit(self, interaction):
        if interaction.user.id not in self.rv.controllers():
            return await fail(interaction)
        k = safe_int(self.kills.value, 0, 999)
        d = safe_int(self.deaths.value, 0, 999)
        if k is None or d is None:
            return await fail(interaction)
        self.rv.stats[self.uid] = (k, d)
        await interaction.response.edit_message(embed=self.rv.results_embed(), view=self.rv)

class PlayerPick(discord.ui.Select):
    def __init__(self, rv):
        self.rv = rv
        opts = []
        for uid in rv.all_players():
            nm = rv.name(uid)
            opts.append(discord.SelectOption(label=shorten(nm, 25), value=str(uid)))
        super().__init__(placeholder="Select a player to set stats", min_values=1, max_values=1, options=opts)

    async def callback(self, interaction):
        if interaction.user.id not in self.rv.controllers():
            return await fail(interaction)
        uid = int(self.values[0])
        await interaction.response.send_modal(StatsModal(self.rv, uid))

class PlayerPickView(discord.ui.View):
    def __init__(self, rv):
        super().__init__(timeout=120)
        self.add_item(PlayerPick(rv))

class ResultsView(discord.ui.View):
    def __init__(self, wager, guild):
        super().__init__(timeout=None)
        self.wager = wager
        self.guild = guild
        self.stats = {}
        self.notes = None

    def controllers(self):
        s = {self.wager.host_id}
        if self.wager.middleman_id:
            s.add(self.wager.middleman_id)
        return s

    def all_players(self):
        return list(self.wager.team_a_ids() + self.wager.team_b_ids())

    def name(self, uid):
        m = self.guild.get_member(uid) if self.guild else None
        if m:
            return m.display_name
        u = bot.get_user(uid)
        return u.name if u else f"User{uid}"

    def totals(self, ids):
        return sum(self.stats.get(i, (0, 0))[0] for i in ids)

    def winner_text(self):
        ta = self.wager.team_a_ids()
        tb = self.wager.team_b_ids()
        ka = self.totals(ta)
        kb = self.totals(tb)
        if ka > kb:
            return f"🏆 Winner: {self.wager.a}"
        if kb > ka:
            return f"🏆 Winner: {self.wager.b}"
        return "🤝 Draw"

    def pretty_rows(self, ids):
        lines = []
        for uid in ids:
            nm = shorten(self.name(uid), 18)
            k, d = self.stats.get(uid, (0, 0))
            lines.append(f"**{nm}** — **{k}K** / **{d}D** • **KD {kd(k,d)}** {dot(k,d)}")
        return "\n".join(lines) if lines else "—"

    def results_embed(self):
        ta = self.wager.team_a_ids()
        tb = self.wager.team_b_ids()
        ka = self.totals(ta)
        kb = self.totals(tb)

        color = discord.Color.green() if ka != kb else discord.Color.gold()
        e = discord.Embed(title="🏁 MATCH RESULTS", description=self.winner_text(), color=color)
        e.add_field(name=f"{self.wager.a} — {ka} Kills", value=self.pretty_rows(ta), inline=False)
        e.add_field(name=f"{self.wager.b} — {kb} Kills", value=self.pretty_rows(tb), inline=False)
        if self.notes:
            e.add_field(name="Notes", value=self.notes, inline=False)
        e.set_footer(text="Enter stats for each player • Add notes • Finalize to generate image + log")
        return e

    @discord.ui.button(label="Set Player Stats", style=discord.ButtonStyle.primary, emoji="📝")
    async def set_stats(self, interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)
        await interaction.response.send_message("Pick a player:", view=PlayerPickView(self), ephemeral=True)

    @discord.ui.button(label="Add Notes", style=discord.ButtonStyle.secondary, emoji="🗒️")
    async def add_notes(self, interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)
        await interaction.response.send_modal(NotesModal(self))

    @discord.ui.button(label="Finalize", style=discord.ButtonStyle.success, emoji="✅")
    async def finalize(self, interaction, _):
        if interaction.user.id not in self.controllers():
            return await fail(interaction)

        ta = self.wager.team_a_ids()
        tb = self.wager.team_b_ids()

        img = scoreboard_image(
            self.guild,
            "MATCH RESULTS",
            self.wager.a,
            self.wager.b,
            ta,
            tb,
            self.stats,
            self.notes or "—",
            self.winner_text()
        )

        file = discord.File(fp=img, filename="results.png")
        embed = self.results_embed()
        embed.set_image(url="attachment://results.png")

        log = bot.get_channel(LOG_CHANNEL_ID)
        if log:
            await log.send(embed=embed, file=file)

        await interaction.response.edit_message(content="✅ **Results logged.**", embed=embed, attachments=[file], view=None)

class MiddlemanAcceptView(discord.ui.View):
    def __init__(self, wager, uid):
        super().__init__(timeout=120)
        self.wager = wager
        self.uid = uid

    @discord.ui.button(label="Accept Middleman", style=discord.ButtonStyle.success, emoji="🧑‍⚖️")
    async def accept(self, interaction, _):
        if interaction.user.id != self.uid:
            return await fail(interaction)
        self.wager.middleman_id = self.uid
        try:
            await interaction.message.delete()
        except Exception:
            pass
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
            return await interaction.response.send_message("❌ User lacks Middleman role.", ephemeral=True)
        await interaction.response.send_message(
            f"<@{member.id}> you were selected as **Middleman**.",
            view=MiddlemanAcceptView(self.wager, member.id)
        )

class MiddlemanView(discord.ui.View):
    def __init__(self, wager):
        super().__init__(timeout=60)
        self.add_item(MiddlemanPick(wager))

class WagerView(discord.ui.View):
    def __init__(self, host_id, size, a, b, prize, time, rules, guild):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.guild = guild
        self.middleman_id = None
        self.no_middleman = False
        self.size = clamp(int(size), 1, 8)
        self.a = str(a)[:40]
        self.b = str(b)[:40]
        self.prize = str(prize)[:1800]
        self.time = str(time)[:80]
        self.rules = str(rules)[:1200]
        self.team_a = set()
        self.team_b = set()
        self.status = "🟢 OPEN"
        self.msg_id = None
        self.begin_sent = False

    def team_a_ids(self):
        return list(self.team_a)

    def team_b_ids(self):
        return list(self.team_b)

    def embed(self):
        mm = "🚫 None" if self.no_middleman else (f"<@{self.middleman_id}>" if self.middleman_id else "—")
        e = discord.Embed(
            title="💎 WAGER",
            description=f"**Match:** {self.size}v{self.size} • **Start:** {self.time}\n**Prize:** {self.prize}",
            color=discord.Color.from_rgb(88, 101, 242)
        )
        e.add_field(name="Host", value=f"<@{self.host_id}>", inline=True)
        e.add_field(name="Middleman", value=mm, inline=True)
        e.add_field(name="\u200b", value="\u200b", inline=True)

        def list_team(ids):
            if not ids:
                return "—"
            names = []
            for uid in ids:
                m = self.guild.get_member(uid) if self.guild else None
                nm = m.display_name if m else None
                if not nm:
                    u = bot.get_user(uid)
                    nm = u.name if u else f"User{uid}"
                names.append(f"• {shorten(nm, 22)}")
            return "\n".join(names)

        e.add_field(name=self.a, value=list_team(self.team_a_ids()), inline=True)
        e.add_field(name=self.b, value=list_team(self.team_b_ids()), inline=True)
        e.add_field(name="\u200b", value="\u200b", inline=True)
        e.add_field(name="Rules", value=self.rules, inline=False)
        e.add_field(name="Status", value=self.status, inline=False)
        e.set_footer(text="Join teams • Optional middleman • Teams full → React to Begin")
        return e

    async def redraw(self, interaction):
        try:
            if interaction.response.is_done():
                await interaction.message.edit(embed=self.embed(), view=self)
            else:
                await interaction.response.edit_message(embed=self.embed(), view=self)
        except Exception:
            await fail(interaction)

    async def try_start(self, channel):
        if self.begin_sent:
            return
        if len(self.team_a) == self.size and len(self.team_b) == self.size:
            if self.middleman_id or self.no_middleman:
                self.begin_sent = True
                users = set(self.team_a_ids() + self.team_b_ids())
                mentions = " ".join(f"<@{u}>" for u in users)
                await channel.send(f"{mentions}\n⚔️ **Teams are full. React to begin.**", view=BeginView(self, users))

    @discord.ui.button(label="Join Team A", style=discord.ButtonStyle.primary)
    async def join_a(self, interaction, _):
        uid = interaction.user.id
        if uid in self.team_a:
            await interaction.response.send_message("You are already in Team A.", ephemeral=True)
            return
        if len(self.team_a) >= self.size:
            await interaction.response.send_message("Team A is full.", ephemeral=True)
            return
        self.team_b.discard(uid)
        self.team_a.add(uid)
        await self.redraw(interaction)
        await self.try_start(interaction.channel)

    @discord.ui.button(label="Join Team B", style=discord.ButtonStyle.primary)
    async def join_b(self, interaction, _):
        uid = interaction.user.id
        if uid in self.team_b:
            await interaction.response.send_message("You are already in Team B.", ephemeral=True)
            return
        if len(self.team_b) >= self.size:
            await interaction.response.send_message("Team B is full.", ephemeral=True)
            return
        self.team_a.discard(uid)
        self.team_b.add(uid)
        await self.redraw(interaction)
        await self.try_start(interaction.channel)

    @discord.ui.button(label="Middleman", style=discord.ButtonStyle.secondary, emoji="🧑‍⚖️")
    async def mm(self, interaction, _):
        if interaction.user.id != self.host_id:
            return await fail(interaction)
        await interaction.response.send_message("Select middleman:", view=MiddlemanView(self), ephemeral=True)

    @discord.ui.button(label="No Middleman", style=discord.ButtonStyle.secondary, emoji="🚫")
    async def no_mm(self, interaction, _):
        if interaction.user.id != self.host_id:
            return await fail(interaction)
        self.no_middleman = True
        await self.redraw(interaction)
        await self.try_start(interaction.channel)

    @discord.ui.button(label="End", style=discord.ButtonStyle.danger, emoji="🏁")
    async def end(self, interaction, _):
        if interaction.user.id not in {self.host_id, self.middleman_id}:
            return await fail(interaction)
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
