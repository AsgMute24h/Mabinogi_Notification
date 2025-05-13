import os
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv
from datetime import datetime
import pytz
import keep_alive

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

korea = pytz.timezone('Asia/Seoul')

@bot.event
async def on_ready():
    print(f"[봇 온라인] {bot.user} is ready.")
    print(f"[환경 변수] TOKEN 길이: {len(TOKEN)}, CHANNEL_ID: {CHANNEL_ID}")
    notify_time.start()

@tasks.loop(minutes=1)
async def notify_time():
    now = datetime.now(korea)
    hour = now.hour
    minute = now.minute
    print(f"[⏰ 시간 체크] 현재 시각: {hour}:{minute:02d}")

    if minute == 55:
        target_hour = (hour + 1) % 24  # 5분 뒤 시각 기준
        print(f"[🔔 예정된 알림] 5분 뒤 시각: {target_hour}")

        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            print("[❌ 오류] 채널을 찾을 수 없음.")
            return
        print(f"[📢 채널 확인 완료] 채널 이름: {channel.name}")

        group_a = {3, 6, 9, 12, 15, 18, 21, 0}
        group_b = {12, 18, 20, 22}

        if target_hour in group_a:
            print(f"[🔥 group A] {target_hour}시 알림 예정")
            await channel.send(f"@everyone 🔥 5분 뒤 {target_hour}시! 불길한 소환의 결계가 나타날 것 같습니다.")

        if target_hour in group_b:
            print(f"[⚔️ group B] {target_hour}시 알림 예정")
            await channel.send(f"@everyone ⚔️ 5분 뒤 {target_hour}시! 필드 보스가 출현할 것으로 보입니다.")

@bot.command(name="test", aliases=["테스트"])
async def test(ctx):
    print(f"[🧪 명령 호출됨] 채널 ID: {ctx.channel.id}, 기대값: {CHANNEL_ID}")
    if ctx.channel.id == CHANNEL_ID:
        await ctx.send("@everyone [테스트 메시지] 지금은 테스트 중입니다!")
        print("[✅ 메시지 전송 성공]")
    else:
        await ctx.send("⚠️ 이 채널에서는 테스트 명령이 허용되지 않습니다.")
        print("[⚠️ 테스트 명령 채널 ID 불일치]")

@bot.event
async def on_message(message):
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("⚠️ 해당 명령어를 찾을 수 없습니다.")
        print(f"[🚫 명령어 없음] '{ctx.message.content}'")
    else:
        raise error

keep_alive.keep_alive()
bot.run(TOKEN)
