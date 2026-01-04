import os
import discord
from discord.ext import commands
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = 1443765937793667194
MIDDLEMAN_ROLE_ID = 1457241934832861255
LOG_CHANNEL_ID = 1457242121009631312

ERR = '❌ Error has happened — please contact "Levi" for fixes.'

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

def fnt(size, bold=False):
    paths = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except:
            pass
    return ImageFont.load_default()

def kd(k, d):
    return round(k / d, 2) if d else float(k)

def kd_dot(k, d):
    if k > d:
        return (46, 204, 113)
    if k == d:
        return (241, 196, 15)
    return (231, 76, 60)

def display_name(guild: discord.Guild, uid: int):
    m = guild.get_member(uid)
    if m:
        return m.display_name
    u = bot.get_user(uid)
    return u.name if u else f"User{uid}"

def mention(uid: int):
    return f"<@{uid}>"

def safe_send_err(i: discord.Interaction):
    try:
        if i.response.is_done():
            return i.followup.send(ERR, ephemeral=True)
        return i.response.send_message(ERR, ephemeral=True)
    except:
        return None

def gradient_bg(w, h, c1, c2):
    img = Image.new("RGB", (w, h), c1)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        d.line((0, y, w, y), fill=(r, g, b))
    return img

def draw_scoreboard(guild, title, team_a_name, team_b_name, team_a_ids, team_b_ids, stats, winner_text, notes_text):
    W = 1280
    pad = 40
    top_h = 150
    col_gap = 32
    col_w = (W - pad * 2 - col_gap) // 2

    rows = max(len(team_a_ids), len(team_b_ids), 1)
    row_h = 58
    base_h = top_h + 520
    H = max(base_h, top_h + 220 + rows * row_h + 160)

    img = gradient_bg(W, H, (14, 16, 28), (8, 10, 20))
    d = ImageDraw.Draw(img)

    ft_title = fnt(48, True)
    ft_sub = fnt(24, False)
    ft_hdr = fnt(28, True)
    ft_col = fnt(18, True)
    ft_row = fnt(22, False)
    ft_small = fnt(18, False)

    d.rounded_rectangle((pad, 28, W - pad, top_h - 18), radius=26, fill=(30, 34, 58))
    d.text((pad + 26, 44), title, font=ft_title, fill=(245, 248, 255))
    d.text((pad + 30, 104), winner_text, font=ft_sub, fill=(180, 220, 255))

    def card(x, y, w, h, accent):
        d.rounded_rectangle((x, y, x + w, y + h), radius=26, fill=(22, 24, 40))
        d.rounded_rectangle((x, y, x + w, y + 12), radius=26, fill=accent)

    def team_card(x, y, name, ids, accent):
        ch = 220 + rows * row_h
        card(x, y, col_w, ch, accent)
        d.text((x + 24, y + 22), name, font=ft_hdr, fill=(238, 242, 255))
        hy = y + 76
        d.text((x + 24, hy), "PLAYER", font=ft_col, fill=(155, 170, 200))
        d.text((x + col_w - 290, hy), "K", font=ft_col, fill=(155, 170, 200))
        d.text((x + col_w - 225, hy), "D", font=ft_col, fill=(155, 170, 200))
        d.text((x + col_w - 160, hy), "KD", font=ft_col, fill=(155, 170, 200))
        ry = hy + 28
        total_k = 0
        for idx, uid in enumerate(ids):
            k, de = stats.get(uid, (0, 0))
            total_k += k
            bg = (28, 31, 54) if idx % 2 == 0 else (26, 28, 50)
            d.rounded_rectangle((x + 14, ry, x + col_w - 14, ry + row_h - 10), radius=18, fill=bg)
            nm = display_name(guild, uid)
            if len(nm) > 18:
                nm = nm[:17] + "…"
            d.text((x + 26, ry + 14), nm, font=ft_row, fill=(240, 243, 255))
            d.text((x + col_w - 292, ry + 14), str(k), font=ft_row, fill=(240, 243, 255))
            d.text((x + col_w - 227, ry + 14), str(de), font=ft_row, fill=(240, 243, 255))
            d.text((x + col_w - 170, ry + 14), str(kd(k, de)), font=ft_row, fill=(240, 243, 255))
            c = kd_dot(k, de)
            d.ellipse((x + col_w - 80, ry + 18, x + col_w - 58, ry + 40), fill=c)
            ry += row_h
        d.text((x + 24, y + ch - 54), f"Total Kills: {total_k}", font=ft_sub, fill=(190, 220, 255))
        return total_k, ch

    y0 = top_h + 14
    xA = pad
    xB = pad + col_w + col_gap

    ka, ha = team_card(xA, y0, team_a_name, team_a_ids, (92, 110, 255))
    kb, hb = team_card(xB, y0, team_b_name, team_b_ids, (170, 92, 255))

    ny = y0 + max(ha, hb) + 18
    notes_h = 110
    card(pad, ny, W - pad * 2, notes_h, (80, 90, 120))
    d.text((pad + 24, ny + 18), "Notes", font=ft_hdr, fill=(238, 242, 255))
    nt = notes_text.strip() if notes_text else "—"
    if len(nt) > 160:
        nt = nt[:159] + "…"
    d.text((pad + 24, ny + 64), nt, font=ft_small, fill=(210, 215, 235))

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
    async def begin(self, i: discord.Interaction, _):
        try:
            if i.user.id not in self.users:
                return await safe_send_err(i)
            self.ready.add(i.user.id)
            if self.ready == self.users:
                self.wager.status = "⚔️ IN PROGRESS"
                msg = await i.channel.fetch_message(self.wager.msg_id)
                await msg.edit(embed=self.wager.embed(), view=self.wager)
                await i.message.edit(content="⚔️ Match started.", view=None)
            else:
                await i.response.send_message("Ready ✔", ephemeral=True)
        except:
            await safe_send_err(i)

