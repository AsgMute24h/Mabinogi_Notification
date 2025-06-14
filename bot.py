import discord
from discord.ext import commands, tasks
from discord.ui import View, Button
from datetime import datetime
import os
import json
import pytz
import asyncio
import sqlite3
from dotenv import load_dotenv
import shutil
import subprocess
import asyncio

# 🌟 설정
DB_PATH = "data.db"
BACKUP_DIR = "backup"
ALERT_FILE = "alert_config.json"
korea = pytz.timezone("Asia/Seoul")
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# 🌟 DB 연결
os.makedirs(BACKUP_DIR, exist_ok=True)
def get_conn():
    return sqlite3.connect(DB_PATH)

def create_table():
    with get_conn() as conn:
        cur = conn.cursor()

        # 테이블이 없다면 생성
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_data (
                user_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                last_msg_id TEXT,
                alert_enabled INTEGER DEFAULT 1
            );
        """)

        # 🌟 alert_msg_id 컬럼이 없다면 추가
        try:
            cur.execute("ALTER TABLE user_data ADD COLUMN alert_msg_id TEXT;")
        except sqlite3.OperationalError:
            # 이미 존재하면 무시
            pass

        conn.commit()

def load_all_user_data():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, data, last_msg_id, alert_enabled, alert_msg_id FROM user_data;")
        rows = cur.fetchall()
        return {
            str(row[0]): {
                "data": json.loads(row[1]),
                "last_msg_id": row[2],
                "alert_enabled": bool(row[3]),
                "alert_msg_id": row[4]
            } for row in rows
        }

def save_user_data(uid, data, last_msg_id=None, alert_enabled=True, alert_msg_id=None):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_data (user_id, data, last_msg_id, alert_enabled, alert_msg_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                data=excluded.data,
                last_msg_id=excluded.last_msg_id,
                alert_enabled=excluded.alert_enabled,
                alert_msg_id=excluded.alert_msg_id;
        """, (uid, json.dumps(data, ensure_ascii=False), last_msg_id, int(alert_enabled), alert_msg_id))
        conn.commit()

    now_str = datetime.now(korea).strftime("%Y%m%d_%H%M%S")
    db_backup = f"{BACKUP_DIR}/{now_str}_data.db"
    shutil.copy(DB_PATH, db_backup)

# 🌟 숙제 항목 정의
binary_tasks = ["요일 던전", "심층 던전", "필드 보스", "어비스", "레이드", "보석 상자", "무료 상품"]
count_tasks = {"검은 구멍": 3, "결계": 2, "망령의 탑": 5}
daily_tasks = ["요일 던전", "심층 던전", "검은 구멍", "결계", "망령의 탑"]
weekly_tasks = ["필드 보스", "어비스", "레이드"]
shop_tasks = ["보석 상자", "무료 상품"]

def get_task_status_display(char_data):
    def checkbox(val): return "☑" if val else "☐"
    return (
        "```\n"
        "┌─────────────┐┌─────────────┐\n"
        f"  {checkbox(char_data['요일 던전'])} 요일 던전     {checkbox(char_data['필드 보스'])} 필드 보스\n"
        f"  {checkbox(char_data['심층 던전'])} 심층 던전     {checkbox(char_data['어비스'])} 어비스\n"
        f"  검은 구멍 {char_data['검은 구멍']}/3   {checkbox(char_data['레이드'])} 레이드\n"
        f"  결계 {char_data['결계']}/2\n"
        f"  망령의 탑 {char_data['망령의 탑']}/5\n"
        "└─────────────┘└─────────────┘\n"
        "┌────────────────────────────┐\n"
        f"    {checkbox(char_data['보석 상자'])} 보석 상자 　{checkbox(char_data['무료 상품'])} 무료 상품\n"
        "└────────────────────────────┘\n"
        "```"
    )

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
            if str(interaction.user.id) != self.user_id:
                return
            if custom_id == "prev":
                self.page = (self.page - 1) % len(self.user_data[self.user_id]["data"])
            elif custom_id == "next":
                self.page = (self.page + 1) % len(self.user_data[self.user_id]["data"])
            elif custom_id == "alert|toggle":
                current = self.user_data[self.user_id].get("alert_enabled", True)
                self.user_data[self.user_id]["alert_enabled"] = not current
            else:
                task = custom_id.split("|")[1]
                current_char = list(self.user_data[self.user_id]["data"].keys())[self.page]
                char_data = self.user_data[self.user_id]["data"][current_char]
                if task in count_tasks:
                    char_data[task] = (char_data[task] - 1) if char_data[task] > 0 else count_tasks[task]
                elif task in ["보석 상자", "무료 상품"]:
                    new_val = not char_data[task]
                    for uid in self.user_data:
                        for char in self.user_data[uid]["data"]:
                            self.user_data[uid]["data"][char][task] = new_val
                else:
                    char_data[task] = not char_data[task]
            save_user_data(
                self.user_id,
                self.user_data[self.user_id]["data"],
                self.user_data[self.user_id]["last_msg_id"],
                self.user_data[self.user_id].get("alert_enabled", True)
            )
            self.update_buttons()
            await self.update(interaction)
        button.callback = callback
        return button

    def update_buttons(self):
        self.clear_items()
        self.add_item(self.create_button("이전", discord.ButtonStyle.secondary, "prev", 0))
        self.add_item(self.create_button("다음", discord.ButtonStyle.secondary, "next", 0))
        current_char_data = self.user_data[self.user_id]["data"][list(self.user_data[self.user_id]["data"].keys())[self.page]]
        for task in ["요일 던전", "심층 던전"]:
            style = discord.ButtonStyle.success if not current_char_data[task] else discord.ButtonStyle.secondary
            self.add_item(self.create_button(task, style, f"bin|{task}", 1))
        for task in ["검은 구멍", "결계", "망령의 탑"]:
            style = discord.ButtonStyle.success if current_char_data[task] != 0 else discord.ButtonStyle.secondary
            self.add_item(self.create_button(task, style, f"bin|{task}", 1))
        for task in ["필드 보스", "어비스", "레이드"]:
            style = discord.ButtonStyle.primary if not current_char_data[task] else discord.ButtonStyle.secondary
            self.add_item(self.create_button(task, style, f"bin|{task}", 2))
        for task in ["보석 상자", "무료 상품"]:
            first_char = list(self.user_data[self.user_id]["data"].keys())[0]
            style = discord.ButtonStyle.danger if not self.user_data[self.user_id]["data"][first_char][task] else discord.ButtonStyle.secondary
            self.add_item(self.create_button(task, style, f"bin|{task}", 3))

        is_enabled = self.user_data[self.user_id].get("alert_enabled", True)
        label = "🔔" if is_enabled else "🔕"
        style = discord.ButtonStyle.success if is_enabled else discord.ButtonStyle.secondary
        self.add_item(self.create_button(label, style, "alert|toggle", 4))
        
    async def update(self, interaction: discord.Interaction):
        current_char = list(self.user_data[self.user_id]["data"].keys())[self.page]
        now = datetime.now(korea).strftime("[%Y/%m/%d]")
        desc = get_task_status_display(self.user_data[self.user_id]["data"][current_char])
        await interaction.response.edit_message(content=f"{now} {current_char}\n{desc}", view=self)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

