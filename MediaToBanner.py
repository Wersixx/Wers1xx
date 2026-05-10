# meta developer: @Wers1xx

import io
import logging
import os
import tempfile
from typing import Optional

from .. import loader, utils
from ..types import Message

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)


@loader.tds
class MediaToBannerMod(loader.Module):
    """Установка баннера через реплай на медиа"""

    strings = {
        "name": "MediaToBanner",
        "no_reply": "❌ <b>Нужно ответить на медиа</b>",
        "no_media": "❌ <b>В ответе нет медиа</b>",
        "getting_url": "🔄 <b>Загружаю...</b>",
        "uploading": "📤 <b>Загружаю на хостинг...</b>",
        "success": "✅ <b>Баннер {} установлен!</b>",
        "upload_failed": "❌ <b>Не удалось загрузить</b>",
        "no_requests": "❌ <b>pip install requests</b>",
        "ping_banner": "пинга",
        "info_banner": "инфо",
    }
    
    strings_ru = {
        "no_reply": "❌ <b>Нужно ответить на медиа</b>",
        "no_media": "❌ <b>В ответе нет медиа</b>",
        "getting_url": "🔄 <b>Загружаю...</b>",
        "uploading": "📤 <b>Загружаю на хостинг...</b>",
        "success": "✅ <b>Баннер {} установлен!</b>",
        "upload_failed": "❌ <b>Не удалось загрузить</b>",
        "no_requests": "❌ <b>pip install requests</b>",
        "ping_banner": "пинга",
        "info_banner": "инфо",
    }
    
    async def client_ready(self, client, db):
        self.client = client
        self.db = db
    
    async def _upload_to_x0(self, file_path: str, ext: str) -> Optional[str]:
        """Загружает на x0.at"""
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (f'banner.{ext}', f)}
                resp = requests.post('https://x0.at/', files=files, timeout=15)
            
            if resp.status_code == 200:
                url = resp.text.strip()
                if url.startswith('http'):
                    return url
        except Exception as e:
            logger.error(f"x0.at: {e}")
        return None
    
    async def _upload_to_catbox(self, file_path: str, ext: str) -> Optional[str]:
        """Загружает на catbox.moe"""
        try:
            with open(file_path, 'rb') as f:
                files = {
                    'reqtype': (None, 'fileupload'),
                    'fileToUpload': (f'banner.{ext}', f)
                }
                resp = requests.post(
                    'https://catbox.moe/user/api.php',
                    files=files,
                    timeout=15
                )
            
            if resp.status_code == 200:
                url = resp.text.strip()
                if url.startswith('http'):
                    return url
        except Exception as e:
            logger.error(f"catbox: {e}")
        return None
    
    async def _upload_to_pomf(self, file_path: str, ext: str) -> Optional[str]:
        """Загружает на pomf.lain.la"""
        try:
            with open(file_path, 'rb') as f:
                files = {'files[]': (f'banner.{ext}', f)}
                resp = requests.post(
                    'https://pomf.lain.la/upload.php',
                    files=files,
                    timeout=15
                )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get('files') and len(data['files']) > 0:
                    return data['files'][0].get('url')
        except Exception as e:
            logger.error(f"pomf: {e}")
        return None
    
    @loader.command()
    async def ft(self, message: Message):
        """Установить баннер пинга из ответного медиа"""
        await self._set_banner(message, "ping")
    
    @loader.command()
    async def fi(self, message: Message):
        """Установить баннер инфо из ответного медиа"""
        await self._set_banner(message, "info")
    
    async def _set_banner(self, message: Message, banner_type: str):
        replied = await message.get_reply_message()
        if not replied:
            await utils.answer(message, self.strings("no_reply"))
            return
        
        if not (replied.photo or replied.video or replied.animation or replied.document):
            await utils.answer(message, self.strings("no_media"))
            return
        
        if requests is None:
            await utils.answer(message, self.strings("no_requests"))
            return
        
        status = await utils.answer(message, self.strings("getting_url"))
        
        # Определяем расширение
        ext = "jpg"
        if replied.video:
            ext = "mp4"
        elif replied.animation:
            ext = "gif"
        elif replied.document:
            for attr in getattr(replied.document, 'attributes', []):
                name = getattr(attr, 'file_name', '')
                if '.' in name:
                    ext = name.split('.')[-1]
                    break
        
        tmp_path = None
        media_url = None
        
        try:
            # Скачиваем
            tmp_path = os.path.join(tempfile.gettempdir(), f"banner_{message.id}.{ext}")
            await self.client.download_media(replied, file=tmp_path)
            
            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                await status.edit(self.strings("upload_failed"))
                return
            
            await status.edit(self.strings("uploading"))
            
            # Пробуем хостинги по очереди
            for uploader in [self._upload_to_x0, self._upload_to_catbox, self._upload_to_pomf]:
                media_url = await uploader(tmp_path, ext)
                if media_url:
                    break
            
            if not media_url:
                await status.edit(self.strings("upload_failed"))
                return
            
            # Прямая установка конфига через lookup
            try:
                if banner_type == "ping":
                    tester_mod = self.lookup("tester")
                    if tester_mod:
                        tester_mod.config["banner_url"] = media_url
                else:
                    herokuinfo_mod = self.lookup("herokuinfo")
                    if herokuinfo_mod:
                        herokuinfo_mod.config["banner_url"] = media_url
            except Exception as e:
                logger.error(f"Config set error: {e}")
                await status.edit(f"❌ Ошибка установки: {e}")
                return
            
            name = self.strings("ping_banner") if banner_type == "ping" else self.strings("info_banner")
            await status.edit(self.strings("success").format(name))
            
        except Exception as e:
            logger.error(f"Error: {e}")
            await status.edit(f"❌ {e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass