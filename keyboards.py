from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from config import TARGET_BOT_LINK, CHANNEL_LINK


def kb_subscribe(check_cb: str = "check_sub") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подписаться на канал", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="Я подписался →",       callback_data=check_cb)],
    ])


def kb_terms() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Далее →", callback_data="terms_accept")]
    ])


def kb_cancel_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✕  Отмена", callback_data="cancel_reg")]
    ])


def kb_cancel_with_skip_passport() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мне нет 18+", callback_data="skip_passport")],
        [InlineKeyboardButton(text="✕  Отмена",   callback_data="cancel_reg")],
    ])


def kb_send_contact() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отправить номер телефона", request_contact=True)],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def kb_remove() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def kb_access_granted() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перейти в Malik Shop Bot", url=TARGET_BOT_LINK)]
    ])


def kb_admin_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Поиск пользователя",   callback_data="admin_search")],
        [InlineKeyboardButton(text="Проверить базу",        callback_data="admin_check_db")],
        [InlineKeyboardButton(text="Список пользователей", callback_data="admin_all_users:0")],
        [InlineKeyboardButton(text="Статистика",           callback_data="admin_stats")],
        [InlineKeyboardButton(text="✕  Закрыть",           callback_data="admin_close")],
    ])


def kb_admin_search_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Назад", callback_data="admin_panel")]
    ])


def kb_search_results(users: list) -> InlineKeyboardMarkup:
    buttons = []
    for u in users:
        icon = {"approved": "✓", "rejected": "✗", "pending": "…"}.get(u.get("status",""), "·")
        if u['username']:
            label = f"@{u['username']}"
        elif u['first_name']:
            label = (u['first_name'] + (" " + u['last_name'] if u['last_name'] else "")).strip()
        else:
            label = str(u['user_id'])
        buttons.append([InlineKeyboardButton(
            text=f"[{icon}]  {label}",
            callback_data=f"admin_user:{u['user_id']}"
        )])
    buttons.append([InlineKeyboardButton(text="← Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_all_users(users: list, offset: int, total: int) -> InlineKeyboardMarkup:
    buttons = []
    for u in users:
        icon = {"approved": "✓", "rejected": "✗", "pending": "…"}.get(u.get("status",""), "·")
        if u['username']:
            label = f"@{u['username']}"
        elif u['first_name']:
            label = (u['first_name'] + (" " + u['last_name'] if u['last_name'] else "")).strip()
        else:
            label = str(u['user_id'])
        buttons.append([InlineKeyboardButton(
            text=f"[{icon}]  {label}",
            callback_data=f"admin_user:{u['user_id']}"
        )])
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="← Пред.", callback_data=f"admin_all_users:{offset-10}"))
    if offset + 10 < total:
        nav.append(InlineKeyboardButton(text="След. →", callback_data=f"admin_all_users:{offset+10}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="← Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_user_card(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Назад к списку", callback_data="admin_all_users:0")],
        [InlineKeyboardButton(text="← В панель",       callback_data="admin_panel")],
        [InlineKeyboardButton(text="✕  Закрыть",       callback_data="admin_close")],
    ])


def kb_review(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✓  Проверка пройдена", callback_data=f"review_approve:{user_id}"),
            InlineKeyboardButton(text="✗  Отклонить",         callback_data=f"review_reject:{user_id}"),
        ]
    ])
