import os
import json
import asyncio
import re
import requests
from datetime import datetime

import discord
from discord.ext import commands, tasks
from keep_alive import keep_alive

# ================= ENV =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

CYAN = 0x00E5FF
DATA_PATH = "data/users.json"

# ================= CHANNEL IDS =================

WELCOME_CH = 1469368246468612280
YOUTUBE_CH = 1469374072134570054
ACHIEVEMENT_CH = 1470771286278934640

FITNESS_CH = 1469378149526540530
READING_CH = 1469376564805369866
MEDITATION_CH = 1469376651879252059
RESULTS_CH = 1469378406582980850
STAFF_CH = 1469337120526303366

XP_CHANNELS = [
    FITNESS_CH,
    READING_CH,
    MEDITATION_CH,
    RESULTS_CH,
    STAFF_CH
]

# ================= ROLE IDS =================

AUTO_MEMBER_ROLE = 1469697770817585376
FOCUS_ROLE = 1469680976992014438

ROLES = {
    "beginner": 1470767546277040229,
    "consistent": 1470767759204810961,
    "disciplined": 1470768063455690774,
    "elite": 1470768181269500161,
    "reader": 1470768616801697822,
    "focused": 1470768907487805543,
    "proof": 1470768796800123055
}

# ================= YOUTUBE =================

YOUTUBE_CHANNEL_ID = "UCtHcUANC5lCC9E-HbXRq7Eg"

# ================= BOT SETUP =================

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="$", intents=intents)

# ================= DATA =================

def load_data():
    if not os.path.exists(DATA_PATH):
        return {}
    with open(DATA_PATH, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2)

def get_user(data, uid):
    return data.setdefault(str(uid), {
        "xp": 0,
        "streak": 0,
        "last_day": None,
        "daily": {},
        "achievements": [],
        "wins": [],
        "intro": None,
        "checkins": []
    })

# ================= UTIL =================

def parse_time(text):
    text = text.lower()
    h = re.search(r"(\d+)\s*(h|hr|hour)", text)
    m = re.search(r"(\d+)\s*(m|min|minute)", text)
    if h:
        return int(h.group(1)) * 60
    if m:
        return int(m.group(1))
    return None

def level_from_xp(xp):
    if xp >= 2000:
        return "elite"
    if xp >= 800:
        return "disciplined"
    if xp >= 300:
        return "consistent"
    return "beginner"

async def update_level(member, lvl):
    for r in ["beginner", "consistent", "disciplined", "elite"]:
        role = member.guild.get_role(ROLES[r])
        if role and role in member.roles:
            await member.remove_roles(role)
    await member.add_roles(member.guild.get_role(ROLES[lvl]))

async def announce(guild, text):
    ch = guild.get_channel(ACHIEVEMENT_CH)
    if ch:
        await ch.send(embed=discord.Embed(description=text, color=CYAN))

# ================= READY =================

@bot.event
async def on_ready():
    print("BOT ONLINE")
    await bot.tree.sync()
    print("Slash commands synced")
    youtube_check.start()

# ================= MEMBER JOIN =================

@bot.event
async def on_member_join(member):
    role = member.guild.get_role(AUTO_MEMBER_ROLE)
    if role:
        await member.add_roles(role)

    ch = member.guild.get_channel(WELCOME_CH)
    if ch:
        embed = discord.Embed(
            title="Welcome",
            description=f"Welcome {member.mention}",
            color=CYAN
        )
        await ch.send(embed=embed)

# ================= XP SYSTEM =================

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    data = load_data()
    user = get_user(data, message.author.id)
    today = str(datetime.utcnow().date())

    if message.channel.id in XP_CHANNELS:
        if user["daily"].get(str(message.channel.id)) != today:
            user["xp"] += 10
            user["daily"][str(message.channel.id)] = today

        if user["last_day"] != today:
            user["streak"] += 1
            user["last_day"] = today

        await update_level(message.author, level_from_xp(user["xp"]))

    save_data(data)
    await bot.process_commands(message)

# ================= INTRODUCE =================

@bot.tree.command(name="introduce")
async def introduce(
    interaction: discord.Interaction,
    name: str,
    age: int,
    location: str,
    goals: str,
    picture: discord.Attachment = None
):
    data = load_data()
    user = get_user(data, interaction.user.id)

    user["intro"] = {
        "name": name,
        "age": age,
        "location": location,
        "goals": goals,
        "picture": picture.url if picture else None
    }

    save_data(data)

    embed = discord.Embed(title=f"{name}'s Introduction", color=CYAN)
    embed.add_field(name="Age", value=age)
    embed.add_field(name="Location", value=location)
    embed.add_field(name="Goals", value=goals, inline=False)

    if picture:
        embed.set_image(url=picture.url)

    await interaction.response.send_message(embed=embed)

