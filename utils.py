import contextlib

import aiosql
import aiosqlite
import tekore as tk

CONNECTION_STRING = "database.db"


def build_queries():
    return aiosql.from_path("./sql", "aiosqlite")


@contextlib.asynccontextmanager
async def connect(commit=False):
    async with aiosqlite.connect(CONNECTION_STRING) as connection:
        yield connection
        if commit:
            await connection.commit()


def get_scope():
    return tk.scope.user_read_playback_state + tk.scope.user_modify_playback_state
