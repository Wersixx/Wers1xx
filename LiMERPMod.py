# meta developer: @Wers1xx
# requires: toml aiohttp json re logging
import os
import pickle
import toml
import json
import re
import logging
import time
from functools import lru_cache
from hikka import loader, utils
from telethon.tl.types import Channel
from aiohttp import web

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# noinspection PyCallingNonCallable
@loader.tds
class RPMod(loader.Module):
    """A little upgraded mod of module of @Wers1xx"""

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "action_decoration",
                'normal | без стилей',
                lambda: self.strings("cfg_action_decoration"),
                validator=loader.validators.Choice(
                    [
                        "normal | без стилей",
                        "bold | полужирный",
                        "italic | курсив",
                        "underlined | подчёркнутый",
                        "strikethrough | зачёркнутый",
                        "spoiler | скрытый",
                    ]
                ),
            ),
            loader.ConfigValue(
                "replica_decoration",
                'normal | без стилей',
                lambda: self.strings("cfg_replica_decoration"),
                validator=loader.validators.Choice(
                    [
                        "normal | без стилей",
                        "bold | полужирный",
                        "italic | курсив",
                        "underlined | подчёркнутый",
                        "strikethrough | зачёркнутый",
                        "spoiler | скрытый",
                    ]
                ),
            ),
            loader.ConfigValue(
                "speech_bubble",
                '💬',
                lambda: self.strings("cfg_speech_bubble"),
                validator=loader.validators.String()
            ),
            loader.ConfigValue(
                "web_port",
                8080,
                lambda: "Port for web interface",
                validator=loader.validators.Integer(minimum=1024, maximum=65535)
            ),
            loader.ConfigValue(
                "enable_web",
                False,
                lambda: "Enable web interface",
                validator=loader.validators.Boolean()
            )
        )

        self.web_app = None
        self.web_runner = None

    strings = {
        'name': 'LiMERPMod',
        'separator…': '🤐 <b>Here\'s an emoji separator, but no emoji. eh</b>',
        'name?': '🧐 <b>Where\'s the name of the RP command?</b>',
        'action?': '🧐 <b>Where\'s the action of the RP command?</b>',
        'aarf': '🤢 <b>RP commands can\'t be named "all"</b>',
        'space': '🤐 <b>Multi-word commands are now supported!</b>',
        'added1': "🤩 <b>Command '<code>{}</code>' successfully added with emoji '{}'!</b>",
        'added2': "☺️ <b>Command '<code>{}</code>' successfully added!</b>",
        'weresall': '🤐 <b>You\'ve not entered separator or haven\'t entered anything at all.</b>',
        'cleared': '🍃 <b>RP commands successfully cleared!</b>',
        'arg?': '🧐 <b>Where\'s the argument?</b>',
        'deleted': '🗑️ <b>RP command <code>{}</code> successfully deleted!</b>',
        'notfound': '🧐 <b>Command <code>{}</code> not found!</b>',
        'on': '😀 <b>RP commands are now on!</b>',
        'off': '😴 <b>RP commands are now off!</b>',
        's-t-wrong': '😟 <b>Something went wrong!</b>',
        'nick-changed': '🏷️ <b>RP nickname of {} successfully changed to <code>{}</code>!</b>',
        'count': '📋 <b>You have <code>{}</code> commands</b>',
        'error-with-type': '❌ <b>Error: <code>{}</code></b>',
        'actualised': '👍🏻 <b>RP commands successfully actualised!</b>',
        'chat-excluded': '➖ <b>Chat {} successfully excluded!</b>',
        'chat-included': '➕ <b>Chat {} successfully included!</b>',
        'id-wrong': '🔢 <b>Wrong ID!</b>',
        'empty-exclude': '🪁 <b>Excluded chats list is empty!</b>',
        'excluded-chats': '📃 <b>Excluded chats:</b>',
        'on-in-chat': '📗💬 <b>RP commands are now on for members of this chat!</b>',
        'off-in-chat': '📕💬 <b>RP commands are now off for members of this chat!</b>',
        'who-have': '📄 <b>Who has RP commands access:</b>',
        'chats-s': '💬 <b>Chats:</b>',
        'users-s': '👤 <b>Users:</b>',
        'on-for-usr': '📗 <b>RP commands are now on for <code>{}</code>!</b>',
        'off-for-usr': '📕 <b>RP commands are now off for <code>{}</code>!</b>',
        'whatschanged': '''🍋 <b>LiMERPMod</b> (2.0) - Enhanced RP Module
What's new?
    • Multi-word commands support
    • Usage statistics
    • JSON import/export
    • Web interface
    • Permission system per command
    • Variables in actions: {user}, {target}, {random}
    • Enhanced help system
    • Improved error handling
    • Performance caching
Enjoy!''',
        'with-replica': 'Saying:',
        'arg-unknown': '🤌🏻 <b>Unknown argument!</b>',
        'num-unknown': 'Ⓜ️ <b>Unknown number!</b>',
        'done': '✅ <b>Done!</b>',
        'less-then-2': '▫️ <b>Less than 2 arguments!</b>',
        'toml-minparse-failure': '😦 <b>Failed to parse toml!</b>\nAre you sure it\'s a backup?',
        'toml-parse-failure': '💀 <b>Failed to parse toml!</b>\nThe backup is corrupted.',
        'cfg_action_decoration': 'Decoration for RP action',
        'cfg_replica_decoration': 'Decoration for RP replica',
        'cfg_speech_bubble': 'Speech bubble emoji for «with replica»',
        'stats_title': '📊 <b>RP Commands Statistics:</b>\n\n',
        'most_used': '🔥 <b>Most used commands:</b>\n{}\n',
        'never_used': '💤 <b>Never used commands:</b>\n{}\n',
        'per_user': '👥 <b>Commands per user:</b>\n{}\n',
        'permission_granted': '✅ <b>Permission granted for command "{}" to {}</b>',
        'permission_revoked': '❌ <b>Permission revoked for command "{}" from {}</b>',
        'permissions_list': '🔐 <b>Command permissions:</b>\n{}',
        'web_started': '🌐 <b>Web interface started on port {}</b>',
        'web_stopped': '🛑 <b>Web interface stopped</b>',
        'web_error': '❌ <b>Web interface error: {}</b>',
        'help_title': '📚 <b>LiMERPMod Commands List</b>\n\n',
        'help_command': '  • <code>{}</code> - {} {}\n',
        'json_exported': '📤 <b>Commands exported to JSON successfully!</b>',
        'json_imported': '📥 <b>Commands imported from JSON successfully!</b>',
        'stats_cleared': '🧹 <b>Statistics cleared!</b>',
        'variables_info': '''🎯 <b>Available variables:</b>
• <code>{user}</code> - Your nickname
• <code>{target}</code> - Target's nickname
• <code>{random}</code> - Random number 1-100
• <code>{time}</code> - Current time
• <code>{date}</code> - Current date''',
        'no_nicks': '📝 <b>No nicknames set!</b>',
    }

    strings_ru = {
        'name': 'LiMERPMod',
        'separator…': '🤐 <b>Вот разделитель, но нет эмодзи. епт</b>',
        'name?': '🧐 <b>Где имя РП-команды?</b>',
        'action?': '🧐 <b>Где действие РП-команды?</b>',
        'aarf': '🤢 <b>РП-команды не могут называться "all"</b>',
        'space': '🤐 <b>Многословные команды теперь поддерживаются!</b>',
        'added1': "🤩 <b>Команда '<code>{}</code>' успешно добавлена с эмодзи '{}'!</b>",
        'added2': "☺️ <b>Команда '<code>{}</code>' успешно добавлена!</b>",
        'weresall': '🤐 <b>Вы не ввели разделитель или ничего не ввели вообще.</b>',
        'cleared': '🍃 <b>РП-команды успешно очищены!</b>',
        'arg?': '🧐 <b>Где аргумент?</b>',
        'deleted': '🗑️ <b>РП-команда <code>{}</code> успешно удалена!</b>',
        'notfound': '🧐 <b>Команда <code>{}</code> не найдена!</b>',
        'on': '😀 <b>РП-команды теперь включены!</b>',
        'off': '😴 <b>РП-команды теперь выключены!</b>',
        's-t-wrong': '😟 <b>Что-то пошло не так!</b>',
        'nick-changed': '🏷️ <b>Ник {} успешно изменен на <code>{}</code>!</b>',
        'count': '📋 <b>У вас <code>{}</code> команд</b>',
        'error-with-type': '❌ <b>Ошибка: <code>{}</code></b>',
        'actualised': '👍🏻 <b>РП-команды успешно обновлены!</b>',
        'chat-excluded': '➖ <b>Чат {} успешно исключен!</b>',
        'chat-included': '➕ <b>Чат {} успешно включен!</b>',
        'id-wrong': '🔢 <b>Неверный ID!</b>',
        'empty-exclude': '🪁 <b>Список исключённых чатов пуст!</b>',
        'excluded-chats': '📃 <b>Исключённые чаты:</b>',
        'on-in-chat': '📗💬 <b>РП-команды теперь включены для участников этого чата!</b>',
        'off-in-chat': '📕💬 <b>РП-команды теперь выключены для участников этого чата!</b>',
        'who-have': '📄 <b>Кто имеет доступ к РП-командам:</b>',
        'chats-s': '💬 <b>Чаты:</b>',
        'users-s': '👤 <b>Пользователи:</b>',
        'on-for-usr': '📗 <b>РП-команды теперь включены для <code>{}</code>!</b>',
        'off-for-usr': '📕 <b>РП-команды теперь выключены для <code>{}</code>!</b>',
        'whatschanged': '''🍋 <b>LiMERPMod</b> (2.0) - Улучшенный RP модуль
Что нового?
    • Поддержка многословных команд
    • Статистика использования
    • Импорт/экспорт в JSON
    • Веб-интерфейс
    • Система прав для каждой команды
    • Переменные в действиях: {user}, {target}, {random}
    • Улучшенная система помощи
    • Улучшенная обработка ошибок
    • Кэширование для производительности
Наслаждайтесь!''',
        'with-replica': 'С репликой:',
        'arg-unknown': '🤌🏻 <b>Неизвестный аргумент!</b>',
        'num-unknown': 'Ⓜ️ <b>Неизвестная цифра!</b>',
        'done': '✅ <b>Готово!</b>',
        'less-then-2': '▫️ <b>Меньше 2 аргументов!</b>',
        'toml-minparse-failure': '😦 <b>Ошибка парсинга toml!</b>\nЭто точно бэкап?',
        'toml-parse-failure': '💀 <b>Ошибка парсинга toml!</b>\nБэкап повреждён.',
        'cfg_action_decoration': 'Декорация для действия РП-команды',
        'cfg_replica_decoration': 'Декорация для реплики РП-команды',
        'cfg_speech_bubble': 'Эмодзи речевого пузыря для «с репликой»',
        'stats_title': '📊 <b>Статистика РП команд:</b>\n\n',
        'most_used': '🔥 <b>Самые используемые команды:</b>\n{}\n',
        'never_used': '💤 <b>Неиспользуемые команды:</b>\n{}\n',
        'per_user': '👥 <b>Команды по пользователям:</b>\n{}\n',
        'permission_granted': '✅ <b>Разрешение выдано для команды "{}" для {}</b>',
        'permission_revoked': '❌ <b>Разрешение отозвано для команды "{}" у {}</b>',
        'permissions_list': '🔐 <b>Права на команды:</b>\n{}',
        'web_started': '🌐 <b>Веб-интерфейс запущен на порту {}</b>',
        'web_stopped': '🛑 <b>Веб-интерфейс остановлен</b>',
        'web_error': '❌ <b>Ошибка веб-интерфейса: {}</b>',
        'help_title': '📚 <b>Список команд LiMERPMod</b>\n\n',
        'help_command': '  • <code>{}</code> - {} {}\n',
        'json_exported': '📤 <b>Команды экспортированы в JSON успешно!</b>',
        'json_imported': '📥 <b>Команды импортированы из JSON успешно!</b>',
        'stats_cleared': '🧹 <b>Статистика очищена!</b>',
        'variables_info': '''🎯 <b>Доступные переменные:</b>
• <code>{user}</code> - Ваш ник
• <code>{target}</code> - Ник цели
• <code>{random}</code> - Случайное число 1-100
• <code>{time}</code> - Текущее время
• <code>{date}</code> - Текущая дата''',
        'no_nicks': '📝 <b>Никнеймы не установлены!</b>',
    }

    async def client_ready(self, client, db):
        self.db = db
        self.client = client

        # Initialize database
        if not self.db.get("RPMod", "exlist", False):
            self.db.set("RPMod", "exlist", [])

        if not self.db.get("RPMod", "status", False):
            self.db.set("RPMod", "status", 1)

        if not self.db.get("RPMod", "rpnicks", False):
            self.db.set("RPMod", "rpnicks", {})

        if not self.db.get("RPMod", "nrpcommands", False):
            self.db.set("RPMod", "nrpcommands", {})

        if not self.db.get("RPMod", "command_permissions", False):
            self.db.set("RPMod", "command_permissions", {})

        if not self.db.get("RPMod", "usage_stats", False):
            self.db.set("RPMod", "usage_stats", {"commands": {}, "users": {}})

        if not self.db.get("RPMod", "useraccept", False):
            self.db.set("RPMod", "useraccept", {"chats": [], "users": []})

        # Start web interface if enabled
        if self.config['enable_web']:
            await self.start_web_interface()

    async def on_unload(self):
        """Called when module is unloaded"""
        if self.web_runner:
            await self.web_runner.cleanup()
            logger.info("Web interface stopped")

    # ============== Web Interface ==============
    async def start_web_interface(self):
        """Start web interface for managing RP commands"""
        try:
            self.web_app = web.Application()
            self.web_app.router.add_get('/', self.web_index)
            self.web_app.router.add_get('/api/commands', self.web_get_commands)
            self.web_app.router.add_post('/api/command', self.web_add_command)
            self.web_app.router.add_delete('/api/command/{name}', self.web_delete_command)
            self.web_app.router.add_get('/api/stats', self.web_get_stats)

            self.web_runner = web.AppRunner(self.web_app)
            await self.web_runner.setup()
            site = web.TCPSite(self.web_runner, 'localhost', self.config['web_port'])
            await site.start()
            logger.info(f"Web interface started on port {self.config['web_port']}")
        except Exception as e:
            logger.error(f"Failed to start web interface: {e}")

    async def web_index(self, request):
        """Main web interface page"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>LiMERPMod Control Panel</title>
            <meta charset="utf-8">
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; background: #f0f0f0; }
                .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
                h1 { color: #333; }
                .command { border: 1px solid #ddd; padding: 10px; margin: 5px 0; border-radius: 5px; display: flex; align-items: center; }
                .emoji { font-size: 24px; margin-right: 10px; }
                .cmd-info { flex: 1; }
                .cmd-name { font-weight: bold; font-size: 16px; }
                .cmd-action { color: #666; }
                button { padding: 5px 15px; margin: 2px; cursor: pointer; background: #ff4444; color: white; border: none; border-radius: 3px; }
                button:hover { background: #cc0000; }
                .stats { margin: 20px 0; padding: 15px; background: #f9f9f9; border-radius: 5px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🍋 LiMERPMod Control Panel</h1>
                <div id="stats" class="stats">Loading stats...</div>
                <h2>Commands</h2>
                <div id="commands">Loading commands...</div>
            </div>
            <script>
                async function loadData() {
                    const commandsRes = await fetch('/api/commands');
                    const commands = await commandsRes.json();
                    const statsRes = await fetch('/api/stats');
                    const stats = await statsRes.json();
                    
                    let html = '';
                    for (const [name, data] of Object.entries(commands)) {
                        html += `<div class="command">`;
                        html += `<div class="emoji">${data.emoji || '📝'}</div>`;
                        html += `<div class="cmd-info">`;
                        html += `<div class="cmd-name">${name}</div>`;
                        html += `<div class="cmd-action">${data.action}</div>`;
                        html += `</div>`;
                        html += `<button onclick="deleteCommand('${name}')">Delete</button>`;
                        html += `</div>`;
                    }
                    document.getElementById('commands').innerHTML = html || '<p>No commands yet</p>';
                    
                    let statsHtml = '<h3>Statistics</h3>';
                    statsHtml += `<p>Total commands: ${Object.keys(commands).length}</p>`;
                    statsHtml += '<h4>Most Used</h4>';
                    for (const [cmd, count] of Object.entries(stats.most_used || {})) {
                        statsHtml += `<div>${cmd}: ${count} uses</div>`;
                    }
                    document.getElementById('stats').innerHTML = statsHtml;
                }
                
                async function deleteCommand(name) {
                    if (confirm('Delete command ' + name + '?')) {
                        await fetch('/api/command/' + encodeURIComponent(name), {method: 'DELETE'});
                        loadData();
                    }
                }
                
                loadData();
                setInterval(loadData, 5000);
            </script>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')

    async def web_get_commands(self, request):
        """API: Get all commands"""
        commands = self.db.get("RPMod", "nrpcommands", {})
        return web.json_response(commands)

    async def web_add_command(self, request):
        """API: Add new command"""
        data = await request.json()
        commands = self.db.get("RPMod", "nrpcommands", {})
        commands[data['name']] = [data['action'], data.get('emoji', '')]
        self.db.set("RPMod", "nrpcommands", commands)
        return web.json_response({"status": "ok"})

    async def web_delete_command(self, request):
        """API: Delete command"""
        name = request.match_info['name']
        commands = self.db.get("RPMod", "nrpcommands", {})
        if name in commands:
            del commands[name]
            self.db.set("RPMod", "nrpcommands", commands)
        return web.json_response({"status": "ok"})

    async def web_get_stats(self, request):
        """API: Get statistics"""
        stats = self.db.get("RPMod", "usage_stats", {})
        return web.json_response(stats)

    async def rpwebcmd(self, message):
        """Toggle web interface on/off"""
        args = utils.get_args_raw(message)
        
        if args == "on":
            if not self.web_runner:
                await self.start_web_interface()
                await utils.answer(message, self.strings("web_started").format(self.config['web_port']))
            else:
                await utils.answer(message, "Web interface already running!")
        elif args == "off":
            if self.web_runner:
                await self.web_runner.cleanup()
                self.web_runner = None
                await utils.answer(message, self.strings("web_stopped"))
            else:
                await utils.answer(message, "Web interface not running!")
        else:
            status = "running" if self.web_runner else "stopped"
            await utils.answer(message, f"Web interface is {status}")

    # ============== Enhanced Commands ==============
    async def dobrpcmd(self, message):
        """Create RP command with multi-word support
