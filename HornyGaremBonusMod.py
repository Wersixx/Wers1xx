# meta developer: @Wers1xx
# meta pic: https://img.icons8.com/fluency/48/000000/coins.png

import asyncio
import logging
from datetime import datetime, timedelta

from telethon.tl.types import Message
from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class HornyGaremBonusMod(loader.Module):
    """Автоматически собирает бонус в боте @Horny_GaremBot"""

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "total_coins",
                0,
                "Всего получено монет",
                validator=loader.validators.Integer(minimum=0),
            ),
            loader.ConfigValue(
                "bonus_count",
                0,
                "Количество полученных бонусов",
                validator=loader.validators.Integer(minimum=0),
            ),
        )

        self._task = None
        self._next_bonus_time = None
        self.bot_username = "@Horny_GaremBot"

    async def client_ready(self, client, db):
        self._client = client
        if self.get("_was_running", False):
            await self._start_task()

    async def _start_task(self):
        if self._task and not self._task.done():
            return
        self.set("_was_running", True)
        self._task = asyncio.ensure_future(self._bonus_loop())

    async def _stop_task(self):
        self.set("_was_running", False)
        if self._task and not self._task.done():
            self._task.cancel()
        self._next_bonus_time = None

    async def _bonus_loop(self):
        while True:
            try:
                await self._send_bonus()
                self._next_bonus_time = datetime.now() + timedelta(hours=6)
                await asyncio.sleep(6 * 3600)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле бонусов: {e}")
                await asyncio.sleep(60)

    async def _send_bonus(self):
        try:
            async with self._client.conversation(self.bot_username) as conv:
                await conv.send_message("/bonus")
                try:
                    response = await conv.get_response(timeout=10)
                    if response and response.text:
                        logger.info(f"Ответ бота: {response.text}")
                except Exception:
                    logger.warning("Бот не ответил, но бонус засчитан")

            self.config["total_coins"] += 750
            self.config["bonus_count"] += 1

            logger.info(
                f"Бонус получен! +750 монет. Всего: {self.config['total_coins']} монет, "
                f"{self.config['bonus_count']} бонусов"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить бонус: {e}")

    async def bonuscmd(self, message: Message):
        """Запустить автоматические бонусы (каждые 6 часов)"""
        if self.get("_was_running", False):
            await utils.answer(
                message, "<emoji document_id=5226497259566307266>🚨</emoji> <b>Авто-бонусы уже запущены!</b>"
            )
            return

        await self._start_task()
        self._next_bonus_time = datetime.now() + timedelta(hours=6)

        await utils.answer(
            message,
            "<emoji document_id=5206607081334906820>✔️</emoji> <b>Авто-бонусы запущены!</b>\n"
            "<emoji document_id=5440621591387980068>🔜</emoji> Каждые 6 часов будет отправляться /bonus\n"
            "<emoji document_id=5409048419211682843>💵</emoji> +750 монет за каждый бонус",
        )

    async def stopbonuscmd(self, message: Message):
        """Остановить автоматические бонусы"""
        if not self.get("_was_running", False):
            await utils.answer(
                message, "<emoji document_id=5226497259566307266>🚨</emoji> <b>Авто-бонусы не запущены!</b>"
            )
            return

        await self._stop_task()
        await utils.answer(
            message, "<emoji document_id=5420323339723881652>⚠️</emoji> <b>Авто-бонусы остановлены!</b>"
        )

    async def bonusstatcmd(self, message: Message):
        """Показать статистику бонусов"""
        is_running = self.get("_was_running", False)
        status = "<emoji document_id=5206607081334906820>✔️</emoji> <b>Активен</b>" if is_running else "<emoji document_id=5420323339723881652>⚠️</emoji> <b>Остановлен</b>"

        if self._next_bonus_time and is_running:
            remaining = self._next_bonus_time - datetime.now()
            if remaining.total_seconds() > 0:
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                next_bonus = f"{hours}ч {minutes}мин"
            else:
                next_bonus = "скоро..."
        else:
            next_bonus = "—"

        await utils.answer(
            message,
            "<b><emoji document_id=5231200819986047254>📊</emoji> Статистика бонусов:</b>\n\n"
            f"<emoji document_id=5409048419211682843>💵</emoji> Всего монет получено: <code>{self.config['total_coins']}</code>\n"
            f"<emoji document_id=5402477260982731644>☀️</emoji> Всего бонусов получено: <code>{self.config['bonus_count']}</code>\n"
            f"<emoji document_id=5440621591387980068>🔜</emoji> Следующий бонус через: <code>{next_bonus}</code>\n"
            f"<emoji document_id=5249019346512008974>▶️</emoji> Статус: {status}",
        )

    async def bonusnowcmd(self, message: Message):
        """Получить бонус прямо сейчас (вручную)"""
        await utils.answer(message, "⏳ <b>Отправляю /bonus...</b>")
        await self._send_bonus()
        await utils.answer(
            message,
            "<emoji document_id=5402477260982731644>☀️</emoji> <b>Бонус получен!</b>\n"
            f"<emoji document_id=5409048419211682843>💵</emoji> +750 монет\n"
            f"<emoji document_id=5231200819986047254>📊</emoji> Всего монет: <code>{self.config['total_coins']}</code>\n"
            f"<emoji document_id=5226513232549664618>🔢</emoji> Бонусов: <code>{self.config['bonus_count']}</code>",
        )

    async def on_unload(self):
        await self._stop_task()