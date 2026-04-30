from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, Contact
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

from config import ADMIN_IDS, CHANNEL_ID
from database import (
    upsert_user, set_agreed, set_phone, set_circle,
    set_imei, set_passport_front, set_passport_back,
    set_access_granted, set_rejected,
    get_user, get_user_by_username,
    search_users, get_all_users, get_stats
)
from keyboards import (
    kb_subscribe, kb_terms, kb_send_contact, kb_remove,
    kb_access_granted, kb_admin_main, kb_admin_search_cancel,
    kb_search_results, kb_all_users, kb_user_card, kb_review,
    kb_cancel_inline, kb_cancel_with_skip_passport
)

router = Router()


class Reg(StatesGroup):
    waiting_circle         = State()
    waiting_phone          = State()
    waiting_imei           = State()
    waiting_passport_front = State()
    waiting_passport_back  = State()


class AdminFlow(StatesGroup):
    waiting_query    = State()
    waiting_reject   = State()
    waiting_check_db = State()


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


async def safe_delete(bot: Bot, chat_id: int, message_id: int):
    try:
        await bot.delete_message(chat_id, message_id)
    except TelegramBadRequest:
        pass


async def delete_prev(bot: Bot, chat_id: int, state: FSMContext):
    data = await state.get_data()
    msg_id = data.get("last_bot_msg_id")
    if msg_id:
        await safe_delete(bot, chat_id, msg_id)


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status not in ("left", "kicked")
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════
#  УСЛОВИЯ
# ══════════════════════════════════════════════════════════════

TERMS_TEXT = (
    "<b>УСЛОВИЯ ИСПОЛЬЗОВАНИЯ</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "<b>Входя в бот, ты принимаешь эти условия.</b>\n\n"
    "<b>1. Тотальная ответственность</b>\n"
    "<i>Аккаунты стоят денег. Любой ущерб (бан, слив, кража) — "
    "твоя личная вина, и ты обязан возместить всё до копейки.</i>\n\n"
    "<b>2. Сбор данных</b>\n"
    "<i>Мы сохраняем твой номер телефона, данные аккаунта и историю "
    "всех действий в боте. Мы знаем, кто ты.</i>\n\n"
    "<b>3. Обращение в Отдел К</b>\n"
    "<i>При малейшем подозрении на кибермошенничество — данные и номер "
    "телефона моментально передаются в полицию. Оформляется как уголовное "
    "дело о краже и мошенничестве.</i>\n\n"
    "<b>4. Идентификация устройства</b>\n"
    "<i>Устройство будет идентифицировано по IMEI и передано "
    "правоохранительным органам. Снятие ограничений — только после "
    "личного обращения и выплаты тройного ущерба.</i>\n\n"
    "<b>5. Без исключений</b>\n"
    "<i>Все меры применяются мгновенно и без предупреждения.</i>\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "<blockquote><b>Аренда без подтверждения этих условий невозможна.</b>\n"
    "Наши специалисты контролируют соблюдение правил "
    "в режиме реального времени.</blockquote>"
)


# ══════════════════════════════════════════════════════════════
#  /start
# ══════════════════════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    user = message.from_user
    await delete_prev(bot, message.chat.id, state)
    await state.clear()
    await upsert_user(user.id, user.username, user.first_name, user.last_name)

    # Админы сразу получают панель — верификация им не нужна
    if is_admin(user.id):
        stats = await get_stats()
        sent = await message.answer(
            "<b>Malik Shop — Панель администратора</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Всего:</b> <code>{stats['total']}</code>\n"
            f"<b>Приняты:</b> <code>{stats['granted']}</code>\n"
            f"<b>Ожидают:</b> <code>{stats['pending']}</code>\n"
            f"<b>Отклонены:</b> <code>{stats['rejected']}</code>",
            parse_mode="HTML",
            reply_markup=kb_admin_main()
        )
        await state.update_data(last_bot_msg_id=sent.message_id)
        return

    # Обычные пользователи — проверка подписки
    if not await is_subscribed(bot, user.id):
        sent = await message.answer(
            "<b>Malik Shop</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Для доступа к боту необходима подписка на канал.</b>\n\n"
            "<i>Подпишитесь на официальный канал Malik Shop, "
            "затем нажмите кнопку «Я подписался».</i>",
            parse_mode="HTML",
            reply_markup=kb_subscribe()
        )
        await state.update_data(last_bot_msg_id=sent.message_id)
        return

    await _show_terms(message.chat.id, bot, state)


