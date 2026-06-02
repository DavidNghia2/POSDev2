from __future__ import annotations

import asyncio
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from cloud.supabase_client import get_access_token, get_supabase_settings
from database import db


class RealtimeSyncWorker(QObject):
    dirty = pyqtSignal(object)
    status = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, store_id: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.store_id = store_id
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._stop_requested = False

    @pyqtSlot()
    def run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run())
        except Exception as error:
            self.status.emit(f"Realtime sync stopped: {error}")
        finally:
            try:
                self._cancel_pending_tasks()
                self._loop.close()
            finally:
                self._loop = None
                self.finished.emit()

    @pyqtSlot()
    def stop(self) -> None:
        self._stop_requested = True
        if self._loop is not None and self._stop_event is not None:
            self._loop.call_soon_threadsafe(self._stop_event.set)

    async def _run(self) -> None:
        try:
            from realtime.types import RealtimePostgresChangesListenEvent
            from supabase import create_async_client
        except ImportError as error:
            self.status.emit(f"Realtime unavailable: {error}")
            return

        settings = get_supabase_settings()
        client = await create_async_client(settings.url, settings.anon_key)
        token = get_access_token()
        if token:
            await client.realtime.set_auth(token)

        self._stop_event = asyncio.Event()
        if self._stop_requested:
            self._stop_event.set()

        channel = client.channel(f"pos-store-{self.store_id}")
        event_filter = f"store_id=eq.{self.store_id}"

        def product_changed(payload: Any) -> None:
            try:
                if db.should_ignore_product_realtime_event(payload):
                    return
            except Exception:
                pass
            self.dirty.emit({"products"})

        def sale_changed(_payload: Any) -> None:
            self.dirty.emit({"sales"})

        for event in (
            RealtimePostgresChangesListenEvent.Insert,
            RealtimePostgresChangesListenEvent.Update,
        ):
            channel.on_postgres_changes(
                event,
                callback=product_changed,
                schema="public",
                table="products",
                filter=event_filter,
            )
            channel.on_postgres_changes(
                event,
                callback=sale_changed,
                schema="public",
                table="sales",
                filter=event_filter,
            )

        subscribed_once = False
        disconnected_since_subscribe = False

        def on_subscribe(state: Any, error: Exception | None) -> None:
            nonlocal subscribed_once, disconnected_since_subscribe
            state_value = str(getattr(state, "value", state))
            if state_value == "SUBSCRIBED":
                catch_up = not subscribed_once or disconnected_since_subscribe
                subscribed_once = True
                disconnected_since_subscribe = False
                self.status.emit("Realtime sync connected.")
                if catch_up:
                    self.dirty.emit({"products", "sales"})
                return

            disconnected_since_subscribe = True
            if error is not None:
                self.status.emit(f"Realtime sync {state_value.lower()}: {error}")
            else:
                self.status.emit(f"Realtime sync {state_value.lower()}.")

        await channel.subscribe(on_subscribe)

        try:
            was_connected = bool(client.realtime.is_connected)
            while self._stop_event is not None and not self._stop_event.is_set():
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
                connected = bool(client.realtime.is_connected)
                if not connected and was_connected:
                    disconnected_since_subscribe = True
                    self.status.emit("Realtime sync disconnected; waiting to reconnect.")
                elif connected and not was_connected and disconnected_since_subscribe:
                    self.status.emit("Realtime sync reconnected; catching up.")
                    self.dirty.emit({"products", "sales"})
                    disconnected_since_subscribe = False
                was_connected = connected
        finally:
            try:
                await client.remove_channel(channel)
            except Exception:
                try:
                    await channel.unsubscribe()
                except Exception:
                    pass
            try:
                await client.realtime.close()
            except Exception:
                pass

    def _cancel_pending_tasks(self) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return

        pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
        if not pending_tasks:
            return

        for task in pending_tasks:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
        loop.run_until_complete(loop.shutdown_asyncgens())