class NotesModal(discord.ui.Modal, title="Notes"):
    notes = discord.ui.TextInput(label="Notes", style=discord.TextStyle.paragraph, required=True, max_length=1200)

    def __init__(self, wager):
        super().__init__()
        self.wager = wager

    async def on_submit(self, i: discord.Interaction):
        try:
            if i.user.id not in self.wager.controllers():
                return await safe_send_err(i)
            self.wager.notes = str(self.notes.value).strip()
            await i.response.edit_message(embed=self.wager.embed(), view=self.wager)
        except:
            await safe_send_err(i)

class StatsModal(discord.ui.Modal, title="Set Player Stats"):
    kills = discord.ui.TextInput(label="Kills", required=True, max_length=4)
    deaths = discord.ui.TextInput(label="Deaths", required=True, max_length=4)

    def __init__(self, wager, uid):
        super().__init__()
        self.wager = wager
        self.uid = uid

    async def on_submit(self, i: discord.Interaction):
        try:
            if i.user.id not in self.wager.controllers():
                return await safe_send_err(i)
            k = int(str(self.kills.value).strip())
            d = int(str(self.deaths.value).strip())
            if k < 0 or d < 0 or k > 999 or d > 999:
                return await safe_send_err(i)
            self.wager.stats[self.uid] = (k, d)
            await i.response.edit_message(embed=self.wager.embed(), view=self.wager)
        except:
            await safe_send_err(i)

class PlayerPick(discord.ui.Select):
    def __init__(self, wager):
        self.wager = wager
        options = []
        for uid in wager.all_players():
            lbl = display_name(wager.guild, uid)
            if len(lbl) > 25:
                lbl = lbl[:24] + "…"
            options.append(discord.SelectOption(label=lbl, value=str(uid)))
        super().__init__(placeholder="Select a player", min_values=1, max_values=1, options=options)

    async def callback(self, i: discord.Interaction):
        try:
            if i.user.id not in self.wager.controllers():
                return await safe_send_err(i)
            uid = int(self.values[0])
            await i.response.send_modal(StatsModal(self.wager, uid))
        except:
            await safe_send_err(i)

