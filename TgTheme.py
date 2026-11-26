# meta source: https://raw.githubusercontent.com/Wersixx/Wers1xx/main/TgTheme.py
# requires: Pillow
# meta developer: @H_SunMods, @WersModules
# meta pic: https://r2.fakecrime.bio/uploads/47308ab9-6035-4e7d-bc96-6b58f864bb33.jpg
# meta banner: https://r2.fakecrime.bio/uploads/47308ab9-6035-4e7d-bc96-6b58f864bb33.jpg
# meta fhsdesc: Theme, Темы, Sunnex, SunnexGB, H_SunMods, Wersixx, Wers1xx, WersModules

import asyncio
import colorsys
import io
import logging
import math

from PIL import Image
from .. import loader, utils

try:
    from PIL import ImageOps
except Exception:  # pragma: no cover
    ImageOps = None

logger = logging.getLogger(__name__)


# ======================================================================
#                         ЦВЕТОВАЯ МАТЕМАТИКА
# ======================================================================

def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _to_hex(c):
    return "{:02x}{:02x}{:02x}".format(*[int(max(0, min(255, round(v)))) for v in c])


def _lin(v):
    v /= 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _lum(c):
    """Относительная яркость (WCAG)."""
    return 0.2126 * _lin(c[0]) + 0.7152 * _lin(c[1]) + 0.0722 * _lin(c[2])


