import asyncio
import json
import logging
import os
import random
import re
import time

from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TOKEN_BOT")
if not TOKEN:
    raise RuntimeError("TOKEN_BOT не задан! Установи переменную окружения на Render.")

RENDER_URL = os.environ.get("RENDER_URL", "")

# ── Facts ──────────────────────────────────────────────────────────────────────

FACTS = [
    "🐆 Снежный барс не умеет рычать — он мурлычет, как домашняя кошка.",
    "🐬 Дельфины спят с одним открытым глазом, чтобы не утонуть.",
    "🦜 Попугаи жако могут выучить до 1000 слов и понимают их значение.",
    "🐘 Слоны — единственные животные, которые не умеют прыгать.",
    "🦩 Фламинго розовые из-за пигментов в пище — без них они были бы белыми.",
    "🐙 У осьминога три сердца и голубая кровь.",
    "🦁 Лев спит до 20 часов в сутки.",
    "🐧 Пингвины делают предложение своей паре, преподнося камушек.",
    "🐢 Черепахи существуют более 200 миллионов лет — старше динозавров.",
    "🦋 Бабочки ощущают вкус лапками.",
    "🐝 Пчела делает в среднем одну двенадцатую чайной ложки мёда за всю жизнь.",
    "🦈 Акулы старше деревьев — они появились 400 миллионов лет назад.",
    "🐦 Стриж проводит в воздухе до 10 месяцев без посадки.",
    "🦊 Лисы используют магнитное поле Земли для прыжков на добычу.",
    "🐌 Улитка может спать 3 года подряд.",
    "🦩 У фламинго колени сгибаются назад — то что мы видим как колено это лодыжка.",
    "🐳 Синий кит весит столько же, сколько 30 слонов.",
    "🦭 Тюлени могут задерживать дыхание на 2 часа.",
    "🐻‍❄️ Белые медведи не белые — их шерсть прозрачная и полая внутри.",
    "🦅 Орлы могут видеть добычу с расстояния 3 километра.",
    "🐆 Гепард разгоняется до 120 км/ч за 3 секунды.",
    "🦒 У жирафа столько же позвонков в шее, как и у человека — семь.",
    "🐠 Рыбы-клоуны могут менять пол — все они рождаются самцами.",
    "🦎 Хамелеоны меняют цвет не для маскировки, а для общения.",
    "🐦‍⬛ Вороны помнят лица людей и могут держать обиду годами.",
    "🦇 Летучие мыши — единственные летающие млекопитающие.",
    "🐺 Волки могут учуять добычу на расстоянии 2,5 километра.",
    "🦥 Ленивцы настолько медленные, что на их шерсти растут водоросли.",
    "🐡 Рыба-шар токсичнее цианида в 1200 раз.",
    "🦬 Бизон может бежать со скоростью 65 км/ч — быстрее лошади.",
    "🌍 На Земле больше деревьев, чем звёзд в Млечном Пути.",
    "🌊 Океан изучен людьми менее чем на 20%.",
    "⚡ Молния нагревает воздух до 30 000 градусов — в 5 раз горячее поверхности Солнца.",
    "🌙 На Луне следы астронавтов сохранятся миллионы лет — там нет ветра.",
    "🧠 Мозг человека потребляет 20% всей энергии тела.",
    "💤 Человек проводит треть жизни во сне.",
    "👁 Человеческий глаз различает около 10 миллионов оттенков цвета.",
    "❤️ Сердце бьётся около 100 000 раз в день.",
    "🍯 Мёд не портится — в египетских гробницах нашли мёд возрастом 3000 лет.",
    "🍎 Яблоки на 25% состоят из воздуха — поэтому они плавают.",
    "☕ Кофе был открыт благодаря козам — пастух заметил что они не спали после ягод.",
    "🍫 Шоколад был валютой у ацтеков.",
    "🚀 До Луны можно добраться за 3 дня, до Марса — от 7 месяцев.",
    "⭐ Солнце составляет 99,86% массы всей Солнечной системы.",
    "🌌 Млечный Путь содержит от 200 до 400 миллиардов звёзд.",
    "🔭 Свет от ближайшей звезды идёт до Земли 4,2 года.",
    "📱 Современный смартфон мощнее компьютеров которые отправили человека на Луну.",
    "🐈 Кошки мяукают только для общения с людьми, но не друг с другом.",
    "🐕 Собаки понимают около 250 слов и жестов.",
    "🦦 Выдры держатся за лапы во время сна, чтобы не разлучиться.",
    "🐬 Дельфины дают имена друг другу и откликаются на них.",
    "🐿 Белки забывают где спрятали 74% своих запасов, помогая лесам расти.",
]

