import discord
from discord.ext import tasks
from discord.ui import View, Button
from discord import app_commands
from discord.app_commands import Group
from datetime import datetime, timedelta
import asyncio
import os
import json
import pytz
from dotenv import load_dotenv
import keep_alive

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
korea = pytz.timezone('Asia/Seoul')

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

user_data = {}

@tasks.loop(minutes=1)
async def reset_checker():
    pass

@tasks.loop(minutes=1)
async def notify_time():
    pass

class CharacterGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="캐릭터", description="캐릭터를 관리합니다.")

    @app_commands.command(name="추가", description="캐릭터를 추가합니다.")
    @app_commands.describe(닉네임="추가할 캐릭터 이름")
    async def 추가(self, interaction: discord.Interaction, 닉네임: str):
        uid = interaction.user.id
        if uid not in user_data:
            user_data[uid] = []
        if 닉네임 in user_data[uid]:
            await interaction.response.send_message(f"이미 존재하는 캐릭터입니다: {닉네임}", ephemeral=True)
        else:
            user_data[uid].append(닉네임)
            await interaction.response.send_message(f"✅ 캐릭터 '{닉네임}' 추가 완료!", ephemeral=True)

    @app_commands.command(name="제거", description="캐릭터를 제거합니다.")
    @app_commands.describe(닉네임="제거할 캐릭터 이름")
    async def 제거(self, interaction: discord.Interaction, 닉네임: str):
        uid = interaction.user.id
        if uid not in user_data or 닉네임 not in user_data[uid]:
            await interaction.response.send_message(f"존재하지 않는 캐릭터입니다: {닉네임}", ephemeral=True)
        else:
            user_data[uid].remove(닉네임)
            await interaction.response.send_message(f"🗑️ 캐릭터 '{닉네임}' 제거 완료!", ephemeral=True)

    @app_commands.command(name="목록", description="등록된 캐릭터 목록을 확인합니다.")
    async def 목록(self, interaction: discord.Interaction):
        uid = interaction.user.id
        if uid not in user_data or not user_data[uid]:
            await interaction.response.send_message("❌ 등록된 캐릭터가 없습니다.", ephemeral=True)
        else:
            char_list = "\n".join(f"- {name}" for name in user_data[uid])
            await interaction.response.send_message(f"📋 현재 등록된 캐릭터 목록:\n{char_list}", ephemeral=True)

character_group = CharacterGroup()
tree.add_command(character_group)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ {bot.user} 로 로그인됨")
    reset_checker.start()
    notify_time.start()

keep_alive.keep_alive()
bot.run(TOKEN)