class PlayerPickView(discord.ui.View):
    def __init__(self, wager):
        super().__init__(timeout=120)
        self.add_item(PlayerPick(wager))

class MiddlemanAcceptView(discord.ui.View):
    def __init__(self, wager, uid):
        super().__init__(timeout=120)
        self.wager = wager
        self.uid = uid

    @discord.ui.button(label="Accept Middleman", style=discord.ButtonStyle.success, emoji="🧑‍⚖️")
    async def accept(self, i: discord.Interaction, _):
        try:
            if i.user.id != self.uid:
                return await safe_send_err(i)
            self.wager.middleman = self.uid
            try:
                await i.message.delete()
            except:
                pass
            await self.wager.try_start(i.channel)
        except:
            await safe_send_err(i)

class MiddlemanPick(discord.ui.UserSelect):
    def __init__(self, wager):
        super().__init__(min_values=1, max_values=1, placeholder="Pick a middleman (role-gated)")
        self.wager = wager

    async def callback(self, i: discord.Interaction):
        try:
            if i.user.id != self.wager.host:
                return await safe_send_err(i)
            picked = self.values[0]
            m = i.guild.get_member(picked.id)
            if not m:
                return await i.response.send_message(ERR, ephemeral=True)
            if not any(r.id == MIDDLEMAN_ROLE_ID for r in m.roles):
                return await i.response.send_message("❌ That user does not have the Middleman role.", ephemeral=True)
            await i.response.send_message(
                f"{mention(m.id)} you were selected as Middleman. Press to accept.",
                view=MiddlemanAcceptView(self.wager, m.id)
            )
        except:
            await safe_send_err(i)

class MiddlemanView(discord.ui.View):
    def __init__(self, wager):
        super().__init__(timeout=60)
        self.add_item(MiddlemanPick(wager))