def _cr(a, b):
    """Контраст двух цветов (WCAG, 1..21)."""
    la, lb = _lum(a), _lum(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def _mix(a, b, t):
    return tuple(int(round(a[i] * (1 - t) + b[i] * t)) for i in range(3))


def _hls(c):
    return colorsys.rgb_to_hls(c[0] / 255.0, c[1] / 255.0, c[2] / 255.0)


def _from_hls(h, l, s):
    r, g, b = colorsys.hls_to_rgb(h % 1.0, _clamp(l), _clamp(s))
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def _lab(c):
    r, g, b = _lin(c[0]), _lin(c[1]), _lin(c[2])
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def _de(a, b):
    return math.dist(a, b)


def _hdiff(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _fit(c, cons, prefer_light=True):
    """
    Подгоняет светлоту цвета (оттенок и насыщенность сохраняются), пока контраст
    с каждым фоном из cons=[(фон, мин_контраст), ...] не станет достаточным.
    """
    c = tuple(c)

    def ok(x):
        return all(_cr(x, b) >= r for b, r in cons)

    if ok(c):
        return c
    h, l, s = _hls(c)
    order = (1, -1) if prefer_light else (-1, 1)
    for i in range(1, 101):
        for sgn in order:
            l2 = l + sgn * i / 100.0
            if 0.0 <= l2 <= 1.0:
                x = _from_hls(h, l2, s)
                if ok(x):
                    return x
    return max(
        ((255, 255, 255), (0, 0, 0)),
        key=lambda x: min(_cr(x, b) / r for b, r in cons),
    )


# ======================================================================
#                       ИЗВЛЕЧЕНИЕ ПАЛИТРЫ ИЗ ФОТО
# ======================================================================

def _extract_palette(img, limit=32):
    """
    Медианное сечение (64 кластера) + слияние близких оттенков в пространстве Lab.
    Возвращает кластеры, отсортированные по площади: rgb, вес, Lab, L, C, H.
    """
    im = img.convert("RGB")
    im.thumbnail((256, 256))
    q = im.quantize(colors=64, method=0, dither=0)
    pal = q.getpalette() or []
    total = float(im.size[0] * im.size[1]) or 1.0

    items = []
    for cnt, idx in (q.getcolors() or []):
        rgb = tuple(pal[idx * 3: idx * 3 + 3])
        if len(rgb) == 3:
            items.append([rgb, cnt / total])
    items.sort(key=lambda x: -x[1])

    merged = []
    for rgb, w in items:
        lab = _lab(rgb)
        for m in merged:
            if _de(lab, m["lab"]) < 7:
                tot = m["w"] + w
                m["rgb"] = tuple(
                    int(round((m["rgb"][i] * m["w"] + rgb[i] * w) / tot)) for i in range(3)
                )
                m["w"] = tot
                m["lab"] = _lab(m["rgb"])
                break
        else:
            merged.append({"rgb": rgb, "w": w, "lab": lab})

    for m in merged:
        L, a, b = m["lab"]
        m["L"] = L
        m["C"] = math.hypot(a, b)
        m["H"] = math.degrees(math.atan2(b, a)) % 360
    merged.sort(key=lambda m: -m["w"])
    return merged[:limit]


# ======================================================================
#                 РОЛИ: ОДИН ЦВЕТ — ОДНА ФУНКЦИЯ В ИНТЕРФЕЙСЕ
# ======================================================================

def _build_palette(colors, force=None, grad=False):
    if not colors:
        rgb = (30, 30, 34)
        L, a, b = _lab(rgb)
        colors = [{"rgb": rgb, "w": 1.0, "lab": (L, a, b), "L": L, "C": 0.0, "H": 0.0}]

    total = sum(c["w"] for c in colors) or 1.0
    mean_l = sum(c["L"] * c["w"] for c in colors) / total
    if force == "dark":
        dark = True
    elif force == "light":
        dark = False
    else:
        dark = mean_l < 55

    # ---------- акценты: самые яркие и РАЗНЫЕ цвета фото ----------
    vivid = [c for c in colors if c["C"] >= 14 and 10 < c["L"] < 96]
    vivid.sort(key=lambda c: -(c["C"] * (c["w"] ** 0.35)))
    picked = []

    def take(cands, min_h, min_de):
        for c in cands:
            if len(picked) >= 8:
                return
            if c in picked:
                continue
            if all(_hdiff(c["H"], p["H"]) >= min_h or _de(c["lab"], p["lab"]) >= min_de
                   for p in picked):
                picked.append(c)

    take(vivid, 20, 35)
    if len(picked) < 8:
        take(vivid, 8, 20)
    if len(picked) < 8:
        take(vivid, 0, 10)
    acc = [p["rgb"] for p in picked]

    dom = colors[0]
    dh, dl, ds = _hls(dom["rgb"])

    if len(acc) < 8:  # фото бедное на цвета — достраиваем оттенки вокруг его цвета
        if acc:
            bh, bl, bs = _hls(acc[0])
        else:
            bh, bl, bs = dh, 0.6, max(ds, 0.06)
        shifts = [0, 30, -30, 60, -60, 90, -90, 150]
        while len(acc) < 8:
            acc.append(_from_hls(bh + shifts[len(acc) % len(shifts)] / 360.0, bl, bs))

    sats = [_hls(a)[2] for a in acc]
    avg_s = _clamp(sum(sats) / len(sats), 0.45, 0.8)

    def semantic(target_h, tol, synth_h):
        cands = [c for c in colors
                 if c["C"] >= 14 and 15 < c["L"] < 95 and _hdiff(c["H"], target_h) <= tol]
        if cands:
            return max(cands, key=lambda c: c["C"] * (c["w"] ** 0.3))["rgb"]
        return _from_hls(synth_h, 0.6, avg_s)

    danger0 = semantic(40, 25, 0.005)    # красный
    success0 = semantic(140, 35, 0.37)   # зелёный
    warning0 = semantic(78, 22, 0.10)    # янтарный

    # ---------- поверхности ----------
    if dom["C"] < 6:
        bh = _hls(acc[0])[0]
        s_bg = 0.12
    else:
        bh = dh
        s_bg = min(ds, 0.55)

    if dark:
        bg = _from_hls(bh, 0.105, s_bg * 0.85)
        bg_hi = _from_hls(bh, 0.150, s_bg * 0.80)
        bg_lo = _from_hls(bh, 0.065, s_bg * 0.85)
        panel = _mix(bg_hi, acc[0], 0.10)
        in_bubble = _mix(_from_hls(bh, 0.17, s_bg * 0.8), acc[0], 0.06)
        action_bar = bg_lo
        on_accent = _from_hls(bh, 0.07, 0.35)
    else:
        bg = _from_hls(bh, 0.95, min(s_bg, 0.5))
        bg_hi = _from_hls(bh, 0.99, min(s_bg, 0.5))
        bg_lo = _from_hls(bh, 0.90, min(s_bg, 0.5))
        panel = _mix(bg_lo, acc[0], 0.08)
        in_bubble = _mix(_from_hls(bh, 0.99, min(s_bg, 0.5)), acc[0], 0.03)
        action_bar = bg_hi
        on_accent = _from_hls(bh, 0.985, 0.25)

    surfaces = [bg, bg_hi, bg_lo, panel, in_bubble, action_bar]

    text = _fit(_from_hls(bh, 0.96 if dark else 0.08, 0.3),
                [(b, 10.0) for b in surfaces], dark)
    subtext = _fit(_mix(text, bg, 0.40), [(b, 4.6) for b in surfaces], dark)

    # все акценты читаются на поверхностях и при этом на них читается on_accent
    cons_acc = [(b, 4.5) for b in surfaces] + [(on_accent, 4.2)]
    A = [_fit(a, cons_acc, dark) for a in acc]
    danger = _fit(danger0, cons_acc, dark)
    success = _fit(success0, cons_acc, dark)
    warning = _fit(warning0, cons_acc, dark)

    link = _fit(_mix(A[0], text, 0.25), [(b, 5.0) for b in surfaces], dark)

    # ---------- исходящие пузыри ----------
    ah, _, asat = _hls(A[0])
    out_bubble = _from_hls(ah, 0.27 if dark else 0.86, min(asat, 0.55 if dark else 0.75))
    out_backs = [out_bubble]
    roles_extra = {}
    if grad:
        g1h, _, g1s = _hls(A[1])
        g2h, _, g2s = _hls(A[2])
        gl = 0.27 if dark else 0.86
        roles_extra["out_grad1"] = _from_hls(g1h, gl, min(g1s, 0.55 if dark else 0.75))
        roles_extra["out_grad2"] = _from_hls(g2h, gl, min(g2s, 0.55 if dark else 0.75))
        out_backs += [roles_extra["out_grad1"], roles_extra["out_grad2"]]

    out_text = _fit(_from_hls(ah, 0.97 if dark else 0.08, 0.25),
                    [(b, 8.0) for b in out_backs], dark)
    out_subtext = _fit(_mix(out_text, out_bubble, 0.38), [(b, 4.6) for b in out_backs], dark)
    out_cons5 = [(b, 5.0) for b in out_backs]
    out_accent = _fit(_mix(A[1], out_text, 0.35), out_cons5, dark)
    out_accent2 = _fit(_mix(A[2], out_text, 0.35), out_cons5, dark)
    out_link = _fit(_mix(A[3], out_text, 0.30), out_cons5, dark)
    out_danger = _fit(danger, [(b, 4.5) for b in out_backs], dark)
    out_success = _fit(success, [(b, 4.5) for b in out_backs], dark)

    roles = {
        "bg": bg, "bg_hi": bg_hi, "bg_lo": bg_lo, "panel": panel,
        "action_bar": action_bar, "in_bubble": in_bubble, "out_bubble": out_bubble,
        "on_accent": on_accent, "text": text, "subtext": subtext, "link": link,
        "divider": _mix(bg, text, 0.14),
        "seek_bg": _mix(bg, text, 0.25),
        "seek_fill": A[0],
        "reply_line": A[1],
        "sel": _mix(in_bubble, A[0], 0.28),
        "danger": danger, "success": success, "warning": warning,
        "out_text": out_text, "out_subtext": out_subtext,
        "out_accent": out_accent, "out_accent2": out_accent2, "out_link": out_link,
        "out_danger": out_danger, "out_success": out_success,
        "out_seek_bg": _mix(out_bubble, out_text, 0.28),
        "out_seek_fill": out_accent,
        "out_panel": _mix(out_bubble, out_text, 0.12),
        "out_sel": _mix(out_bubble, out_accent, 0.30),
    }
    for i, a in enumerate(A):
        roles["accent" if i == 0 else "accent%d" % (i + 1)] = a
    roles.update(roles_extra)

    meta = {
        "is_dark": dark,
        "colors": len(colors),
        "accents": ["#" + _to_hex(a) for a in A],
    }
    return roles, meta


# ======================================================================
#          КАРТА «КЛЮЧ ТЕМЫ → РОЛЬ» (каждый элемент интерфейса)
#   формат:  ключ=роль          цвет без прозрачности
#            ключ=роль@AA       фиксированная прозрачность (hex)
#            ключ=роль@A        прозрачность, заданная пользователем
#            ключ=#aarrggbb     готовый цвет
#   Для chat_out* роли text/subtext/accent/link/... автоматически
#   заменяются на out_* — они подогнаны под цвет исходящего пузыря.
# ======================================================================

SPEC = """actionBarActionModeDefault=action_bar@A
actionBarActionModeDefaultIcon=text
actionBarActionModeDefaultSelector=accent@44
actionBarActionModeDefaultTop=bg_lo
actionBarActionModeReaction=accent
actionBarActionModeReactionText=text
actionBarActionModeReactionDot=text
actionBarBrowser=accent
actionBarDefault=action_bar@A
actionBarDefaultArchived=accent2
actionBarDefaultArchivedIcon=on_accent
actionBarDefaultArchivedSearch=on_accent
actionBarDefaultArchivedSelector=on_accent@33
actionBarDefaultArchivedTitle=on_accent
actionBarDefaultIcon=text
actionBarDefaultSearch=accent
actionBarDefaultSearchArchivedPlaceholder=on_accent@99
actionBarDefaultSearchPlaceholder=subtext
actionBarDefaultSelector=accent@44
actionBarDefaultSubmenuBackground=bg@A
actionBarDefaultSubmenuItem=text
actionBarDefaultSubmenuItemIcon=text
actionBarDefaultSubmenuSeparator=divider
actionBarDefaultSubtitle=subtext
actionBarDefaultTitle=text
actionBarTabActiveText=accent
actionBarTabLine=accent
actionBarTabSelector=accent@44
actionBarTabUnactiveText=subtext
actionBarWhiteSelector=accent@44
avatar_actionBarIconBlue=on_accent
avatar_actionBarSelectorBlue=on_accent@33
avatar_backgroundActionBarBlue=accent
avatar_backgroundArchived=accent2
avatar_backgroundArchivedHidden=accent3
avatar_backgroundBlue=accent
avatar_backgroundCyan=accent2
avatar_backgroundGreen=success
avatar_backgroundInProfileBlue=accent
avatar_backgroundOrange=warning
avatar_backgroundPink=accent3
avatar_backgroundRed=danger
avatar_backgroundSaved=accent
avatar_backgroundViolet=accent4
avatar_background2Blue=accent
avatar_background2Cyan=accent2
avatar_background2Green=success
avatar_background2Orange=warning
avatar_background2Pink=accent3
avatar_background2Red=danger
avatar_background2Saved=accent
avatar_background2Violet=accent4
avatar_nameInMessageBlue=accent
avatar_nameInMessageCyan=accent2
avatar_nameInMessageGreen=success
avatar_nameInMessageOrange=warning
avatar_nameInMessagePink=accent3
avatar_nameInMessageRed=danger
avatar_nameInMessageViolet=accent4
avatar_subtitleInProfileBlue=on_accent@cc
avatar_text=on_accent@A
bot_loadingIcon=text
calls_callReceivedGreenIcon=success
calls_callReceivedRedIcon=danger
changephoneinfo_image2=text
chats_actionBackground=accent
chats_actionIcon=on_accent@A
chats_actionMessage=accent
chats_actionPressedBackground=accent2
chats_archiveBackground=accent2
chats_archiveIcon=on_accent@A
chats_archivePinBackground=accent
chats_archivePullDownBackground=accent
chats_archivePullDownBackgroundActive=accent2
chats_archiveText=on_accent@A
chats_attachMessage=accent
chats_date=subtext
chats_draft=accent
chats_mentionIcon=on_accent@A
chats_menuBackground=bg@A
chats_menuItemCheck=text
chats_menuItemIcon=text
chats_menuItemText=text
chats_menuName=on_accent
chats_menuPhone=on_accent@cc
chats_menuPhoneCats=on_accent@cc
chats_menuTopBackground=accent
chats_menuTopBackgroundCats=accent2
chats_menuTopShadow=#00000000
chats_menuTopShadowCats=#00000000
chats_message=text
chats_messageArchived=subtext
chats_message_threeLines=text
chats_muteIcon=subtext
chats_name=text
chats_nameArchived=subtext
chats_nameMessage=accent
chats_nameMessageArchived=accent2
chats_nameMessageArchived_threeLines=accent2
chats_nameMessage_threeLines=accent
chats_onlineCircle=success
chats_pinnedIcon=text
chats_pinnedOverlay=#00000000
chats_secretIcon=accent
chats_secretName=accent
chats_sentCheck=accent
chats_sentClock=subtext
chats_sentError=danger
chats_sentErrorIcon=on_accent@A
chats_sentReadCheck=accent
chats_tabUnreadActiveBackground=accent
chats_tabUnreadUnactiveBackground=accent2
chats_tabletSelectedOverlay=#00000000
chats_unreadCounter=accent
chats_unreadCounterMuted=subtext
chats_unreadCounterText=on_accent@A
chats_verifiedBackground=accent
chats_verifiedCheck=on_accent@A
chat_addContact=accent
chat_adminSelectedText=text
chat_adminText=subtext
chat_attachActiveTab=accent
chat_attachAudioBackground=accent
chat_attachAudioText=on_accent@A
chat_attachCheckBoxBackground=accent
chat_attachCheckBoxCheck=on_accent@A
chat_attachContactBackground=accent2
chat_attachContactText=on_accent@A
chat_attachEmptyImage=text
chat_attachFileBackground=accent3
chat_attachFileText=on_accent@A
chat_attachGalleryBackground=accent
chat_attachGalleryText=on_accent@A
chat_attachIcon=on_accent@A
chat_attachLocationBackground=accent2
chat_attachLocationText=on_accent@A
chat_attachPermissionImage=text
chat_attachPermissionMark=text
chat_attachPermissionText=text
chat_attachPhotoBackground=#00000000
chat_attachPollBackground=accent
chat_attachPollText=on_accent@A
chat_attachUnactiveTab=subtext
chat_BlurAlpha=#be000000
chat_BlurAlphaSlow=#be000000
chat_botButtonText=accent
chat_botKeyboardButtonBackground=panel@A
chat_botKeyboardButtonBackgroundPressed=accent@44
chat_botKeyboardButtonText=accent
chat_botSwitchToInlineText=accent
chat_editMediaButton=accent
chat_emojiBottomPanelIcon=text
chat_emojiPanelBackground=bg@A
chat_emojiPanelBackspace=text
chat_emojiPanelEmptyText=subtext
chat_emojiPanelIcon=text
chat_emojiPanelIconSelected=accent
chat_emojiPanelNewTrending=accent
chat_emojiPanelShadowLine=divider
chat_emojiPanelStickerPackSelector=accent@44
chat_emojiPanelStickerPackSelectorLine=accent
chat_emojiPanelStickerSetName=text
chat_emojiPanelStickerSetNameHighlight=accent
chat_emojiPanelStickerSetNameIcon=text
chat_emojiPanelTrendingDescription=subtext
chat_emojiPanelTrendingTitle=text
chat_emojiSearchBackground=panel@A
chat_emojiSearchIcon=text
chat_fieldOverlayText=accent
chat_gifSaveHintBackground=accent
chat_gifSaveHintText=on_accent@A
chat_goDownButton=panel@A
chat_goDownButtonCounter=on_accent@A
chat_goDownButtonCounterBackground=accent
chat_goDownButtonIcon=text
chat_inAudioCacheSeekbar=subtext
chat_inAudioDurationSelectedText=text
chat_inAudioDurationText=subtext
chat_inAudioPerfomerSelectedText=text
chat_inAudioPerfomerText=subtext
chat_inAudioProgress=accent
chat_inAudioSeekbar=seek_bg
chat_inAudioSeekbarFill=seek_fill
chat_inAudioSeekbarSelected=seek_fill
chat_inAudioSelectedProgress=accent
chat_inAudioTitleText=text
chat_inBubble=in_bubble
chat_inBubbleSelected=sel
chat_inBubbleShadow=#00000000
chat_inContactBackground=accent
chat_inContactIcon=on_accent
chat_inContactNameText=text
chat_inContactPhoneSelectedText=text
chat_inContactPhoneText=subtext
chat_inDownCall=danger
chat_inFileBackground=panel@A
chat_inFileBackgroundSelected=accent@44
chat_inFileInfoSelectedText=text
chat_inFileInfoText=subtext
chat_inFileNameText=text
chat_inFileProgress=accent
chat_inFileProgressSelected=accent
chat_inForwardedNameText=accent
chat_inInstant=accent
chat_inInstantSelected=accent2
chat_inlineResultIcon=accent
chat_inLoader=accent
chat_inLoaderPhoto=text
chat_inLoaderSelected=accent2
chat_inLocationBackground=accent
chat_inLocationIcon=on_accent
chat_inMediaIcon=on_accent
chat_inMediaIconSelected=on_accent
chat_inMenu=text
chat_inMenuSelected=text
chat_inPollCorrectAnswer=success
chat_inPollWrongAnswer=danger
chat_inPreviewInstantText=text
chat_inPreviewLine=accent
chat_inPsaNameText=text
chat_inReactionButtonBackground=accent
chat_inReactionButtonText=text
chat_inReactionButtonTextSelected=text
chat_inReplyLine=reply_line
chat_inReplyMediaMessageSelectedText=subtext
chat_inReplyMediaMessageText=subtext
chat_inReplyMessageText=subtext
chat_inReplyNameText=link
chat_inSentClock=subtext
chat_inSentClockSelected=subtext
chat_inSiteNameText=accent
chat_inTextSelectionHighlight=accent@44
chat_inTimeSelectedText=subtext
chat_inTimeText=subtext
chat_inVenueInfoSelectedText=text
chat_inVenueInfoText=subtext
chat_inViaBotNameText=accent
chat_inViews=subtext
chat_inViewsSelected=subtext
chat_inVoiceSeekbar=seek_bg
chat_inVoiceSeekbarFill=seek_fill
chat_inVoiceSeekbarSelected=seek_fill
chat_linkSelectBackground=accent@44
chat_lockIcon=text
chat_mediaInfoText=text
chat_mediaLoaderPhoto=bg@aa
chat_mediaLoaderPhotoIcon=text
chat_mediaLoaderPhotoIconSelected=text
chat_mediaLoaderPhotoSelected=bg@aa
chat_mediaMenu=text
chat_mediaProgress=text
chat_mediaSentCheck=text
chat_mediaSentClock=text
chat_mediaTimeBackground=bg@88
chat_mediaTimeText=text
chat_mediaViews=text
chat_messageLinkIn=link
chat_messageLinkOut=link
chat_messagePanelBackground=panel@A
chat_messagePanelCancelInlineBot=text
chat_messagePanelCursor=accent
chat_messagePanelHint=subtext
chat_messagePanelIcons=text
chat_messagePanelSend=accent
chat_messagePanelShadow=divider
chat_messagePanelText=text
chat_messagePanelVoiceBackground=accent
chat_messagePanelVoiceDelete=text
chat_messagePanelVoiceDuration=on_accent@A
chat_messagePanelVoicePressed=accent2
chat_messageTextIn=text
chat_messageTextOut=text
chat_muteIcon=subtext
chat_outAdminSelectedText=text
chat_outAdminText=subtext
chat_outAudioCacheSeekbar=subtext
chat_outAudioDurationSelectedText=text
chat_outAudioDurationText=subtext
chat_outAudioPerfomerSelectedText=text
chat_outAudioPerfomerText=subtext
chat_outAudioProgress=accent
chat_outAudioSeekbar=seek_bg
chat_outAudioSeekbarFill=seek_fill
chat_outAudioSeekbarSelected=seek_fill
chat_outAudioSelectedProgress=accent
chat_outAudioTitleText=text
chat_outBubble=out_bubble
chat_outBubbleGradientAnimated=accent
chat_outBubbleGradientSelectedOverlay=accent@44
chat_outBubbleSelected=sel
chat_outBubbleShadow=#00000000
chat_outContactBackground=panel@A
chat_outContactIcon=text
chat_outContactNameText=text
chat_outContactPhoneSelectedText=text
chat_outContactPhoneText=subtext
chat_outFileBackground=panel@A
chat_outFileBackgroundSelected=accent@44
chat_outFileInfoSelectedText=text
chat_outFileInfoText=subtext
chat_outFileNameText=text
chat_outFileProgress=accent
chat_outFileProgressSelected=accent2
chat_outForwardedNameText=text
chat_outInstant=text
chat_outInstantSelected=text
chat_outLinkSelectBackground=accent@44
chat_outLoader=text
chat_outLoaderSelected=text
chat_outLocationIcon=out_bubble
chat_outMediaIcon=out_bubble
chat_outMediaIconSelected=out_bubble
chat_outMenu=text
chat_outMenuSelected=text
chat_outPollCorrectAnswer=success
chat_outPollWrongAnswer=danger
chat_outPreviewInstantText=text
chat_outPreviewLine=accent
chat_outPsaNameText=text
chat_outReactionButtonBackground=accent@88
chat_outReactionButtonText=text
chat_outReactionButtonTextSelected=text
chat_outReplyLine=reply_line
chat_outReplyMediaMessageSelectedText=subtext
chat_outReplyMediaMessageText=subtext
chat_outReplyMessageText=subtext
chat_outReplyNameText=text
chat_outSentCheck=text
chat_outSentCheckRead=text
chat_outSentCheckReadSelected=text
chat_outSentCheckSelected=text
chat_outSentClock=subtext
chat_outSentClockSelected=subtext
chat_outSiteNameText=text
chat_outTextSelectionCursor=text
chat_outTextSelectionHighlight=accent@44
chat_outTimeSelectedText=subtext
chat_outTimeText=subtext
chat_outUpCall=success
chat_outVenueInfoSelectedText=text
chat_outVenueInfoText=subtext
chat_outViaBotNameText=text
chat_outViews=subtext
chat_outViewsSelected=subtext
chat_outVoiceSeekbar=seek_bg
chat_outVoiceSeekbarFill=seek_fill
chat_outVoiceSeekbarSelected=seek_fill
chat_previewDurationText=text
chat_previewGameText=text
chat_recordedVoiceBackground=accent
chat_recordedVoiceDarkerBackground=accent2
chat_recordedVoiceDot=danger
chat_recordedVoicePlayPause=on_accent@A
chat_recordedVoiceProgress=on_accent
chat_recordedVoiceProgressInner=on_accent@A
chat_recordTime=text
chat_recordVoiceCancel=text
chat_replyPanelClose=text
chat_replyPanelIcons=accent
chat_replyPanelLine=accent
chat_replyPanelName=accent
chat_searchPanelIcons=text
chat_searchPanelText=text
chat_secretChatStatusText=text
chat_secretTimeText=text
chat_selectedBackground=accent@55
chat_sentError=danger
chat_sentErrorIcon=on_accent@A
chat_serviceBackground=bg@88
chat_serviceBackgroundSelected=accent@aa
chat_serviceBackgroundSelector=accent@44
chat_serviceIcon=text
chat_serviceLink=accent
chat_serviceText=text
chat_status=accent
chat_stickerNameText=text
chat_stickerReplyLine=accent
chat_stickerReplyMessageText=text
chat_stickerReplyNameText=accent
chat_stickerViaBotNameText=text
chat_stickersHintPanel=panel@A
chat_textSelectBackground=accent@55
chat_TextSelectionCursor=text
chat_topPanelBackground=on_accent
chat_topPanelClose=text
chat_topPanelLine=accent
chat_topPanelMessage=text
chat_topPanelTitle=accent
chat_unreadMessagesStartArrowIcon=text
chat_unreadMessagesStartBackground=accent
chat_unreadMessagesStartText=on_accent@A
checkbox=accent
checkboxCheck=on_accent@A
checkboxDisabled=subtext
checkboxSquareBackground=accent
checkboxSquareCheck=on_accent@A
checkboxSquareDisabled=subtext
checkboxSquareUnchecked=subtext
color_blue=accent
color_green=success
color_lightblue=accent2
color_lightgreen=success
color_orange=warning
color_purple=accent4
color_red=danger
color_yellow=warning
contacts_inviteBackground=accent
contacts_inviteText=on_accent@A
contextProgressInner1=accent
contextProgressInner2=accent2
contextProgressInner3=accent3
contextProgressInner4=accent4
contextProgressOuter1=accent
contextProgressOuter2=accent2
contextProgressOuter3=accent3
contextProgressOuter4=accent4
dialogBackground=bg_hi
dialogBackgroundGray=bg_hi
dialogButton=accent
dialogButtonSelector=accent@44
dialogCardShadow=#00000000
dialogCameraIcon=on_accent@A
dialogCheckboxSquareBackground=accent
dialogCheckboxSquareCheck=on_accent@A
dialogCheckboxSquareDisabled=subtext
dialogCheckboxSquareUnchecked=subtext
dialogEmptyImage=text
dialogEmptyText=text
dialogFloatingButton=accent
dialogFloatingButtonPressed=accent2
dialogFloatingIcon=on_accent@A
dialogGiftsBackground=accent
dialogGiftsTabText=text
dialogGrayLine=divider
dialogIcon=text
dialogInputField=subtext
dialogInputFieldActivated=accent
dialogLineProgress=accent
dialogLineProgressBackground=seek_bg
dialogLinkSelection=accent@44
dialogRadioBackground=subtext
dialogRadioBackgroundChecked=accent
dialogReactionMentionBackground=accent
dialogRoundCheckBox=accent
dialogRoundCheckBoxCheck=on_accent@A
dialogScrollGlow=bg@A
dialogSearchBackground=panel@A
dialogSearchHint=subtext
dialogSearchIcon=text
dialogSearchText=text
dialogShadowLine=divider
dialogSwipeRemove=danger
dialogTextBlack=text
dialogTextBlue=accent
dialogTextBlue2=accent2
dialogTextBlue4=accent
dialogTextGray=subtext
dialogTextGray2=subtext
dialogTextGray3=subtext
dialogTextGray4=subtext
dialogTextHint=subtext
dialogTextLink=link
dialogTopBackground=accent
dialog_inlineProgress=accent
dialog_inlineProgressBackground=seek_bg
dialog_liveLocationProgress=accent
divider=divider@66
emptyListPlaceholder=subtext
fastScrollActive=accent
fastScrollInactive=subtext
fastScrollText=on_accent@A
featuredStickers_addButton=accent
featuredStickers_addButtonPressed=accent2
featuredStickers_addedIcon=accent
featuredStickers_buttonProgress=accent
featuredStickers_buttonText=on_accent@A
featuredStickers_removeButtonText=danger
featuredStickers_unread=accent
files_folderIcon=on_accent
files_folderIconBackground=accent
files_iconText=on_accent
fill_RedNormal=danger
fill_RedDark=danger
gift_ribbon=accent
gift_ribbon_soldout=accent2
graySection=subtext
groupcreate_cursor=accent
groupcreate_hintText=subtext
groupcreate_sectionShadow=divider
groupcreate_sectionText=text
groupcreate_spanBackground=panel@A
groupcreate_spanDelete=accent
groupcreate_spanText=text
inappPlayerBackground=bg_hi
inappPlayerClose=text
inappPlayerPerformer=subtext
inappPlayerPlayPause=accent
inappPlayerTitle=text
iv_ab_progress=accent
iv_background=#00000000
iv_backgroundGray=#00000000
iv_navigationBackground=#00000000
key_chat_messagePanelVoiceLock=text
key_chat_messagePanelVoiceLockBackground=accent
key_chat_messagePanelVoiceLockShadow=#00000000
key_graySectionText=text
key_player_progressCachedBackground=subtext
key_sheet_other=text
key_sheet_scrollUp=accent
listSelectorSDK21=accent@22
location_actionActiveIcon=accent
location_actionBackground=accent
location_actionIcon=text
location_actionPressedBackground=accent2
location_liveLocationProgress=accent
location_placeLocationBackground=accent
location_sendLiveLocationBackground=accent
location_sendLiveLocationIcon=on_accent@A
location_sendLiveLocationText=on_accent@A
location_sendLocationBackground=accent
location_sendLocationIcon=on_accent@A
location_sendLocationText=on_accent@A
login_progressInner=accent
login_progressOuter=accent2
passport_authorizeBackground=accent
passport_authorizeBackgroundSelected=accent2
passport_authorizeText=on_accent@A
picker_badge=accent
picker_badgeText=on_accent@A
picker_disabledButton=subtext
picker_enabledButton=accent
player_actionBarItems=text
player_actionBarSelector=accent@44
player_actionBarSubtitle=subtext
player_actionBarTitle=text
player_background=bg_hi
player_button=text
player_buttonActive=accent
player_progress=accent
player_progressBackground=bg@A
player_time=text
premiumCoinGradient1=accent
premiumCoinGradient2=accent2
premiumGradient0=accent
premiumGradient1=accent2
premiumGradient2=accent3
premiumGradient3=accent4
premiumGradient4=accent5
premiumGradientBackground1=accent
premiumGradientBackground2=accent2
premiumGradientBackground3=accent3
premiumGradientBackground4=accent4
premiumGradientBackgroundOverlay=accent
premiumGradientBottomSheet1=accent
premiumGradientBottomSheet2=accent2
premiumGradientBottomSheet3=accent3
premiumStarGradient1=accent
premiumStarGradient2=accent2
premiumStartSmallStarsColor=accent
premiumStartSmallStarsColor2=accent2
profile_actionBackground=accent
profile_actionIcon=on_accent@A
profile_actionPressedBackground=accent2
profile_creatorIcon=accent
profile_status=on_accent@cc
profile_tabSelectedLine=accent
profile_tabSelectedText=accent
profile_tabSelector=accent@44
profile_tabText=subtext
profile_title=on_accent
profile_verifiedBackground=accent
profile_verifiedCheck=on_accent@A
progressCircle=accent
radioBackground=subtext
radioBackgroundChecked=accent
reactionStarSelector=accent
returnToCallBackground=accent
returnToCallMutedBackground=accent2
returnToCallText=on_accent@A
sessions_devicesImage=text
sharedMedia_linkPlaceholder=panel@A
sharedMedia_linkPlaceholderText=text
sharedMedia_photoPlaceholder=panel@A
sharedMedia_startStopLoadIcon=accent
statisticChartActiveLine=accent
statisticChartActivePickerChart=accent
statisticChartLineEmpty=subtext
statisticChartLine_blue=accent
statisticChartLine_cyan=accent2
statisticChartLine_golden=warning
statisticChartLine_green=success
statisticChartLine_indigo=accent4
statisticChartLine_lightblue=accent5
statisticChartLine_lightgreen=accent7
statisticChartLine_orange=warning
statisticChartLine_purple=accent6
statisticChartLine_red=danger
statisticChartRipple=accent
statisticChartSignature=accent
statisticChartSignatureAlpha=accent
stickers_menu=text
stickers_menuSelector=text@33
stories_circle_closeFriends1=success
stories_circle_closeFriends2=accent5
stories_circle_dialog1=accent
stories_circle_dialog2=accent2
stories_circle1=accent
stories_circle2=accent2
switch2Track=seek_bg
switch2TrackChecked=accent
switchTrack=seek_bg
switchTrackBlue=seek_bg
switchTrackBlueChecked=accent
switchTrackBlueSelector=accent@44
switchTrackBlueSelectorChecked=accent@44
switchTrackBlueThumb=text
switchTrackBlueThumbChecked=on_accent
switchTrackChecked=accent
table_background=panel
table_border=divider
text_RedBold=danger
text_RedRegular=danger
topics_unreadCounter=accent
topics_unreadCounterMuted=subtext
undo_background=bg_hi@ee
undo_cancelColor=text
undo_infoColor=text
voipgroup_actionBar=bg_lo
voipgroup_actionBarItems=text
voipgroup_actionBarItemsSelector=accent@44
voipgroup_actionBarUnscrolled=bg_lo
voipgroup_checkMenu=accent
voipgroup_connectingProgress=accent
voipgroup_dialogBackground=bg
voipgroup_disabledButton=bg_hi
voipgroup_disabledButtonActive=bg_hi
voipgroup_disabledButtonActiveScrolled=bg_hi
voipgroup_inviteMembersBackground=accent
voipgroup_lastSeenText=text
voipgroup_lastSeenTextUnscrolled=text
voipgroup_leaveButton=danger
voipgroup_leaveButtonScrolled=danger
voipgroup_leaveCallMenu=danger
voipgroup_listeningText=text
voipgroup_listSelector=accent@44
voipgroup_listViewBackground=bg
voipgroup_listViewBackgroundUnscrolled=bg
voipgroup_muteButton=accent
voipgroup_muteButton2=accent2
voipgroup_muteButton3=accent3
voipgroup_mutedByAdminGradient=accent
voipgroup_mutedByAdminGradient2=accent2
voipgroup_mutedByAdminGradient3=accent3
voipgroup_mutedByAdminIcon=text
voipgroup_mutedByAdminMuteButton=accent
voipgroup_mutedByAdminMuteButtonDisabled=accent
voipgroup_mutedIcon=text
voipgroup_mutedIconUnscrolled=text
voipgroup_nameText=text
voipgroup_overlayAlertGradientMuted=accent
voipgroup_overlayAlertGradientMuted2=accent2
voipgroup_overlayAlertGradientUnmuted=accent
voipgroup_overlayAlertGradientUnmuted2=accent2
voipgroup_overlayAlertMutedByAdmin=accent
voipgroup_overlayAlertMutedByAdmin2=accent2
voipgroup_overlayBlue1=accent
voipgroup_overlayBlue2=accent2
voipgroup_overlayGreen1=success
voipgroup_overlayGreen2=accent5
voipgroup_rtmpButton=accent
voipgroup_scrollUp=accent
voipgroup_searchBackground=panel
voipgroup_searchPlaceholder=subtext
voipgroup_searchText=text
voipgroup_soundButton=accent
voipgroup_soundButton2=accent2
voipgroup_soundButtonActive=accent
voipgroup_soundButtonActive2=accent2
voipgroup_soundButtonActive2Scrolled=accent2
voipgroup_soundButtonActiveScrolled=accent
voipgroup_speakingText=text
voipgroup_topPanelBlue1=accent
voipgroup_topPanelBlue2=accent2
voipgroup_topPanelGray=bg_hi
voipgroup_topPanelGreen1=success
voipgroup_topPanelGreen2=accent
voipgroup_unmuteButton=accent
voipgroup_unmuteButton2=accent2
voipgroup_windowBackgroundWhiteInputField=accent
voipgroup_windowBackgroundWhiteInputFieldActivated=accent
windowBackgroundChecked=accent
windowBackgroundCheckText=on_accent@A
windowBackgroundGray=bg_lo@A
windowBackgroundGrayShadow=#00000000
windowBackgroundUnchecked=text
windowBackgroundWhite=bg@A
windowBackgroundWhiteBlackText=text
windowBackgroundWhiteBlueButton=accent
windowBackgroundWhiteBlueHeader=accent
windowBackgroundWhiteBlueIcon=accent
windowBackgroundWhiteBlueText=accent
windowBackgroundWhiteBlueText2=accent2
windowBackgroundWhiteBlueText3=accent
windowBackgroundWhiteBlueText4=accent
windowBackgroundWhiteBlueText5=accent
windowBackgroundWhiteBlueText6=accent
windowBackgroundWhiteBlueText7=accent
windowBackgroundWhiteGrayIcon=subtext
windowBackgroundWhiteGrayText=subtext
windowBackgroundWhiteGrayText2=subtext
windowBackgroundWhiteGrayText3=subtext
windowBackgroundWhiteGrayText4=subtext
windowBackgroundWhiteGrayText5=subtext
windowBackgroundWhiteGrayText6=subtext
windowBackgroundWhiteGrayText7=subtext
windowBackgroundWhiteGrayText8=subtext
windowBackgroundWhiteGreenText=success
windowBackgroundWhiteGreenText2=success
windowBackgroundWhiteHintText=subtext
windowBackgroundWhiteInputField=subtext
windowBackgroundWhiteInputFieldActivated=accent
windowBackgroundWhiteLinkSelection=accent@44
windowBackgroundWhiteLinkText=link
windowBackgroundWhiteValueText=accent
chat_wallpaper=#00000000
chat_wallpaper_gradient_to=#00000000
key_chat_wallpaper_gradient_to2=#00000000
key_chat_wallpaper_gradient_to3=#00000000
dialogTextRed=danger
dialogTextRed2=danger
dialogTextBlue3=accent
dialogInputFieldText=text
dialogBadgeBackground=accent
dialogBadgeText=on_accent@A
windowBackgroundWhiteRadius=bg@A
windowBackgroundWhiteRedText=danger
windowBackgroundWhiteRedText2=danger
windowBackgroundWhiteRedText3=danger
windowBackgroundWhiteRedText4=danger
windowBackgroundWhiteRedText5=danger
windowBackgroundWhiteRedText6=danger
windowBackgroundWhiteGrayLine=divider
windowBackgroundGrayLine=divider
profile_adminIcon=accent
switchThumb=text
switchThumbChecked=on_accent
chat_inReplyBackground=text@28
chat_outReplyBackground=text@28
chat_replyPanelMessage=text
chat_attachAudioIcon=on_accent
chat_attachContactIcon=on_accent
chat_attachFileIcon=on_accent
chat_attachGalleryIcon=on_accent
chat_attachLocationIcon=on_accent
chat_attachPollIcon=on_accent
chat_attachMediaBanBackground=bg_hi
chat_attachMediaBanText=text
chat_emojiPanelBadgeBackground=accent
chat_emojiPanelBadgeText=on_accent
chat_outLocationBackground=accent"""

_OUT_MAP = {
    "text": "out_text", "subtext": "out_subtext",
    "accent": "out_accent", "accent2": "out_accent2", "accent3": "out_accent2",
    "link": "out_link", "seek_bg": "out_seek_bg", "seek_fill": "out_seek_fill",
    "panel": "out_panel", "sel": "out_sel", "reply_line": "out_accent2",
    "danger": "out_danger", "success": "out_success",
}


def _is_out_key(key):
    return key.startswith("chat_out") or key in ("chat_messageTextOut", "chat_messageLinkOut")


def _render_theme(roles, alpha_hex, grad=False):
    out = []
    for raw in SPEC.splitlines():
        raw = raw.strip()
        if not raw or "=" not in raw:
            continue
        key, val = raw.split("=", 1)
        if val.startswith("#"):
            out.append(raw)
            continue
        role, _, al = val.partition("@")
        if _is_out_key(key):
            role = _OUT_MAP.get(role, role)
        col = roles.get(role)
        if col is None:
            logger.warning("TgTheme: unknown role %s for %s", role, key)
            col = roles["accent"]
        a = alpha_hex if al == "A" else (al or "ff")
        out.append("%s=#%s%s" % (key, a, _to_hex(col)))

    if grad:
        for k, r in (("chat_outBubbleGradient1", "out_grad1"),
                     ("chat_outBubbleGradient2", "out_grad2"),
                     ("chat_outBubbleGradient3", "out_bubble")):
            out.append("%s=#ff%s" % (k, _to_hex(roles[r])))
    return "\n".join(out) + "\n", len(out)


# ======================================================================
#                                МОДУЛЬ
# ======================================================================

@loader.tds
class tgtheme(loader.Module):
    """Module that creates an android-theme from a photo: every photo color is used, every element is colored"""

    strings = {
        "name": "TgTheme",
        "no_photo": "<b>Reply to a photo</b>",
        "processing": "<b>🎨 Building the theme...</b>",
        "done": (
            "<b>✨ Theme ready!</b>\n"
            "<b>🎭 Type:</b> {}\n"
            "<b>🔹 Transparency:</b> {}%\n"
            "<b>🎨 Photo colors found:</b> {}\n"
            "<b>🖌 Accents:</b> {}\n"
            "<b>🧩 Elements colored:</b> {}"
        ),
        "dark": "🌙 Dark",
        "light": "☀️ Light",
        "error": "<b>❌ Error:</b> {}",
    }

    strings_ru = {
        "_cls_doc": "Модуль, который создаёт тг-тему по фото: используются все цвета фото, раскрашен каждый элемент",
        "no_photo": "<b>Ответьте на фото</b>",
        "processing": "<b>🎨 Собираю тему...</b>",
        "done": (
            "<b>✨ Тема готова!</b>\n"
            "<b>🎭 Тип:</b> {}\n"
            "<b>🔹 Прозрачность:</b> {}%\n"
            "<b>🎨 Цветов найдено в фото:</b> {}\n"
            "<b>🖌 Акценты:</b> {}\n"
            "<b>🧩 Элементов раскрашено:</b> {}"
        ),
        "dark": "🌙 Тёмная",
        "light": "☀️ Светлая",
        "error": "<b>❌ Ошибка:</b> {}",
    }

    def _theme_wallpaper(self, img, max_size=1920):
        """Создаёт обои из изображения"""
        output = io.BytesIO()
        img_copy = img.copy()
        if img_copy.mode != "RGB":
            img_copy = img_copy.convert("RGB")
        if max(img_copy.size) > max_size:
            scale = max_size / max(img_copy.size)
            img_copy = img_copy.resize(
                (int(img_copy.size[0] * scale), int(img_copy.size[1] * scale)),
                Image.LANCZOS,
            )
        img_copy.save(output, format="JPEG", quality=88, optimize=True)
        return output.getvalue()

    @staticmethod
    def _open_image(photo_bytes):
        img = Image.open(io.BytesIO(photo_bytes))
        if ImageOps is not None:
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass
        if img.mode in ("RGBA", "LA", "P"):
            rgba = img.convert("RGBA")
            base = Image.new("RGBA", rgba.size, (128, 128, 128, 255))
            base.alpha_composite(rgba)
            return base.convert("RGB")
        return img.convert("RGB")

    def _process_photo(self, photo_bytes, alpha_hex="e6", force=None, grad=False):
        img = self._open_image(photo_bytes)
        colors = _extract_palette(img)
        roles, meta = _build_palette(colors, force, grad)
        theme, keys = _render_theme(roles, alpha_hex, grad)
        wallpaper = self._theme_wallpaper(img)
        meta["keys"] = keys
        data = theme.encode("utf-8") + b"\n\nWPS\n" + wallpaper + b"\nWPE\n"
        return data, meta

    @loader.command(
        ru_doc="[прозрачность 0-100] [dark|light] [grad] — тг-тема по фото (все цвета фото, каждая деталь раскрашена)"
    )
    async def android(self, message):
        """[transparency 0-100] [dark|light] [grad] — tg-theme from a photo (all photo colors used, every element colored)"""
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

            transparency, force, grad = 90, None, False
            for a in (utils.get_args_raw(message) or "").lower().split():
                if a.isdigit():
                    transparency = max(0, min(100, int(a)))
                elif a in ("dark", "d", "тёмная", "темная", "тем"):
                    force = "dark"
                elif a in ("light", "l", "светлая", "свет"):
                    force = "light"
                elif a in ("grad", "gradient", "град"):
                    grad = True
            alpha = "%02x" % int(transparency / 100 * 255)

            loop = asyncio.get_running_loop()
            theme_bytes, meta = await loop.run_in_executor(
                None, self._process_photo, photo_bytes, alpha, force, grad
            )

            file = io.BytesIO(theme_bytes)
            file.name = "tgtheme_%s.attheme" % ("dark" if meta["is_dark"] else "light")

            swatches = " ".join("<code>%s</code>" % c for c in meta["accents"])
            await utils.answer(
                message,
                self.strings["done"].format(
                    self.strings["dark"] if meta["is_dark"] else self.strings["light"],
                    transparency,
                    meta["colors"],
                    swatches,
                    meta["keys"],
                ),
                file=file,
            )

        except Exception as e:
            logger.exception("TgTheme error")
            await utils.answer(message, self.strings["error"].format(str(e)))
