# meta developer: @Wers1xx

import asyncio
from .. import loader, utils

@loader.tds
class WersMusicMod(loader.Module):
    """Поиск и скачивание музыки через @WersModule_Musicbot"""

    strings = {
        "name": "WersMusic",
        "searching": "<emoji document_id=5231012545799666522>🔍</emoji> <b>Ищу: {}</b>",
        "no_args": "<emoji document_id=5210952531676504517>❌</emoji> <b>Укажите название песни</b>\n\n<b>Пример:</b> <code>.wm название песни</code>",
        "bot_not_found": "<emoji document_id=5210952531676504517>❌</emoji> <b>Бот не найден</b>",
        "no_results": "<emoji document_id=5210952531676504517>❌</emoji> <b>Ничего не найдено</b>",
        "select_track": "<emoji document_id=5463107823946717464>🎵</emoji> <b>Выберите трек:</b>",
        "downloading": "<emoji document_id=6030828743004524170>📥</emoji> <b>Скачиваю...</b>",
        "uploading": "<emoji document_id=5445355530111437729>📤</emoji> <b>Отправляю...</b>",
        "waiting": "<emoji document_id=5386367538735104399>⌛</emoji> <b>Ожидаю загрузку...</b>",
        "error": "<emoji document_id=5210952531676504517>❌</emoji> <b>Ошибка:</b> {}",
        "expired": "<emoji document_id=5210952531676504517>❌</emoji> Сессия истекла",
        "sub_required": "<emoji document_id=5350626912546865231>‼️</emoji> <b>Для использования модуля необходимо подписаться на каналы бота:</b>",
        "ignore_warning": "Если проигнорировать подписку на ресурсы то вы не сможете использовать модуль!",
        "ignored_text": "<emoji document_id=5210952531676504517>❌</emoji> <b>Подписка проигнорирована. Модуль отменен.</b>"
    }

    async def client_ready(self, client, db):
        self.client = client
        self.bot = "WersModule_Musicbot"
        self.cache = {}

    async def _clear_bot_chat(self, bot):
        """Полная очистка всех сообщений в чате с ботом"""
        try:
            while True:
                messages = await self.client.get_messages(bot, limit=100)
                if not messages:
                    break
                msg_ids = [m.id for m in messages]
                await self.client.delete_messages(bot, msg_ids)
                if len(messages) < 100:
                    break
                await asyncio.sleep(0.5)
        except Exception:
            pass

    @loader.command()
    async def wm(self, message):
        """<название> - Найти и скачать музыку через @WersModule_Musicbot"""
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

                # Проверка на запрос подписки
                is_sub_req = False
                for row in resp.buttons:
                    for btn in row:
                        if hasattr(btn, 'text') and btn.text:
                            t = btn.text.strip().lower()
                            if any(k in t for k in ["подписа", "канал", "спас"]):
                                is_sub_req = True
                                break
                    if is_sub_req:
                        break

                if is_sub_req or any(any(any(k in btn.text.lower() for k in ["подписа", "канал"]) for btn in row) for row in resp.buttons):
                    cid = f"{message.chat_id}_{message.id}"
                    
                    sub_links = []
                    for row in resp.buttons:
                        for btn in row:
                            if hasattr(btn, 'url') and btn.url:
                                sub_links.append(btn)

                    self.cache[cid] = {
                        "conv": conv,
                        "status": status,
                        "orig": message,
                        "reply": reply,
                        "bot": bot,
                        "args": args,
                        "resp": resp,
                        "sub_links": sub_links
                    }

                    buttons = []
                    for btn in sub_links:
                        buttons.append([{
                            "text": f"📢 {btn.text}",
                            "url": btn.url
                        }])
                    
                    buttons.append([
                        {"text": "✅ Подписаться", "callback": self._create_sub_callback(cid)},
                        {"text": "❌ Игнор", "callback": self._create_ignore_callback(cid)}
                    ])

                    await self.inline.form(
                        text=self.strings["sub_required"],
                        message=status,
                        reply_markup=buttons,
                        ttl=300
                    )
                    return

                await self._process_tracks_response(resp, status, message, reply, bot, conv, args)

        except asyncio.TimeoutError:
            await utils.answer(status, self.strings["error"].format("Таймаут"))
        except Exception as e:
            await utils.answer(status, self.strings["error"].format(str(e)))

    async def _process_tracks_response(self, resp, status, message, reply, bot, conv, args):
        tracks = []
        for row in resp.buttons:
            for btn in row:
                if hasattr(btn, 'text') and btn.text:
                    t = btn.text.strip()
                    skip = ["❌", "Назад", "Вперед", "Больше", "🎵", ".", "Отмена", "Закрыть", "Добавить"]
                    if t and not any(s in t for s in skip):
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
            "bot": bot,
            "args": args
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

    def _create_sub_callback(self, cid):
        async def handler(call):
            c = self.cache.get(cid)
            if not c:
                await call.answer(self.strings["expired"], alert=True)
                return

            await call.answer("🔄 Проверяем подписки...", alert=False)
            
            try:
                for btn in c.get("sub_links", []):
                    if hasattr(btn, 'url') and btn.url:
                        try:
                            if "t.me/" in btn.url:
                                username = btn.url.split("t.me/")[-1].split("/")[0].split("?")[0]
                                if username:
                                    await self.client(
                                        __import__('telethon.tl.functions.channels', fromlist=['JoinChannelRequest']).JoinChannelRequest(
                                            username
                                        )
                                    )
                                    await asyncio.sleep(0.5)
                        except Exception:
                            pass

                # Полная очистка чата с ботом
                await self._clear_bot_chat(c["bot"])

                # Заново отправляем боту запрос с треком
                await c["conv"].send_message(c["args"])
                
                resp = None
                for _ in range(15):
                    r = await c["conv"].get_response()
                    if r.text and any(e in r.text for e in ["⏳", "⌛"]):
                        continue
                    if r.buttons:
                        resp = r
                        break
                    await asyncio.sleep(0.3)

                if not resp:
                    await self.client.edit_message(c["status"], self.strings["no_results"])
                    return

                await call.delete()
                await self._process_tracks_response(resp, c["status"], c["orig"], c["reply"], c["bot"], c["conv"], c["args"])

            except Exception as e:
                await self.client.edit_message(c["status"], self.strings["error"].format(str(e)))

        return handler

    def _create_ignore_callback(self, cid):
        async def handler(call):
            c = self.cache.get(cid)
            if not c:
                await call.answer(self.strings["expired"], alert=True)
                return

            buttons = [
                [
                    {"text": "Подтвердить", "callback": self._create_confirm_ignore_callback(cid)},
                    {"text": "Отменить", "callback": self._create_cancel_callback(cid)}
                ]
            ]

            await call.edit(
                text=self.strings["ignore_warning"],
                reply_markup=buttons
            )

        return handler

    def _create_confirm_ignore_callback(self, cid):
        async def handler(call):
            self.cache.pop(cid, None)
            await call.answer("❌ Отменено", alert=False)
            try:
                await call.edit(text=self.strings["ignored_text"])
            except:
                pass

        return handler

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
                    
                    # Отправляем аудио файл пользователю
                    await self.client.send_file(
                        c["orig"].chat_id,
                        audio_msg.media,
                        reply_to=c["reply"].id if c["reply"] else c["orig"].id
                    )
                    
                    # Удаляем статусное/инлайн сообщение модуля
                    try:
                        await c["status"].delete()
                    except:
                        pass
                        
                    try:
                        await call.delete()
                    except:
                        pass

                    # Полная очистка чата с ботом
                    await self._clear_bot_chat(c["bot"])
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