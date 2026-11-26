# meta developer: @H_SunMods, @WersModules
# requires: Pillow
# meta pic: https://r2.fakecrime.bio/uploads/47308ab9-6035-4e7d-bc96-6b58f864bb33.jpg
# meta banner: https://r2.fakecrime.bio/uploads/47308ab9-6035-4e7d-bc96-6b58f864bb33.jpg
# meta fhsdesc: Theme, Темы, iOS, Sunnex, SunnexGB, H_SunMods, Wersixx, Wers1xx, WersModules

import asyncio
import colorsys
import io
import logging
import math
import re

from PIL import Image
from .. import loader, utils

try:
    from PIL import ImageOps
except Exception:
    ImageOps = None

logger = logging.getLogger(__name__)


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _to_hex(c):
    return "{:02x}{:02x}{:02x}".format(*[int(max(0, min(255, round(v)))) for v in c])


def _lin(v):
    v /= 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _lum(c):
    return 0.2126 * _lin(c[0]) + 0.7152 * _lin(c[1]) + 0.0722 * _lin(c[2])


def _cr(a, b):
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


def _extract_palette(img, limit=32):
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

    if len(acc) < 8:
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

    danger0 = semantic(40, 25, 0.005)
    success0 = semantic(140, 35, 0.37)
    warning0 = semantic(78, 22, 0.10)

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

    cons_acc = [(b, 4.5) for b in surfaces] + [(on_accent, 4.2)]
    A = [_fit(a, cons_acc, dark) for a in acc]
    danger = _fit(danger0, cons_acc, dark)
    success = _fit(success0, cons_acc, dark)
    warning = _fit(warning0, cons_acc, dark)

    link = _fit(_mix(A[0], text, 0.25), [(b, 5.0) for b in surfaces], dark)

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


