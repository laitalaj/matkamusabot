import os
import re
import time

from geopy import distance as dist
import tekore as tk
from telebot.async_telebot import AsyncTeleBot
from telebot import util as tbutils

import utils

DEFAULT_RADIUS = 5
SONG_TIMEOUT = 60 * 60 * 60


class LocationTransaction:
    def __init__(self):
        self.location = None
        self.radius = None
        self.song = None

    def validate(self):
        if self.radius is None:
            self.radius = DEFAULT_RADIUS
        return self.location is not None and self.song is not None


queries = utils.build_queries()
bot = AsyncTeleBot(os.environ["TG_BOT_TOKEN"])

# Synchronous on purpose:
# "While asynchronous Credentials is supported,
# it is worth considering that concurrently refreshing tokens may lead to multiple refreshes for one token.
# Synchronous credentials clients are recommended."
credentials = tk.RefreshingCredentials(*tk.config_from_environment())

# Doing quite a lot of dirty global modifications in this atm,
# but it's All Fine as we're async :^)
global_spotify = None
spotifys = {}
transactions = {}
locations = None
timeouts = {}


async def add_user(tgid, uuid):
    async with utils.connect(True) as connection:
        res = await queries.get_login(connection, uuid=uuid)
        if res is None:
            return False

        code, state = res
        auth = tk.UserAuth(credentials, utils.get_scope())
        auth.state = (
            state  # We have already checked that this is valid when inserting to the DB
        )

        try:
            token = auth.request_token(code, state)
        except tk.ClientError | tk.ServerError:
            return False

        spotifys[tgid] = tk.Spotify(token, asynchronous=True)
        return True


async def get_spotify(tgid, chatid):
    if tgid in spotifys:
        return spotifys[tgid]
    else:
        await bot.send_message(chatid, "No spotify linked! Please log in again.")
        return None


def get_global_spotify():
    global global_spotify
    if global_spotify is None:
        global_spotify = tk.Spotify(
            credentials.request_client_token(), asynchronous=True
        )
    return global_spotify


async def get_locations():
    global locations
    if locations is None:
        async with utils.connect() as connection:
            locations = await queries.get_locations(connection)
    return locations


async def create_location(tgid, lat, lon, radius, song):
    if locations is not None:
        locations.append(
            (tgid, lat, lon, radius, song["id"], song["name"], song["artist"])
        )
    async with utils.connect(True) as connection:
        await queries.create_location(
            connection,
            tgid=tgid,
            lat=lat,
            lon=lon,
            radius=radius,
            songid=song["id"],
            songname=song["name"],
            songartist=song["artist"],
        )


@bot.message_handler(commands=["start"])
async def start(message):
    parts = message.text.split()

    if len(parts) > 1:
        tgid = message.from_user.id
        uuid = parts[1]
        success = await add_user(tgid, uuid)
        res = "Ready!" if success else "Invalid UUID or failed auth!"
    else:
        res = "No UUID given! :<"

    await bot.send_message(message.chat.id, res)


@bot.message_handler(commands=["queue"])
async def queue(message):
    spotify = await get_spotify(message.from_user.id, message.chat.id)
    if spotify is None:
        return
    await spotify.playback_queue_add("spotify:track:1LL7vVZ1cKdIbMsw5TWTc7")
    await bot.send_message(message.chat.id, "Enjoy!")


@bot.message_handler(commands=["list"])
async def list(message):
    locations = await get_locations()
    msg = "\n".join(
        f"({lat:.5f}, {lon:.5f}): {artist} - {name} ({radius}km)"
        for _, lat, lon, radius, _, name, artist in locations
    )
    msgs = tbutils.smart_split(msg)
    for m in msgs:
        await bot.send_message(message.chat.id, m)


@bot.message_handler(commands=["add"])
async def add_location(message):
    transactions[message.from_user.id] = LocationTransaction()
    await bot.send_message(
        message.chat.id,
        "Adding a song to a location. Send me a /done when you're ready!",
    )


