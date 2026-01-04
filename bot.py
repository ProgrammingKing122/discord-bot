import os
import math
import discord
from discord.ext import commands
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1443765937793667194
LOG_CHANNEL_ID = 123456789012345678

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def setup_hook():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

@bot.event
async def on_ready():
    print(f"ONLINE as {bot.user}")

def name(guild, uid):
    m = guild.get_member(uid)
    if m:
        return m.display_name
    u = bot.get_user(uid)
    return u.name if u else f"<@{uid}>"

def kd(k, d):
    return round(k / d, 2) if d else float(k)

def dot(k, d):
    return (46,204,113) if k>d else (241,196,15) if k==d else (231,76,60)

def font(size, bold=False):
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            size
        )
    except:
        return ImageFont.load_default()

def gradient(w, h, c1, c2):
    img = Image.new("RGB", (w, h), c1)
    d = ImageDraw.Draw(img)
    for y in range(h):
        r = int(c1[0] + (c2[0]-c1[0]) * y/h)
        g = int(c1[1] + (c2[1]-c1[1]) * y/h)
        b = int(c1[2] + (c2[2]-c1[2]) * y/h)
        d.line((0, y, w, y), fill=(r,g,b))
    return img

def scoreboard(guild, a, b, ta, tb, stats, winner):
    W, H = 1200, 720
    img = gradient(W, H, (20,24,40), (10,12,24))
    d = ImageDraw.Draw(img)

    d.rounded_rectangle((30,30,W-30,120), 28, fill=(35,40,70))
    d.text((50,50),"MATCH RESULTS",font=font(44,True),fill=(255,255,255))
    d.text((50,100),winner,font=font(24),fill=(180,220,255))

    col_w = (W-120)//2
    y0 = 160

    def draw_team(x, title, team):
        d.rounded_rectangle((x,y0,x+col_w,y0+500),26,fill=(28,32,60))
        d.text((x+24,y0+18),title,font=font(30,True),fill=(220,230,255))
        hy = y0+70
        d.text((x+24,hy),"PLAYER",font=font(18,True),fill=(160,180,210))
        d.text((x+col_w-260,hy),"K",font=font(18,True),fill=(160,180,210))
        d.text((x+col_w-200,hy),"D",font=font(18,True),fill=(160,180,210))
        d.text((x+col_w-130,hy),"KD",font=font(18,True),fill=(160,180,210))
        ry = hy+30
        for uid in team:
            k,dth = stats.get(uid,(0,0))
            d.rounded_rectangle((x+14,ry,x+col_w-14,ry+44),18,fill=(40,44,80))
            d.text((x+26,ry+10),name(guild,uid),font=font(20),fill=(240,240,255))
            d.text((x+col_w-260,ry+10),str(k),font=font(20),fill=(240,240,255))
            d.text((x+col_w-200,ry+10),str(dth),font=font(20),fill=(240,240,255))
            d.text((x+col_w-130,ry+10),str(kd(k,dth)),font=font(20),fill=(240,240,255))
            d.ellipse((x+col_w-70,ry+10,x+col_w-50,ry+30),fill=dot(k,dth))
            ry += 52

    draw_team(40,a,ta)
    draw_team(80+col_w,b,tb)

    buf = BytesIO()
    img.save(buf,"PNG")
    buf.seek(0)
    return buf

@bot.tree.command(name="ping", description="Ping", guild=discord.Object(id=GUILD_ID))
async def ping(i: discord.Interaction):
    await i.response.send_message("🏓 Pong")

@bot.tree.command(name="developerpanel", description="Debug panel", guild=discord.Object(id=GUILD_ID))
async def dev(i: discord.Interaction):
    e = discord.Embed(title="Developer Panel",color=discord.Color.orange())
    e.add_field(name="Latency",value=f"{round(bot.latency*1000)}ms",inline=False)
    e.add_field(name="Commands",value=", ".join(c.name for c in bot.tree.get_commands()),inline=False)
    await i.response.send_message(embed=e,ephemeral=True)

class StatsModal(discord.ui.Modal,title="Set Stats"):
    kills = discord.ui.TextInput(label="Kills")
    deaths = discord.ui.TextInput(label="Deaths")
    def __init__(self,view,uid):
        super().__init__()
        self.view=view
        self.uid=uid
    async def on_submit(self,i):
        self.view.stats[self.uid]=(int(self.kills.value),int(self.deaths.value))
        await i.response.edit_message(embed=self.view.embed(),view=self.view)

