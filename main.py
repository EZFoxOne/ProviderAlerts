from discord import Client, Intents, Interaction, Object, Webhook, app_commands
from discord.ext import tasks
from config import bot_token
from db_tools import register_provider, create_provider_tables, check_providers
from graphana import update_provider_stats


create_provider_tables()

intents = Intents.default()
client = Client(intents=intents)
tree = app_commands.CommandTree(client)
dev_guild = Object(id=1069820414102081546)


@tree.command(name="register-provider", description="Register an SCP Storage Provider to be monitored.",
              guilds=[dev_guild])
async def register_provider_call(interaction: Interaction, provider_id: str, notify: bool = True, interval: int = 60):
    output_text = register_provider(interaction.user.id, provider_id, notify, interval)
    await interaction.response.send_message(output_text, ephemeral=True)


@tasks.loop(seconds=60)
async def run_checks():
    update_provider_stats()
    await check_providers(client)


@client.event
async def on_ready():

    if not run_checks.is_running():
        run_checks.start()

    for guild in client.guilds:
        try:
            await tree.sync(guild=guild)
        except Exception as e:
            print(e)

    print(f'We have logged in as {client.user}')


if __name__ == '__main__':
    client.run(bot_token)

