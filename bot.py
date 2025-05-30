import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button
from datetime import datetime
import os
import json
import pytz
from dotenv import load_dotenv
from keep_alive import keep_alive
import psycopg2
import asyncio

# 🌟 환경설정 및 DB 연결
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
GUILD_ID = int(os.getenv("GUILD_ID"))
korea = pytz.timezone('Asia/Seoul')

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def create_table():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_data (
                    user_id BIGINT PRIMARY KEY,
                    data JSONB NOT NULL
                );
            """)
        conn.commit()

def load_all_user_data():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, data FROM user_data;")
            rows = cur.fetchall()
            return {str(row[0]): row[1] for row in rows}

def save_user_data(user_id, data):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_data (user_id, data)
                VALUES (%s, %s)
                ON CONFLICT (user_id)
                DO UPDATE SET data = EXCLUDED.data;
            """, (user_id, json.dumps(data, ensure_ascii=False)))
        conn.commit()

# 🌟 채널 설정 파일
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "channel_config.json")
def load_channel_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_channel_config():
    global channel_config
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(channel_config, f, ensure_ascii=False, indent=2)

channel_config = load_channel_config()

# 🌟 디스코드 봇 설정
keep_alive()
os.environ["TZ"] = "Asia/Seoul"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

binary_tasks = ["요일 던전", "심층 던전", "필드 보스", "어비스", "레이드", "보석 상자", "무료 상품"]
count_tasks = {"검은 구멍": 3, "결계": 2}
daily_tasks = ["요일 던전", "심층 던전", "검은 구멍", "결계"]
weekly_tasks = ["필드 보스", "어비스", "레이드"]
shop_tasks = ["보석 상자", "무료 상품"]

async def safe_send(interaction: discord.Interaction, content=None, **kwargs):
    try:
        await interaction.response.send_message(content=content, **kwargs)
    except discord.errors.NotFound:
        try:
            await interaction.edit_original_response(content=content, **kwargs)
        except Exception as e:
            print(f"[safe_send 오류] {e}")

def get_task_status_display(char_data):
    def checkbox(val): return "☑" if val else "☐"
    daily = (
        f"  {checkbox(char_data['요일 던전'])} 요일 던전     {checkbox(char_data['필드 보스'])} 필드 보스\n"
        f"  {checkbox(char_data['심층 던전'])} 심층 던전     {checkbox(char_data['어비스'])} 어비스 \n"
        f"  검은 구멍 {char_data['검은 구멍']}/3   {checkbox(char_data['레이드'])} 레이드\n"
        f"  결계 {char_data['결계']}/2"
    )
    shop = f"    {checkbox(char_data['보석 상자'])} 보석 상자 　{checkbox(char_data['무료 상품'])} 무료 상품"
    return (
        "```\n"
        "┌─────────────┐┌─────────────┐\n"
        f"{daily}\n"
        "└─────────────┘└─────────────┘\n"
        "┌────────────────────────────┐\n"
        f"{shop}\n"
        "└────────────────────────────┘\n"
        "```"
    )

# 캐릭터 숙제 관리 명령어
@tree.command(name="추가", description="캐릭터를 추가합니다.")
@app_commands.describe(닉네임="추가할 캐릭터 이름")
async def 추가(interaction: discord.Interaction, 닉네임: str):
    uid = str(interaction.user.id)
    user_data = load_all_user_data()
    if uid not in user_data:
        user_data[uid] = {}
    if 닉네임 in user_data[uid]:
        await safe_send(interaction, f"이미 존재하는 캐릭터입니다: {닉네임}", ephemeral=True)
    else:
        user_data[uid][닉네임] = {t: False for t in binary_tasks} | count_tasks.copy()
        save_user_data(uid, user_data[uid])
        await safe_send(interaction, f"✅ {닉네임} 캐릭터를 추가했습니다.", ephemeral=True)

@tree.command(name="제거", description="캐릭터를 제거합니다.")
@app_commands.describe(닉네임="제거할 캐릭터 이름")
async def 제거(interaction: discord.Interaction, 닉네임: str):
    uid = str(interaction.user.id)
    user_data = load_all_user_data()
    if uid in user_data and 닉네임 in user_data[uid]:
        del user_data[uid][닉네임]
        save_user_data(uid, user_data[uid])
        await safe_send(interaction, f"🗑️ {닉네임} 캐릭터를 제거했습니다.", ephemeral=True)
    else:
        await safe_send(interaction, f"❌ 존재하지 않는 캐릭터입니다: {닉네임}", ephemeral=True)

