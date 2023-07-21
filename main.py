from discord import Client, Intents, Interaction, Embed, app_commands
from discord.ext import tasks
from config import bot_token
from db_tools import register_provider, check_providers, update_provider_stats, \
    update_guild, initialize_guild, deregister_provider

intents = Intents.default()
client = Client(intents=intents)
tree = app_commands.CommandTree(client)


@tree.command(name="register-provider", description="Register an SCP Storage Provider to be monitored.")
async def register_provider_call(interaction: Interaction, provider_id: str, notify: bool = True, interval: int = 60):
    embed = register_provider(interaction.guild_id, interaction.user.id, provider_id, notify, interval)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="deregister-provider", description="Removes an SCP Storage Provider from being monitored.")
async def deregister_provider_call(interaction: Interaction, provider_id: str):
    embed = deregister_provider(interaction.guild_id, interaction.user.id, provider_id)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="set-alert-channel", description="Sets the alert channel to channel this command is called in.")
async def set_alert_channel_call(interaction: Interaction):
    if interaction.user.guild_permissions.administrator or interaction.user.id == 349706451805274123:
        update_guild(guild_id=interaction.guild.id, alert_channel=interaction.channel.id)
        embed = Embed(description=f"Alert channel set to <#{interaction.channel.id}>", color=0x00ff00)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = Embed(description="You do not have permission to use this command", color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="enable-provider-alerts", description="Enables the bot for this server.")
async def enable_call(interaction: Interaction, enable: bool = True):
    if interaction.user.guild_permissions.administrator or interaction.user.id == 349706451805274123:
        update_guild(guild_id=interaction.guild.id, enable=enable)
        embed = Embed(description=f"Bot {'enabled' if enable else 'disabled'}", color=0x00ff00)
        await interaction.response.send_message(embed, ephemeral=True)
    else:
        embed = Embed(description="You do not have permission to use this command", color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def register_commands(guild):
    try:
        tree.add_command(register_provider_call, guild=guild)
        tree.add_command(enable_call, guild=guild)
        tree.add_command(set_alert_channel_call, guild=guild)
        tree.add_command(deregister_provider_call, guild=guild)
        await tree.sync(guild=guild)
    except Exception as e:
        print(e)
        print(f"Failed to register commands for guild: {guild.id}")


@tasks.loop(minutes=5)
async def run_checks():
    update_provider_stats()
    await check_providers(client)


@client.event
async def on_guild_join(guild):
    await register_commands(guild)
    initialize_guild(guild.id)


@client.event
async def on_ready():

    if not run_checks.is_running():
        run_checks.start()

    for guild in client.guilds:
        initialize_guild(guild.id)
        await register_commands(guild)

    print(f'We have logged in as {client.user}')


if __name__ == '__main__':
    if bot_token == "placeholder":
        print("Please set your bot token in .env")
        print("Shutting down bot...")
        exit()
    client.run(bot_token)

