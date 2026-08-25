# meta developer: @Wers1xx
# scope: hikka_only
# scope: hikka_min 1.2.10

from .. import loader, utils
import logging
import asyncio
import os
import random
from telethon import types, functions

logger = logging.getLogger(__name__)

@loader.tds
class StoryPosterMod(loader.Module):
    """Модуль для публикации сторис по реплаю на медиа"""
    
    strings = {
        "name": "StoryPoster",
        "no_reply": "<b>❌ Нужно ответить на медиа (фото/видео)</b>",
        "not_media": "<b>❌ Это не медиа файл</b>",
        "uploading": "<b>📤 Публикую сторис...</b>",
        "success": "<b>✅ Сторис успешно опубликована!</b>",
        "error": "<b>❌ Ошибка при публикации: {}</b>",
        "processing": "<b>⏳ Обрабатываю медиа...</b>",
        "preparing": "<b>🎬 Подготавливаю медиа для сторис...</b>",
    }
    
    strings_ru = {
        "no_reply": "<b>❌ Нужно ответить на медиа (фото/видео)</b>",
        "not_media": "<b>❌ Это не медиа файл</b>",
        "uploading": "<b>📤 Публикую сторис...</b>",
        "success": "<b>✅ Сторис успешно опубликована!</b>",
        "error": "<b>❌ Ошибка при публикации: {}</b>",
        "processing": "<b>⏳ Обрабатываю медиа...</b>",
        "preparing": "<b>🎬 Подготавливаю медиа для сторис...</b>",
    }

    async def _publish_story(self, client, media_path, caption=""):
        """Публикует сторис используя правильный API метод"""
        try:
            # Загружаем файл на сервер Telegram
            uploaded_file = await client.upload_file(media_path)
            
            # Определяем тип медиа
            file_ext = os.path.splitext(media_path)[1].lower()
            is_photo = file_ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp']
            
            # Создаем правильный InputMedia для сторис
            if is_photo:
                input_media = types.InputMediaUploadedPhoto(
                    file=uploaded_file
                )
            else:
                input_media = types.InputMediaUploadedDocument(
                    file=uploaded_file,
                    mime_type="video/mp4",
                    attributes=[
                        types.DocumentAttributeVideo(
                            duration=0,
                            w=720,
                            h=1280,
                            round_message=False,
                            supports_streaming=True
                        )
                    ]
                )
            
            # Прямой вызов API метода stories.sendStory с обязательным random_id
            result = await client(
                functions.stories.SendStoryRequest(
                    peer='me',
                    media=input_media,
                    caption=caption if caption else "",
                    privacy_rules=[types.InputPrivacyValueAllowAll()],
                    random_id=random.randint(-(2**63), 2**63 - 1)
                )
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error publishing story: {e}")
            raise e

    async def storycmd(self, message):
        """Публикует сторис из медиа по реплаю. Использование: .story [caption]"""
        
        reply = await message.get_reply_message()
        
        if not reply:
            await utils.answer(message, self.strings("no_reply"))
            return
            
        if not reply.media:
            await utils.answer(message, self.strings("not_media"))
            return
        
        # Получаем подпись
        args = utils.get_args_raw(message)
        caption = args if args else (reply.message if reply.message else "")
        
        # Показываем статус
        status_msg = await utils.answer(message, self.strings("preparing"))
        
        try:
            # Скачиваем медиа
            media_path = await reply.download_media()
            if not media_path:
                await utils.answer(status_msg, self.strings("error").format("не удалось скачать медиа"))
                return
            
            await utils.answer(status_msg, self.strings("uploading"))
            
            # Публикуем сторис
            await self._publish_story(message.client, media_path, caption)
            
            # Очищаем временный файл
            if os.path.exists(media_path):
                os.remove(media_path)
            
            await utils.answer(status_msg, self.strings("success"))
            
        except Exception as e:
            logger.error(f"Error posting story: {e}")
            await utils.answer(status_msg, self.strings("error").format(str(e)))