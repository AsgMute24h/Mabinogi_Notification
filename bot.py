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
from typing import Literal
import keep_alive

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
GUILD_ID = int(os.getenv("GUILD_ID"))  # 서버 ID를 환경 변수에서 불러오기
korea = pytz.timezone('Asia/Seoul')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

user_data = {}
channel_config = {"alert": None, "homework": None}

@tasks.loop(minutes=1)
async def reset_checker():
    pass

@tasks.loop(minutes=1)
async def notify_time():
    now = datetime.now(korea)
    hour = now.hour
    minute = now.minute
    if minute == 55:
        target_hour = (hour + 1) % 24
        channel = bot.get_channel(channel_config["alert"] if channel_config["alert"] else CHANNEL_ID)
        if not channel:
            print("[❌ 오류] 채널을 찾을 수 없음.")
            return

        group_a = set(range(24))
        group_b = {12, 18, 20, 22}

        if target_hour in group_a:
            await channel.send(f"@everyone 🔥 5분 뒤 {target_hour}시, 불길한 소환의 결계가 나타납니다.")
        if target_hour in group_b:
            await channel.send(f"@everyone ⚔️ 5분 뒤 {target_hour}시, 필드 보스가 출현합니다.")

@tree.command(name="채널", description="알림 또는 숙제 채널을 설정합니다.")
@app_commands.choices(유형=[
    app_commands.Choice(name="알림", value="알림"),
    app_commands.Choice(name="숙제", value="숙제")
])
@app_commands.describe(유형="알림 또는 숙제", 대상="지정할 텍스트 채널")
async def 채널(interaction: discord.Interaction, 유형: app_commands.Choice[str], 대상: discord.TextChannel):
    if 유형.value == "알림":
        channel_config["alert"] = 대상.id
    else:
        channel_config["homework"] = 대상.id
    await interaction.response.send_message(f"✅ {유형.name} 채널이 <#{대상.id}>로 설정되었습니다.", ephemeral=True)

@tree.command(name="추가", description="캐릭터를 추가합니다.")
@app_commands.describe(닉네임="추가할 캐릭터 이름")
async def 추가(interaction: discord.Interaction, 닉네임: str):
    uid = interaction.user.id
    if uid not in user_data:
        user_data[uid] = []
    if 닉네임 in user_data[uid]:
        await interaction.response.send_message(f"이미 존재하는 캐릭터입니다: {닉네임}", ephemeral=True)
    else:
        user_data[uid].append(닉네임)
        await interaction.response.send_message(f"✅ 캐릭터 '{닉네임}' 추가 완료!", ephemeral=True)

@tree.command(name="제거", description="캐릭터를 제거합니다.")
@app_commands.describe(닉네임="제거할 캐릭터 이름")
async def 제거(interaction: discord.Interaction, 닉네임: str):
    uid = interaction.user.id
    if uid not in user_data or 닉네임 not in user_data[uid]:
        await interaction.response.send_message(f"존재하지 않는 캐릭터입니다: {닉네임}", ephemeral=True)
    else:
        user_data[uid].remove(닉네임)
        await interaction.response.send_message(f"🗑️ 캐릭터 '{닉네임}' 제거 완료!", ephemeral=True)

@tree.command(name="목록", description="등록된 캐릭터 목록을 확인합니다.")
async def 목록(interaction: discord.Interaction):
    uid = interaction.user.id
    if uid not in user_data or not user_data[uid]:
        await interaction.response.send_message("❌ 등록된 캐릭터가 없습니다.", ephemeral=True)
    else:
        char_list = "\n".join(f"- {name}" for name in user_data[uid])
        await interaction.response.send_message(f"📋 현재 등록된 캐릭터 목록:\n{char_list}", ephemeral=True)

@tree.command(name="숙제", description="숙제 현황을 표시합니다.")
async def 숙제(interaction: discord.Interaction):
    uid = interaction.user.id
    if uid not in user_data or not user_data[uid]:
        await interaction.response.send_message("❌ 등록된 캐릭터가 없습니다. `/추가` 명령어로 캐릭터를 먼저 등록하세요.", ephemeral=True)
        return

    embed = discord.Embed(title="📋 숙제 현황", description="버튼을 눌러 완료 여부를 관리하세요.")
    for name in user_data[uid]:
        embed.add_field(name=f"ㅇ {name}", value="✅ 요일 던전, ❌ 심층 던전", inline=False)  # 예시 값

    view = View()
    view.add_item(Button(label="요일 던전 완료", style=discord.ButtonStyle.green))  # 예시 버튼
    view.add_item(Button(label="심층 던전 완료", style=discord.ButtonStyle.gray))

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.event
async def on_ready():
    print("on_ready 호출됨")
    try:
        guild = discord.Object(id=GUILD_ID)
        if not tree.get_commands(guild=guild):
            synced = await tree.sync(guild=guild)
            print(f"✅ {bot.user} 로 로그인됨, {len(synced)}개의 명령어 동기화됨")
            for cmd in synced:
                print(f"- {cmd.name}")
        else:
            print(f"✅ {bot.user} 로 로그인됨 (명령어 이미 동기화됨)")
    except Exception as e:
        print(f"❌ 명령어 동기화 실패: {e}")
    reset_checker.start()
    notify_time.start()

keep_alive.keep_alive()
bot.run(TOKEN)
