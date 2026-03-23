# meta developer: @WersMod
# meta pic: https://example.com/icon.png
# meta banner: https://example.com/banner.png
# scope: hikka_only
# scope: hikka_min 1.2.10

from .. import loader, utils
import asyncio
import re

@loader.tds
class AutoBottlesMod(loader.Module):
    """Автоматическое пополнение бутылок в гильдии"""
    
    strings = {
        "name": "AutoBottles",
        "need_bottles": "🎯 Сколько бутылок нужно вложить?",
        "processing": "🔄 Обрабатываю...",
        "started_infinite": "♾ Бесконечное пополнение запущено! Остановка при 0 бутылок.",
        "started_limited": "🎯 Нужно вложить: {} бутылок. Начинаю...",
        "stopped": "🛑 Пополнение остановлено.",
        "progress": "📊 Прогресс: {}/{} ({}%) | Вложено: +{} | Осталось: {}",
        "finished": "✅ Цель достигнута! Вложено {} бутылок.",
        "zero_bottles": "⚠ Бутылки закончились! Останавливаюсь.",
        "max_detected": "📈 Максимум за раз: {} бутылок",
        "invalid_args": "❌ Укажи число бутылок или 'inf' для бесконечного режима",
        "already_running": "⚠ Уже запущен другой процесс!",
        "no_handler": "⚠ Нет обработчика событий",
        "parse_error": "⚠ Не удалось распознать сообщение",
        "stopped_by_user": "⏹ Остановлено пользователем",
    }
    
    strings_ru = {
        "need_bottles": "🎯 Сколько бутылок нужно вложить?",
        "processing": "🔄 Обрабатываю...",
        "started_infinite": "♾ Бесконечное пополнение запущено! Остановка при 0 бутылок.",
        "started_limited": "🎯 Нужно вложить: {} бутылок. Начинаю...",
        "stopped": "🛑 Пополнение остановлено.",
        "progress": "📊 Прогресс: {}/{} ({}%) | Вложено: +{} | Осталось: {}",
        "finished": "✅ Цель достигнута! Вложено {} бутылок.",
        "zero_bottles": "⚠ Бутылки закончились! Останавливаюсь.",
        "max_detected": "📈 Максимум за раз: {} бутылок",
        "invalid_args": "❌ Укажи число бутылок или 'inf' для бесконечного режима",
        "already_running": "⚠ Уже запущен другой процесс!",
        "no_handler": "⚠ Нет обработчика событий",
        "parse_error": "⚠ Не удалось распознать сообщение",
        "stopped_by_user": "⏹ Остановлено пользователем",
    }
    
    def __init__(self):
        self.running = False
        self.max_per_action = None
        self.target = None
        self.current = 0
    
    @loader.command(
        ru_doc="Запустить автопополнение: .bottles <количество/inf>",
        en_doc="Start auto refill: .bottles <amount/inf>"
    )
    async def bottlescmd(self, message):
        """<количество/inf> - запустить автопополнение"""
        args = utils.get_args_raw(message)
        
        if self.running:
            await utils.answer(message, self.strings("already_running"))
            return
        
        if not args:
            await utils.answer(message, self.strings("invalid_args"))
            return
        
        # Сбрасываем состояние
        self.max_per_action = None
        self.current = 0
        
        if args.lower() == "inf":
            self.target = float('inf')
            await utils.answer(message, self.strings("started_infinite"))
        else:
            try:
                self.target = int(args)
                await utils.answer(message, self.strings("started_limited").format(self.target))
            except ValueError:
                await utils.answer(message, self.strings("invalid_args"))
                return
        
        self.running = True
        
        # Запускаем обработчик сообщений
        handler_id = self._db.get(__name__, "handler_id", None)
        if handler_id:
            self._db.set(__name__, "handler_id", None)
        
        # Запускаем процесс
        asyncio.create_task(self._bottles_loop(message))
    
    async def _bottles_loop(self, message):
        """Основной цикл пополнения"""
        try:
            # Первый запрос с "макс" для определения максимума
            await self._send_command(message, "макс")
            
            # Ждём ответа для определения максимума
            max_wait = 10
            while self.max_per_action is None and max_wait > 0 and self.running:
                await asyncio.sleep(0.5)
                max_wait -= 0.5
            
            if not self.running:
                return
            
            # Основной цикл
            while self.running:
                # Проверяем достижение цели
                if self.current >= self.target:
                    await utils.answer(message, self.strings("finished").format(self.current))
                    self.running = False
                    break
                
                # Определяем сколько вкладывать
                remaining = self.target - self.current
                
                if self.max_per_action is None:
                    # Если максимум ещё не определён, пробуем макс
                    await self._send_command(message, "макс")
                elif remaining > self.max_per_action:
                    # Нужно больше максимума - вкладываем макс
                    await self._send_command(message, "макс")
                else:
                    # Вкладываем остаток
                    await self._send_command(message, str(remaining))
                
                # Ждём 2 секунды перед следующим сообщением
                await asyncio.sleep(2)
                
        except Exception as e:
            await utils.answer(message, f"❌ Ошибка: {e}")
            self.running = False
    
    async def _send_command(self, message, amount):
        """Отправляет команду пополнения"""
        chat = message.chat_id
        cmd = f"Пополнить бутылки {amount}"
        await message.client.send_message(chat, cmd)
    
    @loader.watcher(only_messages=True, only_chats=True)
    async def bottles_watcher(self, message):
        """Отслеживает ответы о пополнении"""
        if not self.running:
            return
        
        text = message.raw_text
        if not text or "ты успешно пополнил" not in text.lower():
            return
        
        # Парсим количество бутылок
        pattern = r"за ([\d\s]+) 🍾"
        match = re.search(pattern, text)
        
        if not match:
            return
        
        bottles_str = match.group(1).replace(" ", "")
        try:
            bottles = int(bottles_str)
        except ValueError:
            return
        
        # Если вложено 0 бутылок - останавливаем
        if bottles == 0:
            await self._stop_with_message(message, self.strings("zero_bottles"))
            return
        
        # Обновляем максимум
        if self.max_per_action is None or bottles > self.max_per_action:
            self.max_per_action = bottles
            await self._send_status(message, self.strings("max_detected").format(bottles))
        
        # Обновляем прогресс
        self.current += bottles
        
        # Если цель конечная - показываем прогресс
        if self.target != float('inf'):
            percent = min(100, int((self.current / self.target) * 100))
            remaining = max(0, self.target - self.current)
            await self._send_status(
                message, 
                self.strings("progress").format(self.current, self.target, percent, bottles, remaining)
            )
    
    async def _send_status(self, message, status_text):
        """Отправляет статус в чат"""
        try:
            await message.reply(status_text)
        except:
            pass
    
    async def _stop_with_message(self, message, reason):
        """Останавливает процесс с сообщением"""
        self.running = False
        await self._send_status(message, reason)
    
    @loader.command(
        ru_doc="Остановить автопополнение",
        en_doc="Stop auto refill"
    )
    async def bottlesstopcmd(self, message):
        """Остановить автопополнение"""
        if not self.running:
            await utils.answer(message, self.strings("stopped"))
            return
        
        self.running = False
        await utils.answer(message, self.strings("stopped_by_user"))