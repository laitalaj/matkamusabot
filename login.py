import asyncio
import time
import uuid
import os

import tekore as tk
from quart import Quart, request, redirect

import utils

TG_URI = os.environ["TG_BOT_URL"]

LOGIN_CLEAR_INTERVAL = 600
LOGIN_MAX_AGE = 300

queries = utils.build_queries()

cred = tk.Credentials(*tk.config_from_environment())

auths = {}

app = Quart(__name__)


async def init_db():
    async with utils.connect(True) as connection:
        await queries.init(connection)


async def clear_logins():
    while True:
        await asyncio.sleep(LOGIN_CLEAR_INTERVAL)

        async with utils.connect(True) as connection:
            await queries.clear_old_logins(connection, maxage=LOGIN_MAX_AGE)

        now = time.time()
        old_auths = [s for s, t in auths.items() if t < now - LOGIN_MAX_AGE]
        for state in old_auths:
            auths.pop(state)


@app.before_serving
async def startup():
    await init_db()
    app.add_background_task(clear_logins)


@app.route("/")
def login():
    scope = utils.get_scope()
    auth = tk.UserAuth(cred, scope)
    auths[auth.state] = time.time()
    return redirect(auth.url, 307)


@app.route("/callback")
async def callback():
    code = request.args["code"]
    state = request.args["state"]

    if state not in auths:
        return "No auth for that state!", 400
    t = auths.pop(state)
    if t < time.time() - LOGIN_MAX_AGE:
        return "Login timed out", 400

    uniq_id = str(uuid.uuid4())

    async with utils.connect(True) as connection:
        await queries.create_login(connection, uuid=uniq_id, code=code, state=state)

    return redirect(TG_URI + uniq_id, 307)


if __name__ == "__main__":
    app.run("127.0.0.1", 5000)
