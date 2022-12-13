import nextcord
from gptjerry import GPTJerry
from config import DISCORD_BOT_TOKEN

intents = nextcord.Intents.default()
intents.message_content, intents.typing, intents.guild_typing, intents.dm_typing = True, True, True, True
client = nextcord.Client(intents=intents)
gptjerrys: dict[int, GPTJerry] = dict()

@client.event
async def on_ready():
    print("Ready.")
    await client.sync_application_commands()

# On raw typing event, if it's not Jerry and it's in a Jerry Thread, add the typing event
@client.event
async def on_raw_typing(payload: nextcord.RawTypingEvent):
    if payload.user_id == client.user.id or payload.channel_id not in gptjerrys:
        return
    gptjerrys[payload.channel_id].add_typing(payload)

# Start command, sets up the thread and creates a GPTJerry instance
@client.slash_command(name="chat")
async def chat(interaction: nextcord.Interaction):
    embed = nextcord.Embed(title='GPTJerry', description='Send messages in this thread to interact with Jerry. The thread will expire after 60 minutes of inactivity')
    start_message = await interaction.send(embed=embed)
    start_message = await start_message.fetch()
    thread: nextcord.Thread = await start_message.create_thread(name=f'GPTJerry - {interaction.user.display_name}', auto_archive_duration=60)
    gptjerrys[thread.id] = GPTJerry()

# On message, if it's not Jerry and it's in a Jerry Thread, handle the message
@client.event
async def on_message(message: nextcord.Message):
    if message.author.bot or message.channel.id not in gptjerrys:
        return
    await gptjerrys[message.channel.id].on_message(message)

client.run(DISCORD_BOT_TOKEN)