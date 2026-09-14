# meta developer: @Wers1xx
# scope: hikka_min 1.6.0
# scope: hikka_only
# meta banner: https://x0.at/1TCL.jpg

from hikkatl.types import Message
from .. import loader, utils
import logging

logger = logging.getLogger(__name__)

@loader.tds
class InstantReadMod(loader.Module):
    """Мгновенно читает все входящие сообщения (ЛС + теги), чтобы не приходили уведомления"""

    strings = {
        "name": "InstantRead",
        "enabled": "✅ <b>InstantRead включен</b>\nТеперь все входящие сообщения будут мгновенно читаться",
        "disabled": "❌ <b>InstantRead выключен</b>",
        "status_on": "🟢 <b>Статус:</b> Включен",
        "status_off": "🔴 <b>Статус:</b> Выключен",
        "only_pm": "✅ Теперь читаю <b>только личные сообщения</b>",
        "only_mentions": "✅ Теперь читаю <b>только теги/упоминания</b>",
        "all": "✅ Теперь читаю <b>всё</b> (ЛС + теги + обычные сообщения в группах)",
        "current_mode": "📌 Текущий режим: <b>{}</b>",
    }

    strings_ru = {
        "name": "InstantRead",
        "enabled": "✅ <b>InstantRead включен</b>\nТеперь все входящие сообщения будут мгновенно читаться",
        "disabled": "❌ <b>InstantRead выключен</b>",
        "status_on": "🟢 <b>Статус:</b> Включен",
        "status_off": "🔴 <b>Статус:</b> Выключен",
        "only_pm": "✅ Теперь читаю <b>только личные сообщения</b>",
        "only_mentions": "✅ Теперь читаю <b>только теги/упоминания</b>",
        "all": "✅ Теперь читаю <b>всё</b> (ЛС + теги + обычные сообщения в группах)",
        "current_mode": "📌 Текущий режим: <b>{}</b>",
        "_cls_doc": "Мгновенно читает входящие сообщения, чтобы Telegram не успевал слать уведомления",
        "_cmd_doc_iread": "Включить/выключить модуль",
        "_cmd_doc_ireadmode": "Сменить режим работы (all / pm / mentions)",
        "_cmd_doc_ireadstatus": "Показать текущий статус",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "mode",
                "all",
                lambda: "Режим работы: all / pm / mentions",
                validator=loader.validators.Choice(["all", "pm", "mentions"]),
            ),
        )

    async def client_ready(self, client, db):
        self._client = client
        if self.get("enabled") is None:
            self.set("enabled", True)

    @loader.command()
    async def iread(self, message: Message):
        """Включить/выключить InstantRead"""
        current = self.get("enabled", True)
        self.set("enabled", not current)
        
        if not current:
            await utils.answer(message, self.strings("enabled"))
        else:
            await utils.answer(message, self.strings("disabled"))

    @loader.command()
    async def ireadmode(self, message: Message):
        """Сменить режим: all / pm / mentions"""
        args = utils.get_args_raw(message).lower().strip()
        
        if args not in ("all", "pm", "mentions"):
            current = self.config["mode"]
            modes = {
                "all": "всё (ЛС + теги + группы)",
                "pm": "только личные сообщения",
                "mentions": "только теги/упоминания"
            }
            await utils.answer(
                message,
                self.strings("current_mode").format(modes.get(current, current))
                + "\n\nДоступные режимы:\n"
                "• <code>.ireadmode all</code> — читать всё\n"
                "• <code>.ireadmode pm</code> — только ЛС\n"
                "• <code>.ireadmode mentions</code> — только теги"
            )
            return

        self.config["mode"] = args
        
        if args == "all":
            text = self.strings("all")
        elif args == "pm":
            text = self.strings("only_pm")
        else:
            text = self.strings("only_mentions")
            
        await utils.answer(message, text)

    @loader.command()
    async def ireadstatus(self, message: Message):
        """Показать статус модуля"""
        enabled = self.get("enabled", True)
        mode = self.config["mode"]
        
        modes = {
            "all": "всё (ЛС + теги + группы)",
            "pm": "только личные сообщения",
            "mentions": "только теги/упоминания"
        }
        
        status = self.strings("status_on") if enabled else self.strings("status_off")
        await utils.answer(
            message,
            f"{status}\n{self.strings('current_mode').format(modes.get(mode, mode))}"
        )

    @loader.watcher(only_messages=True, no_commands=True)
    async def watcher(self, message: Message):
        if not self.get("enabled", True):
            return
            
        if message.out:
            return

        mode = self.config["mode"]
        chat_id = utils.get_chat_id(message)

        try:
            if mode == "all":
                # Читаем абсолютно всё
                await self._client.send_read_acknowledge(
                    message.peer_id,
                    message,
                    clear_mentions=True
                )
                
            elif mode == "pm":
                # Только личные сообщения
                if message.is_private:
                    await self._client.send_read_acknowledge(
                        message.peer_id,
                        message,
                        clear_mentions=True
                    )
                    
            elif mode == "mentions":
                # Только упоминания/теги
                if message.mentioned or (message.is_private):
                    await self._client.send_read_acknowledge(
                        message.peer_id,
                        message,
                        clear_mentions=True
                    )
                    
        except Exception as e:
            logger.debug(f"InstantRead error: {e}")