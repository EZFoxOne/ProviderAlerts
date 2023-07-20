# ProviderAlerts
A simple Discord bot allowing users to register their provider IDs to receive pings in a discord server's channel when their provider is not 'Active'

*Installation Instructions*

1) Clone the repo
2) Set your bot token in the .env file
3) Create an Oauth URL with the following permissions
   - Send Messages
   - Embed Links
   - Attach Files
4) Invite the bot to your server

*Commands*

 - /enable-provider-alerts
   - enable/disable the bot
 - /set-alert-channel
   - run in the channel you wish to receive alerts
 - /register-provider
   - register a provider for alerts
     - Optional: notify allows you to turn pings on or off for alerts
     - Optional: set a custom interval for how often you should be alerted during consistent downtime
     - **NOTE**: registering an existing provider will update its settings
 - /deregister-provider -- remove a provider from alerts
