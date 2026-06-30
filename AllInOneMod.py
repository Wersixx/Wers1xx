# meta developer: @Wers1xx
# meta pic: https://x0.at/3Wu7.jpg
# scope: hikka_only
# scope: hikka_min 1.6.2

import asyncio
import re
import logging
from hikka import loader, utils
from telethon.tl.types import Message
from telethon.errors.rpcerrorlist import YouBlockedUserError, FloodWaitError
from telethon.tl.functions.contacts import UnblockRequest
from telethon.tl.functions.messages import ReadMentionsRequest

logger = logging.getLogger(__name__)

ORES = {
    "Железо": "⛓‍💥",
    "Золото": "🌕",
    "Алмаз": "💎",
    "Аметист": "🎆",
    "Аквамарин": "💠",
    "Изумруд": "🍀",
    "Материя": "🌌",
    "Плазма": "💥",
    "Никель": "🪙",
    "Титан": "⚙",
    "Кобальт": "🧪",
    "Эктоплазма": "🎇"
}

MINE_COMMAND_MAP = {
    "Железо": "железо",
    "Золото": "золото",
    "Алмаз": "алмазы",
    "Аметист": "аметисты",
    "Аквамарин": "аквамарин",
    "Изумруд": "изумруды",
    "Материя": "материю",
    "Плазма": "плазму",
    "Никель": "никель",
    "Титан": "титан",
    "Кобальт": "кобальт",
    "Эктоплазма": "эктоплазму"
}