SPEC = """
intro_statusBar=!bar
intro_primaryText=text
intro_accentText=accent
intro_disabledText=subtext
intro_startButton=accent
intro_dot=seek_bg
passcode_bg_top=bg_lo
passcode_bg_bottom=bg
passcode_button=bg_hi
passcode_button_text=text
root_statusBar=!bar
root_tabBar_background=action_bar@A
root_tabBar_separator=divider
root_tabBar_icon=subtext
root_tabBar_selectedIcon=accent
root_tabBar_text=subtext
root_tabBar_selectedText=accent
root_tabBar_badgeBackground=danger
root_tabBar_badgeStroke=action_bar
root_tabBar_badgeText=on_accent
root_navBar_button=accent
root_navBar_disabledButton=subtext
root_navBar_primaryText=text
root_navBar_secondaryText=subtext
root_navBar_control=subtext
root_navBar_accentText=accent
root_navBar_background=action_bar@A
root_navBar_opaqueBackground=action_bar
root_navBar_separator=divider
root_navBar_badgeFill=danger
root_navBar_badgeStroke=action_bar
root_navBar_badgeText=on_accent
root_navBar_segmentedBg=panel
root_navBar_segmentedFg=seek_bg
root_navBar_segmentedText=text
root_navBar_segmentedDivider=divider
root_searchBar_background=action_bar
root_searchBar_accent=accent
root_searchBar_inputFill=panel
root_searchBar_inputText=text
root_searchBar_inputPlaceholderText=subtext
root_searchBar_inputIcon=subtext
root_searchBar_inputClearButton=subtext
root_searchBar_separator=divider
root_keyboard=!kb
list_blocksBg=bg_lo
list_plainBg=bg
list_primaryText=text
list_secondaryText=subtext
list_disabledText=subtext@99
list_accent=accent
list_highlighted=accent2
list_destructive=danger
list_placeholderText=subtext
list_itemBlocksBg=bg
list_itemHighlightedBg=sel
list_blocksSeparator=divider
list_plainSeparator=divider
list_disclosureArrow=subtext
list_sectionHeaderText=accent
list_freeText=subtext
list_freeTextError=danger
list_freeTextSuccess=success
list_freeMonoIcon=subtext
list_switch_frame=seek_bg
list_switch_handle=#FFFFFF
list_switch_content=accent
list_switch_positive=success
list_switch_negative=danger
list_disclosureActions_neutral1_bg=accent2
list_disclosureActions_neutral1_fg=on_accent
list_disclosureActions_neutral2_bg=accent3
list_disclosureActions_neutral2_fg=on_accent
list_disclosureActions_destructive_bg=danger
list_disclosureActions_destructive_fg=on_accent
list_disclosureActions_constructive_bg=success
list_disclosureActions_constructive_fg=on_accent
list_disclosureActions_accent_bg=accent
list_disclosureActions_accent_fg=on_accent
list_disclosureActions_warning_bg=warning
list_disclosureActions_warning_fg=on_accent
list_disclosureActions_inactive_bg=seek_bg
list_disclosureActions_inactive_fg=text
list_check_bg=accent
list_check_stroke=subtext
list_check_fg=on_accent
list_controlSecondary=subtext
list_freeInputField_bg=panel
list_freeInputField_stroke=divider
list_freeInputField_placeholder=subtext
list_freeInputField_primary=text
list_freeInputField_control=subtext
list_itemInputField_bg=panel
list_itemInputField_stroke=divider
list_itemInputField_placeholder=subtext
list_itemInputField_primary=text
list_itemInputField_control=subtext
list_mediaPlaceholder=panel
list_scrollIndicator=text@4C
list_pageIndicatorInactive=text@4C
list_pageIndicatorActive=accent
list_inputClearButton=subtext
list_itemBarChart_color1=accent
list_itemBarChart_color2=accent2
list_itemBarChart_color3=seek_bg
chatList_bg=bg
chatList_itemSeparator=divider
chatList_itemBg=bg
chatList_pinnedItemBg=panel
chatList_pinnedItemHighlightedBg=sel
chatList_itemHighlightedBg=sel
chatList_itemSelectedBg=sel
chatList_title=text
chatList_secretTitle=success
chatList_dateText=subtext
chatList_authorName=text
chatList_messageText=subtext
chatList_messageHighlightedText=text
chatList_messageDraftText=danger
chatList_checkmark=accent
chatList_pendingIndicator=subtext
chatList_failedFill=danger
chatList_failedFg=on_accent
chatList_muteIcon=subtext
chatList_unreadBadgeActiveBg=accent
chatList_unreadBadgeActiveText=on_accent
chatList_unreadBadgeInactiveBg=subtext
chatList_unreadBadgeInactiveText=on_accent
chatList_reactionBadgeActiveBg=accent
chatList_reactionBadgeActiveFg=on_accent
chatList_reactionBadgeInactiveBg=subtext
chatList_reactionBadgeInactiveFg=on_accent
chatList_pinnedBadge=subtext
chatList_pinnedSearchBar=panel
chatList_regularSearchBar=panel
chatList_sectionHeaderBg=bg_lo
chatList_sectionHeaderText=subtext
chatList_verifiedIconBg=accent
chatList_verifiedIconFg=on_accent
chatList_secretIcon=success
chatList_pinnedArchiveAvatar_background_top=accent2
chatList_pinnedArchiveAvatar_background_bottom=accent
chatList_pinnedArchiveAvatar_foreground=on_accent
chatList_unpinnedArchiveAvatar_background_top=seek_bg
chatList_unpinnedArchiveAvatar_background_bottom=seek_bg
chatList_unpinnedArchiveAvatar_foreground=text
chatList_onlineDot=success
chatList_storyUnseen_top=accent
chatList_storyUnseen_bottom=accent2
chatList_storySeen_top=seek_bg
chatList_storySeen_bottom=seek_bg
chatList_storyUnseenPrivate_top=success
chatList_storyUnseenPrivate_bottom=accent5
chat_message_incoming_bubble_withWp_bg=in_bubble
chat_message_incoming_bubble_withWp_gradientBg=in_bubble
chat_message_incoming_bubble_withWp_highlightedBg=sel
chat_message_incoming_bubble_withWp_stroke=#00000000
chat_message_incoming_bubble_withoutWp_bg=in_bubble
chat_message_incoming_bubble_withoutWp_gradientBg=in_bubble
chat_message_incoming_bubble_withoutWp_highlightedBg=sel
chat_message_incoming_bubble_withoutWp_stroke=#00000000
chat_message_incoming_primaryText=text
chat_message_incoming_secondaryText=subtext
chat_message_incoming_linkText=link
chat_message_incoming_linkHighlight=link@7F
chat_message_incoming_scam=danger
chat_message_incoming_textHighlight=warning@80
chat_message_incoming_accentText=accent
chat_message_incoming_accentControl=accent
chat_message_incoming_mediaActiveControl=accent
chat_message_incoming_mediaInactiveControl=accent@66
chat_message_incoming_mediaControlInnerBg=in_bubble
chat_message_incoming_pendingActivity=subtext
chat_message_incoming_fileTitle=text
chat_message_incoming_fileDescription=subtext
chat_message_incoming_fileDuration=subtext
chat_message_incoming_mediaPlaceholder=panel
chat_message_incoming_polls_radioButton=subtext
chat_message_incoming_polls_radioProgress=accent
chat_message_incoming_polls_highlight=accent@1E
chat_message_incoming_polls_separator=divider
chat_message_incoming_polls_bar=accent
chat_message_incoming_polls_barIconForeground=on_accent
chat_message_incoming_polls_barPositive=success
chat_message_incoming_polls_barNegative=danger
chat_message_incoming_actionButtonsBg_withWp=bg_lo@99
chat_message_incoming_actionButtonsBg_withoutWp=bg_lo@99
chat_message_incoming_actionButtonsStroke_withWp=divider@AA
chat_message_incoming_actionButtonsStroke_withoutWp=divider@AA
chat_message_incoming_actionButtonsText_withWp=plain_text
chat_message_incoming_actionButtonsText_withoutWp=plain_text
chat_message_incoming_textSelection=accent@33
chat_message_incoming_textSelectionKnob=accent
chat_message_incoming_bubble_withWp_reactionInactiveBg=accent@33
chat_message_incoming_bubble_withWp_reactionInactiveFg=accent
chat_message_incoming_bubble_withWp_reactionActiveBg=accent
chat_message_incoming_bubble_withWp_reactionActiveFg=on_accent
chat_message_incoming_bubble_withoutWp_reactionInactiveBg=accent@33
chat_message_incoming_bubble_withoutWp_reactionInactiveFg=accent
chat_message_incoming_bubble_withoutWp_reactionActiveBg=accent
chat_message_incoming_bubble_withoutWp_reactionActiveFg=on_accent
chat_message_outgoing_bubble_withWp_bg=out_bubble
chat_message_outgoing_bubble_withWp_gradientBg=out_bubble
chat_message_outgoing_bubble_withWp_highlightedBg=sel
chat_message_outgoing_bubble_withWp_stroke=#00000000
chat_message_outgoing_bubble_withoutWp_bg=out_bubble
chat_message_outgoing_bubble_withoutWp_gradientBg=out_bubble
chat_message_outgoing_bubble_withoutWp_highlightedBg=sel
chat_message_outgoing_bubble_withoutWp_stroke=#00000000
chat_message_outgoing_primaryText=text
chat_message_outgoing_secondaryText=subtext
chat_message_outgoing_linkText=link
chat_message_outgoing_linkHighlight=link@7F
chat_message_outgoing_scam=danger
chat_message_outgoing_textHighlight=warning@80
chat_message_outgoing_accentText=accent
chat_message_outgoing_accentControl=accent
chat_message_outgoing_mediaActiveControl=text
chat_message_outgoing_mediaInactiveControl=text@7F
chat_message_outgoing_mediaControlInnerBg=out_bubble
chat_message_outgoing_pendingActivity=subtext
chat_message_outgoing_fileTitle=text
chat_message_outgoing_fileDescription=subtext
chat_message_outgoing_fileDuration=subtext
chat_message_outgoing_mediaPlaceholder=panel
chat_message_outgoing_polls_radioButton=text
chat_message_outgoing_polls_radioProgress=text
chat_message_outgoing_polls_highlight=text@1E
chat_message_outgoing_polls_separator=text@7F
chat_message_outgoing_polls_bar=text
chat_message_outgoing_polls_barIconForeground=out_bubble
chat_message_outgoing_polls_barPositive=success
chat_message_outgoing_polls_barNegative=danger
chat_message_outgoing_actionButtonsBg_withWp=bg_lo@99
chat_message_outgoing_actionButtonsBg_withoutWp=bg_lo@99
chat_message_outgoing_actionButtonsStroke_withWp=divider@AA
chat_message_outgoing_actionButtonsStroke_withoutWp=divider@AA
chat_message_outgoing_actionButtonsText_withWp=plain_text
chat_message_outgoing_actionButtonsText_withoutWp=plain_text
chat_message_outgoing_textSelection=text@33
chat_message_outgoing_textSelectionKnob=text
chat_message_outgoing_bubble_withWp_reactionInactiveBg=text@33
chat_message_outgoing_bubble_withWp_reactionInactiveFg=text
chat_message_outgoing_bubble_withWp_reactionActiveBg=text
chat_message_outgoing_bubble_withWp_reactionActiveFg=out_bubble
chat_message_outgoing_bubble_withoutWp_reactionInactiveBg=text@33
chat_message_outgoing_bubble_withoutWp_reactionInactiveFg=text
chat_message_outgoing_bubble_withoutWp_reactionActiveBg=text
chat_message_outgoing_bubble_withoutWp_reactionActiveFg=out_bubble
chat_message_freeform_withWp_bg=bg_hi
chat_message_freeform_withWp_gradientBg=bg_hi
chat_message_freeform_withWp_highlightedBg=sel
chat_message_freeform_withWp_stroke=divider
chat_message_freeform_withoutWp_bg=bg_hi
chat_message_freeform_withoutWp_gradientBg=bg_hi
chat_message_freeform_withoutWp_highlightedBg=sel
chat_message_freeform_withoutWp_stroke=divider
chat_message_infoPrimaryText=text
chat_message_infoLinkText=link
chat_message_outgoingCheck=accent
chat_message_mediaDateAndStatusBg=bg_lo@99
chat_message_mediaDateAndStatusText=plain_text
chat_message_shareButtonBg_withWp=bg_lo@99
chat_message_shareButtonBg_withoutWp=bg_lo@99
chat_message_shareButtonStroke_withWp=divider@AA
chat_message_shareButtonStroke_withoutWp=divider@AA
chat_message_shareButtonFg_withWp=plain_text
chat_message_shareButtonFg_withoutWp=plain_text
chat_message_mediaOverlayControl_bg=bg_lo@99
chat_message_mediaOverlayControl_fg=plain_text
chat_message_selectionControl_bg=accent
chat_message_selectionControl_stroke=text
chat_message_selectionControl_fg=on_accent
chat_message_deliveryFailed_bg=danger
chat_message_deliveryFailed_fg=on_accent
chat_message_mediaHighlightOverlay=plain_text@55
chat_message_stickerPlaceholder_withWp=panel
chat_message_stickerPlaceholder_withoutWp=panel
chat_message_stickerPlaceholderShimmer_withWp=plain_text@26
chat_message_stickerPlaceholderShimmer_withoutWp=plain_text@26
chat_serviceMessage_components_withDefaultWp_bg=bg_lo@AA
chat_serviceMessage_components_withDefaultWp_primaryText=plain_text
chat_serviceMessage_components_withDefaultWp_linkHighlight=plain_text@1E
chat_serviceMessage_components_withDefaultWp_scam=danger
chat_serviceMessage_components_withDefaultWp_dateFillStatic=bg_lo@99
chat_serviceMessage_components_withDefaultWp_dateFillFloat=bg_lo@55
chat_serviceMessage_components_withCustomWp_bg=bg_lo@AA
chat_serviceMessage_components_withCustomWp_primaryText=plain_text
chat_serviceMessage_components_withCustomWp_linkHighlight=plain_text@1E
chat_serviceMessage_components_withCustomWp_scam=danger
chat_serviceMessage_components_withCustomWp_dateFillStatic=bg_lo@99
chat_serviceMessage_components_withCustomWp_dateFillFloat=bg_lo@55
chat_serviceMessage_unreadBarBg=bg_hi
chat_serviceMessage_unreadBarStroke=bg_hi
chat_serviceMessage_unreadBarText=text
chat_serviceMessage_dateText_withWp=plain_text
chat_serviceMessage_dateText_withoutWp=plain_text
chat_inputPanel_panelBg=action_bar
chat_inputPanel_panelSeparator=divider
chat_inputPanel_panelControlAccent=accent
chat_inputPanel_panelControl=accent
chat_inputPanel_panelControlDisabled=accent@7F
chat_inputPanel_panelControlDestructive=danger
chat_inputPanel_inputBg=panel
chat_inputPanel_inputStroke=divider
chat_inputPanel_inputPlaceholder=subtext
chat_inputPanel_inputText=text
chat_inputPanel_inputControl=subtext
chat_inputPanel_actionControlBg=accent
chat_inputPanel_actionControlFg=on_accent
chat_inputPanel_primaryText=text
chat_inputPanel_secondaryText=subtext
chat_inputPanel_mediaRecordDot=danger
chat_inputPanel_mediaRecordControl_button=accent
chat_inputPanel_mediaRecordControl_micLevel=accent@33
chat_inputPanel_mediaRecordControl_activeIcon=on_accent
chat_inputMediaPanel_panelSeparator=divider
chat_inputMediaPanel_panelIcon=subtext
chat_inputMediaPanel_panelHighlightedIconBg=panel
chat_inputMediaPanel_stickersBg=bg
chat_inputMediaPanel_stickersSectionText=subtext
chat_inputMediaPanel_stickersSearchBg=panel
chat_inputMediaPanel_stickersSearchPlaceholder=subtext
chat_inputMediaPanel_stickersSearchPrimary=text
chat_inputMediaPanel_stickersSearchControl=subtext
chat_inputMediaPanel_gifsBg=bg
chat_inputButtonPanel_panelBg=bg_lo
chat_inputButtonPanel_panelSeparator=divider
chat_inputButtonPanel_buttonBg=panel
chat_inputButtonPanel_buttonStroke=divider
chat_inputButtonPanel_buttonHighlightedBg=sel
chat_inputButtonPanel_buttonHighlightedStroke=divider
chat_inputButtonPanel_buttonText=text
chat_historyNav_bg=bg_hi
chat_historyNav_stroke=divider
chat_historyNav_fg=text
chat_historyNav_badgeBg=accent
chat_historyNav_badgeStroke=accent
chat_historyNav_badgeText=on_accent
actionSheet_dim=#0000007F
actionSheet_bgType=!bgtype
actionSheet_opaqueItemBg=bg_hi
actionSheet_itemBg=bg_hi@CC
actionSheet_opaqueItemHighlightedBg=sel
actionSheet_itemHighlightedBg=sel@BB
actionSheet_opaqueItemSeparator=divider
actionSheet_standardActionText=accent
actionSheet_destructiveActionText=danger
actionSheet_disabledActionText=subtext@99
actionSheet_primaryText=text
actionSheet_secondaryText=subtext
actionSheet_controlAccent=accent
actionSheet_inputBg=panel
actionSheet_inputHollowBg=panel
actionSheet_inputBorder=divider
actionSheet_inputPlaceholder=subtext
actionSheet_inputText=text
actionSheet_inputClearButton=subtext
actionSheet_checkContent=on_accent
contextMenu_dim=#00000099
contextMenu_background=bg_hi@D0
contextMenu_itemSeparator=text@26
contextMenu_sectionSeparator=bg_lo@66
contextMenu_itemBg=#00000000
contextMenu_itemHighlightedBg=text@26
contextMenu_primary=text
contextMenu_secondary=subtext
contextMenu_destructive=danger
notification_bg=bg_hi
notification_primaryText=text
notification_expanded_bgType=!bgtype
notification_expanded_navBar_background=bg_hi
notification_expanded_navBar_primaryText=text
notification_expanded_navBar_control=text
notification_expanded_navBar_separator=divider
chart_labels=subtext
chart_helperLines=subtext@59
chart_strongLines=subtext@59
chart_barStrongLines=subtext@72
chart_detailsText=text
chart_detailsArrow=subtext
chart_detailsView=bg_hi
chart_rangeViewFrame=seek_bg
chart_rangeViewMarker=text
premium_starFg=accent
premium_buttonBg_top=accent
premium_buttonBg_bottom=accent2
premium_buttonFg=on_accent
premium_badgeBg=accent
premium_badgeFg=on_accent
"""