Usage: .dobrp command/action/emoji"""
        args = utils.get_args_raw(message)
        
        # Improved parsing with regex for multi-word commands
        pattern = r'^(.+?)\s*\/\s*(.+?)(?:\s*\/\s*(.+))?$'
        match = re.match(pattern, args)
        
        if not match:
            await utils.answer(message, self.strings("weresall"))
            return
            
        key_rp = match.group(1).strip()
        value_rp = match.group(2).strip()
        emoji_rp = match.group(3).strip() if match.group(3) else ''
        
        dict_rp = self.db.get("RPMod", "nrpcommands", {})
        
        if not key_rp:
            return await utils.answer(message, self.strings("name?"))
        elif not value_rp:
            return await utils.answer(message, self.strings("action?"))
        elif key_rp.lower() == "all":
            return await utils.answer(message, self.strings("aarf"))
            
        dict_rp[key_rp] = [value_rp, emoji_rp]
        self.db.set("RPMod", "nrpcommands", dict_rp)
        
        if emoji_rp:
            await utils.answer(message, self.strings("added1").format(key_rp, emoji_rp))
        else:
            await utils.answer(message, self.strings("added2").format(key_rp))

    async def rpvariablescmd(self, message):
        """Show available variables for RP actions"""
        await utils.answer(message, self.strings("variables_info"))

    def format_action(self, action, user, target):
        """Format action with variables"""
        import random
        from datetime import datetime
        
        replacements = {
            '{user}': user,
            '{target}': target,
            '{random}': str(random.randint(1, 100)),
            '{time}': datetime.now().strftime('%H:%M'),
            '{date}': datetime.now().strftime('%Y-%m-%d')
        }
        
        for var, value in replacements.items():
            action = action.replace(var, value)
            
        return action

    # ============== Statistics ==============
    async def rpstatscmd(self, message):
        """Show RP commands usage statistics"""
        stats = self.db.get("RPMod", "usage_stats", {"commands": {}, "users": {}})
        commands = self.db.get("RPMod", "nrpcommands", {})
        
        result = self.strings("stats_title")
        
        # Most used commands
        if stats["commands"]:
            sorted_cmds = sorted(stats["commands"].items(), key=lambda x: x[1], reverse=True)[:10]
            most_used = "\n".join([f"  • {cmd}: {count} uses" for cmd, count in sorted_cmds])
            result += self.strings("most_used").format(most_used)
        
        # Never used commands
        never_used = [cmd for cmd in commands.keys() if cmd not in stats["commands"]]
        if never_used:
            never_used_str = "\n".join([f"  • {cmd}" for cmd in never_used[:10]])
            if len(never_used) > 10:
                never_used_str += f"\n  ... and {len(never_used) - 10} more"
            result += self.strings("never_used").format(never_used_str)
        
        # Per user stats
        if stats["users"]:
            sorted_users = sorted(stats["users"].items(), key=lambda x: x[1], reverse=True)[:10]
            users_str = "\n".join([f"  • {uid}: {count} commands" for uid, count in sorted_users])
            result += self.strings("per_user").format(users_str)
        
        await utils.answer(message, result)

    async def rpclearstatscmd(self, message):
        """Clear usage statistics"""
        self.db.set("RPMod", "usage_stats", {"commands": {}, "users": {}})
        await utils.answer(message, self.strings("stats_cleared"))

    # ============== Permissions ==============
    async def rppermissionscmd(self, message):
        """Manage command permissions