class WagerView(discord.ui.View):
    def __init__(self, host, size, team_a, team_b, prize, start_time, rules, guild):
        super().__init__(timeout=None)
        self.host = host
        self.guild = guild
        self.size = max(1, min(int(size), 8))
        self.team_a = str(team_a)[:40]
        self.team_b = str(team_b)[:40]
        self.prize = str(prize)[:300]
        self.start_time = str(start_time)[:80]
        self.rules = str(rules)[:1200]
        self.ta = []
        self.tb = []
        self.middleman = None
        self.no_mm = False
        self.status = "🟢 OPEN"
        self.msg_id = None
        self.begin_sent = False
        self.stats = {}
        self.notes = ""

    def controllers(self):
        s = {self.host}
        if self.middleman:
            s.add(self.middleman)
        return s

    def all_players(self):
        return list(dict.fromkeys(self.ta + self.tb))

    def totals(self, ids):
        return sum(self.stats.get(u, (0, 0))[0] for u in ids)

    def winner_text(self):
        a = self.totals(self.ta)
        b = self.totals(self.tb)
        if a > b:
            return f"🏆 Winner: {self.team_a}"
        if b > a:
            return f"🏆 Winner: {self.team_b}"
        return "🤝 Draw"

    def list_team(self, ids):
        if not ids:
            return "—"
        return "\n".join(f"• {mention(u)}" for u in ids)

    def embed(self):
        mm = "🚫 None" if self.no_mm else (mention(self.middleman) if self.middleman else "—")
        e = discord.Embed(
            title="💎 WAGER",
            description=f"**⚔️ Match** `{self.size}v{self.size}` • **🕒 Start** `{self.start_time}`\n**🎁 Prize** `{self.prize}`",
            color=discord.Color.from_rgb(88, 101, 242)
        )
        e.add_field(name="👑 Host", value=mention(self.host), inline=True)
        e.add_field(name="🧑‍⚖️ Middleman", value=mm, inline=True)
        e.add_field(name="\u200b", value="\u200b", inline=True)
        e.add_field(name=f"🅰️ {self.team_a}", value=self.list_team(self.ta), inline=True)
        e.add_field(name=f"🅱️ {self.team_b}", value=self.list_team(self.tb), inline=True)
        e.add_field(name="\u200b", value="\u200b", inline=True)
        e.add_field(name="📜 Rules", value=self.rules, inline=False)
        e.add_field(name="📊 Status", value=self.status, inline=False)

        if self.stats:
            ka = self.totals(self.ta)
            kb = self.totals(self.tb)
            e.add_field(name="📈 Current Totals", value=f"**{self.team_a}: {ka}** kills\n**{self.team_b}: {kb}** kills", inline=False)

        if self.notes:
            e.add_field(name="🗒️ Notes", value=self.notes[:1000], inline=False)

        e.set_footer(text="Join teams • Middleman optional • Teams full → React to Begin")
        return e

    async def try_start(self, channel: discord.abc.Messageable):
        if self.begin_sent:
            return
        if len(self.ta) == self.size and len(self.tb) == self.size:
            if self.no_mm or self.middleman:
                self.begin_sent = True
                users = set(self.ta + self.tb)
                mentions = " ".join(mention(u) for u in users)
                await channel.send(f"{mentions}\n⚔️ **Teams are full. React to begin.**", view=BeginView(self, users))

    async def redraw(self, i: discord.Interaction):
        try:
            if i.response.is_done():
                await i.followup.edit_message(i.message.id, embed=self.embed(), view=self)
            else:
                await i.response.edit_message(embed=self.embed(), view=self)
        except:
            try:
                await i.message.edit(embed=self.embed(), view=self)
            except:
                await safe_send_err(i)

    @discord.ui.button(label="Join Team A", style=discord.ButtonStyle.primary, emoji="🅰️")
    async def join_a(self, i: discord.Interaction, _):
        try:
            u = i.user.id
            if u in self.ta:
                return await i.response.send_message("You are already in Team A.", ephemeral=True)
            if len(self.ta) >= self.size:
                return await i.response.send_message("Team A is full.", ephemeral=True)
            if u in self.tb:
                self.tb.remove(u)
            self.ta.append(u)
            await i.response.edit_message(embed=self.embed(), view=self)
            await self.try_start(i.channel)
        except:
            await safe_send_err(i)

    @discord.ui.button(label="Join Team B", style=discord.ButtonStyle.primary, emoji="🅱️")
    async def join_b(self, i: discord.Interaction, _):
        try:
            u = i.user.id
            if u in self.tb:
                return await i.response.send_message("You are already in Team B.", ephemeral=True)
            if len(self.tb) >= self.size:
                return await i.response.send_message("Team B is full.", ephemeral=True)
            if u in self.ta:
                self.ta.remove(u)
            self.tb.append(u)
            await i.response.edit_message(embed=self.embed(), view=self)
            await self.try_start(i.channel)
        except:
            await safe_send_err(i)

    @discord.ui.button(label="Middleman", style=discord.ButtonStyle.secondary, emoji="🧑‍⚖️")
    async def middleman_btn(self, i: discord.Interaction, _):
        try:
            if i.user.id != self.host:
                return await safe_send_err(i)
            await i.response.send_message("Select middleman:", view=MiddlemanView(self), ephemeral=True)
        except:
            await safe_send_err(i)

    @discord.ui.button(label="No Middleman", style=discord.ButtonStyle.secondary, emoji="🚫")
    async def no_middleman_btn(self, i: discord.Interaction, _):
        try:
            if i.user.id != self.host:
                return await safe_send_err(i)
            self.no_mm = True
            await i.response.edit_message(embed=self.embed(), view=self)
            await self.try_start(i.channel)
        except:
            await safe_send_err(i)

    @discord.ui.button(label="Set Stats", style=discord.ButtonStyle.secondary, emoji="📝")
    async def set_stats_btn(self, i: discord.Interaction, _):
        try:
            if i.user.id not in self.controllers():
                return await safe_send_err(i)
            if not self.all_players():
                return await i.response.send_message("No players in teams yet.", ephemeral=True)
            await i.response.send_message("Select a player:", view=PlayerPickView(self), ephemeral=True)
        except:
            await safe_send_err(i)

    @discord.ui.button(label="Notes", style=discord.ButtonStyle.secondary, emoji="🗒️")
    async def notes_btn(self, i: discord.Interaction, _):
        try:
            if i.user.id not in self.controllers():
                return await safe_send_err(i)
            await i.response.send_modal(NotesModal(self))
        except:
            await safe_send_err(i)

    @discord.ui.button(label="Finalize", style=discord.ButtonStyle.success, emoji="✅")
    async def finalize_btn(self, i: discord.Interaction, _):
        try:
            if i.user.id not in self.controllers():
                return await safe_send_err(i)
            winner = self.winner_text()
            img = draw_scoreboard(
                i.guild,
                "MATCH RESULTS",
                self.team_a,
                self.team_b,
                self.ta,
                self.tb,
                self.stats,
                winner,
                self.notes
            )
            file = discord.File(img, filename="results.png")
            e = discord.Embed(title="🏁 MATCH RESULTS", description=winner, color=discord.Color.green())
            e.set_image(url="attachment://results.png")
            e.add_field(name=f"{self.team_a} kills", value=str(self.totals(self.ta)), inline=True)
            e.add_field(name=f"{self.team_b} kills", value=str(self.totals(self.tb)), inline=True)
            if self.notes:
                e.add_field(name="Notes", value=self.notes[:1000], inline=False)

            log = bot.get_channel(LOG_CHANNEL_ID)
            if log:
                await log.send(embed=e, file=file)

            await i.response.edit_message(embed=e, attachments=[file], view=None)
        except:
            await safe_send_err(i)

    @discord.ui.button(label="End", style=discord.ButtonStyle.danger, emoji="🏁")
    async def end_btn(self, i: discord.Interaction, _):
        try:
            if i.user.id not in self.controllers():
                return await safe_send_err(i)
            self.status = "🏁 FINISHING"
            await i.response.edit_message(embed=self.embed(), view=self)
        except:
            await safe_send_err(i)

