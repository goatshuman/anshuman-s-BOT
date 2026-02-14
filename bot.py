import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import asyncio
import random
import requests
import io
from datetime import datetime, timedelta, timezone
from keep_alive import keep_alive

CYAN = 0x00E5FF
PREFIX = "$"
DATA_FILE = "data/users.json"
GUILD_ID = 1469337119582326886

FITNESS_CH = 1469378149526540530
READING_CH = 1469376564805369866
MEDITATION_CH = 1469376651879252059
RESULTS_CH = 1469378406582980850
STAFF_CH = 1469337120526303366
INTRODUCE_CH = 1471905738216444162
XP_CHANNELS = [FITNESS_CH, READING_CH, MEDITATION_CH, RESULTS_CH, STAFF_CH]

WELCOME_CH = 1469368246468612280
JOIN_ROLE = 1471905446150537435
VERIFIED_ROLE = 1469697770817585376
YOUTUBE_CH = 1469374072134570054
YT_CHANNEL_ID = "UCskSUo642Lbyy1E5wDHt5MA"

ACHIEVEMENT_CH = 1470771286278934640

# Support System Constants
SUPPORT_PANEL_CH = 1472203030576500849
TICKET_CATEGORY_ID = 1472203354926092411
TRANSCRIPT_CH = 1472204145615306895
SUPPORT_ROLES = [1472198495426318576, 1472197841169678540]

# Message Count Roles
MSG_ROLES = {
    1470767546277040229: 100,
    1470767759204810961: 1000,
    1470768063455690774: 5000,
    1470768181269500161: 10000
}

FIRST_STEP_ROLE = 1470768438132605072
READER_ROLE = 1470768616801697822
FOCUSED_MIND_ACH_ROLE = 1470768907487805543
PROOF_OF_WORK_ACH_ROLE = 1470768796800123055

# XP Milestone Roles
XP_MILESTONE_ROLES = {
    1470769036584292490: 250,
    1470769182340677773: 500,
    1470769296358772940: 1000
}

CHANNEL_ACHIEVEMENTS = {
    READING_CH: {"count": 100, "name": "Reader Achievement", "role_id": READER_ROLE}, 
    MEDITATION_CH: {"count": 100, "name": "Focused Mind", "role_id": FOCUSED_MIND_ACH_ROLE},
}

MOTIVATIONAL_QUOTES = [
    "The only bad workout is the one that didn't happen.",
    "Discipline is choosing between what you want now and what you want most.",
    "Success is the sum of small efforts, repeated day in and day out.",
    "Your only limit is your mind.",
    "Push yourself, because no one else is going to do it for you.",
    "Great things never come from comfort zones.",
    "Don't stop when you're tired. Stop when you're done.",
    "Wake up with determination. Go to bed with satisfaction.",
    "The harder you work, the luckier you get.",
    "Fall seven times, stand up eight.",
    "Believe you can and you're halfway there.",
    "It always seems impossible until it's done.",
    "Strive for progress, not perfection.",
    "You don't have to be extreme, just consistent.",
    "One day or day one. You decide.",
    "Small daily improvements are the key to staggering long-term results.",
    "Champions keep playing until they get it right.",
    "The pain you feel today will be the strength you feel tomorrow.",
    "Work hard in silence, let your success be the noise.",
    "Dream big. Start small. Act now."
]

active_focus_sessions = {}

