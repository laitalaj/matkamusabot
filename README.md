# matkamusabot

A Telegram bot that queues Spotify songs based on shared location

## Quickstart

1. `pip install -r requirements.txt`
2. Set some environment variables:
    * `SPOTIFY_CLIENT_ID`: Client ID for Spotify API
    * `SPOTIFY_CLIENT_SECRET`: Client secret for Spotify API
    * `SPOTIFY_REDIRECT_URI`: URL to the callback endpoint of `login.py`,
    e.g. `http://127.0.0.1:5000/callback`
    * `TG_BOT_URL`: `https://t.me/your_bots_name_here?start=`
    * `TG_BOT_TOKEN`: Token for the Telegram bot
3. `python3 login.py`
4. In a separate shell, `python3 bot.py`
5. Navigate to the login service's root, log in with Spotify, add some songs with the `/add` command
and then send the bot your live location!
