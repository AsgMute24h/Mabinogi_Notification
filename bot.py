import os
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv
from datetime import datetime
import pytz
import keep_alive

# 환경변수 로드
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

# 디스코드 봇 설정
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

korea = pytz.timezone('Asia/Seoul')

@bot.event
async def on_ready():
    print(f'{bot.user} is online')
    notify_time.start()

@tasks.loop(minutes=1)
async def notify_time():
    now = datetime.now(korea)
    hour = now.hour
    minute = now.minute

    if minute == 55:  # 매 시각 5분 전
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            return

        group_a = {3, 6, 9, 12, 15, 18, 21, 0}
        group_b = {12, 18, 20, 22}

        if hour in group_a:
            await channel.send(f"@everyone 불길한 소환의 결계가 나타난 것 같다.")

        if hour in group_b:
            await channel.send(f"@everyone 필드 보스가 출현했습니다.")

# 명령어가 작동하도록 메시지 이벤트 전달
@bot.event
async def on_message(message):
    await bot.process_commands(message)

# 테스트 명령어
@bot.command(name="테스트", aliases=["test"])
async def test(ctx):
    if ctx.channel.id == CHANNEL_ID:
        await ctx.send("@everyone [테스트 메시지] 지금은 테스트 중입니다!")

# 명령어 에러 처리 (예: 존재하지 않는 명령어)
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("⚠️ 해당 명령어를 찾을 수 없습니다.")
    else:
        raise error

# keep_alive 서버 실행 후 봇 시작
keep_alive.keep_alive()
bot.run(TOKEN)
