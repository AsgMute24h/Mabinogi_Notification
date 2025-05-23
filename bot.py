import discord
from discord.ext import commands, tasks
from discord.ui import View, Button
from datetime import datetime, timedelta
import asyncio
import os
import json
import pytz
from dotenv import load_dotenv
import keep_alive

# ====== 설정 로딩 ======
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
korea = pytz.timezone('Asia/Seoul')

# ====== 봇 초기화 ======
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# ====== 파일 저장 ======
DATA_FILE = "user_data.json"
CONFIG_FILE = "channel_config.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

def load_channel_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"alert": None, "homework": None}

def save_channel_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(channel_config, f, ensure_ascii=False, indent=2)

channel_config = load_channel_config()
user_data = load_data()

# ====== 숙제 설정 ======
count_tasks = {"검은 구멍": 3, "결계": 2}
binary_tasks = ["요일 던전", "심층 던전", "필드 보스", "어비스", "레이드", "보석 상자", "무료 상품"]
daily_tasks = ["요일 던전", "심층 던전", "검은 구멍", "결계"]
weekly_tasks = ["필드 보스", "어비스", "레이드"]
shop_tasks = ["보석 상자", "무료 상품"]

def get_default_characters():
    return ["두식", "호야", "냥이", "뽀뽀"]

def next_count(task, current):
    max_val = count_tasks[task]
    return max_val if current == 0 else current - 1

class TaskButton(Button):
    def __init__(self, user_id, char_name, task_name, is_counter=False):
        super().__init__(label=task_name, style=discord.ButtonStyle.primary)
        self.user_id = user_id
        self.char_name = char_name
        self.task_name = task_name
        self.is_counter = is_counter

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("본인의 숙제만 조작할 수 있습니다.", ephemeral=True)
            return

        char_data = user_data[self.user_id][self.char_name]
        if self.is_counter:
            current = char_data[self.task_name]
            char_data[self.task_name] = next_count(self.task_name, current)
        else:
            char_data[self.task_name] = not char_data[self.task_name]

        save_data()
        await interaction.response.edit_message(embed=generate_embed(self.user_id), view=generate_view(self.user_id))

def generate_embed(user_id):
    embed = discord.Embed(title="숙제 현황", description="각 캐릭터의 숙제 상태입니다.")
    for char_name, tasks in user_data[user_id].items():
        lines = []
        lines.append("[일간] " + " | ".join([
            f"{'✅' if tasks[t] else '❌'} {t}" for t in ["요일 던전", "심층 던전"]
        ] + [
            f"{tasks['검은 구멍']}/3 검은 구멍",
            f"{tasks['결계']}/2 결계"
        ]))
        lines.append("[주간] " + " | ".join([
            f"{'✅' if tasks[t] else '❌'} {t}" for t in weekly_tasks
        ]))
        lines.append("[구매] " + " | ".join([
            f"{'✅' if tasks[t] else '❌'} {t}" for t in shop_tasks
        ]))
        embed.add_field(name=f"ㅇ {char_name}", value="\n".join(lines), inline=False)
    return embed

def generate_view(user_id):
    view = View(timeout=None)
    for char_name in user_data[user_id]:
        for task in binary_tasks:
            view.add_item(TaskButton(user_id, char_name, task))
        for task in count_tasks:
            view.add_item(TaskButton(user_id, char_name, task, is_counter=True))
    return view

@bot.command()
async def 채널(ctx, 유형: str, 대상: discord.TextChannel = None):
    if 유형 not in ["알림", "숙제"]:
        await ctx.send("⚠️ 유형은 '알림' 또는 '숙제'만 가능합니다.", ephemeral=True)
        return

    if 대상 is None:
        target = channel_config["alert" if 유형 == "알림" else "homework"]
        if target:
            await ctx.send(f"현재 설정된 {유형} 채널: <#{target}>", ephemeral=True)
        else:
            await ctx.send(f"설정된 {유형} 채널이 없습니다.", ephemeral=True)
    else:
        if 유형 == "알림":
            channel_config["alert"] = 대상.id
        else:
            channel_config["homework"] = 대상.id
        save_channel_config()
        await ctx.send(f"✅ {유형} 채널이 <#{대상.id}>로 설정되었습니다.", ephemeral=True)

