import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button
from datetime import datetime, timedelta
import asyncio
import os
import json
import pytz
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
GUILD_ID = int(os.getenv("GUILD_ID"))
korea = pytz.timezone('Asia/Seoul')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

binary_tasks = ["요일 던전", "심층 던전", "필드 보스", "어비스", "레이드", "보석 상자", "무료 상품"]
count_tasks = {"검은 구멍": 3, "결계": 2}
daily_tasks = ["요일 던전", "심층 던전", "검은 구멍", "결계"]
weekly_tasks = ["필드 보스", "어비스", "레이드"]
shop_tasks = ["보석 상자", "무료 상품"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "user_data.json")
CONFIG_FILE = os.path.join(BASE_DIR, "channel_config.json")

def load_user_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def load_channel_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

user_data = load_user_data()
channel_config = load_channel_config()

def save_user_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

def save_channel_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(channel_config, f, ensure_ascii=False, indent=2)

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

class PageView(View):
    def __init__(self, user_id, page=0):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.page = page
        self.update_buttons()

    def create_button(self, label, style, custom_id, row):
        button = Button(label=label, style=style, custom_id=custom_id, row=row)
        async def callback(interaction: discord.Interaction):
            if custom_id == "prev":
                self.page = (self.page - 1) % len(user_data[self.user_id])
            elif custom_id == "next":
                self.page = (self.page + 1) % len(user_data[self.user_id])
            else:
                current_char = list(user_data[self.user_id].keys())[self.page]
                if custom_id.startswith("bin|"):
                    task = custom_id.split("|")[1]
                    if task in ["검은 구멍", "결계"]:
                        if user_data[self.user_id][current_char][task] > 0:
                            user_data[self.user_id][current_char][task] -= 1
                        else:
                            user_data[self.user_id][current_char][task] = count_tasks[task]
                    elif task in ["보석 상자", "무료 상품"]:
                        # 계정 단위로 처리
                        new_val = not user_data[self.user_id][current_char][task]
                        for uid in user_data:
                            for char in user_data[uid]:
                                user_data[uid][char][task] = new_val
                    else:
                        user_data[self.user_id][current_char][task] = not user_data[self.user_id][current_char][task]
                save_user_data()

            self.update_buttons()
            await self.update(interaction)

        button.callback = callback
        return button

    def update_buttons(self):
        self.clear_items()
        self.add_item(self.create_button("이전", discord.ButtonStyle.secondary, "prev", 0))
        self.add_item(self.create_button("다음", discord.ButtonStyle.secondary, "next", 0))
        for task in ["요일 던전", "심층 던전"]:
            val = user_data[self.user_id][list(user_data[self.user_id].keys())[self.page]][task]
            style = discord.ButtonStyle.success if not val else discord.ButtonStyle.secondary
            self.add_item(self.create_button(task, style, f"bin|{task}", 1))
        for task in ["검은 구멍", "결계"]:
            val = user_data[self.user_id][list(user_data[self.user_id].keys())[self.page]][task]
            style = discord.ButtonStyle.success if val != 0 else discord.ButtonStyle.secondary
            self.add_item(self.create_button(task, style, f"bin|{task}", 1))
        for task in ["필드 보스", "어비스", "레이드"]:
            val = user_data[self.user_id][list(user_data[self.user_id].keys())[self.page]][task]
            style = discord.ButtonStyle.primary if not val else discord.ButtonStyle.secondary
            self.add_item(self.create_button(task, style, f"bin|{task}", 2))
        for task in ["보석 상자", "무료 상품"]:
            # 계정 단위로 처리
            first_char = list(user_data[self.user_id].keys())[0]
            val = user_data[self.user_id][first_char][task]
            style = discord.ButtonStyle.danger if not val else discord.ButtonStyle.secondary
            self.add_item(self.create_button(task, style, f"bin|{task}", 3))

    async def update(self, interaction: discord.Interaction):
        char_list = list(user_data[self.user_id].keys())
        current_char = char_list[self.page]
        now = datetime.now(korea).strftime("[%Y/%m/%d]")
        desc = get_task_status_display(user_data[self.user_id][current_char])
        await interaction.response.edit_message(content=f"{now} {current_char}\n{desc}", view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def on_timeout(self):
        self.clear_items()

    @discord.ui.button(label="이전", style=discord.ButtonStyle.secondary, row=0)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = (self.page - 1) % len(user_data[self.user_id])
        self.update_buttons()
        await self.update(interaction)

    @discord.ui.button(label="다음", style=discord.ButtonStyle.secondary, row=0)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = (self.page + 1) % len(user_data[self.user_id])
        self.update_buttons()
        await self.update(interaction)

@tree.command(name="채널", description="알림 또는 숙제 채널을 설정합니다.")
@app_commands.describe(유형="알림 또는 숙제", 대상="지정할 텍스트 채널")
async def 채널(interaction: discord.Interaction, 유형: str, 대상: discord.TextChannel):
    if 유형 == "알림":
        channel_config["alert"] = 대상.id
    else:
        channel_config["homework"] = 대상.id
    save_channel_config()
    await interaction.response.send_message(f"✅ {유형} 채널이 <#{대상.id}>로 설정되었습니다.", ephemeral=True)

@tree.command(name="추가", description="캐릭터를 추가합니다.")
@app_commands.describe(닉네임="추가할 캐릭터 이름")
async def 추가(interaction: discord.Interaction, 닉네임: str):
    uid = interaction.user.id
    if uid not in user_data:
        user_data[uid] = {}
    if 닉네임 in user_data[uid]:
        await interaction.response.send_message(f"이미 존재하는 캐릭터입니다: {닉네임}", ephemeral=True)
    else:
        user_data[uid][닉네임] = {t: False for t in binary_tasks} | count_tasks.copy()
        save_user_data()
        await show_homework(interaction)

@tree.command(name="제거", description="캐릭터를 제거합니다.")
@app_commands.describe(닉네임="제거할 캐릭터 이름")
async def 제거(interaction: discord.Interaction, 닉네임: str):
    uid = interaction.user.id
    if uid in user_data and 닉네임 in user_data[uid]:
        del user_data[uid][닉네임]
        save_user_data()
        await show_homework(interaction)
    else:
        await interaction.response.send_message(f"존재하지 않는 캐릭터입니다: {닉네임}", ephemeral=True)

@tree.command(name="목록", description="등록된 캐릭터 목록을 확인합니다.")
async def 목록(interaction: discord.Interaction):
    uid = interaction.user.id
    if uid not in user_data or not user_data[uid]:
        await interaction.response.send_message("❌ 등록된 캐릭터가 없습니다.", ephemeral=True)
    else:
        char_list = "\n".join(f"- {name}" for name in user_data[uid])
        await interaction.response.send_message(f"📋 현재 등록된 캐릭터 목록:\n{char_list}", ephemeral=True)

async def show_homework(interaction):
    uid = interaction.user.id
    if uid not in user_data or not user_data[uid]:
        await interaction.response.send_message("❌ 등록된 캐릭터가 없습니다. `/추가` 명령어로 캐릭터를 먼저 등록하세요.", ephemeral=True)
        return
    char_list = list(user_data[uid].keys())
    # 최근에 추가된 캐릭터를 가장 앞에 오도록 정렬
    current_char = char_list[-1]
    desc = get_task_status_display(user_data[uid][current_char])
    if interaction.message:
        await interaction.response.edit_message(content=f"[2025/05/25] {current_char}\n{desc}", view=PageView(uid, page=len(char_list)-1))
    else:
        await interaction.response.send_message(content=f"[2025/05/25] {current_char}\n{desc}", view=PageView(uid, page=len(char_list)-1))

@tree.command(name="숙제", description="숙제 현황을 표시합니다.")
async def 숙제(interaction: discord.Interaction):
    await show_homework(interaction)

@tasks.loop(minutes=1)
async def reset_checker():
    now = datetime.now(korea)
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
        save_user_data()
        print("숙제 리셋 완료")
        channel = bot.get_channel(channel_config["homework"])
        if channel:
            for uid in user_data:
                try:
                    char_list = list(user_data[uid].keys())
                    current_char = char_list[0]
                    desc = get_task_status_display(user_data[uid][current_char])
                    await channel.send(f"**{current_char}**\n{desc}", view=PageView(uid))
                except Exception as e:
                    print(f"[숙제 리셋 실패] {e}")

@tasks.loop(minutes=1)
async def notify_time():
    now = datetime.now(korea)
    if now.minute == 55:
        target_hour = (now.hour + 1) % 24
        channel = bot.get_channel(channel_config["alert"] or CHANNEL_ID)
        if channel:
            if target_hour in range(24):
                await channel.send(f"@everyone 🔥 5분 뒤 {target_hour}시, 불길한 소환의 결계가 나타납니다.")
            if target_hour in {12, 18, 20, 22}:
                await channel.send(f"@everyone ⚔️ 5분 뒤 {target_hour}시, 필드 보스가 출현합니다.")

@bot.event
async def on_ready():
    global user_data, channel_config
    print("on_ready 호출됨")
    try:
        guild = discord.Object(id=GUILD_ID)
        await tree.sync(guild=guild)
        print("✅ 명령어 동기화 완료")
    except Exception as e:
        print(f"❌ 명령어 동기화 실패: {e}")
    reset_checker.start()
    notify_time.start()

bot.run(TOKEN)
