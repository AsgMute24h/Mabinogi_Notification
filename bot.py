import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button
from discord.errors import HTTPException
from datetime import datetime
from datetime import datetime, timedelta
import os
import json
import pytz
import asyncio
import sqlite3
from dotenv import load_dotenv
from keep_alive import keep_alive
import math
import shutil

# 🌟 환경설정
DB_PATH = "data.db"
TIME_OFFSET = 130  # 2분 10초
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
GUILD_ID = int(os.getenv("GUILD_ID"))
korea = pytz.timezone("Asia/Seoul")

# 🌟 DB 연결
def get_conn():
    return sqlite3.connect(DB_PATH)

def create_table():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_data (
                user_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            );
        """)
        conn.commit()

def load_all_user_data():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, data FROM user_data;")
        rows = cur.fetchall()
        return {str(row[0]): json.loads(row[1]) for row in rows}

def save_user_data(user_id, data):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_data (user_id, data)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET data=excluded.data;
        """, (user_id, json.dumps(data, ensure_ascii=False)))
        conn.commit()

# 🌟 config (알림 채널, 메시지 ID)
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
    print(f"✅ 채널 설정 저장됨: {channel_config}")

channel_config = load_channel_config()

# 🌟 봇 설정
keep_alive()
os.environ["TZ"] = "Asia/Seoul"
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# 🌟 숙제 관리
binary_tasks = ["요일 던전", "심층 던전", "필드 보스", "어비스", "레이드", "보석 상자", "무료 상품"]
count_tasks = {"검은 구멍": 3, "결계": 2, "망령의 탑": 5}
daily_tasks = ["요일 던전", "심층 던전", "검은 구멍", "결계", "망령의 탑"]
weekly_tasks = ["필드 보스", "어비스", "레이드"]
shop_tasks = ["보석 상자", "무료 상품"]