def load_data():
    if not os.path.exists("data"):
        os.makedirs("data")
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f)
    with open(DATA_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return {}

def save_data(data):
    if not os.path.exists("data"):
        os.makedirs("data")
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user_data(data, user_id):
    uid = str(user_id)
    if uid not in data:
        data[uid] = {
            "xp": 0,
            "streak": 0,
            "daily": {},
            "last_active": None,
            "introduce": None,
            "checkins": [],
            "join_number": data.get("_meta", {}).get("total_members", 0) + 1,
            "total_messages": 0,
            "channel_messages": {},
            "wins": [],
            "focus_minutes": 0
        }
    return data[uid]

def make_embed(title, description, footer_extra=""):
    embed = discord.Embed(
        title=title,
        description=description,
        color=CYAN,
        timestamp=datetime.now(timezone.utc)
    )
    footer_text = "powered by anshuman"
    if footer_extra:
        footer_text = f"{footer_extra} | {footer_text}"
    embed.set_footer(text=footer_text)
    return embed

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Support System View
class SupportPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        
        # Check if user already has a ticket
        existing = discord.utils.get(category.text_channels, name=f"ticket-{interaction.user.name.lower()}")
        if existing:
            await interaction.response.send_message(f"You already have an open ticket: {existing.mention}", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        for role_id in SUPPORT_ROLES:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        ticket_channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        await interaction.response.send_message(f"Ticket created: {ticket_channel.mention}", ephemeral=True)
        
        role_mentions = " ".join([f"<@&{rid}>" for rid in SUPPORT_ROLES])
        embed = make_embed(
            "Support Ticket", 
            f"Hello {interaction.user.mention},\n\nSupport will be with you shortly. Please describe your issue in detail.\n\nUse `$close` to end this ticket."
        )
        await ticket_channel.send(content=f"{interaction.user.mention} {role_mentions}", embed=embed)

def calculate_score(u):
    xp = u.get("xp", 0)
    focus = u.get("focus_minutes", 0) * 2
    msg = u.get("total_messages", 0) / 10
    ach = len([k for k in u.get("channel_messages", {}).keys()]) * 50
    checkins = len(u.get("checkins", [])) * 10
    return xp + focus + msg + ach + checkins

async def update_level_roles(member, xp):
    guild = member.guild
    for role_id, threshold in XP_MILESTONE_ROLES.items():
        if xp >= threshold:
            role = guild.get_role(role_id)
            if role and role not in member.roles:
                try:
                    await member.add_roles(role)
                    await notify_achievement(member, role.name, role.mention)
                except: pass

async def notify_achievement(member, role_name, role_mention=None):
    try:
        channel = await bot.fetch_channel(ACHIEVEMENT_CH)
        if hasattr(channel, 'send'):
            mention = role_mention if role_mention else f"**{role_name}**"
            embed = make_embed(
                "Achievement Unlocked!", 
                f"Congratulations {member.mention}! You've earned the {mention} role!"
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(content=member.mention, embed=embed)
    except Exception as e:
        print(f"Achievement notify error: {e}")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    if not youtube_check.is_running():
        youtube_check.start()

    # Persist the support panel view
    bot.add_view(SupportPanel())

    # Send support panel if not exists
    data = load_data()
    channel = bot.get_channel(SUPPORT_PANEL_CH)
    if channel:
        # We'll just resend/update if the user wants it professional
        embed = make_embed(
            "Anshuman Support", 
            "Need help or have a question? Click the button below to open a private support ticket.\n\nOur staff team will assist you as soon as possible."
        )
        await channel.purge(limit=10) # Clean up old panel
        await channel.send(content="@everyone", embed=embed, view=SupportPanel())
        if "_meta" not in data: data["_meta"] = {}
        data["_meta"]["support_panel_sent"] = True
        save_data(data)

@bot.event
async def on_member_join(member):
    data = load_data()
    if "_meta" not in data:
        data["_meta"] = {"total_members": 0, "_last_video": None}
    data["_meta"]["total_members"] = data["_meta"].get("total_members", 0) + 1
    save_data(data)
    try:
        role = member.guild.get_role(JOIN_ROLE)
        if role: await member.add_roles(role)
    except: pass

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.mentions:
        for user in message.mentions:
            if user.id in active_focus_sessions:
                session = active_focus_sessions[user.id]
                remaining = session['end_time'] - datetime.now(timezone.utc)
                if remaining.total_seconds() > 0:
                    hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    time_str = f"{hours}h {minutes}m {seconds}s"
                    embed = make_embed("Locked In!", f"{user.mention} is currently locked in! Do not disturb.\n\n**Time Remaining:** {time_str}")
                    await message.channel.send(embed=embed)

    if message.channel.id == INTRODUCE_CH:
        if not message.interaction:
            try: await message.delete()
            except: pass
            return

    if len(message.content.strip()) < 3:
        await bot.process_commands(message)
        return

    data = load_data()
    uid = str(message.author.id)
    user = get_user_data(data, message.author.id)
    
    if user.get("total_messages", 0) == 0:
        member = message.guild.get_member(message.author.id) if message.guild else None
        if member:
            role = message.guild.get_role(FIRST_STEP_ROLE)
            if role:
                try:
                    await member.add_roles(role)
                    await notify_achievement(member, role.name, role.mention)
                except: pass

    user["total_messages"] = user.get("total_messages", 0) + 1
    ch_id = str(message.channel.id)
    channel_counts = user.get("channel_messages", {})
    channel_counts[ch_id] = channel_counts.get(ch_id, 0) + 1
    user["channel_messages"] = channel_counts
    save_data(data)

    member = message.author
    if isinstance(member, discord.Member):
        total_msg = user["total_messages"]
        for role_id, threshold in MSG_ROLES.items():
            if total_msg == threshold:
                role = message.guild.get_role(role_id)
                if role and role not in member.roles:
                    try:
                        await member.add_roles(role)
                        await notify_achievement(member, role.name, role.mention)
                    except: pass

        if message.channel.id in CHANNEL_ACHIEVEMENTS:
            ach = CHANNEL_ACHIEVEMENTS[message.channel.id]
            if channel_counts[ch_id] == ach["count"]:
                role = message.guild.get_role(ach["role_id"]) if ach.get("role_id") else None
                if role:
                    try:
                        await member.add_roles(role)
                        await notify_achievement(member, role.name, role.mention)
                    except: pass

    if message.channel.id in XP_CHANNELS:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if "daily" not in user: user["daily"] = {}
        if today not in user["daily"]: user["daily"][today] = False
        if user["daily"][today] is False:
            user["daily"][today] = True
            last_active = user.get("last_active")
            if last_active:
                yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
                if last_active == yesterday: user["streak"] = user.get("streak", 0) + 1
                elif last_active != today:
                    user["streak"] = 1
                    user["xp"] = 0 
            else: user["streak"] = 1
            user["xp"] = user.get("xp", 0) + 10
            user["last_active"] = today
            save_data(data)
            if isinstance(member, discord.Member): await update_level_roles(member, user["xp"])

    await bot.process_commands(message)

@bot.command(name="xp")
async def prefix_xp(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = load_data()
    user = get_user_data(data, target.id)
    embed = make_embed(f"{target.display_name}'s Stats", f"**XP:** {user.get('xp', 0)}\n**Streak:** {user.get('streak', 0)} day(s)")
    embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="xpguide")
@commands.has_permissions(administrator=True)
async def prefix_xpguide(ctx):
    desc = "**How XP works:**\n- Get 10 XP per day total for messaging in designated focus channels.\n- **STREAK RESET:** If you miss even 1 day without sending an XP-earning message, your streak resets to 1 and your XP resets to 0.\n\n**XP Roles:**\n"
    for role_id, threshold in XP_MILESTONE_ROLES.items():
        desc += f"- <@&{role_id}>: {threshold} XP\n"
    await ctx.send(embed=make_embed("XP Guide", desc))

@bot.command(name="info")
async def prefix_info(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = load_data()
    user = get_user_data(data, target.id)
    intro_text = "No introduction yet."
    if user.get("introduce"):
        intro = user["introduce"]
        intro_text = f"**Name:** {intro.get('name')}\n**Goals:** {intro.get('goals')}"
    achievement_roles = []
    ach_ids = list(MSG_ROLES.keys()) + [FIRST_STEP_ROLE, READER_ROLE, FOCUSED_MIND_ACH_ROLE, PROOF_OF_WORK_ACH_ROLE]
    for role in target.roles:
        if role.id in ach_ids: achievement_roles.append(role.mention)
    embed = make_embed(f"Info: {target.display_name}", f"**XP:** {user.get('xp')}\n**Streak:** {user.get('streak')} days\n**Total Messages:** {user.get('total_messages')}\n\n**Introduction:**\n{intro_text}\n\n**Achievements:**\n{', '.join(achievement_roles) if achievement_roles else 'None'}")
    embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="rank")
async def prefix_rank(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = load_data()
    user_list = [(uid, calculate_score(u)) for uid, u in data.items() if not uid.startswith("_")]
    user_list.sort(key=lambda x: x[1], reverse=True)
    rank = next((i + 1 for i, (uid, _) in enumerate(user_list) if int(uid) == target.id), "N/A")
    user_data = get_user_data(data, target.id)
    embed = make_embed(f"Rank: {target.display_name}", f"**Global Rank:** #{rank}\n**Total Score:** {int(calculate_score(user_data))}\n**XP:** {user_data.get('xp')}\n**Focus:** {user_data.get('focus_minutes')}m")
    embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="wins")
async def prefix_wins(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = load_data()
    user = get_user_data(data, target.id)
    wins = user.get("wins", [])
    desc = f"Total Wins: **{len(wins)}**\n\n"
    if wins:
        for i, win in enumerate(reversed(wins[-10:])): desc += f"**{i+1}.** {win.get('text')} ({win.get('date')})\n"
    else: desc += "No wins recorded yet."
    await ctx.send(embed=make_embed(f"Wins: {target.display_name}", desc.strip()))

@bot.command(name="checkin")
async def prefix_checkin_list(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = load_data()
    user = get_user_data(data, target.id)
    checkins = user.get("checkins", [])
    desc = f"Total Check-ins: **{len(checkins)}**\n\n"
    if checkins:
        for ci in reversed(checkins[-5:]): desc += f"{ci['date']}: {ci['message']}\n"
    else: desc += "No check-ins yet."
    await ctx.send(embed=make_embed(f"Check-ins: {target.display_name}", desc.strip()))

@bot.command(name="focus")
async def prefix_focus_stats(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = load_data()
    user = get_user_data(data, target.id)
    minutes = user.get("focus_minutes", 0)
    embed = make_embed(f"Focus Time: {target.display_name}", f"Total Lock-in Time: **{round(minutes/60, 2)} hours** ({minutes} minutes)")
    embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="clear")
@commands.has_permissions(administrator=True)
async def prefix_clear(ctx):
    await ctx.channel.purge()

@bot.command(name="commands")
async def prefix_commands(ctx):
    desc = "**Available Commands ($):**\n`$xp`, `$info`, `$rank`, `$wins`, `$checkin`, `$focus`, `$introduce`, `$leaderboard`, `$achievements`"
    await ctx.send(embed=make_embed("Anshuman Gang Commands", desc))

@bot.command(name="close")
async def close_ticket(ctx):
    if not ctx.channel.name.startswith("ticket-"):
        return

    # Permissions check: Only specific support roles can close
    member_roles = [r.id for r in ctx.author.roles]
    if not any(rid in SUPPORT_ROLES for rid in member_roles) and not ctx.author.guild_permissions.administrator:
        await ctx.send("Only support staff can close this ticket.", delete_after=5)
        return

    await ctx.send("Closing ticket and generating transcript...")
    
    # Generate Transcript
    messages = []
    async for msg in ctx.channel.history(limit=None, oldest_first=True):
        timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        messages.append(f"[{timestamp}] {msg.author}: {msg.content}")
    
    transcript_text = "\n".join(messages)
    file = discord.File(io.StringIO(transcript_text), filename=f"transcript-{ctx.channel.name}.txt")
    
    transcript_ch = bot.get_channel(TRANSCRIPT_CH)
    if transcript_ch:
        await transcript_ch.send(f"Transcript for {ctx.channel.name} closed by {ctx.author.mention}", file=file)
    
    await ctx.channel.delete()

@bot.command(name="leaderboard")
async def prefix_leaderboard(ctx):
    data = load_data()
    users = [(uid, calculate_score(u), u.get("xp", 0), u.get("focus_minutes", 0)) for uid, u in data.items() if not uid.startswith("_")]
    users.sort(key=lambda x: x[1], reverse=True)
    top_10 = users[:10]
    desc = "**Ranked by XP, Focus Time, and Discipline:**\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, s, xp, focus) in enumerate(top_10):
        prefix = medals[i] if i < 3 else f"**{i+1}.**"
        desc += f"{prefix} <@{uid}> — **{int(s)} Score** (XP: {xp} | Focus: {focus}m)\n"
    await ctx.send(embed=make_embed("Global Leaderboard", desc.strip()))

@bot.tree.command(name="checkin")
async def slash_checkin_simple(interaction: discord.Interaction):
    await interaction.response.send_message("Check-in recorded!", ephemeral=True)
    data = load_data()
    user = get_user_data(data, interaction.user.id)
    user["checkins"].append({"date": datetime.now(timezone.utc).strftime("%Y-%m-%d %I:%M %p"), "message": "Simple check-in"})
    save_data(data)

@bot.tree.command(name="wins")
@app_commands.describe(text="Describe your win")
async def slash_wins(interaction: discord.Interaction, text: str, image: discord.Attachment = None):
    data = load_data()
    user = get_user_data(data, interaction.user.id)
    user.setdefault("wins", []).append({"text": text, "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %I:%M %p"), "image": image.url if image else None})
    save_data(data)
    if interaction.channel_id == RESULTS_CH:
        member = interaction.guild.get_member(interaction.user.id)
        role = interaction.guild.get_role(PROOF_OF_WORK_ACH_ROLE)
        if member and role and role not in member.roles:
            try: await member.add_roles(role); await notify_achievement(member, role.name, role.mention)
            except: pass
    embed = make_embed("New Win!", f"{interaction.user.mention} just scored a win!\n\n> {text}")
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    if image: embed.set_image(url=image.url)
    await interaction.response.send_message(embed=embed)

class QuitFocusView(discord.ui.View):
    def __init__(self, user_id, start_time):
        super().__init__(timeout=None)
        self.user_id, self.start_time = user_id, start_time
    @discord.ui.button(label="Quit Lock-in", style=discord.ButtonStyle.danger)
    async def quit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id: return
        session = active_focus_sessions.pop(self.user_id, None)
        if not session: return
        guild = bot.get_guild(GUILD_ID)
        member = guild.get_member(self.user_id)
        if member:
            try: await member.edit(timed_out_until=None, nick=session['old_nick'])
            except: pass
        elapsed_min = int((datetime.now(timezone.utc) - self.start_time).total_seconds() / 60)
        data = load_data()
        user = get_user_data(data, self.user_id)
        user["focus_minutes"] = user.get("focus_minutes", 0) + elapsed_min
        save_data(data)
        await interaction.response.edit_message(embed=make_embed("Focus Ended", f"Ended early. Time: **{elapsed_min}m**."), view=None)

@bot.tree.command(name="focus")
@app_commands.describe(duration="Duration (e.g. 30 min, 1 hour)")
async def slash_focus(interaction: discord.Interaction, duration: str):
    parts = duration.lower().strip().split()
    try:
        val = int(parts[0])
        minutes = val * 60 if "hour" in (parts[1] if len(parts) > 1 else "min") or (parts[1] if len(parts) > 1 else "") == "h" else val
    except: await interaction.response.send_message("Invalid duration.", ephemeral=True); return
    if not (1 <= minutes <= 480): await interaction.response.send_message("Duration must be 1m-8h.", ephemeral=True); return
    member = interaction.guild.get_member(interaction.user.id)
    old_nick = member.display_name
    end_time = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    try: await member.edit(nick=f"[LOCKED IN] {old_nick}"[:32], timed_out_until=end_time)
    except: await interaction.response.send_message("Permission error. Ensure my role is higher.", ephemeral=True); return
    active_focus_sessions[member.id] = {"end_time": end_time, "old_nick": old_nick}
    await interaction.response.send_message(f"**LOCKED IN.** {member.mention} is focused for {minutes}m.")
    try: await member.send(embed=make_embed("Lock-in Started", f"Focused for **{minutes}m**."), view=QuitFocusView(member.id, datetime.now(timezone.utc)))
    except: pass
    await asyncio.sleep(minutes * 60)
    if member.id in active_focus_sessions:
        session = active_focus_sessions.pop(member.id)
        try: await member.edit(nick=session['old_nick'])
        except: pass
        data = load_data()
        user = get_user_data(data, member.id)
        user["focus_minutes"] = user.get("focus_minutes", 0) + minutes
        save_data(data)

@bot.tree.command(name="introduce")
@app_commands.describe(name="Your name", age="Age", location="Location", goals="Goals")
async def slash_introduce(interaction: discord.Interaction, name: str, age: int, location: str, goals: str, picture: discord.Attachment = None):
    if interaction.channel_id != INTRODUCE_CH: await interaction.response.send_message(f"Use <#{INTRODUCE_CH}>", ephemeral=True); return
    data = load_data()
    user = get_user_data(data, interaction.user.id)
    user["introduce"] = {"name": name, "age": age, "location": location, "goals": goals, "picture": picture.url if picture else None}
    save_data(data)
    member = interaction.guild.get_member(interaction.user.id)
    if member:
        try:
            await member.add_roles(interaction.guild.get_role(VERIFIED_ROLE))
            await member.remove_roles(interaction.guild.get_role(JOIN_ROLE))
            channel = await bot.fetch_channel(WELCOME_CH)
            quote = random.choice(MOTIVATIONAL_QUOTES)
            embed = make_embed("Welcome", f"Welcome {member.mention}\n\n> *\"{quote}\"*\n\nYou are member **#{user['join_number']}**")
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)
        except: pass
    embed = make_embed("Introduction", f"**Name:** {name}\n**Age:** {age}\n**Location:** {location}\n**Goals:** {goals}")
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    if picture: embed.set_image(url=picture.url)
    await interaction.response.send_message(embed=embed)

def get_uploads_playlist_id():
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key: return None
    url = f"https://www.googleapis.com/youtube/v3/channels?part=contentDetails&id={YT_CHANNEL_ID}&key={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get("items"): return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    except: pass
    return None

def get_latest_video(playlist_id):
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key or not playlist_id: return None
    url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=1&playlistId={playlist_id}&key={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get("items"):
            snippet = data["items"][0]["snippet"]
            video_id = snippet["resourceId"]["videoId"]
            return {"video_id": video_id, "title": snippet["title"], "thumbnail": snippet["thumbnails"].get("high", {}).get("url", ""), "url": f"https://www.youtube.com/watch?v={video_id}"}
    except: pass
    return None

@tasks.loop(seconds=30)
async def youtube_check():
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key: return
    data = load_data()
    if "_meta" not in data: data["_meta"] = {"total_members": 0, "_last_video": None}
    playlist_id = get_uploads_playlist_id()
    if not playlist_id: return
    video = get_latest_video(playlist_id)
    if not video or data["_meta"].get("_last_video") == video["video_id"]: return
    data["_meta"]["_last_video"] = video["video_id"]
    save_data(data)
    try:
        channel = await bot.fetch_channel(YOUTUBE_CH)
        if hasattr(channel, 'send'):
            embed = make_embed(video['title'], f"[Click here to watch]({video['url']})")
            if video["thumbnail"]: embed.set_image(url=video["thumbnail"])
            await channel.send(content="@everyone New video dropped!", embed=embed, allowed_mentions=discord.AllowedMentions(everyone=True))
    except: pass

@youtube_check.before_loop
async def before_youtube_check(): await bot.wait_until_ready()

keep_alive()
bot.run(os.getenv("BOT_TOKEN", ""))
