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
        "notify integer, last_notified text, last_status text, private integer, "
        "UNIQUE (guild_id, user_id, provider_id))")
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


def get_offline_providers_for_alert():
    conn, c = create_connection('provider')
    providers = c.execute("SELECT "
                          "registered_providers.guild_id, "
                          "registered_providers.user_id, "
                          "registered_providers.provider_id, "
                          "provider.status, "
                          "registered_providers.notify, "
                          "guilds.alert_channel, "
                          "provider.last_scanned, "
                          "registered_providers.private "
                          "FROM registered_providers "
                          "INNER JOIN guilds ON registered_providers.guild_id = guilds.guild_id "
                          "INNER JOIN provider ON registered_providers.provider_id = provider.provider_id "
                          "WHERE provider.status != '1' AND guilds.enabled = 1 AND guilds.alert_channel != 0 "
                          "AND (date('now') >= "
                          "strftime('%Y-%m-%d %H:%M:%f', registered_providers.last_notified, '+24 hours'))").fetchall()
    report_offline = c.execute("SELECT registered_providers.guild_id, registered_providers.user_id, "
                               "registered_providers.provider_id, provider.status, registered_providers.notify, "
                               "guilds.alert_channel, provider.last_scanned "
                               "FROM registered_providers "
                               "INNER JOIN guilds ON registered_providers.guild_id = guilds.guild_id "
                               "INNER JOIN provider ON registered_providers.provider_id = provider.provider_id "
                               "WHERE provider.status != '1' AND guilds.enabled = 1 AND guilds.alert_channel != 0 "
                               "AND (date('now') >= "
                               "strftime('%Y-%m-%d %H:%M:%f', registered_providers.last_notified, '+24 hours'))").fetchall()
    conn.close()
    return providers


def get_online_providers_for_alert():
    conn, c = create_connection('provider')
    providers = c.execute("SELECT "
                          "registered_providers.guild_id, "
                          "registered_providers.user_id, "
                          "registered_providers.provider_id, "
                          "provider.status, "
                          "registered_providers.notify, "
                          "guilds.alert_channel, "
                          "provider.last_scanned, "
                          "registered_providers.last_status, "
                          "registered_providers.private "
                          "FROM registered_providers "
                          "INNER JOIN guilds on registered_providers.guild_id = guilds.guild_id "
                          "INNER JOIN provider on registered_providers.provider_id = provider.provider_id "
                          "WHERE provider.status = '1' AND guilds.enabled = 1 AND guilds.alert_channel != 0 "
                          "AND registered_providers.last_status != '1'").fetchall()
    conn.close()
    return providers


async def check_providers(client):
    print("Checking providers")

    offline_providers = get_offline_providers_for_alert()
    online_providers = get_online_providers_for_alert()

    conn, c = create_connection('provider')

    for p in offline_providers:
        guild_id, user_id, provider_id, status, notify, alert_channel, last_scanned, private = \
            p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7]
        status_text = "Passive" if status == "-1" else "Offline"
        print("Sending offline alert...")
        channel = client.get_channel(int(alert_channel))
        last_scanned = int(int(last_scanned) / 1000)
        embed = build_offline_alert_embed(user_id, provider_id, status_text, last_scanned)
        await channel.send(content=f"<@{user_id}>" if notify else None,
                           embed=embed)

        c.execute("UPDATE "
                  "registered_providers "
                  "SET last_notified = ?, "
                  "last_status = ? "
                  "WHERE provider_id = ? "
                  "AND guild_id = ? "
                  "AND user_id = ?",
                  (datetime.now(), status, provider_id, guild_id, user_id))

    for p in online_providers:
        guild_id, user_id, provider_id, status, notify, alert_channel, last_scanned, last_status, private = \
            p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8]

        print("Sending online alert...")
        channel = client.get_channel(int(alert_channel))
        embed = build_online_alert_embed(user_id, provider_id)
        await channel.send(content=f"<@{user_id}>" if notify else None,
                           embed=embed)

        c.execute("UPDATE registered_providers "
                  "SET last_status = ? "
                  "WHERE provider_id = ? "
                  "AND guild_id = ? "
                  "AND user_id = ?",
                  ("1", provider_id, guild_id, user_id))

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


def build_offline_alert_embed(user_id, provider_id, status, last_scanned):
    embed = Embed(color=Color.red())
    embed.add_field(name="Provider ID", value=f"`{provider_id}`", inline=False)
    embed.add_field(name="Status", value=f"`{status}`", inline=False)
    embed.add_field(name="Last seen online and active", value=f"<t:{last_scanned}>", inline=False)
    embed.add_field(name=f"Alert registered by", value=f"<@{user_id}>")
    embed.add_field(name="Grafana Link", value=f"[Click Here to Visit]({build_provider_link(provider_id)})")
    return embed


