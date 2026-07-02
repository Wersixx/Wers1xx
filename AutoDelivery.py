# meta developer: @Wers1xx
# scope: hikka_only
# requires: telethon

import asyncio
import re
from telethon import events
from .. import loader, utils

class TruckFarmMod(loader.Module):
    """Автоматический фарм рейсов в @botdobryk_bot"""
    strings = {"name": "TruckFarm"}

    async def client_ready(self, client, db):
        self.client = client
        self.running = False
        self._task = None
        
        try:
            self.bot_entity = await client.get_entity("@botdobryk_bot")
            self._log("✅ Бот найден успешно")
        except Exception as e:
            self._log(f"❌ Ошибка получения бота: {e}", "error")
            self.bot_entity = None

    def _log(self, message, level="info"):
        """Внутренний метод логирования."""
        if hasattr(self, 'logger') and self.logger:
            if level == "info":
                self.logger.info(message)
            elif level == "warning":
                self.logger.warning(message)
            elif level == "error":
                self.logger.error(message)
        else:
            print(f"[{level.upper()}] {message}")

    def _clean_text(self, text):
        """Очищает текст от эмодзи и лишних символов."""
        if not text:
            return ""
        
        cleaned = re.sub(r'[^\w\s.,!?\-]', '', text)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def _normalize_button_text(self, text):
        """Нормализует текст кнопки для сравнения."""
        if not text:
            return ""
        cleaned = self._clean_text(text)
        return cleaned.lower().strip()

    async def _send_command(self, command, delay=2):
        """Отправляет команду боту."""
        if not self.bot_entity:
            self._log("❌ Бот не инициализирован", "error")
            return False
        
        try:
            await self.client.send_message(self.bot_entity, command)
            self._log(f"📤 Отправлена команда: {command}")
            await asyncio.sleep(delay)
            return True
        except Exception as e:
            self._log(f"❌ Ошибка отправки {command}: {e}", "error")
            return False

    async def _get_last_messages(self, limit=10):
        """Получает последние сообщения от бота."""
        try:
            return await self.client.get_messages(self.bot_entity, limit=limit)
        except Exception as e:
            self._log(f"❌ Ошибка получения сообщений: {e}", "error")
            return []

    async def _wait_for_text_in_messages(self, texts, timeout=120, check_interval=5):
        """
        Ожидает появление одного из указанных текстов в последних сообщениях.
        Проверяет каждые check_interval секунд.
        """
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            messages = await self._get_last_messages(limit=10)
            
            for msg in messages:
                if msg.text:
                    clean_msg_text = self._clean_text(msg.text)
                    
                    for text in texts:
                        clean_search_text = self._clean_text(text)
                        if clean_search_text.lower() in clean_msg_text.lower():
                            self._log(f"✅ Найден текст: {text}")
                            return msg
            
            await asyncio.sleep(check_interval)
        
        self._log(f"⏰ Таймаут {timeout}с. Текст не найден", "warning")
        return None

    async def _wait_for_new_message(self, texts, timeout=120, check_interval=3, start_id=None):
        """
        Ожидает НОВОЕ сообщение с указанными текстами.
        Проверяет новые сообщения, игнорируя старые.
        """
        # Если start_id не указан, запоминаем последнее известное сообщение
        if start_id is None:
            try:
                last_messages = await self._get_last_messages(limit=1)
                start_id = last_messages[0].id if last_messages else None
            except:
                start_id = None
        
        self._log(f"📌 Начинаем поиск новых сообщений с ID > {start_id}")
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            messages = await self._get_last_messages(limit=10)
            
            for msg in messages:
                # Проверяем, что это новое сообщение
                if start_id and msg.id <= start_id:
                    continue
                    
                if msg.text:
                    clean_msg_text = self._clean_text(msg.text)
                    
                    for text in texts:
                        clean_search_text = self._clean_text(text)
                        if clean_search_text.lower() in clean_msg_text.lower():
                            self._log(f"✅ Найдено новое сообщение: {text}")
                            return msg
            
            await asyncio.sleep(check_interval)
        
        self._log(f"⏰ Таймаут {timeout}с. Новое сообщение не найдено", "warning")
        return None

    async def _parse_time_from_message(self, message):
        """Извлекает время из сообщения."""
        if not message or not message.text:
            return None
        
        text = message.text
        self._log(f"🔍 Парсим время из: {text[:100]}...")
        
        total = 0
        
        hours = re.search(r"(\d+)\s*час", text, re.IGNORECASE)
        minutes = re.search(r"(\d+)\s*минут", text, re.IGNORECASE)
        seconds = re.search(r"(\d+)\s*секунд", text, re.IGNORECASE)
        
        if hours:
            total += int(hours.group(1)) * 3600
        if minutes:
            total += int(minutes.group(1)) * 60
        if seconds:
            total += int(seconds.group(1))
        
        if total == 0:
            time_match = re.search(r"Время:\s*(\d+)", text, re.IGNORECASE)
            if time_match:
                total = int(time_match.group(1)) * 60
        
        if total == 0:
            numbers = re.findall(r"(\d+)", text)
            if numbers:
                num = int(numbers[0])
                if num < 60:
                    total = num * 60
                else:
                    total = num
        
        self._log(f"⏱ Найдено время: {total} секунд")
        return total if total > 0 else 180

    async def _wait_for_job_completion(self):
        """Ожидает завершения рейса."""
        self._log("🔄 Ожидание начала рейса...")
        
        # Запоминаем ID последнего сообщения перед отправкой команды
        try:
            last_messages = await self._get_last_messages(limit=1)
            start_id = last_messages[0].id if last_messages else None
        except:
            start_id = None
        
        # Ждем сообщение "Рейс начался!"
        start_msg = await self._wait_for_new_message(
            ["Рейс начался!"],
            timeout=30,
            check_interval=2,
            start_id=start_id
        )
        
        if not start_msg:
            self._log("⚠️ Сообщение о начале рейса не найдено", "warning")
            return False
        
        # Парсим время из сообщения
        wait_seconds = await self._parse_time_from_message(start_msg)
        self._log(f"⏳ Ожидание {wait_seconds} секунд...")
        
        # Обновляем start_id для поиска завершения
        try:
            last_messages = await self._get_last_messages(limit=1)
            start_id = last_messages[0].id if last_messages else None
        except:
            start_id = None
        
        # Ждем завершения рейса, проверяя каждые 5 секунд
        self._log("🔄 Ожидание завершения рейса...")
        
        # Используем wait_for_new_message для поиска нового сообщения
        complete_msg = await self._wait_for_new_message(
            ["Рейс Завершён", "Рейс завершён", "завершён", "закончился", "рейс завершен"],
            timeout=wait_seconds + 60,
            check_interval=5,
            start_id=start_id
        )
        
        if complete_msg:
            self._log("✅ Рейс завершен!")
            return True
        else:
            self._log("⚠️ Сообщение о завершении не найдено", "warning")
            return False

    async def _click_button(self, message, button_text):
        """Нажимает кнопку с заданным текстом."""
        if not message or not message.buttons:
            return False
        
        search_text = self._normalize_button_text(button_text)
        
        for row in message.buttons:
            for btn in row:
                btn_text = self._normalize_button_text(btn.text)
                
                if btn_text == search_text or search_text in btn_text:
                    self._log(f"🔘 Нажата кнопка: {btn.text}")
                    await btn.click()
                    await asyncio.sleep(1.5)
                    return True
        
        self._log(f"⚠️ Кнопка не найдена: {button_text}", "warning")
        return False

    async def _do_maintenance(self):
        """Обслуживание грузовика."""
        self._log("🔧 Начинаем обслуживание...")
        
        # 1. Отправляем команду
        await self._send_command("🚚 Мой грузовик", 3)
        
        # 2. Ищем сообщение о грузовике с кнопками
        truck_msg = await self._wait_for_text_in_messages(
            ["🚚 Ваш грузовик:", "Ваш грузовик", "грузовик"],
            timeout=15,
            check_interval=2
        )
        
        if not truck_msg:
            self._log("⚠️ Сообщение о грузовике не найдено", "warning")
            return False
        
        # 3. Нажимаем "Полный бак"
        self._log("⛽ Нажимаем 'Полный бак'...")
        await self._click_button(truck_msg, "Полный бак")
        await asyncio.sleep(2)
        
        # 4. Получаем обновленное сообщение и ищем "Полный ремонт"
        self._log("🔧 Ищем кнопку 'Полный ремонт'...")
        
        try:
            updated_msg = await self.client.get_messages(self.bot_entity, ids=truck_msg.id)
            if updated_msg:
                await self._click_button(updated_msg, "Полный ремонт")
            else:
                recent_messages = await self._get_last_messages(limit=5)
                for msg in recent_messages:
                    if msg.buttons:
                        await self._click_button(msg, "Полный ремонт")
                        break
        except Exception as e:
            self._log(f"❌ Ошибка обновления сообщения: {e}", "error")
            recent_messages = await self._get_last_messages(limit=5)
            for msg in recent_messages:
                if msg.buttons:
                    await self._click_button(msg, "Полный ремонт")
                    break
        
        self._log("✅ Обслуживание завершено")
        await asyncio.sleep(2)
        return True

    async def _farm_loop(self):
        """Основной цикл фарма."""
        self._log("🚛 Запуск фарма...")
        
        try:
            # Шаг 1: Вход в профессию
            self._log("📋 Шаг 1: Вход в профессию")
            await self._send_command("💰 Работы", 3)
            await self._send_command("🚚 Дальнобойщик", 3)
            
            # Шаг 2: Начало первого рейса
            self._log("🚚 Шаг 2: Начало первого рейса")
            await self._send_command("🚚 Начать рейс", 3)
            
            # Шаг 3: Ожидание завершения рейса
            self._log("⏳ Ожидание завершения первого рейса...")
            completed = await self._wait_for_job_completion()
            
            if not completed:
                self._log("⚠️ Первый рейс не завершен корректно", "warning")
            
            # Шаг 4: Основной цикл
            cycle_number = 1
            while self.running:
                self._log(f"🔄 Цикл #{cycle_number}")
                
                try:
                    # Обслуживание (заправка + ремонт)
                    self._log("🔧 Начинаем обслуживание перед новым рейсом...")
                    await self._do_maintenance()
                    
                    # Начинаем новый рейс
                    self._log("🚚 Начинаем новый рейс...")
                    await self._send_command("🚚 Ещё рейс", 3)
                    
                    # Ждем завершения
                    self._log("⏳ Ожидание завершения рейса...")
                    completed = await self._wait_for_job_completion()
                    
                    if not completed:
                        self._log("⚠️ Рейс не завершен корректно", "warning")
                    
                    cycle_number += 1
                    
                except asyncio.CancelledError:
                    self._log("⏹ Цикл отменен")
                    break
                except Exception as e:
                    self._log(f"❌ Ошибка в цикле: {e}", "error")
                    self._log("🔄 Перезапуск через 10 секунд...")
                    await asyncio.sleep(10)
                    
                    try:
                        self._log("🔄 Попытка восстановления...")
                        await self._send_command("🚚 Ещё рейс", 3)
                        await self._wait_for_job_completion()
                    except Exception as recovery_error:
                        self._log(f"❌ Ошибка восстановления: {recovery_error}", "error")
                    
        except asyncio.CancelledError:
            self._log("⏹ Фарм остановлен")
        except Exception as e:
            self._log(f"❌ Критическая ошибка: {e}", "error")
        finally:
            self.running = False
            self._log("🛑 Фарм завершен")

    @loader.command()
    async def farmstart(self, message):
        """Запустить автоматический фарм рейсов"""
        if self.running:
            await utils.answer(message, "⚠️ Фарм уже запущен.")
            return
        
        if not self.bot_entity:
            await utils.answer(message, "❌ Бот @botdobryk_bot не найден. Проверьте подписку.")
            return
        
        self.running = True
        self._task = asyncio.ensure_future(self._farm_loop())
        await utils.answer(message, "🚛 Фарм рейсов запущен!")

    @loader.command()
    async def farmstop(self, message):
        """Остановить фарм рейсов"""
        if not self.running:
            await utils.answer(message, "⚠️ Фарм не запущен.")
            return
        
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        await utils.answer(message, "🛑 Фарм остановлен.")

    @loader.command()
    async def farmstatus(self, message):
        """Проверить статус фарма"""
        status = "✅ Активен" if self.running else "❌ Остановлен"
        await utils.answer(message, f"📊 Статус фарма: {status}")