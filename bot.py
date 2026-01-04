import os
import discord
from discord.ext import commands
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1443765937793667194
MIDDLEMAN_ROLE_ID = 1457241934832861255
LOG_CHANNEL_ID = 1457242121009631312

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

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
        bot.tree.remove_command("DeveloperPanel", guild=guild)
    except:
        pass
    await bot.tree.sync(guild=guild)

@bot.event
async def on_ready():
    print(f"ONLINE as {bot.user}")

def dn(guild, uid):
    m = guild.get_member(uid)
    if m:
        return m.display_name
    u = bot.get_user(uid)
    return u.name if u else f"<@{uid}>"

def kd(k, d):
    return round(k / d, 2) if d else float(k)

def dot(k, d):
    return "🟢" if k > d else "🟡" if k == d else "🔴"

def font(size):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except:
        return ImageFont.load_default()

def scoreboard(guild, a, b, ta, tb, stats, winner):
    img = Image.new("RGB", (1000, 600), (20, 20, 26))
    d = ImageDraw.Draw(img)
    d.text((40, 30), "MATCH RESULTS", font=font(40), fill=(255,255,255))
    d.text((40, 90), winner, font=font(22), fill=(180,220,255))
    y = 150
    for name, team in ((a, ta), (b, tb)):
        d.text((40, y), name, font=font(28), fill=(200,200,255))
        y += 40
        for uid in team:
            k, de = stats.get(uid, (0,0))
            d.text((60, y), f"{dn(guild,uid)}  K:{k} D:{de} KD:{kd(k,de)} {dot(k,de)}", font=font(20), fill=(230,230,255))
            y += 28
        y += 20
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

@bot.tree.command(name="ping", description="Ping test", guild=discord.Object(id=GUILD_ID))
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong! Bot is online.")

@bot.tree.command(name="DeveloperPanel", description="Developer debug panel", guild=discord.Object(id=GUILD_ID))
async def devpanel(interaction: discord.Interaction):
    e = discord.Embed(title="🛠 Developer Panel", color=discord.Color.orange())
    e.add_field(name="Latency", value=f"{round(bot.latency*1000)}ms", inline=False)
    e.add_field(name="Guilds", value=str(len(bot.guilds)), inline=False)
    e.add_field(name="Commands", value=", ".join(c.name for c in bot.tree.get_commands()), inline=False)
    await interaction.response.send_message(embed=e, ephemeral=True)

class WagerView(discord.ui.View):
    def __init__(self, host, size, a, b, prize, time, rules, guild):
        super().__init__(timeout=None)
        self.host = host
        self.guild = guild
        self.middleman = None
        self.size = size
        self.a = a
        self.b = b
        self.prize = prize
        self.time = time
        self.rules = rules
        self.ta = []
        self.tb = []
        self.stats = {}
        self.status = "🟢 OPEN"
        self.msg_id = None

    def embed(self):
        e = discord.Embed(
            title="💎 WAGER",
            description=f"⚔️ {self.size}v{self.size} • 🕒 {self.time}\n🎁 {self.prize}",
            color=discord.Color.blurple()
        )
        e.add_field(name="Host", value=f"<@{self.host}>", inline=True)
        e.add_field(name="Middleman", value=f"<@{self.middleman}>" if self.middleman else "—", inline=True)
        e.add_field(name="\u200b", value="\u200b", inline=True)
        e.add_field(name=f"🅰️ {self.a}", value="\n".join(dn(self.guild,u) for u in self.ta) or "—", inline=True)
        e.add_field(name=f"🅱️ {self.b}", value="\n".join(dn(self.guild,u) for u in self.tb) or "—", inline=True)
        e.add_field(name="\u200b", value="\u200b", inline=True)
        e.add_field(name="Rules", value=self.rules, inline=False)
        e.add_field(name="Status", value=self.status, inline=False)
        return e

    async def redraw(self, i):
        await i.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Join Team A", style=discord.ButtonStyle.primary)
    async def ja(self, i, _):
        u = i.user.id
        if u in self.ta or len(self.ta) >= self.size:
            return
        if u in self.tb:
            self.tb.remove(u)
        self.ta.append(u)
        await self.redraw(i)

    @discord.ui.button(label="Join Team B", style=discord.ButtonStyle.primary)
    async def jb(self, i, _):
        u = i.user.id
        if u in self.tb or len(self.tb) >= self.size:
            return
        if u in self.ta:
            self.ta.remove(u)
        self.tb.append(u)
        await self.redraw(i)

    @discord.ui.button(label="End", style=discord.ButtonStyle.danger)
    async def end(self, i, _):
        if i.user.id != self.host:
            return
        ka = sum(self.stats.get(u,(0,0))[0] for u in self.ta)
        kb = sum(self.stats.get(u,(0,0))[0] for u in self.tb)
        winner = f"🏆 Winner: {self.a}" if ka>kb else f"🏆 Winner: {self.b}" if kb>ka else "🤝 Draw"
        img = scoreboard(self.guild,self.a,self.b,self.ta,self.tb,self.stats,winner)
        f = discord.File(img,"results.png")
        e = discord.Embed(title="🏁 MATCH RESULTS", description=winner, color=discord.Color.green())
        e.set_image(url="attachment://results.png")
        log = bot.get_channel(LOG_CHANNEL_ID)
        if log:
            await log.send(embed=e,file=f)
        await i.response.edit_message(embed=e,attachments=[f],view=None)

@bot.tree.command(name="wager", description="Create a wager", guild=discord.Object(id=GUILD_ID))
async def wager(
    interaction: discord.Interaction,
    size: int,
    team_a: str,
    team_b: str,
    prize: str,
    start_time: str,
    rules: str
):
    v = WagerView(interaction.user.id,size,team_a,team_b,prize,start_time,rules,interaction.guild)
    await interaction.response.send_message(embed=v.embed(),view=v)
    m = await interaction.original_response()
    v.msg_id = m.id

bot.run(TOKEN)
