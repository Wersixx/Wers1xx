# requires: Pillow
# meta developer: @H_SunMods, @WersModules
# meta pic: https://r2.fakecrime.bio/uploads/47308ab9-6035-4e7d-bc96-6b58f864bb33.jpg
# meta banner: https://r2.fakecrime.bio/uploads/47308ab9-6035-4e7d-bc96-6b58f864bb33.jpg
# meta fhsdesc: Theme, Темы, Sunnex, SunnexGB, H_SunMods, Wersixx, Wers1xx, WersModules

import io
import logging
from PIL import Image
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class tgtheme(loader.Module):
    """Module that creates an android-theme from a photo with smart per-element color calculation"""

    strings = {
        "name": "TgTheme",
        "no_photo": "<b>Reply to a photo</b>",
        "processing": "<b>🎨 Creating smart theme...</b>",
        "done": "<b>✨ Theme ready!</b>\n<b>🎭 Type:</b> {}\n<b>🔹 Transparency:</b> {}%\n<b>💬 Text:</b> {}\n<b>🎨 Colors:</b> {} extracted",
        "error": "<b>❌ Error:</b> {}",
    }

    strings_ru = {
        "_cls_doc": "Модуль который создаёт тг-тему по фото с умным подбором цвета для каждой детали",
        "no_photo": "<b>Ответьте на фото</b>",
        "processing": "<b>🎨 Создаю умную тему...</b>",
        "done": "<b>✨ Тема готова!</b>\n<b>🎭 Тип:</b> {}\n<b>🔹 Прозрачность:</b> {}%\n<b>💬 Текст:</b> {}\n<b>🎨 Цветов:</b> {} извлечено",
        "error": "<b>❌ Ошибка:</b> {}",
    }

    # ==================== УМНАЯ ЦВЕТОВАЯ БИБЛИОТЕКА ====================

    def _rgb(self, h):
        """HEX → (r, g, b)"""
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def _hex(self, r, g, b):
        """(r, g, b) → HEX"""
        return f"{max(0, min(255, int(r))):02x}{max(0, min(255, int(g))):02x}{max(0, min(255, int(b))):02x}"

    def _brightness(self, h):
        """Яркость цвета (0-255)"""
        r, g, b = self._rgb(h)
        return r * 0.299 + g * 0.587 + b * 0.114

    def _saturation(self, h):
        """Насыщенность (0-1)"""
        r, g, b = [x / 255 for x in self._rgb(h)]
        mx, mn = max(r, g, b), min(r, g, b)
        if mx == 0:
            return 0
        return (mx - mn) / mx

    def _darken(self, h, factor=0.7):
        """Затемняет цвет"""
        r, g, b = self._rgb(h)
        return self._hex(r * factor, g * factor, b * factor)

    def _lighten(self, h, factor=0.3):
        """Осветляет цвет (смешивает с белым)"""
        r, g, b = self._rgb(h)
        return self._hex(r + (255 - r) * factor, g + (255 - g) * factor, b + (255 - b) * factor)

    def _blend(self, h1, h2, ratio=0.5):
        """Смешивает два цвета"""
        r1, g1, b1 = self._rgb(h1)
        r2, g2, b2 = self._rgb(h2)
        return self._hex(
            r1 * (1 - ratio) + r2 * ratio,
            g1 * (1 - ratio) + g2 * ratio,
            b1 * (1 - ratio) + b2 * ratio
        )

    def _contrast(self, h, dark="1a1a1a", light="f5f5f5"):
        """Возвращает контрастный цвет (тёмный или светлый)"""
        return light if self._brightness(h) < 140 else dark

    def _adjust_for_bg(self, color, bg, min_diff=45):
        """Если цвет слишком похож на фон — корректирует его"""
        if abs(self._brightness(color) - self._brightness(bg)) < min_diff:
            if self._brightness(bg) > 140:
                return self._darken(color, 0.55)
            else:
                return self._lighten(color, 0.45)
        return color

    def _extract_palette(self, img, count=12):
        """Извлекает богатую палитру + сортирует по яркости и насыщенности"""
        small = img.copy().convert("RGB")
        if max(small.size) > 220:
            scale = 220 / max(small.size)
            small = small.resize(
                (int(small.size[0] * scale), int(small.size[1] * scale)),
                Image.LANCZOS,
            )

        buckets = {}
        for r, g, b in small.getdata():
            # Более точная квантизация
            key = (r >> 3, g >> 3, b >> 3)
            if key not in buckets:
                buckets[key] = [r, g, b, 1]
            else:
                buckets[key][0] += r
                buckets[key][1] += g
                buckets[key][2] += b
                buckets[key][3] += 1

        top = sorted(buckets.values(), key=lambda x: x[3], reverse=True)
        colors = []
        for sr, sg, sb, c in top[:count * 2]:  # берём с запасом
            hex_c = self._hex(sr // c, sg // c, sb // c)
            # Фильтруем слишком похожие цвета
            if all(abs(self._brightness(hex_c) - self._brightness(ex)) > 18 or
                   abs(self._saturation(hex_c) - self._saturation(ex)) > 0.12
                   for ex in colors):
                colors.append(hex_c)
            if len(colors) >= count:
                break

        # Сортируем: сначала по яркости, потом по насыщенности
        colors = sorted(colors, key=lambda h: (self._brightness(h), self._saturation(h)))
        return colors

    def _build_smart_palette(self, colors):
        """Строит умную палитру для всех элементов темы"""
        if not colors:
            colors = ["1a1a1a", "888888", "ffffff"]

        # Основной фон (самый частотный / средний по яркости)
        mid = len(colors) // 2
        bg = colors[mid] if colors else "1e1e1e"

        # Определяем тёмная/светлая тема
        is_dark = self._brightness(bg) < 145

        # Текст основной
        text = "f0f0f0" if is_dark else "1a1a1a"
        subtext = "b0b0b0" if is_dark else "555555"

        # Акценты — самые насыщенные цвета
        saturated = sorted(colors, key=self._saturation, reverse=True)
        accent = saturated[0] if saturated else ("6ba3ff" if is_dark else "2b6cb0")
        accent = self._adjust_for_bg(accent, bg)

        # Второй акцент (чуть другой оттенок)
        accent2 = saturated[1] if len(saturated) > 1 else self._blend(accent, "ffffff" if is_dark else "000000", 0.25)
        accent2 = self._adjust_for_bg(accent2, bg)

        # Третий акцент
        accent3 = saturated[2] if len(saturated) > 2 else self._blend(accent, accent2, 0.5)

        # Бабблы
        if is_dark:
            in_bubble = self._lighten(bg, 0.08)          # входящие чуть светлее фона
            out_bubble = self._blend(accent, bg, 0.35)   # исходящие с акцентом
        else:
            in_bubble = self._darken(bg, 0.92)
            out_bubble = self._blend(accent, "ffffff", 0.25)

        in_bubble = self._adjust_for_bg(in_bubble, bg, 25)
        out_bubble = self._adjust_for_bg(out_bubble, bg, 30)

        # Панели и action bar
        action_bar = self._darken(bg, 0.85) if is_dark else self._lighten(bg, 0.12)
        panel = self._blend(bg, accent, 0.08)

        # Ссылки
        link = self._lighten(accent, 0.25) if is_dark else self._darken(accent, 0.75)
        link = self._adjust_for_bg(link, bg, 50)

        # Разделители / тени
        divider = self._blend(bg, text, 0.18)
        shadow = "000000" if is_dark else "ffffff"

        # Плеер / диалоги (плотный фон)
        solid = bg

        # Цвета для голосовых, прогресса и т.д.
        seek_fill = accent if is_dark else self._darken(accent, 0.8)
        seek_bg = self._blend(bg, text, 0.25)

        # Реплаи / цитаты
        reply_line = accent2
        reply_bg = f"28{text}" if is_dark else f"18{text}"  # полупрозрачный

        # Иконки
        icon = text
        icon_active = accent

        return {
            "bg": bg,
            "text": text,
            "subtext": subtext,
            "accent": accent,
            "accent2": accent2,
            "accent3": accent3,
            "in_bubble": in_bubble,
            "out_bubble": out_bubble,
            "action_bar": action_bar,
            "panel": panel,
            "link": link,
            "divider": divider,
            "shadow": shadow,
            "solid": solid,
            "seek_fill": seek_fill,
            "seek_bg": seek_bg,
            "reply_line": reply_line,
            "reply_bg": reply_bg,
            "icon": icon,
            "icon_active": icon_active,
            "is_dark": is_dark,
            "palette_size": len(colors),
        }

    def _theme_wallpaper(self, img, max_size=1920):
        """Создаёт обои из изображения"""
        output = io.BytesIO()
        img_copy = img.copy()
        if img_copy.mode != 'RGB':
            img_copy = img_copy.convert('RGB')
        if max(img_copy.size) > max_size:
            scale = max_size / max(img_copy.size)
            img_copy = img_copy.resize(
                (int(img_copy.size[0] * scale), int(img_copy.size[1] * scale)),
                Image.LANCZOS
            )
        img_copy.save(output, format='JPEG', quality=88, optimize=True)
        return output.getvalue()

    def _build_theme(self, p, alpha="e6"):
        """Строит тему, используя умную палитру для каждой детали"""
        a = alpha  # прозрачность для фонов

        def c(key, force_alpha=None):
            """Быстрый хелпер: цвет из палитры + альфа"""
            col = p[key]
            al = force_alpha if force_alpha is not None else a
            return f"#{al}{col}"

        def solid(key):
            return f"#ff{p[key]}"

        def plain(key):
            return f"#{p[key]}"

        # Выбранный цвет для selection
        dsel = f"#ff{self._blend(p['bg'], p['accent'], 0.28)}"

        theme = f"""actionBarActionModeDefault={c('action_bar')}
actionBarActionModeDefaultIcon={plain('text')}
actionBarActionModeDefaultSelector={plain('accent')}
actionBarActionModeDefaultTop={plain('accent')}
actionBarActionModeReaction={plain('accent')}
actionBarActionModeReactionText={plain('text')}
actionBarActionModeReactionDot={plain('text')}
actionBarBrowser={plain('accent')}
actionBarDefault={c('action_bar')}
actionBarDefaultArchived={plain('accent2')}
actionBarDefaultArchivedIcon={plain('text')}
actionBarDefaultArchivedSearch={plain('accent')}
actionBarDefaultArchivedSelector={plain('accent')}
actionBarDefaultArchivedTitle={plain('text')}
actionBarDefaultIcon={plain('text')}
actionBarDefaultSearch={plain('accent')}
actionBarDefaultSearchArchivedPlaceholder={plain('subtext')}
actionBarDefaultSearchPlaceholder={plain('subtext')}
actionBarDefaultSelector={plain('accent')}
actionBarDefaultSubmenuBackground={c('bg')}
actionBarDefaultSubmenuItem={plain('text')}
actionBarDefaultSubmenuItemIcon={plain('text')}
actionBarDefaultSubmenuSeparator={plain('divider')}
actionBarDefaultSubtitle={plain('subtext')}
actionBarDefaultTitle={plain('text')}
actionBarTabActiveText={plain('accent')}
actionBarTabLine={plain('accent')}
actionBarTabSelector={plain('accent')}
actionBarTabUnactiveText={plain('subtext')}
actionBarWhiteSelector={plain('accent')}
avatar_actionBarIconBlue={plain('text')}
avatar_actionBarSelectorBlue={plain('accent')}
avatar_backgroundActionBarBlue={plain('accent')}
avatar_backgroundArchived={plain('accent2')}
avatar_backgroundArchivedHidden={plain('accent3')}
avatar_backgroundBlue={plain('accent')}
avatar_backgroundCyan={plain('accent2')}
avatar_backgroundGreen={plain('accent3')}
avatar_backgroundInProfileBlue={plain('text')}
avatar_backgroundOrange={plain('accent')}
avatar_backgroundPink={plain('accent2')}
avatar_backgroundRed={plain('accent3')}
avatar_backgroundSaved={plain('accent')}
avatar_backgroundViolet={plain('accent2')}
avatar_background2Blue={plain('accent')}
avatar_background2Cyan={plain('accent2')}
avatar_background2Green={plain('accent3')}
avatar_background2Orange={plain('accent')}
avatar_background2Pink={plain('accent2')}
avatar_background2Red={plain('accent3')}
avatar_background2Saved={plain('accent')}
avatar_background2Violet={plain('accent2')}
avatar_nameInMessageBlue={plain('accent')}
avatar_nameInMessageCyan={plain('accent2')}
avatar_nameInMessageGreen={plain('accent3')}
avatar_nameInMessageOrange={plain('accent')}
avatar_nameInMessagePink={plain('accent2')}
avatar_nameInMessageRed={plain('accent3')}
avatar_nameInMessageViolet={plain('accent2')}
avatar_subtitleInProfileBlue={plain('subtext')}
avatar_text={c('bg')}
bot_loadingIcon={plain('text')}
calls_callReceivedGreenIcon={plain('accent')}
calls_callReceivedRedIcon={plain('text')}
changephoneinfo_image2={plain('text')}
chats_actionBackground={plain('accent')}
chats_actionIcon={c('bg')}
chats_actionMessage={plain('accent')}
chats_actionPressedBackground={plain('accent2')}
chats_archiveBackground={plain('accent2')}
chats_archiveIcon={c('bg')}
chats_archivePinBackground={plain('accent')}
chats_archivePullDownBackground={plain('accent')}
chats_archivePullDownBackgroundActive={plain('accent2')}
chats_archiveText={c('bg')}
chats_attachMessage={plain('accent')}
chats_date={plain('subtext')}
chats_draft={plain('accent')}
chats_mentionIcon={c('bg')}
chats_menuBackground={c('bg')}
chats_menuItemCheck={plain('text')}
chats_menuItemIcon={plain('text')}
chats_menuItemText={plain('text')}
chats_menuName={plain('accent')}
chats_menuPhone={plain('subtext')}
chats_menuPhoneCats={plain('subtext')}
chats_menuTopBackground={plain('accent')}
chats_menuTopBackgroundCats={plain('accent2')}
chats_menuTopShadow=#00000000
chats_menuTopShadowCats=#00000000
chats_message={plain('text')}
chats_messageArchived={plain('subtext')}
chats_message_threeLines={plain('text')}
chats_muteIcon={plain('subtext')}
chats_name={plain('text')}
chats_nameArchived={plain('subtext')}
chats_nameMessage={plain('accent')}
chats_nameMessageArchived={plain('accent2')}
chats_nameMessageArchived_threeLines={plain('accent2')}
chats_nameMessage_threeLines={plain('accent')}
chats_onlineCircle={plain('accent')}
chats_pinnedIcon={plain('text')}
chats_pinnedOverlay=#00000000
chats_secretIcon={plain('accent')}
chats_secretName={plain('accent')}
chats_sentCheck={plain('accent')}
chats_sentClock={plain('subtext')}
chats_sentError={plain('text')}
chats_sentErrorIcon={c('bg')}
chats_sentReadCheck={plain('accent')}
chats_tabUnreadActiveBackground={plain('accent')}
chats_tabUnreadUnactiveBackground={plain('accent2')}
chats_tabletSelectedOverlay=#00000000
chats_unreadCounter={plain('accent')}
chats_unreadCounterMuted={plain('subtext')}
chats_unreadCounterText={c('bg')}
chats_verifiedBackground={plain('accent')}
chats_verifiedCheck={c('bg')}
chat_addContact={plain('accent')}
chat_adminSelectedText={plain('text')}
chat_adminText={plain('subtext')}
chat_attachActiveTab={plain('accent')}
chat_attachAudioBackground={plain('accent')}
chat_attachAudioText={c('bg')}
chat_attachCheckBoxBackground={plain('accent')}
chat_attachCheckBoxCheck={c('bg')}
chat_attachContactBackground={plain('accent2')}
chat_attachContactText={c('bg')}
chat_attachEmptyImage={plain('text')}
chat_attachFileBackground={plain('accent3')}
chat_attachFileText={c('bg')}
chat_attachGalleryBackground={plain('accent')}
chat_attachGalleryText={c('bg')}
chat_attachIcon={c('bg')}
chat_attachLocationBackground={plain('accent2')}
chat_attachLocationText={c('bg')}
chat_attachPermissionImage={plain('text')}
chat_attachPermissionMark={plain('text')}
chat_attachPermissionText={plain('text')}
chat_attachPhotoBackground=#00000000
chat_attachPollBackground={plain('accent')}
chat_attachPollText={c('bg')}
chat_attachUnactiveTab={plain('subtext')}
chat_BlurAlpha=#be000000
chat_BlurAlphaSlow=#be000000
chat_botButtonText={plain('accent')}
chat_botKeyboardButtonBackground={c('panel')}
chat_botKeyboardButtonBackgroundPressed={plain('accent')}
chat_botKeyboardButtonText={plain('accent')}
chat_botSwitchToInlineText={plain('accent')}
chat_editMediaButton={plain('accent')}
chat_emojiBottomPanelIcon={plain('text')}
chat_emojiPanelBackground={c('bg')}
chat_emojiPanelBackspace={plain('text')}
chat_emojiPanelEmptyText={plain('subtext')}
chat_emojiPanelIcon={plain('text')}
chat_emojiPanelIconSelected={plain('accent')}
chat_emojiPanelNewTrending={plain('accent')}
chat_emojiPanelShadowLine={plain('accent')}
chat_emojiPanelStickerPackSelector={plain('accent')}
chat_emojiPanelStickerPackSelectorLine={plain('accent')}
chat_emojiPanelStickerSetName={plain('text')}
chat_emojiPanelStickerSetNameHighlight={plain('accent')}
chat_emojiPanelStickerSetNameIcon={plain('text')}
chat_emojiPanelTrendingDescription={plain('subtext')}
chat_emojiPanelTrendingTitle={plain('text')}
chat_emojiSearchBackground={c('panel')}
chat_emojiSearchIcon={plain('text')}
chat_fieldOverlayText={plain('accent')}
chat_gifSaveHintBackground={plain('accent')}
chat_gifSaveHintText={c('bg')}
chat_goDownButton={c('panel')}
chat_goDownButtonCounter={c('bg')}
chat_goDownButtonCounterBackground={plain('accent')}
chat_goDownButtonIcon={plain('text')}
chat_inAudioCacheSeekbar={plain('subtext')}
chat_inAudioDurationSelectedText={plain('text')}
chat_inAudioDurationText={plain('subtext')}
chat_inAudioPerfomerSelectedText={plain('text')}
chat_inAudioPerfomerText={plain('subtext')}
chat_inAudioProgress={plain('accent')}
chat_inAudioSeekbar={plain('seek_bg')}
chat_inAudioSeekbarFill={plain('seek_fill')}
chat_inAudioSeekbarSelected={plain('seek_fill')}
chat_inAudioSelectedProgress={plain('accent')}
chat_inAudioTitleText={plain('text')}
chat_inBubble={solid('in_bubble')}
chat_inBubbleSelected={dsel}
chat_inBubbleShadow=#00000000
chat_inContactBackground={plain('accent')}
chat_inContactIcon={c('bg')}
chat_inContactNameText={plain('text')}
chat_inContactPhoneSelectedText={plain('text')}
chat_inContactPhoneText={plain('subtext')}
chat_inDownCall={plain('text')}
chat_inFileBackground={c('panel')}
chat_inFileBackgroundSelected={plain('accent')}
chat_inFileInfoSelectedText={plain('text')}
chat_inFileInfoText={plain('subtext')}
chat_inFileNameText={plain('text')}
chat_inFileProgress={c('bg')}
chat_inFileProgressSelected={plain('accent')}
chat_inForwardedNameText={plain('accent')}
chat_inInstant={plain('accent')}
chat_inInstantSelected={plain('accent2')}
chat_inlineResultIcon={plain('accent')}
chat_inLoader={plain('accent')}
chat_inLoaderPhoto={plain('text')}
chat_inLoaderSelected={plain('accent2')}
chat_inLocationBackground={plain('accent')}
chat_inLocationIcon={plain('text')}
chat_inMediaIcon={plain('text')}
chat_inMediaIconSelected={plain('text')}
chat_inMenu={plain('text')}
chat_inMenuSelected={plain('text')}
chat_inPollCorrectAnswer={plain('accent')}
chat_inPollWrongAnswer={plain('text')}
chat_inPreviewInstantText={plain('text')}
chat_inPreviewLine={plain('accent')}
chat_inPsaNameText={plain('text')}
chat_inReactionButtonBackground={plain('accent')}
chat_inReactionButtonText={plain('text')}
chat_inReactionButtonTextSelected={plain('text')}
chat_inReplyLine={plain('reply_line')}
chat_inReplyMediaMessageSelectedText={plain('subtext')}
chat_inReplyMediaMessageText={plain('subtext')}
chat_inReplyMessageText={plain('subtext')}
chat_inReplyNameText={plain('link')}
chat_inSentClock={plain('subtext')}
chat_inSentClockSelected={plain('subtext')}
chat_inSiteNameText={plain('accent')}
chat_inTextSelectionHighlight={c('accent', '44')}
chat_inTimeSelectedText={plain('subtext')}
chat_inTimeText={plain('subtext')}
chat_inVenueInfoSelectedText={plain('text')}
chat_inVenueInfoText={plain('subtext')}
chat_inViaBotNameText={plain('accent')}
chat_inViews={plain('subtext')}
chat_inViewsSelected={plain('subtext')}
chat_inVoiceSeekbar={plain('seek_bg')}
chat_inVoiceSeekbarFill={plain('seek_fill')}
chat_inVoiceSeekbarSelected={plain('seek_fill')}
chat_linkSelectBackground={c('accent', '44')}
chat_lockIcon={plain('text')}
chat_mediaInfoText={plain('text')}
chat_mediaLoaderPhoto=#00000000
chat_mediaLoaderPhotoIcon={plain('text')}
chat_mediaLoaderPhotoIconSelected={plain('text')}
chat_mediaLoaderPhotoSelected=#00000000
chat_mediaMenu={plain('text')}
chat_mediaProgress={c('bg')}
chat_mediaSentCheck={plain('text')}
chat_mediaSentClock={plain('text')}
chat_mediaTimeBackground={c('bg', '88')}
chat_mediaTimeText={c('bg')}
chat_mediaViews={plain('text')}
chat_messageLinkIn={plain('link')}
chat_messageLinkOut={plain('link')}
chat_messagePanelBackground={c('panel')}
chat_messagePanelCancelInlineBot={c('bg')}
chat_messagePanelCursor={plain('accent')}
chat_messagePanelHint={plain('subtext')}
chat_messagePanelIcons={plain('text')}
chat_messagePanelSend={plain('accent')}
chat_messagePanelShadow={plain('accent')}
chat_messagePanelText={plain('text')}
chat_messagePanelVoiceBackground={plain('accent')}
chat_messagePanelVoiceDelete={plain('text')}
chat_messagePanelVoiceDuration={c('bg')}
chat_messagePanelVoicePressed={plain('accent2')}
chat_messageTextIn={plain('text')}
chat_messageTextOut={plain('text')}
chat_muteIcon={plain('subtext')}
chat_outAdminSelectedText={plain('text')}
chat_outAdminText={plain('subtext')}
chat_outAudioCacheSeekbar={plain('subtext')}
chat_outAudioDurationSelectedText={plain('text')}
chat_outAudioDurationText={plain('subtext')}
chat_outAudioPerfomerSelectedText={plain('text')}
chat_outAudioPerfomerText={plain('subtext')}
chat_outAudioProgress={plain('accent')}
chat_outAudioSeekbar={plain('seek_bg')}
chat_outAudioSeekbarFill={plain('seek_fill')}
chat_outAudioSeekbarSelected={plain('seek_fill')}
chat_outAudioSelectedProgress={plain('accent')}
chat_outAudioTitleText={plain('text')}
chat_outBubble={solid('out_bubble')}
noGradient={plain('accent')}
noGradient2={plain('accent2')}
noGradient3={plain('accent3')}
chat_outBubbleGradientAnimated={plain('accent')}
chat_outBubbleGradientSelectedOverlay={plain('accent')}
chat_outBubbleSelected={dsel}
chat_outBubbleShadow=#00000000
chat_outContactBackground={c('panel')}
chat_outContactIcon={plain('text')}
chat_outContactNameText={plain('text')}
chat_outContactPhoneSelectedText={plain('text')}
chat_outContactPhoneText={plain('subtext')}
chat_outFileBackground={c('panel')}
chat_outFileBackgroundSelected={plain('accent')}
chat_outFileInfoSelectedText={plain('text')}
chat_outFileInfoText={plain('subtext')}
chat_outFileNameText={plain('text')}
chat_outFileProgress={plain('accent')}
chat_outFileProgressSelected={plain('accent2')}
chat_outForwardedNameText={plain('text')}
chat_outInstant={plain('text')}
chat_outInstantSelected={plain('text')}
chat_outLinkSelectBackground={c('accent', '44')}
chat_outLoader={plain('text')}
chat_outLoaderSelected={plain('text')}
chat_outLocationIcon={plain('text')}
chat_outMediaIcon={plain('accent')}
chat_outMediaIconSelected={plain('accent')}
chat_outMenu={plain('text')}
chat_outMenuSelected={plain('text')}
chat_outPollCorrectAnswer={plain('accent')}
chat_outPollWrongAnswer={plain('text')}
chat_outPreviewInstantText={plain('text')}
chat_outPreviewLine={plain('accent')}
chat_outPsaNameText={plain('text')}
chat_outReactionButtonBackground={c('accent', '88')}
chat_outReactionButtonText={plain('text')}
chat_outReactionButtonTextSelected={plain('text')}
chat_outReplyLine={plain('reply_line')}
chat_outReplyMediaMessageSelectedText={plain('subtext')}
chat_outReplyMediaMessageText={plain('subtext')}
chat_outReplyMessageText={plain('subtext')}
chat_outReplyNameText={plain('text')}
chat_outSentCheck={plain('text')}
chat_outSentCheckRead={plain('text')}
chat_outSentCheckReadSelected={plain('text')}
chat_outSentCheckSelected={plain('text')}
chat_outSentClock={plain('subtext')}
chat_outSentClockSelected={plain('subtext')}
chat_outSiteNameText={plain('text')}
chat_outTextSelectionCursor={plain('text')}
chat_outTextSelectionHighlight={c('accent', '44')}
chat_outTimeSelectedText={plain('subtext')}
chat_outTimeText={plain('subtext')}
chat_outUpCall={plain('text')}
chat_outVenueInfoSelectedText={plain('text')}
chat_outVenueInfoText={plain('subtext')}
chat_outViaBotNameText={plain('text')}
chat_outViews={plain('subtext')}
chat_outViewsSelected={plain('subtext')}
chat_outVoiceSeekbar={plain('seek_bg')}
chat_outVoiceSeekbarFill={plain('seek_fill')}
chat_outVoiceSeekbarSelected={plain('seek_fill')}
chat_previewDurationText={c('bg')}
chat_previewGameText={c('bg')}
chat_recordedVoiceBackground={plain('accent')}
chat_recordedVoiceDarkerBackground={plain('accent2')}
chat_recordedVoiceDot={plain('text')}
chat_recordedVoicePlayPause={c('bg')}
chat_recordedVoiceProgress={plain('accent')}
chat_recordedVoiceProgressInner={c('bg')}
chat_recordTime={plain('text')}
chat_recordVoiceCancel={plain('text')}
chat_replyPanelClose={plain('text')}
chat_replyPanelIcons={plain('accent')}
chat_replyPanelLine={plain('accent')}
chat_replyPanelName={plain('accent')}
chat_searchPanelIcons={plain('text')}
chat_searchPanelText={plain('text')}
chat_secretChatStatusText={plain('text')}
chat_secretTimeText={plain('text')}
chat_selectedBackground={c('accent', '55')}
chat_sentError={plain('text')}
chat_sentErrorIcon={c('bg')}
chat_serviceBackground={c('bg', '88')}
chat_serviceBackgroundSelected={plain('accent')}
chat_serviceBackgroundSelector={plain('accent')}
chat_serviceIcon={plain('text')}
chat_serviceLink={plain('accent')}
chat_serviceText={plain('text')}
chat_status={plain('accent')}
chat_stickerNameText={c('bg')}
chat_stickerReplyLine={plain('accent')}
chat_stickerReplyMessageText={plain('text')}
chat_stickerReplyNameText={plain('accent')}
chat_stickerViaBotNameText={c('bg')}
chat_stickersHintPanel={c('panel')}
chat_textSelectBackground={c('accent', '55')}
chat_TextSelectionCursor={plain('text')}
chat_topPanelBackground={plain('bg')}
chat_topPanelClose={plain('text')}
chat_topPanelLine={plain('accent')}
chat_topPanelMessage={plain('text')}
chat_topPanelTitle={plain('accent')}
chat_unreadMessagesStartArrowIcon={plain('text')}
chat_unreadMessagesStartBackground={plain('accent')}
chat_unreadMessagesStartText={c('bg')}
checkbox={plain('accent')}
checkboxCheck={c('bg')}
checkboxDisabled={plain('subtext')}
checkboxSquareBackground={plain('accent')}
checkboxSquareCheck={c('bg')}
checkboxSquareDisabled={plain('subtext')}
checkboxSquareUnchecked={plain('text')}
color_blue={plain('accent')}
color_green={plain('accent3')}
color_lightblue={plain('accent2')}
color_lightgreen={plain('accent3')}
color_orange={plain('accent')}
color_purple={plain('accent2')}
color_red={plain('text')}
color_yellow={plain('accent')}
contacts_inviteBackground={plain('accent')}
contacts_inviteText={c('bg')}
contextProgressInner1={plain('accent')}
contextProgressInner2={plain('accent2')}
contextProgressInner3={plain('accent3')}
contextProgressInner4={plain('accent')}
contextProgressOuter1={plain('accent')}
contextProgressOuter2={plain('accent2')}
contextProgressOuter3={plain('accent3')}
contextProgressOuter4={plain('accent')}
dialogBackground={solid('solid')}
dialogBackgroundGray={solid('solid')}
dialogButton={plain('accent')}
dialogButtonSelector={plain('accent')}
dialogCardShadow=#00000000
dialogCameraIcon={c('bg')}
dialogCheckboxSquareBackground={plain('accent')}
dialogCheckboxSquareCheck={c('bg')}
dialogCheckboxSquareDisabled={plain('subtext')}
dialogCheckboxSquareUnchecked={plain('text')}
dialogEmptyImage={plain('text')}
dialogEmptyText={plain('text')}
dialogFloatingButton={plain('accent')}
dialogFloatingButtonPressed={plain('accent2')}
dialogFloatingIcon={c('bg')}
dialogGiftsBackground={plain('accent')}
dialogGiftsTabText={plain('text')}
dialogGrayLine={plain('divider')}
dialogIcon={plain('text')}
dialogInputField={plain('text')}
dialogInputFieldActivated={plain('accent')}
dialogLineProgress={plain('accent')}
dialogLineProgressBackground={plain('seek_bg')}
dialogLinkSelection={c('accent', '44')}
dialogRadioBackground={plain('text')}
dialogRadioBackgroundChecked={plain('accent')}
dialogReactionMentionBackground={plain('accent')}
dialogRoundCheckBox={plain('accent')}
dialogRoundCheckBoxCheck={c('bg')}
dialogScrollGlow={c('bg')}
dialogSearchBackground={c('panel')}
dialogSearchHint={plain('subtext')}
dialogSearchIcon={plain('text')}
dialogSearchText={plain('text')}
dialogShadowLine={plain('divider')}
dialogSwipeRemove={plain('text')}
dialogTextBlack={plain('text')}
dialogTextBlue={plain('accent')}
dialogTextBlue2={plain('accent2')}
dialogTextBlue4={plain('accent')}
dialogTextGray={plain('accent')}
dialogTextGray2={plain('subtext')}
dialogTextGray3={plain('subtext')}
dialogTextGray4={plain('subtext')}
dialogTextHint={plain('subtext')}
dialogTextLink={plain('link')}
dialogTopBackground={plain('accent')}
dialog_inlineProgress={plain('accent')}
dialog_inlineProgressBackground={plain('text')}
dialog_liveLocationProgress={plain('accent')}
divider={c('divider', '66')}
emptyListPlaceholder={plain('subtext')}
fastScrollActive={plain('accent')}
fastScrollInactive={plain('subtext')}
fastScrollText={c('bg')}
featuredStickers_addButton={plain('accent')}
featuredStickers_addButtonPressed={plain('accent2')}
featuredStickers_addedIcon={plain('accent')}
featuredStickers_buttonProgress={plain('accent')}
featuredStickers_buttonText={c('bg')}
featuredStickers_removeButtonText={plain('text')}
featuredStickers_unread={plain('accent')}
files_folderIcon={plain('text')}
files_folderIconBackground={plain('accent')}
files_iconText={plain('text')}
fill_RedNormal={plain('text')}
fill_RedDark={plain('text')}
gift_ribbon={plain('accent')}
gift_ribbon_soldout={plain('accent2')}
graySection={plain('subtext')}
groupcreate_cursor={plain('accent')}
groupcreate_hintText={plain('subtext')}
groupcreate_sectionShadow={plain('accent')}
groupcreate_sectionText={plain('text')}
groupcreate_spanBackground={c('panel')}
groupcreate_spanDelete={plain('accent')}
groupcreate_spanText={plain('text')}
inappPlayerBackground={solid('solid')}
inappPlayerClose={plain('text')}
inappPlayerPerformer={plain('subtext')}
inappPlayerPlayPause={plain('accent')}
inappPlayerTitle={plain('text')}
iv_ab_progress={plain('accent')}
iv_background=#00000000
iv_backgroundGray=#00000000
iv_navigationBackground=#00000000
key_chat_messagePanelVoiceLock={plain('text')}
key_chat_messagePanelVoiceLockBackground={plain('accent')}
key_chat_messagePanelVoiceLockShadow=#00000000
key_graySectionText={plain('text')}
key_player_progressCachedBackground={plain('subtext')}
key_sheet_other={plain('text')}
key_sheet_scrollUp={plain('accent')}
listSelectorSDK21={c('bg', '88')}
location_actionActiveIcon={plain('accent')}
location_actionBackground={plain('accent')}
location_actionIcon={plain('text')}
location_actionPressedBackground={plain('accent2')}
location_liveLocationProgress={plain('accent')}
location_placeLocationBackground={plain('accent')}
location_sendLiveLocationBackground={plain('accent')}
location_sendLiveLocationIcon={c('bg')}
location_sendLiveLocationText={c('bg')}
location_sendLocationBackground={plain('accent')}
location_sendLocationIcon={c('bg')}
location_sendLocationText={c('bg')}
login_progressInner={plain('accent')}
login_progressOuter={plain('accent2')}
passport_authorizeBackground={plain('accent')}
passport_authorizeBackgroundSelected={plain('accent2')}
passport_authorizeText={c('bg')}
picker_badge={plain('accent')}
picker_badgeText={c('bg')}
picker_disabledButton={plain('subtext')}
picker_enabledButton={plain('accent')}
player_actionBarItems={plain('text')}
player_actionBarSelector={plain('accent')}
player_actionBarSubtitle={plain('subtext')}
player_actionBarTitle={plain('text')}
player_background={solid('solid')}
player_button={plain('text')}
player_buttonActive={plain('accent')}
player_progress={plain('accent')}
player_progressBackground={c('bg')}
player_time={plain('text')}
premiumCoinGradient1={plain('accent')}
premiumCoinGradient2={plain('accent2')}
premiumGradient0={plain('accent')}
premiumGradient1={plain('accent')}
premiumGradient2={plain('accent2')}
premiumGradient3={plain('accent3')}
premiumGradient4={plain('accent')}
premiumGradientBackground1={plain('accent')}
premiumGradientBackground2={plain('accent2')}
premiumGradientBackground3={plain('accent3')}
premiumGradientBackground4={plain('accent')}
premiumGradientBackgroundOverlay={plain('accent')}
premiumGradientBottomSheet1={plain('accent')}
premiumGradientBottomSheet2={plain('accent2')}
premiumGradientBottomSheet3={plain('accent3')}
premiumStarGradient1={plain('accent')}
premiumStarGradient2={plain('accent2')}
premiumStartSmallStarsColor={plain('accent')}
premiumStartSmallStarsColor2={plain('accent2')}
profile_actionBackground={plain('accent')}
profile_actionIcon={c('bg')}
profile_actionPressedBackground={plain('accent2')}
profile_creatorIcon={plain('accent')}
profile_status={plain('accent')}
profile_tabSelectedLine={plain('accent')}
profile_tabSelectedText={plain('accent')}
profile_tabSelector={plain('accent')}
profile_tabText={plain('subtext')}
profile_title={plain('text')}
profile_verifiedBackground={plain('accent')}
profile_verifiedCheck={c('bg')}
progressCircle={plain('accent')}
radioBackground={plain('text')}
radioBackgroundChecked={plain('accent')}
reactionStarSelector={plain('accent')}
returnToCallBackground={plain('accent')}
returnToCallMutedBackground={plain('accent2')}
returnToCallText={c('bg')}
sessions_devicesImage={plain('text')}
sharedMedia_linkPlaceholder={c('panel')}
sharedMedia_linkPlaceholderText={plain('text')}
sharedMedia_photoPlaceholder={c('panel')}
sharedMedia_startStopLoadIcon={plain('accent')}
statisticChartActiveLine={plain('accent')}
statisticChartActivePickerChart={plain('accent')}
statisticChartLineEmpty={plain('subtext')}
statisticChartLine_blue={plain('accent')}
statisticChartLine_cyan={plain('accent2')}
statisticChartLine_golden={plain('accent')}
statisticChartLine_green={plain('accent3')}
statisticChartLine_indigo={plain('accent2')}
statisticChartLine_lightblue={plain('accent')}
statisticChartLine_lightgreen={plain('accent3')}
statisticChartLine_orange={plain('accent')}
statisticChartLine_purple={plain('accent2')}
statisticChartLine_red={plain('accent3')}
statisticChartRipple={plain('accent')}
statisticChartSignature={plain('accent')}
statisticChartSignatureAlpha={plain('accent')}
stickers_menu={plain('text')}
stickers_menuSelector={plain('text')}
stories_circle_closeFriends1={plain('accent')}
stories_circle_closeFriends2={plain('accent2')}
stories_circle_dialog1={plain('accent')}
stories_circle_dialog2={plain('accent2')}
stories_circle1={plain('accent')}
stories_circle2={plain('accent2')}
switch2Track={plain('subtext')}
switch2TrackChecked={plain('accent')}
switchTrack={plain('subtext')}
switchTrackBlue={plain('accent')}
switchTrackBlueChecked={plain('accent')}
switchTrackBlueSelector={plain('accent')}
switchTrackBlueSelectorChecked={plain('accent')}
switchTrackBlueThumb={plain('accent')}
switchTrackBlueThumbChecked={plain('accent')}
switchTrackChecked={plain('accent')}
table_background={plain('accent')}
table_border={plain('text')}
text_RedBold={plain('text')}
text_RedRegular={plain('text')}
topics_unreadCounter={plain('accent')}
topics_unreadCounterMuted={plain('accent2')}
undo_background={c('bg', '88')}
undo_cancelColor={plain('text')}
undo_infoColor={plain('text')}
voipgroup_actionBar={plain('accent')}
voipgroup_actionBarItems={plain('text')}
voipgroup_actionBarItemsSelector={plain('accent')}
voipgroup_actionBarUnscrolled={plain('accent')}
voipgroup_checkMenu={plain('accent')}
voipgroup_connectingProgress={plain('accent')}
voipgroup_dialogBackground={plain('accent')}
voipgroup_disabledButton={plain('accent')}
voipgroup_disabledButtonActive={plain('accent')}
voipgroup_disabledButtonActiveScrolled={plain('accent')}
voipgroup_inviteMembersBackground={plain('accent')}
voipgroup_lastSeenText={plain('text')}
voipgroup_lastSeenTextUnscrolled={plain('text')}
voipgroup_leaveButton={plain('accent')}
voipgroup_leaveButtonScrolled={plain('accent')}
voipgroup_leaveCallMenu={plain('accent')}
voipgroup_listeningText={plain('text')}
voipgroup_listSelector={plain('accent')}
voipgroup_listViewBackground={plain('accent')}
voipgroup_listViewBackgroundUnscrolled={plain('accent')}
voipgroup_muteButton={plain('accent')}
voipgroup_muteButton2={plain('accent2')}
voipgroup_muteButton3={plain('accent3')}
voipgroup_mutedByAdminGradient={plain('accent')}
voipgroup_mutedByAdminGradient2={plain('accent2')}
voipgroup_mutedByAdminGradient3={plain('accent3')}
voipgroup_mutedByAdminIcon={plain('text')}
voipgroup_mutedByAdminMuteButton={plain('accent')}
voipgroup_mutedByAdminMuteButtonDisabled={plain('accent')}
voipgroup_mutedIcon={plain('text')}
voipgroup_mutedIconUnscrolled={plain('text')}
voipgroup_nameText={plain('text')}
voipgroup_overlayAlertGradientMuted={plain('accent')}
voipgroup_overlayAlertGradientMuted2={plain('accent2')}
voipgroup_overlayAlertGradientUnmuted={plain('accent')}
voipgroup_overlayAlertGradientUnmuted2={plain('accent2')}
voipgroup_overlayAlertMutedByAdmin={plain('accent')}
voipgroup_overlayAlertMutedByAdmin2={plain('accent2')}
voipgroup_overlayBlue1={plain('accent')}
voipgroup_overlayBlue2={plain('accent2')}
voipgroup_overlayGreen1={plain('accent3')}
voipgroup_overlayGreen2={plain('accent')}
voipgroup_rtmpButton={plain('accent')}
voipgroup_scrollUp={plain('accent')}
voipgroup_searchBackground={plain('accent')}
voipgroup_searchPlaceholder={plain('subtext')}
voipgroup_searchText={plain('text')}
voipgroup_soundButton={plain('accent')}
voipgroup_soundButton2={plain('accent2')}
voipgroup_soundButtonActive={plain('accent')}
voipgroup_soundButtonActive2={plain('accent2')}
voipgroup_soundButtonActive2Scrolled={plain('accent2')}
voipgroup_soundButtonActiveScrolled={plain('accent')}
voipgroup_speakingText={plain('text')}
voipgroup_topPanelBlue1={plain('accent')}
voipgroup_topPanelBlue2={plain('accent2')}
voipgroup_topPanelGray={plain('accent')}
voipgroup_topPanelGreen1={plain('accent3')}
voipgroup_topPanelGreen2={plain('accent')}
voipgroup_unmuteButton={plain('accent')}
voipgroup_unmuteButton2={plain('accent2')}
voipgroup_windowBackgroundWhiteInputField={plain('accent')}
voipgroup_windowBackgroundWhiteInputFieldActivated={plain('accent')}
windowBackgroundChecked={plain('accent')}
windowBackgroundCheckText={c('bg')}
windowBackgroundGray={c('bg')}
windowBackgroundGrayShadow=#00000000
windowBackgroundUnchecked={plain('text')}
windowBackgroundWhite={c('bg')}
windowBackgroundWhiteBlackText={plain('text')}
windowBackgroundWhiteBlueButton={plain('accent')}
windowBackgroundWhiteBlueHeader={plain('accent')}
windowBackgroundWhiteBlueIcon={plain('accent')}
windowBackgroundWhiteBlueText={plain('accent')}
windowBackgroundWhiteBlueText2={plain('accent2')}
windowBackgroundWhiteBlueText3={plain('accent')}
windowBackgroundWhiteBlueText4={plain('accent')}
windowBackgroundWhiteBlueText5={plain('accent')}
windowBackgroundWhiteBlueText6={plain('accent')}
windowBackgroundWhiteBlueText7={plain('accent')}
windowBackgroundWhiteGrayIcon={plain('subtext')}
windowBackgroundWhiteGrayText={plain('subtext')}
windowBackgroundWhiteGrayText2={plain('subtext')}
windowBackgroundWhiteGrayText3={plain('subtext')}
windowBackgroundWhiteGrayText4={plain('subtext')}
windowBackgroundWhiteGrayText5={plain('subtext')}
windowBackgroundWhiteGrayText6={plain('subtext')}
windowBackgroundWhiteGrayText7={plain('subtext')}
windowBackgroundWhiteGrayText8={plain('subtext')}
windowBackgroundWhiteGreenText={plain('accent3')}
windowBackgroundWhiteGreenText2={plain('accent3')}
windowBackgroundWhiteHintText={plain('subtext')}
windowBackgroundWhiteInputField={plain('text')}
windowBackgroundWhiteInputFieldActivated={plain('accent')}
windowBackgroundWhiteLinkSelection={c('accent', '44')}
windowBackgroundWhiteLinkText={plain('link')}
windowBackgroundWhiteValueText={plain('accent')}
chat_wallpaper=#00000000
chat_wallpaper_gradient_to=#00000000
key_chat_wallpaper_gradient_to2=#00000000
key_chat_wallpaper_gradient_to3=#00000000
dialogTextRed={plain('text')}
dialogTextRed2={plain('text')}
dialogTextBlue3={plain('accent')}
dialogInputFieldText={plain('text')}
dialogBadgeBackground={plain('accent')}
dialogBadgeText={c('bg')}
windowBackgroundWhiteRadius={c('bg')}
windowBackgroundWhiteRedText={plain('text')}
windowBackgroundWhiteRedText2={plain('text')}
windowBackgroundWhiteRedText3={plain('text')}
windowBackgroundWhiteRedText4={plain('text')}
windowBackgroundWhiteRedText5={plain('text')}
windowBackgroundWhiteRedText6={plain('text')}
windowBackgroundWhiteGrayLine={plain('divider')}
windowBackgroundGrayLine={plain('divider')}
profile_adminIcon={plain('accent')}
switchThumb={plain('text')}
switchThumbChecked={plain('accent')}
chat_inReplyBackground=#{p['reply_bg']}
chat_outReplyBackground=#{p['reply_bg']}
"""
        return theme

    def _process_photo(self, photo_bytes: bytes, alpha_hex: str = "e6"):
        """Основная функция — умный расчёт цветов для каждой детали"""
        img = Image.open(io.BytesIO(photo_bytes)).convert("RGB")

        # 1. Извлекаем богатую палитру
        colors = self._extract_palette(img, count=12)

        # 2. Строим умную палитру для всех элементов
        palette = self._build_smart_palette(colors)

        # 3. Собираем тему
        theme = self._build_theme(palette, alpha_hex)

        # 4. Обои
        wallpaper = self._theme_wallpaper(img)

        return (
            theme.encode("utf-8")
            + b"\n\nWPS\n"
            + wallpaper
            + b"\nWPE\n"
        ), palette["is_dark"], palette["palette_size"]

    @loader.command(ru_doc="- Создать умную тг-тему по фото (каждая деталь со своим цветом)")
    async def android(self, message):
        """- Create smart tg-theme from a photo (every element gets its own calculated color)"""
        reply = await message.get_reply_message()
        if not reply:
            return await utils.answer(message, self.strings["no_photo"])

        photo = None
        if reply.photo:
            photo = reply.photo
        elif reply.document and reply.document.mime_type and reply.document.mime_type.startswith("image/"):
            photo = reply.document

        if photo is None:
            return await utils.answer(message, self.strings["no_photo"])

        await utils.answer(message, self.strings["processing"])

        try:
            photo_bytes = await self._client.download_file(photo, bytes)

            args = utils.get_args_raw(message)
            transparency = 90
            if args and args.strip().isdigit():
                transparency = max(0, min(100, int(args.strip())))
            alpha = f"{int(transparency / 100 * 255):02x}"

            # УМНАЯ ОБРАБОТКА
            theme_bytes, is_dark, color_count = self._process_photo(photo_bytes, alpha)

            file = io.BytesIO(theme_bytes)
            file.name = f"tgtheme_{'dark' if is_dark else 'light'}_smart.attheme"

            await utils.answer(
                message,
                self.strings["done"].format(
                    "🌙 Тёмная" if is_dark else "☀️ Светлая",
                    transparency,
                    "БЕЛЫЙ" if is_dark else "ЧЁРНЫЙ",
                    color_count
                ),
                file=file,
            )

        except Exception as e:
            logger.error(f"Error: {e}")
            import traceback
            traceback.print_exc()
            await utils.answer(message, self.strings["error"].format(str(e)))