_OUT_MAP = {
    "text": "out_text", "subtext": "out_subtext",
    "accent": "out_accent", "accent2": "out_accent2", "accent3": "out_accent2",
    "link": "out_link", "seek_bg": "out_seek_bg", "seek_fill": "out_seek_fill",
    "panel": "out_panel", "sel": "out_sel", "reply_line": "out_accent2",
    "danger": "out_danger", "success": "out_success",
}

_GRAD_KEYS = (
    "chat_message_outgoing_bubble_withWp_gradientBg",
    "chat_message_outgoing_bubble_withoutWp_gradientBg",
)

_VALUE_RE = re.compile(r"#[0-9A-F]{6}([0-9A-F]{2})?")


def _is_out_key(key):
    return key.startswith("chat_message_outgoing")


def _render_theme(roles, meta, alpha_hex, name, wallpaper, grad=False):
    dark = meta["is_dark"]
    roles = dict(roles)
    roles["plain_text"] = roles["text"]
    special = {
        "!bar": "white" if dark else "black",
        "!kb": "dark" if dark else "light",
        "!bgtype": "dark" if dark else "light",
    }

    lines = [
        "name: %s" % name,
        "basedOn: %s" % ("night" if dark else "day"),
        "dark: %s" % ("true" if dark else "false"),
        "wallpaper: %s" % wallpaper,
    ]
    for raw in SPEC.splitlines():
        raw = raw.strip()
        if not raw or "=" not in raw:
            continue
        key, val = raw.split("=", 1)
        if val in special:
            lines.append("%s: %s" % (key, special[val]))
            continue
        if val.startswith("#"):
            lines.append("%s: %s" % (key, val.upper()))
            continue
        if grad and key in _GRAD_KEYS:
            val = "out_grad1"
        role, _, al = val.partition("@")
        if _is_out_key(key):
            role = _OUT_MAP.get(role, role)
        col = roles.get(role)
        if col is None:
            logger.warning("TgThemeIOS: unknown role %s for %s", role, key)
            col = roles["accent"]
        a = alpha_hex if al == "A" else al
        value = "#" + _to_hex(col).upper() + (a.upper() if a and a.lower() != "ff" else "")
        lines.append("%s: %s" % (key, value))
    return "\n".join(lines) + "\n", len(lines) - 4


