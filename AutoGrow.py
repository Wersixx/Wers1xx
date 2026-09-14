# meta developer: @Wers1xx
# requires: re

import re
import asyncio
import logging
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class AutoGrow(loader.Module):
    """Автоматическое выращивание овощей в теплице"""
    strings = {"name": "AutoGrow"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "vegetable",
                "картошку",
                lambda: "Выбранный овощ для автовыращивания",
                validator=loader.validators.Choice([
                    "картошку", "морковь", "рис", "чеснок", "свеклу", 
                    "огурец", "капусту", "фасоль", "помидор", "баклажан"
                ])
            ),
        )
        
        # Состояние
        self.running = False
        self.bot_id = 8748567379

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.chat = await self.client.get_entity(self.bot_id)
        
        # Восстанавливаем состояние
        self.running = self.db.get("AutoGrow", "running", False)
        
        # Запускаем задачу, если была активна
        if self.running:
            asyncio.create_task(self.grow_loop())

    def get_grow_keyboard(self):
        """Создает клавиатуру для теплицы"""
        veggies = [
            ("🥔 Картошка", "картошку"),
            ("🥕 Морковь", "морковь"),
            ("🍚 Рис", "рис"),
            ("🧄 Чеснок", "чеснок"),
            ("🍠 Свекла", "свеклу"),
            ("🥒 Огурец", "огурец"),
            ("🥬 Капуста", "капусту"),
            ("🫘 Фасоль", "фасоль"),
            ("🍅 Помидор", "помидор"),
            ("🍆 Баклажан", "баклажан")
        ]
        
        current_veg = self.config["vegetable"]
        
        buttons = []
        row = []
        for i, (display_name, veg_name) in enumerate(veggies):
            state = "❤️‍🩹" if veg_name == current_veg else "💤"
            row.append({"text": f"{state} {display_name}", "callback": self.select_veg, "args": (veg_name,)})
            if len(row) == 3 or i == len(veggies) - 1:
                buttons.append(row)
                row = []
        
        buttons.append([
            {"text": "🔋 Старт" if not self.running else "🪫 Стоп", "callback": self.toggle_grow}
        ])
        
        return buttons

    @loader.command(ru_doc="Открыть меню автовыращивания овощей")
    async def autogrow(self, message):
        """Открыть меню автовыращивания овощей"""
        veg_display = {
            "картошку": "Картошка",
            "морковь": "Морковь",
            "рис": "Рис",
            "чеснок": "Чеснок",
            "свеклу": "Свекла",
            "огурец": "Огурец",
            "капусту": "Капуста",
            "фасоль": "Фасоль",
            "помидор": "Помидор",
            "баклажан": "Баклажан"
        }.get(self.config["vegetable"], self.config["vegetable"])
        
        text = (
            f"🌱 <b>Автовыращивание овощей</b>\n\n"
            f"🥗 Овощ: {veg_display}\n"
            f"📊 Статус: {'❤️‍🩹 Запущено' if self.running else '💤 Остановлено'}\n\n"
            f"Выберите овощ для выращивания и нажмите Старт"
        )
        
        await self.inline.form(
            message=message,
            text=text,
            reply_markup=self.get_grow_keyboard()
        )

    async def select_veg(self, call, veg):
        """Выбор овоща для выращивания"""
        self.config["vegetable"] = veg
        self.db.set("AutoGrow", "vegetable", veg)
        
        veg_display = {
            "картошку": "Картошка",
            "морковь": "Морковь",
            "рис": "Рис",
            "чеснок": "Чеснок",
            "свеклу": "Свекла",
            "огурец": "Огурец",
            "капусту": "Капуста",
            "фасоль": "Фасоль",
            "помидор": "Помидор",
            "баклажан": "Баклажан"
        }.get(veg, veg)
        
        text = (
            f"🌱 <b>Автовыращивание овощей</b>\n\n"
            f"🥗 Овощ: {veg_display}\n"
            f"📊 Статус: {'❤️‍🩹 Запущено' if self.running else '💤 Остановлено'}\n\n"
            f"Выберите овощ для выращивания и нажмите Старт"
        )
        
        await call.edit(text, reply_markup=self.get_grow_keyboard())

    async def toggle_grow(self, call):
        """Переключает состояние автовыращивания (запуск/остановка)"""
        if self.running:
            self.running = False
            self.db.set("AutoGrow", "running", False)
            await call.answer("Автовыращивание остановлено.")
        else:
            self.running = True
            self.db.set("AutoGrow", "running", True)
            asyncio.create_task(self.grow_loop())
            await call.answer("Автовыращивание запущено.")
        
        veg_display = {
            "картошку": "Картошка",
            "морковь": "Морковь",
            "рис": "Рис",
            "чеснок": "Чеснок",
            "свеклу": "Свекла",
            "огурец": "Огурец",
            "капусту": "Капуста",
            "фасоль": "Фасоль",
            "помидор": "Помидор",
            "баклажан": "Баклажан"
        }.get(self.config["vegetable"], self.config["vegetable"])
        
        text = (
            f"🌱 <b>Автовыращивание овощей</b>\n\n"
            f"🥗 Овощ: {veg_display}\n"
            f"📊 Статус: {'❤️‍🩹 Запущено' if self.running else '💤 Остановлено'}\n\n"
            f"Выберите овощ для выращивания и нажмите Старт"
        )
        
        await call.edit(text, reply_markup=self.get_grow_keyboard())

    async def grow_loop(self):
        """Основной цикл для автовыращивания овощей"""
        while self.running:
            try:
                await self.client.send_message(self.chat, f"Вырастить {self.config['vegetable']}")
                logger.info(f"Отправлена команда: Вырастить {self.config['vegetable']}")
                await asyncio.sleep(602)  # ~10 минут
            except asyncio.CancelledError:
                logger.info("Цикл автовыращивания отменен.")
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле автовыращивания: {e}", exc_info=True)
                await asyncio.sleep(60)

    @loader.command(ru_doc="Запустить автовыращивание овощей")
    async def startgrow(self, message):
        """Запустить автовыращивание овощей"""
        if self.running:
            return await utils.answer(message, "❌ Автовыращивание уже запущено.")
        
        self.running = True
        self.db.set("AutoGrow", "running", True)
        asyncio.create_task(self.grow_loop())
        await utils.answer(message, f"✅ Автовыращивание {self.config['vegetable']} запущено.")

    @loader.command(ru_doc="Остановить автовыращивание овощей")
    async def stopgrow(self, message):
        """Остановить автовыращивание овощей"""
        if not self.running:
            return await utils.answer(message, "❌ Автовыращивание не запущено.")
        
        self.running = False
        self.db.set("AutoGrow", "running", False)
        await utils.answer(message, "✅ Автовыращивание остановлено.")

    @loader.command(ru_doc="Выбрать овощ для выращивания")
    async def setveg(self, message):
        """Выбрать овощ для выращивания
        
        Доступные овощи: картошку, морковь, рис, чеснок, свеклу, огурец, капусту, фасоль, помидор, баклажан
        Пример: .setveg картошку
        """
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(
                message,
                "❌ Укажите овощ.\n"
                "Доступные: картошку, морковь, рис, чеснок, свеклу, огурец, капусту, фасоль, помидор, баклажан"
            )
        
        veg = args.lower().strip()
        available = ["картошку", "морковь", "рис", "чеснок", "свеклу", "огурец", "капусту", "фасоль", "помидор", "баклажан"]
        
        if veg not in available:
            return await utils.answer(
                message,
                f"❌ Неверный овощ: {veg}\n"
                f"Доступные: {', '.join(available)}"
            )
        
        self.config["vegetable"] = veg
        self.db.set("AutoGrow", "vegetable", veg)
        await utils.answer(message, f"✅ Выбран овощ: {veg}")

    @loader.command(ru_doc="Показать статус автовыращивания")
    async def growstatus(self, message):
        """Показать статус автовыращивания"""
        veg_display = {
            "картошку": "Картошка",
            "морковь": "Морковь",
            "рис": "Рис",
            "чеснок": "Чеснок",
            "свеклу": "Свекла",
            "огурец": "Огурец",
            "капусту": "Капуста",
            "фасоль": "Фасоль",
            "помидор": "Помидор",
            "баклажан": "Баклажан"
        }.get(self.config["vegetable"], self.config["vegetable"])
        
        text = (
            f"🌱 <b>Статус автовыращивания</b>\n\n"
            f"🥗 Овощ: {veg_display}\n"
            f"📊 Статус: {'❤️‍🩹 Запущено' if self.running else '💤 Остановлено'}\n"
            f"⏱️ Интервал: ~10 минут"
        )
        
        await utils.answer(message, text)