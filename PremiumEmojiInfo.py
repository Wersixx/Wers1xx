# meta developer: @Wers1xx
# scope: hikka_only
# scope: hikka_min 1.2.10

from telethon.tl.types import Message
from telethon.tl.custom import Message as CustomMessage
from telethon.tl.types import (
    MessageEntityBold,
    MessageEntityItalic,
    MessageEntityCode,
    MessageEntityPre,
    MessageEntityUnderline,
    MessageEntityStrike,
    MessageEntityBlockquote,
    MessageEntitySpoiler,
    MessageEntityTextUrl,
    MessageEntityUrl,
    MessageEntityEmail,
    MessageEntityMentionName,
    MessageEntityCustomEmoji,
)
from .. import loader, utils
import html
import struct
import re


def _add_surrogate(text: str) -> str:
    return "".join(
        "".join(chr(y) for y in struct.unpack("<HH", x.encode("utf-16le")))
        if 0x10000 <= ord(x) <= 0x10FFFF
        else x
        for x in text
    )


def _del_surrogate(text: str) -> str:
    return text.encode("utf-16", "surrogatepass").decode("utf-16")


def _within_surrogate(text: str, index: int) -> bool:
    length = len(text)
    return (
        0 < index < length
        and "\ud800" <= text[index - 1] <= "\udbff"
        and "\udc00" <= text[index] <= "\udfff"
    )


@loader.tds
class PremiumEmojiInfoMod(loader.Module):
    """Превращает любое сообщение (текст + форматирование + премиум эмодзи) в HTML-теги.
    
    Команда .em — реплаем на сообщение.
    
    В Eval:
    • .e em(r)  — получить HTML-исходник из реплая
    • .e em()   — из реплая или текущего сообщения
    """

    strings = {
        "name": "PremiumEmojiInfo",
        "no_reply": "<b>❌ Нужен реплай на сообщение</b>",
        "no_content": "<b>❌ В сообщении нет текста/эмодзи</b>",
    }

    strings_ru = {
        "no_reply": "<b>❌ Нужен реплай на сообщение</b>",
        "no_content": "<b>❌ В сообщении нет текста/эмодзи</b>",
    }

    async def client_ready(self, client, db):
        """Добавляем функцию em() в контекст Eval"""
        evaluator = self.lookup("Evaluator")
        if not evaluator:
            return

        original_getattrs = evaluator.getattrs

        async def patched_getattrs(message: Message) -> dict:
            attrs = await original_getattrs(message)
            attrs["em"] = lambda msg=None: self.to_html(
                msg or attrs.get("r") or attrs.get("message")
            )
            return attrs

        evaluator.getattrs = patched_getattrs

    def to_html(self, msg) -> str:
        """Конвертирует сообщение в HTML с <emoji document_id=...>"""
        if not msg:
            return "❌ Нет сообщения"

        text = getattr(msg, "raw_text", None) or getattr(msg, "message", None) or ""
        entities = list(getattr(msg, "entities", None) or [])

        # Медиа-стикер / премиум эмодзи без текста
        if not text and not entities and getattr(msg, "document", None):
            doc = msg.document
            if hasattr(doc, "attributes"):
                for attr in doc.attributes:
                    if hasattr(attr, "document_id") and attr.document_id:
                        return f'<emoji document_id={attr.document_id}>❓</emoji>'

        if not text and not entities:
            return "❌ В сообщении нет текста/эмодзи"

        if not entities:
            return html.escape(text)

        # Всегда используем свой unparse, чтобы гарантировать document_id
        result = self._unparse(text, entities)

        # На всякий случай заменяем tg-emoji на нужный формат (если вдруг)
        result = re.sub(
            r'<tg-emoji emoji-id="?(\d+)"?>(.*?)</tg-emoji>',
            r'<emoji document_id=\1>\2</emoji>',
            result,
            flags=re.DOTALL,
        )
        result = re.sub(
            r'<tg-emoji emoji-id=(\d+)>(.*?)</tg-emoji>',
            r'<emoji document_id=\1>\2</emoji>',
            result,
            flags=re.DOTALL,
        )

        return result

    def _unparse(self, text: str, entities) -> str:
        """Unparse с правильной вложенностью + <emoji document_id=...>"""
        ENTITY_TO_FORMATTER = {
            MessageEntityBold: ("<b>", "</b>"),
            MessageEntityItalic: ("<i>", "</i>"),
            MessageEntityCode: ("<code>", "</code>"),
            MessageEntityUnderline: ("<u>", "</u>"),
            MessageEntityStrike: ("<s>", "</s>"),
            MessageEntityBlockquote: ("<blockquote>", "</blockquote>"),
            MessageEntitySpoiler: ("<tg-spoiler>", "</tg-spoiler>"),
            MessageEntityPre: lambda e, _: (
                f'<pre><code class="language-{html.escape(getattr(e, "language", "") or "")}">',
                "</code></pre>",
            ),
            MessageEntityTextUrl: lambda e, _: (
                f'<a href="{html.escape(e.url)}">',
                "</a>",
            ),
            MessageEntityMentionName: lambda e, _: (
                f'<a href="tg://user?id={e.user_id}">',
                "</a>",
            ),
            MessageEntityCustomEmoji: lambda e, _: (
                f'<emoji document_id={e.document_id}>',
                "</emoji>",
            ),
            MessageEntityUrl: lambda _, t: (f'<a href="{html.escape(t)}">', "</a>"),
            MessageEntityEmail: lambda _, t: (f'<a href="mailto:{html.escape(t)}">', "</a>"),
        }

        text = _add_surrogate(text)
        insert_at = []

        for i, entity in enumerate(entities):
            s = entity.offset
            e = entity.offset + entity.length
            delimiter = ENTITY_TO_FORMATTER.get(type(entity))
            if not delimiter:
                continue
            if callable(delimiter):
                delimiter = delimiter(entity, text[s:e])
            insert_at.append((s, i, delimiter[0]))
            insert_at.append((e, -i, delimiter[1]))

        insert_at.sort(key=lambda t: (t[0], t[1]))
        next_escape_bound = len(text)

        while insert_at:
            at, _, what = insert_at.pop()
            while _within_surrogate(text, at):
                at += 1
            text = text[:at] + what + html.escape(text[at:next_escape_bound]) + text[next_escape_bound:]
            next_escape_bound = at

        text = html.escape(text[:next_escape_bound]) + text[next_escape_bound:]
        return _del_surrogate(text)

    @loader.command(
        ru_doc="Реплаем на любое сообщение показывает его HTML-исходник (форматирование + эмодзи)",
        en_doc="Reply to any message to get its HTML source (formatting + premium emoji)",
    )
    async def em(self, message: CustomMessage):
        """Показать HTML-исходник сообщения"""
        reply = await message.get_reply_message()

        if not reply:
            await utils.answer(message, self.strings("no_reply"))
            return

        result = self.to_html(reply)

        if result.startswith("❌"):
            await utils.answer(message, self.strings("no_content"))
            return

        await utils.answer(message, f"<code>{html.escape(result)}</code>")
