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
__version__ = (2, 0, 0)
# meta developer: @Wers1xx
import os
import zipfile
import pickle
import asyncio
import re
import json
import sqlite3
from datetime import datetime
from telethon.tl.types import Message
from telethon.tl.custom import Message as CustomMessage
from .. import loader, utils

@loader.tds
class ReadFileMod(loader.Module):
    """Чтение файлов, база данных, редактирование и упаковка в разные форматы"""

    strings = {"name": "ReadFile"}

    def __init__(self):
        self.chunks = []
        self.file_info = {}
        self.file_content = ""
        self.file_path = ""
        self.binary_mode = False
        self.db_path = "readfile_storage.db"
        self._init_db()
        self._collected_pages = []
        
    def _init_db(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                file_type TEXT NOT NULL,
                size INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER,
                content TEXT NOT NULL,
                version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files (id)
            )
        ''')
        conn.commit()
        conn.close()

    def _save_to_db(self, name, content, file_type):
        """Сохраняет файл в БД"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Проверяем, существует ли файл
        cursor.execute("SELECT id FROM files WHERE name = ?", (name,))
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующий файл
            file_id = existing[0]
            cursor.execute(
                "UPDATE files SET content = ?, size = ?, updated_at = ? WHERE id = ?",
                (content, len(content), datetime.now().isoformat(), file_id)
            )
            # Сохраняем версию
            cursor.execute(
                "INSERT INTO file_versions (file_id, content, version, created_at) VALUES (?, ?, (SELECT COUNT(*) FROM file_versions WHERE file_id = ?) + 1, ?)",
                (file_id, content, file_id, datetime.now().isoformat())
            )
        else:
            # Создаем новый файл
            cursor.execute(
                "INSERT INTO files (name, content, file_type, size, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (name, content, file_type, len(content), datetime.now().isoformat(), datetime.now().isoformat())
            )
            file_id = cursor.lastrowid
            # Сохраняем первую версию
            cursor.execute(
                "INSERT INTO file_versions (file_id, content, version, created_at) VALUES (?, ?, 1, ?)",
                (file_id, content, datetime.now().isoformat())
            )
        
        conn.commit()
        conn.close()
        return file_id

    def _get_from_db(self, name=None, file_id=None):
        """Получает файл из БД"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if file_id:
            cursor.execute("SELECT id, name, content, file_type, size, created_at, updated_at FROM files WHERE id = ?", (file_id,))
        elif name:
            cursor.execute("SELECT id, name, content, file_type, size, created_at, updated_at FROM files WHERE name = ?", (name,))
        else:
            cursor.execute("SELECT id, name, content, file_type, size, created_at, updated_at FROM files ORDER BY id DESC")
        
        result = cursor.fetchall()
        conn.close()
        
        if not result:
            return None
        
        if len(result) == 1 and (name or file_id):
            row = result[0]
            return {
                "id": row[0],
                "name": row[1],
                "content": row[2],
                "file_type": row[3],
                "size": row[4],
                "created_at": row[5],
                "updated_at": row[6]
            }
        return result

    def _delete_from_db(self, name):
        """Удаляет файл из БД"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM files WHERE name = ?", (name,))
        file = cursor.fetchone()
        if file:
            cursor.execute("DELETE FROM file_versions WHERE file_id = ?", (file[0],))
            cursor.execute("DELETE FROM files WHERE id = ?", (file[0],))
            conn.commit()
            conn.close()
            return True
        conn.close()
        return False

    def _list_files_db(self, page=0, per_page=10):
        """Получает список файлов с пагинацией"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        offset = page * per_page
        cursor.execute(
            "SELECT id, name, file_type, size, created_at, updated_at FROM files ORDER BY id DESC LIMIT ? OFFSET ?",
            (per_page, offset)
        )
        files = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) FROM files")
        total = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "files": files,
            "total": total,
            "page": page,
            "pages": (total + per_page - 1) // per_page
        }

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
            if file_ext == '.zip':
                self.file_content = self._read_zip_file(self.file_path)
                self.binary_mode = False
            elif file_ext in ['.pkl', '.pickle']:
                self.file_content = self._read_pickle_file(self.file_path)
                self.binary_mode = False
            elif file_ext in ['.pyc', '.exe', '.dll', '.so', '.bin', '.dat']:
                self.file_content = self._read_binary_file(self.file_path)
                self.binary_mode = True
            else:
                self.file_content = self._read_text_file(self.file_path)
                self.binary_mode = False
                
        except Exception as e:
            await message.edit(f"❌ Ошибка при чтении: {e}")
            return

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
        """упаковать текст в файл. Формат: .rpy [формат] (реплай на текст)"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        if not reply:
            await message.edit("❌ Ответь на сообщение с текстом.")
            return
        
        # Определяем формат
        if args:
            fmt = args.lower().strip()
            if fmt.startswith('.'):
                fmt = fmt[1:]
            valid_formats = ['py', 'txt', 'json', 'xml', 'html', 'css', 'js', 'md', 'csv', 'log', 'sh', 'bat']
            if fmt not in valid_formats and fmt != 'zip':
                await message.edit(f"❌ Неподдерживаемый формат. Доступны: {', '.join(valid_formats)}, zip")
                return
        else:
            fmt = 'txt'
        
        await message.edit(f"📦 Собираю текст в формат {fmt}...")
        
        try:
            full_text = await self._collect_text_from_message(reply, message)
            
            if not full_text.strip():
                await message.edit("❌ Не удалось получить текст.")
                return
            
            # Генерируем имя файла
            file_name = self._generate_filename(full_text, fmt)
            
            if fmt == 'json':
                try:
                    # Пытаемся парсить JSON
                    json_data = json.loads(full_text)
                    content = json.dumps(json_data, indent=2, ensure_ascii=False)
                except:
                    # Если не JSON, создаем JSON объект с текстом
                    content = json.dumps({"text": full_text}, indent=2, ensure_ascii=False)
            elif fmt == 'zip':
                # Создаем ZIP архив
                zip_name = f"{file_name.split('.')[0]}.zip"
                with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    temp_file = f"temp_{file_name}"
                    with open(temp_file, "w", encoding="utf-8") as f:
                        f.write(full_text)
                    zipf.write(temp_file, file_name)
                    os.remove(temp_file)
                file_name = zip_name
                content = full_text
            else:
                content = full_text
            
            # Сохраняем в БД
            if fmt != 'zip':
                self._save_to_db(file_name, content, fmt)
            
            # Сохраняем локальный файл
            if fmt != 'zip':
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(content)
            
            # Отправляем файл
            file_size = os.path.getsize(file_name)
            line_count = content.count('\n') + 1 if fmt != 'zip' else 0
            
            caption = (
                f"📄 Файл: {file_name}\n"
                f"📏 Строк: {line_count}\n"
                f"📄 Страниц собрано: {len(self._collected_pages)}\n"
                f"💾 Размер: {file_size} байт\n"
                f"📁 Формат: {fmt}"
            )
            
            if fmt == 'zip':
                caption = f"📦 Архив: {file_name}\n💾 Размер: {file_size} байт"
            
            await message.client.send_file(
                message.chat_id,
                file_name,
                caption=caption,
                reply_to=reply.id
            )
            
            # Удаляем временный файл
            if os.path.exists(file_name):
                os.remove(file_name)
            await message.delete()
            
        except Exception as e:
            await message.edit(f"❌ Ошибка при сохранении: {e}")

    async def savecmd(self, message: Message):
        """сохранить текст в БД. Формат: .save [имя] [формат] (реплай на текст)"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        if not reply:
            await message.edit("❌ Ответь на сообщение с текстом.")
            return
        
        if not args:
            await message.edit("❌ Укажи имя файла и формат. Пример: .save myfile txt")
            return
        
        parts = args.split()
        if len(parts) < 2:
            await message.edit("❌ Укажи имя файла и формат. Пример: .save myfile txt")
            return
        
        name = parts[0]
        fmt = parts[1].lower()
        if fmt.startswith('.'):
            fmt = fmt[1:]
        
        valid_formats = ['py', 'txt', 'json', 'xml', 'html', 'css', 'js', 'md', 'csv', 'log', 'sh', 'bat']
        if fmt not in valid_formats:
            await message.edit(f"❌ Неподдерживаемый формат. Доступны: {', '.join(valid_formats)}")
            return
        
        file_name = f"{name}.{fmt}"
        
        try:
            full_text = await self._collect_text_from_message(reply, message)
            
            if not full_text.strip():
                await message.edit("❌ Не удалось получить текст.")
                return
            
            self._save_to_db(file_name, full_text, fmt)
            
            await message.edit(f"✅ Файл {file_name} сохранен в БД!\n📏 Строк: {full_text.count(chr(10)) + 1}")
            
        except Exception as e:
            await message.edit(f"❌ Ошибка при сохранении: {e}")

    async def getcmd(self, message: Message):
        """получить файл из БД. Формат: .get [имя]"""
        args = utils.get_args_raw(message)
        
        if not args:
            await message.edit("❌ Укажи имя файла. Пример: .get myfile.txt")
            return
        
        file_data = self._get_from_db(args)
        
        if not file_data:
            await message.edit(f"❌ Файл {args} не найден в БД.")
            return
        
        # Создаем временный файл
        temp_path = file_data['name']
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(file_data['content'])
        
        caption = (
            f"📄 Файл: {file_data['name']}\n"
            f"📁 Формат: {file_data['file_type']}\n"
            f"📏 Строк: {file_data['content'].count(chr(10)) + 1}\n"
            f"💾 Размер: {file_data['size']} байт\n"
            f"📅 Создан: {file_data['created_at']}\n"
            f"🔄 Обновлен: {file_data['updated_at']}"
        )
        
        await message.client.send_file(
            message.chat_id,
            temp_path,
            caption=caption
        )
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        await message.delete()

    async def listcmd(self, message: Message):
        """показать список файлов в БД. Формат: .list [страница]"""
        args = utils.get_args_raw(message)
        page = int(args) - 1 if args and args.isdigit() else 0
        
        if page < 0:
            page = 0
        
        data = self._list_files_db(page)
        
        if not data['files']:
            await message.edit("📭 В БД нет файлов.")
            return
        
        text = f"📚 Файлы в БД (стр. {data['page'] + 1}/{data['pages']})\n"
        text += "─" * 30 + "\n"
        
        for file in data['files']:
            text += f"📄 {file[1]}\n"
            text += f"   📁 {file[2]} | 💾 {file[3]} байт\n"
            text += f"   📅 {file[4][:10]}\n\n"
        
        # Создаем кнопки навигации
        buttons = []
        nav_buttons = []
        
        if data['page'] > 0:
            nav_buttons.append({"text": "⬅️", "callback": self._list_page_cb, "args": (data['page'] - 1,)})
        
        nav_buttons.append({"text": f"{data['page'] + 1}/{data['pages']}", "callback": self._list_page_cb, "args": (data['page'],)})
        
        if data['page'] < data['pages'] - 1:
            nav_buttons.append({"text": "➡️", "callback": self._list_page_cb, "args": (data['page'] + 1,)})
        
        buttons.append(nav_buttons)
        
        await self.inline.form(text=text, message=message, reply_markup=buttons)

    async def _list_page_cb(self, call, page):
        """Обработчик пагинации списка"""
        await self.inline.form(
            text=call.text,
            message=call,
            reply_markup=[
                [
                    {"text": "⬅️", "callback": self._list_page_cb, "args": (page - 1,)},
                    {"text": "🔄", "callback": self._list_page_cb, "args": (page,)},
                    {"text": "➡️", "callback": self._list_page_cb, "args": (page + 1,)}
                ]
            ]
        )

    async def appendcmd(self, message: Message):
        """добавить текст к файлу в БД. Формат: .append [имя] (реплай на текст)"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        if not reply:
            await message.edit("❌ Ответь на сообщение с текстом.")
            return
        
        if not args:
            await message.edit("❌ Укажи имя файла. Пример: .append myfile.txt")
            return
        
        file_data = self._get_from_db(args)
        
        if not file_data:
            await message.edit(f"❌ Файл {args} не найден в БД.")
            return
        
        try:
            new_text = await self._collect_text_from_message(reply, message)
            
            if not new_text.strip():
                await message.edit("❌ Не удалось получить текст.")
                return
            
            # Добавляем новый текст
            updated_content = file_data['content'] + "\n" + new_text
            
            # Обновляем в БД
            self._save_to_db(file_data['name'], updated_content, file_data['file_type'])
            
            await message.edit(
                f"✅ Текст добавлен к файлу {file_data['name']}\n"
                f"📏 Новых строк: {new_text.count(chr(10)) + 1}\n"
                f"📏 Всего строк: {updated_content.count(chr(10)) + 1}"
            )
            
        except Exception as e:
            await message.edit(f"❌ Ошибка при добавлении: {e}")

    async def rmcmd(self, message: Message):
        """удалить файл из БД. Формат: .rm [имя]"""
        args = utils.get_args_raw(message)
        
        if not args:
            await message.edit("❌ Укажи имя файла. Пример: .rm myfile.txt")
            return
        
        if self._delete_from_db(args):
            await message.edit(f"✅ Файл {args} удален из БД.")
        else:
            await message.edit(f"❌ Файл {args} не найден в БД.")

    async def editcmd(self, message: Message):
        """редактировать файл в БД. Формат: .edit [имя] (реплай на новый текст)"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        if not reply:
            await message.edit("❌ Ответь на сообщение с новым текстом.")
            return
        
        if not args:
            await message.edit("❌ Укажи имя файла. Пример: .edit myfile.txt")
            return
        
        file_data = self._get_from_db(args)
        
        if not file_data:
            await message.edit(f"❌ Файл {args} не найден в БД.")
            return
        
        try:
            new_text = await self._collect_text_from_message(reply, message)
            
            if not new_text.strip():
                await message.edit("❌ Не удалось получить текст.")
                return
            
            # Обновляем в БД
            self._save_to_db(file_data['name'], new_text, file_data['file_type'])
            
            await message.edit(
                f"✅ Файл {file_data['name']} обновлен!\n"
                f"📏 Строк: {new_text.count(chr(10)) + 1}"
            )
            
        except Exception as e:
            await message.edit(f"❌ Ошибка при редактировании: {e}")

    # Остальные методы остаются без изменений, но я добавлю несколько улучшений

    async def _collect_text_from_message(self, reply, message):
        """Собирает весь текст из сообщения, включая все страницы инлайн кнопок"""
        self._collected_pages = []
        processed_messages = set()
        all_pages = {}
        
        if reply.text:
            self._collected_pages.append(reply.text)
            all_pages[0] = reply.text
        
        if reply.reply_markup and hasattr(reply.reply_markup, 'rows'):
            navigation_type = self._detect_navigation_type(reply.reply_markup)
            
            if navigation_type:
                await message.edit(f"📖 Перелистываю страницы (тип: {navigation_type})...")
                
                if navigation_type == "arrows":
                    await self._collect_arrows_pages(reply, all_pages, processed_messages)
                elif navigation_type == "numbers":
                    await self._collect_numbers_pages(reply, all_pages, processed_messages)
                elif navigation_type == "prev_next":
                    await self._collect_prev_next_pages(reply, all_pages, processed_messages)
        
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
        
        if len(all_pages) > 1:
            sorted_pages = [all_pages[key] for key in sorted(all_pages.keys())]
        else:
            sorted_pages = list(all_pages.values())
        
        return self._extract_text_from_pages(sorted_pages)

    def _generate_filename(self, text, fmt='txt'):
        """Генерирует имя файла на основе содержимого и формата"""
        if fmt == 'zip':
            return f"archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        
        first_line = text.split('\n')[0].strip() if text else ""
        
        # Определяем имя по содержимому
        if fmt == 'py' or (first_line.startswith('#!') and fmt == 'sh'):
            name = "script"
        elif fmt == 'json':
            name = "data"
        elif fmt == 'html' or first_line.lower().startswith('<!doctype'):
            name = "page"
        elif fmt == 'xml':
            name = "data"
        else:
            name = "output"
        
        return f"{name}.{fmt}"

    # Остальные вспомогательные методы из оригинального кода
    def _read_text_file(self, path):
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

    # Методы для навигации по страницам из оригинального кода
    def _detect_navigation_type(self, reply_markup):
        all_buttons = []
        for row in reply_markup.rows:
            for button in row.buttons:
                all_buttons.append(button.text)
        
        if "⬅️" in all_buttons and "➡️" in all_buttons:
            return "arrows"
        elif "◀" in all_buttons and "▶" in all_buttons:
            return "arrows"
        
        numbers = [b for b in all_buttons if b.isdigit()]
        if len(numbers) >= 3:
            return "numbers"
        
        nav_texts = ["назад", "вперед", "←", "→", "prev", "next", "<<"]
        if any(nav in ' '.join(all_buttons).lower() for nav in nav_texts):
            return "prev_next"
        
        return None

    async def _collect_arrows_pages(self, reply, all_pages, processed_messages):
        current_msg = reply
        processed_messages.add(current_msg.id)
        
        for _ in range(50):
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
        
        current_msg = reply
        
        for _ in range(50):
            prev_btn = self._find_button(current_msg, ["⬅️", "◀"])
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

    async def _collect_numbers_pages(self, reply, all_pages, processed_messages):
        current_msg = reply
        processed_messages.add(current_msg.id)
        
        number_buttons = self._get_number_buttons(reply)
        
        for page_num in sorted(number_buttons.keys()):
            if page_num == self._get_current_page_number(reply):
                continue
            
            btn = number_buttons[page_num]
            
            for _ in range(3):
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
        buttons = {}
        if message.reply_markup and hasattr(message.reply_markup, 'rows'):
            for row in message.reply_markup.rows:
                for button in row.buttons:
                    if button.text.isdigit():
                        buttons[int(button.text)] = button
        return buttons

    def _get_current_page_number(self, message):
        if message.text:
            match = re.search(r'(?:Страница|Page)\s*(\d+)/(\d+)', message.text)
            if match:
                return int(match.group(1))
            
            match = re.search(r'📒\s*Страница\s*(\d+)', message.text)
            if match:
                return int(match.group(1))
        return 0

    def _find_button(self, message, texts):
        if not message.reply_markup or not hasattr(message.reply_markup, 'rows'):
            return None
        
        for row in message.reply_markup.rows:
            for button in row.buttons:
                if button.text in texts:
                    return button
        return None

    def _find_button_by_text(self, message, text):
        if not message.reply_markup or not hasattr(message.reply_markup, 'rows'):
            return None
        
        for row in message.reply_markup.rows:
            for button in row.buttons:
                if button.text == text:
                    return button
        return None

    async def _collect_prev_next_pages(self, reply, all_pages, processed_messages):
        current_msg = reply
        processed_messages.add(current_msg.id)
        
        next_texts = ["Вперед", "вперед", "Next", "next", "▶", "→", ">>"]
        prev_texts = ["Назад", "назад", "Prev", "prev", "◀", "←", "<<"]
        
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
        
        current_msg = reply
        
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
        if not pages:
            return ""
        
        texts = []
        for page in pages:
            lines = page.split('\n')
            clean_lines = []
            skip_next = False
            
            for line in lines:
                if re.search(r'📒\s*Страница\s*\d+', line):
                    skip_next = True
                    continue
                if skip_next and not line.strip():
                    skip_next = False
                    continue
                
                line = line.replace('<pre>', '').replace('</pre>', '')
                line = line.replace('<code>', '').replace('</code>', '')
                
                clean_lines.append(line)
            
            clean_text = '\n'.join(clean_lines).strip()
            if clean_text:
                texts.append(clean_text)
        
        return self._merge_unique_texts(texts)

    def _merge_unique_texts(self, texts):
        if not texts:
            return ""
        
        if len(texts) == 1:
            return texts[0]
        
        unique_texts = []
        seen = set()
        for text in texts:
            if text not in seen:
                unique_texts.append(text)
                seen.add(text)
        
        if len(unique_texts) == 1:
            return unique_texts[0]
        
        merged = unique_texts[0]
        for next_text in unique_texts[1:]:
            overlap = self._find_overlap(merged, next_text)
            if overlap > 0:
                merged = merged + next_text[overlap:]
            else:
                merged += '\n' + next_text
        
        return merged

    def _find_overlap(self, text1, text2):
        max_overlap = min(len(text1), len(text2), 100)
        for i in range(max_overlap, 0, -1):
            if text1[-i:] == text2[:i]:
                return i
        return 0