@bot.tree.command(name="ping", description="Ping test", guild=discord.Object(id=GUILD_ID))
async def ping(i: discord.Interaction):
    await i.response.send_message("🏓 Pong! All set up.")

@bot.tree.command(name="developerpanel", description="Developer debug panel", guild=discord.Object(id=GUILD_ID))
async def developerpanel(i: discord.Interaction):
    try:
        e = discord.Embed(title="🛠 Developer Panel", color=discord.Color.orange())
        e.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=False)
        e.add_field(name="Guilds", value=str(len(bot.guilds)), inline=False)
        e.add_field(name="Commands", value=", ".join(c.name for c in bot.tree.get_commands()), inline=False)
        await i.response.send_message(embed=e, ephemeral=True)
    except:
        await safe_send_err(i)

@bot.tree.command(name="wager", description="Create a wager", guild=discord.Object(id=GUILD_ID))
async def wager(i: discord.Interaction, size: int, team_a: str, team_b: str, prize: str, start_time: str, rules: str):
    try:
        v = WagerView(i.user.id, size, team_a, team_b, prize, start_time, rules, i.guild)
        await i.response.send_message(embed=v.embed(), view=v)
        msg = await i.original_response()
        v.msg_id = msg.id
    except:
        await safe_send_err(i)

@bot.event
async def setup_hook():
    guild = discord.Object(id=GUILD_ID)
    try:
        bot.tree.remove_command("wager", guild=guild)
    except:
        pass
    try:
        bot.tree.remove_command("ping", guild=guild)
    except:
        pass
    try:
        bot.tree.remove_command("developerpanel", guild=guild)
    except:
        pass
    await bot.tree.sync(guild=guild)

bot.run(TOKEN)
