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
    print(f'{bot.user} is online')
    notify_time.start()

@tasks.loop(minutes=1)
async def notify_time():
    now = datetime.now(korea)
    hour = now.hour
    if now.minute == 0:
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            return

        group_a = {3, 6, 9, 12, 15, 18, 21, 0}
        group_b = {12, 18, 20, 22}

        if hour in group_a:
            await channel.send("@everyone 불길한 소환의 결계가 나타난 것 같다.".format(hour))

        if hour in group_b:
            await channel.send("@everyone 필드 보스가 출현했습니다.".format(hour))

keep_alive.keep_alive()
bot.run(TOKEN)

@bot.event
async def on_message(message):
    await bot.process_commands(message)

@bot.command()
async def 테스트(ctx):
    if ctx.channel.id == CHANNEL_ID:
        await ctx.send("@everyone [테스트 메시지] 지금은 테스트 중입니다!")
