# meta developer: @Wers1xx

import asyncio
import re
from .. import loader, utils


@loader.tds
class AutoRelationsMod(loader.Module):
    """Автоматическая прокачка отношений в чатах с ботом."""

    strings = {
        "name": "AutoRelations",
        "no_chat": '<emoji document_id=5210952531676504517>❌</emoji> <b>Используй команду в чате, где нужно качать отношения.</b>',
        "started": '<emoji document_id=5145427681680032825>🚀</emoji> <b>Автопрокачка запущена в этом чате.</b>',
        "stopped": '<emoji document_id=5352734663452430904>💥</emoji> <b>Автопрокачка остановлена.</b>',
        "already_running": '<emoji document_id=5352746835389737564>❗️</emoji> <b>Автопрокачка уже запущена в этом чате.</b>',
        "not_running": '<emoji document_id=5334544901428229844>ℹ️</emoji> <b>Автопрокачка не запущена.</b>',
    }

    def __init__(self):
        self._tasks = {}
        self._counters = {}
        self._current_action = {}

    async def client_ready(self, client, db):
        self._client = client

    def _parse_cd(self, cd_text: str) -> int:
        cd_text = cd_text.lower().replace("ч.", "ч").replace("м.", "м").strip()
        total = 0
        hours_match = re.search(r'(\d+)\s*ч', cd_text)
        mins_match = re.search(r'(\d+)\s*м', cd_text)
        if hours_match:
            total += int(hours_match.group(1)) * 3600
        if mins_match:
            total += int(mins_match.group(1)) * 60
        return total if total > 0 else 60

    def _parse_actions(self, text: str) -> list:
        available = []
        pattern = r'\[(\d+)\]\s*(✅|🔐|🔒)\s*•\s*«([^»]+)»\s*\|\s*🔥\+(\d+)\|([^\n]+)'
        matches = re.findall(pattern, text)
        for num, icon, name, fire, cd in matches:
            if icon == "✅":
                cd_seconds = self._parse_cd(cd.strip())
                available.append({
                    "num": int(num),
                    "name": name.strip(),
                    "fire": int(fire),
                    "cd_seconds": cd_seconds,
                    "cd_text": cd.strip(),
                })
        return available

    async def _get_available_action(self, chat_id: int) -> dict | None:
        await self._client.send_message(chat_id, ".отн действия")
        await asyncio.sleep(2.5)

        messages = await self._client.get_messages(chat_id, limit=8)
        for msg in messages:
            if msg.out:
                continue
            text = msg.raw_text or ""
            if "Обычные действия" in text or "Сделать комплимент" in text:
                actions = self._parse_actions(text)
                if actions:
                    actions.sort(key=lambda x: x["num"])
                    return actions[-1]
        return None

    async def _auto_loop(self, chat_id: int):
        action = None
        self._counters.setdefault(chat_id, 0)

        while True:
            try:
                task = self._tasks.get(chat_id)
                if task is None or task.cancelled():
                    break

                if action is None:
                    action = await self._get_available_action(chat_id)
                    if not action:
                        await asyncio.sleep(30)
                        continue
                    self._current_action[chat_id] = action["name"]
                    self._counters[chat_id] = 0

                cmd = f".отн {action['name'].lower()}"
                await self._client.send_message(chat_id, cmd)
                self._counters[chat_id] += 1

                if self._counters[chat_id] >= 10:
                    self._counters[chat_id] = 0
                    action = None
                    await asyncio.sleep(2)
                    continue

                await asyncio.sleep(action["cd_seconds"] + 3)

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(10)

    @loader.command()
    async def sst(self, message):
        """Запустить автопрокачку отношений в этом чате."""
        chat_id = message.chat_id
        if chat_id in self._tasks and not self._tasks[chat_id].done():
            await utils.answer(message, self.strings("already_running"), parse_mode="html")
            return

        self._tasks[chat_id] = asyncio.create_task(self._auto_loop(chat_id))
        self._counters[chat_id] = 0
        await utils.answer(message, self.strings("started"), parse_mode="html")

    @loader.command()
    async def sststop(self, message):
        """Остановить автопрокачку отношений в этом чате."""
        chat_id = message.chat_id
        task = self._tasks.get(chat_id)
        if task and not task.done():
            task.cancel()
            self._tasks.pop(chat_id, None)
            self._counters.pop(chat_id, None)
            self._current_action.pop(chat_id, None)
            await utils.answer(message, self.strings("stopped"), parse_mode="html")
        else:
            await utils.answer(message, self.strings("not_running"), parse_mode="html")

    async def on_unload(self):
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        self._counters.clear()
        self._current_action.clear()