import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import datetime

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

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
    send_reminders.start()

@tasks.loop(minutes=1)
async def send_reminders():
    now = datetime.datetime.now()
    if now.minute == 0 and now.hour in [3, 6, 9, 12]:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await channel.send("@everyone ⏰ 숙제할 시간이에요! 각자 체크 잊지 마세요!")

@bot.command()
async def 숙제(ctx):
    embed = discord.Embed(title="🎯 숙제 현황", color=0x00ffcc)
    for char_name, status in task_status.items():
        daily = ", ".join(status["일일"])
        weekly = ", ".join(status["주간"])
        shop = ", ".join(status["캐시샵"])
        value = f"**일일**: {daily}\n**주간**: {weekly}\n**캐시샵**: {shop}"
        embed.add_field(name=f"📌 {char_name}", value=value, inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def 완료(ctx, char: str, 유형: str, *숙제명):
    if char not in characters:
        await ctx.send(f"⚠️ 캐릭터 이름이 올바르지 않아요: {char}")
        return

    if 유형 not in task_status[char]:
        await ctx.send(f"⚠️ '{유형}'은(는) 유효한 유형이 아니에요. 일일 / 주간 / 캐시샵 중에서 선택해 주세요.")
        return

    done_list = task_status[char][유형]
    for t in 숙제명:
        if t in done_list:
            done_list.remove(t)

    await ctx.send(f"✅ `{char}`의 `{유형}` 숙제 중 {', '.join(숙제명)} 완료 처리했어요.")

@bot.command()
async def 초기화(ctx):
    for char in characters:
        task_status[char]["일일"] = daily_tasks.copy()
    await ctx.send("🔄 모든 캐릭터의 일일 숙제를 초기화했어요.")

bot.run(TOKEN)
