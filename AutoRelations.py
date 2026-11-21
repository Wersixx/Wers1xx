# meta developer: @Wers1xx

import asyncio
import re
from .. import loader, utils
from telethon.tl.types import Message


@loader.tds
class AutoRelationsMod(loader.Module):
    """Автоматическая прокачка отношений в чатах с ботом."""

    strings = {
        "name": "AutoRelations",
        "started": '<emoji document_id=5145427681680032825>🚀</emoji> <b>Автопрокачка запущена в этом чате.</b>',
        "stopped": '<emoji document_id=5352734663452430904>💥</emoji> <b>Автопрокачка остановлена.</b>',
        "already_running": '<emoji document_id=5352746835389737564>❗️</emoji> <b>Автопрокачка уже запущена в этом чате.</b>',
        "not_running": '<emoji document_id=5334544901428229844>ℹ️</emoji> <b>Автопрокачка не запущена.</b>',
        "names_not_found": '<emoji document_id=5210952531676504517>❌</emoji> <b>Не удалось получить ники из профиля. Убедись, что у тебя есть пара в боте.</b>',
        "fetching_names": '<emoji document_id=5334544901428229844>ℹ️</emoji> <b>Получаю информацию о ваших никах...</b>',
    }

    def __init__(self):
        self._tasks = {}
        self._counters = {}
        self._current_action = {}
        self._my_name = None
        self._partner_name = None

    async def client_ready(self, client, db):
        self._client = client

    def _parse_time(self, time_str: str) -> int:
        time_str = time_str.lower().replace("ч.", "ч").replace("м.", "м").replace("с.", "с").strip()
        total = 0
        hours_match = re.search(r'(\d+)\s*ч', time_str)
        mins_match = re.search(r'(\d+)\s*м', time_str)
        secs_match = re.search(r'(\d+)\s*с', time_str)
        
        if hours_match:
            total += int(hours_match.group(1)) * 3600
        if mins_match:
            total += int(mins_match.group(1)) * 60
        if secs_match:
            total += int(secs_match.group(1))
            
        return total if total > 0 else 60

    async def _fetch_names(self, chat_id: int):
        await self._client.send_message(chat_id, ".отн я")
        await asyncio.sleep(3)
        
        messages = await self._client.get_messages(chat_id, limit=5)
        for msg in messages:
            if msg.out:
                continue
            text = msg.raw_text or ""
            if "Твоя половинка:" in text:
                partner_match = re.search(r'Твоя половинка:\s*\n?([^\n]+)', text)
                if partner_match:
                    partner_raw = partner_match.group(1).strip()
                    clean_partner = re.sub(r'[^\w\s]', '', partner_raw.split('#')[0]).strip()
                    if clean_partner:
                        self._partner_name = clean_partner.split()[0]

                header_match = re.search(r'([^\n]+)\n?[^\n]*Твоя половинка', text)
                if header_match:
                    raw_header = header_match.group(1)
                    clean_header = re.sub(r'[^\w\s]', '', raw_header.split('#')[0]).strip()
                    if clean_header:
                        self._my_name = clean_header.split()[0]

                if self._my_name and self._partner_name:
                    return True
        return False

    def _parse_actions(self, text: str) -> list:
        available = []
        pattern = r'\[(\d+)\]\s*(✅|🔐|🔒)\s*•\s*«([^»]+)»'
        matches = re.findall(pattern, text)
        for num, icon, name in matches:
            if icon == "✅":
                available.append({
                    "num": int(num),
                    "name": name.strip(),
                })
        return available

    def _split_sections(self, text: str) -> tuple:
        premium_marker = "Доступно только с премиум-статусом"
        if premium_marker in text:
            parts = text.split(premium_marker, 1)
            return parts[0], parts[1]
        return text, ""

    def _parse_cd_from_text(self, text: str, num: int) -> int:
        pattern = rf'\[{num}\]\s*(✅|🔐|🔒)\s*•\s*«[^»]+»\s*\|\s*🔥\+(\d+)\|([^\n]+)'
        match = re.search(pattern, text)
        if match:
            return self._parse_time(match.group(3).strip())
        return 0

    async def _get_available_action(self, chat_id: int) -> dict | None:
        await self._client.send_message(chat_id, ".отн действия")
        await asyncio.sleep(2.5)

        messages = await self._client.get_messages(chat_id, limit=8)
        for msg in messages:
            if msg.out:
                continue
            text = msg.raw_text or ""
            if "Обычные действия" not in text and "Сделать комплимент" not in text:
                continue

            regular_text, premium_text = self._split_sections(text)

            premium_actions = self._parse_actions(premium_text) if premium_text else []
            if premium_actions:
                premium_actions.sort(key=lambda x: x["num"])
                chosen = premium_actions[-1]
                cd_seconds = self._parse_cd_from_text(premium_text, chosen["num"])
                chosen["cd_seconds"] = cd_seconds if cd_seconds else 60
                chosen["premium"] = True
                return chosen

            regular_actions = self._parse_actions(regular_text)
            if regular_actions:
                regular_actions.sort(key=lambda x: x["num"])
                chosen = regular_actions[-1]
                cd_seconds = self._parse_cd_from_text(regular_text, chosen["num"])
                chosen["cd_seconds"] = cd_seconds if cd_seconds else 60
                chosen["premium"] = False
                return chosen

        return None

    async def _check_bot_response(self, chat_id: int) -> int:
        await asyncio.sleep(1.5)
        messages = await self._client.get_messages(chat_id, limit=3)
        for msg in messages:
            if msg.out:
                continue
            text = msg.raw_text or ""
            match = re.search(r'подождите ещё\s*([\dчмс\.\s]+)', text, re.IGNORECASE)
            if match:
                return self._parse_time(match.group(1))
        return 0

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
                
                cooldown_error = await self._check_bot_response(chat_id)
                
                if cooldown_error > 0:
                    await asyncio.sleep(cooldown_error + 3)
                    continue
                
                self._counters[chat_id] += 1

                if self._counters[chat_id] >= 10:
                    self._counters[chat_id] = 0
                    action = None
                    await asyncio.sleep(2)
                    continue

                await asyncio.sleep(action["cd_seconds"] + 5)

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

        if not self._my_name or not self._partner_name:
            await utils.answer(message, self.strings("fetching_names"), parse_mode="html")
            
            success = await self._fetch_names(chat_id)
            if not success:
                await asyncio.sleep(2)
                success = await self._fetch_names(chat_id)
                if not success:
                    await utils.answer(message, self.strings("names_not_found"), parse_mode="html")
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

    @loader.watcher(only_messages=True)
    async def watcher(self, message: Message):
        if not isinstance(message, Message) or message.out:
            return

        if message.chat_id not in self._tasks:
            return

        if not self._my_name or not self._partner_name:
            return

        text = message.raw_text or ""
        text_lower = text.lower()
        
        my_name_lower = self._my_name.lower()
        partner_name_lower = self._partner_name.lower()

        if my_name_lower not in text_lower and partner_name_lower not in text_lower:
            return

        event_ids = []
        
        text_ids = re.findall(r'(?:🆔|ID|Id|id)\s*([a-zA-Z0-9]+)', text)
        for tid in text_ids:
            clean_id = tid.replace("|", "").strip()
            if clean_id:
                event_ids.append(clean_id)

        for ev_id in set(event_ids):
            if ev_id:
                await self._client.send_message(message.chat_id, f".отн бер сб {ev_id}")
                await asyncio.sleep(2)

    async def on_unload(self):
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        self._counters.clear()
        self._current_action.clear()