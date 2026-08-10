# meta developer: @Wers1xx
# scope: hikka_only
# scope: hikka_min 1.2.10

from telethon.tl.types import Message
from telethon.tl.custom import Message as CustomMessage
from .. import loader, utils
import html

@loader.tds
class PremiumEmojiInfoMod(loader.Module):
    """Показывает document_id премиум эмодзи по реплаю (для тех кому лень использовать .e r.text)"""
    
    strings = {
        "name": "PremiumEmojiInfo",
        "no_reply": "<b>❌ Нужен реплай на сообщение с премиум эмодзи</b>",
        "no_emoji": "<b>❌ В сообщении нет премиум эмодзи</b>",
    }
    
    strings_ru = {
        "no_reply": "<b>❌ Нужен реплай на сообщение с премиум эмодзи</b>",
        "no_emoji": "<b>❌ В сообщении нет премиум эмодзи</b>",
    }
    
    @loader.command(
        ru_doc="Реплаем на сообщение с премиум эмодзи показывает его document_id",
        en_doc="Reply to message with premium emoji to get its document_id"
    )
    async def em(self, message: CustomMessage):
        """Показать document_id премиум эмодзи"""
        reply = await message.get_reply_message()
        
        if not reply:
            await utils.answer(message, self.strings("no_reply"))
            return
        
        # Собираем все эмодзи из сообщения
        entities = []
        if reply.entities:
            for entity in reply.entities:
                if hasattr(entity, 'document_id') and entity.document_id:
                    entities.append(entity)
        
        # Если нет entities, но есть media (стикер-эмодзи)
        if not entities and reply.document:
            if hasattr(reply.document, 'attributes'):
                for attr in reply.document.attributes:
                    if hasattr(attr, 'document_id') and attr.document_id:
                        entities.append(attr)
                        break
        
        if not entities:
            await utils.answer(message, self.strings("no_emoji"))
            return
        
        # Формируем ответ с экранированием HTML
        result_parts = []
        
        for entity in entities:
            doc_id = entity.document_id
            # Получаем текст эмодзи из сообщения
            if hasattr(entity, 'offset') and hasattr(entity, 'length'):
                emoji_text = reply.raw_text[entity.offset:entity.offset + entity.length]
            else:
                emoji_text = "❓"
            
            # Экранируем HTML теги, чтобы они отображались как текст
            escaped_text = html.escape(f"<emoji document_id={doc_id}>{emoji_text}</emoji>")
            result_parts.append(f"<code>{escaped_text}</code>")
        
        await utils.answer(message, "\n".join(result_parts))