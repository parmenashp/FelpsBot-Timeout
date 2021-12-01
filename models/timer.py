import asyncio
from typing import TYPE_CHECKING, Awaitable
from datetime import datetime
import logging

if TYPE_CHECKING:
    from models.db import DataBase

logger = logging.getLogger('felpstimeout.timer')


# can only asyncio.sleep for up to ~48 days reliably
# so we're gonna cap it off at 40 days
# see: http://bugs.python.org/issue20493
MAX_SLEEP_TIME = 3456000


class TimeoutTimer():

    def __init__(self, db: "DataBase", timeout_callback: Awaitable, timeout_end_callback: Awaitable) -> None:
        self.loop = asyncio.get_event_loop()
        self.db = db
        self._timeout_callback = timeout_callback
        self._timeout_end_callback = timeout_end_callback
        self._has_active = asyncio.Event()
        self._has_ending = asyncio.Event()

    async def start(self):
        self._task = self.loop.create_task(self.dispatch_timers())
        self._task_end = self.loop.create_task(self.dispatch_end_timers())

    async def wait_for_active_timers(self):
        logger.debug("Chamado o wait_for_active_timers")
        timer = await self.db.get_next_active_timeout()
        if timer is not None:
            self._has_active.set()
            return timer

        self._has_active.clear()
        logger.debug('Nenhum timeout ativo, esperando um novo.')
        await self._has_active.wait()
        return await self.db.get_next_active_timeout()

    async def wait_for_ending_timers(self):
        logger.debug("Chamado o wait_for_ending_timers")
        timer = await self.db.get_next_ending_timeout()
        if timer is not None:
            self._has_ending.set()
            return timer

        self._has_ending.clear()
        logger.debug('Nenhum timeout acabando, esperando um novo.')
        await self._has_active.wait()
        return await self.db.get_next_ending_timeout()

    async def dispatch_timers(self):
        logger.debug('Dispatch_timers iniciado.')
        try:
            while True:
                to = await self.wait_for_active_timers()
                if not to:
                    continue
                now = datetime.utcnow()

                next_to_time = to.next_timeout_time

                if next_to_time >= now:
                    segundos = (next_to_time - now).total_seconds()
                    logger.debug(f"Timeout agendado, dormindo por {segundos} segundos...")
                    await asyncio.sleep(segundos)

                # TODO: fazer um aviso quando um timeout estiver com o "tempo atrasado", ou seja, não teve que dormir

                logger.debug("Chamando callback do timeout timer")
                await self._timeout_callback(to)
        except asyncio.CancelledError:
            raise
        except (OSError):
            self._task.cancel()
            self._task = self.loop.create_task(self.dispatch_timers())
        except Exception:
            logger.exception("Erro no dispatch_timers")

    async def dispatch_end_timers(self):
        logger.debug('Dispatch_end_timers iniciado.')
        try:
            while True:
                to = await self.wait_for_ending_timers()
                if not to:
                    continue
                now = datetime.utcnow()
                end_to_time = to.finish_at
                seconds_remaining = (end_to_time - now).total_seconds()

                if end_to_time >= now:
                    while seconds_remaining > 0:
                        if seconds_remaining > MAX_SLEEP_TIME:  # explicação na linha linha 12
                            logger.debug(f"Fim de timeout agendado, dormindo por 40 dias...")
                            await asyncio.sleep(MAX_SLEEP_TIME)
                            seconds_remaining -= MAX_SLEEP_TIME
                        else:
                            logger.debug(f"Fim de timeout agendado, dormindo por {seconds_remaining} segundos...")
                            await asyncio.sleep(seconds_remaining)
                            break

                logger.debug("Chamando callback de end timer")
                await self._timeout_end_callback(to)
        except asyncio.CancelledError:
            raise
        except (OSError):
            self._task_end.cancel()
            self._task_end = self.loop.create_task(self.dispatch_end_timers())
        except Exception:
            logger.exception("Erro no dispatch_end_timers")

    async def unlock_timers(self):
        self._has_active.set()
        self._has_ending.set()
        logger.debug("Timers desbloqueados")

    async def restart_timers(self):
        self._task.cancel()
        self._task_end.cancel()
        self._task = self.loop.create_task(self.dispatch_timers())
        self._task_end = self.loop.create_task(self.dispatch_end_timers())
        logger.debug("Timers resetados")
