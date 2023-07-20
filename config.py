from dotenv import load_dotenv
from os import getenv, mkdir
from os.path import exists
from db_tools import create_provider_tables

if not exists('.env'):
    print("No .env file found, creating one...")
    with open('.env', 'w') as f:
        f.write(f"BOT_TOKEN=placeholder")

load_dotenv()

bot_token = getenv('BOT_TOKEN')

if not exists('db'):
    mkdir('db')

create_provider_tables()

