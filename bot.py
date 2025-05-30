import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button
from datetime import datetime
import os
import json
import pytz
import asyncio
import psycopg2
from dotenv import load_dotenv
from keep_alive import keep_alive

# 🌟 환경설정
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
GUILD_ID = int(os.getenv("GUILD_ID"))
korea = pytz.timezone("Asia/Seoul")

# 🌟 DB 연결
def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

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
count_tasks = {"검은 구멍": 3, "결계": 2}
daily_tasks = ["요일 던전", "심층 던전", "검은 구멍", "결계"]
weekly_tasks = ["필드 보스", "어비스", "레이드"]
shop_tasks = ["보석 상자", "무료 상품"]

def get_task_status_display(char_data):
    def checkbox(val): return "☑" if val else "☐"
    daily = (
        f"  {checkbox(char_data['요일 던전'])} 요일 던전     {checkbox(char_data['필드 보스'])} 필드 보스\n"
        f"  {checkbox(char_data['심층 던전'])} 심층 던전     {checkbox(char_data['어비스'])} 어비스\n"
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
                if task in ["검은 구멍", "결계"]:
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
        for task in ["검은 구멍", "결계"]:
            style = discord.ButtonStyle.success if current_char_data[task] != 0 else discord.ButtonStyle.secondary
            self.add_item(self.create_button(task, style, f"bin|{task}", 1))
        for task in ["필드 보스", "어비스", "레이드"]:
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

# 🌟 채널 설정
@tree.command(name="채널", description="알림 및 숙제 채널을 설정합니다.")
@app_commands.describe(대상="지정할 텍스트 채널")
async def 채널(interaction: discord.Interaction, 대상: discord.TextChannel):
    global channel_config
    channel_config["alert"] = 대상.id
    save_channel_config()
    await safe_send(interaction, f"✅ 모든 알림이 <#{대상.id}> 채널에 통합됩니다.", ephemeral=True)

@tree.command(name="추가", description="캐릭터를 추가합니다.")
@app_commands.describe(닉네임="캐릭터 이름")
async def 추가(interaction: discord.Interaction, 닉네임: str):
    uid = str(interaction.user.id)
    user_data = load_all_user_data()
    if uid not in user_data:
        user_data[uid] = {}
    if 닉네임 in user_data[uid]:
        await safe_send(interaction, f"이미 존재하는 캐릭터입니다: {닉네임}", ephemeral=True)
        return
    user_data[uid][닉네임] = {t: False for t in binary_tasks} | count_tasks.copy()
    save_user_data(uid, user_data[uid])
    await 숙제(interaction)

@tree.command(name="제거", description="캐릭터를 제거합니다.")
@app_commands.describe(닉네임="제거할 캐릭터 이름")
async def 제거(interaction: discord.Interaction, 닉네임: str):
    uid = str(interaction.user.id)
    user_data = load_all_user_data()
    if 닉네임 in user_data.get(uid, {}):
        del user_data[uid][닉네임]
        save_user_data(uid, user_data[uid])
        await 숙제(interaction)
    else:
        await safe_send(interaction, f"존재하지 않는 캐릭터입니다: {닉네임}", ephemeral=True)

@tree.command(name="목록", description="등록된 캐릭터 목록을 확인합니다.")
async def 목록(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    user_data = load_all_user_data()
    if uid not in user_data or not user_data[uid]:
        await safe_send(interaction, "❌ 등록된 캐릭터가 없습니다.", ephemeral=True)
    else:
        char_list = "\n".join(f"- {name}" for name in user_data[uid])
        await safe_send(interaction, f"📋 현재 등록된 캐릭터 목록:\n{char_list}", ephemeral=True)

@tree.command(name="숙제", description="숙제 현황을 보여줍니다.")
async def 숙제(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    user_data = load_all_user_data()
    if uid not in user_data or not user_data[uid]:
        await safe_send(interaction, "❌ 등록된 캐릭터가 없습니다.", ephemeral=True)
        return
    current_char = list(user_data[uid].keys())[0]
    desc = get_task_status_display(user_data[uid][current_char])
    content = f"[{datetime.now(korea).strftime('%Y/%m/%d')}] {current_char}\n{desc}"
    view = PageView(uid, user_data=user_data)
    await safe_send(interaction, content=content, view=view, ephemeral=True)

# 🌟 알림 루프: 메시지를 한 번만 보내고 8분 타이머 돌리기
@tasks.loop(minutes=1)
async def notify_time():
    now = datetime.now(korea)
    channel = bot.get_channel(channel_config.get("alert") or CHANNEL_ID)
    if not channel:
        return

    next_hour = now.hour + 1
    next_boss = next_field_boss_time(next_hour)

    # 55분일 때만 8분 타이머 시작!
    if now.minute == 55:
        boss_hours = [12, 18, 20, 22]
        is_boss_time = next_hour in boss_hours

        if is_boss_time:
            msg = await channel.send(
                f"@everyone\n"
                f"🔥 5분 뒤 {next_hour}시, 결계가 나타납니다! (8:00)\n"
                f"⚔️ 5분 뒤 {next_hour}시, 필드 보스가 출현합니다!"
            )
        else:
            msg = await channel.send(
                f"@everyone\n"
                f"🔥 5분 뒤 {next_hour}시, 결계가 나타납니다! (8:00)\n"
                f"⚔️ 다음 필드 보스는 {next_boss}시입니다."
            )

        channel_config["alert_msg_id"] = msg.id
        save_channel_config()

        for remaining in range(480, 0, -1):
            m, s = divmod(remaining, 60)
            if is_boss_time:
                content = (
                    f"@everyone\n"
                    f"🔥 5분 뒤 {next_hour}시, 결계가 나타납니다! ({m}:{s:02d})\n"
                    f"⚔️ 5분 뒤 {next_hour}시, 필드 보스가 출현합니다!"
                )
            else:
                content = (
                    f"@everyone\n"
                    f"🔥 5분 뒤 {next_hour}시, 결계가 나타납니다! ({m}:{s:02d})\n"
                    f"⚔️ 다음 필드 보스는 {next_boss}시입니다."
                )
            await msg.edit(content=content)
            await asyncio.sleep(1)

        # 종료 시
        content = (
            f"@everyone\n"
            f"🔥 5분 뒤 {next_hour}시, 결계가 나타납니다! (종료)\n"
            f"⚔️ 다음 필드 보스는 {next_boss}시입니다."
        )
        await msg.edit(content=content)

# 🌟 메시지 삭제 복구
@bot.event
async def on_message_delete(message):
    alert_channel_id = channel_config.get("alert") or CHANNEL_ID
    alert_msg_id = channel_config.get("alert_msg_id")
    if message.channel.id == alert_channel_id and message.id == alert_msg_id:
        channel = bot.get_channel(alert_channel_id)
        if not channel:
            return

        now = datetime.now(korea)
        next_hour = now.hour + 1
        next_boss = next_field_boss_time(next_hour)
        boss_hours = [12, 18, 20, 22]
        is_boss_time = next_hour in boss_hours

        # 원래처럼 복구 메시지 재전송
        if is_boss_time:
            msg = await channel.send(
                f"@everyone\n"
                f"🔥 5분 뒤 {next_hour}시, 결계가 나타납니다! (8:00)\n"
                f"⚔️ 5분 뒤 {next_hour}시, 필드 보스가 출현합니다!"
            )
        else:
            msg = await channel.send(
                f"@everyone\n"
                f"🔥 5분 뒤 {next_hour}시, 결계가 나타납니다! (8:00)\n"
                f"⚔️ 다음 필드 보스는 {next_boss}시입니다."
            )

        channel_config["alert_msg_id"] = msg.id
        save_channel_config()

        # 8분 타이머 다시 시작
        for remaining in range(480, 0, -1):
            m, s = divmod(remaining, 60)
            if is_boss_time:
                content = (
                    f"@everyone\n"
                    f"🔥 5분 뒤 {next_hour}시, 결계가 나타납니다! ({m}:{s:02d})\n"
                    f"⚔️ 5분 뒤 {next_hour}시, 필드 보스가 출현합니다!"
                )
            else:
                content = (
                    f"@everyone\n"
                    f"🔥 5분 뒤 {next_hour}시, 결계가 나타납니다! ({m}:{s:02d})\n"
                    f"⚔️ 다음 필드 보스는 {next_boss}시입니다."
                )
            await msg.edit(content=content)
            await asyncio.sleep(1)

        # 종료 시
        content = (
            f"@everyone\n"
            f"🔥 5분 뒤 {next_hour}시, 결계가 나타납니다! (종료)\n"
            f"⚔️ 다음 필드 보스는 {next_boss}시입니다."
        )
        await msg.edit(content=content)

def next_field_boss_time(current_hour):
    schedule = [12, 18, 20, 22]
    for t in schedule:
        if current_hour < t:
            return t
    return schedule[0]

# 🌟 숙제 리셋
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
        print("✅ 숙제 리셋 완료!")

# 🌟 봇 시작
@bot.event
async def on_ready():
    create_table()
    print("✅ 봇 준비 완료됨!")
    try:
        await tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"✅ 길드 동기화 완료 (GUILD_ID: {GUILD_ID})")
    except Exception as e:
        print(f"❌ 동기화 오류: {e}")
    reset_checker.start()
    notify_time.start()

bot.run(TOKEN)
