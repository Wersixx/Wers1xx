# meta developer: @Wers1xx

import io
import math
import re
from datetime import timezone
from PIL import Image, ImageDraw, ImageFont
from telethon.tl.types import (
    DocumentAttributeSticker,
    InputStickerSetEmpty,
    PeerColor,
)
from hikkatl.types import Message
from .. import loader, utils


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
        "_cmd_doc_quote": "Создаёт стикер с цитатой сообщения (аватарка, ник, текст, premium, reply)",
        "_cls_doc": "Создаёт стикер-скриншот сообщения",
    }

    NAME_COLORS = {
        0: (255, 81, 106),
        1: (255, 168, 92),
        2: (218, 138, 247),
        3: (110, 214, 143),
        4: (93, 211, 211),
        5: (90, 166, 255),
        6: (255, 117, 168),
    }

    @loader.command(
        ru_doc="Создаёт стикер с цитатой сообщения (аватарка, ник, текст, premium, reply)"
    )
    async def quote(self, message: Message):
        """Создаёт стикер-цитату сообщения"""
        reply = await message.get_reply_message()
        if not reply:
            await utils.answer(message, self.strings("no_reply"))
            return

        await utils.answer(message, self.strings("processing"))

        try:
            sender = await reply.get_sender()
            name = self._get_sender_name(sender)

            text = self._get_message_text(reply)
            avatar = await self._get_avatar(sender, message.client)
            is_premium = bool(getattr(sender, "premium", False)) if sender else False
            name_color = self._get_name_color(sender)

            # Reply
            reply_info = None
            if reply.is_reply:
                try:
                    replied = await reply.get_reply_message()
                    if replied:
                        r_sender = await replied.get_sender()
                        r_name = self._get_sender_name(r_sender)
                        r_text = self._get_message_text(replied, short=True)
                        reply_info = {
                            "name": r_name,
                            "text": r_text,
                            "color": self._get_name_color(r_sender),
                        }
                except Exception:
                    pass

            # Forward
            fwd_from = None
            if reply.fwd_from:
                try:
                    if reply.fwd_from.from_name:
                        fwd_from = reply.fwd_from.from_name
                    elif getattr(reply, "forward", None) and reply.forward.sender:
                        fwd_from = self._get_sender_name(reply.forward.sender)
                    else:
                        fwd_from = "Unknown"
                except Exception:
                    fwd_from = "Unknown"

            time_str = self._format_time(reply.date)

            sticker_data = self._create_quote_sticker(
                avatar=avatar,
                name=name,
                text=text,
                name_color=name_color,
                is_premium=is_premium,
                reply_info=reply_info,
                fwd_from=fwd_from,
                time_str=time_str,
            )

            uploaded = await message.client.upload_file(sticker_data, file_name="quote.webp")
            await message.client.send_file(
                message.chat_id,
                uploaded,
                force_document=False,
                attributes=[DocumentAttributeSticker(alt="Quote", stickerset=InputStickerSetEmpty())],
                reply_to=reply.id,
            )
            await message.delete()

        except Exception as e:
            await utils.answer(message, self.strings("error").format(str(e)))

    def _get_message_text(self, msg, short: bool = False) -> str:
        """Возвращает текст или красивое описание медиа"""
        raw = msg.text or msg.message
        if raw:
            if short:
                return raw.replace("\n", " ").strip()[:55]
            return raw

        # Медиа
        if msg.photo:
            return "📷 Фото"
        if msg.gif or (msg.document and getattr(msg.document, "mime_type", "").startswith("image/gif")):
            return "🎞 GIF"
        if msg.video or msg.video_note:
            return "🎥 Видео"
        if msg.voice:
            return "🎤 Голосовое сообщение"
        if msg.audio:
            title = ""
            if msg.file and msg.file.name:
                title = f" — {msg.file.name}"
            return f"🎵 Аудио{title}"
        if msg.sticker:
            return "🌟 Стикер"
        if msg.document:
            name = ""
            if msg.file and msg.file.name:
                name = f" {msg.file.name}"
            return f"📄 Файл{name}"
        return "📎 Медиафайл"

    def _get_sender_name(self, sender) -> str:
        if not sender:
            return "Unknown"
        if hasattr(sender, "first_name"):
            if getattr(sender, "last_name", None):
                return f"{sender.first_name} {sender.last_name}".strip()
            return sender.first_name or "Unknown"
        if hasattr(sender, "title"):
            return sender.title or "Unknown"
        return "Unknown"

    def _get_name_color(self, sender) -> tuple:
        if not sender:
            return self.NAME_COLORS[5]
        color_obj = getattr(sender, "color", None)
        if color_obj and isinstance(color_obj, PeerColor):
            color_id = getattr(color_obj, "color", None)
            if color_id is not None:
                return self.NAME_COLORS.get(color_id % 7, self.NAME_COLORS[5])
        user_id = getattr(sender, "id", 0) or 0
        return self.NAME_COLORS[user_id % 7]

    def _format_time(self, dt) -> str:
        if not dt:
            return "12:34"
        try:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone().strftime("%H:%M")
        except Exception:
            return "12:34"

    async def _get_avatar(self, sender, client) -> Image.Image:
        try:
            if not sender:
                return self._create_default_avatar()
            photos = await client.get_profile_photos(sender, limit=1)
            if photos:
                buf = io.BytesIO()
                await client.download_media(photos[0], buf)
                buf.seek(0)
                avatar = Image.open(buf).convert("RGBA")
                return self._make_circle(avatar, 54)
        except Exception:
            pass
        return self._create_default_avatar()

    def _create_default_avatar(self) -> Image.Image:
        img = Image.new("RGBA", (54, 54), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([0, 0, 53, 53], fill=(90, 130, 180, 255))
        d.ellipse([13, 9, 41, 37], fill=(230, 235, 245, 255))
        d.ellipse([17, 35, 37, 52], fill=(230, 235, 245, 255))
        return img

    def _make_circle(self, image: Image.Image, size: int) -> Image.Image:
        image = image.resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out.paste(image, (0, 0), mask)
        return out

    def _draw_premium_badge(self, draw: ImageDraw.Draw, x: float, y: float, size: float = 14):
        """Рисует более похожую на Telegram Premium звезду"""
        cx = x + size / 2
        cy = y + size / 2
        # Внешний круг (лёгкий фон)
        draw.ellipse([x - 1, y - 1, x + size + 1, y + size + 1], fill=(255, 196, 0, 40))
        # Звезда
        outer = size / 2
        inner = size / 4.5
        pts = []
        for i in range(10):
            ang = math.radians(-90 + i * 36)
            r = outer if i % 2 == 0 else inner
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
        draw.polygon(pts, fill=(255, 196, 0, 255))

    def _create_quote_sticker(
        self,
        avatar: Image.Image,
        name: str,
        text: str,
        name_color: tuple,
        is_premium: bool = False,
        reply_info: dict = None,
        fwd_from: str = None,
        time_str: str = "12:34",
    ) -> io.BytesIO:

        S = 2
        av = 54 * S
        gap = 12 * S
        pad = 14 * S
        line_h = 29 * S

        try:
            f_name = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 23 * S)
            f_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 23 * S)
            f_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17 * S)
            f_reply = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17 * S)
        except Exception:
            f_name = f_text = f_small = f_reply = ImageFont.load_default()

        # Сначала меряем ширину имени + время + звезда
        dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        name_bb = dummy.textbbox((0, 0), name, font=f_name)
        name_w = name_bb[2] - name_bb[0]
        time_bb = dummy.textbbox((0, 0), time_str, font=f_small)
        time_w = time_bb[2] - time_bb[0]
        star_w = 20 * S if is_premium else 0

        header_w = name_w + star_w + 8 * S + time_w

        # Текст
        max_text_w = max(340 * S, header_w)
        lines = self._wrap(text, f_text, max_text_w)

        # Высота
        content_h = 28 * S
        if fwd_from:
            content_h += 20 * S
        if reply_info:
            content_h += 40 * S
        content_h += max(len(lines), 1) * line_h
        content_h += 10 * S

        bubble_h = content_h + pad * 2
        bubble_w = max_text_w + pad * 2

        total_w = av + gap + bubble_w
        total_h = max(av + 6 * S, bubble_h)

        img = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Аватарка слева
        av_img = avatar.resize((av, av), Image.Resampling.LANCZOS)
        img.paste(av_img, (0, 0), av_img)

        # Облако справа
        bx = av + gap
        by = 0
        draw.rounded_rectangle(
            [bx, by, bx + bubble_w - 1, by + bubble_h - 1],
            radius=16 * S,
            fill=(42, 54, 70, 255),
        )

        nx = bx + pad
        ny = by + pad

        # Имя
        draw.text((nx, ny), name, font=f_name, fill=(*name_color, 255))
        cur_x = nx + name_w

        # Premium
        if is_premium:
            self._draw_premium_badge(draw, cur_x + 4 * S, ny + 2 * S, 14 * S)
            cur_x += 20 * S

        # Время
        draw.text(
            (cur_x + 6 * S, ny + 3 * S),
            time_str,
            font=f_small,
            fill=(150, 165, 180, 255),
        )

        cy = ny + 26 * S

        if fwd_from:
            draw.text((nx, cy), f"↪️ {fwd_from}", font=f_small, fill=(150, 165, 180, 255))
            cy += 20 * S

        if reply_info:
            col = (*reply_info["color"], 255)
            draw.rounded_rectangle(
                [nx, cy + 1 * S, nx + 3 * S, cy + 32 * S],
                radius=2 * S,
                fill=col,
            )
            draw.text((nx + 8 * S, cy), reply_info["name"], font=f_reply, fill=col)
            prev = reply_info["text"]
            if len(prev) > 38:
                prev = prev[:35] + "..."
            draw.text((nx + 8 * S, cy + 15 * S), prev, font=f_reply, fill=(160, 175, 190, 255))
            cy += 40 * S

        for line in lines:
            self._draw_line(draw, line, nx, cy, f_text, f_name)
            cy += line_h

        final = img.resize((total_w // S, total_h // S), Image.Resampling.LANCZOS)

        out = io.BytesIO()
        final.save(out, format="WebP", lossless=True)
        out.seek(0)
        return out

    def _wrap(self, text: str, font, max_width: int) -> list:
        d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        result = []
        for para in text.split("\n"):
            if not para.strip():
                result.append("")
                continue
            words = para.split()
            cur = []
            for w in words:
                test = " ".join(cur + [w])
                bb = d.textbbox((0, 0), test, font=font)
                if bb[2] - bb[0] <= max_width:
                    cur.append(w)
                else:
                    if cur:
                        result.append(" ".join(cur))
                    cur = [w]
            if cur:
                result.append(" ".join(cur))
        return result or [""]

    def _draw_line(self, draw, line, x, y, f_reg, f_bold):
        parts = re.split(r"(\*\*.*?\*\*)", line)
        cx = x
        for p in parts:
            if p.startswith("**") and p.endswith("**") and len(p) > 4:
                t = p[2:-2]
                draw.text((cx, y), t, font=f_bold, fill=(255, 255, 255, 255))
                bb = draw.textbbox((0, 0), t, font=f_bold)
                cx += bb[2] - bb[0]
            else:
                draw.text((cx, y), p, font=f_reg, fill=(255, 255, 255, 255))
                bb = draw.textbbox((0, 0), p, font=f_reg)
                cx += bb[2] - bb[0]
