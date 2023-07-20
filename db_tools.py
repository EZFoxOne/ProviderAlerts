import sqlite3
from discord import Embed, Color
from datetime import datetime, timedelta
from json import dumps
from requests.structures import CaseInsensitiveDict
from requests import post

dev_mode = False


def create_connection(db_name):
    try:
        conn = sqlite3.connect(f"db\\{db_name}.db")
        c = conn.cursor()
        return conn, c
    except sqlite3.Error as e:
        print(e)


def create_provider_tables():
    conn, c = create_connection("provider")
    c.execute(
        "CREATE TABLE IF NOT EXISTS provider (provider_id text unique, provider_ip text, status text, "
        "last_scanned text)")
    c.execute(
        "CREATE TABLE IF NOT EXISTS registered_providers (guild_id integer, user_id integer, provider_id text, "
        "notify integer, interval real, last_notified text, UNIQUE (guild_id, user_id, provider_id))")
    conn.commit()
    conn.close()


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


def get_enabled_guilds():
    conn, c = create_connection('provider')
    enabled_guilds = {g[0]: [g[1], g[2]] for g in c.execute("SELECT * FROM guilds WHERE enabled = '1'").fetchall()}
    conn.close()
    return enabled_guilds


def get_nonactive_providers():
    conn, c = create_connection('provider')
    nonactive_providers = {p[0]: [p[1], p[2], p[3]] for p in
                           c.execute("SELECT * FROM provider WHERE status != '1'").fetchall()}
    conn.close()
    return nonactive_providers


def get_registered_providers():
    conn, c = create_connection('provider')
    registered_providers = c.execute("SELECT * FROM registered_providers").fetchall()
    conn.close()
    return registered_providers


async def check_providers(client):
    print("Checking providers")

    conn, c = create_connection('provider')

    enabled_guilds = get_enabled_guilds()
    alert_list = get_nonactive_providers()
    registered_providers = get_registered_providers()

    for p in registered_providers:

        guild_id, user_id, provider_id, notify, interval, last_notified = p[0], p[1], p[2], p[3], p[4], p[5]

        if guild_id not in enabled_guilds:
            print(f"Guild ({guild_id}) not enabled for provider {provider_id}, skipping alert...")
            if not dev_mode:
                continue

        alert_list_keys = list(alert_list.keys())
        if provider_id in alert_list_keys:

            status = "Passive" if alert_list[provider_id] == "-1" else "Offline"

            print(f"Provider {provider_id} is {status}")
            print(f"Dev Mode: {dev_mode}")

            if last_notified == "0":
                last_notified = datetime.now() - timedelta(minutes=int(interval) + 1)
            else:
                last_notified = datetime.fromisoformat(last_notified)

            notified_expiration = datetime.now() - timedelta(minutes=int(interval))

            if last_notified < notified_expiration or dev_mode:

                guild_alert_channel = enabled_guilds[guild_id][0]

                if guild_alert_channel != "0":

                    print("Sending alert...")
                    channel = client.get_channel(int(guild_alert_channel))
                    last_scanned = int(int(alert_list[provider_id][2])/1000)
                    embed = build_alert_embed(user_id, provider_id, status, last_scanned)
                    await channel.send(content=f"<@{user_id}>" if notify else None,
                                       embed=embed)

                    c.execute("UPDATE registered_providers SET last_notified = ? WHERE provider_id = ?",
                              (datetime.now(), provider_id))

    conn.commit()


