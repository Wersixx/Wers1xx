# meta developer: @Wers1xx

import io
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from telethon.tl.types import DocumentAttributeSticker, InputStickerSetEmpty
from hikkatl.types import Message
from .. import loader, utils
import aiohttp
import re


@loader.tds
class MessageStickerMod(loader.Module):
    """Создаёт стикер ответом на сообщение пользователя"""

    strings = {
        "name": "MessageSticker",
        "no_reply": "❌ Нужно ответить на сообщение",
        "processing": "⏳ Создаю стикер-цитату...",
        "error": "❌ Ошибка:\n{}",
    }

    strings_ru = {
        "no_reply": "❌ Нужно ответить на сообщение",
        "processing": "⏳ Создаю стикер-цитату...",
        "error": "❌ Ошибка:\n{}",
        "_cmd_doc_quote": "Создаёт стикер с цитатой сообщения (аватарка, ник, текст)",
        "_cls_doc": "Создаёт стикер-скриншот сообщения",
    }

    @loader.command(
        ru_doc="Создаёт стикер с цитатой сообщения (аватарка, ник, текст)"
    )
    async def quote(self, message: Message):
        """Создаёт стикер-цитату сообщения"""
        reply = await message.get_reply_message()
        if not reply:
            await utils.answer(message, self.strings("no_reply"))
            return

        await utils.answer(message, self.strings("processing"))

        try:
            # Получаем данные для стикера
            sender = await reply.get_sender()
            
            # Имя отправителя
            name = self._get_sender_name(sender)
            
            # Текст сообщения
            text = reply.text or "📎 Медиафайл"
            
            # Аватарка
            avatar = await self._get_avatar(sender, message.client)
            
            # Создаём стикер
            sticker_data = await self._create_quote_sticker(
                avatar=avatar,
                name=name,
                text=text,
                is_reply=reply.is_reply,
                fwd_from=reply.fwd_from
            )
            
            # Отправляем
            uploaded = await message.client.upload_file(sticker_data, file_name="quote.webp")
            await message.client.send_file(
                message.chat_id,
                uploaded,
                force_document=False,
                attributes=[DocumentAttributeSticker(alt="Quote", stickerset=InputStickerSetEmpty())],
                reply_to=reply.id
            )
            
            await message.delete()
            
        except Exception as e:
            await utils.answer(message, self.strings("error").format(str(e)))

    def _get_sender_name(self, sender) -> str:
        """Получает отображаемое имя отправителя"""
        if not sender:
            return "Unknown"
        
        if hasattr(sender, 'first_name'):
            if sender.last_name:
                return f"{sender.first_name} {sender.last_name}".strip()
            return sender.first_name
        elif hasattr(sender, 'title'):
            return sender.title
        return "Unknown"

    async def _get_avatar(self, sender, client) -> Image.Image:
        """Загружает аватарку пользователя"""
        try:
            if not sender:
                return self._create_default_avatar()
            
            # Скачиваем фото профиля
            photos = await client.get_profile_photos(sender, limit=1)
            if photos:
                photo_data = io.BytesIO()
                await client.download_media(photos[0], photo_data)
                photo_data.seek(0)
                
                avatar = Image.open(photo_data).convert("RGBA")
                # Делаем круглой
                return self._make_circle_avatar(avatar, 80)
        except:
            pass
        
        return self._create_default_avatar()

    def _create_default_avatar(self) -> Image.Image:
        """Создаёт дефолтную аватарку"""
        avatar = Image.new("RGBA", (80, 80), (85, 111, 143, 255))
        draw = ImageDraw.Draw(avatar)
        
        # Рисуем силуэт
        draw.ellipse([20, 15, 60, 55], fill=(200, 210, 220, 255))
        draw.ellipse([28, 50, 52, 75], fill=(200, 210, 220, 255))
        
        return self._make_circle_avatar(avatar, 80)

    def _make_circle_avatar(self, image: Image.Image, size: int) -> Image.Image:
        """Делает аватарку круглой"""
        # Ресайзим
        image = image.resize((size, size), Image.Resampling.LANCZOS)
        
        # Создаём маску
        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse([0, 0, size, size], fill=255)
        
        # Применяем маску
        result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        result.paste(image, (0, 0), mask)
        
        return result

    async def _create_quote_sticker(
        self,
        avatar: Image.Image,
        name: str,
        text: str,
        is_reply: bool = False,
        fwd_from = None
    ) -> io.BytesIO:
        """Создаёт стикер с цитатой"""
        
        # Размеры
        width = 512
        min_height = 200
        padding = 24
        avatar_size = 80
        name_height = 40
        
        # Шрифты
        try:
            font_name = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
            font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except:
            font_name = ImageFont.load_default()
            font_text = ImageFont.load_default()
            font_small = font_name
        
        # Подготавливаем текст
        max_text_width = width - padding * 2 - avatar_size - 20
        
        # Оборачиваем текст
        wrapped_text = self._wrap_text(text, font_text, max_text_width)
        
        # Вычисляем высоту
        line_height = 36
        text_height = len(wrapped_text) * line_height
        height = max(min_height, padding * 2 + name_height + text_height + 60)
        
        # Добавляем высоту для reply/fwd
        if is_reply:
            height += 40
        if fwd_from:
            height += 40
        
        # Создаём изображение с градиентным фоном как в Telegram
        image = self._create_telegram_background(width, height)
        draw = ImageDraw.Draw(image)
        
        # Рисуем аватарку
        avatar_x = padding
        avatar_y = padding
        image.paste(avatar, (avatar_x, avatar_y), avatar)
        
        # Имя пользователя
        name_x = avatar_x + avatar_size + 16
        name_y = avatar_y + 10
        draw.text((name_x, name_y), name, font=font_name, fill=(58, 133, 198, 255))
        
        # Время (имитация)
        time_str = "12:34"  # Можно добавить реальное время из reply.date
        time_x = name_x + draw.textbbox((0, 0), name, font=font_name)[2] + 10
        time_y = name_y + 8
        draw.text((time_x, time_y), time_str, font=font_small, fill=(141, 157, 172, 255))
        
        # Reply индикатор
        current_y = name_y + name_height
        
        if is_reply:
            reply_y = current_y
            draw.rectangle([name_x, reply_y + 5, name_x + 4, reply_y + 35], fill=(58, 133, 198, 255))
            draw.text((name_x + 12, reply_y), "↩️ Reply", font=font_small, fill=(58, 133, 198, 255))
            current_y += 40
        
        if fwd_from:
            fwd_y = current_y
            draw.text((name_x, fwd_y), "↪️ Forwarded", font=font_small, fill=(141, 157, 172, 255))
            current_y += 40
        
        # Текст сообщения
        text_y = current_y + 10
        for line in wrapped_text:
            # Поддержка форматирования (жирный, курсив, моноширинный)
            self._draw_formatted_line(draw, line, name_x, text_y, font_text, font_name)
            text_y += line_height
        
        # Конвертируем в WebP
        output = io.BytesIO()
        image.save(output, format="WebP", lossless=True, quality=100)
        output.seek(0)
        
        return output

    def _create_telegram_background(self, width: int, height: int) -> Image.Image:
        """Создаёт фон как в Telegram (тёмная тема)"""
        image = Image.new("RGBA", (width, height), (33, 45, 61, 255))
        
        # Добавляем лёгкий градиент
        draw = ImageDraw.Draw(image)
        for i in range(height):
            alpha = int(10 * (i / height))
            draw.rectangle([0, i, width, i + 1], fill=(40, 53, 70, alpha))
        
        return image

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
        """Переносит текст по словам"""
        draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        lines = []
        
        for paragraph in text.split('\n'):
            if not paragraph.strip():
                lines.append("")
                continue
                
            words = paragraph.split()
            current_line = []
            
            for word in words:
                test_line = ' '.join(current_line + [word])
                bbox = draw.textbbox((0, 0), test_line, font=font)
                width = bbox[2] - bbox[0]
                
                if width <= max_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        # Слово слишком длинное - обрезаем
                        lines.append(word[:20] + "...")
                        current_line = []
            
            if current_line:
                lines.append(' '.join(current_line))
        
        return lines

    def _draw_formatted_line(self, draw: ImageDraw.Draw, line: str, x: int, y: int, 
                            font_regular, font_bold):
        """Рисует строку с поддержкой markdown-форматирования"""
        # Обработка **жирного**
        parts = re.split(r'(\*\*.*?\*\*)', line)
        
        current_x = x
        for part in parts:
            if part.startswith('**') and part.endswith('**'):
                # Жирный текст
                text = part[2:-2]
                draw.text((current_x, y), text, font=font_bold, fill=(255, 255, 255, 255))
                bbox = draw.textbbox((0, 0), text, font=font_bold)
                current_x += bbox[2] - bbox[0]
            else:
                # Обычный текст
                draw.text((current_x, y), part, font=font_regular, fill=(255, 255, 255, 230))
                bbox = draw.textbbox((0, 0), part, font=font_regular)
                current_x += bbox[2] - bbox[0]