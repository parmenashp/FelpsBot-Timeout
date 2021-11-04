import asyncio
from typing import TYPE_CHECKING, Awaitable
from datetime import datetime
import logging

if TYPE_CHECKING:
    from models.db import DataBase

logger = logging.getLogger('felpstimeout.timer')


class TimeoutTimer():

    def __init__(self, db: "DataBase", timeout_callback: Awaitable) -> None:
        self.loop = asyncio.get_event_loop()
        self.db = db
        self._timeout_callback = timeout_callback
        self._have_active = asyncio.Event()

    async def start(self):
        self._task = self.loop.create_task(self.dispatch_timers())

    async def wait_for_active_timers(self):
        logger.debug("Chamado o wait_for_active_timers")
        timer = await self.db.get_next_active_timeout()
        if timer is not None:
            self._have_active.set()
            return timer

        self._have_active.clear()
        self._current_to = None
        logger.debug('Nenhum timeout ativo, esperando um novo.')
        await self._have_active.wait()
        return await self.db.get_next_active_timeout()

    async def dispatch_timers(self):
        logger.debug('Dispatch_timers iniciado.')
        try:
            while True:
                to = self._current_to = await self.wait_for_active_timers()
                if not to:
                    continue
                now = datetime.now()

                next_to_time = to.next_timeout_time

                if next_to_time >= now:
                    segundos = (next_to_time - now).total_seconds()
                    logger.debug(f"Timeout agendado, dormindo por {segundos} segundos...")
                    await asyncio.sleep(segundos)

                logger.debug("Chamando callback do timer")
                await self._timeout_callback(to)
        except asyncio.CancelledError:
            raise
        except (OSError):
            self._task.cancel()
            self._task = self.loop.create_task(self.dispatch_timers())
        except Exception:
            logger.exception("Erro no dispatch_timers")

    async def unlock_timer(self):
        self._have_active.set()
        logger.debug("Timer desbloqueado")

    async def restart_timer(self):
        self._task.cancel()
        self._task = self.loop.create_task(self.dispatch_timers())
        logger.debug("Timer resetado")


# TODO fazer outros timer pra quando acabar o timeout
