
import os, json, asyncio, re, feedparser
from datetime import datetime
import discord
from discord.ext import commands, tasks
from keep_alive import keep_alive

BOT_TOKEN = os.getenv("BOT_TOKEN")
CYAN = 0x00E5FF

WELCOME_CH = 1469368246468612280
YOUTUBE_CH = 1469374072134570054
FITNESS_CH = 1469378149526540530
READING_CH = 1469376564805369866
MEDITATION_CH = 1469376651879252059
RESULTS_CH = 1469378406582980850
ACHIEVEMENT_CH = 1470771286278934640

AUTO_MEMBER_ROLE = 1469697770817585376
FOCUS_ROLE = 1469680976992014438

ROLES = {
 "beginner":1470767546277040229,
 "consistent":1470767759204810961,
 "disciplined":1470768063455690774,
 "elite":1470768181269500161,
 "on_fire":1470769036584292490,
 "unstoppable":1470769182340677773,
 "no_excuses":1470769296358772940,
 "first_step":1470768438132605072,
 "reader":1470768616801697822,
 "proof":1470768796800123055,
 "focused":1470768907487805543
}

DATA_PATH = "data/users.json"
YT_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id="
YT_CHANNEL_ID = None

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents)

def load():
    if not os.path.exists(DATA_PATH): return {}
    return json.load(open(DATA_PATH))

def save(d): json.dump(d, open(DATA_PATH,"w"), indent=2)

def user(d, uid):
    return d.setdefault(str(uid), {"introduce":None,"goals":None,"habits":None,"checkins":[],"wins":[],"xp":0,"streak":0,"last_day":None,"daily":{},"ach":[]})

def parse_time(text):
    text=text.lower()
    h=re.search(r"(\d+)\s*(h|hr|hour)",text)
    m=re.search(r"(\d+)\s*(m|min|minute)",text)
    if h: return int(h.group(1))*60
    if m: return int(m.group(1))
    return None

def level_from_xp(xp):
    if xp>=2000: return "elite"
    if xp>=800: return "disciplined"
    if xp>=300: return "consistent"
    return "beginner"

async def update_level(member, lvl):
    for k in ["beginner","consistent","disciplined","elite"]:
        r = member.guild.get_role(ROLES[k])
        if r and r in member.roles:
            await member.remove_roles(r)
    await member.add_roles(member.guild.get_role(ROLES[lvl]))

async def announce(guild, text):
    ch = guild.get_channel(ACHIEVEMENT_CH)
    if ch: await ch.send(embed=discord.Embed(description=text, color=CYAN))

@bot.event
async def on_ready():
    print("MERGED BOT ONLINE")
    youtube_check.start()

@bot.event
async def on_member_join(member):
    r = member.guild.get_role(AUTO_MEMBER_ROLE)
    if r: await member.add_roles(r)
    ch = member.guild.get_channel(WELCOME_CH)
    if ch:
        e=discord.Embed(title="Welcome", description=f"Welcome {member.mention}!", color=CYAN)
        e.set_thumbnail(url=member.display_avatar.url)
        await ch.send(embed=e)

@bot.event
async def on_message(m):
    if m.author.bot: return
    d=load(); u=user(d,m.author.id)
    today=str(datetime.utcnow().date())

    if m.channel.id in [FITNESS_CH,READING_CH,MEDITATION_CH,RESULTS_CH]:
        if u["daily"].get(str(m.channel.id))!=today:
            u["xp"]+=10; u["daily"][str(m.channel.id)]=today
        if u["last_day"]!=today:
            u["streak"]+=1; u["last_day"]=today

        if m.channel.id==READING_CH and "reader" not in u["ach"]:
            u["ach"].append("reader")
            await m.author.add_roles(m.guild.get_role(ROLES["reader"]))
            await announce(m.guild,f"📚 {m.author.mention} unlocked **Reader**")

        if m.channel.id==MEDITATION_CH and "focused" not in u["ach"]:
            u["ach"].append("focused")
            await m.author.add_roles(m.guild.get_role(ROLES["focused"]))
            await announce(m.guild,f"🧠 {m.author.mention} unlocked **Focused Mind**")

        await update_level(m.author, level_from_xp(u["xp"]))

    save(d)
    await bot.process_commands(m)

