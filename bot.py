import os
import re
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1443765937793667194

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

ERR_TXT = '❌ **Error has happened — please contact "Levi" for fixes.**'

def _digits(s: str) -> int | None:
    m = re.search(r"\d{15,21}", s or "")
    return int(m.group(0)) if m else None

async def fail(interaction: discord.Interaction):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(ERR_TXT, ephemeral=True)
        else:
            await interaction.response.send_message(ERR_TXT, ephemeral=True)
    except Exception:
        pass

@bot.event
async def setup_hook():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

@bot.event
async def on_ready():
    print(f"ONLINE as {bot.user}")

class EditRulesModal(discord.ui.Modal, title="Edit Rules"):
    rules = discord.ui.TextInput(label="Rules", style=discord.TextStyle.paragraph, required=True, max_length=1200)

    def __init__(self, view):
        super().__init__()
        self.view = view
        self.rules.default = view.rules

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if interaction.user.id not in self.view.controllers():
                return await fail(interaction)
            self.view.rules = str(self.rules.value).strip()
            await interaction.response.edit_message(embed=self.view.embed(), view=self.view)
        except Exception:
            await fail(interaction)

class EndResultModal(discord.ui.Modal, title="End Wager"):
    result = discord.ui.TextInput(label="Result", style=discord.TextStyle.paragraph, required=True, max_length=1200)

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if interaction.user.id not in self.view.controllers():
                return await fail(interaction)
            self.view.status = "🏁 FINISHED"
            self.view.result_text = str(self.result.value).strip()
            await interaction.response.edit_message(embed=self.view.embed(), view=self.view)
        except Exception:
            await fail(interaction)

class MiddlemanSelect(discord.ui.UserSelect):
    def __init__(self, view):
        super().__init__(placeholder="Select middleman", min_values=1, max_values=1)
        self.view = view

    async def callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.view.host_id:
                return await fail(interaction)
            self.view.middleman_id = self.values[0].id
            await interaction.response.edit_message(embed=self.view.embed(), view=self.view)
        except Exception:
            await fail(interaction)

class MiddlemanPickView(discord.ui.View):
    def __init__(self, wager_view):
        super().__init__(timeout=120)
        self.wager_view = wager_view
        self.add_item(MiddlemanSelect(wager_view))

    async def on_timeout(self):
        try:
            for c in self.children:
                if hasattr(c, "disabled"):
                    c.disabled = True
        except Exception:
            pass