fact_index = random.randint(0, len(FACTS) - 1)

# ── Helpers ────────────────────────────────────────────────────────────────────

def mention(first_name: str, user_id: int) -> str:
    name = first_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<a href="tg://user?id={user_id}">{name}</a>'

MUTE = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
)
UNMUTE = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
)

async def mute(bot: Bot, chat_id, user_id: int):
    try:
        await bot.restrict_chat_member(chat_id, user_id, MUTE)
    except Exception:
        pass

async def unmute(bot: Bot, chat_id, user_id: int):
    try:
        await bot.restrict_chat_member(chat_id, user_id, UNMUTE)
    except Exception:
        pass

async def get_owner_id(bot: Bot, chat_id) -> int | None:
    try:
        admins = await bot.get_chat_administrators(chat_id)
        for a in admins:
            if a.status == ChatMemberStatus.CREATOR:
                return a.user.id
    except Exception:
        pass
    return None

async def is_admin_or_owner(bot: Bot, chat_id, user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
    except Exception:
        return False

async def is_owner_check(bot: Bot, chat_id, user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status == ChatMemberStatus.CREATOR
    except Exception:
        return False

def is_lawsuit_cmd(text: str) -> bool:
    return bool(text and re.match(r"^!\s*суд(\s|$)", text.strip(), re.IGNORECASE))

def extract_target(text: str) -> str | None:
    m = re.search(r"!\s*суд\s+@(\w+)", text, re.IGNORECASE)
    return m.group(1) if m else None

def parse_participants(text: str) -> dict:
    result = {"plaintiff": None, "defendant": None, "witnesses": [], "judge": None}
    for part in text.split(";"):
        part = part.strip()
        lower = part.lower()
        m = re.search(r"@(\w+)", part)
        if not m:
            continue
        username = m.group(1)
        if "истец" in lower:
            result["plaintiff"] = username
        elif "ответчик" in lower:
            result["defendant"] = username
        elif "свидетел" in lower:
            result["witnesses"].append(username)
        elif "судья" in lower:
            result["judge"] = username
    return result

async def resolve_username(bot: Bot, username: str):
    try:
        chat = await bot.get_chat(f"@{username}")
        return chat.id, getattr(chat, "first_name", username) or username
    except Exception:
        return None

# ── Router ─────────────────────────────────────────────────────────────────────

router = Router()

# ── Commands ───────────────────────────────────────────────────────────────────

HELP_TEXT = """<b>⚖️ Команды CaseSolve:</b>

<b>Участники:</b>
• <code>! суд @username</code> — подать иск
• <code>! суд</code> (в ответ на сообщение) — иск против автора
• <code>/lawsuit @username</code> — то же самое

<b>Для администраторов:</b>
• <code>! суд</code> или <code>/lawsuit</code> — создать суд вручную

<b>В личных сообщениях (владелец):</b>
• <code>/настройки</code> — настроить зал суда

• <code>/help</code> — это сообщение"""

@router.message(CommandStart())
async def cmd_start(message: Message):
    if message.chat.type != "private":
        return
    await message.answer(
        f"⚖️ <b>Добро пожаловать в CaseSolve!</b>\n\nДобавьте меня в группу с правами администратора.\n\n{HELP_TEXT}",
        parse_mode=ParseMode.HTML,
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode=ParseMode.HTML)

@router.message(Command(commands=["settings", "настройки"]))
async def cmd_settings(message: Message):
    if message.chat.type != "private":
        await message.answer("⚙️ Настройки доступны только в личных сообщениях.")
        return
    await message.answer(
        "⚙️ <b>Настройка зала суда</b>\n\nПерешлите любое сообщение из группы, которую хотите назначить <b>залом суда</b>.\n\n<i>Ожидаю пересланное сообщение...</i>",
        parse_mode=ParseMode.HTML,
    )
    db.session_set(message.from_user.id, "awaiting_court_group_global", None)

@router.message(Command("lawsuit"))
async def cmd_lawsuit(message: Message, bot: Bot):
    if message.chat.type == "private":
        await message.answer("⚖️ Команда /lawsuit работает только в группах.")
        return
    admin = await is_admin_or_owner(bot, message.chat.id, message.from_user.id)
    if admin:
        await handle_admin_lawsuit(message, bot)
    else:
        await handle_user_lawsuit(message, bot)

# ── Bot added to group ─────────────────────────────────────────────────────────

@router.my_chat_member()
async def on_my_chat_member(update: ChatMemberUpdated, bot: Bot):
    chat = update.chat
    if chat.type not in ("group", "supergroup"):
        return
    new_status = update.new_chat_member.status
    if new_status not in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR):
        return
    db.group_upsert(str(chat.id), getattr(chat, "title", None))
    owner_id = await get_owner_id(bot, chat.id)
    if owner_id:
        db.group_set_owner(owner_id, str(chat.id))
    await bot.send_message(
        chat.id,
        f"⚖️ <b>Привет! Я — CaseSolve.</b>\n\nПомогаю организовать разбирательства в группе.\n\n{HELP_TEXT}",
        parse_mode=ParseMode.HTML,
    )

# ── Lawsuit handlers ───────────────────────────────────────────────────────────

async def handle_user_lawsuit(message: Message, bot: Bot):
    chat = message.chat
    from_user = message.from_user
    target_id, target_name = None, ""

    if message.reply_to_message and message.reply_to_message.from_user:
        replied = message.reply_to_message.from_user
        if replied.is_bot:
            await message.answer("❕️ Нельзя подавать иск на бота.")
            return
        target_id = replied.id
        target_name = replied.first_name
    else:
        username = extract_target(message.text or "")
        if not username:
            await message.answer(
                "❔️ Укажи ответчика.\nПример: <code>! суд @username</code>",
                parse_mode=ParseMode.HTML,
            )
            return
        res = await resolve_username(bot, username)
        if not res:
            await message.answer(f"❕️ Не удалось найти @{username}.")
            return
        target_id, target_name = res

    if target_id == from_user.id:
        await message.answer("❕️ Нельзя подавать иск на самого себя.")
        return

    if db.court_awaiting_in_origin(str(chat.id)):
        await message.answer("❕️ В этом чате уже создаётся суд. Ожидайте.")
        return

    owner_id = await get_owner_id(bot, chat.id)
    if not owner_id:
        await message.answer("❕️ Не удалось найти владельца группы.")
        return

    db.group_upsert(str(chat.id), getattr(chat, "title", None))
    db.group_set_owner(owner_id, str(chat.id))

    court = db.court_create({
        "origin_chat_id": str(chat.id),
        "court_chat_id": None,
        "plaintiff_id": from_user.id,
        "plaintiff_name": from_user.first_name,
        "defendant_id": target_id,
        "defendant_name": target_name,
        "judge_id": None,
        "judge_name": None,
        "owner_id": owner_id,
        "status": "pending",
        "current_speaker": None,
        "created_at": db.now(),
    })

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⚖️ Создать суд", callback_data=f"create_court:{court['id']}")
    ]])
    sent = await message.answer(
        f"‼️\n{mention(from_user.first_name, from_user.id)} вызывает в суд {mention(target_name, target_id)}.\n‼️",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )
    db.court_update(court["id"], {"announcement_msg_id": sent.message_id})

    await asyncio.sleep(1)
    try:
        owner_member = await bot.get_chat_member(chat.id, owner_id)
        await bot.send_message(
            chat.id,
            f"✔️\nВызван {mention(owner_member.user.first_name, owner_id)} (Владелец).\nОжидайте создания Суда.\n✔️",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass

async def handle_admin_lawsuit(message: Message, bot: Bot):
    if db.court_awaiting_in_origin(str(message.chat.id)):
        await message.answer("❕️ В этом чате уже создаётся суд.")
        return
    await message.answer(
        "❔️\n<b>Кто участвует в суде?</b>\n\n"
        "Введите в формате:\n"
        "<code>Истец: @user; Ответчик: @user; Свидетель: @user; Судья: @user</code>\n\n"
        "<i>Судья и свидетели — необязательны.</i>",
        parse_mode=ParseMode.HTML,
    )
    db.session_set(message.from_user.id, f"awaiting_participants:{message.chat.id}", None)

# ── Text message handler ───────────────────────────────────────────────────────

@router.message(F.text)
async def on_text(message: Message, bot: Bot):
    chat = message.chat
    from_user = message.from_user
    text = message.text or ""

    # ── Private chat ──────────────────────────────────────────────────────────
    if chat.type == "private":
        session = db.session_get(from_user.id)
        if not session:
            return
        state = session["state"]
        data = json.loads(session["data"]) if session.get("data") else {}

        if text.lower().strip() == "нет" and state == "awaiting_witnesses":
            db.session_clear(from_user.id)
            court = db.court_by_id(data.get("court_id"))
            if court:
                group = db.group_get(court["origin_chat_id"])
                if group and group.get("court_chat_id"):
                    await start_court_in_group(bot, court["id"], group["court_chat_id"])
                else:
                    db.session_set(from_user.id, "awaiting_court_group",
                                   json.dumps({"court_id": court["id"], "origin_chat_id": court["origin_chat_id"]}))
                    await message.answer("❔️ <b>В каком чате провести суд?</b>\n\nПерешлите сообщение из нужной группы.", parse_mode=ParseMode.HTML)
            return

        # Forwarded message handling
        if message.forward_from_chat and state in ("awaiting_court_group_global", "awaiting_court_group", "awaiting_origin_group"):
            await handle_court_group_forward(message, bot, state, data)
            return
        return

    # ── Group chat ────────────────────────────────────────────────────────────
    session = db.session_get(from_user.id)

    # Admin entering participants
    if session and session["state"] == f"awaiting_participants:{chat.id}":
        await handle_admin_participants(message, bot, text)
        return

    # Owner entering witnesses in group
    if session and session["state"] == "awaiting_witnesses_group":
        data = json.loads(session["data"]) if session.get("data") else {}
        if data.get("origin_chat_id") == str(chat.id):
            await handle_witnesses_in_group(message, bot, text, data)
            return

    # Judge keyboard buttons
    court = db.court_active_in_chat(str(chat.id))
    if court and court.get("judge_id") == from_user.id:
        if text == "🛑 Остановить":
            db.court_update(court["id"], {"status": "stopped"})
            witnesses = db.witnesses_by_court(court["id"])
            for uid in [court["plaintiff_id"], court["defendant_id"]] + [w["user_id"] for w in witnesses]:
                await unmute(bot, chat.id, uid)
            await message.answer(
                f"🛑 <b>Заседание прекращено.</b>\n\nДело №{court['id']} закрыто без вердикта.",
                parse_mode=ParseMode.HTML,
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        if text == "⚖️ Принять решение" and court["status"] == "in_session":
            witnesses = db.witnesses_by_court(court["id"])
            for uid in [court["plaintiff_id"], court["defendant_id"]] + [w["user_id"] for w in witnesses]:
                await mute(bot, chat.id, uid)
            db.court_update(court["id"], {"status": "deliberation"})
            await message.answer(
                "🔒 <b>Суд удаляется в совещательную комнату.</b>\n\nОжидайте решения судьи.",
                parse_mode=ParseMode.HTML,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="📋 Огласить решение")]],
                    resize_keyboard=True,
                ),
            )
            return

        if text == "📋 Огласить решение" and court["status"] == "deliberation":
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="⚖️ Виновен Истец", callback_data=f"verdict:plaintiff:{court['id']}"),
                    InlineKeyboardButton(text="⚖️ Виновен Ответчик", callback_data=f"verdict:defendant:{court['id']}"),
                ],
                [InlineKeyboardButton(text="🤝 Ничья", callback_data=f"verdict:draw:{court['id']}")],
            ])
            await message.answer("⚖️ Выберите вердикт:", reply_markup=kb)
            return

    # Session: turn management
    if court and court["status"] == "in_session":
        db.msg_add(court["id"], message.message_id, str(chat.id))
        uid = from_user.id
        witnesses = db.witnesses_by_court(court["id"])
        if uid in (court.get("judge_id"), court.get("owner_id")):
            return
        if any(w["user_id"] == uid for w in witnesses):
            return
        if court["current_speaker"] == "plaintiff" and uid == court["plaintiff_id"]:
            await mute(bot, chat.id, court["plaintiff_id"])
            await unmute(bot, chat.id, court["defendant_id"])
            db.court_update(court["id"], {"current_speaker": "defendant"})
            await bot.send_message(
                chat.id,
                f"🎤 Слово предоставляется {mention(court['defendant_name'], court['defendant_id'])} (<b>Ответчик</b>).",
                parse_mode=ParseMode.HTML,
            )
        elif court["current_speaker"] == "defendant" and uid == court["defendant_id"]:
            await mute(bot, chat.id, court["defendant_id"])
            await unmute(bot, chat.id, court["plaintiff_id"])
            db.court_update(court["id"], {"current_speaker": "plaintiff"})
            await bot.send_message(
                chat.id,
                f"🎤 Слово снова у {mention(court['plaintiff_name'], court['plaintiff_id'])} (<b>Истец</b>).",
                parse_mode=ParseMode.HTML,
            )
        return

    # Lawsuit command
    if not (is_lawsuit_cmd(text) or text.strip().startswith("/lawsuit")):
        return
    admin = await is_admin_or_owner(bot, chat.id, from_user.id)
    if admin:
        await handle_admin_lawsuit(message, bot)
    else:
        await handle_user_lawsuit(message, bot)

