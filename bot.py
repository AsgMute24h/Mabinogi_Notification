import discord
from discord.ext import tasks
from discord.ui import View, Button
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import os
import json
import pytz
from dotenv import load_dotenv
import keep_alive

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
korea = pytz.timezone('Asia/Seoul')

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

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

        if self.user_id not in user_data or self.char_name not in user_data[self.user_id]:
            await interaction.response.send_message("❌ 이 캐릭터는 삭제되었거나 존재하지 않습니다. `/숙제`를 다시 입력해 주세요.", ephemeral=True)
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
    today = datetime.now(korea)
    date_str = today.strftime("[%Y/%m/%d %A]").replace("Monday", "월요일").replace("Tuesday", "화요일").replace("Wednesday", "수요일").replace("Thursday", "목요일").replace("Friday", "금요일").replace("Saturday", "토요일").replace("Sunday", "일요일")
    embed = discord.Embed(title="숙제 현황", description=f"{date_str}\n각 캐릭터의 숙제 상태입니다.")
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
        embed.add_field(name=f"ㅇ {char_name}", value="
"".join(lines), inline=False)

    # 계정 통합 항목은 맨 아래에 한 번만 표시
    if user_data[user_id]:
        first_char = next(iter(user_data[user_id].values()))
        shop_line = "[구매] " + " | ".join([
            f"{'✅' if first_char[t] else '❌'} {t}" for t in shop_tasks
        ])
        embed.add_field(name="📦 계정 공통", value=shop_line, inline=False)
".join(lines), inline=False)
    return embed

def generate_view(user_id):
    view = View(timeout=None)
    for char_name in user_data[user_id]:
        for task in binary_tasks:
            view.add_item(TaskButton(user_id, char_name, task))
        for task in count_tasks:
            view.add_item(TaskButton(user_id, char_name, task, is_counter=True))
    return view

@tree.command(name="채널", description="알림 또는 숙제 채널을 설정합니다.")
@app_commands.describe(유형="알림 또는 숙제", 대상="지정할 텍스트 채널")
async def 채널(interaction: discord.Interaction, 유형: str, 대상: discord.TextChannel):
    if 유형 not in ["알림", "숙제"]:
        await interaction.response.send_message("⚠️ 유형은 '알림' 또는 '숙제'만 가능합니다.", ephemeral=True)
        return
    if 유형 == "알림":
        channel_config["alert"] = 대상.id
    else:
        channel_config["homework"] = 대상.id
    save_channel_config()
    await interaction.response.send_message(f"✅ {유형} 채널이 <#{대상.id}>로 설정되었습니다.", ephemeral=True)

@tree.command(name="캐릭터", description="캐릭터를 추가하거나 제거하거나 목록을 확인합니다.")
@app_commands.describe(subcommand="추가, 제거 또는 목록", 닉네임="캐릭터 닉네임 (목록일 경우 생략 가능)")
async def 캐릭터(interaction: discord.Interaction, subcommand: str, 닉네임: str = None):
    uid = interaction.user.id
    if uid not in user_data:
        user_data[uid] = {name: {t: False for t in binary_tasks} | {t: count_tasks[t] for t in count_tasks} for name in get_default_characters()}
    if subcommand == "추가":
        if 닉네임 in user_data[uid]:
            await interaction.response.send_message(f"이미 존재하는 캐릭터입니다: {닉네임}", ephemeral=True)
        else:
            user_data[uid][닉네임] = {t: False for t in binary_tasks} | {t: count_tasks[t] for t in count_tasks}
            save_data()
            embed = generate_embed(uid)
            view = generate_view(uid)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    elif subcommand == "제거":
        if 닉네임 in user_data[uid]:
            del user_data[uid][닉네임]
            save_data()
            embed = generate_embed(uid)
            view = generate_view(uid)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(f"존재하지 않는 캐릭터입니다: {닉네임}", ephemeral=True)
    elif subcommand == "목록":
        if uid not in user_data or not user_data[uid]:
            await interaction.response.send_message("❌ 등록된 캐릭터가 없습니다.", ephemeral=True)
        else:
            char_list = "
".join(f"- {name}" for name in user_data[uid].keys())
            await interaction.response.send_message(f"📋 현재 등록된 캐릭터 목록:
{char_list}", ephemeral=True)
    else:
        await interaction.response.send_message("서브 명령어는 '추가', '제거', 또는 '목록'만 가능합니다.", ephemeral=True)

@tree.command(name="숙제", description="숙제 현황을 표시합니다.")
async def 숙제(interaction: discord.Interaction):
    try:
        if channel_config["homework"] and interaction.channel.id != channel_config["homework"]:
            await interaction.response.send_message("⚠️ 이 채널에서는 숙제 명령을 사용할 수 없습니다.", ephemeral=True)
            return

        uid = interaction.user.id
        if uid not in user_data:
            user_data[uid] = {name: {t: False for t in binary_tasks} | {t: count_tasks[t] for t in count_tasks} for name in get_default_characters()}

        embed = generate_embed(uid)
        view = generate_view(uid)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message("❌ 오류가 발생했습니다. 로그를 확인해 주세요.", ephemeral=True)
        print(f"[숙제 오류] {e}")

@tasks.loop(minutes=1)
async def reset_checker():
    now = datetime.utcnow() + timedelta(hours=9)
    if now.hour == 6 and now.minute == 0:
        for uid in user_data:
            for char in user_data[uid].values():
                for task in daily_tasks:
                    char[task] = False if task in binary_tasks else count_tasks[task]
                for task in shop_tasks:
                    char[task] = False
                if now.weekday() == 1:
                    for task in weekly_tasks:
                        char[task] = False
        save_data()
        print("숙제 리셋 완료")

        channel = bot.get_channel(channel_config["homework"])
        if channel:
            for uid in user_data:
                try:
                    embed = generate_embed(uid)
                    await channel.send(embed=embed, ephemeral=True)
                except Exception as e:
                    print(f"[숙제 리셋 전송 실패] {uid}: {e}")

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
    await tree.sync()
    print(f"✅ {bot.user} 로 로그인됨")
    reset_checker.start()
    notify_time.start()

keep_alive.keep_alive()
bot.run(TOKEN)