@bot.message_handler(commands=["done"])
async def finalize_transaction(message):
    if message.from_user.id not in transactions:
        await bot.send_message(message.chat.id, "No transaction in progress!")
        return

    transaction = transactions[message.from_user.id]
    if not transaction.validate():
        await bot.send_message(
            message.chat.id, "I need you to give me a location and a song!"
        )
        return

    transaction = transactions.pop(message.from_user.id)
    await create_location(
        message.from_user.id,
        transaction.location[0],
        transaction.location[1],
        transaction.radius,
        transaction.song,
    )
    await bot.send_message(message.chat.id, f"Song added at {transaction.location}!")


@bot.message_handler(regexp=r"^\d+(\.\d+)?$")
async def set_radius(message):
    if message.from_user.id in transactions:
        transactions[message.from_user.id].radius = float(message.text)
        await bot.send_message(
            message.chat.id,
            f"Set the radius to {transactions[message.from_user.id].radius} km!",
        )


LOCATION_RE = r"^\((?P<lat>\d+(\.\d+)?), (?P<lon>\d+(\.\d+)?)\)$"


@bot.message_handler(regexp=LOCATION_RE)
async def set_location(message):
    if message.from_user.id in transactions:
        match = re.match(LOCATION_RE, message.text)
        lat = float(match.group("lat"))
        lon = float(match.group("lon"))
        transactions[message.from_user.id].location = (lat, lon)
        await bot.send_message(
            message.chat.id,
            f"Set the location to {transactions[message.from_user.id].location}!",
        )


SONG_RE = r"^https://open.spotify.com/track/(?P<id>[a-zA-Z0-9]+)(\?.*)?$"


@bot.message_handler(regexp=SONG_RE)
async def set_song(message):
    if message.from_user.id in transactions:
        spotify = get_global_spotify()
        match = re.match(SONG_RE, message.text)
        song_id = match.group("id")
        try:
            track = await spotify.track(song_id)
        except tk.ClientError:
            await bot.send_message(
                message.chat.id, "Couldn't find a track with that ID!"
            )
            return

        transactions[message.from_user.id].song = {
            "id": "spotify:track:" + song_id,
            "name": track.name,
            "artist": track.artists[0].name,
        }
        await bot.send_message(
            message.chat.id, f"Set the song to {track.name} by {track.artists[0].name}!"
        )


async def get_nearby_songs(lat, lon):
    locs = await get_locations()
    nearby = []
    for _, loc_lat, loc_lon, radius, songid, _, _ in locs:
        if dist.distance((lat, lon), (loc_lat, loc_lon)).km < radius:
            nearby.append(songid)
    return nearby


def get_timeouts(tgid):
    if tgid not in timeouts:
        timeouts[tgid] = {}
    return timeouts[tgid]


def is_timed_out(tgid, song):
    timeouts = get_timeouts(tgid)
    return song in timeouts and timeouts[song] > time.time()


def add_timeout(tgid, song):
    timeouts = get_timeouts(tgid)
    timeouts[song] = time.time() + SONG_TIMEOUT


async def queue_nearby_songs(tgid, chatid, loc):
    spotify = await get_spotify(tgid, chatid)
    if spotify is None:
        return False

    lat, lon = loc.latitude, loc.longitude
    nearby = await get_nearby_songs(lat, lon)
    for song in nearby:
        if not is_timed_out(tgid, song):
            await spotify.playback_queue_add(song)
            add_timeout(tgid, song)
    return True


@bot.message_handler(content_types=["location"])
async def location(message):
    await queue_nearby_songs(message.from_user.id, message.chat.id, message.location)


@bot.edited_message_handler(content_types=["location"])
async def location_update(message):
    await queue_nearby_songs(message.from_user.id, message.chat.id, message.location)


if __name__ == "__main__":
    import asyncio

    asyncio.run(bot.infinity_polling(request_timeout=300))