@loader.tds
class tgthemeios(loader.Module):
    """Module that creates an iOS Telegram theme (.tgios-theme) from a photo: every photo color is used, every element is colored"""

    strings = {
        "name": "TgThemeIOS",
        "no_photo": "<b>Reply to a photo</b>",
        "processing": "<b>🎨 Building the iOS theme...</b>",
        "done": (
            "<b>✨ iOS theme ready!</b>\n"
            "<b>🎭 Type:</b> {}\n"
            "<b>🔹 Transparency:</b> {}%\n"
            "<b>🎨 Photo colors found:</b> {}\n"
            "<b>🖌 Accents:</b> {}\n"
            "<b>🧩 Elements colored:</b> {}\n"
            "<b>🖼 Wallpaper:</b> {}\n\n"
            "<i>Open the file in Telegram on iPhone and tap «Apply».</i>"
        ),
        "dark": "🌙 Dark",
        "light": "☀️ Light",
        "wp_cloud": "your photo (cloud wallpaper)",
        "wp_link": "link you provided",
        "wp_color": "solid color. A .tgios-theme can't hold a photo, so set it manually: Settings → Appearance → Chat Background",
        "error": "<b>❌ Error:</b> {}",
    }

    strings_ru = {
        "_cls_doc": "Модуль, который создаёт тему Telegram для iOS (.tgios-theme) по фото: используются все цвета фото, раскрашен каждый элемент",
        "no_photo": "<b>Ответьте на фото</b>",
        "processing": "<b>🎨 Собираю iOS-тему...</b>",
        "done": (
            "<b>✨ iOS-тема готова!</b>\n"
            "<b>🎭 Тип:</b> {}\n"
            "<b>🔹 Прозрачность:</b> {}%\n"
            "<b>🎨 Цветов найдено в фото:</b> {}\n"
            "<b>🖌 Акценты:</b> {}\n"
            "<b>🧩 Элементов раскрашено:</b> {}\n"
            "<b>🖼 Обои:</b> {}\n\n"
            "<i>Откройте файл в Telegram на iPhone и нажмите «Применить».</i>"
        ),
        "dark": "🌙 Тёмная",
        "light": "☀️ Светлая",
        "wp_cloud": "ваше фото (облачные обои)",
        "wp_link": "ваша ссылка",
        "wp_color": "однотонный цвет. В .tgios-theme нельзя вложить фото, поставьте его вручную: Настройки → Оформление → Фон чата",
        "error": "<b>❌ Ошибка:</b> {}",
    }

    @staticmethod
    def _theme_wallpaper(img, max_size=1600):
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

    def _process_photo(self, photo_bytes, alpha_hex="e6", force=None, grad=False, wallpaper=None):
        img = self._open_image(photo_bytes)
        colors = _extract_palette(img)
        roles, meta = _build_palette(colors, force, grad)
        if not wallpaper:
            wallpaper = "#" + _to_hex(roles["bg"]).upper()
        theme, keys = _render_theme(roles, meta, alpha_hex, "TgTheme", wallpaper, grad)
        meta["keys"] = keys
        meta["wallpaper"] = wallpaper
        return theme.encode("utf-8"), meta

    async def _upload_wallpaper(self, photo_bytes):
        try:
            from telethon.tl import functions, types

            data = self._theme_wallpaper(self._open_image(photo_bytes))
            buf = io.BytesIO(data)
            buf.name = "wallpaper.jpg"
            uploaded = await self._client.upload_file(buf, file_name="wallpaper.jpg")
            wp = await self._client(
                functions.account.UploadWallPaperRequest(
                    file=uploaded,
                    mime_type="image/jpeg",
                    settings=types.WallPaperSettings(),
                )
            )
            slug = getattr(wp, "slug", None)
            return "https://t.me/bg/%s" % slug if slug else None
        except Exception:
            logger.warning("TgThemeIOS: wallpaper upload failed", exc_info=True)
            return None

    @loader.command(
        ru_doc="[прозрачность 0-100] [dark|light] [grad] [nowp] [ссылка t.me/bg/...] — iOS-тема (.tgios-theme) по фото"
    )
    async def ios(self, message):
        """[transparency 0-100] [dark|light] [grad] [nowp] [t.me/bg/... link] — iOS theme (.tgios-theme) from a photo"""
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

            transparency, force, grad, nowp, link = 90, None, False, False, None
            for a in (utils.get_args_raw(message) or "").split():
                al = a.lower()
                if al.isdigit():
                    transparency = max(0, min(100, int(al)))
                elif al in ("dark", "d", "тёмная", "темная", "тем"):
                    force = "dark"
                elif al in ("light", "l", "светлая", "свет"):
                    force = "light"
                elif al in ("grad", "gradient", "град"):
                    grad = True
                elif al in ("nowp", "nobg", "безобоев"):
                    nowp = True
                elif "t.me/bg/" in al:
                    link = a if a.startswith("http") else "https://" + a
            alpha = "%02x" % int(transparency / 100 * 255)

            wallpaper = link
            if wallpaper is None and not nowp:
                wallpaper = await self._upload_wallpaper(photo_bytes)

            loop = asyncio.get_running_loop()
            theme_bytes, meta = await loop.run_in_executor(
                None, self._process_photo, photo_bytes, alpha, force, grad, wallpaper
            )

            file = io.BytesIO(theme_bytes)
            file.name = "tgtheme_ios_%s.tgios-theme" % ("dark" if meta["is_dark"] else "light")

            if link:
                wp_text = self.strings["wp_link"]
            elif wallpaper:
                wp_text = self.strings["wp_cloud"]
            else:
                wp_text = self.strings["wp_color"]

            swatches = " ".join("<code>%s</code>" % c for c in meta["accents"])
            await utils.answer(
                message,
                self.strings["done"].format(
                    self.strings["dark"] if meta["is_dark"] else self.strings["light"],
                    transparency,
                    meta["colors"],
                    swatches,
                    meta["keys"],
                    wp_text,
                ),
                file=file,
            )

        except Exception as e:
            logger.exception("TgThemeIOS error")
            await utils.answer(message, self.strings["error"].format(str(e)))