@bot.command()
async def 캐릭터(ctx, subcommand: str, *, 닉네임: str = None):
    uid = ctx.author.id
    if uid not in user_data:
        user_data[uid] = {name: {t: False for t in binary_tasks} | {t: count_tasks[t] for t in count_tasks} for name in get_default_characters()}

    if subcommand == "추가" and 닉네임:
        if 닉네임 in user_data[uid]:
            await ctx.send(f"이미 존재하는 캐릭터입니다: {닉네임}", ephemeral=True)
        else:
            user_data[uid][닉네임] = {t: False for t in binary_tasks} | {t: count_tasks[t] for t in count_tasks}
            save_data()
            await ctx.send(f"캐릭터 {닉네임} 추가 완료!", ephemeral=True)

    elif subcommand == "제거" and 닉네임:
        if 닉네임 in user_data[uid]:
            del user_data[uid][닉네임]
            save_data()
            await ctx.send(f"캐릭터 {닉네임} 제거 완료!", ephemeral=True)
        else:
            await ctx.send(f"존재하지 않는 캐릭터입니다: {닉네임}", ephemeral=True)

    elif subcommand == "목록":
        캐릭터들 = ", ".join(user_data[uid].keys())
        await ctx.send(f"현재 등록된 캐릭터: {캐릭터들}", ephemeral=True)

    else:
        await ctx.send("잘못된 명령어입니다. 사용 예: `/캐릭터 추가 닉네임`, `/캐릭터 제거 닉네임`, `/캐릭터 목록`", ephemeral=True)

@bot.command()
async def 숙제(ctx):
    if channel_config["homework"] and ctx.channel.id != channel_config["homework"]:
        await ctx.send("⚠️ 이 채널에서는 숙제 명령을 사용할 수 없습니다.", ephemeral=True)
        return

    uid = ctx.author.id
    if uid not in user_data:
        user_data[uid] = {name: {t: False for t in binary_tasks} | {t: count_tasks[t] for t in count_tasks} for name in get_default_characters()}

    embed = generate_embed(uid)
    view = generate_view(uid)
    await ctx.send(embed=embed, view=view, ephemeral=True)

@bot.command(name="test", aliases=["테스트"])
async def test(ctx):
    if ctx.channel.id == CHANNEL_ID:
        await ctx.send("@everyone [테스트 메시지] 지금은 테스트 중입니다!")
    else:
        await ctx.send("⚠️ 이 채널에서는 테스트 명령이 허용되지 않습니다.")

@tasks.loop(minutes=1)
async def reset_checker():
    now = datetime.utcnow() + timedelta(hours=9)
    if now.hour == 6 and now.minute == 0:
        for uid in user_data:
            for char in user_data[uid].values():
                for task in daily_tasks:
                    char[task] = False if task in binary_tasks else count_tasks[task]
                if now.weekday() == 1:
                    for task in weekly_tasks:
                        char[task] = False
        save_data()
        print("숙제 리셋 완료")

@tasks.loop(minutes=1)
async def notify_time():
    now = datetime.now(korea)
    hour = now.hour
    minute = now.minute
    if minute == 55:
        target_hour = (hour + 1) % 24
        channel = bot.get_channel(channel_config["alert"] if channel_config["alert"] else CHANNEL_ID)
        if not channel:
            print("[❌ 오류] 채널을 찾을 수 없음.")
            return

        group_a = set(range(24))
        group_b = {12, 18, 20, 22}

        if target_hour in group_a:
            await channel.send(f"@everyone 🔥 5분 뒤 {target_hour}시, 불길한 소환의 결계가 나타납니다.")
        if target_hour in group_b:
            await channel.send(f"@everyone ⚔️ 5분 뒤 {target_hour}시, 필드 보스가 출현합니다.")

@bot.event
async def on_ready():
    print(f"✅ {bot.user} 로 로그인됨")
    reset_checker.start()
    notify_time.start()

@bot.event
async def on_message(message):
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("⚠️ 해당 명령어를 찾을 수 없습니다.", ephemeral=True)
    else:
        raise error

keep_alive.keep_alive()
bot.run(TOKEN)
