# meta developer: @Wers1xx
# requires: yt-dlp aiohttp aiofiles

import os
import asyncio
import aiohttp
import aiofiles
import yt_dlp
from .. import loader, utils

@loader.tds
class MediaLoaderMod(loader.Module):
    """Универсальный загрузчик видео из TikTok, Instagram, Pinterest, Likee и 1000+ других сайтов"""

    strings = {
        "name": "MediaLoader",
        "processing": "⏳ <b>Обрабатываю ссылку...</b>",
        "downloading": "📤 <b>Скачиваю и отправляю файл...</b>",
        "error": "❌ <b>Ошибка загрузки:</b> {}",
        "no_args": "❌ <b>Укажите ссылку на видео.</b>",
        "unsupported": "❌ <b>Не удалось извлечь видео. Возможно, ссылка приватная или недействительная.</b>",
        "file_too_big": "❌ <b>Файл превышает 2 ГБ (ограничение Telegram).</b>",
        "success": "✅ <b>Скачано с помощью MediaLoader</b>"
    }

    async def client_ready(self, client, db):
        self.client = client
        self.temp_dir = "media_downloads"
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    @loader.command()
    async def dlv(self, message):
        """<ссылка> - Скачать видео из поддерживаемого источника"""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings["no_args"])
            return

        url = args.strip()
        msg = await utils.answer(message, self.strings["processing"])
        
        file_path = None
        title = ""
        
        try:
            # Скачиваем напрямую через yt-dlp (это решит проблему с неработающими видео)
            file_path, title = await self._download_via_ytdlp(url)
            
            if not file_path or not os.path.exists(file_path):
                await utils.answer(msg, self.strings["unsupported"])
                return

            await utils.answer(msg, self.strings["downloading"])
            
            file_size = os.path.getsize(file_path)
            if file_size > 2000 * 1024 * 1024:
                await utils.answer(msg, self.strings["file_too_big"])
                return

            caption = f"{self.strings['success']}\n<b>Источник:</b> {url}"
            if title:
                caption = f"<b>{title}</b>\n{caption}"
            
            await self.client.send_file(
                message.chat_id,
                file_path,
                caption=caption,
                reply_to=message.reply_to_msg_id or message.id,
                supports_streaming=True
            )
            await msg.delete()
            
        except Exception as e:
            await utils.answer(msg, self.strings["error"].format(str(e)))
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

    async def _download_via_ytdlp(self, url: str):
        """
        Скачивает видео напрямую через yt-dlp в отдельном потоке.
        Это гарантирует правильный формат и работоспособность файла.
        """
        # Генерируем уникальное имя файла
        import uuid
        temp_filename = f"{uuid.uuid4().hex}.%(ext)s"
        output_template = os.path.join(self.temp_dir, temp_filename)
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'outtmpl': output_template,
            'format': 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / bv*+ba/b',
            'merge_output_format': 'mp4',
            'cookiefile': 'cookies.txt',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            },
            'restrictfilenames': True,
        }
        
        loop = asyncio.get_event_loop()
        
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Определяем путь к скачанному файлу
                if 'entries' in info:
                    info = info['entries'][0]
                
                # Получаем реальное имя файла, которое использовал yt-dlp
                filename = ydl.prepare_filename(info)
                if not os.path.exists(filename):
                    # Пробуем с mp4 расширением
                    base = os.path.splitext(filename)[0]
                    filename = f"{base}.mp4"
                
                title = info.get('title', '')
                return filename, title
        
        return await loop.run_in_executor(None, download)

    async def _download_file(self, url: str, path: str) -> bool:
        """
        Запасной метод для прямого скачивания URL.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return False
                        
                    async with aiofiles.open(path, 'wb') as f:
                        async for chunk in resp.content.iter_chunked(1024 * 1024):
                            await f.write(chunk)
            return True
        except Exception:
            return False