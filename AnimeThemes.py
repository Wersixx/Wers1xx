# meta developer: @Wers1xx
# meta pic: https://img.icons8.com/fluency/48/000000/anime.png
# scope: hikka_only
# scope: hikka_min 1.2.10

from telethon.tl.types import Message
from .. import loader, utils
import asyncio

@loader.tds
class AnimeThemesMod(loader.Module):
    """Модуль для получения рандомных тем для тг"""
    
    strings = {
        "name": "AnimeThemes",
        "processing": "<b><emoji document_id=5116163917713769254>⭐️</emoji> Запрашиваю темы...</b>",
        "no_response": "<b><emoji document_id=5121063440311386962>👎</emoji> Бот не ответил. Попробуйте позже.</b>",
        "_cmd_doc_tem": "Искать рандомные темы"
    }
    
    strings_ru = {
        "processing": "<b><emoji document_id=5116163917713769254>⭐️</emoji> Запрашиваю темы...</b>",
        "no_response": "<b><emoji document_id=5121063440311386962>👎</emoji> Бот не ответил. Попробуйте позже.</b>",
        "_cmd_doc_tem": "Искать рандомные темы"
    }
    
    async def _send_copy(self, message: Message, peer_id):
        """Копирует сообщение без пересылки"""
        if message.media:
            await self._client.send_file(
                peer_id,
                message.media,
                caption=message.text,
            )
        else:
            await self._client.send_message(
                peer_id,
                message.text,
            )
    
    @loader.command(ru_doc="Искать рандомные темы")
    async def temcmd(self, message: Message):
        """Ищет рандомные темы через @animerar_bot"""
        bot_username = "@animerar_bot"
        text_to_send = "✨ Темы"
        
        status_msg = await utils.answer(message, self.strings("processing"))
        
        async with self._client.conversation(bot_username) as conv:
            await conv.send_message(text_to_send)
            
            try:
                response = await conv.get_response(timeout=30)
            except asyncio.TimeoutError:
                await utils.answer(message, self.strings("no_response"))
                return
            
            if not response:
                await utils.answer(message, self.strings("no_response"))
                return
            
            await self._send_copy(response, message.peer_id)
            
            while True:
                try:
                    extra_response = await conv.get_response(timeout=2)
                    if extra_response:
                        await self._send_copy(extra_response, message.peer_id)
                except asyncio.TimeoutError:
                    break
        
        if status_msg:
            await status_msg.delete()
        
        try:
            await message.delete()
        except:
            pass
        
        try:
            await self._client.delete_dialog(bot_username)
        except:
            pass
    
    async def client_ready(self, client, db):
        self._client = client