def build_online_alert_embed(user_id, provider_id):
    embed = Embed(color=Color.green())
    embed.add_field(name="Provider ID", value=f"`{provider_id}`", inline=False)
    embed.add_field(name="Status", value="Back Online!", inline=False)
    embed.add_field(name=f"Alert registered by", value=f"<@{user_id}>")
    embed.add_field(name="Grafana Link", value=f"[Click Here to Visit]({build_provider_link(provider_id)})")
    return embed


def register_provider(guild_id, user_id, provider_id, notify, private):
    conn, c = create_connection("provider")
    existing_data = c.execute("SELECT * FROM provider WHERE provider_id = ?", [provider_id]).fetchall()
    c.execute(
        "INSERT OR REPLACE INTO registered_providers (guild_id, user_id, provider_id, notify, private, last_notified) "
        "VALUES (?, ?, ?, ?, ?, ?)", (guild_id, user_id, provider_id, notify, private, 0))
    conn.commit()
    conn.close()
    embed = Embed(title=f"{'Successful Registration' if len(existing_data) != 0 else 'Updated Registration'}")
    embed.add_field(name="Provider ID", value=f"`{provider_id}`", inline=False)
    embed.add_field(name="Notify", value="Yes" if notify else "No", inline=False)
    embed.add_field(name="Private", value='Yes' if private else 'No', inline=False)
    return embed


def deregister_provider(guild_id, user_id, provider_id):
    conn, c = create_connection("provider")
    existing_data = c.execute(
        "SELECT * FROM registered_providers WHERE provider_id = ? AND guild_id = ? AND user_id = ?",
        [provider_id, guild_id, user_id]).fetchall()
    if len(existing_data) == 0:
        return Embed(title="De-registration Failed",
                     description=f"You don't currently have a provider with ID {provider_id} registered in this server.",
                     color=Color.red())
    c.execute("DELETE FROM registered_providers WHERE guild_id = ? AND user_id = ? AND provider_id = ?",
              (guild_id, user_id, provider_id))
    conn.commit()
    conn.close()
    embed = Embed(title="Successful De-registration", color=Color.red())
    embed.add_field(name="Provider ID", value=f"`{provider_id}`", inline=False)
    return embed


def list_providers(guild_id, user_id):
    conn, c = create_connection("provider")
    providers = c.execute("SELECT * FROM registered_providers WHERE guild_id = ? AND user_id = ?",
                          [guild_id, user_id]).fetchall()
    if len(providers) == 0:
        return Embed(title="No Providers Registered",
                     description=f"You don't currently have any providers registered in this server.",
                     color=Color.red())
    embed = Embed(title="Registered Providers", color=Color.red())
    for provider in providers:
        embed.add_field(name=provider[2],
                        value=f"Notify: {'Yes' if provider[3] == 1 else 'No'}\n"
                              f"Interval: {provider[4]} minute(s)", inline=False)
    return embed


def build_provider_link(url):
    return f"https://grafana.scpri.me/d/Cg7V28sMk/provider-detail?var-provider={url}&kiosk=tv&orgId=1"


def sql_test():
    conn, c = create_connection('provider')
    report_offline = c.execute("SELECT registered_providers.guild_id, registered_providers.user_id, "
                               "registered_providers.provider_id, provider.status, registered_providers.notify, "
                               "guilds.alert_channel, provider.last_scanned "
                               "FROM registered_providers "
                               "INNER JOIN guilds ON registered_providers.guild_id = guilds.guild_id "
                               "INNER JOIN provider ON registered_providers.provider_id = provider.provider_id "
                               "WHERE provider.status != '1' AND guilds.enabled = 1 AND guilds.alert_channel != 0 "
                               "AND (date('now') >= "
                               "strftime('%Y-%m-%d %H:%M:%f', registered_providers.last_notified, '+24 hours'))").fetchall()
    report_online = c.execute("SELECT "
                              "registered_providers.guild_id, "
                              "registered_providers.user_id, "
                              "registered_providers.provider_id, "
                              "provider.status, "
                              "registered_providers.notify, "
                              "guilds.alert_channel, "
                              "provider.last_scanned "
                              "FROM registered_providers "
                              "INNER JOIN guilds on registered_providers.guild_id = guilds.guild_id "
                              "INNER JOIN provider on registered_providers.provider_id = provider.provider_id "
                              "WHERE provider.status = '1' AND guilds.enabled = 1 AND guilds.alert_channel != 0 "
                              "AND registered_providers.last_status != '1'").fetchall()
    print(report_offline)
    print(report_online)


if __name__ == "__main__":
    sql_test()