# ── Forwarded message in DM ────────────────────────────────────────────────────

@router.message(F.forward_from_chat)
async def on_forward(message: Message, bot: Bot):
    if message.chat.type != "private":
        return
    from_user = message.from_user
    session = db.session_get(from_user.id)
    if not session:
        return
    state = session["state"]
    data = json.loads(session["data"]) if session.get("data") else {}
    if state in ("awaiting_court_group_global", "awaiting_court_group", "awaiting_origin_group"):
        await handle_court_group_forward(message, bot, state, data)

async def handle_court_group_forward(message: Message, bot: Bot, state: str, data: dict):
    from_user = message.from_user
    court_chat_id = str(message.forward_from_chat.id)

    try:
        bm = await bot.get_chat_member(court_chat_id, bot.id)
        if bm.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
            await message.answer("❕️ Бот должен быть администратором в этом чате.")
            return
    except Exception:
        await message.answer("❕️ Бот не состоит в этом чате или нет доступа.")
        return

    if state == "awaiting_court_group_global":
        db.session_set(from_user.id, "awaiting_origin_group", json.dumps({"court_chat_id": court_chat_id}))
        await message.answer(
            "✔️ Зал суда принят!\n\nТеперь перешлите сообщение из группы <b>откуда</b> будут поступать иски.",
            parse_mode=ParseMode.HTML,
        )
        return

    if state == "awaiting_origin_group":
        db.group_set_court_chat(court_chat_id, data.get("court_chat_id", court_chat_id))
        db.session_clear(from_user.id)
        await message.answer("✔️ Готово! Зал суда привязан к группе.")
        return

    if state == "awaiting_court_group":
        court_id = data.get("court_id")
        origin_chat_id = data.get("origin_chat_id")
        if court_id and origin_chat_id:
            db.group_set_court_chat(court_chat_id, origin_chat_id)
            db.court_update(court_id, {"court_chat_id": court_chat_id})
        db.session_clear(from_user.id)
        await message.answer("✔️ Чат для суда сохранён!")
        if court_id:
            await start_court_in_group(bot, court_id, court_chat_id)

