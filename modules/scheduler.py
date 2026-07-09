import asyncio
import logging
from datetime import datetime, timedelta, timezone

from discord.ext import commands

from database import repository
from database.schemas import TimerModel

logger = logging.getLogger("onetap.scheduler")

# Only actively sleep on timers due within this window; longer ones sit in the DB
# and are picked up once they come into range. Bounds a single asyncio.sleep.
MAX_SLEEP_DAYS = 40


class Scheduler(commands.Cog):
    """Generic, persistent job scheduler.

    One background task sleeps until the next due timer, then dispatches
    ``on_<event>_timer_complete``. Timers live in the database, so pending jobs
    survive restarts; the loop is idle (zero CPU) whenever nothing is due.
    """

    def __init__(self, bot):
        self.bot = bot
        self._have_data = asyncio.Event()
        self._current_timer: TimerModel | None = None
        self._task: asyncio.Task | None = None

    async def cog_load(self):
        self._task = self.bot.loop.create_task(self._dispatch_loop())

    def cog_unload(self):
        if self._task:
            self._task.cancel()

    # ---- public API ----
    async def create_timer(self, event: str, expires_at: datetime, payload: dict,
                           *, guild_id: int | None = None) -> TimerModel:
        """Schedule `event` to fire at `expires_at` with `payload`."""
        now = datetime.now(timezone.utc)
        timer = await repository.create_timer(event, expires_at, payload, now, guild_id=guild_id)

        # Wake the loop if it's idle and this fits the active window.
        if (expires_at - now).total_seconds() <= MAX_SLEEP_DAYS * 86400:
            self._have_data.set()

        # If this timer is sooner than the one we're currently sleeping on, restart.
        if self._current_timer and expires_at < self._current_timer.expires_at:
            self._restart()
        return timer

    async def cancel_timer(self, event: str, **payload_match) -> int:
        """Delete timers of `event` whose payload matches all given fields."""
        removed = 0
        restart = False
        for timer in await repository.get_timers_by_event(event):
            if all(timer.payload.get(k) == v for k, v in payload_match.items()):
                await repository.delete_timer(timer.id)
                removed += 1
                if self._current_timer and self._current_timer.id == timer.id:
                    restart = True
        if restart:
            self._restart()
        return removed

    # ---- internals ----
    def _restart(self):
        if self._task:
            self._task.cancel()
        self._task = self.bot.loop.create_task(self._dispatch_loop())

    async def _wait_for_next_timer(self) -> TimerModel:
        """Return the next due timer, blocking (idle) until one exists."""
        horizon = datetime.now(timezone.utc) + timedelta(days=MAX_SLEEP_DAYS)
        timer = await repository.get_next_timer(horizon)
        if timer is not None:
            self._have_data.set()
            return timer

        # Nothing scheduled: sleep on the event until create_timer wakes us.
        self._have_data.clear()
        self._current_timer = None
        await self._have_data.wait()
        horizon = datetime.now(timezone.utc) + timedelta(days=MAX_SLEEP_DAYS)
        return await repository.get_next_timer(horizon)

    async def _dispatch_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                timer = self._current_timer = await self._wait_for_next_timer()
                now = datetime.now(timezone.utc)
                if timer.expires_at > now:
                    await asyncio.sleep((timer.expires_at - now).total_seconds())
                await self._call_timer(timer)
            except asyncio.CancelledError:
                raise  # a reschedule/unload cancelled us — let it stop cleanly
            except Exception:
                # Never hot-loop: log and back off before trying again.
                logger.exception("Error in scheduler dispatch loop; backing off")
                await asyncio.sleep(5)

    async def _call_timer(self, timer: TimerModel):
        await repository.delete_timer(timer.id)
        self._current_timer = None
        logger.debug("Firing timer %s (%s)", timer.id, timer.event)
        self.bot.dispatch(f"{timer.event}_timer_complete", timer)


async def setup(bot):
    await bot.add_cog(Scheduler(bot))
