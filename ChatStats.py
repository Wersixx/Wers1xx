# meta developer: @Wers1xx

from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.messages import GetCommonChatsRequest
from telethon.tl.types import InputMessagesFilterEmpty
from telethon.errors import ChatAdminRequiredError, FloodWaitError
from telethon.utils import get_display_name
from hikkatl.types import Message
from .. import loader, utils
import asyncio
from datetime import datetime
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

@loader.tds
class ChatStatsMod(loader.Module):
    """Считает сообщения и показывает информацию о пользователях"""

    strings = {"name": "ChatStats"}

    async def statscmd(self, message: Message):
        """Показывает количество сообщений в текущем чате от каждого участника."""
        chat_id = message.chat_id
        
        args = utils.get_args_raw(message)
        limit = None
        if args:
            try:
                limit = int(args)
            except ValueError:
                await utils.answer(message, "<emoji document_id=5210952531676504517>❌</emoji> Укажите число для лимита сообщений.")
                return

        status_msg = await utils.answer(message, f"<emoji document_id=5116468787377341336>💬</emoji> Анализирую сообщения...\n{'<emoji document_id=6035084557378654059>👤</emoji> Личный чат' if message.is_private else '<emoji document_id=6032609071373226027>👥</emoji> Групповой чат'}")

        users_msg_count = defaultdict(int)
        users_cache = {}
        
        try:
            async for msg in message.client.iter_messages(chat_id, limit=limit):
                if msg.sender_id:
                    users_msg_count[msg.sender_id] += 1
                    if msg.sender_id not in users_cache and msg.sender:
                        users_cache[msg.sender_id] = msg.sender
        except FloodWaitError as e:
            await utils.answer(message, f"<emoji document_id=5210952531676504517>❌</emoji> Флуд-контроль: ждите {e.seconds}с")
            return

        if not users_msg_count:
            await utils.answer(message, "<emoji document_id=5210952531676504517>❌</emoji> Не найдено сообщений.")
            return

        if not message.is_private and len(users_cache) < 30:
            try:
                participants = await message.client.get_participants(chat_id, limit=100)
                for p in participants:
                    if p.id not in users_cache:
                        users_cache[p.id] = p
            except:
                pass

        sorted_users = sorted(users_msg_count.items(), key=lambda x: x[1], reverse=True)
        
        response = (
            f"<emoji document_id=5116240346656801621>❓</emoji> <b>Статистика сообщений</b>\n"
            f"<emoji document_id=4904845878868575100>😇</emoji> <b>{'Личный чат' if message.is_private else 'Группа'}</b>\n"
            f"<emoji document_id=5105344272324887540>😐</emoji> <b>Проанализировано</b>: {sum(users_msg_count.values())} сообщений\n\n"
        )

        for user_id, count in sorted_users[:30]:
            user = users_cache.get(user_id)
            if not user:
                try:
                    user = await message.client.get_entity(user_id)
                    users_cache[user_id] = user
                except:
                    pass
            
            if user:
                username = f"@{user.username}" if user.username else ""
                name = get_display_name(user)
                display = f"{name} ({username})" if username else name
            else:
                display = f"ID{user_id}"
            
            response += f"<emoji document_id=5258011929993026890>👤</emoji> {display}: {count} сообщ.\n"

        if len(sorted_users) > 30:
            response += f"\n<emoji document_id=5253836448687204081>📌</emoji> Показаны топ-30 из {len(sorted_users)} участников"

        await status_msg.edit(response)

    async def uinfocmd(self, message: Message):
        """Показывает детальную информацию о пользователе."""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        user = None
        if reply:
            user = await message.client.get_entity(reply.sender_id)
        elif args:
            try:
                user = await message.client.get_entity(args)
            except Exception as e:
                await utils.answer(message, f"<emoji document_id=5210952531676504517>❌</emoji> Не удалось найти пользователя: {e}")
                return
        else:
            await utils.answer(message, "<emoji document_id=5210952531676504517>❌</emoji> Ответьте на сообщение или укажите @username/ID.")
            return

        status_msg = await utils.answer(message, "<emoji document_id=5116468787377341336>💬</emoji> Собираю информацию...")

        try:
            full_user = await message.client(GetFullUserRequest(user))
        except Exception as e:
            await status_msg.edit(f"<emoji document_id=5210952531676504517>❌</emoji> Ошибка получения данных: {e}")
            return

        # Получаем аватарку
        avatar = None
        try:
            user_photos = await message.client.get_profile_photos(user, limit=1)
            if user_photos:
                avatar = user_photos[0]
        except:
            pass

        # ---- Базовые данные ----
        first_name = user.first_name or "Нет"
        last_name = user.last_name or "Нет"
        user_id = user.id
        bio = full_user.full_user.about or "Нет"

        # ---- Имена пользователей (все возможные) ----
        usernames = []
        if user.username:
            usernames.append(f"@{user.username}")
        if hasattr(full_user.full_user, 'usernames') and full_user.full_user.usernames:
            for u in full_user.full_user.usernames:
                if u != user.username:
                    usernames.append(f"@{u}")
        usernames_display = ", ".join(usernames) if usernames else "Нет"

        # ---- ЭМОДЗИ СТАТУС (максимально агрессивный поиск) ----
        emoji_status = "Нет"
        try:
            fu = full_user.full_user
            
            # 1. Проверяем user.emoji_status
            if hasattr(user, 'emoji_status') and user.emoji_status:
                val = user.emoji_status
                if isinstance(val, str):
                    emoji_status = val
                elif hasattr(val, 'document_id'):
                    emoji_status = f"<emoji document_id={val.document_id}>🌙</emoji>"
                elif hasattr(val, 'emoji'):
                    emoji_status = val.emoji
                else:
                    emoji_status = str(val)
            
            # 2. Проверяем full_user.user.emoji_status
            if emoji_status == "Нет" and hasattr(full_user, 'user') and hasattr(full_user.user, 'emoji_status'):
                val = full_user.user.emoji_status
                if val:
                    if isinstance(val, str):
                        emoji_status = val
                    elif hasattr(val, 'document_id'):
                        emoji_status = f"<emoji document_id={val.document_id}>🌙</emoji>"
                    elif hasattr(val, 'emoji'):
                        emoji_status = val.emoji
                    else:
                        emoji_status = str(val)
            
            # 3. Проверяем fu.emoji_status
            if emoji_status == "Нет" and hasattr(fu, 'emoji_status') and fu.emoji_status:
                val = fu.emoji_status
                if isinstance(val, str):
                    emoji_status = val
                elif hasattr(val, 'document_id'):
                    emoji_status = f"<emoji document_id={val.document_id}>🌙</emoji>"
                elif hasattr(val, 'emoji'):
                    emoji_status = val.emoji
                else:
                    emoji_status = str(val)
            
            # 4. Проверяем fu.status
            if emoji_status == "Нет" and hasattr(fu, 'status') and fu.status:
                val = fu.status
                if hasattr(val, 'emoji') and val.emoji:
                    emoji_status = val.emoji
                elif hasattr(val, 'document_id'):
                    emoji_status = f"<emoji document_id={val.document_id}>🌙</emoji>"
            
            # 5. Проверяем возможные поля в __dict__
            if emoji_status == "Нет" and hasattr(fu, '__dict__'):
                d = fu.__dict__
                possible_fields = ['emoji_status', 'status', 'emoji', 'status_emoji', 'emoji_status_document_id', 'status_document_id']
                for field in possible_fields:
                    if field in d and d[field]:
                        val = d[field]
                        if isinstance(val, str):
                            emoji_status = val
                            break
                        elif hasattr(val, 'document_id'):
                            emoji_status = f"<emoji document_id={val.document_id}>🌙</emoji>"
                            break
                        elif hasattr(val, 'emoji'):
                            emoji_status = val.emoji
                            break
            
            # 6. Если всё ещё Нет, логируем атрибуты для отладки
            if emoji_status == "Нет":
                logger.debug(f"Не удалось найти эмодзи-статус. Доступные атрибуты fu: {dir(fu)}")
                if hasattr(fu, '__dict__'):
                    logger.debug(f"__dict__ fu: {fu.__dict__}")
        except Exception as e:
            logger.error(f"Ошибка получения эмодзи-статуса: {e}")

        # ---- ЛИЧНЫЙ КАНАЛ ----
        personal_channel = "Нет"
        try:
            fu = full_user.full_user
            if hasattr(fu, 'personal_channel') and fu.personal_channel:
                channel = fu.personal_channel
                if channel.username:
                    personal_channel = f'<a href="https://t.me/{channel.username}"><b>{channel.title or "Канал"}</b></a>'
                else:
                    personal_channel = channel.title or "Канал"
            elif hasattr(fu, 'personal_channel_id') and fu.personal_channel_id:
                try:
                    channel_entity = await message.client.get_entity(fu.personal_channel_id)
                    if channel_entity.username:
                        personal_channel = f'<a href="https://t.me/{channel_entity.username}"><b>{channel_entity.title or "Канал"}</b></a>'
                    else:
                        personal_channel = channel_entity.title or "Канал"
                except:
                    pass
        except:
            pass

        # ---- ДЕНЬ РОЖДЕНИЯ ----
        birthday = "Не указан"
        try:
            if hasattr(full_user.full_user, 'birthday') and full_user.full_user.birthday:
                bd = full_user.full_user.birthday
                birthday = f"{bd.day}.{bd.month}." + (f"{bd.year}" if hasattr(bd, 'year') and bd.year else "")
        except:
            pass

        # ---- КОЛИЧЕСТВО ПОДАРКОВ ----
        gifts_count = 0
        try:
            fu = full_user.full_user
            if hasattr(fu, 'stargifts_count') and fu.stargifts_count is not None:
                gifts_count = fu.stargifts_count
            elif hasattr(fu, 'gifts_count') and fu.gifts_count is not None:
                gifts_count = fu.gifts_count
            elif hasattr(fu, 'gift_count') and fu.gift_count is not None:
                gifts_count = fu.gift_count
            elif hasattr(fu, 'stars') and fu.stars is not None:
                gifts_count = fu.stars
            elif hasattr(fu, 'gifts') and fu.gifts:
                gifts_count = len(fu.gifts)
            elif hasattr(fu, 'gift_info') and fu.gift_info:
                gifts_count = getattr(fu.gift_info, 'count', 0)
        except:
            pass

        # ---- ПРЕМИУМ ----
        is_premium = "Нет"
        try:
            fu = full_user.full_user
            if hasattr(fu, 'premium') and fu.premium:
                is_premium = "Да"
            elif hasattr(user, 'premium') and user.premium:
                is_premium = "Да"
            elif hasattr(fu, 'flags') and (fu.flags & 4):
                is_premium = "Да"
        except:
            pass

        # ---- БОТ ----
        is_bot = "<emoji document_id=5255772095958229697>🤚</emoji> Нет" if not user.bot else "<emoji document_id=5255813619702049821>✅</emoji> Да"

        # ---- ВЕРИФИКАЦИЯ ----
        is_verified = "<emoji document_id=5255772095958229697>🤚</emoji> Нет" if not getattr(user, 'verified', False) else "<emoji document_id=5255813619702049821>✅</emoji> Да"

        # ---- ОБЩИЕ ЧАТЫ ----
        common_chats_count = 0
        common_chats_list = []
        try:
            common_chats = await message.client(GetCommonChatsRequest(
                user_id=user.id,
                max_id=0,
                limit=100
            ))
            if common_chats and common_chats.chats:
                common_chats_count = len(common_chats.chats)
                for chat in common_chats.chats[:5]:
                    if chat.username:
                        common_chats_list.append(f'<a href="https://t.me/{chat.username}"><b>{chat.title or "Чат"}</b></a>')
                    else:
                        common_chats_list.append(f'<b>{chat.title or "Чат"}</b>')
        except Exception as e:
            logger.error(f"GetCommonChatsRequest error: {e}")
            try:
                common_chats = await message.client.get_common_chats(user)
                if common_chats:
                    common_chats_count = len(common_chats)
                    for chat in common_chats[:5]:
                        if chat.username:
                            common_chats_list.append(f'<a href="https://t.me/{chat.username}"><b>{chat.title or "Чат"}</b></a>')
                        else:
                            common_chats_list.append(f'<b>{chat.title or "Чат"}</b>')
            except Exception as e2:
                logger.error(f"get_common_chats error: {e2}")

        # ---- РАБОЧИЕ ЧАСЫ ----
        business_work_hours = "Нет"
        try:
            fu = full_user.full_user
            if hasattr(fu, 'business_work_hours') and fu.business_work_hours:
                work_hours = fu.business_work_hours
                if hasattr(work_hours, 'weekly_open') and work_hours.weekly_open:
                    weekdays = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
                    hours = []
                    for item in work_hours.weekly_open:
                        day_index = item.start_minute // (24 * 60)
                        if day_index < 7:
                            day = weekdays[day_index]
                            start_h = item.start_minute // 60
                            start_m = item.start_minute % 60
                            end_h = item.end_minute // 60
                            end_m = item.end_minute % 60
                            hours.append(f"{day}: {start_h:02d}:{start_m:02d} - {end_h:02d}:{end_m:02d}")
                    if hours:
                        business_work_hours = ", ".join(hours)
        except:
            pass

        # ---- ДАТА РЕГИСТРАЦИИ ----
        registration_date = "Недоступно"
        try:
            if hasattr(full_user.full_user, 'date') and full_user.full_user.date:
                registration_date = full_user.full_user.date.strftime("%d.%m.%Y %H:%M:%S")
            elif user.id > 0:
                reg_timestamp = (user.id >> 32) + 1136073600
                registration_date = datetime.fromtimestamp(reg_timestamp).strftime("%d.%m.%Y %H:%M:%S")
        except:
            pass

        # ---- ФОРМИРУЕМ ОТВЕТ ----
        response = (
            f"<blockquote>"
            f"<emoji document_id=5985457743576698865>#️⃣</emoji><b> ID: </b><code>{user_id}</code>\n"
            f"<emoji document_id=5408849420491962048>🔥</emoji><b> Имя: </b>{first_name}\n"
            f"<emoji document_id=5408849420491962048>🔥</emoji><b> Фамилия: </b>{last_name}\n"
            f"<emoji document_id=5364052602357044385>🐶</emoji><b> Имена пользователей: </b>{usernames_display}\n"
            f"</blockquote>\n"
            f"<blockquote>"
            f"<emoji document_id=5985616786215669454>ℹ️</emoji><b> О себе: </b>{bio}\n"
            f"</blockquote>\n"
            f"<blockquote>"
            f"<emoji document_id=5408892365869952851>❤️</emoji><b> Статус с эмодзи: </b>{emoji_status}\n"
            f"</blockquote>"
            f"<blockquote>"
            f"<emoji document_id=5409331062419502443>🔉</emoji><b> Личный канал: </b>{personal_channel}\n"
            f"<emoji document_id=6024041612345088787>🎂</emoji><b> День рождения: </b>{birthday}\n"
            f"<emoji document_id=6037175527846975726>🎁</emoji><b> Количество подарков: </b>{gifts_count}\n"
            f"</blockquote>"
            f"<blockquote>"
            f"<emoji document_id=5208842667647061916>🚨</emoji><b> Количество общих чатов: </b>{common_chats_count}\n"
        )
        
        if common_chats_list:
            response += f"<emoji document_id=5985401861757210746>👥</emoji><b> Общие чаты: </b>{', '.join(common_chats_list)}\n"
        
        response += (
            f"</blockquote>"
            f"<blockquote>"
            f"<emoji document_id=5258093637450866522>🤖</emoji><b> Бот: </b>{is_bot}\n"
            f"<emoji document_id=5357069174512303778>✅</emoji><b> Верифицирован: </b>{is_verified}\n"
            f"<emoji document_id=5258165702707125574>⭐️</emoji><b> Премиум: </b>{is_premium}\n"
            f"<emoji document_id=5258330865674494479>🍑</emoji><b> Дата регистрации: </b>{registration_date}\n"
            f"<emoji document_id=5408910404732595664>🕐</emoji><b> Рабочие часы: </b>{business_work_hours}"
            f"</blockquote>"
        )

        # Отправляем с аватаркой
        if avatar:
            await message.client.send_file(
                message.chat_id,
                avatar,
                caption=response,
                reply_to=message.id,
                parse_mode='html'
            )
            await status_msg.delete()
        else:
            await status_msg.edit(response)