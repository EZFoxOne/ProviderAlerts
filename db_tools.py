import sqlite3
from discord import Webhook, Embed
from datetime import datetime, timedelta
webhook_url = "https://discord.com/api/webhooks/1130656017659727963/vithJ42_8zeKuPiQeF3rN6sxAq6_rQtWcJda8Uoo_lLFvVXUurO_Nx9Nm583dHd5Js-t"
dev_mode = False

def create_connection(db_name):
    try:
        conn = sqlite3.connect(f"db\\{db_name}.db")
        c = conn.cursor()
        return conn, c
    except sqlite3.Error as e:
        print(e)


def initialize_guild(guild_id):
    conn, c = create_connection('provider')
    c.execute("CREATE TABLE IF NOT EXISTS guilds (guild_id integer unique, alert_channel integer, enabled integer)")
    c.execute("INSERT OR IGNORE INTO guilds VALUES (?, ?, ?)", (guild_id, 0, 0))
    conn.commit()
    conn.close()


def update_guild(guild_id, alert_channel=None, enable=None):
    conn, c = create_connection('provider')
    if alert_channel is not None:
        c.execute("UPDATE guilds SET alert_channel = ? WHERE guild_id = ?", (alert_channel, guild_id))
    if enable is not None:
        c.execute("UPDATE guilds SET enabled = ? WHERE guild_id = ?", (enable, guild_id))
    conn.commit()
    conn.close()


async def check_providers(client):
    print("Checking providers")
    conn, c = create_connection('provider')
    providers = c.execute("SELECT * FROM provider").fetchall()
    alert_list = {p[0]: p[2] for p in providers if p[2] != "Active"}
    registered_providers = {p[1]: [p[0], p[2], p[3], p[4]] for p in c.execute("SELECT * FROM registered_providers").fetchall()}

    for provider in registered_providers:
        if provider in alert_list.keys():
            webhook = Webhook.from_url(webhook_url, client=client)
            notification_status = c.execute("SELECT notify, last_notified FROM registered_providers "
                                            "WHERE provider_id = ?", [provider]).fetchone()
            if (notification_status[0] == 1 and datetime.fromisoformat(registered_providers[provider][3]) < datetime.now() - timedelta(minutes=int(registered_providers[provider][2]))) or dev_mode:
                await webhook.send(content=f"<@{registered_providers[provider][0]}>\n\nProvider {provider} is "
                                           f"{alert_list[provider]}",)
            c.execute("UPDATE registered_providers SET last_notified = ? WHERE provider_id = ?", (datetime.now(), provider))
    conn.commit()


def create_provider_tables():
    conn, c = create_connection("provider")
    c.execute(
        "CREATE TABLE IF NOT EXISTS provider (provider_id text unique, provider_ip text, status text, last_scanned text)")
    c.execute(
        "CREATE TABLE IF NOT EXISTS registered_providers (user_id integer, provider_id text unique, notify integer, interval real, last_notified text)")
    conn.commit()
    conn.close()


def insert_provider_data(conn, c, provider_id, provider_ip, status, last_scanned):
    c.execute("INSERT OR REPLACE INTO provider (provider_id, provider_ip, status, last_scanned) VALUES (?, ?, ?, ?)",
              (provider_id, provider_ip, status, last_scanned))


def build_alert_embed(user_id, provider_id, last_scanned):
    message = {
        "content": f"<@{user_id}>",
        "embeds": [
            {
                "title": f"Provider ID: {provider_id} is OFFLINE",
                "description": f"Last scanned: {last_scanned}",
            }
        ],
        "attachments": []
    }
    return message


def register_provider(user_id, provider_id, notify, interval):
    conn, c = create_connection("provider")
    existing_data = c.execute("SELECT * FROM provider WHERE provider_id = ?", [provider_id]).fetchall()
    c.execute("INSERT OR REPLACE INTO registered_providers (user_id, provider_id, notify, interval, last_notified) "
              "VALUES (?, ?, ?, ?, ?)", (user_id, provider_id, notify, interval, 0))
    conn.commit()
    conn.close()
    output_text = f"Provider {provider_id} {'updated' if len(existing_data) != 0 else 'registered'} " \
                  f"successfully with the following settings:\n" \
                  f"Notify: {notify}\n" \
                  f"Interval: {interval}"
    return output_text