def update_provider_stats():
    print("Getting provider data...")

    url = 'https://grafana.scpri.me/api/ds/query'
    headers = CaseInsensitiveDict()
    headers["Accept"] = "application/json"
    headers["Content-Type"] = "application/json"

    query = {
        "queries": [
            {
                "datasource": {
                    "type": "postgres",
                    "uid": "nJPYpy2Gk"
                },
                "rawSql": "select \ngroupindex||'/'||groupsize as \"Group\","
                          "\n--groupid,\nnetaddress as \"Announced Address\","
                          "\ncountry as \"Country\",\nversion as \"Version\","
                          "\ntotalstorage/1000000000 as \"Total Storage (GB)\", "
                          "\nusedstorage/1000000000 as \"Used Storage (GB)\","
                          "\ncontracting as \"Contracting\","
                          "\nconnectivity as \"Ports\","
                          "\nuptimeratio as \"Uptime\","
                          "\nto_timestamp(added) as \"Tracked Since\", "
                          "\nto_timestamp(lastsuccessfulscantime) as \"Last Successful Scan\","
                          "\npublickey \nfrom network.provider_list_view"
                          "\nwhere lastsuccessfulscantime >= unix_now()-3600*25*7"
                          "--to_timestamp(lastsuccessfulscantime) > now()-interval '1 week'"
                          "\nand (licensed=true or xaminer=true)"
                          "\norder by added desc",
                "format": "table",
            }
        ],
    }

    data = dumps(query)
    r = post(url, data=data, headers=headers)
    conn, c = create_connection('provider')
    if r.status_code == 200:
        r = r.json()
        r = r["results"]["A"]["frames"][0]["data"]["values"]
        for a in range(len(r[0])):
            provider_id, provider_ip, status, last_scanned = r[11][a], r[1][a], r[6][a], r[10][a]
            c.execute("INSERT OR REPLACE INTO provider (provider_id, provider_ip, status, last_scanned) "
                      "VALUES (?, ?, ?, ?)", (provider_id, provider_ip, status, last_scanned))
        conn.commit()

    print("Provider data updated.")


def build_alert_embed(user_id, provider_id, status, last_scanned):
    embed = Embed(color=Color.red())
    embed.add_field(name="Provider ID", value=f"`{provider_id}`", inline=False)
    embed.add_field(name="Status", value=f"`{status}`", inline=False)
    embed.add_field(name="Last Scanned", value=f"<t:{last_scanned}>", inline=False)
    embed.add_field(name=f"Alert registered by", value=f"<@{user_id}>")
    embed.add_field(name="Grafana Link", value=f"[Click Here to Visit]({build_provider_link(provider_id)})")
    return embed


def register_provider(guild_id, user_id, provider_id, notify, interval):
    conn, c = create_connection("provider")
    existing_data = c.execute("SELECT * FROM provider WHERE provider_id = ?", [provider_id]).fetchall()
    c.execute(
        "INSERT OR REPLACE INTO registered_providers (guild_id, user_id, provider_id, notify, interval, last_notified) "
        "VALUES (?, ?, ?, ?, ?, ?)", (guild_id, user_id, provider_id, notify, interval, 0))
    conn.commit()
    conn.close()
    embed = Embed(title=f"{'Successful Registration' if len(existing_data) != 0 else 'Updated Registration'}")
    embed.add_field(name="Provider ID", value=f"`{provider_id}`", inline=False)
    embed.add_field(name="Notify", value="Yes" if notify else "No", inline=False)
    embed.add_field(name="Interval", value=f"{interval} minute(s)", inline=False)
    return embed


def deregister_provider(guild_id, user_id, provider_id):
    conn, c = create_connection("provider")
    existing_data = c.execute("SELECT * FROM registered_providers WHERE provider_id = ? AND guild_id = ? AND user_id = ?",
                              [provider_id, guild_id, user_id]).fetchall()
    if len(existing_data) == 0:
        return Embed(title="De-registration Failed",
                     description=f"You don't currently have a provider with ID {provider_id} registered in this server.",
                     color=Color.red())
    c.execute("DELETE FROM registered_providers WHERE guild_id = ? AND user_id = ? AND provider_id = ?",
              (guild_id, user_id, provider_id))
    conn.commit()
    conn.close()
    embed = Embed(title="Successful De-registration",color=Color.red())
    embed.add_field(name="Provider ID", value=f"`{provider_id}`", inline=False)
    return embed


def build_provider_link(url):
    return f"https://grafana.scpri.me/d/Cg7V28sMk/provider-detail?var-provider={url}&kiosk=tv&orgId=1"