@tree.command(name="목록", description="등록된 캐릭터 목록을 확인합니다.")
async def 목록(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    user_data = load_all_user_data()
    if uid not in user_data or not user_data[uid]:
        await safe_send(interaction, "❌ 등록된 캐릭터가 없습니다.", ephemeral=True)
    else:
        char_list = "\n".join(f"- {name}" for name in user_data[uid])
        await safe_send(interaction, f"📋 현재 등록된 캐릭터 목록:\n{char_list}", ephemeral=True)

@tree.command(name="숙제", description="숙제 현황을 확인합니다.")
async def 숙제(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    user_data = load_all_user_data()
    if uid not in user_data or not user_data[uid]:
        await safe_send(interaction, "❌ 등록된 캐릭터가 없습니다. `/추가`로 먼저 등록하세요!", ephemeral=True)
    else:
        current_char = list(user_data[uid].keys())[0]
        desc = get_task_status_display(user_data[uid][current_char])
        await safe_send(interaction, f"[{datetime.now(korea).strftime('%Y/%m/%d')}] {current_char}\n{desc}", ephemeral=True)

# 채널 설정 명령어
@tree.command(name="채널", description="알림 또는 숙제 채널을 설정합니다.")
@app_commands.describe(유형="알림 또는 숙제", 대상="지정할 텍스트 채널")
async def 채널(interaction: discord.Interaction, 유형: str, 대상: discord.TextChannel):
    global channel_config
    if 유형 not in ["알림", "숙제"]:
        await safe_send(interaction, "❌ 유형은 '알림' 또는 '숙제'만 가능합니다.", ephemeral=True)
        return
    channel_config[유형] = 대상.id
    save_channel_config()
    await safe_send(interaction, f"✅ {유형} 채널이 <#{대상.id}>로 설정되었습니다.", ephemeral=True)

@tasks.loop(minutes=1)
async def reset_checker():
    now = datetime.now(korea)
    if now.hour == 6 and now.minute == 0:
        user_data = load_all_user_data()
        for uid in user_data:
            for char in user_data[uid].values():
                for task in daily_tasks:
                    char[task] = False if task in binary_tasks else count_tasks[task]
                for task in shop_tasks:
                    char[task] = False
                if now.weekday() == 0:
                    for task in weekly_tasks:
                        char[task] = False
            save_user_data(uid, user_data[uid])
        print("✅ 숙제 리셋 완료")

@tasks.loop(minutes=1)
async def notify_time():
    now = datetime.now(korea)
    if now.minute == 0:
        target_hour = now.hour
        channel = bot.get_channel(channel_config.get("알림") or CHANNEL_ID)
        if channel:
            msg = await channel.send(
                f"@everyone 🔥 {target_hour}시! 불길한 소환의 결계가 나타났습니다.\n남은 시간: 3:00"
            )
            for remaining in range(180, 0, -1):
                minutes, seconds = divmod(remaining, 60)
                await msg.edit(
                    content=(
                        f"@everyone 🔥 {target_hour}시! 불길한 소환의 결계가 나타났습니다.\n"
                        f"남은 시간: {minutes}:{seconds:02d}"
                    )
                )
                await asyncio.sleep(1)
            await msg.edit(
                content=f"@everyone 🔥 {target_hour}시! 불길한 소환의 결계가 종료되었습니다."
            )
        if target_hour in {12, 18, 20, 22}:
            await channel.send(f"@everyone ⚔️ {target_hour}시, 필드 보스가 출현합니다.")

@bot.event
async def on_ready():
    create_table()
    print("✅ 봇 준비 완료됨!")
    try:
        await tree.sync()
        await tree.sync(guild=discord.Object(id=GUILD_ID))
        print("✅ Slash 명령어 동기화 완료")
    except Exception as e:
        print(f"❌ Slash 명령어 동기화 실패: {e}")
    reset_checker.start()
    notify_time.start()

bot.run(TOKEN)
