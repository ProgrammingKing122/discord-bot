import os
import discord
from discord.ext import commands
from discord import app_commands
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1443765937793667194
MIDDLEMAN_ROLE_ID = 1457241934832861255
LOG_CHANNEL_ID = 1457242121009631312
ERR = '❌ Error has happened — please contact "Levi" for fixes.'

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def setup_hook():
    guild = discord.Object(id=GUILD_ID)
    try:
        bot.tree.remove_command("wager", guild=guild)
    except Exception:
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

def scoreboard(guild, a, b, ta, tb, stats, winner, notes):
    w, h = 1100, 650
    img = Image.new("RGB", (w, h), (18, 18, 24))
    d = ImageDraw.Draw(img)
    d.text((40, 30), "MATCH RESULTS", font=font(42), fill=(255,255,255))
    d.text((40, 85), winner, font=font(22), fill=(180,220,255))
    y = 150
    for name, team in ((a, ta), (b, tb)):
        d.text((40, y), name, font=font(28), fill=(200,200,255))
        y += 40
        for uid in team:
            k, de = stats.get(uid, (0,0))
            line = f"{dn(guild,uid)}  K:{k}  D:{de}  KD:{kd(k,de)} {dot(k,de)}"
            d.text((60, y), line, font=font(22), fill=(230,230,255))
            y += 30
        y += 20
    if notes:
        d.text((40, y+10), "Notes:", font=font(26), fill=(200,200,255))
        d.text((40, y+50), notes[:250], font=font(22), fill=(220,220,220))
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

class BeginView(discord.ui.View):
    def __init__(self, wager, users):
        super().__init__(timeout=None)
        self.wager = wager
        self.users = set(users)
        self.ready = set()

    @discord.ui.button(label="React to Begin", style=discord.ButtonStyle.success, emoji="⚔️")
    async def begin(self, i, _):
        if i.user.id not in self.users:
            return
        self.ready.add(i.user.id)
        if self.ready == self.users:
            self.wager.status = "⚔️ IN PROGRESS"
            msg = await i.channel.fetch_message(self.wager.msg_id)
            await msg.edit(embed=self.wager.embed(), view=self.wager)
            await i.message.edit(content="⚔️ Match started.", view=None)
        else:
            await i.response.send_message("Ready ✔", ephemeral=True)

class StatsModal(discord.ui.Modal, title="Set Player Stats"):
    kills = discord.ui.TextInput(label="Kills", required=True)
    deaths = discord.ui.TextInput(label="Deaths", required=True)

    def __init__(self, rv, uid):
        super().__init__()
        self.rv = rv
        self.uid = uid

    async def on_submit(self, i):
        if i.user.id not in self.rv.controllers():
            return await i.response.send_message(ERR, ephemeral=True)
        self.rv.stats[self.uid] = (int(self.kills.value), int(self.deaths.value))
        await i.response.edit_message(embed=self.rv.embed(), view=self.rv)

class PlayerPick(discord.ui.Select):
    def __init__(self, rv):
        self.rv = rv
        opts = [discord.SelectOption(label=dn(rv.guild,u), value=str(u)) for u in rv.players()]
        super().__init__(placeholder="Select player", options=opts)

    async def callback(self, i):
        if i.user.id not in self.rv.controllers():
            return
        await i.response.send_modal(StatsModal(self.rv, int(self.values[0])))

class ResultsView(discord.ui.View):
    def __init__(self, wager, guild):
        super().__init__(timeout=None)
        self.wager = wager
        self.guild = guild
        self.stats = {}
        self.notes = ""

    def controllers(self):
        s = {self.wager.host}
        if self.wager.middleman:
            s.add(self.wager.middleman)
        return s

    def players(self):
        return self.wager.ta + self.wager.tb

    def total(self, team):
        return sum(self.stats.get(u,(0,0))[0] for u in team)

    def winner(self):
        a,b = self.total(self.wager.ta), self.total(self.wager.tb)
        if a>b: return f"🏆 Winner: {self.wager.a}"
        if b>a: return f"🏆 Winner: {self.wager.b}"
        return "🤝 Draw"

    def embed(self):
        e = discord.Embed(title="🏁 MATCH RESULTS", description=self.winner(), color=discord.Color.green())
        def block(team):
            return "\n".join(f"{dn(self.guild,u)} • {self.stats.get(u,(0,0))[0]}K {self.stats.get(u,(0,0))[1]}D KD {kd(*self.stats.get(u,(0,0)))} {dot(*self.stats.get(u,(0,0)))}" for u in team) or "—"
        e.add_field(name=f"{self.wager.a}", value=block(self.wager.ta), inline=False)
        e.add_field(name=f"{self.wager.b}", value=block(self.wager.tb), inline=False)
        if self.notes:
            e.add_field(name="Notes", value=self.notes, inline=False)
        return e

    @discord.ui.button(label="Set Stats", style=discord.ButtonStyle.primary)
    async def setstats(self,i,_):
        if i.user.id not in self.controllers(): return
        v=discord.ui.View()
        v.add_item(PlayerPick(self))
        await i.response.send_message("Select player:",view=v,ephemeral=True)

    @discord.ui.button(label="Finalize", style=discord.ButtonStyle.success)
    async def fin(self,i,_):
        if i.user.id not in self.controllers(): return
        img = scoreboard(self.guild,self.wager.a,self.wager.b,self.wager.ta,self.wager.tb,self.stats,self.winner(),self.notes)
        f=discord.File(img,"results.png")
        e=self.embed()
        e.set_image(url="attachment://results.png")
        log=bot.get_channel(LOG_CHANNEL_ID)
        if log: await log.send(embed=e,file=f)
        await i.response.edit_message(content="✅ Results logged.",embed=e,attachments=[f],view=None)

