import os
import discord
from discord.ext import tasks
from discord import app_commands
from dotenv import load_dotenv
import datetime

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# 캐릭터 이름 리스트
characters = ["본캐", "부캐1", "부캐2", "부캐3"]

# 과제 목록
daily_tasks = ["요일 던전", "심층 던전", "검은 구멍 3회", "결계 2회"]
weekly_tasks = ["필드 보스", "어비스", "레이드"]
shop_checks = ["보석 상자", "무료 상품"]

# 각 캐릭터의 숙제 현황을 저장할 딕셔너리
task_status = {char: {
    "일일": daily_tasks.copy(),
    "주간": weekly_tasks.copy(),
    "캐시샵": shop_checks.copy()
} for char in characters}

@bot.event
async def on_ready():
    print(f"{bot.user} is online")
    try:
        synced = await tree.sync()
        print(f"✅ 슬래시 커맨드 {len(synced)}개 동기화 완료")
    except Exception as e:
        print(f"❌ 슬래시 커맨드 동기화 실패: {e}")
    send_reminders.start()

@tasks.loop(minutes=1)
async def send_reminders():
    now = datetime.datetime.now()
    if now.minute == 0 and now.hour in [3, 6, 9, 12]:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await channel.send("@everyone ⏰ 숙제할 시간이에요! 각자 체크 잊지 마세요!")

@tree.command(name="숙제", description="모든 캐릭터의 숙제 현황을 확인합니다.")
async def slash_숙제(interaction: discord.Interaction):
    embed = discord.Embed(title="🎯 숙제 현황", color=0x00ffcc)
    for char_name, status in task_status.items():
        daily = ", ".join(status["일일"])
        weekly = ", ".join(status["주간"])
        shop = ", ".join(status["캐시샵"])
        value = f"**일일**: {daily}\n**주간**: {weekly}\n**캐시샵**: {shop}"
        embed.add_field(name=f"📌 {char_name}", value=value, inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="완료", description="특정 캐릭터의 숙제를 완료 처리합니다.")
@app_commands.describe(char="캐릭터 이름", 유형="숙제 유형", 숙제명="완료할 숙제명들")
async def slash_완료(interaction: discord.Interaction, char: str, 유형: str, 숙제명: str):
    if char not in characters:
        await interaction.response.send_message(f"⚠️ 캐릭터 이름이 올바르지 않아요: {char}", ephemeral=True)
        return

    if 유형 not in task_status[char]:
        await interaction.response.send_message(f"⚠️ '{유형}'은(는) 유효한 유형이 아니에요. 일일 / 주간 / 캐시샵 중에서 선택해 주세요.", ephemeral=True)
        return

    done_list = task_status[char][유형]
    targets = 숙제명.split()
    for t in targets:
        if t in done_list:
            done_list.remove(t)

    await interaction.response.send_message(f"✅ `{char}`의 `{유형}` 숙제 중 {', '.join(targets)} 완료 처리했어요.")

@tree.command(name="초기화", description="모든 캐릭터의 일일 숙제를 초기화합니다.")
async def slash_초기화(interaction: discord.Interaction):
    for char in characters:
        task_status[char]["일일"] = daily_tasks.copy()
    await interaction.response.send_message("🔄 모든 캐릭터의 일일 숙제를 초기화했어요.")

@tree.command(name="캐릭터목록", description="등록된 캐릭터 목록을 보여줍니다.")
async def 캐릭터목록(interaction: discord.Interaction):
    char_list = "\n".join(characters)
    await interaction.response.send_message(f"📋 등록된 캐릭터 목록:\n{char_list}")

bot.run(TOKEN)
