# meta developer: @Wers1xx

# name: AdvancedSpam
# description: Модуль для спам-рассылки с полным контролем

import asyncio
import logging
from typing import List

from .. import loader, utils
from telethon import functions, types
from telethon.tl.functions.channels import GetFullChannelRequest

logger = logging.getLogger(__name__)

@loader.tds
class AdvancedSpamMod(loader.Module):
    """Модуль для контролируемой рассылки сообщений"""
    
    strings = {
        "name": "AdvancedSpam",
        "spam_started": "🚀 <b>Рассылка запущена!</b>\nИнтервал: <code>{}</code> сек.\nЧатов в списке: <code>{}</code>",
        "spam_stopped": "🛑 <b>Рассылка остановлена.</b>",
        "spam_already_running": "⚠️ <b>Рассылка уже активна!</b>",
        "spam_not_running": "ℹ️ <b>Рассылка не запущена.</b>",
        "msg_set": "✅ <b>Сообщение установлено:</b>\n\n{}",
        "msg_not_set": "❌ <b>Сообщение не задано!</b>",
        "chat_added": "➕ <b>Чат добавлен:</b> <code>{}</code>",
        "chat_exists": "⚠️ Чат уже в списке.",
        "chat_removed": "➖ <b>Чат удален:</b> <code>{}</code>",
        "chat_not_found": "❌ Чат не найден в списке.",
        "chatlist": "📋 <b>Список чатов для рассылки ({}/{}):</b>\n{}",
        "chatlist_empty": "📭 <b>Список чатов пуст.</b>",
        "delay_set": "⏱ <b>Задержка установлена:</b> <code>{}</code> сек.",
        "invalid_delay": "❌ Укажите корректную задержку в секундах.",
        "invalid_link": "❌ Укажите корректную ссылку на чат (@username или https://t.me/...).",
        "cleared": "🧹 <b>Список чатов очищен.</b>",
        "status": "📊 <b>Статус рассылки:</b>\n"
                  "Активна: <b>{}</b>\n"
                  "Сообщение: {}\n"
                  "Чатов: <code>{}</code>\n"
                  "Задержка: <code>{}</code> сек.",
        "test_sent": "✅ Тестовое сообщение отправлено."
    }

    def __init__(self):
        self._message: str = ""
        self._chats: List[str] = []
        self._delay: int = 5
        self._spam_task: asyncio.Task = None
        self._running: bool = False

    async def client_ready(self, client, db):
        self._client = client
        # Загрузка сохраненных данных
        self._message = db.get(self.__class__.__name__, "message", "")
        self._chats = db.get(self.__class__.__name__, "chats", [])
        self._delay = db.get(self.__class__.__name__, "delay", 5)

    def _save_settings(self):
        """Сохраняет настройки в базу данных."""
        self.db.set(self.__class__.__name__, "message", self._message)
        self.db.set(self.__class__.__name__, "chats", self._chats)
        self.db.set(self.__class__.__name__, "delay", self._delay)

    async def _spam_loop(self):
        """Основной цикл рассылки."""
        while self._running:
            if not self._message or not self._chats:
                await asyncio.sleep(1)
                continue
                
            for chat in self._chats:
                if not self._running:
                    break
                try:
                    # Используем сущность напрямую, если это username
                    entity = await self._client.get_input_entity(chat)
                    await self._client.send_message(entity, self._message)
                    await asyncio.sleep(self._delay)
                except Exception as e:
                    logger.error(f"Ошибка отправки в {chat}: {e}")
                    await asyncio.sleep(1)

    @loader.command()
    async def setmsg(self, message):
        """[текст] - Установить сообщение для рассылки"""
        text = utils.get_args_raw(message)
        if not text:
            await utils.answer(message, self.strings("msg_not_set"))
            return
        self._message = text
        self._save_settings()
        await utils.answer(message, self.strings("msg_set").format(text))

    @loader.command()
    async def addchat(self, message):
        """[ссылка] - Добавить чат в список рассылки"""
        link = utils.get_args_raw(message)
        if not link:
            await utils.answer(message, self.strings("invalid_link"))
            return
            
        if link in self._chats:
            await utils.answer(message, self.strings("chat_exists"))
            return
            
        self._chats.append(link)
        self._save_settings()
        await utils.answer(message, self.strings("chat_added").format(link))

    @loader.command()
    async def delchat(self, message):
        """[ссылка] - Удалить чат из списка"""
        link = utils.get_args_raw(message)
        if not link:
            await utils.answer(message, self.strings("invalid_link"))
            return
            
        if link in self._chats:
            self._chats.remove(link)
            self._save_settings()
            await utils.answer(message, self.strings("chat_removed").format(link))
        else:
            await utils.answer(message, self.strings("chat_not_found"))

    @loader.command()
    async def chatlist(self, message):
        """Показать список чатов для рассылки"""
        if not self._chats:
            await utils.answer(message, self.strings("chatlist_empty"))
            return
            
        chat_list = "\n".join([f"• <code>{chat}</code>" for chat in self._chats])
        await utils.answer(message, self.strings("chatlist").format(
            len(self._chats), len(self._chats), chat_list
        ))

    @loader.command()
    async def setdelay(self, message):
        """[секунды] - Установить задержку между сообщениями"""
        args = utils.get_args_raw(message)
        if not args or not args.isdigit():
            await utils.answer(message, self.strings("invalid_delay"))
            return
            
        self._delay = int(args)
        self._save_settings()
        await utils.answer(message, self.strings("delay_set").format(self._delay))

    @loader.command()
    async def startspam(self, message):
        """Запустить рассылку"""
        if self._running:
            await utils.answer(message, self.strings("spam_already_running"))
            return
            
        if not self._message:
            await utils.answer(message, self.strings("msg_not_set"))
            return
            
        if not self._chats:
            await utils.answer(message, self.strings("chatlist_empty"))
            return
            
        self._running = True
        self._spam_task = asyncio.create_task(self._spam_loop())
        await utils.answer(message, self.strings("spam_started").format(
            self._delay, len(self._chats)
        ))

    @loader.command()
    async def stopspam(self, message):
        """Остановить рассылку"""
        if not self._running:
            await utils.answer(message, self.strings("spam_not_running"))
            return
            
        self._running = False
        if self._spam_task:
            self._spam_task.cancel()
            self._spam_task = None
        await utils.answer(message, self.strings("spam_stopped"))

    @loader.command()
    async def spamstatus(self, message):
        """Показать статус рассылки"""
        msg_preview = self._message[:50] + "..." if len(self._message) > 50 else self._message
        msg_status = f"<i>\"{msg_preview}\"</i>" if self._message else "❌ не задано"
        
        await utils.answer(message, self.strings("status").format(
            "✅ Да" if self._running else "❌ Нет",
            msg_status,
            len(self._chats),
            self._delay
        ))

    @loader.command()
    async def clearspam(self, message):
        """Очистить список чатов"""
        self._chats.clear()
        self._save_settings()
        await utils.answer(message, self.strings("cleared"))

    @loader.command()
    async def testspam(self, message):
        """Отправить тестовое сообщение в первый чат списка"""
        if not self._message:
            await utils.answer(message, self.strings("msg_not_set"))
            return
        if not self._chats:
            await utils.answer(message, self.strings("chatlist_empty"))
            return
            
        try:
            entity = await self._client.get_input_entity(self._chats[0])
            await self._client.send_message(entity, self._message)
            await utils.answer(message, self.strings("test_sent"))
        except Exception as e:
            await utils.answer(message, f"❌ Ошибка: {e}")