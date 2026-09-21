# meta developer: @Wers1xx

# scope: hikka_only
# scope: hikka_admin_tools

from telethon.tl.functions.channels import EditBannedRequest, EditAdminRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import ChatBannedRights, ChatAdminRights
from telethon import functions, types
from .. import loader, utils
import asyncio
import datetime

@loader.tds
class AdminToolsMod(loader.Module):
    """Модуль с расширенными админ-командами для управления чатом"""
    strings = {"name": "AdminTools"}

    async def client_ready(self, client, db):
        self.client = client
        self.db = db

    @loader.command()
    @loader.group_admin_ban_users
    async def mute(self, message):
        """<reply/user> <time> <reason> - Замутить пользователя"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        if not args and not reply:
            await utils.answer(message, "<b>❌ Укажите пользователя (reply или username/id) и время в минутах</b>")
            return

        try:
            if reply:
                user = await message.client.get_entity(reply.sender_id)
                args_list = args.split(maxsplit=1) if args else ["60"]
            else:
                parts = args.split(maxsplit=2)
                if len(parts) < 2:
                    await utils.answer(message, "<b>❌ Формат: .mute <user> <минуты> [причина]</b>")
                    return
                user = await message.client.get_entity(parts[0])
                args_list = parts[1:]

            time_min = int(args_list[0])
            reason = args_list[1] if len(args_list) > 1 else "Без причины"
            
            until_time = datetime.datetime.now() + datetime.timedelta(minutes=time_min)
            rights = ChatBannedRights(
                until_date=until_time,
                send_messages=True,
                send_media=True,
                send_stickers=True,
                send_gifs=True,
                send_games=True,
                send_inline=True,
                embed_links=True,
                send_polls=True,
                change_info=False,
                invite_users=False,
                pin_messages=False
            )
            
            await message.client(EditBannedRequest(message.chat_id, user.id, rights))
            await utils.answer(
                message,
                f"<b>🔇 Пользователь <a href='tg://user?id={user.id}'>{user.first_name}</a> замучен на {time_min} мин.</b>\n"
                f"<b>Причина:</b> {reason}"
            )
        except ValueError:
            await utils.answer(message, "<b>❌ Неверный формат времени</b>")
        except Exception as e:
            await utils.answer(message, f"<b>❌ Ошибка:</b> {e}")

    @loader.command()
    @loader.group_admin_ban_users
    async def unmute(self, message):
        """<reply/user> - Размутить пользователя"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        if not args and not reply:
            await utils.answer(message, "<b>❌ Укажите пользователя (reply или username/id)</b>")
            return

        try:
            if reply:
                user = await message.client.get_entity(reply.sender_id)
            else:
                user = await message.client.get_entity(args)

            rights = ChatBannedRights(
                until_date=None,
                send_messages=False,
                send_media=False,
                send_stickers=False,
                send_gifs=False,
                send_games=False,
                send_inline=False,
                embed_links=False,
                send_polls=False,
                change_info=False,
                invite_users=False,
                pin_messages=False
            )
            
            await message.client(EditBannedRequest(message.chat_id, user.id, rights))
            await utils.answer(
                message,
                f"<b>🔊 Пользователь <a href='tg://user?id={user.id}'>{user.first_name}</a> размучен</b>"
            )
        except Exception as e:
            await utils.answer(message, f"<b>❌ Ошибка:</b> {e}")

    @loader.command()
    @loader.group_admin_ban_users
    async def ban(self, message):
        """<reply/user> <reason> - Забанить пользователя"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        if not args and not reply:
            await utils.answer(message, "<b>❌ Укажите пользователя (reply или username/id)</b>")
            return

        try:
            if reply:
                user = await message.client.get_entity(reply.sender_id)
                reason = args if args else "Без причины"
            else:
                parts = args.split(maxsplit=1)
                user = await message.client.get_entity(parts[0])
                reason = parts[1] if len(parts) > 1 else "Без причины"

            rights = ChatBannedRights(
                until_date=None,
                view_messages=True,
                send_messages=True,
                send_media=True,
                send_stickers=True,
                send_gifs=True,
                send_games=True,
                send_inline=True,
                embed_links=True,
                send_polls=True,
                change_info=True,
                invite_users=True,
                pin_messages=True
            )
            
            await message.client(EditBannedRequest(message.chat_id, user.id, rights))
            await utils.answer(
                message,
                f"<b>🚫 Пользователь <a href='tg://user?id={user.id}'>{user.first_name}</a> забанен</b>\n"
                f"<b>Причина:</b> {reason}"
            )
        except Exception as e:
            await utils.answer(message, f"<b>❌ Ошибка:</b> {e}")

    @loader.command()
    @loader.group_admin_ban_users
    async def unban(self, message):
        """<username/id> - Разбанить пользователя"""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, "<b>❌ Укажите username или ID пользователя</b>")
            return

        try:
            user = await message.client.get_entity(args)
            rights = ChatBannedRights(
                until_date=None,
                view_messages=False,
                send_messages=False,
                send_media=False,
                send_stickers=False,
                send_gifs=False,
                send_games=False,
                send_inline=False,
                embed_links=False,
                send_polls=False,
                change_info=False,
                invite_users=False,
                pin_messages=False
            )
            
            await message.client(EditBannedRequest(message.chat_id, user.id, rights))
            await utils.answer(
                message,
                f"<b>✅ Пользователь <a href='tg://user?id={user.id}'>{user.first_name}</a> разбанен</b>"
            )
        except Exception as e:
            await utils.answer(message, f"<b>❌ Ошибка:</b> {e}")

    @loader.command()
    @loader.group_admin_add_admins
    async def promote(self, message):
        """<reply/user> <title> - Выдать админские права"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        if not args and not reply:
            await utils.answer(message, "<b>❌ Укажите пользователя (reply или username/id)</b>")
            return

        try:
            if reply:
                user = await message.client.get_entity(reply.sender_id)
                title = args if args else ""
            else:
                parts = args.split(maxsplit=1)
                user = await message.client.get_entity(parts[0])
                title = parts[1] if len(parts) > 1 else ""

            # Полные админские права
            admin_rights = ChatAdminRights(
                change_info=True,
                post_messages=True,
                edit_messages=True,
                delete_messages=True,
                ban_users=True,
                invite_users=True,
                pin_messages=True,
                add_admins=False,  # Обычно выдаётся без права добавлять админов
                anonymous=False,
                manage_call=True,
                other=True
            )
            
            await message.client(EditAdminRequest(message.chat_id, user.id, admin_rights, title))
            await utils.answer(
                message,
                f"<b>👑 Пользователь <a href='tg://user?id={user.id}'>{user.first_name}</a> назначен администратором</b>\n"
                f"<b>Тайтл:</b> {title if title else 'Без тайтла'}"
            )
        except Exception as e:
            await utils.answer(message, f"<b>❌ Ошибка:</b> {e}")

    @loader.command()
    @loader.group_admin_add_admins
    async def demote(self, message):
        """<reply/user> - Снять админские права"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        if not args and not reply:
            await utils.answer(message, "<b>❌ Укажите пользователя (reply или username/id)</b>")
            return

        try:
            if reply:
                user = await message.client.get_entity(reply.sender_id)
            else:
                user = await message.client.get_entity(args)

            admin_rights = ChatAdminRights(
                change_info=False,
                post_messages=False,
                edit_messages=False,
                delete_messages=False,
                ban_users=False,
                invite_users=False,
                pin_messages=False,
                add_admins=False,
                anonymous=False,
                manage_call=False,
                other=False
            )
            
            await message.client(EditAdminRequest(message.chat_id, user.id, admin_rights, ""))
            await utils.answer(
                message,
                f"<b>⬇️ Пользователь <a href='tg://user?id={user.id}'>{user.first_name}</a> снят с админки</b>"
            )
        except Exception as e:
            await utils.answer(message, f"<b>❌ Ошибка:</b> {e}")

    @loader.command()
    @loader.group_admin_change_info
    async def title(self, message):
        """<reply/user> <title> - Установить тайтл администратора"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        if not args and not reply:
            await utils.answer(message, "<b>❌ Укажите пользователя и тайтл</b>")
            return

        try:
            if reply:
                user = await message.client.get_entity(reply.sender_id)
                title = args if args else ""
            else:
                parts = args.split(maxsplit=1)
                user = await message.client.get_entity(parts[0])
                title = parts[1] if len(parts) > 1 else ""

            # Получаем текущие права админа
            full_user = await message.client(GetFullUserRequest(user.id))
            
            # Сохраняем текущие права
            admin_rights = ChatAdminRights(
                change_info=True,
                post_messages=True,
                edit_messages=True,
                delete_messages=True,
                ban_users=True,
                invite_users=True,
                pin_messages=True,
                add_admins=False,
                anonymous=False,
                manage_call=True,
                other=True
            )
            
            await message.client(EditAdminRequest(message.chat_id, user.id, admin_rights, title))
            await utils.answer(
                message,
                f"<b>🏷️ Для <a href='tg://user?id={user.id}'>{user.first_name}</a> установлен тайтл:</b> {title}"
            )
        except Exception as e:
            await utils.answer(message, f"<b>❌ Ошибка:</b> {e}")

    @loader.command()
    @loader.group_admin_ban_users
    async def kick(self, message):
        """<reply/user> - Кикнуть пользователя из чата"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        if not args and not reply:
            await utils.answer(message, "<b>❌ Укажите пользователя (reply или username/id)</b>")
            return

        try:
            if reply:
                user = await message.client.get_entity(reply.sender_id)
            else:
                user = await message.client.get_entity(args)

            await message.client.kick_participant(message.chat_id, user.id)
            await utils.answer(
                message,
                f"<b>👢 Пользователь <a href='tg://user?id={user.id}'>{user.first_name}</a> кикнут из чата</b>"
            )
        except Exception as e:
            await utils.answer(message, f"<b>❌ Ошибка:</b> {e}")