Usage: .rppermissions grant <command> <user_id/chat_id>
       .rppermissions revoke <command> <user_id/chat_id>
       .rppermissions list [command]"""
        args = utils.get_args_raw(message).split()
        
        if not args:
            await utils.answer(message, self.strings("arg?"))
            return
            
        action = args[0].lower()
        permissions = self.db.get("RPMod", "command_permissions", {})
        
        if action == "grant" and len(args) >= 3:
            cmd = args[1]
            target = args[2]
            
            if cmd not in permissions:
                permissions[cmd] = {"allowed": [], "denied": []}
            
            if target not in permissions[cmd]["allowed"]:
                permissions[cmd]["allowed"].append(target)
                self.db.set("RPMod", "command_permissions", permissions)
                await utils.answer(message, self.strings("permission_granted").format(cmd, target))
            else:
                await utils.answer(message, f"Permission already granted!")
                
        elif action == "revoke" and len(args) >= 3:
            cmd = args[1]
            target = args[2]
            
            if cmd in permissions and target in permissions[cmd]["allowed"]:
                permissions[cmd]["allowed"].remove(target)
                self.db.set("RPMod", "command_permissions", permissions)
                await utils.answer(message, self.strings("permission_revoked").format(cmd, target))
            else:
                await utils.answer(message, "Permission not found!")
                
        elif action == "list":
            if len(args) > 1:
                cmd = args[1]
                if cmd in permissions:
                    perms_list = f"Permissions for '{cmd}':\n"
                    perms_list += f"Allowed: {', '.join(permissions[cmd]['allowed']) or 'none'}\n"
                    perms_list += f"Denied: {', '.join(permissions[cmd]['denied']) or 'none'}"
                    await utils.answer(message, perms_list)
                else:
                    await utils.answer(message, f"No permissions set for '{cmd}'")
            else:
                perms_list = ""
                for cmd, perms in permissions.items():
                    perms_list += f"\n{cmd}: {len(perms['allowed'])} allowed, {len(perms['denied'])} denied"
                await utils.answer(message, self.strings("permissions_list").format(perms_list or "No permissions set"))

    # ============== JSON Import/Export ==============
    async def rpjsonexportcmd(self, message):
        """Export commands to JSON format"""
        commands = self.db.get("RPMod", "nrpcommands", {})
        
        export_data = {
            "version": "2.0",
            "commands": commands,
            "exported_at": int(time.time())
        }
        
        file_name = "LiMERPMod_export.json"
        with open(file_name, "w", encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        await message.client.send_file(message.to_id, file_name)
        os.remove(file_name)
        await utils.answer(message, self.strings("json_exported"))

    async def rpjsonimportcmd(self, message):
        """Import commands from JSON format"""
        reply = await message.get_reply_message()
        
        if not reply or not reply.document:
            await utils.answer(message, "Reply to a JSON file!")
            return
            
        file_name = "LiMERPMod_import.json"
        await reply.download_media(file_name)
        
        try:
            with open(file_name, "r", encoding='utf-8') as f:
                data = json.load(f)
            
            if "commands" in data:
                self.db.set("RPMod", "nrpcommands", data["commands"])
                
            await utils.answer(message, self.strings("json_imported"))
        except Exception as e:
            await utils.answer(message, self.strings("error-with-type").format(str(e)))
        finally:
            os.remove(file_name)

    # ============== Help System ==============
    async def rphelpcmd(self, message):
        """Show all RP commands in a simple list"""
        commands = self.db.get("RPMod", "nrpcommands", {})
        
        if not commands:
            await utils.answer(message, self.strings("count").format(0))
            return
            
        help_text = self.strings("help_title")
        help_text += self.strings("count").format(len(commands)) + "\n\n"
        
        # Sort commands alphabetically
        for cmd in sorted(commands.keys()):
            cmd_data = commands[cmd]
            emoji = cmd_data[1] if len(cmd_data) > 1 else ""
            action = cmd_data[0]
            # Truncate long actions
            if len(action) > 60:
                action = action[:57] + "..."
            help_text += self.strings("help_command").format(cmd, action, emoji)
        
        await utils.answer(message, help_text)

    # ============== Cached Decorations ==============
    @lru_cache(maxsize=128)
    def get_decoration_tags(self, decoration_type):
        """Cached decoration tags"""
        if 'bold' in decoration_type:
            return ["<b>", "</b>"]
        elif 'italic' in decoration_type:
            return ["<i>", "</i>"]
        elif 'underline' in decoration_type:
            return ["<u>", "</u>"]
        elif 'strikethrough' in decoration_type:
            return ["<s>", "</s>"]
        elif 'spoiler' in decoration_type:
            return ["<spoiler>", "</spoiler>"]
        else:
            return ["", ""]

    # ============== Original Methods (Preserved) ==============
    async def addrpcmd(self, message):
        """dobrp alias."""
        await self.dobrpcmd(message)

    async def delrpcmd(self, message):
        """Use: .delrp (command) to delete command.