# ══════════════════════════════════════════════════════════════
#  Проверка подписки
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "check_sub")
async def cb_check_sub(call: CallbackQuery, state: FSMContext, bot: Bot):
    if is_admin(call.from_user.id):
        await safe_delete(bot, call.message.chat.id, call.message.message_id)
        await call.answer()
        stats = await get_stats()
        sent = await bot.send_message(
            call.message.chat.id,
            "<b>Malik Shop — Панель администратора</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Всего:</b> <code>{stats['total']}</code>\n"
            f"<b>Приняты:</b> <code>{stats['granted']}</code>\n"
            f"<b>Ожидают:</b> <code>{stats['pending']}</code>\n"
            f"<b>Отклонены:</b> <code>{stats['rejected']}</code>",
            parse_mode="HTML",
            reply_markup=kb_admin_main()
        )
        await state.update_data(last_bot_msg_id=sent.message_id)
        return

    if not await is_subscribed(bot, call.from_user.id):
        await call.answer("Вы ещё не подписались на канал.", show_alert=True)
        return

    await safe_delete(bot, call.message.chat.id, call.message.message_id)
    await call.answer()
    await _show_terms(call.message.chat.id, bot, state)



# ══════════════════════════════════════════════════════════════
#  /admin — открыть панель в любой момент
# ══════════════════════════════════════════════════════════════

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    stats = await get_stats()
    await message.delete()
    await message.answer(
        "<b>Панель администратора</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Всего:</b> <code>{stats['total']}</code>\n"
        f"<b>Приняты:</b> <code>{stats['granted']}</code>\n"
        f"<b>Ожидают:</b> <code>{stats['pending']}</code>\n"
        f"<b>Отклонены:</b> <code>{stats['rejected']}</code>",
        parse_mode="HTML",
        reply_markup=kb_admin_main()
    )


# ══════════════════════════════════════════════════════════════
#  /admin — панель в любой момент
# ══════════════════════════════════════════════════════════════

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    stats = await get_stats()
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer(
        "<b>Панель администратора</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Всего:</b> <code>{stats['total']}</code>\n"
        f"<b>Приняты:</b> <code>{stats['granted']}</code>\n"
        f"<b>Ожидают:</b> <code>{stats['pending']}</code>\n"
        f"<b>Отклонены:</b> <code>{stats['rejected']}</code>",
        parse_mode="HTML",
        reply_markup=kb_admin_main()
    )

async def _show_terms(chat_id: int, bot: Bot, state: FSMContext):
    sent = await bot.send_message(
        chat_id,
        "<b>Malik Shop</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<i>Торговая платформа игровых аккаунтов.\n"
        "Ознакомьтесь с условиями и пройдите верификацию.</i>",
        parse_mode="HTML"
    )
    await state.update_data(last_bot_msg_id=sent.message_id)
    sent2 = await bot.send_message(
        chat_id, TERMS_TEXT,
        parse_mode="HTML",
        reply_markup=kb_terms()
    )
    await state.update_data(last_bot_msg_id=sent2.message_id)


# ══════════════════════════════════════════════════════════════
#  Принятие условий → Шаг 1: Кружок
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "terms_accept")
async def cb_terms_accept(call: CallbackQuery, state: FSMContext, bot: Bot):
    user = call.from_user
    await upsert_user(user.id, user.username, user.first_name, user.last_name)
    await set_agreed(user.id)
    await safe_delete(bot, call.message.chat.id, call.message.message_id)
    await state.set_state(Reg.waiting_circle)

    sent = await bot.send_message(
        call.message.chat.id,
        "<b>Шаг 1 / 4 — Видеозапись</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Запишите и отправьте <b>видео-кружок</b>.\n\n"
        "<blockquote>"
        "<b>Инструкция:</b>\n"
        "· Смотрите прямо в камеру\n"
        "· Медленно поверните голову влево, затем вправо\n"
        "· Лицо должно быть чётко видно, без перекрытий\n"
        "· Хорошее освещение обязательно"
        "</blockquote>",
        parse_mode="HTML",
        reply_markup=kb_cancel_inline()
    )
    await state.update_data(last_bot_msg_id=sent.message_id)
    await call.answer()