def get_task_status_display(char_data):
    def checkbox(val): return "☑" if val else "☐"
    daily = (
    f"  {checkbox(char_data['요일 던전'])} 요일 던전     {checkbox(char_data['필드 보스'])} 필드 보스\n"
    f"  {checkbox(char_data['심층 던전'])} 심층 던전     {checkbox(char_data['어비스'])} 어비스\n"
    f"  검은 구멍 {char_data['검은 구멍']}/3   {checkbox(char_data['레이드'])} 레이드\n"
    f"  결계 {char_data['결계']}/2\n"
    f"  망령의 탑 {char_data['망령의 탑']}/5"
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

# 🌟 버튼 뷰 (PageView)
class PageView(View):
    def __init__(self, user_id, page=0, user_data=None):
        super().__init__(timeout=None)
        self.user_id = str(user_id)
        self.page = page
        self.user_data = user_data or load_all_user_data()
        self.update_buttons()

    def create_button(self, label, style, custom_id, row):
        button = Button(label=label, style=style, custom_id=custom_id, row=row)
        async def callback(interaction: discord.Interaction):
            if custom_id == "prev":
                self.page = (self.page - 1) % len(self.user_data[self.user_id])
            elif custom_id == "next":
                self.page = (self.page + 1) % len(self.user_data[self.user_id])
            else:
                current_char = list(self.user_data[self.user_id].keys())[self.page]
                task = custom_id.split("|")[1]
                if task in count_tasks:
                    if self.user_data[self.user_id][current_char][task] > 0:
                        self.user_data[self.user_id][current_char][task] -= 1
                    else:
                        self.user_data[self.user_id][current_char][task] = count_tasks[task]
                elif task in ["보석 상자", "무료 상품"]:
                    new_val = not self.user_data[self.user_id][current_char][task]
                    for uid in self.user_data:
                        for char in self.user_data[uid]:
                            self.user_data[uid][char][task] = new_val
                else:
                    self.user_data[self.user_id][current_char][task] = not self.user_data[self.user_id][current_char][task]
                save_user_data(self.user_id, self.user_data[self.user_id])
            self.update_buttons()
            await self.update(interaction)
        button.callback = callback
        return button

    def update_buttons(self):
        self.clear_items()
        self.add_item(self.create_button("이전", discord.ButtonStyle.secondary, "prev", 0))
        self.add_item(self.create_button("다음", discord.ButtonStyle.secondary, "next", 0))
        current_char_data = self.user_data[self.user_id][list(self.user_data[self.user_id].keys())[self.page]]
        for task in ["요일 던전", "심층 던전"]:
            style = discord.ButtonStyle.success if not current_char_data[task] else discord.ButtonStyle.secondary
            self.add_item(self.create_button(task, style, f"bin|{task}", 1))
        for task in ["검은 구멍", "결계", "망령의 탑"]:
            style = discord.ButtonStyle.success if current_char_data[task] != 0 else discord.ButtonStyle.secondary
            self.add_item(self.create_button(task, style, f"bin|{task}", 1))
        for task in ["필드 보스", "어비스", "레이드"]:
            if task in count_tasks:
                style = discord.ButtonStyle.primary if current_char_data[task] != 0 else discord.ButtonStyle.secondary
                self.add_item(self.create_button(task, style, f"bin|{task}", 2))
            else:
                style = discord.ButtonStyle.primary if not current_char_data[task] else discord.ButtonStyle.secondary
                self.add_item(self.create_button(task, style, f"bin|{task}", 2))
        for task in ["보석 상자", "무료 상품"]:
            first_char = list(self.user_data[self.user_id].keys())[0]
            style = discord.ButtonStyle.danger if not self.user_data[self.user_id][first_char][task] else discord.ButtonStyle.secondary
            self.add_item(self.create_button(task, style, f"bin|{task}", 3))

    async def update(self, interaction: discord.Interaction):
        current_char = list(self.user_data[self.user_id].keys())[self.page]
        now = datetime.now(korea).strftime("[%Y/%m/%d]")
        desc = get_task_status_display(self.user_data[self.user_id][current_char])
        await interaction.response.edit_message(content=f"{now} {current_char}\n{desc}", view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == int(self.user_id)

# 🌟 안전 전송
from discord.errors import InteractionResponded

async def safe_send(interaction: discord.Interaction, content=None, ephemeral=False, **kwargs):
    try:
        await interaction.response.send_message(content=content, ephemeral=ephemeral, **kwargs)
    except InteractionResponded:
        try:
            await interaction.edit_original_response(content=content, **kwargs)
        except discord.NotFound:
            pass
    except HTTPException as e:
        if e.status == 429:
            retry_after = int(e.response.headers.get("Retry-After", "5"))
            print(f"⏳ Rate limit hit. Retrying after {retry_after} seconds...")
            await asyncio.sleep(retry_after)
            await interaction.followup.send(content=content, ephemeral=ephemeral, **kwargs)

# 🌟 숙제 명령 함수 분리
async def show_homework(interaction):
    uid = str(interaction.user.id)
    user_data = load_all_user_data()
    if uid not in user_data or not user_data[uid]:
        await safe_send(interaction, "❌ 등록된 캐릭터가 없습니다.", ephemeral=True)
        return
    for char_name in user_data[uid]:
        for task in binary_tasks:
            if task not in user_data[uid][char_name]:
                user_data[uid][char_name][task] = False
        for task in count_tasks:
            if task not in user_data[uid][char_name]:
                user_data[uid][char_name][task] = count_tasks[task]
    save_user_data(uid, user_data[uid])

    current_char = list(user_data[uid].keys())[0]
    desc = get_task_status_display(user_data[uid][current_char])
    content = f"[{datetime.now(korea).strftime('%Y/%m/%d')}] {current_char}\n{desc}"
    view = PageView(uid, user_data=user_data)
    await safe_send(interaction, content=content, view=view, ephemeral=True)

async def register_character(interaction, 닉네임):
    uid = str(interaction.user.id)
    user_data = load_all_user_data()
    if uid not in user_data:
        user_data[uid] = {}
    if 닉네임 in user_data[uid]:
        await safe_send(interaction, f"이미 존재하는 캐릭터입니다: {닉네임}", ephemeral=True)
        return
    user_data[uid][닉네임] = {t: False for t in binary_tasks} | count_tasks.copy()
    save_user_data(uid, user_data[uid])
    await show_homework(interaction)

async def remove_character(interaction, 닉네임):
    uid = str(interaction.user.id)
    user_data = load_all_user_data()
    if 닉네임 in user_data.get(uid, {}):
        del user_data[uid][닉네임]
        save_user_data(uid, user_data[uid])
        await show_homework(interaction)
    else:
        await safe_send(interaction, f"존재하지 않는 캐릭터입니다: {닉네임}", ephemeral=True)

async def list_characters(interaction):
    uid = str(interaction.user.id)
    user_data = load_all_user_data()
    if uid not in user_data or not user_data[uid]:
        await safe_send(interaction, "❌ 등록된 캐릭터가 없습니다.", ephemeral=True)
    else:
        char_list = "\n".join(f"- {name}" for name in user_data[uid])
        await safe_send(interaction, f"📋 현재 등록된 캐릭터 목록:\n{char_list}", ephemeral=True)

async def set_alert_channel(interaction, 대상):
    global channel_config
    channel_config["alert"] = 대상.id
    save_channel_config()
    await safe_send(interaction, f"✅ 알림 채널이 <#{대상.id}>로 설정되었습니다.", ephemeral=True)

# 🌟 명령어 핸들러
@tree.command(name="숙제", description="숙제 현황을 보여줍니다.")
async def 숙제(interaction: discord.Interaction):
    await show_homework(interaction)

@tree.command(name="추가", description="캐릭터를 추가합니다.")
@app_commands.describe(닉네임="캐릭터 이름")
async def 추가(interaction: discord.Interaction, 닉네임: str):
    await register_character(interaction, 닉네임)

@tree.command(name="제거", description="캐릭터를 제거합니다.")
@app_commands.describe(닉네임="제거할 캐릭터 이름")
async def 제거(interaction: discord.Interaction, 닉네임: str):
    await remove_character(interaction, 닉네임)

@tree.command(name="목록", description="등록된 캐릭터 목록을 확인합니다.")
async def 목록(interaction: discord.Interaction):
    await list_characters(interaction)

@tree.command(name="채널", description="알림 채널을 설정합니다.")
@app_commands.describe(대상="지정할 텍스트 채널")
async def 채널(interaction: discord.Interaction, 대상: discord.TextChannel):
    await set_alert_channel(interaction, 대상)
    
def next_field_boss_time(now):
    hour, minute = now.hour, now.minute
    if (hour, minute) == (11, 55):
        return 12
    elif (hour, minute) == (17, 55):
        return 18
    elif (hour, minute) == (19, 55):
        return 20
    elif (hour, minute) == (21, 55):
        return 22
    return None

@tasks.loop(minutes=1)
async def notify_time():
    try:
        now = datetime.now(korea)
        channel = bot.get_channel(channel_config.get("alert") or CHANNEL_ID)
        if not channel or now.minute != 55:
            return

        next_hour = (now.hour + 1) % 24
        field_boss_hours = [11, 17, 19, 21]

        if now.hour >= 22 or now.hour < 11:
            boss_msg = "⚔️ 오늘 필드 보스를 모두 처치했습니다."
        elif now.hour in field_boss_hours:
            boss_msg = f"⚔️ 5분 뒤 {next_hour}시, 필드 보스가 출현합니다!"
        else:
            def next_field_boss_time(now_hour):
                for h in field_boss_hours:
                    if h > now_hour:
                        return h
                return field_boss_hours[0]
            boss_msg = f"⚔️ 다음 필드 보스는 {next_field_boss_time(now.hour)}시입니다."

        headline = f"@everyone\n🔥 5분 뒤 {next_hour}시, 불길한 소환의 결계가 나타납니다!"

        # 이전 메시지 삭제
        if channel_config.get("alert_msg_id"):
            try:
                old_msg = await channel.fetch_message(channel_config["alert_msg_id"])
                await old_msg.delete()
            except discord.NotFound:
                pass
            channel_config["alert_msg_id"] = None
            save_channel_config()

        # 초기 메시지 전송
        msg = await channel.send(f"{headline} (8:00)\n{boss_msg}")
        channel_config["alert_msg_id"] = msg.id
        save_channel_config()

        # 8분 → 0분 카운트다운 (절대 시간 기준)
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=480)

        while True:
            now = datetime.now()
            remaining = (end_time - now).total_seconds()

            if remaining <= 0:
                try:
                    await msg.edit(content=f"{headline} [종료]\n{boss_msg}")
                except discord.NotFound:
                    pass
                break

            minutes, seconds = divmod(int(remaining), 60)
            time_display = f"{minutes}:{seconds:02d}"

            try:
                await msg.edit(content=f"{headline} ({time_display})\n{boss_msg}")
            except discord.NotFound:
                break

            await asyncio.sleep(1)

    except Exception as e:
        print(f"❌ notify_time 에러: {e}")

@tasks.loop(minutes=1)
async def reset_checker():
    try:
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
            print("✅ 숙제 리셋 완료!")
    except Exception as e:
        print(f"❌ reset_checker 루프 중 에러: {e}")

@tasks.loop(hours=6)
async def backup_files():
    try:
        now_str = datetime.now(korea).strftime("%Y%m%d_%H%M")
        db_backup = f"backup/{now_str}_data.db"
        config_backup = f"backup/{now_str}_channel_config.json"
        shutil.copy("data.db", db_backup)
        shutil.copy("channel_config.json", config_backup)
        print(f"✅ 자동 백업 완료: {db_backup}, {config_backup}")
    except Exception as e:
        print(f"❌ 백업 중 오류 발생: {e}")

@bot.event
async def on_ready():
    create_table()

    if not notify_time.is_running():
        notify_time.start()
    if not backup_files.is_running():
        backup_files.start()
    if not reset_checker.is_running():
        reset_checker.start()

    print("✅ 봇 준비 완료됨!")

    try:
        # 글로벌로 싱크
        synced = await tree.sync()
        print(f"✅ 글로벌 명령어 동기화: {len(synced)}개")
    except Exception as e:
        print(f"❌ 동기화 오류: {e}")

# 전역 에러 핸들러
@bot.event
async def on_error(event, *args, **kwargs):
    print(f"❌ 전역 이벤트 에러: {event} / {args} / {kwargs}")

# asyncio 루프 예외 처리
def handle_exception(loop, context):
    msg = context.get("exception", context["message"])
    print(f"❌ asyncio 루프 예외 발생: {msg}")

asyncio.get_event_loop().set_exception_handler(handle_exception)

bot.run(TOKEN)
