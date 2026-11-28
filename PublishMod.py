# meta developer: @Wers1xx
# meta pic: https://img.icons8.com/color/48/000000/python.png
# meta banner: https://i.imgur.com/your_banner.jpg
# scope: hikka_only
# scope: hikka_min 1.2.10

import logging
import inspect
import importlib.util
import sys
import os
import re
import ast
import base64
import aiohttp
from typing import Union, Optional
from hikkaritl.tl.types import Message, InputMediaWebPage, KeyboardButtonCopy

from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class PublishMod(loader.Module):
    """Публикация модулей в канал + авто-загрузка в GitHub"""
    strings = {"name": "PublishMod"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "github_raw_link",
                "https://raw.githubusercontent.com/Wersixx/Wers1xx/main/",
                "Ссылка на raw GitHub (с / в конце)",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "github_repo",
                "Wersixx/Wers1xx",
                "Репозиторий GitHub в формате owner/repo",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "github_token",
                "",
                "GitHub Personal Access Token (нужны права repo)",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "github_branch",
                "main",
                "Ветка репозитория",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "auto_upload_github",
                True,
                "Автоматически загружать модуль в GitHub перед публикацией",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "channel",
                "@your_channel",
                "Канал для публикации (@username или -100... id)",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "bot_token",
                "",
                "Токен бота (Bot API) для настоящих Rich Messages. Бот должен быть админом канала.",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "media_url",
                "https://x0.at/3Wu7.jpg",
                "Ссылка на медиа для публикации (fallback, если нет banner в модуле)",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "quote_media",
                True,
                "Использовать quote_media (только userbot-режим)",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "invert_media",
                True,
                "Использовать invert_media (только userbot-режим)",
                validator=loader.validators.Boolean(),
            ),
        )

    async def pmcmd(self, message: Message):
        """<reply to module file> [описание обновления] - Опубликовать модуль в канал (+ GitHub)"""
        reply = await message.get_reply_message()
        
        if not reply or not reply.file:
            await utils.answer(message, "<emoji document_id=5121063440311386962>👎</emoji> <b>Ответь на файл модуля!</b>")
            return
        
        if not reply.file.name.endswith(".py"):
            await utils.answer(message, "<emoji document_id=5121063440311386962>👎</emoji> <b>Это не Python файл!</b>")
            return
        
        # Текст после команды = описание обновления (если есть)
        update_description = utils.get_args_raw(message).strip() or "Обновление модуля"
        
        await utils.answer(message, "<emoji document_id=5253464392850221514>🔃</emoji> <b>Анализирую модуль...</b>")
        
        # Скачиваем файл
        file_path = await reply.download_media()
        
        try:
            # Анализируем модуль
            module_info = self._analyze_module(file_path)
            
            if not module_info:
                await utils.answer(message, "<emoji document_id=5121063440311386962>👎</emoji> <b>Не удалось проанализировать модуль!</b>")
                return
            
            # Используем название модуля из strings["name"] для ссылки и имени файла
            module_name = module_info.get("name")
            if not module_name or module_name == "Unknown":
                await utils.answer(message, "<emoji document_id=5121063440311386962>👎</emoji> <b>Не удалось определить имя модуля (strings['name'])!</b>")
                return
            
            # Очищаем имя файла от недопустимых символов
            safe_name = re.sub(r'[^\w\-.]', '', module_name)
            if not safe_name:
                safe_name = "module"
            
            target_filename = f"{safe_name}.py"
            
            # Переименовываем файл локально
            dir_name = os.path.dirname(file_path) or "."
            new_file_path = os.path.join(dir_name, target_filename)
            
            if file_path != new_file_path:
                os.rename(file_path, new_file_path)
                file_path = new_file_path
            
            # === Авто-загрузка в GitHub ===
            file_existed = False  # по умолчанию считаем новым
            
            if self.config["auto_upload_github"]:
                await utils.answer(message, f"<emoji document_id=5253464392850221514>🔃</emoji> <b>Загружаю <code>{target_filename}</code> в GitHub...</b>")
                
                upload_result = await self._upload_to_github(
                    file_path, 
                    target_filename, 
                    commit_message=update_description
                )
                
                if not upload_result["success"]:
                    await utils.answer(
                        message,
                        f"<emoji document_id=5121063440311386962>👎</emoji> <b>Ошибка загрузки в GitHub:</b>\n<code>{upload_result['error']}</code>"
                    )
                    return
                
                file_existed = upload_result.get("existed", False)
                
                status_text = "обновлён" if file_existed else "загружен"
                await utils.answer(
                    message,
                    f"<emoji document_id=5123163417326126159>✅</emoji> <b>Модуль успешно {status_text} в GitHub!</b>\n"
                    f"<code>{upload_result.get('html_url', '')}</code>"
                )
                
                # Обновляем / создаём full.txt (только если модуль новый)
                if not file_existed:
                    full_result = await self._update_full_txt(safe_name)
                    if full_result.get("success"):
                        action = full_result.get("action", "обновлён")
                        await utils.answer(
                            message,
                            f"<emoji document_id=5123163417326126159>✅</emoji> <b>full.txt {action}</b>"
                        )
                    else:
                        logger.warning(f"full.txt update failed: {full_result.get('error')}")
            
            # Формируем сообщение для публикации
            github_link = self.config["github_raw_link"].rstrip('/') + '/' + module_name + '.py'
            dlm_command = f"dlm {github_link}"
            
            # Баннер: сначала из meta модуля, иначе из конфига
            media_url = module_info.get("banner") or self.config["media_url"]
            
            bot_token = (self.config["bot_token"] or "").strip()
            
            if bot_token:
                # === Настоящий Rich Message через Bot API ===
                if file_existed:
                    rich_html = self._format_update_message_rich(
                        module_name, update_description, dlm_command, media_url
                    )
                else:
                    rich_html = self._format_message_rich(
                        module_info, module_name, dlm_command, media_url
                    )
                
                send_result = await self._send_rich_via_bot(
                    bot_token, self.config["channel"], rich_html
                )
                
                if not send_result.get("ok"):
                    await utils.answer(
                        message,
                        f"<emoji document_id=5121063440311386962>👎</emoji> <b>Ошибка Bot API:</b>\n"
                        f"<code>{send_result.get('description', send_result)}</code>"
                    )
                    return
            else:
                # === Fallback: userbot-режим (классический HTML + KeyboardButtonCopy) ===
                if file_existed:
                    text = self._format_update_message(module_name, update_description)
                else:
                    text = self._format_message(module_info, module_name)
                
                channel = self.config["channel"]
                try:
                    entity = await message.client.get_entity(channel)
                except Exception:
                    await utils.answer(
                        message,
                        f"<emoji document_id=5121063440311386962>👎</emoji> "
                        f"<b>Не удалось найти канал {channel}!</b>"
                    )
                    return
                
                banner = None
                if media_url and self.config["quote_media"]:
                    banner = InputMediaWebPage(media_url, optional=True)
                elif media_url:
                    banner = media_url
                
                install_button = KeyboardButtonCopy(
                    text="📥 Установить",
                    copy_text=dlm_command
                )
                buttons = [[install_button]]
                
                try:
                    await message.client.send_message(
                        entity,
                        text,
                        parse_mode="html",
                        file=banner,
                        invert_media=self.config["invert_media"],
                        buttons=buttons,
                        link_preview=False,
                    )
                except Exception as e:
                    logger.error(f"Failed to send with media/buttons: {e}")
                    try:
                        await message.client.send_message(
                            entity,
                            text,
                            parse_mode="html",
                            file=banner,
                            invert_media=self.config["invert_media"],
                            link_preview=False,
                        )
                    except Exception as e2:
                        logger.error(f"Failed to send with media: {e2}")
                        await message.client.send_message(
                            entity,
                            text,
                            parse_mode="html",
                            link_preview=False,
                        )
            
            if file_existed:
                await utils.answer(
                    message,
                    "<emoji document_id=5123163417326126159>✅</emoji> "
                    "<b>Обновление модуля успешно опубликовано в канал!</b>"
                )
            else:
                await utils.answer(
                    message,
                    "<emoji document_id=5123163417326126159>✅</emoji> "
                    "<b>Модуль успешно опубликован в канал!</b>"
                )
            
        except Exception as e:
            logger.error(f"Error publishing module: {e}")
            await utils.answer(message, f"<emoji document_id=5121063440311386962>👎</emoji> <b>Ошибка:</b> {e}")
        finally:
            # Удаляем временный файл
            if os.path.exists(file_path):
                os.remove(file_path)

    async def _upload_to_github(self, file_path: str, filename: str, commit_message: str = None) -> dict:
        """
        Загружает файл в GitHub через Contents API.
        Если файл уже существует — обновляет его.
        Возвращает existed=True, если файл уже был в репозитории.
        commit_message — текст коммита (используется при обновлении, если передан).
        """
        token = self.config["github_token"].strip()
        repo = self.config["github_repo"].strip()
        branch = self.config["github_branch"].strip() or "main"
        
        if not token:
            return {"success": False, "error": "Не указан github_token в конфиге!"}
        
        if not repo or "/" not in repo:
            return {"success": False, "error": "Неверный формат github_repo (нужно owner/repo)"}
        
        # Читаем содержимое файла
        try:
            with open(file_path, "rb") as f:
                content_bytes = f.read()
            content_b64 = base64.b64encode(content_bytes).decode("utf-8")
        except Exception as e:
            return {"success": False, "error": f"Не удалось прочитать файл: {e}"}
        
        api_base = f"https://api.github.com/repos/{repo}/contents/{filename}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Hikka-PublishMod",
        }
        
        async with aiohttp.ClientSession() as session:
            # Сначала проверяем, существует ли файл (чтобы получить sha для обновления)
            sha = None
            existed = False
            try:
                async with session.get(
                    api_base,
                    headers=headers,
                    params={"ref": branch},
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        sha = data.get("sha")
                        existed = True
                    elif resp.status == 404:
                        sha = None  # файла нет — будем создавать
                        existed = False
                    else:
                        text = await resp.text()
                        return {"success": False, "error": f"Ошибка проверки файла ({resp.status}): {text[:200]}"}
            except Exception as e:
                return {"success": False, "error": f"Ошибка сети при проверке: {e}"}
            
            # Формируем тело запроса
            # Если обновление и пользователь указал описание — используем его как commit message
            if existed and commit_message and commit_message.strip() and commit_message.strip() != "Обновление модуля":
                msg = commit_message.strip()
            elif existed:
                msg = f"Update module: {filename}"
            else:
                msg = f"Upload module: {filename}"
                if commit_message and commit_message.strip() and commit_message.strip() != "Обновление модуля":
                    msg = f"{msg}\n\n{commit_message.strip()}"
            
            payload = {
                "message": msg,
                "content": content_b64,
                "branch": branch,
            }
            if sha:
                payload["sha"] = sha  # обновление существующего файла
            
            try:
                async with session.put(
                    api_base,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    result = await resp.json()
                    
                    if resp.status in (200, 201):
                        html_url = result.get("content", {}).get("html_url") or result.get("commit", {}).get("html_url", "")
                        return {
                            "success": True,
                            "html_url": html_url,
                            "sha": result.get("content", {}).get("sha"),
                            "existed": existed,
                        }
                    else:
                        error_msg = result.get("message", str(result))
                        return {"success": False, "error": f"GitHub API ({resp.status}): {error_msg}"}
            except Exception as e:
                return {"success": False, "error": f"Ошибка загрузки: {e}"}

    async def _update_full_txt(self, module_name: str) -> dict:
        """
        Обновляет/создаёт full.txt в корне репозитория.
        - Если файла нет → создаёт и записывает все .py модули, которые сейчас есть в репо.
        - Если файл есть → добавляет название нового модуля (если его ещё нет).
        """
        token = self.config["github_token"].strip()
        repo = self.config["github_repo"].strip()
        branch = self.config["github_branch"].strip() or "main"
        
        if not token or not repo or "/" not in repo:
            return {"success": False, "error": "Не настроен github_token / github_repo"}
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Hikka-PublishMod",
        }
        
        full_txt_path = "full.txt"
        api_file = f"https://api.github.com/repos/{repo}/contents/{full_txt_path}"
        
        async with aiohttp.ClientSession() as session:
            # 1. Проверяем, существует ли full.txt
            sha = None
            current_content = ""
            file_exists = False
            
            try:
                async with session.get(
                    api_file,
                    headers=headers,
                    params={"ref": branch},
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        sha = data.get("sha")
                        file_exists = True
                        # Декодируем содержимое
                        content_b64 = data.get("content", "")
                        if content_b64:
                            current_content = base64.b64decode(content_b64).decode("utf-8")
                    elif resp.status == 404:
                        file_exists = False
                    else:
                        text = await resp.text()
                        return {"success": False, "error": f"Ошибка чтения full.txt ({resp.status}): {text[:200]}"}
            except Exception as e:
                return {"success": False, "error": f"Ошибка сети при чтении full.txt: {e}"}
            
            # 2. Формируем новое содержимое
            if not file_exists:
                # Создаём full.txt — собираем все .py файлы из корня репозитория
                modules = await self._list_repo_py_modules(session, headers, repo, branch)
                # Добавляем текущий модуль на всякий случай
                if module_name not in modules:
                    modules.append(module_name)
                modules = sorted(set(modules), key=str.lower)
                new_content = "\n".join(modules) + "\n"
                commit_msg = "Create full.txt with all modules"
                action = "создан"
            else:
                # Файл есть — добавляем новый модуль, если его ещё нет
                lines = [line.strip() for line in current_content.splitlines() if line.strip()]
                if module_name in lines:
                    # Уже есть — ничего не делаем
                    return {"success": True, "action": "уже содержит модуль (без изменений)"}
                
                lines.append(module_name)
                lines = sorted(set(lines), key=str.lower)
                new_content = "\n".join(lines) + "\n"
                commit_msg = f"Add {module_name} to full.txt"
                action = "обновлён"
            
            # 3. Записываем файл
            content_b64 = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")
            payload = {
                "message": commit_msg,
                "content": content_b64,
                "branch": branch,
            }
            if sha:
                payload["sha"] = sha
            
            try:
                async with session.put(
                    api_file,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status in (200, 201):
                        return {"success": True, "action": action}
                    else:
                        result = await resp.json()
                        error_msg = result.get("message", str(result))
                        return {"success": False, "error": f"GitHub API ({resp.status}): {error_msg}"}
            except Exception as e:
                return {"success": False, "error": f"Ошибка записи full.txt: {e}"}

    async def _list_repo_py_modules(self, session, headers: dict, repo: str, branch: str) -> list:
        """Получает список названий .py модулей (без расширения) из корня репозитория"""
        modules = []
        api_url = f"https://api.github.com/repos/{repo}/contents/"
        
        try:
            async with session.get(
                api_url,
                headers=headers,
                params={"ref": branch},
                timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                if resp.status != 200:
                    return modules
                
                items = await resp.json()
                if not isinstance(items, list):
                    return modules
                
                for item in items:
                    if item.get("type") == "file":
                        name = item.get("name", "")
                        if name.endswith(".py") and name != "full.txt":
                            # Убираем .py
                            modules.append(name[:-3])
        except Exception as e:
            logger.warning(f"Failed to list repo modules: {e}")
        
        return modules

    def _analyze_module(self, file_path: str) -> dict:
        """Анализирует Python файл модуля"""
        info = {
            "name": None,
            "description": None,
            "commands": [],
            "meta_developer": None,
            "banner": None,
        }
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Ищем meta developer (поддерживает несколько разработчиков)
            meta_dev_match = re.search(r'#\s*meta\s+developer:\s*(.+)', content, re.IGNORECASE)
            if meta_dev_match:
                raw_devs = meta_dev_match.group(1).strip()
                # Извлекаем все @username
                usernames = re.findall(r'@([\w]+)', raw_devs)
                if usernames:
                    info["meta_developer"] = ", ".join(f"@{u}" for u in usernames)
                else:
                    # Если @ не найдены — берём как есть
                    info["meta_developer"] = raw_devs
            
            # Ищем meta banner
            meta_banner_match = re.search(r'#\s*meta\s+banner:\s*(.+)', content, re.IGNORECASE)
            if meta_banner_match:
                banner_url = meta_banner_match.group(1).strip()
                if banner_url and banner_url.startswith(("http://", "https://")):
                    info["banner"] = banner_url
            
            # Ищем класс модуля
            class_match = re.search(r'class\s+(\w+)\(loader\.Module\):', content)
            module_class_name = class_match.group(1) if class_match else None
            
            # Извлекаем описание модуля из docstring класса через regex
            if module_class_name:
                class_doc_pattern = rf'class\s+{module_class_name}\(loader\.Module\):\s*\n\s*"""(.*?)"""'
                class_doc_match = re.search(class_doc_pattern, content, re.DOTALL)
                if class_doc_match:
                    doc_text = class_doc_match.group(1).strip()
                    # Берем первую строку как описание
                    first_line = doc_text.split('\n')[0].strip()
                    if first_line:
                        info["description"] = first_line
                else:
                    # Пробуем найти любой docstring класса
                    doc_match = re.search(r'class\s+\w+\(loader\.Module\):\s*\n\s*"""(.*?)"""', content, re.DOTALL)
                    if doc_match:
                        doc_text = doc_match.group(1).strip()
                        first_line = doc_text.split('\n')[0].strip()
                        if first_line:
                            info["description"] = first_line
            
            # Извлекаем команды через комбинированный подход
            info["commands"] = self._extract_all_commands(content)
            
            # Пытаемся загрузить модуль для получения названия
            if module_class_name:
                try:
                    spec = importlib.util.spec_from_file_location(
                        module_class_name, file_path
                    )
                    module = importlib.util.module_from_spec(spec)
                    
                    sys.modules[module_class_name] = module
                    spec.loader.exec_module(module)
                    
                    # Ищем класс модуля для получения имени
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if hasattr(obj, 'strings') and 'name' in obj.strings:
                            info["name"] = str(obj.strings["name"])
                            break
                    
                    # Удаляем загруженный модуль
                    if module_class_name in sys.modules:
                        del sys.modules[module_class_name]
                    
                except Exception as e:
                    logger.warning(f"Failed to dynamically load module: {e}")
            
            # Если имя не найдено, пытаемся найти через regex
            if not info["name"]:
                name_match = re.search(r'"name":\s*"([^"]+)"', content)
                if not name_match:
                    name_match = re.search(r"'name':\s*'([^']+)'", content)
                if name_match:
                    info["name"] = name_match.group(1)
                else:
                    info["name"] = module_class_name or "Unknown"
            
            # Удаляем дубликаты команд
            seen = set()
            unique_commands = []
            for cmd in info["commands"]:
                if cmd["name"] not in seen:
                    seen.add(cmd["name"])
                    unique_commands.append(cmd)
            info["commands"] = unique_commands
            
        except Exception as e:
            logger.error(f"Error analyzing module: {e}")
            return None
        
        return info

    def _extract_all_commands(self, content: str) -> list:
        """Извлекает все команды используя комбинацию методов"""
        commands = []
        seen = set()
        
        # Метод 1: AST парсинг (самый надежный)
        ast_commands = self._extract_commands_ast_enhanced(content)
        for cmd in ast_commands:
            if cmd["name"] not in seen:
                seen.add(cmd["name"])
                commands.append(cmd)
        
        # Метод 2: Улучшенный regex для @loader.command()
        regex_commands = self._extract_commands_regex_advanced(content)
        for cmd in regex_commands:
            if cmd["name"] not in seen:
                seen.add(cmd["name"])
                commands.append(cmd)
        
        # Метод 3: Старый стиль (методы с cmd)
        old_commands = self._extract_commands_old_style(content)
        for cmd in old_commands:
            if cmd["name"] not in seen:
                seen.add(cmd["name"])
                commands.append(cmd)
        
        return commands

    def _extract_commands_ast_enhanced(self, content: str) -> list:
        """Улучшенный AST парсинг команд"""
        commands = []
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                
                # Проверяем декораторы
                for decorator in node.decorator_list:
                    is_command = False
                    description = ""
                    
                    # Случай: @loader.command(...)
                    if isinstance(decorator, ast.Call):
                        # Проверяем что это вызов loader.command или command
                        if isinstance(decorator.func, ast.Attribute):
                            if (decorator.func.attr == 'command' and 
                                isinstance(decorator.func.value, ast.Name) and 
                                decorator.func.value.id == 'loader'):
                                is_command = True
                                description = self._extract_description_from_ast_call(decorator)
                        elif isinstance(decorator.func, ast.Name) and decorator.func.id == 'command':
                            is_command = True
                            description = self._extract_description_from_ast_call(decorator)
                    
                    # Случай: @loader.command (без скобок)
                    elif isinstance(decorator, ast.Attribute):
                        if (decorator.attr == 'command' and 
                            isinstance(decorator.value, ast.Name) and 
                            decorator.value.id == 'loader'):
                            is_command = True
                    
                    # Случай: @command (без скобок)
                    elif isinstance(decorator, ast.Name) and decorator.id == 'command':
                        is_command = True
                    
                    if is_command:
                        cmd_name = node.name
                        # Убираем суффиксы
                        if cmd_name.endswith('cmd'):
                            cmd_name = cmd_name[:-3]
                        elif cmd_name.endswith('_cmd'):
                            cmd_name = cmd_name[:-4]
                        cmd_name = cmd_name.replace('_', '')
                        
                        # Если описание не найдено, берем из докстринга
                        if not description:
                            if node.body and isinstance(node.body[0], ast.Expr):
                                if isinstance(node.body[0].value, ast.Constant):
                                    doc = node.body[0].value.value
                                    if isinstance(doc, str):
                                        doc = doc.strip()
                                        if doc:
                                            first_line = doc.split('\n')[0].strip()
                                            description = first_line[:100]
                        
                        if cmd_name and not any(c["name"] == cmd_name for c in commands):
                            commands.append({
                                "name": cmd_name,
                                "description": description
                            })
                        break
                        
        except Exception as e:
            logger.warning(f"AST enhanced parsing error: {e}")
        
        return commands

    def _extract_description_from_ast_call(self, call_node) -> str:
        """Извлекает описание из AST Call узла"""
        try:
            # Проверяем ключевые аргументы
            ru_doc = None
            en_doc = None
            ua_doc = None
            
            for keyword in call_node.keywords:
                if keyword.arg == 'ru_doc':
                    if isinstance(keyword.value, ast.Constant):
                        ru_doc = keyword.value.value
                elif keyword.arg == 'en_doc':
                    if isinstance(keyword.value, ast.Constant):
                        en_doc = keyword.value.value
                elif keyword.arg == 'ua_doc':
                    if isinstance(keyword.value, ast.Constant):
                        ua_doc = keyword.value.value
            
            # Приоритет: ru_doc > en_doc > ua_doc
            if ru_doc and isinstance(ru_doc, str):
                return ru_doc[:100]
            elif en_doc and isinstance(en_doc, str):
                return en_doc[:100]
            elif ua_doc and isinstance(ua_doc, str):
                return ua_doc[:100]
            
            # Проверяем позиционные аргументы
            for arg in call_node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    return arg.value[:100]
                    
        except Exception:
            pass
        
        return ""

    def _extract_commands_regex_advanced(self, content: str) -> list:
        """Улучшенный regex парсинг для @loader.command()"""
        commands = []
        seen = set()
        
        # Находим все @loader.command() декораторы с их аргументами
        pattern = r'@loader\.command\s*\(\s*(.*?)\s*\)\s*\n\s*async\s+def\s+(\w+)\s*\([^)]*\):'
        
        for match in re.finditer(pattern, content, re.DOTALL):
            args_str = match.group(1)
            cmd_name = match.group(2)
            
            # Убираем суффиксы
            if cmd_name.endswith('cmd'):
                cmd_name = cmd_name[:-3]
            elif cmd_name.endswith('_cmd'):
                cmd_name = cmd_name[:-4]
            cmd_name = cmd_name.replace('_', '')
            
            if cmd_name and cmd_name not in seen:
                seen.add(cmd_name)
                description = self._extract_description_from_args_string(args_str)
                commands.append({"name": cmd_name, "description": description})
        
        # Ищем @loader.command без аргументов
        pattern_no_args = r'@loader\.command\s*\n\s*async\s+def\s+(\w+)\s*\([^)]*\):'
        for match in re.finditer(pattern_no_args, content):
            cmd_name = match.group(1)
            if cmd_name.endswith('cmd'):
                cmd_name = cmd_name[:-3]
            elif cmd_name.endswith('_cmd'):
                cmd_name = cmd_name[:-4]
            cmd_name = cmd_name.replace('_', '')
            
            if cmd_name and cmd_name not in seen:
                seen.add(cmd_name)
                # Ищем докстринг
                desc = self._extract_docstring_for_function(content, match.group(1))
                commands.append({"name": cmd_name, "description": desc})
        
        return commands

    def _extract_description_from_args_string(self, args_str: str) -> str:
        """Извлекает описание из строки аргументов декоратора"""
        # Ищем ru_doc
        ru_match = re.search(r'ru_doc\s*=\s*["\']([^"\']*)["\']', args_str, re.DOTALL)
        if ru_match:
            desc = ru_match.group(1).strip()
            desc = re.sub(r'\s+', ' ', desc)
            return desc[:100]
        
        # Ищем en_doc
        en_match = re.search(r'en_doc\s*=\s*["\']([^"\']*)["\']', args_str, re.DOTALL)
        if en_match:
            desc = en_match.group(1).strip()
            desc = re.sub(r'\s+', ' ', desc)
            return desc[:100]
        
        # Ищем ua_doc
        ua_match = re.search(r'ua_doc\s*=\s*["\']([^"\']*)["\']', args_str, re.DOTALL)
        if ua_match:
            desc = ua_match.group(1).strip()
            desc = re.sub(r'\s+', ' ', desc)
            return desc[:100]
        
        # Ищем doc
        doc_match = re.search(r'doc\s*=\s*["\']([^"\']*)["\']', args_str, re.DOTALL)
        if doc_match:
            desc = doc_match.group(1).strip()
            desc = re.sub(r'\s+', ' ', desc)
            return desc[:100]
        
        return ""

    def _extract_docstring_for_function(self, content: str, func_name: str) -> str:
        """Извлекает докстринг для указанной функции"""
        pattern = rf'async\s+def\s+{func_name}\s*\([^)]*\):\s*\n\s*"""([^"]*)"""'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            doc = match.group(1).strip()
            first_line = doc.split('\n')[0].strip()
            return first_line[:100]
        return ""

    def _extract_commands_old_style(self, content: str) -> list:
        """Извлекает команды старого стиля (методы с cmd)"""
        commands = []
        seen = set()
        
        # Ищем методы с cmd в названии
        pattern = r'async\s+def\s+(\w+cmd)\s*\([^)]*\):'
        for match in re.finditer(pattern, content):
            cmd_func_name = match.group(1)
            cmd_name = cmd_func_name.replace('cmd', '').replace('_', '')
            
            if cmd_name and cmd_name not in seen:
                seen.add(cmd_name)
                # Ищем докстринг
                desc = self._extract_docstring_for_function(content, cmd_func_name)
                commands.append({"name": cmd_name, "description": desc})
        
        return commands

    def _format_update_message(self, module_name: str, update_description: str) -> str:
        """Fallback (userbot) — обновление модуля"""
        clean_name = module_name or "Без названия"
        
        if len(update_description) > 500:
            update_description = update_description[:497] + "..."
        
        text = (
            f'<emoji document_id=5253952855185829086>⚙️</emoji> <b>Обновление модуля</b> <code>{clean_name}</code>\n\n'
            f'<blockquote expandable>'
            f'<emoji document_id=5256230583717079814>📝</emoji> <b>Что изменилось:</b>\n'
            f'{update_description}'
            f'</blockquote>\n\n'
            f'<emoji document_id=5253577054137362120>🔗</emoji> <i>Нажми кнопку ниже, чтобы скопировать команду установки</i>'
        )
        return text

    def _format_message(self, module_info: dict, module_name: str) -> str:
        """Fallback (userbot) — новый модуль"""
        clean_name = module_name or "Без названия"
        
        module_desc = module_info.get("description") or "Без описания"
        if len(module_desc) > 200:
            module_desc = module_desc[:197] + "..."
        
        text = (
            f'<emoji document_id=5253521692008917018>🌙</emoji> <b>Модуль</b> <code>{clean_name}</code>\n'
            f'<emoji document_id=5256230583717079814>📝</emoji> {module_desc}\n'
        )
        
        if module_info["commands"]:
            max_commands = 5
            total_commands = len(module_info["commands"])
            sorted_commands = sorted(module_info["commands"], key=lambda x: x["name"])
            
            text += f'\n<blockquote expandable>'
            text += f'<emoji document_id=5197195523794157505>▫️</emoji> <b>Команды:</b>\n'
            for cmd in sorted_commands[:max_commands]:
                desc = cmd["description"] or "Без описания"
                text += f'• <code>.{cmd["name"]}</code> — {desc}\n'
            
            if total_commands > max_commands:
                text += f'\n<emoji document_id=6021435576513730578>📋</emoji> <i>И ещё {total_commands - max_commands} команд</i>'
            text += f'</blockquote>\n'
        else:
            text += (
                f'\n<blockquote>'
                f'<emoji document_id=6021435576513730578>📋</emoji> <b>Команды не обнаружены</b>\n'
                f'<i>Возможно, модуль использует другой способ регистрации</i>'
                f'</blockquote>\n'
            )
        
        if module_info.get("meta_developer"):
            devs = module_info["meta_developer"]
            label = "Разработчики" if "," in devs else "Разработчик"
            text += f'\n<emoji document_id=5253464392850221514>👨‍💻</emoji> <b>{label}:</b> {devs}\n'
        
        text += (
            f'\n<emoji document_id=5256094480498436162>📦</emoji> <i>Нажми кнопку ниже, чтобы скопировать команду установки</i>'
        )
        return text

    # ─────────────────────── True Rich Message (Bot API) ───────────────────────

    def _format_update_message_rich(
        self,
        module_name: str,
        update_description: str,
        dlm_command: str,
        media_url: str = None,
    ) -> str:
        """Настоящий Rich HTML для обновления модуля (Bot API sendRichMessage)"""
        clean_name = module_name or "Без названия"
        if len(update_description) > 800:
            update_description = update_description[:797] + "..."

        parts = []
        parts.append(f"<h2>⚙️ Обновление модуля <code>{self._escape(clean_name)}</code></h2>")

        if media_url:
            parts.append(f'<img src="{self._escape(media_url)}"/>')

        parts.append(
            "<blockquote expandable>"
            f"<b>📝 Что изменилось:</b><br/>"
            f"{self._escape(update_description)}"
            "</blockquote>"
        )

        parts.append(
            '<tg-button-row align="center">'
            f'<tg-button type="copy_text" text="{self._escape(dlm_command)}">'
            "📥 Установить"
            "</tg-button>"
            "</tg-button-row>"
        )

        return "\n".join(parts)

    def _format_message_rich(
        self,
        module_info: dict,
        module_name: str,
        dlm_command: str,
        media_url: str = None,
    ) -> str:
        """Настоящий Rich HTML для нового модуля (Bot API sendRichMessage)"""
        clean_name = module_name or "Без названия"
        module_desc = module_info.get("description") or "Без описания"
        if len(module_desc) > 300:
            module_desc = module_desc[:297] + "..."

        parts = []
        parts.append(f"<h2>🌙 Модуль <code>{self._escape(clean_name)}</code></h2>")
        parts.append(f"<p>📝 {self._escape(module_desc)}</p>")

        if media_url:
            parts.append(f'<img src="{self._escape(media_url)}"/>')

        # Команды — красивая таблица
        commands = module_info.get("commands") or []
        if commands:
            sorted_commands = sorted(commands, key=lambda x: x["name"])
            max_show = 8
            rows = [
                "<tr><th>Команда</th><th>Описание</th></tr>"
            ]
            for cmd in sorted_commands[:max_show]:
                name = self._escape(cmd["name"])
                desc = self._escape(cmd.get("description") or "—")
                rows.append(f"<tr><td><code>.{name}</code></td><td>{desc}</td></tr>")

            table = (
                '<table bordered striped compact>'
                "<caption>Команды модуля</caption>"
                + "".join(rows)
                + "</table>"
            )
            if len(sorted_commands) > max_show:
                table += f"<p><i>…и ещё {len(sorted_commands) - max_show} команд</i></p>"

            parts.append(table)
        else:
            parts.append(
                "<blockquote>"
                "📋 <b>Команды не обнаружены</b><br/>"
                "<i>Возможно, модуль использует другой способ регистрации</i>"
                "</blockquote>"
            )

        if module_info.get("meta_developer"):
            devs = module_info["meta_developer"]
            label = "Разработчики" if "," in devs else "Разработчик"
            parts.append(f"<p>👨‍💻 <b>{label}:</b> {self._escape(devs)}</p>")

        parts.append(
            '<tg-button-row align="center">'
            f'<tg-button type="copy_text" text="{self._escape(dlm_command)}">'
            "📥 Установить"
            "</tg-button>"
            "</tg-button-row>"
        )

        return "\n".join(parts)

    @staticmethod
    def _escape(text: str) -> str:
        """Минимальный HTML-escape для Rich Message"""
        if not text:
            return ""
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    async def _send_rich_via_bot(self, bot_token: str, channel: str, html: str) -> dict:
        """Отправляет настоящее Rich Message через Bot API sendRichMessage"""
        url = f"https://api.telegram.org/bot{bot_token}/sendRichMessage"
        payload = {
            "chat_id": channel,
            "rich_message": {
                "html": html,
            },
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    data = await resp.json()
                    return data
        except Exception as e:
            return {"ok": False, "description": str(e)}


    async def pmdelcmd(self, message: Message):
        """<название модуля> - Удалить модуль из GitHub репозитория и full.txt"""
        args = utils.get_args_raw(message).strip()
        
        if not args:
            await utils.answer(
                message,
                "<emoji document_id=5121063440311386962>👎</emoji> <b>Укажи название модуля!</b>\n"
                "<code>.pmdel ModuleName</code>"
            )
            return
        
        module_name = args
        # Убираем .py если пользователь указал
        if module_name.endswith(".py"):
            module_name = module_name[:-3]
        
        safe_name = re.sub(r'[^\w\-.]', '', module_name)
        if not safe_name:
            await utils.answer(message, "<emoji document_id=5121063440311386962>👎</emoji> <b>Некорректное имя модуля!</b>")
            return
        
        filename = f"{safe_name}.py"
        
        await utils.answer(
            message,
            f"<emoji document_id=5253464392850221514>🔃</emoji> <b>Удаляю <code>{filename}</code> из GitHub...</b>"
        )
        
        result = await self._delete_from_github(filename, safe_name)
        
        if result["success"]:
            await utils.answer(
                message,
                f"<emoji document_id=5123163417326126159>✅</emoji> <b>Модуль <code>{safe_name}</code> успешно удалён!</b>\n"
                f"• Файл: {result.get('file_action', 'удалён')}\n"
                f"• full.txt: {result.get('full_action', 'обновлён')}"
            )
        else:
            await utils.answer(
                message,
                f"<emoji document_id=5121063440311386962>👎</emoji> <b>Ошибка удаления:</b>\n<code>{result.get('error', 'Unknown')}</code>"
            )

    async def _delete_from_github(self, filename: str, module_name: str) -> dict:
        """Удаляет файл модуля из репозитория и убирает его из full.txt"""
        token = self.config["github_token"].strip()
        repo = self.config["github_repo"].strip()
        branch = self.config["github_branch"].strip() or "main"
        
        if not token:
            return {"success": False, "error": "Не указан github_token в конфиге!"}
        
        if not repo or "/" not in repo:
            return {"success": False, "error": "Неверный формат github_repo (нужно owner/repo)"}
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Hikka-PublishMod",
        }
        
        file_action = "не найден"
        full_action = "без изменений"
        
        async with aiohttp.ClientSession() as session:
            # 1. Удаляем .py файл
            api_file = f"https://api.github.com/repos/{repo}/contents/{filename}"
            
            try:
                async with session.get(
                    api_file,
                    headers=headers,
                    params={"ref": branch},
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        sha = data.get("sha")
                        
                        if sha:
                            payload = {
                                "message": f"Delete module: {filename}",
                                "sha": sha,
                                "branch": branch,
                            }
                            async with session.delete(
                                api_file,
                                headers=headers,
                                json=payload,
                                timeout=aiohttp.ClientTimeout(total=30)
                            ) as del_resp:
                                if del_resp.status in (200, 201):
                                    file_action = "удалён"
                                else:
                                    err = await del_resp.text()
                                    return {"success": False, "error": f"Ошибка удаления файла ({del_resp.status}): {err[:200]}"}
                    elif resp.status == 404:
                        file_action = "уже отсутствовал"
                    else:
                        text = await resp.text()
                        return {"success": False, "error": f"Ошибка проверки файла ({resp.status}): {text[:200]}"}
            except Exception as e:
                return {"success": False, "error": f"Ошибка сети при удалении файла: {e}"}
            
            # 2. Обновляем full.txt — убираем название модуля
            full_txt_path = "full.txt"
            api_full = f"https://api.github.com/repos/{repo}/contents/{full_txt_path}"
            
            try:
                async with session.get(
                    api_full,
                    headers=headers,
                    params={"ref": branch},
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        sha = data.get("sha")
                        content_b64 = data.get("content", "")
                        
                        if content_b64 and sha:
                            current_content = base64.b64decode(content_b64).decode("utf-8")
                            lines = [line.strip() for line in current_content.splitlines() if line.strip()]
                            
                            if module_name in lines:
                                lines = [l for l in lines if l != module_name]
                                lines = sorted(set(lines), key=str.lower)
                                new_content = "\n".join(lines) + "\n" if lines else ""
                                
                                content_b64_new = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")
                                payload = {
                                    "message": f"Remove {module_name} from full.txt",
                                    "content": content_b64_new,
                                    "sha": sha,
                                    "branch": branch,
                                }
                                
                                async with session.put(
                                    api_full,
                                    headers=headers,
                                    json=payload,
                                    timeout=aiohttp.ClientTimeout(total=30)
                                ) as put_resp:
                                    if put_resp.status in (200, 201):
                                        full_action = "обновлён (модуль удалён)"
                                    else:
                                        err = await put_resp.text()
                                        logger.warning(f"full.txt update failed: {err[:200]}")
                                        full_action = "ошибка обновления"
                            else:
                                full_action = "модуль не был в списке"
                    elif resp.status == 404:
                        full_action = "full.txt отсутствует"
            except Exception as e:
                logger.warning(f"Ошибка при обновлении full.txt: {e}")
                full_action = f"ошибка: {e}"
        
        return {
            "success": True,
            "file_action": file_action,
            "full_action": full_action,
        }

    async def client_ready(self, client, db):
        self.client = client