async def send_or_update_dm(user: discord.User, uid, user_data):
    current_char = list(user_data[uid]["data"].keys())[0]
    desc = get_task_status_display(user_data[uid]["data"][current_char])
    content = f"[{datetime.now(korea).strftime('%Y/%m/%d')}] {current_char}\n{desc}"
    view = PageView(uid, user_data=user_data)

    try:
        if user_data[uid]["last_msg_id"]:
            channel = await user.create_dm()
            old_msg = await channel.fetch_message(int(user_data[uid]["last_msg_id"]))
            await old_msg.delete()
    except Exception:
        pass

    new_msg = await user.send(content=content, view=view)
    user_data[uid]["last_msg_id"] = str(new_msg.id)
    save_user_data(uid, user_data[uid]["data"], new_msg.id, user_data[uid].get("alert_enabled", True))

@tree.command(name="숙제", description="숙제 현황을 보여줍니다.")
async def 숙제(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    all_data = load_all_user_data()
    user_data = all_data.get(uid)

    if not user_data or not user_data["data"]:
        await interaction.response.send_message("❌ 등록된 캐릭터가 없습니다. `/추가` 명령으로 먼저 등록해 주세요.", ephemeral=True)
        return

    # ✅ 필수 응답
    await interaction.response.send_message("📝 숙제 현황이 전송되었습니다.", ephemeral=True)

    # ✅ 이후 DM 전송
    asyncio.create_task(send_or_update_dm(interaction.user, uid, all_data))

@tree.command(name="추가", description="캐릭터를 추가합니다.")
@discord.app_commands.describe(닉네임="캐릭터 이름")
async def 추가(interaction: discord.Interaction, 닉네임: str):
    uid = str(interaction.user.id)
    all_data = load_all_user_data()
    if uid not in all_data:
        all_data[uid] = {"data": {}, "last_msg_id": None, "alert_enabled": True}
    if 닉네임 in all_data[uid]["data"]:
        await interaction.response.send_message("이미 존재하는 캐릭터입니다.", ephemeral=True)
        return
    all_data[uid]["data"][닉네임] = {t: False for t in binary_tasks} | count_tasks.copy()
    await send_or_update_dm(interaction.user, uid, all_data)
    await interaction.response.send_message(f"✅ 캐릭터 `{닉네임}`이(가) 추가되었습니다.", ephemeral=True)

@tree.command(name="제거", description="캐릭터를 제거합니다.")
@discord.app_commands.describe(닉네임="제거할 캐릭터 이름")
async def 제거(interaction: discord.Interaction, 닉네임: str):
    uid = str(interaction.user.id)
    all_data = load_all_user_data()
    if uid not in all_data or 닉네임 not in all_data[uid]["data"]:
        await interaction.response.send_message("존재하지 않는 캐릭터입니다.", ephemeral=True)
        return
    del all_data[uid]["data"][닉네임]
    await send_or_update_dm(interaction.user, uid, all_data)
    await interaction.response.send_message(f"🗑 캐릭터 `{닉네임}` 제거 완료.", ephemeral=True)

@tree.command(name="목록", description="등록된 캐릭터 목록을 확인합니다.")
async def 목록(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    all_data = load_all_user_data()
    if uid not in all_data or not all_data[uid]["data"]:
        await interaction.response.send_message("❌ 등록된 캐릭터가 없습니다.", ephemeral=True)
        return
    char_list = "\n".join(f"- {name}" for name in all_data[uid]["data"])
    await interaction.response.send_message(f"📋 현재 등록된 캐릭터:\n{char_list}", ephemeral=True)

@tree.command(name="삭제", description="기존에 받은 봇의 DM 메시지를 모두 삭제합니다. (최대 99개)")
async def 삭제(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    await interaction.response.send_message("🧹 이전 메시지를 정리 중입니다.", ephemeral=True)
    
    try:
        channel = await interaction.user.create_dm()
        deleted = 0
        async for msg in channel.history(limit=99):  # 여기 limit을 99로 설정
            if msg.author == bot.user:
                await msg.delete()
                deleted += 1
        await interaction.followup.send(f"✅ {deleted}개의 메시지를 삭제했어요.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ 삭제 중 오류 발생: {e}", ephemeral=True)

@tasks.loop(minutes=1)
async def alert_checker():
    now = datetime.now(korea)
    if now.minute != 55:
        return

    field_boss_hours = [11, 17, 19, 21]
    next_hour = (now.hour + 1) % 24

    if now.hour in field_boss_hours:
        boss_msg = f"⚔️ 5분 뒤 {next_hour}시, 필드 보스가 출현합니다!"
    elif now.hour >= 22 or now.hour < 11:
        boss_msg = "⚔️ 오늘 필드 보스를 모두 처치했습니다."
    else:
        for h in field_boss_hours:
            if h > now.hour:
                boss_msg = f"⚔️ 다음 필드 보스는 {h}시입니다."
                break
        else:
            boss_msg = f"⚔️ 다음 필드 보스는 {field_boss_hours[0]}시입니다."

    headline = f"🔥 5분 뒤 {next_hour}시, 불길한 소환의 결계가 나타납니다!"

    all_data = load_all_user_data()
    
    for uid, user in all_data.items():
        if not user.get("alert_enabled", True):
            continue
        try:
            user_obj = await bot.fetch_user(int(uid))
            
            # 과거 메시지 삭제
            if user.get("alert_msg_id"):
                try:
                    channel = await user_obj.create_dm()
                    old_msg = await channel.fetch_message(int(user["alert_msg_id"]))
                    await old_msg.delete()
                except Exception as e:
                    print(f"❌ {uid} 알림 메시지 삭제 실패: {e}")
                    
            # 새 메시지 전송
            new_msg = await user_obj.send(f"{headline}\n{boss_msg}")
            user["alert_msg_id"] = str(new_msg.id)
            
            # 저장
            save_user_data(uid, user["data"], user["last_msg_id"], user["alert_enabled"], user["alert_msg_id"])

        except Exception as e:
            print(f"❌ {uid}에게 DM 실패: {e}")

@tasks.loop(minutes=1)
async def reset_checker():
    now = datetime.now(korea)
    if now.hour == 6 and now.minute == 0:
        all_data = load_all_user_data()
        for uid in all_data:
            for char in all_data[uid]["data"].values():
                for task in daily_tasks:
                    char[task] = False if task in binary_tasks else count_tasks[task]
                for task in shop_tasks:
                    char[task] = False
                if now.weekday() == 0:
                    for task in weekly_tasks:
                        char[task] = False
            save_user_data(uid, all_data[uid]["data"], all_data[uid]["last_msg_id"], all_data[uid]["alert_enabled"])
        print("✅ 숙제 리셋 완료!")

@bot.event
async def on_ready():
    create_table()
    try:
        import subprocess
        subprocess.run(["termux-wake-lock"])
        print("✅ termux-wake-lock executed.")
    except Exception as e:
        print(f"❌ termux-wake-lock 실행 실패: {e}")

    # 명령어 글로벌 등록
    try:
        synced = await tree.sync()  # 🌍 모든 서버에 글로벌로 등록
        print(f"✅ 글로벌 커맨드 동기화 완료: {len(synced)}개 명령어")
    except Exception as e:
        print(f"❌ 글로벌 명령어 동기화 실패: {e}")

    if not reset_checker.is_running():
        reset_checker.start()
    if not alert_checker.is_running():
        alert_checker.start()
    print(f"✅ 봇 시작됨: {bot.user}")
    
@bot.event
async def on_error(event, *args, **kwargs):
    print(f"❌ 전역 이벤트 에러: {event} / {args} / {kwargs}")

def handle_exception(loop, context):
    msg = context.get("exception", context["message"])
    print(f"❌ asyncio 예외: {msg}")

asyncio.get_event_loop().set_exception_handler(handle_exception)

bot.run(TOKEN)