# ══════════════════════════════════════════════════════════════
#  Шаг 1 — Кружок
# ══════════════════════════════════════════════════════════════

@router.message(Reg.waiting_circle, F.video_note)
async def handle_circle(message: Message, state: FSMContext, bot: Bot):
    await safe_delete(bot, message.chat.id, message.message_id)
    await delete_prev(bot, message.chat.id, state)
    await set_circle(message.from_user.id, message.video_note.file_id)
    await state.set_state(Reg.waiting_phone)

    sent = await bot.send_message(
        message.chat.id,
        "<b>Шаг 2 / 4 — Номер телефона</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Нажмите кнопку и передайте номер, "
        "привязанный к аккаунту Telegram.\n\n"
        "<blockquote>"
        "<b>Инструкция:</b>\n"
        "· Используйте только кнопку ниже\n"
        "· Передаётся номер вашего текущего аккаунта\n"
        "· Ввод вручную не принимается"
        "</blockquote>",
        parse_mode="HTML",
        reply_markup=kb_send_contact()
    )
    await state.update_data(last_bot_msg_id=sent.message_id)


@router.message(Reg.waiting_circle)
async def handle_circle_wrong(message: Message, state: FSMContext, bot: Bot):
    await safe_delete(bot, message.chat.id, message.message_id)
    await delete_prev(bot, message.chat.id, state)
    sent = await bot.send_message(
        message.chat.id,
        "<b>Требуется видео-кружок.</b>\n\n"
        "<i>Нажмите скрепку → «Видеосообщение» → запишите кружок.</i>",
        parse_mode="HTML",
        reply_markup=kb_cancel_inline()
    )
    await state.update_data(last_bot_msg_id=sent.message_id)