class MiddlemanAccept(discord.ui.View):
    def __init__(self,wager,uid):
        super().__init__(timeout=60)
        self.wager=wager
        self.uid=uid

    @discord.ui.button(label="Accept Middleman",style=discord.ButtonStyle.success)
    async def acc(self,i,_):
        if i.user.id!=self.uid: return
        self.wager.middleman=self.uid
        await i.message.delete()
        await self.wager.try_start(i.channel)

class WagerView(discord.ui.View):
    def __init__(self,host,size,a,b,prize,time,rules,guild):
        super().__init__(timeout=None)
        self.host=host
        self.guild=guild
        self.middleman=None
        self.no_mm=False
        self.size=size
        self.a=a
        self.b=b
        self.prize=prize
        self.time=time
        self.rules=rules
        self.ta=[]
        self.tb=[]
        self.status="🟢 OPEN"
        self.msg_id=None

    def embed(self):
        e=discord.Embed(title="💎 WAGER",description=f"⚔️ {self.size}v{self.size} • 🕒 {self.time}\n🎁 {self.prize}",color=discord.Color.from_rgb(88,101,242))
        e.add_field(name="👑 Host",value=f"<@{self.host}>",inline=True)
        e.add_field(name="🧑‍⚖️ Middleman",value="🚫 None" if self.no_mm else (f"<@{self.middleman}>" if self.middleman else "—"),inline=True)
        e.add_field(name="\u200b",value="\u200b",inline=True)
        e.add_field(name=f"🅰️ {self.a}",value="\n".join(dn(self.guild,u) for u in self.ta) or "—",inline=True)
        e.add_field(name=f"🅱️ {self.b}",value="\n".join(dn(self.guild,u) for u in self.tb) or "—",inline=True)
        e.add_field(name="\u200b",value="\u200b",inline=True)
        e.add_field(name="📜 Rules",value=self.rules,inline=False)
        e.add_field(name="📊 Status",value=self.status,inline=False)
        return e

    async def try_start(self,ch):
        if len(self.ta)==self.size and len(self.tb)==self.size and (self.middleman or self.no_mm):
            users=set(self.ta+self.tb)
            await ch.send(" ".join(f"<@{u}>" for u in users),view=BeginView(self,users))

    @discord.ui.button(label="Join Team A",style=discord.ButtonStyle.primary)
    async def ja(self,i,_):
        u=i.user.id
        if u in self.ta or len(self.ta)>=self.size: return
        if u in self.tb: self.tb.remove(u)
        self.ta.append(u)
        await i.response.edit_message(embed=self.embed(),view=self)
        await self.try_start(i.channel)

    @discord.ui.button(label="Join Team B",style=discord.ButtonStyle.primary)
    async def jb(self,i,_):
        u=i.user.id
        if u in self.tb or len(self.tb)>=self.size: return
        if u in self.ta: self.ta.remove(u)
        self.tb.append(u)
        await i.response.edit_message(embed=self.embed(),view=self)
        await self.try_start(i.channel)

    @discord.ui.button(label="Middleman",style=discord.ButtonStyle.secondary)
    async def mm(self,i,_):
        if i.user.id!=self.host: return
        v=discord.ui.View()
        s=discord.ui.UserSelect()
        async def cb(ii):
            m=ii.guild.get_member(ii.values[0].id)
            if not any(r.id==MIDDLEMAN_ROLE_ID for r in m.roles): return
            await ii.response.send_message(f"<@{m.id}> selected.",view=MiddlemanAccept(self,m.id))
        s.callback=cb
        v.add_item(s)
        await i.response.send_message("Select middleman:",view=v,ephemeral=True)

    @discord.ui.button(label="No Middleman",style=discord.ButtonStyle.secondary)
    async def nomm(self,i,_):
        if i.user.id!=self.host: return
        self.no_mm=True
        await i.response.edit_message(embed=self.embed(),view=self)
        await self.try_start(i.channel)

    @discord.ui.button(label="End",style=discord.ButtonStyle.danger)
    async def end(self,i,_):
        if i.user.id not in {self.host,self.middleman}: return
        rv=ResultsView(self,i.guild)
        await i.response.edit_message(embed=rv.embed(),view=rv)

@bot.tree.command(name="wager", guild=discord.Object(id=GUILD_ID))
async def wager(i:discord.Interaction,size:int,team_a:str,team_b:str,prize:str,start_time:str,rules:str):
    v=WagerView(i.user.id,size,team_a,team_b,prize,start_time,rules,i.guild)
    await i.response.send_message(embed=v.embed(),view=v)
    m=await i.original_response()
    v.msg_id=m.id

bot.run(TOKEN)