class PlayerPick(discord.ui.Select):
    def __init__(self,view):
        self.view=view
        super().__init__(options=[
            discord.SelectOption(label=name(view.guild,u),value=str(u))
            for u in view.players()
        ])
    async def callback(self,i):
        await i.response.send_modal(StatsModal(self.view,int(self.values[0])))

class ResultsView(discord.ui.View):
    def __init__(self,wager,guild):
        super().__init__(timeout=None)
        self.wager=wager
        self.guild=guild
        self.stats={}
    def players(self):
        return self.wager.ta+self.wager.tb
    def total(self,t):
        return sum(self.stats.get(u,(0,0))[0] for u in t)
    def winner(self):
        a,b=self.total(self.wager.ta),self.total(self.wager.tb)
        return f"🏆 Winner: {self.wager.a}" if a>b else f"🏆 Winner: {self.wager.b}" if b>a else "🤝 Draw"
    def embed(self):
        e=discord.Embed(title="Match Results",description=self.winner(),color=discord.Color.green())
        return e
    @discord.ui.button(label="Set Stats",style=discord.ButtonStyle.primary)
    async def setstats(self,i,_):
        v=discord.ui.View()
        v.add_item(PlayerPick(self))
        await i.response.send_message("Select player",view=v,ephemeral=True)
    @discord.ui.button(label="Finalize",style=discord.ButtonStyle.success)
    async def fin(self,i,_):
        img=scoreboard(self.guild,self.wager.a,self.wager.b,self.wager.ta,self.wager.tb,self.stats,self.winner())
        f=discord.File(img,"results.png")
        e=self.embed()
        e.set_image(url="attachment://results.png")
        ch=bot.get_channel(LOG_CHANNEL_ID)
        if ch:
            await ch.send(embed=e,file=f)
        await i.response.edit_message(embed=e,attachments=[f],view=None)

class WagerView(discord.ui.View):
    def __init__(self,host,size,a,b,prize,time,rules,guild):
        super().__init__(timeout=None)
        self.host=host
        self.guild=guild
        self.size=size
        self.a=a
        self.b=b
        self.prize=prize
        self.time=time
        self.rules=rules
        self.ta=[]
        self.tb=[]
    def embed(self):
        e=discord.Embed(
            title="💎 WAGER",
            description=f"{self.size}v{self.size} • {self.time}\nPrize: {self.prize}",
            color=discord.Color.blurple()
        )
        e.add_field(name=self.a,value="\n".join(name(self.guild,u) for u in self.ta) or "—",inline=True)
        e.add_field(name=self.b,value="\n".join(name(self.guild,u) for u in self.tb) or "—",inline=True)
        e.add_field(name="Rules",value=self.rules,inline=False)
        return e
    @discord.ui.button(label="Join A",style=discord.ButtonStyle.primary)
    async def ja(self,i,_):
        if i.user.id not in self.ta and len(self.ta)<self.size:
            if i.user.id in self.tb: self.tb.remove(i.user.id)
            self.ta.append(i.user.id)
            await i.response.edit_message(embed=self.embed(),view=self)
    @discord.ui.button(label="Join B",style=discord.ButtonStyle.primary)
    async def jb(self,i,_):
        if i.user.id not in self.tb and len(self.tb)<self.size:
            if i.user.id in self.ta: self.ta.remove(i.user.id)
            self.tb.append(i.user.id)
            await i.response.edit_message(embed=self.embed(),view=self)
    @discord.ui.button(label="End",style=discord.ButtonStyle.danger)
    async def end(self,i,_):
        rv=ResultsView(self,i.guild)
        await i.response.edit_message(embed=rv.embed(),view=rv)

@bot.tree.command(name="wager", description="Create wager", guild=discord.Object(id=GUILD_ID))
async def wager(i:discord.Interaction,size:int,team_a:str,team_b:str,prize:str,start_time:str,rules:str):
    v=WagerView(i.user.id,size,team_a,team_b,prize,start_time,rules,i.guild)
    await i.response.send_message(embed=v.embed(),view=v)

bot.run(TOKEN)
