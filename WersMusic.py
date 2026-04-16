# meta developer: @Wers1xx

import asyncio
from .. import loader, utils

@loader.tds
class WersMusicMod(loader.Module):
    """Поиск и скачивание музыки через @WersModule_Musicbot"""

    strings = {
        "name": "WersMusic",
        "searching": "🔍 <b>Ищу: {}</b>",
        "no_args": "❌ <b>Укажите название песни</b>\n\n<b>Пример:</b> <code>.wm название песни</code>",
        "bot_not_found": "❌ <b>Бот не найден</b>",
        "no_results": "❌ <b>Ничего не найдено</b>",
        "select_track": "🎵 <b>Выберите трек:</b>",
        "downloading": "📥 <b>Скачиваю...</b>",
        "uploading": "📤 <b>Отправляю...</b>",
        "waiting": "⏳ <b>Ожидаю загрузку...</b>",
        "error": "❌ <b>Ошибка:</b> {}",
        "expired": "❌ Сессия истекла"
    }

    async def client_ready(self, client, db):
        self.client = client
        self.bot = "WersModule_Musicbot"
        self.cache = {}

    @loader.command()
    async def wm(self, message):
        """<название> - Найти и скачать музыку через WersModule_Musicbot"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        if not args:
            await utils.answer(message, self.strings["no_args"])
            return

        status = await utils.answer(message, self.strings["searching"].format(args))

        try:
            bot = await self.client.get_entity(self.bot)
        except:
            await utils.answer(status, self.strings["bot_not_found"])
            return

        try:
            async with self.client.conversation(bot, timeout=60) as conv:
                await conv.send_message(args)
                
                resp = None
                for _ in range(15):
                    r = await conv.get_response()
                    if r.text and any(e in r.text for e in ["⏳", "⌛"]):
                        continue
                    if r.buttons:
                        resp = r
                        break
                    await asyncio.sleep(0.3)

                if not resp:
                    await utils.answer(status, self.strings["no_results"])
                    return

                tracks = []
                for row in resp.buttons:
                    for btn in row:
                        if hasattr(btn, 'text') and btn.text:
                            t = btn.text.strip()
                            skip = ["❌", "Назад", "Вперед", "Больше", "🎵", ".", "Отмена", "Закрыть", "Добавить"]
                            if t and len(t) > 3 and not any(s in t for s in skip):
                                tracks.append({"title": t, "btn": btn})

                if not tracks:
                    await utils.answer(status, self.strings["no_results"])
                    return

                cid = f"{message.chat_id}_{message.id}"
                self.cache[cid] = {
                    "tracks": tracks[:10],
                    "conv": conv,
                    "status": status,
                    "orig": message,
                    "reply": reply,
                    "bot": bot
                }

                buttons = []
                for i, t in enumerate(tracks[:10]):
                    buttons.append([{
                        "text": f"{i+1}. {t['title'][:40]}",
                        "callback": self._create_callback(cid, i)
                    }])
                
                buttons.append([{
                    "text": "❌ Отмена",
                    "callback": self._create_cancel_callback(cid)
                }])

                await self.inline.form(
                    text=self.strings["select_track"],
                    message=status,
                    reply_markup=buttons,
                    ttl=300
                )

        except asyncio.TimeoutError:
            await utils.answer(status, self.strings["error"].format("Таймаут"))
        except Exception as e:
            await utils.answer(status, self.strings["error"].format(str(e)))

    def _create_callback(self, cid, idx):
        async def handler(call):
            c = self.cache.get(cid)
            if not c:
                await call.answer(self.strings["expired"], alert=True)
                return

            track = c["tracks"][idx]
            await call.answer("✅ Выбрано", alert=False)
            
            try:
                await self.client.edit_message(c["status"], self.strings["downloading"])
            except:
                pass

            try:
                await track["btn"].click()
                await asyncio.sleep(1)
                
                audio_msg = None
                for _ in range(30):
                    await asyncio.sleep(0.5)
                    messages = await self.client.get_messages(c["bot"], limit=2)
                    
                    for msg in messages:
                        if msg.media:
                            if msg.text and "Загрузка" in msg.text:
                                try:
                                    await self.client.edit_message(c["status"], self.strings["waiting"])
                                except:
                                    pass
                                break
                            else:
                                audio_msg = msg
                                break
                    
                    if audio_msg:
                        break

                if audio_msg and audio_msg.media:
                    try:
                        await self.client.edit_message(c["status"], self.strings["uploading"])
                    except:
                        pass
                    
                    await self.client.send_file(
                        c["orig"].chat_id,
                        audio_msg.media,
                        reply_to=c["reply"].id if c["reply"] else c["orig"].id
                    )
                    
                    try:
                        await c["status"].delete()
                    except:
                        pass
                        
                    try:
                        await call.delete()
                    except:
                        pass
                else:
                    try:
                        await self.client.edit_message(c["status"], self.strings["error"].format("Файл не найден"))
                    except:
                        pass

            except Exception as e:
                try:
                    await self.client.edit_message(c["status"], self.strings["error"].format(str(e)))
                except:
                    pass
            finally:
                self.cache.pop(cid, None)

        return handler

    def _create_cancel_callback(self, cid):
        async def handler(call):
            self.cache.pop(cid, None)
            await call.answer("🔴 Отмена", alert=False)
            try:
                await call.delete()
            except:
                pass

        return handler