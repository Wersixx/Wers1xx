# meta developer: @Wers1xx
# requires: 

import asyncio
import logging
from .. import loader, utils

logger = logging.getLogger(__name__)

# --- Глобальные константы для руд ---
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

# --- Карта команд для копания руды (соответствие выбранной руды и команды) ---
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
class AutoMineOreMod(loader.Module):
    """Автоматическая копка руды по расписанию"""
    strings = {"name": "AutoMineOre"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            # Пока нет конфигов, но можно добавить, если понадобятся
        )
        self.auto_mine_ore_running = False
        self.selected_ore = "Железо"  
        self.bot_id = 1721358063  

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.chat = await self.client.get_entity(self.bot_id)
        
        # Восстанавливаем состояние автокопания руды
        self.auto_mine_ore_running = self.db.get("AutoMineOre", "auto_mine_ore_running", False)
        # Убедимся, что загруженная руда существует, иначе используем дефолт
        self.selected_ore = self.db.get("AutoMineOre", "selected_ore", "Железо")
        if self.selected_ore not in ORES:
            self.selected_ore = "Железо" # Сброс на дефолт, если сохраненная руда недействительна

        if self.auto_mine_ore_running:
            asyncio.create_task(self.auto_mine_ore_loop())
            logger.info("AutoMineOre: Цикл автокопания руды был восстановлен и запущен.")

    # ======= АВТОКОПАНИЕ РУДЫ =======
    def get_mine_ore_keyboard(self):
        """Создает клавиатуру для выбора руды и управления автокопанием."""
        current_ore_emoji = ORES.get(self.selected_ore, "")
        text = (
            f"⛏️ Автокопание руды\n\n"
            f"📊 Статус: {'❤️‍🩹 Запущено' if self.auto_mine_ore_running else '💤 Остановлено'}\n"
            f"🌟 Выбрана руда: {current_ore_emoji} {self.selected_ore}"
        )

        buttons = []
        ore_names = list(ORES.keys())
        
        # Разделяем руды на строки по 3 кнопки для удобства
        for i in range(0, len(ore_names), 3):
            row = []
            for ore_name in ore_names[i : i+3]:
                emoji = ORES[ore_name]
                state_emoji = "❤️‍🩹" if ore_name == self.selected_ore else "💤"
                row.append({"text": f"{state_emoji}{emoji} {ore_name}", "callback": self.select_mine_ore, "args": (ore_name,)})
            buttons.append(row)
        
        # Кнопка старт/стоп
        buttons.append([{"text": "💤 Остановить" if self.auto_mine_ore_running else "❤️‍🩹 Запустить",
                         "callback": self.toggle_auto_mine_ore}])
        
        return text, buttons

    @loader.command(ru_doc="Открыть меню автоматического копания руды")
    async def automineore(self, message):
        """Открыть меню автоматического копания руды"""
        text, markup = self.get_mine_ore_keyboard()
        await self.inline.form(message=message, text=text, reply_markup=markup)

    async def select_mine_ore(self, call, ore_name):
        """Коллбэк для выбора руды."""
        self.selected_ore = ore_name
        self.db.set("AutoMineOre", "selected_ore", ore_name)
        
        text, markup = self.get_mine_ore_keyboard()
        await call.edit(text, reply_markup=markup)
        await call.answer(f"Выбрана руда: {ore_name}")
        logger.info(f"AutoMineOre: Выбрана руда '{ore_name}'.")

    async def toggle_auto_mine_ore(self, call):
        """Коллбэк для запуска/остановки автокопания руды."""
        if self.auto_mine_ore_running:
            self.auto_mine_ore_running = False
            self.db.set("AutoMineOre", "auto_mine_ore_running", False)
            await call.answer("Автокопание руды остановлено.")
            logger.info("AutoMineOre: Автокопание руды остановлено.")
        else:
            self.auto_mine_ore_running = True
            self.db.set("AutoMineOre", "auto_mine_ore_running", True)
            asyncio.create_task(self.auto_mine_ore_loop())
            await call.answer("Автокопание руды запущено.")
            logger.info("AutoMineOre: Автокопание руды запущено.")
        
        text, markup = self.get_mine_ore_keyboard()
        await call.edit(text, reply_markup=markup)

    async def auto_mine_ore_loop(self):
        """Основной цикл для автоматического копания руды."""
        while self.auto_mine_ore_running:
            try:
                # Получаем правильную форму команды из MINE_COMMAND_MAP
                command_arg = MINE_COMMAND_MAP.get(self.selected_ore, self.selected_ore.lower())
                command = f"Копать {command_arg}"
                logger.info(f"AutoMineOre: Отправляем команду: '{command}'.")
                await self.client.send_message(self.chat, command)
                
            except asyncio.CancelledError:
                logger.info("AutoMineOre: Цикл автокопания руды отменен.")
                break
            except Exception as e:
                logger.error(f"AutoMineOre: Критическая ошибка в цикле автокопания руды: {e}", exc_info=True)
                await asyncio.sleep(60) # Пауза в случае ошибки
            
            logger.info(f"AutoMineOre: Ожидание 10 минут (600 секунд) до следующей команды копания '{self.selected_ore}'.")
            await asyncio.sleep(600) # Копаем каждые 10 минут