# ══════════════════════════════════════════════════════════════
#  Отмена
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "cancel_reg")
async def cb_cancel_reg(call: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    await safe_delete(bot, call.message.chat.id, call.message.message_id)
    sent = await bot.send_message(
        call.message.chat.id,
        "<b>Верификация отменена.</b>\n\n"
        "<i>Введите /start чтобы начать заново.</i>",
        parse_mode="HTML"
    )
    await state.update_data(last_bot_msg_id=sent.message_id)
    await call.answer()


@router.message(F.text == "Отмена")
async def handle_cancel_reply(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    await safe_delete(bot, message.chat.id, message.message_id)
    await delete_prev(bot, message.chat.id, state)
    sent = await bot.send_message(
        message.chat.id,
        "<b>Верификация отменена.</b>\n\n"
        "<i>Введите /start чтобы начать заново.</i>",
        parse_mode="HTML",
        reply_markup=kb_remove()
    )
    await state.update_data(last_bot_msg_id=sent.message_id)


# ══════════════════════════════════════════════════════════════
#  Шаг 2 — Телефон
# ══════════════════════════════════════════════════════════════

@router.message(Reg.waiting_phone, F.contact)
async def handle_phone(message: Message, state: FSMContext, bot: Bot):
    contact: Contact = message.contact
    user = message.from_user
    await safe_delete(bot, message.chat.id, message.message_id)
    await delete_prev(bot, message.chat.id, state)

    if contact.user_id and contact.user_id != user.id:
        sent = await bot.send_message(
            message.chat.id,
            "<b>Ошибка.</b> Отправьте <b>свой</b> номер — не чужой контакт.",
            parse_mode="HTML",
            reply_markup=kb_send_contact()
        )
        await state.update_data(last_bot_msg_id=sent.message_id)
        return

    await set_phone(user.id, contact.phone_number)
    await state.set_state(Reg.waiting_imei)

    sent = await bot.send_message(
        message.chat.id,
        "<b>Шаг 3 / 4 — Идентификация устройства</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Сфотографируйте IMEI вашего устройства и отправьте скриншот.\n\n"
        "<blockquote>"
        "<b>Инструкция:</b>\n"
        "· Наберите на телефоне: <code>*#06#</code>\n"
        "· На экране появится IMEI — сделайте скриншот\n"
        "· Отправьте скриншот как фото\n"
        "· Принимается только 1 фотография"
        "</blockquote>",
        parse_mode="HTML",
        reply_markup=kb_cancel_inline()
    )
    await state.update_data(last_bot_msg_id=sent.message_id)


@router.message(Reg.waiting_phone)
async def handle_phone_wrong(message: Message, state: FSMContext, bot: Bot):
    await safe_delete(bot, message.chat.id, message.message_id)
    await delete_prev(bot, message.chat.id, state)
    sent = await bot.send_message(
        message.chat.id,
        "<b>Используйте кнопку</b> для отправки номера.",
        parse_mode="HTML",
        reply_markup=kb_send_contact()
    )
    await state.update_data(last_bot_msg_id=sent.message_id)


# ══════════════════════════════════════════════════════════════
#  Шаг 3 — IMEI
# ══════════════════════════════════════════════════════════════

@router.message(Reg.waiting_imei, F.photo)
async def handle_imei(message: Message, state: FSMContext, bot: Bot):
    await safe_delete(bot, message.chat.id, message.message_id)
    await delete_prev(bot, message.chat.id, state)
    await set_imei(message.from_user.id, message.photo[-1].file_id)
    await state.set_state(Reg.waiting_passport_front)

    sent = await bot.send_message(
        message.chat.id,
        "<b>Шаг 4 / 4 — Документ, удостоверяющий личность</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Отправьте фото <b>лицевой стороны паспорта</b>.\n\n"
        "<blockquote>"
        "<b>Инструкция:</b>\n"
        "· Страница с фотографией и ФИО\n"
        "· Положите паспорт на ровную поверхность\n"
        "· Все четыре угла должны быть в кадре\n"
        "· Текст должен быть чётким и читаемым"
        "</blockquote>",
        parse_mode="HTML",
        reply_markup=kb_cancel_with_skip_passport()
    )
    await state.update_data(last_bot_msg_id=sent.message_id)


@router.message(Reg.waiting_imei)
async def handle_imei_wrong(message: Message, state: FSMContext, bot: Bot):
    await safe_delete(bot, message.chat.id, message.message_id)
    await delete_prev(bot, message.chat.id, state)
    sent = await bot.send_message(
        message.chat.id,
        "<b>Требуется фотография.</b>\n\n"
        "<i>Наберите <code>*#06#</code> → сделайте скриншот → отправьте как фото.</i>",
        parse_mode="HTML",
        reply_markup=kb_cancel_inline()
    )
    await state.update_data(last_bot_msg_id=sent.message_id)


# ══════════════════════════════════════════════════════════════
#  Шаг 4а — Паспорт лицевая
# ══════════════════════════════════════════════════════════════

@router.message(Reg.waiting_passport_front, F.photo)
async def handle_passport_front(message: Message, state: FSMContext, bot: Bot):
    await safe_delete(bot, message.chat.id, message.message_id)
    await delete_prev(bot, message.chat.id, state)
    await set_passport_front(message.from_user.id, message.photo[-1].file_id)
    await state.set_state(Reg.waiting_passport_back)

    sent = await bot.send_message(
        message.chat.id,
        "<b>Документ — обратная сторона</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Теперь отправьте фото <b>обратной стороны паспорта</b>.\n\n"
        "<blockquote>"
        "<b>Инструкция:</b>\n"
        "· Переверните паспорт\n"
        "· Все четыре угла в кадре\n"
        "· Текст чёткий и читаемый"
        "</blockquote>",
        parse_mode="HTML",
        reply_markup=kb_cancel_inline()
    )
    await state.update_data(last_bot_msg_id=sent.message_id)


@router.message(Reg.waiting_passport_front)
async def handle_passport_front_wrong(message: Message, state: FSMContext, bot: Bot):
    await safe_delete(bot, message.chat.id, message.message_id)
    await delete_prev(bot, message.chat.id, state)
    sent = await bot.send_message(
        message.chat.id,
        "<b>Требуется фотография лицевой стороны паспорта.</b>",
        parse_mode="HTML",
        reply_markup=kb_cancel_with_skip_passport()
    )
    await state.update_data(last_bot_msg_id=sent.message_id)


# ══════════════════════════════════════════════════════════════
#  «Мне нет 18+» — пропуск паспорта
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "skip_passport")
async def cb_skip_passport(call: CallbackQuery, state: FSMContext, bot: Bot):
    user = call.from_user
    await safe_delete(bot, call.message.chat.id, call.message.message_id)
    await state.clear()

    db_user = await get_user(user.id)
    sent = await bot.send_message(
        call.message.chat.id,
        "<b>Заявка отправлена.</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<i>Ваша заявка передана администратору на рассмотрение.\n"
        "Ожидайте уведомления.</i>",
        parse_mode="HTML"
    )
    await state.update_data(last_bot_msg_id=sent.message_id)
    await call.answer()

    uname = f"@{user.username}" if user.username else "<i>нет</i>"
    name  = ((user.first_name or "") + " " + (user.last_name or "")).strip() or "—"
    phone = (db_user.get("phone") if db_user else None) or "<i>не получен</i>"

    caption = (
        "<b>НОВАЯ ЗАЯВКА — БЕЗ ДОКУМЕНТА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        f"<b>Имя:</b> {name}\n"
        f"<b>Username:</b> {uname}\n"
        f"<b>Телефон:</b> <code>{phone}</code>\n\n"
        "<blockquote>Пользователь указал что ему нет 18 лет.\n"
        "Паспорт не предоставлен.</blockquote>"
    )
    for admin_id in ADMIN_IDS:
        try:
            if db_user and db_user.get("circle_file_id"):
                await bot.send_video_note(admin_id, db_user["circle_file_id"])
            if db_user and db_user.get("imei_file_id"):
                await bot.send_photo(admin_id, db_user["imei_file_id"],
                                     caption="<b>IMEI — скриншот</b>", parse_mode="HTML")
            await bot.send_message(admin_id, caption, parse_mode="HTML",
                                   reply_markup=kb_review(user.id))
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
#  Шаг 4б — Паспорт обратная → отправка на проверку
# ══════════════════════════════════════════════════════════════

@router.message(Reg.waiting_passport_back, F.photo)
async def handle_passport_back(message: Message, state: FSMContext, bot: Bot):
    user = message.from_user
    await safe_delete(bot, message.chat.id, message.message_id)
    await delete_prev(bot, message.chat.id, state)
    await set_passport_back(user.id, message.photo[-1].file_id)
    await state.clear()

    db_user = await get_user(user.id)
    sent = await bot.send_message(
        message.chat.id,
        "<b>Данные получены.</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<i>Заявка передана на проверку администратору.\n"
        "Ожидайте уведомления.</i>",
        parse_mode="HTML"
    )
    await state.update_data(last_bot_msg_id=sent.message_id)

    uname = f"@{user.username}" if user.username else "<i>нет</i>"
    name  = ((user.first_name or "") + " " + (user.last_name or "")).strip() or "—"
    phone = db_user.get("phone") or "<i>не получен</i>"

    caption = (
        "<b>НОВАЯ ЗАЯВКА НА ВЕРИФИКАЦИЮ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        f"<b>Имя:</b> {name}\n"
        f"<b>Username:</b> {uname}\n"
        f"<b>Телефон:</b> <code>{phone}</code>\n\n"
        "<i>Проверьте кружок, IMEI и паспорт выше.</i>"
    )
    for admin_id in ADMIN_IDS:
        try:
            if db_user.get("circle_file_id"):
                await bot.send_video_note(admin_id, db_user["circle_file_id"])
            if db_user.get("imei_file_id"):
                await bot.send_photo(admin_id, db_user["imei_file_id"],
                                     caption="<b>IMEI — скриншот</b>", parse_mode="HTML")
            if db_user.get("passport_front_file_id"):
                await bot.send_photo(admin_id, db_user["passport_front_file_id"],
                                     caption="<b>Паспорт — лицевая сторона</b>", parse_mode="HTML")
            if db_user.get("passport_back_file_id"):
                await bot.send_photo(admin_id, db_user["passport_back_file_id"],
                                     caption="<b>Паспорт — обратная сторона</b>", parse_mode="HTML")
            await bot.send_message(admin_id, caption, parse_mode="HTML",
                                   reply_markup=kb_review(user.id))
        except Exception:
            pass


@router.message(Reg.waiting_passport_back)
async def handle_passport_back_wrong(message: Message, state: FSMContext, bot: Bot):
    await safe_delete(bot, message.chat.id, message.message_id)
    await delete_prev(bot, message.chat.id, state)
    sent = await bot.send_message(
        message.chat.id,
        "<b>Требуется фотография обратной стороны паспорта.</b>",
        parse_mode="HTML",
        reply_markup=kb_cancel_inline()
    )
    await state.update_data(last_bot_msg_id=sent.message_id)


# ══════════════════════════════════════════════════════════════
#  Решение администратора — Принять
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("review_approve:"))
async def cb_approve(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    user_id = int(call.data.split(":")[1])
    await set_access_granted(user_id)
    await call.message.edit_text(
        call.message.text + "\n\n<b>— ОДОБРЕНО</b>",
        parse_mode="HTML", reply_markup=None
    )
    await call.answer("Одобрено.")
    try:
        await bot.send_message(
            user_id,
            "<b>Верификация пройдена.</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<i>Ваши данные проверены.\n"
            "Доступ к торговой платформе открыт.</i>",
            parse_mode="HTML",
            reply_markup=kb_access_granted()
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
#  Решение администратора — Отклонить
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("review_reject:"))
async def cb_reject_prompt(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    user_id = int(call.data.split(":")[1])
    await state.set_state(AdminFlow.waiting_reject)
    await state.update_data(reject_user_id=user_id)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(
        f"<b>Отклонение заявки <code>#{user_id}</code></b>\n\n"
        "<i>Напишите причину — она будет отправлена пользователю.</i>",
        parse_mode="HTML"
    )
    await call.answer()


@router.message(AdminFlow.waiting_reject)
async def cb_reject_reason(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    data    = await state.get_data()
    user_id = data.get("reject_user_id")
    reason  = message.text.strip()
    await state.clear()
    if not user_id:
        return
    await set_rejected(user_id, reason)
    await message.answer(
        f"<b>Заявка <code>#{user_id}</code> отклонена.</b>\n"
        f"<b>Причина:</b> <i>{reason}</i>",
        parse_mode="HTML"
    )
    try:
        await bot.send_message(
            user_id,
            "<b>Верификация не пройдена.</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Причина:</b>\n<blockquote>{reason}</blockquote>\n\n"
            "<i>Для повторной попытки введите /start.</i>",
            parse_mode="HTML"
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
#  ПАНЕЛЬ АДМИНИСТРАТОРА
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    await state.clear()
    stats = await get_stats()
    text = (
        "<b>Панель администратора</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Всего:</b> <code>{stats['total']}</code>\n"
        f"<b>Приняты:</b> <code>{stats['granted']}</code>\n"
        f"<b>Ожидают:</b> <code>{stats['pending']}</code>\n"
        f"<b>Отклонены:</b> <code>{stats['rejected']}</code>"
    )
    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb_admin_main())
    except TelegramBadRequest:
        await call.message.answer(text, parse_mode="HTML", reply_markup=kb_admin_main())
    await call.answer()


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    stats = await get_stats()
    conv  = round(stats['granted'] / stats['total'] * 100) if stats['total'] else 0
    await call.message.edit_text(
        "<b>Статистика</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Всего пользователей:</b> <code>{stats['total']}</code>\n"
        f"<b>Приняли условия:</b> <code>{stats['agreed']}</code>\n"
        f"<b>Приняты:</b> <code>{stats['granted']}</code>\n"
        f"<b>Ожидают:</b> <code>{stats['pending']}</code>\n"
        f"<b>Отклонены:</b> <code>{stats['rejected']}</code>\n\n"
        f"<i>Конверсия верификации: <b>{conv}%</b></i>",
        parse_mode="HTML",
        reply_markup=kb_admin_main()
    )
    await call.answer()


# ══════════════════════════════════════════════════════════════
#  Поиск пользователя
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_search")
async def cb_admin_search(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminFlow.waiting_query)
    await call.message.edit_text(
        "<b>Поиск пользователя</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Поиск по любому параметру:\n"
        "· <code>username</code>\n"
        "· <b>Имя</b> / <b>Фамилия</b>\n"
        "· <code>Telegram ID</code>\n"
        "· <code>Номер телефона</code>\n\n"
        "<i>Частичный поиск поддерживается.</i>",
        parse_mode="HTML",
        reply_markup=kb_admin_search_cancel()
    )
    await call.answer()


@router.message(AdminFlow.waiting_query)
async def handle_admin_search(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.startswith("/"):
        await state.clear()
        return
    await state.clear()
    query = message.text.strip().lstrip("@")
    users = await search_users(query)
    if not users:
        await message.answer(
            f"<b>Ничего не найдено</b> по запросу <code>{query}</code>.",
            parse_mode="HTML", reply_markup=kb_admin_main()
        )
        return
    await message.answer(
        f"<b>Результаты:</b> <code>{query}</code> — <b>{len(users)}</b>",
        parse_mode="HTML", reply_markup=kb_search_results(users)
    )


# ══════════════════════════════════════════════════════════════
#  Проверить базу
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_check_db")
async def cb_admin_check_db(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminFlow.waiting_check_db)
    await call.message.edit_text(
        "<b>Проверить базу</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Отправьте одно из следующего:\n\n"
        "· <code>@username</code> — никнейм пользователя\n"
        "· <code>Telegram ID</code> — числовой идентификатор\n"
        "· <b>Перешлите сообщение</b> от нужного пользователя\n\n"
        "<i>Бот покажет статус верификации этого человека.</i>",
        parse_mode="HTML",
        reply_markup=kb_admin_search_cancel()
    )
    await call.answer()


@router.message(AdminFlow.waiting_check_db)
async def handle_check_db(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.startswith("/"):
        await state.clear()
        return

    await state.clear()
    u = None

    # Пересланное сообщение
    if message.forward_from:
        u = await get_user(message.forward_from.id)
        lookup = f"ID <code>{message.forward_from.id}</code>"

    # Текстовый запрос: @username или цифры
    elif message.text:
        query = message.text.strip().lstrip("@")
        if query.isdigit():
            u = await get_user(int(query))
            lookup = f"ID <code>{query}</code>"
        else:
            u = await get_user_by_username(query)
            lookup = f"@<code>{query}</code>"
    else:
        await message.answer(
            "<b>Не распознан формат запроса.</b>\n\n"
            "<i>Отправьте @username, Telegram ID или перешлите сообщение.</i>",
            parse_mode="HTML", reply_markup=kb_admin_main()
        )
        return

    if not u:
        await message.answer(
            f"<b>Пользователь {lookup} не найден в базе.</b>\n\n"
            "<blockquote>Этот человек ни разу не обращался в бот,\n"
            "либо указанные данные некорректны.</blockquote>",
            parse_mode="HTML", reply_markup=kb_admin_main()
        )
        return

    smap = {
        "approved": "✓  <b>Верификация пройдена</b>",
        "rejected": "✗  <b>Верификация отклонена</b>",
        "pending":  "…  <i>Ожидает проверки</i>",
    }
    status  = smap.get(u.get("status",""), "— <i>Нет данных</i>")
    uname   = f"@{u['username']}" if u['username'] else "<i>нет</i>"
    name    = ((u['first_name'] or "") + " " + (u['last_name'] or "")).strip() or "—"
    phone   = f"<code>{u['phone']}</code>" if u['phone'] else "<i>нет</i>"
    reg     = u.get("registered_at") or "—"
    reason  = u.get("reject_reason")

    text = (
        "<b>Результат проверки базы</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Статус:</b> {status}\n\n"
        f"<b>Telegram ID:</b> <code>{u['user_id']}</code>\n"
        f"<b>Имя:</b> {name}\n"
        f"<b>Username:</b> {uname}\n"
        f"<b>Телефон:</b> {phone}\n\n"
        f"<blockquote>Регистрация: {reg}</blockquote>"
    )
    if reason:
        text += f"\n<b>Причина отказа:</b> <i>{reason}</i>"

    await message.answer(text, parse_mode="HTML", reply_markup=kb_admin_main())


# ══════════════════════════════════════════════════════════════
#  Список всех пользователей
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("admin_all_users:"))
async def cb_admin_all_users(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    offset = int(call.data.split(":")[1])
    stats  = await get_stats()
    users  = await get_all_users(limit=10, offset=offset)
    if not users:
        await call.answer("Пользователей нет.", show_alert=True)
        return
    await call.message.edit_text(
        f"<b>Список пользователей</b>\n"
        f"<i>{offset+1}–{offset+len(users)} из {stats['total']}</i>\n\n"
        f"<code>[✓]</code> принят · <code>[✗]</code> отклонён · <code>[…]</code> ожидает",
        parse_mode="HTML",
        reply_markup=kb_all_users(users, offset, stats['total'])
    )
    await call.answer()


@router.callback_query(F.data.startswith("admin_user:"))
async def cb_admin_user(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    user_id = int(call.data.split(":")[1])
    u = await get_user(user_id)
    if not u:
        await call.answer("Не найден.", show_alert=True)
        return

    uname  = f"@{u['username']}" if u['username'] else "<i>нет</i>"
    name   = ((u['first_name'] or "") + " " + (u['last_name'] or "")).strip() or "—"
    phone  = f"<code>{u['phone']}</code>" if u['phone'] else "<i>нет</i>"
    smap   = {"approved": "<b>✓ Принят</b>", "rejected": "<b>✗ Отклонён</b>",
               "pending": "<i>Ожидает</i>"}
    status = smap.get(u.get("status",""), "—")
    docs   = (
        f"· Кружок: <i>{'есть' if u.get('circle_file_id') else 'нет'}</i>\n"
        f"· IMEI: <i>{'есть' if u.get('imei_file_id') else 'нет'}</i>\n"
        f"· Паспорт лиц.: <i>{'есть' if u.get('passport_front_file_id') else 'нет'}</i>\n"
        f"· Паспорт обр.: <i>{'есть' if u.get('passport_back_file_id') else 'нет'}</i>"
    )
    text = (
        "<b>Карточка пользователя</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Telegram ID:</b> <code>{u['user_id']}</code>\n"
        f"<b>Имя:</b> {name}\n"
        f"<b>Username:</b> {uname}\n"
        f"<b>Телефон:</b> {phone}\n\n"
        f"<b>Статус:</b> {status}\n\n"
        f"<b>Документы:</b>\n{docs}\n\n"
        f"<blockquote>Регистрация: {u.get('registered_at') or '—'}\n"
        f"Верификация: {u.get('verified_at') or '—'}</blockquote>"
    )
    if u.get("status") == "rejected" and u.get("reject_reason"):
        text += f"\n<b>Причина отказа:</b> <i>{u['reject_reason']}</i>"

    await call.message.edit_text(text, parse_mode="HTML",
                                  reply_markup=kb_user_card(user_id))
    await call.answer()


@router.callback_query(F.data == "admin_close")
async def cb_admin_close(call: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    await safe_delete(bot, call.message.chat.id, call.message.message_id)
    await call.answer("Закрыто.")