@loader.tds
class AllInOneMod(loader.Module):
    """Многофункциональный модуль для игрового бота BFG"""
    
    strings = {"name": "AllInOne"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "chat",
                None,
                "Основной чат (@username или ID)",
                validator=loader.validators.String()
            ),
            loader.ConfigValue(
                "delay",
                2.0,
                "Задержка между действиями (сек)",
                validator=loader.validators.Float(minimum=0.5)
            ),
            loader.ConfigValue(
                "vip_level",
                0,
                "VIP уровень для кейсов (0-4)",
                validator=loader.validators.Integer(minimum=0, maximum=4)
            ),
            loader.ConfigValue(
                "garden_time",
                60,
                "Пауза между циклами сада (в минутах)",
                validator=loader.validators.Integer(minimum=1)
            ),
            loader.ConfigValue(
                "max_gpus",
                100,
                "Максимальное количество видеокарт",
                validator=loader.validators.Integer(minimum=1)
            )
        )
        
        self._bup_task = None
        self._farm_task = None
        self._case_task = None
        self._last_progress = ""
        
        self._vip_limits = {0: 6, 1: 20, 2: 40, 3: 60, 4: 250}
        
        self._case_names = {
            1: "Обычный кейс",
            2: "Золотой кейс",
            3: "Рудный кейс",
            4: "Материальный кейс"
        }
        
        self.auto_mine_ore_running = False
        self.selected_ore = "Железо"
        self.bot_id = 1721358063
        self.auto_garden_running = False

    async def client_ready(self, client, db):
        self._client = client
        self._db = db
        
        self.auto_mine_ore_running = self._db.get("AllInOne", "auto_mine_ore_running", False)
        self.selected_ore = self._db.get("AllInOne", "selected_ore", "Железо")
        self.auto_garden_running = self._db.get("AllInOne", "auto_garden_running", False)
        
        if self.selected_ore not in ORES:
            self.selected_ore = "Железо"
        
        if self.auto_mine_ore_running:
            asyncio.create_task(self._auto_mine_ore_loop())
        
        if self.auto_garden_running:
            asyncio.create_task(self._auto_garden_loop())

    def _clean_text(self, text):
        if not text:
            return ""
        
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FA6F"
            "\U0001FA70-\U0001FAFF"
            "\U00002600-\U000026FF"
            "\U0000FE00-\U0000FE0F"
            "\U0000200D"
            "\U0000200C"
            "]+",
            flags=re.UNICODE
        )
        
        return emoji_pattern.sub('', text).strip()

    # ==================== БИЗНЕС ====================
    
    async def bupcmd(self, message: Message):
        """<уровень> - Прокачка бизнеса до указанного уровня"""
        if not self.config["chat"]:
            await utils.answer(message, "❌ <b>Чат не указан в конфиге!</b>")
            return

        args = utils.get_args_raw(message)
        if not args.isdigit():
            await utils.answer(message, "❌ <b>Укажите целевой уровень!</b>\nПример: <code>.bup 100</code>")
            return
            
        target = int(args)
        
        if self._bup_task and not self._bup_task.done():
            self._bup_task.cancel()
            await asyncio.sleep(0.5)
        
        self._bup_task = asyncio.ensure_future(self._upgrade_loop(message, target))
        await utils.answer(message, f"🔄 <b>Начинаю прокачку до уровня {target}</b>")

    async def stopbupcmd(self, message: Message):
        """Остановить прокачку бизнеса"""
        if self._bup_task and not self._bup_task.done():
            self._bup_task.cancel()
            await utils.answer(message, "⏹ <b>Прокачка остановлена</b>")
        else:
            await utils.answer(message, "❌ <b>Нет активной прокачки</b>")

    async def _get_levels(self, message_text):
        territory = None
        business = None
        
        cleaned_text = self._clean_text(message_text)
        
        for line in cleaned_text.split('\n'):
            line = line.strip()
            if 'Территория:' in line and 'бизнеса' not in line.lower():
                try:
                    numbers = re.findall(r'\d+', line)
                    if numbers:
                        territory = int(numbers[0])
                except (ValueError, IndexError):
                    pass
            elif 'Территория бизнеса:' in line or 'Бизнес:' in line:
                try:
                    numbers = re.findall(r'\d+', line)
                    if numbers:
                        business = int(numbers[0])
                except (ValueError, IndexError):
                    pass
        
        return territory, business

    async def _find_business_message(self, chat_id):
        try:
            async for msg in self._client.iter_messages(chat_id, limit=50):
                if msg.text:
                    cleaned = self._clean_text(msg.text)
                    if 'Территория:' in cleaned:
                        return msg
        except Exception:
            pass
        return None

    async def _click_button(self, msg, button_text):
        if not msg or not msg.buttons:
            return False
        
        search_text = self._clean_text(button_text).lower()
        
        for row in msg.buttons:
            for button in row:
                if button.text:
                    button_clean = self._clean_text(button.text).lower()
                    if search_text in button_clean:
                        try:
                            await button.click()
                            return True
                        except Exception:
                            return False
        return False

    async def _upgrade_loop(self, message, target):
        try:
            chat = self.config["chat"]
            try:
                chat_id = int(chat)
            except ValueError:
                chat_id = chat
            
            delay = self.config["delay"]
            no_click_count = 0
            max_no_click = 3
            
            await self._client.send_message(chat_id, "Мой бизнес")
            await asyncio.sleep(delay)
            
            while True:
                msg = await self._find_business_message(chat_id)
                if not msg:
                    await utils.answer(message, "❌ <b>Не нашел сообщения с территорией</b>")
                    await self._client.send_message(chat_id, "Мой бизнес")
                    await asyncio.sleep(delay)
                    continue
                
                territory, business = await self._get_levels(msg.text)
                
                if territory is None or business is None:
                    await utils.answer(message, "❌ <b>Не нашел сообщения с территорией</b>")
                    await self._client.send_message(chat_id, "Мой бизнес")
                    await asyncio.sleep(delay)
                    continue
                
                progress_text = f"📊 <b>Прокачка...</b>\n🧱 Территория: {territory}/{target}\n🏢 Бизнес: {business}/{target}"
                if progress_text != self._last_progress:
                    await utils.answer(message, progress_text)
                    self._last_progress = progress_text
                
                if territory >= target and business >= target:
                    await utils.answer(message, f"✅ <b>Прокачка завершена!</b>\n🧱 Территория: {territory}\n🏢 Бизнес: {business}")
                    return
                
                clicked = False
                
                if territory < target:
                    if await self._click_button(msg, "Увеличить территорию"):
                        clicked = True
                        await asyncio.sleep(delay)
                        continue
                
                if business < target:
                    if await self._click_button(msg, "Увеличить бизнес"):
                        clicked = True
                        await asyncio.sleep(delay)
                        continue
                
                if not clicked:
                    no_click_count += 1
                    if no_click_count >= max_no_click:
                        await utils.answer(message, "⚠️ <b>Кнопки не найдены, обновляю...</b>")
                        await self._client.send_message(chat_id, "Мой бизнес")
                        no_click_count = 0
                    await asyncio.sleep(delay)
                else:
                    no_click_count = 0
                
        except asyncio.CancelledError:
            await utils.answer(message, "⏹ <b>Прокачка остановлена</b>")

    # ==================== ФЕРМА ====================
    
    async def farmcmd(self, message: Message):
        """<количество> - Скупка видеокарт до указанного количества"""
        if not self.config["chat"]:
            await utils.answer(message, "❌ <b>Чат не указан в конфиге!</b>")
            return

        args = utils.get_args_raw(message)
        if not args:
            target = self.config["max_gpus"]
        elif args.isdigit():
            target = int(args)
        else:
            await utils.answer(message, "❌ <b>Укажите целевое количество!</b>\nПример: <code>.farm 100</code>")
            return
        
        if self._farm_task and not self._farm_task.done():
            self._farm_task.cancel()
            await asyncio.sleep(0.5)
        
        self._farm_task = asyncio.ensure_future(self._buy_loop(message, target))
        await utils.answer(message, f"🔄 <b>Начинаю скупку видеокарт до {target}</b>")

    async def stopfarmcmd(self, message: Message):
        """Остановить скупку видеокарт"""
        if self._farm_task and not self._farm_task.done():
            self._farm_task.cancel()
            await utils.answer(message, "⏹ <b>Скупка остановлена</b>")
        else:
            await utils.answer(message, "❌ <b>Нет активной скупки</b>")

    async def _get_gpu_count(self, message_text):
        if not message_text:
            return None
        
        cleaned_text = self._clean_text(message_text)
        
        for line in cleaned_text.split('\n'):
            line = line.strip()
            if 'Видеокарты:' in line or 'Видеокарт:' in line:
                try:
                    numbers = re.findall(r'\d+', line)
                    if numbers:
                        return int(numbers[0])
                except (ValueError, IndexError):
                    pass
        
        return None

    async def _find_farm_message(self, chat_id):
        try:
            async for msg in self._client.iter_messages(chat_id, limit=50):
                if msg.text:
                    cleaned = self._clean_text(msg.text)
                    if 'Видеокарты' in cleaned or 'Майнинг' in cleaned or 'Ферма' in cleaned:
                        return msg
        except Exception:
            pass
        return None

    async def _click_farm_button(self, msg, button_texts):
        if not msg or not msg.buttons:
            return False
        
        if isinstance(button_texts, str):
            button_texts = [button_texts]
        
        search_texts = [self._clean_text(t).lower() for t in button_texts]
        
        for row in msg.buttons:
            for button in row:
                if button.text:
                    button_clean = self._clean_text(button.text).lower()
                    for search_text in search_texts:
                        if search_text in button_clean:
                            try:
                                await button.click()
                                return True
                            except Exception:
                                return False
        return False

    async def _buy_loop(self, message, target):
        try:
            chat = self.config["chat"]
            try:
                chat_id = int(chat)
            except ValueError:
                chat_id = chat
            
            delay = self.config["delay"]
            no_click_count = 0
            max_no_click = 3
            
            await self._client.send_message(chat_id, "Моя ферма")
            await asyncio.sleep(delay)
            
            while True:
                msg = await self._find_farm_message(chat_id)
                if not msg:
                    await utils.answer(message, "❌ <b>Не нашел сообщения с фермой</b>")
                    await self._client.send_message(chat_id, "Моя ферма")
                    await asyncio.sleep(delay)
                    continue
                
                gpu_count = await self._get_gpu_count(msg.text)
                
                if gpu_count is None:
                    await utils.answer(message, "❌ <b>Не нашел сообщения с фермой</b>")
                    await self._client.send_message(chat_id, "Моя ферма")
                    await asyncio.sleep(delay)
                    continue
                
                progress_text = f"📊 <b>Скупаю видеокарты...</b>\n🎮 Видеокарты: {gpu_count}/{target}"
                if progress_text != self._last_progress:
                    await utils.answer(message, progress_text)
                    self._last_progress = progress_text
                
                if gpu_count >= target:
                    await utils.answer(message, f"✅ <b>Скупка завершена!</b>\n🎮 Видеокарты: {gpu_count}")
                    return
                
                clicked = await self._click_farm_button(msg, [
                    "Купить видеокарту",
                    "Купить",
                    "Приобрести видеокарту",
                    "Видеокарта"
                ])
                
                if clicked:
                    no_click_count = 0
                    await asyncio.sleep(delay)
                else:
                    no_click_count += 1
                    if no_click_count >= max_no_click:
                        await utils.answer(message, "⚠️ <b>Кнопка не найдена, обновляю...</b>")
                        await self._client.send_message(chat_id, "Моя ферма")
                        no_click_count = 0
                    await asyncio.sleep(delay)
                
        except asyncio.CancelledError:
            await utils.answer(message, "⏹ <b>Скупка остановлена</b>")

    # ==================== КЕЙСЫ ====================
    
    async def acasecmd(self, message: Message):
        """<номер кейса> - Автооткрытие кейсов (1-4)"""
        if not self.config["chat"]:
            await utils.answer(message, "❌ <b>Чат не указан в конфиге!</b>")
            return

        args = utils.get_args_raw(message)
        if not args.isdigit() or int(args) not in [1, 2, 3, 4]:
            await utils.answer(
                message, 
                "❌ <b>Укажите номер кейса!</b>\n"
                "1 - Обычный кейс\n"
                "2 - Золотой кейс\n"
                "3 - Рудный кейс\n"
                "4 - Материальный кейс\n\n"
                "Пример: <code>.acase 1</code>"
            )
            return
        
        case_number = int(args)
        case_name = self._case_names[case_number]
        
        if self._case_task and not self._case_task.done():
            self._case_task.cancel()
            await asyncio.sleep(0.5)
        
        self._case_task = asyncio.ensure_future(self._open_loop(message, case_number, case_name))
        await utils.answer(message, f"🔄 <b>Начинаю открытие кейсов: {case_name}</b>")

    async def stopacasecmd(self, message: Message):
        """Остановить открытие кейсов"""
        if self._case_task and not self._case_task.done():
            self._case_task.cancel()
            await utils.answer(message, "⏹ <b>Открытие остановлено</b>")
        else:
            await utils.answer(message, "❌ <b>Нет активного открытия</b>")

    def _get_max_open(self):
        vip = self.config["vip_level"]
        return self._vip_limits.get(vip, 6)

    async def _find_case_message(self, chat_id, case_name):
        try:
            async for msg in self._client.iter_messages(chat_id, limit=50):
                if msg.text:
                    cleaned = self._clean_text(msg.text)
                    if case_name in cleaned or "кейс" in cleaned.lower():
                        return msg
        except Exception:
            pass
        return None

    async def _get_case_count(self, message_text, case_name):
        if not message_text:
            return None
        
        cleaned_text = self._clean_text(message_text)
        
        for line in cleaned_text.split('\n'):
            line = line.strip()
            if case_name in line:
                try:
                    numbers = re.findall(r'\d+', line)
                    if numbers:
                        return int(numbers[0])
                except (ValueError, IndexError):
                    pass
        
        return None

    async def _check_no_cases(self, message_text):
        if not message_text:
            return False
        
        cleaned = self._clean_text(message_text).lower()
        no_cases_phrases = [
            "недостаточно кейсов",
            "не хватает кейсов",
            "нет кейсов",
            "у вас нет",
            "недостаточно"
        ]
        
        return any(phrase in cleaned for phrase in no_cases_phrases)

    async def _open_loop(self, message, case_number, case_name):
        try:
            chat = self.config["chat"]
            try:
                chat_id = int(chat)
            except ValueError:
                chat_id = chat
            
            delay = self.config["delay"]
            max_open = self._get_max_open()
            
            while True:
                await self._client.send_message(chat_id, f"Открыть кейс {case_number} {max_open}")
                await asyncio.sleep(delay)
                
                msg = await self._find_case_message(chat_id, case_name)
                if not msg:
                    continue
                
                if await self._check_no_cases(msg.text):
                    await utils.answer(message, "🔍 <b>Проверяю остаток кейсов...</b>")
                    
                    await self._client.send_message(chat_id, "Кейсы")
                    await asyncio.sleep(delay)
                    
                    cases_msg = await self._find_case_message(chat_id, case_name)
                    if cases_msg:
                        remaining = await self._get_case_count(cases_msg.text, case_name)
                        if remaining and remaining > 0:
                            while remaining > 0:
                                open_now = min(remaining, max_open)
                                await self._client.send_message(chat_id, f"Открыть кейс {case_number} {open_now}")
                                await asyncio.sleep(delay)
                                remaining -= open_now
                    
                    await utils.answer(message, "✅ <b>Открытие завершено!</b>")
                    return
                
                await asyncio.sleep(delay)
                
        except asyncio.CancelledError:
            await utils.answer(message, "⏹ <b>Открытие остановлено</b>")

    # ==================== РУДА ====================
    
    def _get_mine_ore_keyboard(self):
        current_ore_emoji = ORES.get(self.selected_ore, "")
        text = (
            f"⛏️ Автокопание руды\n\n"
            f"📊 Статус: {'❤️‍🩹 Запущено' if self.auto_mine_ore_running else '💤 Остановлено'}\n"
            f"🌟 Выбрана руда: {current_ore_emoji} {self.selected_ore}"
        )

        buttons = []
        ore_names = list(ORES.keys())
        
        for i in range(0, len(ore_names), 3):
            row = []
            for ore_name in ore_names[i : i+3]:
                emoji = ORES[ore_name]
                state_emoji = "❤️‍🩹" if ore_name == self.selected_ore else "💤"
                row.append({"text": f"{state_emoji}{emoji} {ore_name}", "callback": self._select_mine_ore, "args": (ore_name,)})
            buttons.append(row)
        
        buttons.append([{"text": "💤 Остановить" if self.auto_mine_ore_running else "❤️‍🩹 Запустить",
                         "callback": self._toggle_auto_mine_ore}])
        
        return text, buttons

    @loader.command(ru_doc="Открыть меню автоматического копания руды")
    async def automineore(self, message):
        """Открыть меню автоматического копания руды"""
        text, markup = self._get_mine_ore_keyboard()
        await self.inline.form(message=message, text=text, reply_markup=markup)

    async def _select_mine_ore(self, call, ore_name):
        self.selected_ore = ore_name
        self._db.set("AllInOne", "selected_ore", ore_name)
        
        text, markup = self._get_mine_ore_keyboard()
        await call.edit(text, reply_markup=markup)
        await call.answer(f"Выбрана руда: {ore_name}")

    async def _toggle_auto_mine_ore(self, call):
        if self.auto_mine_ore_running:
            self.auto_mine_ore_running = False
            self._db.set("AllInOne", "auto_mine_ore_running", False)
            await call.answer("Автокопание руды остановлено.")
        else:
            self.auto_mine_ore_running = True
            self._db.set("AllInOne", "auto_mine_ore_running", True)
            asyncio.create_task(self._auto_mine_ore_loop())
            await call.answer("Автокопание руды запущено.")
        
        text, markup = self._get_mine_ore_keyboard()
        await call.edit(text, reply_markup=markup)

    async def _auto_mine_ore_loop(self):
        while self.auto_mine_ore_running:
            try:
                command_arg = MINE_COMMAND_MAP.get(self.selected_ore, self.selected_ore.lower())
                command = f"Копать {command_arg}"
                await self._client.send_message(self.bot_id, command)
            except Exception:
                pass
            
            await asyncio.sleep(600)

    # ==================== САД ====================
    
    @loader.command(ru_doc="Запуск/остановка автосада и налогов")
    async def autgardencmd(self, message: Message):
        """Запустить/остановить автосад и налоги"""
        if self.auto_garden_running:
            self.auto_garden_running = False
            self._db.set("AllInOne", "auto_garden_running", False)
            await utils.answer(message, "💤 <b>AutoGarden остановлен</b>")
        else:
            self.auto_garden_running = True
            self._db.set("AllInOne", "auto_garden_running", True)
            asyncio.create_task(self._auto_garden_loop())
            await utils.answer(message, f"🌙 <b>AutoGarden запущен</b>")

    async def _auto_garden(self):
        try:
            chat = self.config["chat"]
            if not chat:
                return False
            
            async with self._client.conversation(chat, timeout=15) as conv:
                await conv.send_message("Мой сад")
                garden_msg = await conv.get_response()
                await asyncio.sleep(1)
                try:
                    await garden_msg.click(text="💦 Полить сад")
                    await asyncio.sleep(2)
                except Exception:
                    pass
                try:
                    await garden_msg.click(text="💸 Оплатить налоги")
                    await asyncio.sleep(2)
                except Exception:
                    pass

                await conv.send_message("Мой Бизнес")
                business_msg = await conv.get_response()
                await asyncio.sleep(1)
                try:
                    await business_msg.click(text="💸 Оплатить налоги")
                    await asyncio.sleep(2)
                except Exception:
                    pass

                await conv.send_message("Моя ферма")
                mining_farm_msg = await conv.get_response()
                await asyncio.sleep(1)
                try:
                    await mining_farm_msg.click(text="💸 Оплатить налоги")
                    await asyncio.sleep(2)
                except Exception:
                    pass

                await conv.send_message("Моё дерево")
                tree_msg = await conv.get_response()
                await asyncio.sleep(1)
                try:
                    await tree_msg.click(text="💸 Оплатить налоги")
                    await asyncio.sleep(2)
                except Exception:
                    pass

                await conv.send_message("Мой генератор")
                gen_msg = await conv.get_response()
                await asyncio.sleep(1)
                try:
                    await gen_msg.click(text="💸 Оплатить налоги")
                    await asyncio.sleep(2)
                except Exception:
                    pass

                return True

        except Exception:
            return False

    async def _auto_garden_loop(self):
        while self.auto_garden_running:
            success = await self._auto_garden()
            if success:
                try:
                    await self._client(ReadMentionsRequest(self.config["chat"]))
                except Exception:
                    pass
            await asyncio.sleep(60 * self.config["garden_time"])
