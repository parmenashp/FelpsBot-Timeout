import asyncio
from typing import TYPE_CHECKING, Awaitable
from datetime import datetime


if TYPE_CHECKING:
    from models.db import DataBase


class TimeoutTimer():

    def __init__(self, db: "DataBase", timeout_callback: Awaitable) -> None:
        self.loop = asyncio.get_event_loop()
        self.db = db
        self._timeout_callback = timeout_callback
        self._have_active = asyncio.Event()
        self._task = self.loop.create_task(self.dispatch_timers())

    async def wait_for_active_timers(self):
        timer = await self.db.get_next_active_timeout()
        if timer is not None:
            self._have_active.set()
            return timer

        self._have_active.clear()
        self._current_to = None
        await self._have_active.wait()
        return await self.db.get_next_active_timeout()

    async def dispatch_timers(self):
        try:
            while True:
                to = self._current_to = await self.wait_for_active_timers()
                if not to:
                    continue
                now = datetime.utcnow()

                if to.next_timeout_time >= now:
                    await asyncio.sleep(to.next_timeout_seconds)

                await self._timeout_callback(to)
        except asyncio.CancelledError:
            raise
        except (OSError):
            self._task.cancel()
            self._task = self.loop.create_task(self.dispatch_timers())

    async def unlock_timer(self):
        self._have_active.set()

    async def restart_timer(self):
        self._task.cancel()
        self._task = self.loop.create_task(self.dispatch_timers())
