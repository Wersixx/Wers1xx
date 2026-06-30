# meta developer: @Wers1xx
# meta pic: https://x0.at/3Wu7.jpg
# meta banner: https://x0.at/3Wu7.jpg
# scope: hikka_only
# scope: hikka_min 1.6.0

from .. import loader, utils
import logging
import random
from typing import Dict, List

logger = logging.getLogger(__name__)

@loader.tds
class FontMaster(loader.Module):
    """🎨 Мастер шрифтов - меняйте стиль текста одним кликом!"""
    
    strings = {
        "name": "FontMaster",
        "no_text": "❌ Укажите текст для преобразования",
        "no_font": "❌ Укажите название шрифта",
        "font_not_found": "❌ Шрифт не найден. Используйте .fonts для списка",
        "preview": "🎨 <b>Преобразованный текст:</b>\n<code>{}</code>\n\n📝 <b>Использован шрифт:</b> <code>{}</code>",
        "current_font": "✅ Текущий шрифт: <code>{}</code>",
        "font_changed": "✅ Шрифт изменен на: <code>{}</code>",
        "fonts_list": "📋 <b>Доступные шрифты:</b>\n{}",
        "random_applied": "🎲 Применен случайный шрифт: <code>{}</code>",
        "custom_font_created": "✅ Пользовательский шрифт сохранен как: <code>{}</code>",
        "custom_font_deleted": "✅ Пользовательский шрифт удален: <code>{}</code>",
        "custom_fonts_list": "📝 <b>Пользовательские шрифты:</b>\n{}",
        "error": "❌ Ошибка: {}"
    }
    
    strings_ru = {
        "name": "FontMaster",
        "no_text": "❌ Укажите текст для преобразования",
        "no_font": "❌ Укажите название шрифта",
        "font_not_found": "❌ Шрифт не найден. Используйте .fonts для списка",
        "preview": "🎨 <b>Преобразованный текст:</b>\n<code>{}</code>\n\n📝 <b>Использован шрифт:</b> <code>{}</code>",
        "current_font": "✅ Текущий шрифт: <code>{}</code>",
        "font_changed": "✅ Шрифт изменен на: <code>{}</code>",
        "fonts_list": "📋 <b>Доступные шрифты:</b>\n{}",
        "random_applied": "🎲 Применен случайный шрифт: <code>{}</code>",
        "custom_font_created": "✅ Пользовательский шрифт сохранен как: <code>{}</code>",
        "custom_font_deleted": "✅ Пользовательский шрифт удален: <code>{}</code>",
        "custom_fonts_list": "📝 <b>Пользовательские шрифты:</b>\n{}",
        "error": "❌ Ошибка: {}"
    }
    
    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "default_font",
                "normal",
                lambda: "Шрифт по умолчанию",
                validator=loader.validators.String()
            ),
            loader.ConfigValue(
                "auto_apply",
                False,
                lambda: "Автоприменение шрифта к сообщениям",
                validator=loader.validators.Boolean()
            ),
            loader.ConfigValue(
                "save_history",
                True,
                lambda: "Сохранять историю использованных шрифтов",
                validator=loader.validators.Boolean()
            )
        )
        
        # Инициализируем пустые словари шрифтов
        self.fonts = {}
        self.custom_fonts = {}
        self.current_font = "normal"
        self.font_history = []
        
        # Категории шрифтов
        self.font_categories = {
            "basic": ["normal", "bold", "italic", "bold_italic"],
            "mono": ["monospace", "script", "cursive"],
            "decorative": ["double", "circle", "square", "bubble"],
            "stylized": ["gothic", "smallcaps", "upsidedown"],
            "symbolic": ["symbol", "blackboard", "star", "heart"]
        }
    
    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        
        # Инициализируем шрифты после client_ready
        self._init_fonts()
        
        # Загружаем сохраненные пользовательские шрифты
        custom_fonts_data = self.db.get(__name__, "custom_fonts", {})
        self.custom_fonts = custom_fonts_data
        
        # Загружаем текущий шрифт
        self.current_font = self.db.get(__name__, "current_font", "normal")
        
        # Загружаем историю
        if self.config["save_history"]:
            self.font_history = self.db.get(__name__, "font_history", [])
    
    def _init_fonts(self):
        """Инициализация всех системных шрифтов"""
        # Базовые шрифты с корректными таблицами перевода
        self.fonts = {
            "normal": {},  # Пустой словарь для обычного текста
            
            # Bold (Жирный)
            "bold": self._create_safe_translation(
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
                "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
            ),
            
            # Italic (Курсив)
            "italic": self._create_safe_translation(
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
                "𝐴𝐵𝐶𝐷𝐸𝐹𝐺𝐻𝐼𝐽𝐾𝐿𝑀𝑁𝑂𝑃𝑄𝑅𝑆𝑇𝑈𝑉𝑊𝑋𝑌𝑍𝑎𝑏𝑐𝑑𝑒𝑓𝑔ℎ𝑖𝑗𝑘𝑙𝑚𝑛𝑜𝑝𝑞𝑟𝑠𝑡𝑢𝑣𝑤𝑥𝑦𝑧"
            ),
            
            # Bold Italic (Жирный курсив)
            "bold_italic": self._create_safe_translation(
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
                "𝑨𝑩𝑪𝑫𝑬𝑭𝑮𝑯𝑰𝑱𝑲𝑳𝑴𝑵𝑶𝑷𝑸𝑹𝑺𝑻𝑼𝑽𝑾𝑿𝒀𝒁𝒂𝒃𝒄𝒅𝒆𝒇𝒈𝒉𝒊𝒋𝒌𝒍𝒎𝒏𝒐𝒑𝒒𝒓𝒔𝒕𝒖𝒗𝒘𝒙𝒚𝒛"
            ),
            
            # Monospace (Моноширинный)
            "monospace": self._create_safe_translation(
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
                "𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿"
            ),
            
            # Script (Скриптовый)
            "script": self._create_safe_translation(
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
                "𝒜ℬ𝒞𝒟ℰℱ𝒢ℋℐ𝒥𝒦ℒℳ𝒩𝒪𝒫𝒬ℛ𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵𝒶𝒷𝒸𝒹ℯ𝒻ℊ𝒽𝒾𝒿𝓀𝓁𝓂𝓃ℴ𝓅𝓆𝓇𝓈𝓉𝓊𝓋𝓌𝓍𝓎𝓏"
            ),
            
            # Double-struck (Двойной)
            "double": self._create_safe_translation(
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
                "𝔸𝔹ℂ𝔻𝔼𝔽𝔾ℍ𝕀𝕁𝕂𝕃𝕄ℕ𝕆ℙℚℝ𝕊𝕋𝕌𝕍𝕎𝕏𝕐ℤ𝕒𝕓𝕔𝕕𝕖𝕗𝕘𝕙𝕚𝕛𝕜𝕝𝕞𝕟𝕠𝕡𝕢𝕣𝕤𝕥𝕦𝕧𝕨𝕩𝕪𝕫𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡"
            ),
            
            # Circle (Круговой)
            "circle": self._create_safe_translation(
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
                "ⒶⒷⒸⒹⒺⒻⒼⒽⒾⒿⓀⓁⓂⓃⓄⓅⓆⓇⓈⓉⓊⓋⓌⓍⓎⓏⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ⓪①②③④⑤⑥⑦⑧⑨"
            ),
            
            # Small Caps (Маленькие заглавные)
            "smallcaps": self._create_safe_translation(
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
                "ABCDEFGHIJKLMNOPQRSTUVWXYZᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ"
            ),
            
            # Upside Down (Перевернутый)
            "upsidedown": self._create_safe_translation(
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789?!., ",
                "∀BƆDƎℲפHIſK˥WNOԀQɹS┴∩ΛMXYZɐqɔpǝɟƃɥᴉɾʞlɯuodbɹsʇnʌʍxʎz0ƖᄅƐㄣϛ9ㄥ86¿¡˙' "
            ),
            
            # Square (Квадратный)
            "square": self._create_safe_translation(
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                "🄰🄱🄲🄳🄴🄵🄶🄷🄸🄹🄺🄻🄼🄽🄾🄿🅀🅁🅂🅃🅄🅅🅆🅇🅈🅉"
            ),
        }
        
        # Добавляем более простые шрифты для избежания ошибок
        # Bubble (Пузырьковый) - упрощенная версия
        self.fonts["bubble"] = self._create_safe_translation(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "🅐🅑🅒🅓🅔🅕🅖🅗🅘🅙🅚🅛🅜🅝🅞🅟🅠🅡🅢🅣🅤🅥🅦🅧🅨🅩"
        )
        
        # Symbol (Символьный)
        self.fonts["symbol"] = self._create_safe_translation(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "𝘼𝘽𝘾𝘿𝙀𝙁𝙂𝙃𝙄𝙅𝙆𝙇𝙈𝙉𝙊𝙋𝙌𝙍𝙎𝙏𝙐𝙑𝙒𝙓𝙔𝙕"
        )
        
        # Gothic (Готический)
        self.fonts["gothic"] = self._create_safe_translation(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "𝕬𝕭𝕮𝕯𝕰𝕱𝕲𝕳𝕴𝕵𝕶𝕷𝕸𝕹𝕺𝕻𝕼𝕽𝕾𝕿𝖀𝖁𝖂𝖃𝖄𝖅"
        )
        
        # Blackboard (Школьная доска)
        self.fonts["blackboard"] = self._create_safe_translation(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "𝔸𝔹ℂ𝔻𝔼𝔽𝔾ℍ𝕀𝕁𝕂𝕃𝕄ℕ𝕆ℙℚℝ𝕊𝕋𝕌𝕍𝕎𝕏𝕐ℤ"
        )
        
        # Star (Звездный) - упрощенный
        self.fonts["star"] = self._create_safe_translation(
            "ABCDEF",
            "★✩✪✫✬✭"
        )
        
        # Heart (Сердечный) - упрощенный
        self.fonts["heart"] = self._create_safe_translation(
            "ABCDEF",
            "💖💗💓💞💕💘"
        )
        
        # Cursive (Рукописный)
        self.fonts["cursive"] = self._create_safe_translation(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "𝓐𝓑𝓒𝓓𝓔𝓕𝓖𝓗𝓘𝓙𝓚𝓛𝓜𝓝𝓞𝓟𝓠𝓡𝓢𝓣𝓤𝓥𝓦𝓧𝓨𝓩"
        )
    
    def _create_safe_translation(self, from_chars: str, to_chars: str) -> dict:
        """Создает безопасную таблицу перевода"""
        if len(from_chars) != len(to_chars):
            # Если длины не совпадают, обрезаем до минимальной длины
            min_len = min(len(from_chars), len(to_chars))
            from_chars = from_chars[:min_len]
            to_chars = to_chars[:min_len]
            
        # Создаем словарь перевода
        translation_dict = {}
        for f, t in zip(from_chars, to_chars):
            translation_dict[ord(f)] = t
        
        return translation_dict
    
    def save_custom_fonts(self):
        """Сохраняем пользовательские шрифты"""
        self.db.set(__name__, "custom_fonts", self.custom_fonts)
    
    def save_current_font(self):
        """Сохраняем текущий шрифт"""
        self.db.set(__name__, "current_font", self.current_font)
    
    def save_font_history(self):
        """Сохраняем историю шрифтов"""
        if self.config["save_history"]:
            self.db.set(__name__, "font_history", self.font_history)
    
    def apply_font(self, text: str, font_name: str = None) -> str:
        """Применяет выбранный шрифт к тексту"""
        if font_name is None:
            font_name = self.current_font
        
        if font_name == "normal":
            return text
        
        # Проверяем пользовательские шрифты
        if font_name in self.custom_fonts:
            translation_dict = self.custom_fonts[font_name]
            return text.translate(translation_dict)
        
        # Проверяем системные шрифты
        if font_name in self.fonts:
            translation_dict = self.fonts[font_name]
            return text.translate(translation_dict)
        
        # Если шрифт не найден, возвращаем обычный текст
        return text
    
    @loader.command(
        ru_doc="[текст] [шрифт] - Применить шрифт к тексту",
        en_doc="[text] [font] - Apply font to text"
    )
    async def fontcmd(self, message):
        """Применить шрифт к тексту"""
        args = utils.get_args_raw(message)
        
        if not args:
            await utils.answer(message, self.strings("no_text"))
            return
        
        # Парсим аргументы: текст и шрифт
        parts = args.split(' ', 1)
        
        if len(parts) == 1:
            # Только текст, используем текущий шрифт
            text = parts[0]
            font_name = self.current_font
        else:
            # Проверяем, является ли первое слово названием шрифта
            possible_font = parts[0].lower()
            
            if (possible_font in self.fonts) or (possible_font in self.custom_fonts):
                font_name = possible_font
                text = parts[1]
            else:
                # Если не шрифт, используем текущий
                font_name = self.current_font
                text = args
        
        try:
            result = self.apply_font(text, font_name)
            
            await utils.answer(
                message,
                self.strings("preview").format(result, font_name)
            )
            
            # Добавляем в историю
            if self.config["save_history"] and font_name not in self.font_history:
                self.font_history.append(font_name)
                self.save_font_history()
                
        except Exception as e:
            await utils.answer(message, self.strings("error").format(str(e)))
    
    @loader.command(
        ru_doc="[шрифт] - Установить шрифт по умолчанию",
        en_doc="[font] - Set default font"
    )
    async def setfont(self, message):
        """Установить шрифт по умолчанию"""
        args = utils.get_args_raw(message)
        
        if not args:
            await utils.answer(
                message,
                self.strings("current_font").format(self.current_font)
            )
            return
        
        font_name = args.strip().lower()
        
        # Проверяем существование шрифта
        if font_name not in self.fonts and font_name not in self.custom_fonts and font_name != "normal":
            await utils.answer(message, self.strings("font_not_found"))
            return
        
        self.current_font = font_name
        self.save_current_font()
        
        await utils.answer(
            message,
            self.strings("font_changed").format(font_name)
        )
        
        # Показываем пример
        example = self.apply_font("Пример текста", font_name)
        await message.reply(f"📝 Пример: <code>{example}</code>")
    
    @loader.command(
        ru_doc="[категория] - Показать все доступные шрифты",
        en_doc="[category] - Show all available fonts"
    )
    async def fonts(self, message):
        """Показать все шрифты"""
        args = utils.get_args_raw(message)
        
        if args:
            # Показать шрифты определенной категории
            category = args.strip().lower()
            if category in self.font_categories:
                fonts_list = self.font_categories[category]
                response = f"📁 <b>Категория: {category}</b>\n\n"
                
                for font in fonts_list:
                    if font in self.fonts or font in self.custom_fonts:
                        example = self.apply_font("Abc", font)
                        response += f"• <code>{font:15}</code> → <code>{example}</code>\n"
                
                response += f"\n🎯 <b>Всего: {len(fonts_list)} шрифтов</b>"
                
                await utils.answer(message, response)
            else:
                await utils.answer(
                    message,
                    f"❌ Категория не найдена.\n"
                    f"Доступные категории: {', '.join(self.font_categories.keys())}"
                )
        else:
            # Показать все шрифты с категориями
            response = "🎨 <b>Доступные шрифты по категориям:</b>\n\n"
            
            for category, fonts in self.font_categories.items():
                available_fonts = [f for f in fonts if f in self.fonts or f in self.custom_fonts]
                if available_fonts:
                    response += f"📁 <b>{category.upper()}:</b>\n"
                    for font in available_fonts[:3]:  # Показываем по 3 примера
                        example = self.apply_font("Abc", font)
                        response += f"  • <code>{font:15}</code> → <code>{example}</code>\n"
                    if len(available_fonts) > 3:
                        response += f"  ... и еще {len(available_fonts) - 3} шрифтов\n"
                    response += "\n"
            
            # Пользовательские шрифты
            if self.custom_fonts:
                response += f"📝 <b>Пользовательские шрифты ({len(self.custom_fonts)}):</b>\n"
                for font_name in list(self.custom_fonts.keys())[:5]:
                    response += f"  • <code>{font_name}</code>\n"
                if len(self.custom_fonts) > 5:
                    response += f"  ... и еще {len(self.custom_fonts) - 5} шрифтов\n"
            
            response += (
                f"\n🎯 <b>Всего системных шрифтов:</b> {len(self.fonts)}\n"
                f"🔧 <b>Текущий шрифт:</b> <code>{self.current_font}</code>\n"
                f"📖 <b>Использование:</b> <code>.fontcmd [текст] [шрифт]</code>\n"
                f"📁 <b>Просмотр категории:</b> <code>.fonts [категория]</code>"
            )
            
            await utils.answer(message, response)
    
    @loader.command(
        ru_doc=" - Применить случайный шрифт",
        en_doc=" - Apply random font"
    )
    async def rfont(self, message):
        """Применить случайный шрифт"""
        args = utils.get_args_raw(message)
        
        if not args:
            await utils.answer(message, self.strings("no_text"))
            return
        
        # Выбираем случайный шрифт из всех доступных
        all_fonts = list(self.fonts.keys()) + list(self.custom_fonts.keys())
        if "normal" in all_fonts:
            all_fonts.remove("normal")
        
        if not all_fonts:
            await utils.answer(message, "❌ Нет доступных шрифтов")
            return
        
        random_font = random.choice(all_fonts)
        
        result = self.apply_font(args, random_font)
        
        response = (
            f"{self.strings('random_applied').format(random_font)}\n\n"
            f"📝 <b>Результат:</b>\n<code>{result}</code>"
        )
        
        await utils.answer(message, response)
        
        # Обновляем текущий шрифт
        self.current_font = random_font
        self.save_current_font()
    
    @loader.command(
        ru_doc="[имя] [отображение] - Создать пользовательский шрифт",
        en_doc="[name] [mapping] - Create custom font"
    )
    async def createfont(self, message):
        """Создать пользовательский шрифт"""
        args = utils.get_args_raw(message)
        
        if not args:
            help_text = (
                "🛠️ <b>Создание пользовательского шрифта</b>\n\n"
                "📖 <b>Формат:</b>\n"
                "<code>.createfont имя a:𝕒 b:𝕓 c:𝕔 ...</code>\n\n"
                "📝 <b>Пример:</b>\n"
                "<code>.createfont myspecial A:𝐀 B:𝐁 C:𝐂</code>\n\n"
                "🔤 <b>Поддерживаемые символы:</b>\n"
                "• Заглавные буквы: A-Z\n"
                "• Строчные буквы: a-z\n"
                "• Цифры: 0-9\n"
                "• Знаки препинания: !?., и другие\n\n"
                "💡 <b>Совет:</b> Копируйте специальные символы из примеров!"
            )
            await utils.answer(message, help_text)
            return
        
        parts = args.split(' ')
        if len(parts) < 2:
            await utils.answer(
                message,
                "❌ Укажите имя шрифта и хотя бы одно преобразование\n"
                "Пример: <code>.createfont myfont A:🅐 B:🅑</code>"
            )
            return
        
        font_name = parts[0].lower()
        mappings = parts[1:]
        
        # Проверяем, что имя не занято
        if font_name in self.fonts:
            await utils.answer(
                message,
                f"❌ Имя <code>{font_name}</code> уже используется системным шрифтом"
            )
            return
        
        if font_name in self.custom_fonts:
            await utils.answer(
                message,
                f"❌ Имя <code>{font_name}</code> уже используется пользовательским шрифтом"
            )
            return
        
        try:
            # Создаем таблицу переводов
            translation_dict = {}
            for mapping in mappings:
                if ':' not in mapping:
                    continue
                
                orig_char, new_char = mapping.split(':', 1)
                
                if len(orig_char) != 1:
                    await utils.answer(
                        message,
                        f"❌ Неверный формат: <code>{mapping}</code>\n"
              f"Исходный символ должен быть одним знаком"
                    )
                    return
                
                translation_dict[ord(orig_char)] = new_char
            
            if not translation_dict:
                await utils.answer(
                    message,
                    "❌ Не указаны корректные преобразования символов"
                )
                return
            
            # Сохраняем пользовательский шрифт
            self.custom_fonts[font_name] = translation_dict
            self.save_custom_fonts()
            
            # Показываем пример
            example_text = "".join([mapping.split(':')[0] for mapping in mappings[:5] if ':' in mapping])
            example_result = example_text.translate(translation_dict)
            
            response = (
                f"{self.strings('custom_font_created').format(font_name)}\n\n"
                f"📊 <b>Преобразований:</b> {len(translation_dict)}\n"
                f"📝 <b>Пример:</b> <code>{example_text}</code> → <code>{example_result}</code>\n\n"
                f"💡 <b>Использование:</b>\n"
                f"<code>.fontcmd текст {font_name}</code>\n"
                f"<code>.setfont {font_name}</code>"
            )
            
            await utils.answer(message, response)
            
        except Exception as e:
            await utils.answer(message, self.strings("error").format(str(e)))
    
    @loader.command(
        ru_doc=" - Показать примеры всех шрифтов",
        en_doc=" - Show examples of all fonts"
    )
    async def fshow(self, message):
        """Показать примеры всех шрифтов"""
        # Создаем таблицу с примерами
        example_text = "Abc"
        
        response = "🎨 <b>Примеры всех шрифтов:</b>\n\n"
        
        # Системные шрифты
        response += "🖥️ <b>СИСТЕМНЫЕ ШРИФТЫ:</b>\n"
        for font_name in sorted(self.fonts.keys()):
            if font_name == "normal":
                continue
            try:
                example = self.apply_font(example_text, font_name)
                response += f"• <code>{font_name:15}</code> → <code>{example}</code>\n"
            except:
                response += f"• <code>{font_name:15}</code> → ❌ Ошибка\n"
        
        # Пользовательские шрифты
        if self.custom_fonts:
            response += "\n📝 <b>ПОЛЬЗОВАТЕЛЬСКИЕ ШРИФТЫ:</b>\n"
            for font_name in sorted(self.custom_fonts.keys()):
                try:
                    example = self.apply_font(example_text, font_name)
                    response += f"• <code>{font_name:15}</code> → <code>{example}</code>\n"
                except:
                    response += f"• <code>{font_name:15}</code> → ❌ Ошибка\n"
        
        response += f"\n🎯 <b>Текущий шрифт:</b> <code>{self.current_font}</code>"
        
        # Разбиваем на несколько сообщений если слишком длинное
        if len(response) > 4000:
            chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for chunk in chunks:
                await message.reply(chunk)
                await asyncio.sleep(0.5)
        else:
            await utils.answer(message, response)
    
    @loader.command(
        ru_doc="[текст] - Быстрое применение текущего шрифта",
        en_doc="[text] - Quick apply current font"
    )
    async def f(self, message):
        """Быстрое применение текущего шрифта"""
        args = utils.get_args_raw(message)
        
        if not args:
            await utils.answer(message, self.strings("no_text"))
            return
        
        try:
            result = self.apply_font(args)
            await utils.answer(message, result)
        except Exception as e:
            await utils.answer(message, self.strings("error").format(str(e)))
    
    @loader.command(
        ru_doc=" - Помощь по модулю FontMaster",
        en_doc=" - FontMaster help"
    )
    async def fhelp(self, message):
        """Помощь по модулю"""
        help_text = (
            "🎨 <b>FontMaster - Мастер шрифтов</b>\n\n"
            
            "⚡ <b>Основные команды:</b>\n"
            "• <code>.fontcmd [текст] [шрифт]</code> - Применить шрифт\n"
            "• <code>.f [текст]</code> - Быстрое применение текущего шрифта\n"
            "• <code>.setfont [шрифт]</code> - Установить шрифт по умолчанию\n"
            "• <code>.fonts [категория]</code> - Список шрифтов\n\n"
            
            "🎲 <b>Случайные и специальные:</b>\n"
            "• <code>.rfont [текст]</code> - Случайный шрифт\n"
            "• <code>.fshow</code> - Примеры всех шрифтов\n\n"
            
            "🛠️ <b>Пользовательские шрифты:</b>\n"
            "• <code>.createfont [имя] [преобразования]</code> - Создать шрифт\n\n"
            
            "📁 <b>Категории шрифтов:</b>\n"
            "• basic - основные стили\n"
            "• mono - моноширинные\n"
            "• decorative - декоративные\n"
            "• stylized - стилизованные\n"
            "• symbolic - символьные\n\n"
            
            "⚙️ <b>Настройки в .config:</b>\n"
            "• default_font - шрифт по умолчанию\n"
            "• auto_apply - автоприменение\n"
            "• save_history - сохранение истории\n\n"
            
            "💡 <b>Примеры:</b>\n"
            "<code>.fontcmd Hello bold</code>\n"
            "<code>.setfont italic</code>\n"
            "<code>.fonts decorative</code>\n"
            "<code>.rfont Random text</code>"
        )
        
        await utils.answer(message, help_text)
    
    @loader.command(
        ru_doc="[текст] [шрифт] - Протестировать шрифт",
        en_doc="[text] [font] - Test font"
    )
    async def ftest(self, message):
        """Тестирование шрифта"""
        args = utils.get_args_raw(message)
        
        if not args:
            # Показать алфавит для текущего шрифта
            alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
            result = self.apply_font(alphabet)
            
            response = (
                f"🔤 <b>Алфавит в шрифте <code>{self.current_font}</code>:</b>\n"
                f"<code>{result}</code>\n\n"
                f"📊 <b>Длина:</b> {len(result)} символов"
            )
            
            await utils.answer(message, response)
            return
        
        parts = args.split(' ', 1)
        if len(parts) == 1:
            text = parts[0]
            font_name = self.current_font
        else:
            font_name = parts[0].lower()
            text = parts[1]
            
            if font_name not in self.fonts and font_name not in self.custom_fonts and font_name != "normal":
                await utils.answer(message, self.strings("font_not_found"))
                return
        
        result = self.apply_font(text, font_name)
        
        response = (
            f"🧪 <b>Тестирование шрифта <code>{font_name}</code>:</b>\n\n"
            f"📝 <b>Исходный текст:</b>\n<code>{text}</code>\n\n"
            f"🎨 <b>Результат:</b>\n<code>{result}</code>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"• Исходная длина: {len(text)}\n"
            f"• Результирующая длина: {len(result)}\n"
            f"• Символы изменены: {sum(1 for a, b in zip(text, result) if a != b)}"
        )
        
        await utils.answer(message, response)
