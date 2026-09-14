# meta developer: @Wers1xx

import asyncio
from .. import loader, utils

@loader.tds
class WersMusicMod(loader.Module):
    """Поиск и скачивание музыки через @WersModule_Musicbot + Шазам по видео"""

    strings = {
        "name": "WersMusic",
        "searching": "<emoji document_id=5231012545799666522>🔍</emoji> <b>Ищу: {}</b>",
        "shazaming": "<emoji document_id=5231012545799666522>🔍</emoji> <b>Распознаю трек из медиа...</b>",
        "no_args": "<emoji document_id=5210952531676504517>❌</emoji> <b>Укажите название песни или ответьте на видео/аудио</b>\n\n<b>Пример:</b> <code>.wm название песни</code>\nили реплай на видео + <code>.wm</code>",
        "bot_not_found": "<emoji document_id=5210952531676504517>❌</emoji> <b>Бот не найден</b>",
        "no_results": "<emoji document_id=5210952531676504517>❌</emoji> <b>Ничего не найдено</b>",
        "select_track": "🎵 <b>Выберите трек:</b>",
        "downloading": "<emoji document_id=6030828743004524170>📥</emoji> <b>Скачиваю...</b>",
        "uploading": "<emoji document_id=5445355530111437729>📤</emoji> <b>Отправляю...</b>",
        "waiting": "<emoji document_id=5386367538735104399>⌛</emoji> <b>Ожидаю загрузку...</b>",
        "error": "<emoji document_id=5210952531676504517>❌</emoji> <b>Ошибка:</b> {}",
        "expired": "❌ Сессия истекла",
        "sub_required": "‼️ <b>Для использования модуля необходимо подписаться на каналы бота:</b>",
        "ignore_warning": "Если проигнорировать подписку на ресурсы то вы не сможете использовать модуль!",
        "ignored_text": "<emoji document_id=5210952531676504517>❌</emoji> <b>Подписка проигнорирована. Модуль отменен.</b>",
        "no_media": "<emoji document_id=5210952531676504517>❌</emoji> <b>В реплае нет видео/аудио</b>",
    }

    async def client_ready(self, client, db):
        self.client = client
        self.bot = "WersModule_Musicbot"
        self.cache = {}

    async def _delete_bot_dialog(self, bot):
        """Полностью удаляет диалог с ботом, чтобы не осталось следов"""
        try:
            await self.client.delete_dialog(bot)
        except Exception:
            pass

    @loader.command()
    async def wm(self, message):
        """<название> - Найти и скачать музыку / реплай на видео = Шазам"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        # Режим Шазам: реплай на медиа без текста или с .wm
        is_shazam = False
        media = None
        if reply and (reply.video or reply.audio or reply.voice or reply.video_note or (reply.document and reply.document.mime_type and "video" in reply.document.mime_type)):
            is_shazam = True
            media = reply.media

        if not args and not is_shazam:
            await utils.answer(message, self.strings["no_args"])
            return

        if is_shazam:
            status = await utils.answer(message, self.strings["shazaming"])
        else:
            status = await utils.answer(message, self.strings["searching"].format(args))

        try:
            bot = await self.client.get_entity(self.bot)
        except Exception:
            await utils.answer(status, self.strings["bot_not_found"])
            return

        try:
            async with self.client.conversation(bot, timeout=90) as conv:
                if is_shazam and media:
                    # Пересылаем медиа боту для распознавания
                    await conv.send_file(media)
                else:
                    await conv.send_message(args)

                resp = None
                for _ in range(20):
                    r = await conv.get_response()
                    if r.text and any(e in r.text for e in ["⏳", "⌛", "Загрузка", "распозна"]):
                        continue
                    if r.buttons:
                        resp = r
                        break
                    # Иногда бот сразу кидает аудио после шазама
                    if r.media and (r.audio or r.document):
                        # Прямо отправляем найденный трек
                        try:
                            await self.client.edit_message(status, self.strings["uploading"])
                        except Exception:
                            pass
                        await self.client.send_file(
                            message.chat_id,
                            r.media,
                            reply_to=reply.id if reply else message.id
                        )
                        try:
                            await status.delete()
                        except Exception:
                            pass
                        await self._delete_bot_dialog(bot)
                        return
                    await asyncio.sleep(0.4)

                if not resp:
                    await utils.answer(status, self.strings["no_results"])
                    await self._delete_bot_dialog(bot)
                    return

                # Проверка на запрос подписки
                is_sub_req = False
                for row in resp.buttons:
                    for btn in row:
                        if hasattr(btn, "text") and btn.text:
                            t = btn.text.strip().lower()
                            if any(k in t for k in ["подписа", "канал", "спас"]):
                                is_sub_req = True
                                break
                    if is_sub_req:
                        break

                if is_sub_req:
                    cid = f"{message.chat_id}_{message.id}"

                    sub_links = []
                    for row in resp.buttons:
                        for btn in row:
                            if hasattr(btn, "url") and btn.url:
                                sub_links.append(btn)

                    self.cache[cid] = {
                        "conv": conv,
                        "status": status,
                        "orig": message,
                        "reply": reply,
                        "bot": bot,
                        "args": args,
                        "resp": resp,
                        "sub_links": sub_links,
                        "is_shazam": is_shazam,
                        "media": media,
                    }

                    buttons = []
                    for btn in sub_links:
                        buttons.append([{"text": f"📢 {btn.text}", "url": btn.url}])

                    buttons.append([
                        {"text": "✅ Подписаться", "callback": self._create_sub_callback(cid)},
                        {"text": "❌ Игнор", "callback": self._create_ignore_callback(cid)},
                    ])

                    await self.inline.form(
                        text=self.strings["sub_required"],
                        message=status,
                        reply_markup=buttons,
                        ttl=300,
                    )
                    return

                await self._process_tracks_response(resp, status, message, reply, bot, conv, args, is_shazam)

        except asyncio.TimeoutError:
            await utils.answer(status, self.strings["error"].format("Таймаут"))
            try:
                await self._delete_bot_dialog(bot)
            except Exception:
                pass
        except Exception as e:
            await utils.answer(status, self.strings["error"].format(str(e)))
            try:
                await self._delete_bot_dialog(bot)
            except Exception:
                pass

    async def _process_tracks_response(self, resp, status, message, reply, bot, conv, args, is_shazam=False):
        tracks = []
        for row in resp.buttons:
            for btn in row:
                if hasattr(btn, "text") and btn.text:
                    t = btn.text.strip()
                    skip = ["❌", "Назад", "Вперед", "Больше", "🎵", ".", "Отмена", "Закрыть", "Добавить"]
                    if t and not any(s in t for s in skip):
                        tracks.append({"title": t, "btn": btn})

        if not tracks:
            # Возможно бот сразу скинул файл после шазама
            await utils.answer(status, self.strings["no_results"])
            await self._delete_bot_dialog(bot)
            return

        cid = f"{message.chat_id}_{message.id}"
        self.cache[cid] = {
            "tracks": tracks[:10],
            "conv": conv,
            "status": status,
            "orig": message,
            "reply": reply,
            "bot": bot,
            "args": args,
            "is_shazam": is_shazam,
        }

        buttons = []
        for i, t in enumerate(tracks[:10]):
            buttons.append([{
                "text": f"{i + 1}. {t['title'][:40]}",
                "callback": self._create_callback(cid, i),
            }])

        buttons.append([{
            "text": "❌ Отмена",
            "callback": self._create_cancel_callback(cid),
        }])

        await self.inline.form(
            text=self.strings["select_track"],
            message=status,
            reply_markup=buttons,
            ttl=300,
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
                    if hasattr(btn, "url") and btn.url:
                        try:
                            if "t.me/" in btn.url:
                                username = btn.url.split("t.me/")[-1].split("/")[0].split("?")[0]
                                if username:
                                    from telethon.tl.functions.channels import JoinChannelRequest
                                    await self.client(JoinChannelRequest(username))
                                    await asyncio.sleep(0.5)
                        except Exception:
                            pass

                # Заново отправляем запрос
                if c.get("is_shazam") and c.get("media"):
                    await c["conv"].send_file(c["media"])
                else:
                    await c["conv"].send_message(c["args"])

                resp = None
                for _ in range(20):
                    r = await c["conv"].get_response()
                    if r.text and any(e in r.text for e in ["⏳", "⌛", "Загрузка"]):
                        continue
                    if r.buttons:
                        resp = r
                        break
                    if r.media and (r.audio or r.document):
                        try:
                            await self.client.edit_message(c["status"], self.strings["uploading"])
                        except Exception:
                            pass
                        await self.client.send_file(
                            c["orig"].chat_id,
                            r.media,
                            reply_to=c["reply"].id if c["reply"] else c["orig"].id,
                        )
                        try:
                            await c["status"].delete()
                        except Exception:
                            pass
                        try:
                            await call.delete()
                        except Exception:
                            pass
                        await self._delete_bot_dialog(c["bot"])
                        self.cache.pop(cid, None)
                        return
                    await asyncio.sleep(0.4)

                if not resp:
                    await self.client.edit_message(c["status"], self.strings["no_results"])
                    await self._delete_bot_dialog(c["bot"])
                    return

                await call.delete()
                await self._process_tracks_response(
                    resp, c["status"], c["orig"], c["reply"], c["bot"], c["conv"], c["args"], c.get("is_shazam", False)
                )

            except Exception as e:
                await self.client.edit_message(c["status"], self.strings["error"].format(str(e)))
                await self._delete_bot_dialog(c["bot"])

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
                    {"text": "Отменить", "callback": self._create_cancel_callback(cid)},
                ]
            ]

            await call.edit(
                text=self.strings["ignore_warning"],
                reply_markup=buttons,
            )

        return handler

    def _create_confirm_ignore_callback(self, cid):
        async def handler(call):
            c = self.cache.get(cid)
            self.cache.pop(cid, None)
            await call.answer("❌ Отменено", alert=False)
            try:
                await call.edit(text=self.strings["ignored_text"])
            except Exception:
                pass
            if c:
                await self._delete_bot_dialog(c["bot"])

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
            except Exception:
                pass

            try:
                await track["btn"].click()
                await asyncio.sleep(1)

                audio_msg = None
                for _ in range(35):
                    await asyncio.sleep(0.5)
                    messages = await self.client.get_messages(c["bot"], limit=3)

                    for msg in messages:
                        if msg.media:
                            if msg.text and any(x in (msg.text or "") for x in ["Загрузка", "скачив", "⏳", "⌛"]):
                                try:
                                    await self.client.edit_message(c["status"], self.strings["waiting"])
                                except Exception:
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
                    except Exception:
                        pass

                    await self.client.send_file(
                        c["orig"].chat_id,
                        audio_msg.media,
                        reply_to=c["reply"].id if c["reply"] else c["orig"].id,
                    )

                    try:
                        await c["status"].delete()
                    except Exception:
                        pass

                    try:
                        await call.delete()
                    except Exception:
                        pass

                    # Полностью удаляем диалог с ботом — никаких следов
                    await self._delete_bot_dialog(c["bot"])
                else:
                    try:
                        await self.client.edit_message(c["status"], self.strings["error"].format("Файл не найден"))
                    except Exception:
                        pass
                    await self._delete_bot_dialog(c["bot"])

            except Exception as e:
                try:
                    await self.client.edit_message(c["status"], self.strings["error"].format(str(e)))
                except Exception:
                    pass
                await self._delete_bot_dialog(c["bot"])
            finally:
                self.cache.pop(cid, None)

        return handler

    def _create_cancel_callback(self, cid):
        async def handler(call):
            c = self.cache.get(cid)
            self.cache.pop(cid, None)
            await call.answer("🔴 Отмена", alert=False)
            try:
                await call.delete()
            except Exception:
                pass
            if c:
                await self._delete_bot_dialog(c["bot"])

        return handler