# ── Admin participants input ───────────────────────────────────────────────────

async def handle_admin_participants(message: Message, bot: Bot, text: str):
    from_user = message.from_user
    chat = message.chat
    parsed = parse_participants(text)

    if not parsed["plaintiff"] or not parsed["defendant"]:
        await message.answer(
            "❕️ Нужен минимум <b>Истец</b> и <b>Ответчик</b>.\nПример: <code>Истец: @user1; Ответчик: @user2</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    p = await resolve_username(bot, parsed["plaintiff"])
    d = await resolve_username(bot, parsed["defendant"])
    if not p:
        await message.answer(f"❕️ Не найден @{parsed['plaintiff']}.")
        return
    if not d:
        await message.answer(f"❕️ Не найден @{parsed['defendant']}.")
        return

    judge_id, judge_name = None, None
    if parsed["judge"]:
        j = await resolve_username(bot, parsed["judge"])
        if j:
            judge_id, judge_name = j

    owner_id = await get_owner_id(bot, chat.id)
    court = db.court_create({
        "origin_chat_id": str(chat.id),
        "court_chat_id": None,
        "plaintiff_id": p[0], "plaintiff_name": p[1],
        "defendant_id": d[0], "defendant_name": d[1],
        "judge_id": judge_id, "judge_name": judge_name,
        "owner_id": owner_id,
        "status": "awaiting_court",
        "current_speaker": None,
        "created_at": db.now(),
    })

    for w_un in parsed["witnesses"][:5]:
        w = await resolve_username(bot, w_un)
        if w:
            db.witness_add({"court_id": court["id"], "user_id": w[0], "user_name": w[1], "left_court": False})

    db.session_clear(from_user.id)
    group = db.group_get(str(chat.id))
    if group and group.get("court_chat_id"):
        await start_court_in_group(bot, court["id"], group["court_chat_id"])
    else:
        db.session_set(from_user.id, "awaiting_court_group",
                       json.dumps({"court_id": court["id"], "origin_chat_id": str(chat.id)}))
        await message.answer(
            "❔️ <b>В каком чате провести суд?</b>\n\nПерешлите сообщение из нужной группы.",
            parse_mode=ParseMode.HTML,
        )

async def handle_witnesses_in_group(message: Message, bot: Bot, text: str, data: dict):
    from_user = message.from_user
    court_id = data["court_id"]
    court = db.court_by_id(court_id)
    if not court:
        return
    for w_un in re.findall(r"@(\w+)", text)[:5]:
        w = await resolve_username(bot, w_un)
        if w:
            db.witness_add({"court_id": court_id, "user_id": w[0], "user_name": w[1], "left_court": False})
    db.session_clear(from_user.id)
    group = db.group_get(court["origin_chat_id"])
    if group and group.get("court_chat_id"):
        await start_court_in_group(bot, court_id, group["court_chat_id"])
    else:
        db.session_set(from_user.id, "awaiting_court_group",
                       json.dumps({"court_id": court_id, "origin_chat_id": court["origin_chat_id"]}))
        await message.answer("❔️ <b>В каком чате провести суд?</b>\n\nПерешлите сообщение из нужной группы.", parse_mode=ParseMode.HTML)

# ── Callbacks ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("create_court:"))
async def cb_create_court(call: CallbackQuery, bot: Bot):
    court_id = int(call.data.split(":")[1])
    from_user = call.from_user
    court = db.court_by_id(court_id)

    if not court or court["status"] != "pending":
        await call.answer("❕️ Суд уже обрабатывается.", show_alert=True)
        return
    if not await is_owner_check(bot, court["origin_chat_id"], from_user.id):
        await call.answer("❕️ Только владелец группы может создать суд.", show_alert=True)
        return

    await call.answer()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    db.court_update(court_id, {"status": "awaiting_court"})
    await bot.send_message(
        court["origin_chat_id"],
        f"✔️ {mention(from_user.first_name, from_user.id)} открывает заседание.\n\n"
        f"<i>Укажи свидетелей (до 5) или напиши «нет».</i>\n"
        f"Формат: <code>@username; @username</code>",
        parse_mode=ParseMode.HTML,
    )
    db.session_set(from_user.id, "awaiting_witnesses", json.dumps({"court_id": court_id}))

@router.callback_query(F.data.regexp(r"^verdict:(plaintiff|defendant|draw):(\d+)$"))
async def cb_verdict(call: CallbackQuery, bot: Bot):
    m = re.match(r"^verdict:(plaintiff|defendant|draw):(\d+)$", call.data)
    verdict, court_id = m.group(1), int(m.group(2))
    from_user = call.from_user
    court = db.court_by_id(court_id)
    if not court or court.get("judge_id") != from_user.id:
        await call.answer()
        return

    await call.answer()
    db.court_update(court_id, {"status": "concluded"})
    witnesses = db.witnesses_by_court(court_id)
    for uid in [court["plaintiff_id"], court["defendant_id"]] + [w["user_id"] for w in witnesses]:
        await unmute(bot, court["court_chat_id"], uid)

    judge_mention = mention(court["judge_name"] or "Судья", court["judge_id"] or 0)
    if verdict == "draw":
        text = f"⚖️ <b>Решение суда — Дело №{court_id}</b>\n\nСудья {judge_mention} выносит вердикт:\n\n🤝 <b>Ничья.</b>"
    else:
        if verdict == "plaintiff":
            g_id, g_name = court["plaintiff_id"], court["plaintiff_name"]
            i_id, i_name = court["defendant_id"], court["defendant_name"]
        else:
            g_id, g_name = court["defendant_id"], court["defendant_name"]
            i_id, i_name = court["plaintiff_id"], court["plaintiff_name"]
        text = (
            f"⚖️ <b>Решение суда — Дело №{court_id}</b>\n\n"
            f"Судья {judge_mention} выносит вердикт:\n\n"
            f"🔴 <b>Виновен:</b> {mention(g_name, g_id)}\n"
            f"✅ <b>Оправдан:</b> {mention(i_name, i_id)}"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🗑 Удалить историю и участников", callback_data=f"cleanup:{court_id}")
    ]])
    await bot.send_message(court["court_chat_id"], text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await bot.send_message(court["court_chat_id"], "⚖️ Заседание завершено.", reply_markup=ReplyKeyboardRemove())

@router.callback_query(F.data.startswith("cleanup:"))
async def cb_cleanup(call: CallbackQuery, bot: Bot):
    court_id = int(call.data.split(":")[1])
    from_user = call.from_user
    court = db.court_by_id(court_id)
    if not court or not court.get("court_chat_id"):
        await call.answer()
        return

    owner_ok = await is_owner_check(bot, court["origin_chat_id"], from_user.id)
    is_judge = court.get("judge_id") == from_user.id
    if not owner_ok and not is_judge:
        await call.answer("❕️ Только владелец или судья могут очистить зал.", show_alert=True)
        return

    await call.answer()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    chat_id = court["court_chat_id"]
    await bot.send_message(chat_id, "🗑 <b>Зал суда очищается...</b>", parse_mode=ParseMode.HTML)

    witnesses = db.witnesses_by_court(court_id)
    to_kick = [court["plaintiff_id"], court["defendant_id"]] + [w["user_id"] for w in witnesses]
    if court.get("judge_id"):
        to_kick.append(court["judge_id"])

    for uid in to_kick:
        if uid == court.get("owner_id"):
            continue
        try:
            await bot.ban_chat_member(chat_id, uid)
            await bot.unban_chat_member(chat_id, uid)
        except Exception:
            pass

    for m in db.msgs_by_court(court_id):
        try:
            await bot.delete_message(m["chat_id"], m["message_id"])
        except Exception:
            pass

    await bot.send_message(chat_id, f"✔️ <b>Суд завершён.</b> Дело №{court_id} закрыто.", parse_mode=ParseMode.HTML)

# ── Start court in group ───────────────────────────────────────────────────────

async def start_court_in_group(bot: Bot, court_id: int, court_chat_id: str):
    court = db.court_by_id(court_id)
    if not court:
        return

    witnesses = db.witnesses_by_court(court_id)
    participants = f"{mention(court['plaintiff_name'], court['plaintiff_id'])} — Истец\n"
    participants += f"{mention(court['defendant_name'], court['defendant_id'])} — Ответчик\n"
    if court.get("judge_id") and court.get("judge_name"):
        participants += f"{mention(court['judge_name'], court['judge_id'])} — Судья\n"
    else:
        participants += "<i>Судья не назначен</i>\n"
    for w in witnesses:
        participants += f"{mention(w['user_name'], w['user_id'])} — Свидетель\n"

    db.court_update(court_id, {
        "status": "in_session",
        "court_chat_id": court_chat_id,
        "current_speaker": "plaintiff",
    })

    await bot.send_message(
        court_chat_id,
        f"⚖️ <b>Заседание суда. Дело №{court_id}</b>\n\n<b>Состав:</b>\n{participants}",
        parse_mode=ParseMode.HTML,
    )

    await mute(bot, court_chat_id, court["plaintiff_id"])
    await mute(bot, court_chat_id, court["defendant_id"])
    for w in witnesses:
        await mute(bot, court_chat_id, w["user_id"])

    await asyncio.sleep(2)
    await unmute(bot, court_chat_id, court["plaintiff_id"])
    await bot.send_message(
        court_chat_id,
        f"⚖️ <b>Суд начат!</b>\n\n🎤 Слово предоставляется {mention(court['plaintiff_name'], court['plaintiff_id'])} (<b>Истец</b>).\n\n<i>После вашего сообщения слово перейдёт к Ответчику.</i>",
        parse_mode=ParseMode.HTML,
    )

    if court.get("judge_id") and court.get("judge_name"):
        await bot.send_message(
            court_chat_id,
            f"💼 {mention(court['judge_name'], court['judge_id'])} — Вы Судья.",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="🛑 Остановить"), KeyboardButton(text="⚖️ Принять решение")]],
                resize_keyboard=True,
            ),
        )

# ── Keep-alive & self-ping ────────────────────────────────────────────────────

async def keepalive_handler(request):
    return web.Response(text="OK")

async def run_keepalive():
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", keepalive_handler)
    app.router.add_get("/ping", keepalive_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Keep-alive server running on port {port}")

async def self_ping_loop():
    if not RENDER_URL:
        return
    import aiohttp
    while True:
        await asyncio.sleep(14 * 60)
        try:
            async with aiohttp.ClientSession() as session:
                await session.get(f"{RENDER_URL}/ping", timeout=aiohttp.ClientTimeout(total=10))
        except Exception:
            pass

# ── Facts ─────────────────────────────────────────────────────────────────────

async def send_facts(bot: Bot):
    global fact_index
    groups = db.groups_all()
    fact = FACTS[fact_index % len(FACTS)]
    fact_index += 1
    for group in groups:
        try:
            await bot.send_message(
                group["chat_id"],
                f"💼 <b>Интересный факт:</b>\n\n{fact}",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: asyncio.ensure_future(send_facts(bot)), "cron", hour="*/2", minute=0)
    scheduler.start()

    await run_keepalive()
    asyncio.ensure_future(self_ping_loop())

    logger.info("CaseSolve бот запускается...")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
