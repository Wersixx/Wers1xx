# meta developer: @WersMod

__version__ = (1, 0, 9)

import asyncio
import datetime
import time

from telethon import types
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.users import GetFullUserRequest

from .. import loader, utils
from ..inline.types import InlineCall


class CooldownValidator:
    def __init__(self, min_value: int, error_message: str):
        self.min_value = min_value
        self.error_message = error_message

    def validate(self, value):
        if not isinstance(value, int):
            raise ValueError(self.error_message)
        if value < self.min_value:
            raise ValueError(self.error_message)
        return value


class WersAFK(loader.Module):
    """Полностью настраиваемый модуль для ухода в АФК режим с кулдауном в ЛС."""

    async def client_ready(self, client, db):
        self._me = await client.get_me()
        self._tg_id = self._me.id
        if self._db.get(__name__, "afk_enabled", False):
            await self._apply_afk_profile_changes(
                reason=self._db.get(__name__, "afk_reason", "­")
            )
        else:
            await self._restore_profile_changes()


    strings = {
        "name": "WersAFK",
        "afk_text_cfg": "Кастомный текст AFK. Используйте {time} для времени в AFK, {reason} для причины.",
        "about_text_cfg": "Текст для биографии в AFK. Используйте {bot} для юзернейма фидбэк-бота, {reason} для причины.",
        "feedback_bot_cfg": "Юзернейм вашего feedback бота. Если не нужен - оставьте пустым.",
        "prefix_cfg": "Префикс, который будет добавляться к вашей фамилии во время входа в АФК.",
        "ignore_chats_cfg": "Список ID чатов, в которых AFK не будет срабатывать. (По умолчанию выставлен Support chat хикки, лучше не убирать его)",
        "cooldown_cfg": "Время кулдауна (в секундах) между AFK-ответами одному пользователю в ЛС. Минимум 5 секунд.",
        
        "afk_on": "✅ <b>AFK</b> режим <b>включен</b>!",
        "afk_off": "❌ <b>AFK</b> режим <b>выключен</b>!",
        "text_set": "AFK текст успешно установлен:\n`{}`",
        "prefix_set": "AFK префикс успешно установлен на: `{}`",
        "bio_toggle": "Изменение биографии в AFK: **{}**",
        "name_toggle": "Изменение фамилии (префикса) в AFK: **{}**",
        "cooldown_set": "Кулдаун между AFK-ответами на пользователя установлен на: **{} секунд**",
        "no_text": "Текст не может быть пустым.",
        "status_message": (
            "**⚙️ WersAFK Статус:**\n"
            "  - **AFK режим:** `{afk_status}`\n"
            "  - **AFK текст:** `{afk_text}`\n"
            "  - **AFK префикс:** `{afk_prefix}`\n"
            "  - **Кулдаун на пользователя:** `{cooldown_seconds} сек.`\n"
            "  - **Изменять биографию:** `{change_bio}`\n"
            "  - **Изменять фамилию:** `{change_name}`\n"
            "  - **Feedback бот:** `{feedback_bot}`\n"
            "  - **Игнорируемые чаты:** `{ignore_chats}`"
        ),
        "cooldown_invalid": "Кулдаун должен быть целым числом и не менее 5 секунд.",
        "ignore_chats_invalid": "Каждый ID чата должен быть целым числом.",
    }

    def _validate_cooldown_value(self, value):
        if not isinstance(value, int) or value < 5:
            raise ValueError(self.strings("cooldown_invalid"))
        return value

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "afk_prefix",
                "| afk.",
                doc=lambda: self.strings("prefix_cfg")
            ),
            loader.ConfigValue(
                "afk_text",
                "Извините, сейчас я отошел. Отвечу, как только вернусь!",
                doc=lambda: self.strings("afk_text_cfg")
            ),
            loader.ConfigValue(
                "about_text",
                "Я сейчас в AFK. Связь: @{bot}",
                doc=lambda: self.strings("about_text_cfg")
            ),
            loader.ConfigValue(
                "feedback_bot",
                None,
                doc=lambda: self.strings("feedback_bot_cfg")
            ),
            loader.ConfigValue(
                "change_bio",
                True,
                doc="Менять ли биографию при уходе в AFK.",
                validator=loader.validators.Boolean()
            ),
            loader.ConfigValue(
                "change_name",
                True,
                doc="Менять ли фамилию (добавлять префикс) при уходе в AFK.",
                validator=loader.validators.Boolean()
            ),
            loader.ConfigValue(
                "cooldown_seconds",
                60,
                doc=lambda: self.strings("cooldown_cfg"),
                validator=loader.validators.Integer()
            ),
            loader.ConfigValue(
                "ignore_chats",
                [1554874075],
                doc=lambda: self.strings("ignore_chats_cfg"),
                validator=loader.validators.Series(
                    validator=loader.validators.Union(
                        loader.validators.TelegramID(),
                        loader.validators.RegExp("[0-9]"),
                    ),
                ),
            ),
        )

        try:
            current_cooldown = self.config["cooldown_seconds"]
            self._validate_cooldown_value(current_cooldown)
        except ValueError as e:
            self.allmodules.log(f"[WersAFK] Некорректное значение cooldown_seconds в конфиге: {e}. Устанавливаю 60.", level="WARNING")
            self.config["cooldown_seconds"] = 60


    def _format_afk_text(self) -> str:
        now = datetime.datetime.now().replace(microsecond=0)
        gone_timestamp = self._db.get(__name__, "afk_gone_time", time.time())
        gone = datetime.datetime.fromtimestamp(gone_timestamp).replace(microsecond=0)
        time_diff = now - gone
        reason = self._db.get(__name__, "afk_reason", "без причины")

        return self.config["afk_text"].format(time=time_diff, reason=reason)

    def _format_about_text(self, reason: str) -> str:
        bot_username = self.config["feedback_bot"] if self.config["feedback_bot"] else "нет"
        return self.config["about_text"].format(bot=bot_username, reason=reason)

    async def _apply_afk_profile_changes(self, reason: str):
        user_full = await self._client(GetFullUserRequest(self._tg_id))
        original_about = user_full.full_user.about
        self._db.set(__name__, "original_about", original_about)

        if self.config["change_name"]:
            await self._client(UpdateProfileRequest(last_name=self.config["afk_prefix"]))

        if self.config["change_bio"]:
            bio_text = self._format_about_text(reason)
            await self._client(UpdateProfileRequest(about=bio_text))
            
        await self.allmodules.log(f"[WersAFK] Изменения профиля применены. AFK причина: {reason}")


    async def _restore_profile_changes(self):
        if self.config["change_name"]:
            await self._client(UpdateProfileRequest(last_name=""))

        if self.config["change_bio"]:
            original_about = self._db.get(__name__, "original_about", "")
            if not original_about:
                original_about = "Добро пожаловать!"
            await self._client(UpdateProfileRequest(about=original_about))
            
            if self._db.get(__name__, "original_about") is not None:
                self._db.pop(__name__, "original_about")

        await self.allmodules.log("[WersAFK] Профиль восстановлен.")

    @loader.command(ru_doc="<reason/empty>- войти в АФК режим")
    async def goafk(self, message):
        """<reason/empty> - войти в АФК режим"""
        reason = utils.get_args_raw(message)
        if not reason:
            reason = "­"
        
        self._db.set(__name__, "afk_reason", reason)
        self._db.set(__name__, "afk_gone_time", time.time())
        self._db.set(__name__, "afk_enabled", True)
        self._db.set(__name__, "afk_cooldowns", {})

        await self._apply_afk_profile_changes(reason)

        m = await utils.answer(message, self.strings("afk_on"))
        await asyncio.sleep(5)
        await m.delete()

    @loader.command(ru_doc="- выйти из режима АФК")
    async def ungoafk(self, message):
        """- выйти из режима АФК"""
        self._db.set(__name__, "afk_enabled", False)
        
        # ИЗМЕНЕНИЕ ЗДЕСЬ: Проверяем наличие ключей перед вызовом pop()
        if self._db.get(__name__, "afk_gone_time") is not None:
            self._db.pop(__name__, "afk_gone_time")
        if self._db.get(__name__, "afk_reason") is not None:
            self._db.pop(__name__, "afk_reason")
        if self._db.get(__name__, "afk_cooldowns") is not None:
            self._db.pop(__name__, "afk_cooldowns")

        await self._restore_profile_changes()

        m = await utils.answer(message, self.strings("afk_off"))
        await self.allmodules.log("WersAFK теперь выключен.")
        await asyncio.sleep(5)
        await m.delete()

    @loader.command(ru_doc="<text> - установить кастомный AFK текст")
    async def wsafk_settext(self, message):
        """<text> - установить кастомный AFK текст"""
        text = utils.get_args_raw(message)
        if not text.strip():
            return await utils.answer(message, self.strings("no_text"))
        
        self.config["afk_text"] = text
        await utils.answer(message, self.strings("text_set").format(text))

    @loader.command(ru_doc="<prefix> - установить префикс для фамилии (например, '| afk.')")
    async def wsafk_setprefix(self, message):
        """<prefix> - установить префикс для фамилии (например, '| afk.')"""
        prefix = utils.get_args_raw(message)
        self.config["afk_prefix"] = prefix.strip()
        await utils.answer(message, self.strings("prefix_set").format(self.config["afk_prefix"]))
        
        if self._db.get(__name__, "afk_enabled", False) and self.config["change_name"]:
            await self._client(UpdateProfileRequest(last_name=self.config["afk_prefix"]))

    @loader.command(ru_doc="<on/off> - Включить/выключить изменение биографии при AFK")
    async def wsafk_togglebio(self, message):
        """<on/off> - Включить/выключить изменение биографии при AFK"""
        arg = utils.get_args_raw(message).lower()
        if arg == "on":
            self.config["change_bio"] = True
            msg = "Включено"
        elif arg == "off":
            self.config["change_bio"] = False
            msg = "Выключено"
        else:
            self.config["change_bio"] = not self.config["change_bio"]
            msg = "Включено" if self.config["change_bio"] else "Выключено"
        
        await utils.answer(message, self.strings("bio_toggle").format(msg))

    @loader.command(ru_doc="<on/off> - Включить/выключить изменение фамилии (префикса) при AFK")
    async def wsafk_togglereason(self, message):
        """<on/off> - Включить/выключить изменение фамилии (префикса) при AFK"""
        arg = utils.get_args_raw(message).lower()
        if arg == "on":
            self.config["change_name"] = True
            msg = "Включено"
        elif arg == "off":
            self.config["change_name"] = False
            msg = "Выключено"
        else:
            self.config["change_name"] = not self.config["change_name"]
            msg = "Включено" if self.config["change_name"] else "Выключено"

        await utils.answer(message, self.strings("name_toggle").format(msg))
        
    @loader.command(ru_doc="<seconds> - Установить время кулдауна между AFK-ответами (минимум 5 секунд)")
    async def wsafk_setcooldown(self, message):
        """<seconds> - Установить время кулдауна между AFK-ответами (минимум 5 секунд)"""
        args = utils.get_args_raw(message)
        try:
            new_cooldown = int(args)
            self._validate_cooldown_value(new_cooldown)
            self.config["cooldown_seconds"] = new_cooldown 
            await utils.answer(message, self.strings("cooldown_set").format(new_cooldown))
        except ValueError as e: 
            await utils.answer(message, f"🚫 {e}")
        except Exception as e:
            await utils.answer(message, f"Произошла непредвиденная ошибка: {e}")

    @loader.command(ru_doc="- Показать текущий статус и настройки WersAFK")
    async def wsafk_status(self, message):
        """- Показать текущий статус и настройки WersAFK"""
        afk_status_str = "Включен ✅" if self._db.get(__name__, "afk_enabled", False) else "Выключен 🚫"
        ignore_chats_str = ", ".join(map(str, self.config["ignore_chats"])) if self.config["ignore_chats"] else "Нет"

        await utils.answer(message, self.strings("status_message").format(
            afk_status=afk_status_str,
            afk_text=self.config["afk_text"],
            afk_prefix=self.config["afk_prefix"],
            cooldown_seconds=self.config["cooldown_seconds"],
            change_bio="Да" if self.config["change_bio"] else "Нет",
            change_name="Да" if self.config["change_name"] else "Нет",
            feedback_bot=self.config["feedback_bot"] if self.config["feedback_bot"] else "Не указан",
            ignore_chats=ignore_chats_str,
        ))

    @loader.watcher()
    async def watcher(self, message):
        if not isinstance(message, types.Message):
            return

        if not self._db.get(__name__, "afk_enabled", False):
            return

        if message.peer_id == self._tg_id:
            return

        if utils.get_chat_id(message) in self.config["ignore_chats"]: 
            return

        is_dm = isinstance(message.peer_id, types.PeerUser) and message.peer_id.user_id != self._tg_id
        is_mention = message.mentioned or getattr(message.to_id, "user_id", None) == self._me.id

        if not (is_dm or is_mention):
            return
        
        user = await utils.get_user(message)
        if user.bot or user.verified:
            return

        user_id = user.id
        current_time = time.time()
        
        user_cooldowns = self._db.setdefault(__name__, {}).setdefault("afk_cooldowns", {})
        last_reply_time = user_cooldowns.get(user_id, 0)
        cooldown_duration = self.config["cooldown_seconds"]

        if current_time - last_reply_time >= cooldown_duration:
            try:
                afk_message_text = self._format_afk_text()
                await utils.answer(message, afk_message_text)
                user_cooldowns[user_id] = current_time
                self._db.set(__name__, "afk_cooldowns", user_cooldowns)
            except Exception as e:
                await self.allmodules.log(f"[WersAFK] Ошибка при отправке AFK сообщения пользователю {user.id}: {e}", level="ERROR")