@bot.command()
async def introduce(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = load_data()

    user_data = data.get(str(target.id))
    if not user_data or not user_data.get("intro"):
        await ctx.send(embed=discord.Embed(
            description="User has not introduced themselves yet.",
            color=CYAN
        ))
        return

    intro = user_data["intro"]

    embed = discord.Embed(title=f"{intro['name']}'s Introduction", color=CYAN)
    embed.add_field(name="Age", value=intro["age"])
    embed.add_field(name="Location", value=intro["location"])
    embed.add_field(name="Goals", value=intro["goals"], inline=False)

    if intro["picture"]:
        embed.set_image(url=intro["picture"])

    await ctx.send(embed=embed)

# ================= CHECKIN =================

@bot.tree.command(name="checkin")
async def checkin(interaction: discord.Interaction, message: str):
    data = load_data()
    user = get_user(data, interaction.user.id)

    entry = {
        "date": str(datetime.utcnow().date()),
        "message": message
    }

    user["checkins"].append(entry)
    save_data(data)

    embed = discord.Embed(
        title="Check-in Recorded",
        description=message,
        color=CYAN
    )

    await interaction.response.send_message(embed=embed)

@bot.command()
async def checkin(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = load_data()

    user_data = data.get(str(target.id))
    if not user_data or not user_data.get("checkins"):
        await ctx.send(embed=discord.Embed(
            description="No check-ins found.",
            color=CYAN
        ))
        return

    recent = user_data["checkins"][-5:]
    desc = ""

    for entry in recent:
        desc += f"**{entry['date']}** — {entry['message']}\n"

    embed = discord.Embed(
        title=f"{target.name}'s Check-ins",
        description=desc,
        color=CYAN
    )

    await ctx.send(embed=embed)

# ================= PROFILE =================

@bot.command()
async def profile(ctx, member: discord.Member = None):
    m = member or ctx.author
    data = load_data()
    u = get_user(data, m.id)

    embed = discord.Embed(title=f"{m.name}'s Profile", color=CYAN)
    embed.add_field(name="XP", value=u["xp"])
    embed.add_field(name="Streak", value=u["streak"])
    embed.add_field(name="Total Check-ins", value=len(u["checkins"]))

    await ctx.send(embed=embed)

@bot.command()
async def leaderboard(ctx):
    data = load_data()
    top = sorted(data.items(), key=lambda x: x[1]["xp"], reverse=True)[:10]

    desc = ""
    for i, (uid, u) in enumerate(top, 1):
        desc += f"**{i}.** <@{uid}> – {u['xp']} XP\n"

    await ctx.send(embed=discord.Embed(title="Leaderboard", description=desc, color=CYAN))

# ================= YOUTUBE =================

@tasks.loop(seconds=30)
async def youtube_check():
    if not YOUTUBE_API_KEY:
        return

    data = load_data()
    last_video = data.get("_last_video")

    ch_url = (
        "https://www.googleapis.com/youtube/v3/channels"
        f"?part=contentDetails&id={YOUTUBE_CHANNEL_ID}&key={YOUTUBE_API_KEY}"
    )
    ch_res = requests.get(ch_url)
    if ch_res.status_code != 200:
        return

    uploads_id = ch_res.json()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    pl_url = (
        "https://www.googleapis.com/youtube/v3/playlistItems"
        f"?part=snippet&playlistId={uploads_id}&maxResults=1&key={YOUTUBE_API_KEY}"
    )
    pl_res = requests.get(pl_url)
    if pl_res.status_code != 200:
        return

    item = pl_res.json()["items"][0]
    video_id = item["snippet"]["resourceId"]["videoId"]

    if video_id == last_video:
        return

    data["_last_video"] = video_id
    save_data(data)

    title = item["snippet"]["title"]
    thumb = item["snippet"]["thumbnails"]["high"]["url"]
    link = f"https://www.youtube.com/watch?v={video_id}"

    channel = await bot.fetch_channel(YOUTUBE_CH)

    embed = discord.Embed(
        title=title,
        url=link,
        description="New video is live 🎥",
        color=CYAN
    )
    embed.set_image(url=thumb)

    await channel.send(
        content="@everyone",
        embed=embed,
        allowed_mentions=discord.AllowedMentions(everyone=True)
    )

# ================= START =================

keep_alive()
bot.run(BOT_TOKEN)
