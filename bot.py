...

class CharacterGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="캐릭터", description="캐릭터를 관리합니다.")

    @app_commands.command(name="추가", description="캐릭터를 추가합니다.")
    @app_commands.describe(닉네임="추가할 캐릭터 이름")
    async def 추가(self, interaction: discord.Interaction, 닉네임: str):
        uid = interaction.user.id
        if uid not in user_data:
            user_data[uid] = {name: {t: False for t in binary_tasks} | {t: count_tasks[t] for t in count_tasks} for name in get_default_characters()}
        if 닉네임 in user_data[uid]:
            await interaction.response.send_message(f"이미 존재하는 캐릭터입니다: {닉네임}", ephemeral=True)
            return
        user_data[uid][닉네임] = {t: False for t in binary_tasks} | {t: count_tasks[t] for t in count_tasks}
        save_data()
        embed = generate_embed(uid)
        view = generate_view(uid)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="제거", description="캐릭터를 제거합니다.")
    @app_commands.describe(닉네임="제거할 캐릭터 이름")
    async def 제거(self, interaction: discord.Interaction, 닉네임: str):
        uid = interaction.user.id
        if uid not in user_data or 닉네임 not in user_data[uid]:
            await interaction.response.send_message(f"존재하지 않는 캐릭터입니다: {닉네임}", ephemeral=True)
            return
        del user_data[uid][닉네임]
        save_data()
        embed = generate_embed(uid)
        view = generate_view(uid)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="목록", description="등록된 캐릭터 목록을 확인합니다.")
    async def 목록(self, interaction: discord.Interaction):
        uid = interaction.user.id
        if uid not in user_data or not user_data[uid]:
            await interaction.response.send_message("❌ 등록된 캐릭터가 없습니다.", ephemeral=True)
            return
        char_list = "\n".join(f"- {name}" for name in user_data[uid].keys())
        await interaction.response.send_message(f"📋 현재 등록된 캐릭터 목록:\n{char_list}", ephemeral=True)

# 기존 캐릭터 명령어 제거 및 등록 방식 변경
# tree.command(...) 제거
# 대신 그룹으로 등록

# ... (위 코드 유지)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ {bot.user} 로 로그인됨")
    reset_checker.start()
    notify_time.start()

# 캐릭터 명령어 그룹 등록
character_group = CharacterGroup()
tree.add_command(character_group)

keep_alive.keep_alive()
bot.run(TOKEN)