@bot.tree.command(name="introduce")
async def introduce(i:discord.Interaction, name:str, age:int, location:str, goals:str, picture:discord.Attachment=None):
    d=load(); u=user(d,i.user.id)
    u["introduce"]={"name":name,"age":age,"location":location,"goals":goals,"picture":picture.url if picture else None}
    save(d)
    e=discord.Embed(title="Introduction", color=CYAN)
    e.add_field(name="Name", value=name)
    e.add_field(name="Age", value=age)
    e.add_field(name="Location", value=location)
    e.add_field(name="Goals", value=goals, inline=False)
    if picture: e.set_image(url=picture.url)
    await i.response.send_message(embed=e)

@bot.tree.command(name="goals")
async def set_goals(i:discord.Interaction, goals:str):
    d=load(); u=user(d,i.user.id); u["goals"]=goals; save(d)
    await i.response.send_message(embed=discord.Embed(description=goals, color=CYAN))

@bot.tree.command(name="habits")
async def set_habits(i:discord.Interaction, habits:str):
    d=load(); u=user(d,i.user.id); u["habits"]=habits; save(d)
    await i.response.send_message(embed=discord.Embed(description=habits, color=CYAN))

@bot.tree.command(name="checkin")
async def checkin(i:discord.Interaction, text:str):
    d=load(); u=user(d,i.user.id); u["checkins"].append({"date":str(datetime.utcnow().date()),"text":text}); save(d)
    await i.response.send_message(embed=discord.Embed(description=text, color=CYAN))

@bot.tree.command(name="wins")
async def wins(i:discord.Interaction, text:str, image:discord.Attachment=None):
    d=load(); u=user(d,i.user.id)
    u["wins"].append({"date":str(datetime.utcnow().date()),"text":text,"image":image.url if image else None})
    if "proof" not in u["ach"]:
        u["ach"].append("proof")
        await i.user.add_roles(i.guild.get_role(ROLES["proof"]))
        await announce(i.guild,f"🏆 {i.user.mention} unlocked **Proof of Work**")
    save(d)
    e=discord.Embed(description=text, color=CYAN)
    if image: e.set_image(url=image.url)
    await i.response.send_message(embed=e)

@bot.tree.command(name="focus")
async def focus(i:discord.Interaction, duration:str):
    mins=parse_time(duration)
    if not mins:
        await i.response.send_message(embed=discord.Embed(description="Invalid time", color=CYAN))
        return
    role=i.guild.get_role(FOCUS_ROLE)
    if role: await i.user.add_roles(role)
    await i.response.send_message(embed=discord.Embed(description=f"Lock-in for {mins} minutes.", color=CYAN))
    await asyncio.sleep(mins*60)
    if role: await i.user.remove_roles(role)
    try: await i.user.send("Lock-in complete. Take some rest.")
    except: pass

@bot.command()
async def profile(ctx, member:discord.Member=None):
    m=member or ctx.author; d=load(); u=user(d,m.id)
    e=discord.Embed(title=f"Profile – {m.name}", color=CYAN)
    e.add_field(name="XP", value=u["xp"])
    e.add_field(name="Streak", value=u["streak"])
    e.add_field(name="Achievements", value=", ".join(u["ach"]) or "None", inline=False)
    await ctx.send(embed=e)

@bot.command()
async def leaderboard(ctx):
    d=load(); top=sorted(d.items(), key=lambda x:x[1]["xp"], reverse=True)[:10]
    desc="".join([f"**{i+1}.** <@{uid}> – {u['xp']} XP\n" for i,(uid,u) in enumerate(top)])
    await ctx.send(embed=discord.Embed(title="Leaderboard", description=desc, color=CYAN))

@tasks.loop(minutes=10)
async def youtube_check():
    global YT_CHANNEL_ID
    d=load(); last=d.get("_last_video")
    if not YT_CHANNEL_ID:
        feed=feedparser.parse("https://www.youtube.com/@anshuman.improves")
        if feed.feed.get("yt_channelid"): YT_CHANNEL_ID=feed.feed.yt_channelid
        else: return
    feed=feedparser.parse("https://www.youtube.com/feeds/videos.xml?channel_id="+YT_CHANNEL_ID)
    if not feed.entries: return
    latest=feed.entries[0]
    if latest.id==last: return
    d["_last_video"]=latest.id; save(d)
    ch=bot.get_channel(YOUTUBE_CH)
    if ch:
        e=discord.Embed(title=latest.title, url=latest.link, description="New video is live 🎥", color=CYAN)
        if latest.media_thumbnail: e.set_image(url=latest.media_thumbnail[0]['url'])
        await ch.send(embed=e)

keep_alive()
bot.run(BOT_TOKEN)
