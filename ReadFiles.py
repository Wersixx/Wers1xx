# Copyright 2026, werpyock
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
__version__ = (1, 2, 1)
# meta developer: @Wers1xx
import os
import zipfile
import pickle
import asyncio
import re
from telethon.tl.types import Message
from telethon.tl.custom import Message as CustomMessage
from .. import loader, utils

@loader.tds
class ReadFileMod(loader.Module):
    """Чтение файла из реплая и упаковка текста в файл"""

    strings = {"name": "ReadFile"}

    def __init__(self):
        self.chunks = []
        self.file_info = {}
        self.file_content = ""
        self.file_path = ""
        self.binary_mode = False

    async def rfcmd(self, message: Message):
        """загрузить и прочитать файл."""
        reply = await message.get_reply_message()
        if not reply or not reply.file:
            await message.edit("❌ Ответь на файл.")
            return

        await message.edit("📥 Загружаю файл...")
        self.file_path = await reply.download_media()
        file_ext = os.path.splitext(self.file_path)[1].lower()
        
        try:
            # Обработка ZIP файлов
            if file_ext == '.zip':
                self.file_content = self._read_zip_file(self.file_path)
                self.binary_mode = False
            # Обработка pickle файлов
            elif file_ext in ['.pkl', '.pickle']:
                self.file_content = self._read_pickle_file(self.file_path)
                self.binary_mode = False
            # Обработка бинарных файлов
            elif file_ext in ['.pyc', '.exe', '.dll', '.so', '.bin', '.dat']:
                self.file_content = self._read_binary_file(self.file_path)
                self.binary_mode = True
            # Текстовые файлы
            else:
                self.file_content = self._read_text_file(self.file_path)
                self.binary_mode = False
                
        except Exception as e:
            await message.edit(f"❌ Ошибка при чтении: {e}")
            return

        # Подсчет строк
        line_count = self._count_lines(self.file_content, self.binary_mode)
        
        self.chunks = self._split_text(self.file_content, 1500)
        self.file_info = {
            "Имя": os.path.basename(self.file_path),
            "Размер": f"{os.path.getsize(self.file_path)} байт",
            "Путь": self.file_path,
            "Страниц": len(self.chunks),
            "Строк": line_count,
            "Тип": "Бинарный" if self.binary_mode else "Текстовый"
        }

        await self._show_page(message, 0)

    async def rpycmd(self, message: Message):
        """упаковать текст из реплая в .py файл."""
        reply = await message.get_reply_message()
        if not reply:
            await message.edit("❌ Ответь на сообщение с текстом.")
            return
        
        await message.edit("📦 Собираю текст...")
        
        try:
            full_text = await self._collect_text_from_message(reply, message)
            
            if not full_text.strip():
                await message.edit("❌ Не удалось получить текст.")
                return
            
            # Определяем имя файла
            file_name = self._generate_filename(full_text)
            
            # Сохраняем файл
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(full_text)
            
            # Отправляем файл
            file_size = os.path.getsize(file_name)
            line_count = full_text.count('\n') + 1
            
            caption = (
                f"📄 Файл: {file_name}\n"
                f"📏 Строк: {line_count}\n"
                f"📄 Страниц собрано: {len(self._collected_pages)}\n"
                f"💾 Размер: {file_size} байт"
            )
            
            await message.client.send_file(
                message.chat_id,
                file_name,
                caption=caption,
                reply_to=reply.id
            )
            
            # Удаляем временный файл
            os.remove(file_name)
            await message.delete()
            
        except Exception as e:
            await message.edit(f"❌ Ошибка при сохранении: {e}")

    async def _collect_text_from_message(self, reply, message):
        """Собирает весь текст из сообщения, включая все страницы инлайн кнопок"""
        self._collected_pages = []
        processed_messages = set()
        all_pages = {}
        
        # Проверяем, есть ли в сообщении текст
        if reply.text:
            self._collected_pages.append(reply.text)
            all_pages[0] = reply.text
        
        # Проверяем, есть ли инлайн кнопки
        if reply.reply_markup and hasattr(reply.reply_markup, 'rows'):
            navigation_type = self._detect_navigation_type(reply.reply_markup)
            
            if navigation_type:
                await message.edit(f"📖 Перелистываю страницы (тип: {navigation_type})...")
                
                if navigation_type == "arrows":
                    # Навигация стрелками ⬅️ ➡️
                    await self._collect_arrows_pages(reply, all_pages, processed_messages)
                    
                elif navigation_type == "numbers":
                    # Навигация цифрами 1 2 3 4 5
                    await self._collect_numbers_pages(reply, all_pages, processed_messages)
                    
                elif navigation_type == "prev_next":
                    # Навигация "Назад" "Вперед" или "◀" "▶"
                    await self._collect_prev_next_pages(reply, all_pages, processed_messages)
        
        # Если в сообщении есть файл, но нет текста
        elif reply.file and not reply.text:
            await message.edit("📥 Загружаю файл...")
            temp_path = await reply.download_media()
            try:
                text = self._read_text_file(temp_path)
                self._collected_pages = [text]
                all_pages[0] = text
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        
        # Сортируем и объединяем страницы
        if len(all_pages) > 1:
            sorted_pages = [all_pages[key] for key in sorted(all_pages.keys())]
        else:
            sorted_pages = list(all_pages.values())
        
        # Извлекаем чистый текст из всех страниц
        return self._extract_text_from_pages(sorted_pages)

    def _detect_navigation_type(self, reply_markup):
        """Определяет тип навигации по кнопкам"""
        all_buttons = []
        for row in reply_markup.rows:
            for button in row.buttons:
                all_buttons.append(button.text)
        
        # Проверяем стрелки
        if "⬅️" in all_buttons and "➡️" in all_buttons:
            return "arrows"
        elif "◀" in all_buttons and "▶" in all_buttons:
            return "arrows"
        
        # Проверяем цифровую навигацию
        numbers = [b for b in all_buttons if b.isdigit()]
        if len(numbers) >= 3:  # Если есть хотя бы 3 цифровые кнопки
            return "numbers"
        
        # Проверяем текстовую навигацию
        nav_texts = ["назад", "вперед", "←", "→", "prev", "next", "<<"]
        if any(nav in ' '.join(all_buttons).lower() for nav in nav_texts):
            return "prev_next"
        
        return None

    async def _collect_arrows_pages(self, reply, all_pages, processed_messages):
        """Собирает страницы с навигацией стрелками"""
        current_msg = reply
        processed_messages.add(current_msg.id)
        
        # Идем вперед
        for _ in range(50):  # Максимум 50 страниц
            next_btn = self._find_button(current_msg, ["➡️", "▶"])
            if not next_btn or current_msg.id in processed_messages:
                break
            
            try:
                result = await next_btn.click()
                if result and result.id not in processed_messages:
                    processed_messages.add(result.id)
                    page_num = len(all_pages)
                    if result.text:
                        all_pages[page_num] = result.text
                        self._collected_pages.append(result.text)
                    current_msg = result
                    await asyncio.sleep(0.3)
                else:
                    break
            except:
                break
        
        # Возвращаемся к началу
        current_msg = reply
        
        # Идем назад
        for _ in range(50):  # Максимум 50 страниц
            prev_btn = self._find_button(current_msg, ["⬅️", "◀"])
            if not prev_btn:
                break
            
            try:
                result = await prev_btn.click()
                if result and result.id not in processed_messages:
                    processed_messages.add(result.id)
                    if result.text:
                        # Вставляем в начало
                        all_pages[-1] = result.text
                        self._collected_pages.insert(0, result.text)
                    current_msg = result
                    await asyncio.sleep(0.3)
                else:
                    break
            except:
                break

    async def _collect_numbers_pages(self, reply, all_pages, processed_messages):
        """Собирает страницы с цифровой навигацией"""
        current_msg = reply
        processed_messages.add(current_msg.id)
        
        # Получаем все цифровые кнопки
        number_buttons = self._get_number_buttons(reply)
        
        # Перебираем все цифровые кнопки
        for page_num in sorted(number_buttons.keys()):
            if page_num == self._get_current_page_number(reply):
                continue  # Пропускаем текущую страницу
            
            btn = number_buttons[page_num]
            
            # Ищем кнопку на текущем сообщении
            for _ in range(3):  # Пробуем 3 раза
                found_btn = self._find_button_by_text(current_msg, str(page_num))
                if found_btn:
                    try:
                        result = await found_btn.click()
                        if result and result.id not in processed_messages:
                            processed_messages.add(result.id)
                            if result.text:
                                all_pages[page_num] = result.text
                                self._collected_pages.append(result.text)
                            current_msg = result
                            await asyncio.sleep(0.3)
                            break
                    except:
                        await asyncio.sleep(0.5)
                else:
                    # Если кнопка не найдена, пробуем найти на reply
                    found_btn = self._find_button_by_text(reply, str(page_num))
                    if found_btn:
                        try:
                            result = await found_btn.click()
                            if result and result.id not in processed_messages:
                                processed_messages.add(result.id)
                                if result.text:
                                    all_pages[page_num] = result.text
                                    self._collected_pages.append(result.text)
                                current_msg = result
                                await asyncio.sleep(0.3)
                                break
                        except:
                            break

    def _get_number_buttons(self, message):
        """Получает словарь {номер_страницы: кнопка}"""
        buttons = {}
        if message.reply_markup and hasattr(message.reply_markup, 'rows'):
            for row in message.reply_markup.rows:
                for button in row.buttons:
                    if button.text.isdigit():
                        buttons[int(button.text)] = button
        return buttons

    def _get_current_page_number(self, message):
        """Определяет номер текущей страницы из текста сообщения"""
        if message.text:
            # Ищем паттерны типа "Страница X/Y" или "Page X/Y"
            match = re.search(r'(?:Страница|Page)\s*(\d+)/(\d+)', message.text)
            if match:
                return int(match.group(1))
            
            # Ищем просто номер страницы
            match = re.search(r'📒\s*Страница\s*(\d+)', message.text)
            if match:
                return int(match.group(1))
        return 0

    def _find_button(self, message, texts):
        """Ищет кнопку по тексту"""
        if not message.reply_markup or not hasattr(message.reply_markup, 'rows'):
            return None
        
        for row in message.reply_markup.rows:
            for button in row.buttons:
                if button.text in texts:
                    return button
        return None

    def _find_button_by_text(self, message, text):
        """Ищет кнопку по точному тексту"""
        if not message.reply_markup or not hasattr(message.reply_markup, 'rows'):
            return None
        
        for row in message.reply_markup.rows:
            for button in row.buttons:
                if button.text == text:
                    return button
        return None

    async def _collect_prev_next_pages(self, reply, all_pages, processed_messages):
        """Собирает страницы с навигацией Назад/Вперед"""
        current_msg = reply
        processed_messages.add(current_msg.id)
        
        next_texts = ["Вперед", "вперед", "Next", "next", "▶", "→", ">>"]
        prev_texts = ["Назад", "назад", "Prev", "prev", "◀", "←", "<<"]
        
        # Идем вперед
        for _ in range(50):
            next_btn = self._find_button(current_msg, next_texts)
            if not next_btn:
                break
            
            try:
                result = await next_btn.click()
                if result and result.id not in processed_messages:
                    processed_messages.add(result.id)
                    page_num = len(all_pages)
                    if result.text:
                        all_pages[page_num] = result.text
                        self._collected_pages.append(result.text)
                    current_msg = result
                    await asyncio.sleep(0.3)
                else:
                    break
            except:
                break
        
        # Возвращаемся к началу
        current_msg = reply
        
        # Идем назад
        for _ in range(50):
            prev_btn = self._find_button(current_msg, prev_texts)
            if not prev_btn:
                break
            
            try:
                result = await prev_btn.click()
                if result and result.id not in processed_messages:
                    processed_messages.add(result.id)
                    if result.text:
                        all_pages[-1] = result.text
                        self._collected_pages.insert(0, result.text)
                    current_msg = result
                    await asyncio.sleep(0.3)
                else:
                    break
            except:
                break

    def _extract_text_from_pages(self, pages):
        """Извлекает чистый текст из страниц, убирая навигационную информацию"""
        if not pages:
            return ""
        
        texts = []
        for page in pages:
            lines = page.split('\n')
            clean_lines = []
            skip_next = False
            
            for line in lines:
                # Пропускаем строки с номерами страниц
                if re.search(r'📒\s*Страница\s*\d+', line):
                    skip_next = True
                    continue
                if skip_next and not line.strip():
                    skip_next = False
                    continue
                
                # Убираем обертки <pre> и </pre> если есть
                line = line.replace('<pre>', '').replace('</pre>', '')
                line = line.replace('<code>', '').replace('</code>', '')
                
                clean_lines.append(line)
            
            clean_text = '\n'.join(clean_lines).strip()
            if clean_text:
                texts.append(clean_text)
        
        return self._merge_unique_texts(texts)

    def _merge_unique_texts(self, texts):
        """Объединяет тексты, убирая дублирующиеся части"""
        if not texts:
            return ""
        
        if len(texts) == 1:
            return texts[0]
        
        # Проверяем, нет ли полных дубликатов
        unique_texts = []
        seen = set()
        for text in texts:
            if text not in seen:
                unique_texts.append(text)
                seen.add(text)
        
        if len(unique_texts) == 1:
            return unique_texts[0]
        
        # Пытаемся объединить тексты
        merged = unique_texts[0]
        for next_text in unique_texts[1:]:
            overlap = self._find_overlap(merged, next_text)
            if overlap > 0:
                merged = merged + next_text[overlap:]
            else:
                merged += '\n' + next_text
        
        return merged

    def _find_overlap(self, text1, text2):
        """Находит длину перекрытия между концом text1 и началом text2"""
        max_overlap = min(len(text1), len(text2), 100)
        for i in range(max_overlap, 0, -1):
            if text1[-i:] == text2[:i]:
                return i
        return 0

    def _generate_filename(self, text):
        """Генерирует имя файла на основе содержимого"""
        # Пытаемся определить тип файла по содержимому
        first_line = text.split('\n')[0].strip() if text else ""
        
        if first_line.startswith('#!') or first_line.startswith('#!/'):
            return "script.sh"
        elif 'import' in first_line and ('python' in text[:100].lower() or '.py' in first_line):
            return "script.py"
        elif '<html' in first_line.lower() or '<!doctype' in first_line.lower():
            return "page.html"
        elif first_line.startswith('{') or first_line.startswith('['):
            try:
                import json
                json.loads(text[:1000])
                return "data.json"
            except:
                pass
        elif first_line.startswith('<?xml'):
            return "data.xml"
        
        # По умолчанию
        return "output.txt"

    def _read_text_file(self, path):
        """Чтение текстового файла"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            for encoding in ['latin-1', 'cp1251', 'koi8-r']:
                try:
                    with open(path, "r", encoding=encoding) as f:
                        return f.read()
                except:
                    continue
            return self._read_binary_file(path)

    def _read_binary_file(self, path):
        """Чтение бинарного файла с представлением в hex"""
        with open(path, "rb") as f:
            content = f.read()
        
        if len(content) > 10000:
            content = content[:10000]
            truncated = True
        else:
            truncated = False
        
        result = []
        for i in range(0, len(content), 16):
            chunk = content[i:i+16]
            hex_part = ' '.join([f'{b:02x}' for b in chunk])
            ascii_part = ''.join([chr(b) if 32 <= b <= 126 else '.' for b in chunk])
            result.append(f"{i:08x}  {hex_part:<48}  {ascii_part}")
        
        output = "Шестнадцатеричное представление:\n" + '\n'.join(result)
        if truncated:
            output += "\n\n[Файл обрезан до первых 10000 байт]"
        
        return output

    def _read_zip_file(self, path):
        """Чтение содержимого ZIP архива"""
        result = []
        try:
            with zipfile.ZipFile(path, 'r') as zip_ref:
                result.append(f"📦 ZIP архив содержит {len(zip_ref.namelist())} файлов:\n")
                for file_name in zip_ref.namelist():
                    info = zip_ref.getinfo(file_name)
                    if info.is_dir():
                        result.append(f"📁 {file_name}/")
                    else:
                        size_kb = info.file_size / 1024
                        result.append(f"📄 {file_name} ({size_kb:.1f} КБ)")
        except:
            result.append("❌ Не удалось прочитать ZIP архив")
        
        return '\n'.join(result)

    def _read_pickle_file(self, path):
        """Чтение pickle файла"""
        try:
            with open(path, 'rb') as f:
                data = pickle.load(f)
            
            result = []
            result.append(f"Тип данных: {type(data).__name__}\n")
            
            if isinstance(data, dict):
                result.append(f"Словарь с {len(data)} ключами:")
                for key in list(data.keys())[:20]:
                    result.append(f"  {key}: {type(data[key]).__name__}")
                if len(data) > 20:
                    result.append(f"  ... и еще {len(data) - 20} ключей")
            elif isinstance(data, list):
                result.append(f"Список из {len(data)} элементов")
                result.append(f"Первые элементы: {data[:5]}")
            else:
                result.append(str(data)[:1000])
            
            return '\n'.join(result)
        except Exception as e:
            return f"❌ Ошибка чтения pickle: {e}"

    def _count_lines(self, content, binary_mode):
        """Подсчет количества строк"""
        return content.count('\n') + 1

    def _split_text(self, text, size):
        return [text[i:i + size] for i in range(0, len(text), size)]

    async def _show_page(self, msg_or_call, index):
        total = len(self.chunks)
        index = max(0, min(index, total - 1))
        
        if self.binary_mode:
            text = f"📒 Страница {index + 1}/{total}\n<code>{utils.escape_html(self.chunks[index])}</code>"
        else:
            text = f"📒 Страница {index + 1}/{total}\n<pre>{utils.escape_html(self.chunks[index])}</pre>"
        
        buttons = [
            [
                {"text": "⬅️", "callback": self._page_cb, "args": (index - 1,)},
                {"text": str(index + 1), "callback": self._page_cb, "args": (index,)},
                {"text": "➡️", "callback": self._page_cb, "args": (index + 1,)}
            ],
            [
                {"text": "ℹ️ Инфа", "callback": self._info_cb, "args": (index,)}
            ]
        ]

        if isinstance(msg_or_call, Message):
            await self.inline.form(text=text, message=msg_or_call, reply_markup=buttons)
        elif hasattr(msg_or_call, "edit"):
            await msg_or_call.edit(text=text, reply_markup=buttons)

    async def _page_cb(self, call, index):
        await self._show_page(call, index)

    async def _info_cb(self, call, return_index):
        info_text = "\n".join([f"<b>{k}:</b> {utils.escape_html(str(v))}" for k, v in self.file_info.items()])
        await call.edit(
            text=f"📄 Информация о файле:\n{info_text}",
            reply_markup=[
                [{"text": "↩️ Назад", "callback": self._page_cb, "args": (return_index,)}]
            ]
        )