Use: .delrp all to delete all commands."""
        dict_rp = self.db.get("RPMod", "nrpcommands", {})

        args = utils.get_args_raw(message)
        key_rp = str(args)

        if key_rp == "all":
            dict_rp.clear()
            self.db.set("RPMod", "nrpcommands", dict_rp)
            await utils.answer(message, self.strings("cleared"))
            return

        elif not key_rp or not key_rp.strip():
            await utils.answer(message, self.strings("name?"))

        else:
            try:
                dict_rp.pop(key_rp)
                self.db.set("RPMod", "nrpcommands", dict_rp)
                await utils.answer(message, self.strings("deleted").format(key_rp))
            except KeyError:
                await utils.answer(message, self.strings("notfound"))

    async def rptogglecmd(self, message):
        """Use: .rptoggle to turn on/off RP mode."""
        status = self.db.get("RPMod", "status")

        if status == 1:
            self.db.set("RPMod", "status", 2)
            await utils.answer(message, self.strings("off"))
        else:
            self.db.set("RPMod", "status", 1)
            await utils.answer(message, self.strings("on"))

    async def rplistcmd(self, message):
        """Use: .rplist to see list of RP commands."""
        commands = self.db.get("RPMod", "nrpcommands", {})

        coms_amount = len(commands)
        
        if coms_amount == 0:
            await utils.answer(message, self.strings("count").format(0))
            return

        com_list = self.strings("count").format(coms_amount) + "\n\n"
        
        for cmd_name in sorted(commands.keys()):
            cmd_data = commands[cmd_name]
            if cmd_data[1]:
                com_list += f"• <b><code>{cmd_name}</code> - {cmd_data[0]} |</b> {cmd_data[1]}\n"
            else:
                com_list += f"• <b><code>{cmd_name}</code> - {cmd_data[0]}</b>\n"

        await utils.answer(message, com_list)

    async def rpnickcmd(self, message):
        """Use: .rpnick (nick) to change nick to user or yourself."""
        args = utils.get_args_raw(message).strip()
        reply = await message.get_reply_message()
        nicks = self.db.get("RPMod", "rpnicks")

        if not reply:
            user = await message.client.get_entity(message.sender_id)
        else:
            user = await message.client.get_entity(reply.sender_id)

        if not args:
            if str(user.id) in nicks:
                nicks.pop(str(user.id))

            self.db.set("RPMod", "rpnicks", nicks)
            return await utils.answer(
                message,
                self.strings("nick-changed").format(user.id, user.first_name),
            )

        nicks[str(user.id)] = args
        self.db.set("RPMod", "rpnicks", nicks)
        await utils.answer(
            message,
            self.strings("nick-changed").format(user.id, args),
        )

    async def rpnickscmd(self, message):
        """Use: .rpnicks to see list of nicknames."""
        nicks = self.db.get("RPMod", "rpnicks")

        if len(nicks) == 0:
            return await utils.answer(message, self.strings("no_nicks"))

        str_nicks = "• " + "\n •".join(
            " --- ".join([f"<code>{user_id}</code>", f"<b>{nick}</b>"])
            for user_id, nick in nicks.items()
        )
        await utils.answer(message, str_nicks)

    async def orpbackcmd(self, message):
        """Backup RP commands (old fashioned method)."""
        commands = self.db.get("RPMod", "nrpcommands")
        file_name = "LiMERPModBackUp (on compat).pickle"
        mes_id = message.to_id

        reply = await message.get_reply_message()

        if not reply:
            emojies = {}
            for key, value in commands.items():
                if commands[key][1] != "":
                    emojies[key] = commands[key][1]
                commands[key] = commands[key][0]

            try:
                await message.delete()
                dict_all = {"rp": commands, "emj": emojies}

                with open(file_name, "wb") as f:
                    pickle.dump(dict_all, f)

                await message.client.send_file(mes_id, file_name)
                os.remove(file_name)

            except Exception as e:
                await utils.answer(message, f"<b>Error:\n</b>{e}")

        else:
            try:
                if not reply.document:
                    await utils.answer(message, "It's not a file!")
                await reply.download_media(file_name)

                with open(file_name, "rb") as f:
                    data = pickle.load(f)

                rp = data["rp"]
                emj = data["emj"]

                for key in rp.keys():
                    if key in emj.keys():
                        rp[key] = [rp[key], emj[key]]

                self.db.set("RPMod", "nrpcommands", rp)

                await utils.answer(message, self.strings("actualised"))

            except Exception as e:
                await utils.answer(message, self.strings("error-with-type").format(e))

    async def rpbackcmd(self, message):
        """New way to backup RP commands."""
        commands = self.db.get("RPMod", "nrpcommands")
        file_name = "LiMERPModBackUp.toml"
        mes_id = message.to_id

        reply = await message.get_reply_message()

        if not reply:
            try:
                await message.delete()
                with open(file_name, "w") as f:
                    toml.dump(commands, f)

                await message.client.send_file(mes_id, file_name)
                os.remove(file_name)

            except Exception as e:
                await utils.answer(message, f"<b>Error:\n</b>{e}")

        else:
            try:
                if not reply.document:
                    await utils.answer(message, "It's not a file!")
                await reply.download_media(file_name)

                with open(file_name, "r") as f:
                    try:
                        data = toml.load(f)
                    except toml.TomlDecodeError:
                        return await utils.answer(message, self.strings("toml-parse-failure"))

                self.db.set("RPMod", "nrpcommands", data)

                await utils.answer(message, self.strings("actualised"))

            except Exception as e:
                await utils.answer(message, self.strings("error-with-type").format(e))

    async def rpblockcmd(self, message):
        """Use: .rpblock to add/remove exception."""
        args = utils.get_args_raw(message)
        ex = self.db.get("RPMod", "exlist")
        if not args:
            a = await message.client.get_entity(message.to_id)
            if a.id in ex:
                ex.remove(a.id)
                self.db.set("RPMod", "exlist", ex)
                try:
                    name = a.title
                except Exception:
                    name = a.first_name
                await utils.answer(
                    message,
                    self.strings("chat-included").format(name),
                )
            else:
                ex.append(a.id)
                self.db.set("RPMod", "exlist", ex)
                try:
                    name = a.title
                except Exception:
                    name = a.first_name
                await utils.answer(
                    message,
                    self.strings("chat-excluded").format(name),
                )

        elif args.isdigit():
            args = int(args)
            if args in ex:
                ex.remove(args)
                self.db.set("RPMod", "exlist", ex)
                a = await message.client.get_entity(args)
                try:
                    name = a.title
                except Exception:
                    name = a.first_name
                await utils.answer(
                    message,
                    self.strings("chat-included").format(name),
                )
            else:
                try:
                    a = await message.client.get_entity(args)
                except Exception:
                    return await utils.answer(message, self.strings("id-wrong"))

                ex.append(args)
                self.db.set("RPMod", "exlist", ex)
                try:
                    name = a.title
                except Exception:
                    name = a.first_name
                await utils.answer(message, self.strings("chat-excluded").format(name))

        elif args == "list":
            ex_len = len(ex)
            if ex_len == 0:
                await utils.answer(message, self.strings("empty-exclude"))
                return
            sms = self.strings("excluded-chats")
            for i in ex:
                try:
                    a = await message.client.get_entity(i)
                except Exception:
                    await utils.answer(message, self.strings("id-wrong"))
                    return
                try:
                    name = a.title
                except Exception:
                    name = a.first_name
                sms += f"\n• <b><u>{name}</u> --- </b><code>{i}</code>"
            await utils.answer(message, sms)
        else:
            await utils.answer(message, self.strings("s-t-wrong"))

    async def useracceptcmd(self, message):
        """Adding/removing users/chats allowed to use commands."""
        reply = await message.get_reply_message()
        args = utils.get_args_raw(message)
        user_a = self.db.get("RPMod", "useraccept")
        if not reply and not args and message.is_group:
            chat = message.chat
            if chat.id not in user_a["chats"]:
                user_a["chats"].append(chat.id)
                return await utils.answer(
                    message,
                    self.strings("on-in-chat").format(chat.title),
                )
            else:
                user_a["chats"].remove(chat.id)
                return await utils.answer(
                    message,
                    self.strings("off-in-chat").format(chat.title),
                )

        elif args.lower() == "-l" or args.lower() == "л":
            sms = self.strings("who-have")
            for k, v in user_a.items():
                if k == "chats":
                    sms += '\n' + self.strings("chats-s")
                else:
                    sms += '\n' + self.strings("users-s")
                for i in v:
                    try:
                        user = (
                            (await message.client.get_entity(int(i))).title
                            if k == "chats"
                            else (await message.client.get_entity(int(i))).first_name
                        )
                        sms += f"\n<b>• <u>{user}</u> ---</b> <code>{i}</code>"
                    except Exception:
                        sms += f"\n<b>•</b> <code>{i}</code>"
            await utils.answer(message, sms)

        elif args or reply:
            args = int(args) if args.isdigit() else reply.sender_id
            if args in user_a["users"]:
                user_a["users"].remove(args)
                self.db.set("RPMod", "useraccept", user_a)
                await utils.answer(
                    message,
                    self.strings("off-for-usr").format(args)
                )
            elif args in user_a["chats"]:
                user_a["chats"].remove(args)
                self.db.set("RPMod", "useraccept", user_a)
                await utils.answer(
                    message, self.strings("off-in-chat").format(args)
                )
            elif (
                    args not in user_a["chats"]
                    and type(await message.client.get_entity(args)) == Channel
            ):
                user_a["chats"].append(args)
                self.db.set("RPMod", "useraccept", user_a)
                await utils.answer(
                    message, self.strings("on-in-chat").format(args)
                )
            else:
                user_a["users"].append(args)
                self.db.set("RPMod", "useraccept", user_a)
                await utils.answer(
                    message,
                    self.strings("on-for-usr").format(args),
                )
        else:
            await utils.answer(message, self.strings("s-t-wrong"))

    async def mmminfocmd(self, message):
        """Read mod information and updates."""
        await utils.answer(message, self.strings("whatschanged"))

    # ============== Main Watcher ==============
    async def watcher(self, message):
        try:
            status = self.db.get("RPMod", "status")
            commands = self.db.get("RPMod", "nrpcommands")
            ex = self.db.get("RPMod", "exlist")
            nicks = self.db.get("RPMod", "rpnicks")
            users_accept = self.db.get("RPMod", "useraccept")
            permissions = self.db.get("RPMod", "command_permissions", {})
            stats = self.db.get("RPMod", "usage_stats", {"commands": {}, "users": {}})

            chat_rp = await message.client.get_entity(message.to_id)
            if status != 1 or chat_rp.id in ex:
                return

            me_id = (await message.client.get_me()).id

            if (
                    message.sender_id not in users_accept["users"]
                    and message.sender_id != me_id
                    and chat_rp.id not in users_accept["chats"]
            ):
                return

            me = await message.client.get_entity(message.sender_id)

            if str(me.id) in nicks.keys():
                nick = nicks[str(me.id)]
            else:
                nick = me.first_name

            # Find matching command
            matched_command = None
            for cmd in commands.keys():
                if message.text.lower().startswith(cmd.lower() + ' ') or message.text.lower() == cmd.lower():
                    matched_command = cmd
                    break

            if not matched_command:
                return

            # Check permissions
            if matched_command in permissions:
                if str(message.sender_id) in permissions[matched_command].get("denied", []):
                    return
                if permissions[matched_command].get("allowed") and str(message.sender_id) not in permissions[matched_command]["allowed"]:
                    return

            # Update statistics
            stats["commands"][matched_command] = stats["commands"].get(matched_command, 0) + 1
            stats["users"][str(message.sender_id)] = stats["users"].get(str(message.sender_id), 0) + 1
            self.db.set("RPMod", "usage_stats", stats)

            # Process command
            lines = message.text.splitlines()
            tags = lines[0].split(" ")

            if not tags[-1].startswith("@"):
                reply = await message.get_reply_message()
                if reply:
                    user = await message.client.get_entity(reply.sender_id)
                else:
                    user = me
            else:
                if not tags[-1][1:].isdigit():
                    user = await message.client.get_entity(tags[-1])
                else:
                    user = await message.client.get_entity(int(tags[-1][1:]))
                lines[0] = lines[0].rsplit(" ", 1)[0]

            detail = lines[0].split(" ", maxsplit=1)
            if len(detail) < 2:
                detail.append(" ")

            command = commands[matched_command]

            detail[1] = " " + detail[1]
            
            # Get target name
            target_name = nicks[str(user.id)] if str(user.id) in nicks else user.first_name

            # Get decorations using cache
            action_tags = self.get_decoration_tags(self.config['action_decoration'])
            replica_tags = self.get_decoration_tags(self.config['replica_decoration'])
            bubble = self.config['speech_bubble']

            # Format action with variables
            formatted_action = self.format_action(command[0], nick, target_name)

            rp_message_send = ""
            if command[1]:
                rp_message_send += command[1] + " | "

            rp_message_send += f"<a href=tg://user?id={me.id}>{nick}</a> {action_tags[0]}{formatted_action}{action_tags[1]} " \
                               f"<a href=tg://user?id={user.id}>{target_name}</a>{detail[1]}"

            if len(lines) >= 2:
                replica = '\n'.join(lines[1:])
                rp_message_send += f"\n{bubble} {self.strings('with-replica')} {replica_tags[0]}{replica}{replica_tags[1]}"

            return await utils.answer(message, rp_message_send)
            
        except Exception as e:
            logger.error(f"Watcher error: {e}", exc_info=True)
            pass

    @staticmethod
    def merge_dict(d1, d2):
        d_all = {**d1, **d2}
        for key in d_all:
            d_all[key] = {**d1[key], **d_all[key]}
        return d_all