class BeginView(discord.ui.View):
    def __init__(self, wager_view, player_ids, parent_message_id):
        super().__init__(timeout=None)
        self.wager_view = wager_view
        self.player_ids = set(player_ids)
        self.ready = set()
        self.parent_message_id = parent_message_id

    @discord.ui.button(label="React to Begin", style=discord.ButtonStyle.success, emoji="⚔️")
    async def begin(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if interaction.user.id not in self.player_ids:
                return await fail(interaction)

            self.ready.add(interaction.user.id)
            if self.ready != self.player_ids:
                if not interaction.response.is_done():
                    await interaction.response.send_message("Ready ✔", ephemeral=True)
                else:
                    await interaction.followup.send("Ready ✔", ephemeral=True)
                return

            self.wager_view.status = "⚔️ IN PROGRESS"
            try:
                msg = await interaction.channel.fetch_message(self.parent_message_id)
                await msg.edit(embed=self.wager_view.embed(), view=self.wager_view)
            except Exception:
                pass

            await interaction.message.edit(content="⚔️ **Wager started!**", view=None)
        except Exception:
            await fail(interaction)

class WagerView(discord.ui.View):
    def __init__(self, host_id, team_size, team_a_name, team_b_name, prize, start_time, rules):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.middleman_id = None
        self.team_size = max(1, min(int(team_size), 8))
        self.team_a_name = team_a_name.strip()[:40] or "Team A"
        self.team_b_name = team_b_name.strip()[:40] or "Team B"
        self.prize = prize.strip()[:1800]
        self.start_time = start_time.strip()[:80]
        self.rules = rules.strip()[:1200]
        self.team_a = []
        self.team_b = []
        self.status = "🟢 OPEN"
        self.result_text = None
        self.locked = False

    def controllers(self):
        s = {self.host_id}
        if self.middleman_id:
            s.add(self.middleman_id)
        return s

    def _team_text(self, team):
        return "\n".join(team) if team else "—"

    def _player_ids(self):
        ids = set()
        for m in self.team_a + self.team_b:
            x = _digits(m)
            if x:
                ids.add(x)
        return ids

    def embed(self):
        e = discord.Embed(
            title="💎 WAGER",
            description=(
                f"**Match:** {self.team_size}v{self.team_size} • **Start:** {self.start_time}\n"
                f"**Prize:** {self.prize}"
            ),
            color=discord.Color.from_rgb(88, 101, 242)
        )
        e.add_field(name="Host", value=f"<@{self.host_id}>", inline=True)
        e.add_field(
            name="Middleman",
            value=(f"<@{self.middleman_id}>" if self.middleman_id else "—"),
            inline=True
        )
        e.add_field(name="\u200b", value="\u200b", inline=True)
        e.add_field(name=self.team_a_name, value=self._team_text(self.team_a), inline=True)
        e.add_field(name=self.team_b_name, value=self._team_text(self.team_b), inline=True)
        e.add_field(name="\u200b", value="\u200b", inline=True)
        e.add_field(name="Rules", value=(self.rules if self.rules else "—"), inline=False)
        if self.result_text:
            e.add_field(name="Result", value=self.result_text, inline=False)
        e.add_field(name="Status", value=self.status, inline=False)
        e.set_footer(text="Join teams • Teams fill → React to Begin • Host/Middleman can edit rules & end")
        return e

    async def _maybe_full(self, interaction: discord.Interaction):
        if self.locked:
            return
        if len(self.team_a) == self.team_size and len(self.team_b) == self.team_size:
            self.locked = True
            self.status = "🟣 READY"
            try:
                if interaction.response.is_done():
                    await interaction.followup.edit_message(message_id=interaction.message.id, embed=self.embed(), view=self)
                else:
                    await interaction.response.edit_message(embed=self.embed(), view=self)
            except Exception:
                try:
                    await interaction.message.edit(embed=self.embed(), view=self)
                except Exception:
                    pass

            mentions = " ".join(self.team_a + self.team_b)
            begin_msg = await interaction.channel.send(
                f"{mentions}\n⚔️ **Teams are full. React to begin.**",
                view=BeginView(self, self._player_ids(), interaction.message.id)
            )
            return begin_msg

    async def _safe_edit(self, interaction: discord.Interaction):
        try:
            if interaction.response.is_done():
                await interaction.message.edit(embed=self.embed(), view=self)
            else:
                await interaction.response.edit_message(embed=self.embed(), view=self)
        except Exception:
            try:
                await interaction.message.edit(embed=self.embed(), view=self)
            except Exception:
                await fail(interaction)

    @discord.ui.button(label="Join Team A", style=discord.ButtonStyle.primary)
    async def join_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            u = interaction.user.mention
            if u in self.team_b:
                self.team_b.remove(u)
            if u not in self.team_a:
                if len(self.team_a) >= self.team_size:
                    return await fail(interaction)
                self.team_a.append(u)
            await self._safe_edit(interaction)
            await self._maybe_full(interaction)
        except Exception:
            await fail(interaction)

    @discord.ui.button(label="Join Team B", style=discord.ButtonStyle.primary)
    async def join_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            u = interaction.user.mention
            if u in self.team_a:
                self.team_a.remove(u)
            if u not in self.team_b:
                if len(self.team_b) >= self.team_size:
                    return await fail(interaction)
                self.team_b.append(u)
            await self._safe_edit(interaction)
            await self._maybe_full(interaction)
        except Exception:
            await fail(interaction)

    @discord.ui.button(label="Rules", style=discord.ButtonStyle.secondary, emoji="📜")
    async def rules_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if interaction.user.id not in self.controllers():
                return await fail(interaction)
            await interaction.response.send_modal(EditRulesModal(self))
        except Exception:
            await fail(interaction)

    @discord.ui.button(label="Middleman", style=discord.ButtonStyle.secondary, emoji="🧑‍⚖️")
    async def middleman_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if interaction.user.id != self.host_id:
                return await fail(interaction)
            await interaction.response.send_message("Pick a middleman:", view=MiddlemanPickView(self), ephemeral=True)
        except Exception:
            await fail(interaction)

    @discord.ui.button(label="End", style=discord.ButtonStyle.danger, emoji="🏁")
    async def end_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if interaction.user.id not in self.controllers():
                return await fail(interaction)
            await interaction.response.send_modal(EndResultModal(self))
        except Exception:
            await fail(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if interaction.user.id not in self.controllers():
                return await fail(interaction)
            self.status = "❌ CANCELLED"
            await self._safe_edit(interaction)
            try:
                await interaction.message.edit(view=None)
            except Exception:
                pass
        except Exception:
            await fail(interaction)

@bot.tree.command(
    name="wager",
    description="Create a wager",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(
    team_size="Players per team (1=1v1, 2=2v2, etc.)",
    team_a_name="Team/Clan A name",
    team_b_name="Team/Clan B name",
    prize="Prize on the table",
    start_time="Start time (e.g. 7:30PM AEST)",
    rules="Rules text"
)
async def wager(
    interaction: discord.Interaction,
    team_size: int,
    team_a_name: str,
    team_b_name: str,
    prize: str,
    start_time: str,
    rules: str
):
    try:
        view = WagerView(
            host_id=interaction.user.id,
            team_size=team_size,
            team_a_name=team_a_name,
            team_b_name=team_b_name,
            prize=prize,
            start_time=start_time,
            rules=rules
        )
        await interaction.response.send_message(embed=view.embed(), view=view)
    except Exception:
        await fail(interaction)

bot.run(TOKEN)
