import asyncio
import json
import logging
import os
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import (
    Bot,
    CallbackQuery,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TOKEN_BOT")
if not TOKEN:
    raise RuntimeError("TOKEN_BOT не задан! Установи его в переменных окружения Render.")

RENDER_URL = os.environ.get("RENDER_URL", "")

# ── Facts ─────────────────────────────────────────────────────────────────────

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
    "🦩 У фламинго колени сгибаются назад — то, что мы видим как колено, это на самом деле лодыжка.",
    "🐳 Синий кит весит столько же, сколько 30 слонов.",
    "🦭 Тюлени могут задерживать дыхание на 2 часа.",
    "🐻‍❄️ Белые медведи не белые — их шерсть прозрачная и полая внутри.",
    "🦅 Орлы могут видеть добычу с расстояния 3 километра.",
    "🐆 Гепард разгоняется до 120 км/ч за 3 секунды.",
    "🦒 У жирафа такое же количество позвонков в шее, как и у человека — семь.",
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
    "🌋 На дне океана больше вулканов, чем на суше.",
    "🧠 Мозг человека потребляет 20% всей энергии тела.",
    "💤 Человек проводит треть жизни во сне.",
    "👁 Человеческий глаз различает около 10 миллионов оттенков цвета.",
    "🦷 Зубы — единственная часть тела человека, которая не может восстановиться.",
    "❤️ Сердце бьётся около 100 000 раз в день.",
    "🍯 Мёд не портится — в египетских гробницах нашли мёд возрастом 3000 лет.",
    "🍕 Томаты — это ягоды с точки зрения ботаники.",
    "☕ Кофе был открыт благодаря козам — пастух заметил, что они не спали после поедания ягод.",
    "🍫 Шоколад был валютой у ацтеков.",
    "🥑 Авокадо — фрукт, а точнее, ягода.",
    "🧀 В мире более 1800 сортов сыра.",
    "🍎 Яблоки на 25% состоят из воздуха — поэтому они плавают.",
    "🚀 До Луны можно добраться за 3 дня, до Марса — от 7 месяцев.",
    "🛸 В Солнечной системе больше 200 известных лун.",
    "⭐ Солнце составляет 99,86% массы всей Солнечной системы.",
    "🌌 Галактика Млечный Путь содержит от 200 до 400 миллиардов звёзд.",
    "🔭 Свет от ближайшей звезды (Проксима Центавра) идёт до Земли 4,2 года.",
    "🪐 На Сатурне есть бури размером больше Земли.",
    "💫 Нейтронная звезда имеет размер города, но массу больше Солнца.",
    "🌐 В интернете более 5 миллиардов веб-страниц.",
    "📱 Современный смартфон мощнее компьютеров, которые отправили человека на Луну.",
    "🔋 Первые батарейки были изобретены в 1800 году.",
    "💻 Первый компьютер весил 27 тонн и занимал целую комнату.",
    "📡 Данные со спутника Voyager 1 идут до Земли более 22 часов.",
    "🎮 Видеоигры — индустрия с оборотом больше, чем кино и музыка вместе взятые.",
    "🤖 Первый робот был создан в 1954 году для работы на заводе.",
    "🐈 Кошки мяукают только для общения с людьми, но не друг с другом.",
    "🐕 Собаки понимают около 250 слов и жестов.",
    "🐇 Кролики не могут рвать, поэтому плохая еда для них смертельна.",
    "🐟 Золотые рыбки помнят информацию до 3 месяцев — миф о 3 секундах.",
    "🦜 Попугаи ара живут до 80 лет — дольше многих людей.",
    "🐓 Куры видят в ультрафиолете.",
    "🦔 Ёж иммунен к яду многих змей.",
    "🐿 Белки забывают, где спрятали 74% своих запасов, помогая лесам расти.",
    "🦦 Выдры держатся за лапы во время сна, чтобы не разлучиться.",
    "🐬 Дельфины дают имена друг другу и откликаются на них.",
]

# ── Utils ─────────────────────────────────────────────────────────────────────

def mention(first_name: str, user_id: int) -> str:
    name = first_name.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
    return f'<a href="tg://user?id={user_id}">{name}</a>'

MUTE_PERMS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
)
UNMUTE_PERMS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
)

async def mute(bot: Bot, chat_id, user_id: int):
    try:
        await bot.restrict_chat_member(chat_id, user_id, MUTE_PERMS)
    except Exception:
        pass

async def unmute(bot: Bot, chat_id, user_id: int):
    try:
        await bot.restrict_chat_member(chat_id, user_id, UNMUTE_PERMS)
    except Exception:
        pass

async def get_owner_id(bot: Bot, chat_id) -> int | None:
    try:
        admins = await bot.get_chat_administrators(chat_id)
        for a in admins:
            if a.status == "creator":
                return a.user.id
    except Exception:
        pass
    return None

async def is_admin_or_owner(bot: Bot, chat_id, user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except Exception:
        return False

async def is_owner(bot: Bot, chat_id, user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status == "creator"
    except Exception:
        return False

# ── Commands ──────────────────────────────────────────────────────────────────

HELP_TEXT = """
<b>⚖️ Команды CaseSolve:</b>

<b>Участники:</b>
• <code>! суд @username</code> — подать иск
• <code>! суд</code> (в ответ) — иск против автора
• <code>/lawsuit @username</code> — то же самое

<b>Для администраторов:</b>
• <code>! суд</code> или <code>/lawsuit</code> — создать суд вручную

<b>В личных сообщениях (владелец):</b>
• <code>/настройки</code> — настроить зал суда

<b>Другие:</b>
• <code>/help</code> — это сообщение
""".strip()

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    await update.message.reply_text(
        f"⚖️ <b>Добро пожаловать в CaseSolve!</b>\n\nДобавьте меня в группу с правами администратора.\n\n{HELP_TEXT}",
        parse_mode="HTML",
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="HTML")

async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("⚙️ Настройки доступны только в личных сообщениях.")
        return
    await update.message.reply_text(
        "⚙️ <b>Настройка зала суда</b>\n\nПерешлите любое сообщение из группы, которую хотите назначить <b>залом суда</b>.\n\n<i>Ожидаю пересланное сообщение...</i>",
        parse_mode="HTML",
    )
    db.session_set(update.effective_user.id, "awaiting_court_group_global", None)

# ── Bot added to group ────────────────────────────────────────────────────────

async def on_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    if not result:
        return
    chat = result.chat
    if chat.type not in ("group", "supergroup"):
        return
    new_status = result.new_chat_member.status
    if new_status not in ("member", "administrator"):
        return
    db.group_upsert(str(chat.id), getattr(chat, "title", None))
    owner_id = await get_owner_id(context.bot, chat.id)
    if owner_id:
        db.group_set_owner(owner_id, str(chat.id))
    await context.bot.send_message(
        chat.id,
        f"⚖️ <b>Привет! Я — CaseSolve.</b>\n\nПомогаю организовать разбирательства в группе.\n\n{HELP_TEXT}",
        parse_mode="HTML",
    )

# ── Lawsuit flow ──────────────────────────────────────────────────────────────

def is_lawsuit_cmd(text: str) -> bool:
    return bool(text and text.strip().lower().startswith("! суд"))

def extract_target(text: str) -> str | None:
    parts = text.strip().split()
    for i, p in enumerate(parts):
        if p.lower() == "суд" and i + 1 < len(parts):
            nxt = parts[i + 1]
            if nxt.startswith("@"):
                return nxt[1:]
    return None

async def handle_user_lawsuit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    from_user = update.effective_user

    target_id = None
    target_name = ""

    if msg.reply_to_message and msg.reply_to_message.from_user:
        replied = msg.reply_to_message.from_user
        if replied.is_bot:
            await msg.reply_text("❕️ Нельзя подавать иск на бота.")
            return
        target_id = replied.id
        target_name = replied.first_name
    else:
        username = extract_target(msg.text or "")
        if not username:
            await msg.reply_text(
                "❔️ Укажите ответчика.\nПример: <code>! суд @username</code>",
                parse_mode="HTML",
            )
            return
        try:
            target_chat = await context.bot.get_chat(f"@{username}")
            target_id = target_chat.id
            target_name = getattr(target_chat, "first_name", username)
        except Exception:
            await msg.reply_text(f"❕️ Не удалось найти @{username}.")
            return

    if target_id == from_user.id:
        await msg.reply_text("❕️ Нельзя подавать иск на самого себя.")
        return

    existing = db.court_awaiting_in_origin(str(chat.id))
    if existing:
        await msg.reply_text("❕️ В этом чате уже создаётся суд. Ожидайте.")
        return

    owner_id = await get_owner_id(context.bot, chat.id)
    if not owner_id:
        await msg.reply_text("❕️ Не удалось найти владельца группы.")
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

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("⚖️ Создать суд", callback_data=f"create_court:{court['id']}")
    ]])
    sent = await msg.reply_text(
        f"‼️\n{mention(from_user.first_name, from_user.id)} вызывает в суд {mention(target_name, target_id)}.\n‼️",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    db.court_update(court["id"], {"announcement_msg_id": sent.message_id})

    await asyncio.sleep(1)
    try:
        owner_member = await context.bot.get_chat_member(chat.id, owner_id)
        owner_name = owner_member.user.first_name
        await context.bot.send_message(
            chat.id,
            f"✔️\nВызван {mention(owner_name, owner_id)} (Владелец группы).\nОжидайте создания Суда.\n✔️",
            parse_mode="HTML",
        )
    except Exception:
        pass

async def handle_admin_lawsuit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    from_user = update.effective_user
    chat = update.effective_chat

    existing = db.court_awaiting_in_origin(str(chat.id))
    if existing:
        await msg.reply_text("❕️ В этом чате уже создаётся суд.")
        return

    await msg.reply_text(
        "❔️\n<b>Кто участвует в этом суде?</b>\n\n"
        "Введите в формате:\n"
        "<code>Истец: @username; Ответчик: @username; Свидетель: @username; Судья: @username</code>\n\n"
        "<i>Судья и свидетели — необязательны.</i>\n❕️",
        parse_mode="HTML",
    )
    db.session_set(from_user.id, f"awaiting_participants:{chat.id}", None)

async def lawsuit_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    from_user = update.effective_user
    text = msg.text or ""

    if chat.type == "private":
        await handle_dm_message(update, context)
        return

    # Check admin session
    session = db.session_get(from_user.id)
    if session:
        state = session["state"]
        if state == f"awaiting_participants:{chat.id}":
            await handle_admin_participants(update, context, text)
            return
        if state == "awaiting_witnesses_group" and session.get("data"):
            data = json.loads(session["data"])
            if data.get("origin_chat_id") == str(chat.id):
                await handle_witnesses_text(update, context, text, data)
                return

    if not (is_lawsuit_cmd(text) or text.strip().startswith("/lawsuit")):
        await handle_session_message(update, context)
        return

    admin = await is_admin_or_owner(context.bot, chat.id, from_user.id)
    if admin:
        await handle_admin_lawsuit(update, context)
    else:
        await handle_user_lawsuit(update, context)

async def cmd_lawsuit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    from_user = update.effective_user
    if chat.type == "private":
        await update.message.reply_text("⚖️ Команда /lawsuit работает только в группах.")
        return
    admin = await is_admin_or_owner(context.bot, chat.id, from_user.id)
    if admin:
        await handle_admin_lawsuit(update, context)
    else:
        await handle_user_lawsuit(update, context)

# ── Admin participants input ───────────────────────────────────────────────────

def parse_participants(text: str) -> dict:
    result = {"plaintiff": None, "defendant": None, "witnesses": [], "judge": None}
    for part in text.split(";"):
        part = part.strip()
        lower = part.lower()
        match = None
        import re
        m = re.search(r"@(\w+)", part)
        if m:
            match = m.group(1)
        if "истец" in lower and match:
            result["plaintiff"] = match
        elif "ответчик" in lower and match:
            result["defendant"] = match
        elif "свидетел" in lower and match:
            result["witnesses"].append(match)
        elif "судья" in lower and match:
            result["judge"] = match
    return result

async def resolve_username(bot: Bot, username: str) -> tuple[int, str] | None:
    try:
        chat = await bot.get_chat(f"@{username}")
        return chat.id, getattr(chat, "first_name", username)
    except Exception:
        return None

async def handle_admin_participants(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    msg = update.effective_message
    from_user = update.effective_user
    chat = update.effective_chat

    parsed = parse_participants(text)
    if not parsed["plaintiff"] or not parsed["defendant"]:
        await msg.reply_text(
            "❕️ Укажите хотя бы <b>Истца</b> и <b>Ответчика</b>.\n"
            "Пример: <code>Истец: @user1; Ответчик: @user2</code>",
            parse_mode="HTML",
        )
        return

    p_res = await resolve_username(context.bot, parsed["plaintiff"])
    d_res = await resolve_username(context.bot, parsed["defendant"])
    if not p_res:
        await msg.reply_text(f"❕️ Не найден @{parsed['plaintiff']}.")
        return
    if not d_res:
        await msg.reply_text(f"❕️ Не найден @{parsed['defendant']}.")
        return

    judge_id, judge_name = None, None
    if parsed["judge"]:
        j_res = await resolve_username(context.bot, parsed["judge"])
        if j_res:
            judge_id, judge_name = j_res

    owner_id = await get_owner_id(context.bot, chat.id)
    court = db.court_create({
        "origin_chat_id": str(chat.id),
        "court_chat_id": None,
        "plaintiff_id": p_res[0],
        "plaintiff_name": p_res[1],
        "defendant_id": d_res[0],
        "defendant_name": d_res[1],
        "judge_id": judge_id,
        "judge_name": judge_name,
        "owner_id": owner_id,
        "status": "awaiting_court",
        "current_speaker": None,
        "created_at": db.now(),
    })

    for w_username in parsed["witnesses"][:5]:
        w_res = await resolve_username(context.bot, w_username)
        if w_res:
            db.witness_add({"court_id": court["id"], "user_id": w_res[0], "user_name": w_res[1], "left_court": False})

    db.session_clear(from_user.id)

    group = db.group_get(str(chat.id))
    if group and group.get("court_chat_id"):
        await start_court_in_group(context.bot, court["id"], group["court_chat_id"])
    else:
        db.session_set(
            from_user.id,
            "awaiting_court_group",
            json.dumps({"court_id": court["id"], "origin_chat_id": str(chat.id)}),
        )
        await msg.reply_text(
            "❔️ <b>В каком чате провести суд?</b>\n\nПерешлите сообщение из нужной группы.",
            parse_mode="HTML",
        )

async def handle_witnesses_text(update, context, text: str, data: dict):
    from_user = update.effective_user
    court_id = data["court_id"]
    court = db.court_by_id(court_id)
    if not court:
        return
    import re
    usernames = re.findall(r"@(\w+)", text)
    for w_username in usernames[:5]:
        w_res = await resolve_username(context.bot, w_username)
        if w_res:
            db.witness_add({"court_id": court_id, "user_id": w_res[0], "user_name": w_res[1], "left_court": False})
    db.session_clear(from_user.id)
    group = db.group_get(court["origin_chat_id"])
    if group and group.get("court_chat_id"):
        await start_court_in_group(context.bot, court_id, group["court_chat_id"])
    else:
        db.session_set(
            from_user.id,
            "awaiting_court_group",
            json.dumps({"court_id": court_id, "origin_chat_id": court["origin_chat_id"]}),
        )
        await update.effective_message.reply_text(
            "❔️ <b>В каком чате провести суд?</b>\n\nПерешлите сообщение из нужной группы.",
            parse_mode="HTML",
        )

# ── DM handler (forwards for court group setup) ───────────────────────────────

async def handle_dm_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    from_user = update.effective_user
    text = msg.text or ""

    session = db.session_get(from_user.id)
    if not session:
        return

    state = session["state"]
    data = json.loads(session["data"]) if session.get("data") else {}

    # Нет (skip witnesses)
    if text.lower().strip() == "нет" and state == "awaiting_witnesses":
        db.session_clear(from_user.id)
        court = db.court_by_id(data.get("court_id"))
        if court:
            group = db.group_get(court["origin_chat_id"])
            if group and group.get("court_chat_id"):
                await start_court_in_group(context.bot, court["id"], group["court_chat_id"])
            else:
                db.session_set(
                    from_user.id,
                    "awaiting_court_group",
                    json.dumps({"court_id": court["id"], "origin_chat_id": court["origin_chat_id"]}),
                )
                await msg.reply_text(
                    "❔️ <b>В каком чате провести суд?</b>\n\nПерешлите сообщение из нужной группы.",
                    parse_mode="HTML",
                )
        return

    # Forwarded message for court group
    fwd_chat = getattr(msg, "forward_from_chat", None) or getattr(msg, "forward_origin", None)
    if fwd_chat and state in ("awaiting_court_group_global", "awaiting_court_group", "awaiting_origin_group"):
        await handle_court_group_forward(update, context, state, data)

async def handle_court_group_forward(update: Update, context: ContextTypes.DEFAULT_TYPE, state: str, data: dict):
    msg = update.effective_message
    from_user = update.effective_user

    court_chat_id = None
    fwd_chat = getattr(msg, "forward_from_chat", None)
    if fwd_chat:
        court_chat_id = str(fwd_chat.id)
    else:
        fwd_origin = getattr(msg, "forward_origin", None)
        if fwd_origin and hasattr(fwd_origin, "chat"):
            court_chat_id = str(fwd_origin.chat.id)

    if not court_chat_id:
        await msg.reply_text("❕️ Не удалось определить чат. Перешлите сообщение из нужной группы.")
        return

    try:
        bot_member = await context.bot.get_chat_member(court_chat_id, context.bot.id)
        if bot_member.status not in ("administrator", "creator"):
            await msg.reply_text("❕️ Бот должен быть администратором в этом чате.")
            return
    except Exception:
        await msg.reply_text("❕️ Бот не состоит в этом чате или нет доступа.")
        return

    if state == "awaiting_court_group_global":
        db.session_set(
            from_user.id,
            "awaiting_origin_group",
            json.dumps({"court_chat_id": court_chat_id}),
        )
        await msg.reply_text(
            "✔️ Зал суда принят!\n\nТеперь перешлите сообщение из группы <b>откуда</b> будут поступать иски.",
            parse_mode="HTML",
        )
        return

    if state == "awaiting_origin_group":
        origin_chat_id = data.get("court_chat_id")
        if origin_chat_id:
            db.group_set_court_chat(court_chat_id, origin_chat_id)
        db.session_clear(from_user.id)
        await msg.reply_text("✔️ Готово! Зал суда привязан к группе.")
        return

    if state == "awaiting_court_group":
        court_id = data.get("court_id")
        origin_chat_id = data.get("origin_chat_id")
        if court_id and origin_chat_id:
            db.group_set_court_chat(court_chat_id, origin_chat_id)
            db.court_update(court_id, {"court_chat_id": court_chat_id})
        db.session_clear(from_user.id)
        await msg.reply_text("✔️ Чат для суда сохранён!")
        if court_id:
            await start_court_in_group(context.bot, court_id, court_chat_id)

# ── Callbacks ─────────────────────────────────────────────────────────────────

async def cb_create_court(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query: CallbackQuery = update.callback_query
    await query.answer()
    from_user = query.from_user
    court_id = int(context.matches[0].group(1))

    court = db.court_by_id(court_id)
    if not court or court["status"] != "pending":
        await query.answer("❕️ Суд уже обрабатывается или не найден.", show_alert=True)
        return

    owner_ok = await is_owner(context.bot, court["origin_chat_id"], from_user.id)
    if not owner_ok:
        await query.answer("❕️ Только владелец группы может создать суд.", show_alert=True)
        return

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    db.court_update(court_id, {"status": "awaiting_court"})

    await context.bot.send_message(
        court["origin_chat_id"],
        f"✔️ {mention(from_user.first_name, from_user.id)} открывает судебное заседание.\n\n"
        f"<i>Укажите свидетелей (до 5) или напишите «нет».</i>\n"
        f"Формат: <code>@username; @username</code>",
        parse_mode="HTML",
    )
    db.session_set(
        from_user.id,
        "awaiting_witnesses",
        json.dumps({"court_id": court_id}),
    )

async def cb_verdict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query: CallbackQuery = update.callback_query
    await query.answer()
    from_user = query.from_user
    verdict = context.matches[0].group(1)  # plaintiff / defendant / draw

    court_id = int(context.matches[0].group(2))
    court = db.court_by_id(court_id)
    if not court or court.get("judge_id") != from_user.id:
        return

    db.court_update(court_id, {"status": "concluded"})
    witnesses = db.witnesses_by_court(court_id)
    all_users = [court["plaintiff_id"], court["defendant_id"]] + [w["user_id"] for w in witnesses]
    for uid in all_users:
        await unmute(context.bot, court["court_chat_id"], uid)

    if verdict == "draw":
        text = (
            f"⚖️ <b>Решение суда — Дело №{court_id}</b>\n\n"
            f"Судья {mention(court['judge_name'] or 'Судья', court['judge_id'] or 0)} выносит вердикт:\n\n"
            f"🤝 <b>Ничья.</b> Стороны признаны равно правыми."
        )
    else:
        if verdict == "plaintiff":
            guilty_id, guilty_name = court["plaintiff_id"], court["plaintiff_name"]
            innocent_id, innocent_name = court["defendant_id"], court["defendant_name"]
        else:
            guilty_id, guilty_name = court["defendant_id"], court["defendant_name"]
            innocent_id, innocent_name = court["plaintiff_id"], court["plaintiff_name"]
        text = (
            f"⚖️ <b>Решение суда — Дело №{court_id}</b>\n\n"
            f"Судья {mention(court['judge_name'] or 'Судья', court['judge_id'] or 0)} выносит вердикт:\n\n"
            f"🔴 <b>Виновен:</b> {mention(guilty_name, guilty_id)}\n"
            f"✅ <b>Оправдан:</b> {mention(innocent_name, innocent_id)}"
        )

    cleanup_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🗑 Удалить историю и участников", callback_data=f"cleanup:{court_id}")
    ]])
    await context.bot.send_message(court["court_chat_id"], text, parse_mode="HTML", reply_markup=cleanup_kb)
    await context.bot.send_message(
        court["court_chat_id"], "⚖️ Заседание завершено.",
        reply_markup=ReplyKeyboardRemove()
    )

async def cb_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query: CallbackQuery = update.callback_query
    await query.answer()
    from_user = query.from_user
    court_id = int(context.matches[0].group(1))

    court = db.court_by_id(court_id)
    if not court or not court.get("court_chat_id"):
        return

    owner_ok = await is_owner(context.bot, court["origin_chat_id"], from_user.id)
    is_judge = court.get("judge_id") == from_user.id
    if not owner_ok and not is_judge:
        await query.answer("❕️ Только владелец или судья могут очистить зал.", show_alert=True)
        return

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    chat_id = court["court_chat_id"]
    await context.bot.send_message(chat_id, "🗑 <b>Зал суда очищается...</b>", parse_mode="HTML")

    witnesses = db.witnesses_by_court(court_id)
    to_kick = [court["plaintiff_id"], court["defendant_id"]] + [w["user_id"] for w in witnesses]
    if court.get("judge_id"):
        to_kick.append(court["judge_id"])

    for uid in to_kick:
        if uid == court.get("owner_id"):
            continue
        try:
            await context.bot.ban_chat_member(chat_id, uid)
            await context.bot.unban_chat_member(chat_id, uid)
        except Exception:
            pass

    messages = db.msgs_by_court(court_id)
    for m in messages:
        try:
            await context.bot.delete_message(m["chat_id"], m["message_id"])
        except Exception:
            pass

    await context.bot.send_message(
        chat_id,
        f"✔️ <b>Суд завершён.</b>\n\nДело №{court_id} закрыто. Участники удалены.",
        parse_mode="HTML",
    )

# ── Session: keyboard buttons ─────────────────────────────────────────────────

async def handle_keyboard_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    from_user = update.effective_user
    chat = update.effective_chat
    text = msg.text or ""

    if chat.type == "private":
        return

    chat_id = str(chat.id)
    court = db.court_active_in_chat(chat_id)
    if not court or court.get("judge_id") != from_user.id:
        return

    if text == "🛑 Остановить":
        db.court_update(court["id"], {"status": "stopped"})
        witnesses = db.witnesses_by_court(court["id"])
        all_users = [court["plaintiff_id"], court["defendant_id"]] + [w["user_id"] for w in witnesses]
        for uid in all_users:
            await unmute(context.bot, chat.id, uid)
        await msg.reply_text(
            f"🛑 <b>Заседание суда прекращено.</b>\n\nДело №{court['id']} закрыто без вердикта.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )

    elif text == "⚖️ Принять решение" and court["status"] == "in_session":
        witnesses = db.witnesses_by_court(court["id"])
        all_users = [court["plaintiff_id"], court["defendant_id"]] + [w["user_id"] for w in witnesses]
        for uid in all_users:
            await mute(context.bot, chat.id, uid)
        db.court_update(court["id"], {"status": "deliberation"})
        await msg.reply_text(
            "🔒 <b>Суд удаляется в совещательную комнату.</b>\n\nОжидайте решения судьи.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup([[{"text": "📋 Огласить решение"}]], resize_keyboard=True),
        )

    elif text == "📋 Огласить решение" and court["status"] == "deliberation":
        verdict_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚖️ Виновен Истец", callback_data=f"verdict:plaintiff:{court['id']}"),
                InlineKeyboardButton("⚖️ Виновен Ответчик", callback_data=f"verdict:defendant:{court['id']}"),
            ],
            [InlineKeyboardButton("🤝 Ничья", callback_data=f"verdict:draw:{court['id']}")],
        ])
        await msg.reply_text("⚖️ Выберите вердикт:", reply_markup=verdict_kb)

# ── Session: turn management ──────────────────────────────────────────────────

async def handle_session_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    from_user = update.effective_user
    chat = update.effective_chat
    if not from_user or from_user.is_bot:
        return

    chat_id = str(chat.id)
    court = db.court_active_in_chat(chat_id)
    if not court or court["status"] != "in_session":
        return

    db.msg_add(court["id"], msg.message_id, chat_id)

    from_id = from_user.id
    if court.get("judge_id") == from_id or court.get("owner_id") == from_id:
        return

    witnesses = db.witnesses_by_court(court["id"])
    if any(w["user_id"] == from_id for w in witnesses):
        return

    if court["current_speaker"] == "plaintiff" and from_id == court["plaintiff_id"]:
        await mute(context.bot, chat.id, court["plaintiff_id"])
        await unmute(context.bot, chat.id, court["defendant_id"])
        db.court_update(court["id"], {"current_speaker": "defendant"})
        await context.bot.send_message(
            chat.id,
            f"🎤 Слово предоставляется {mention(court['defendant_name'], court['defendant_id'])} (<b>Ответчик</b>).",
            parse_mode="HTML",
        )

    elif court["current_speaker"] == "defendant" and from_id == court["defendant_id"]:
        await mute(context.bot, chat.id, court["defendant_id"])
        await unmute(context.bot, chat.id, court["plaintiff_id"])
        db.court_update(court["id"], {"current_speaker": "plaintiff"})
        await context.bot.send_message(
            chat.id,
            f"🎤 Слово снова у {mention(court['plaintiff_name'], court['plaintiff_id'])} (<b>Истец</b>).",
            parse_mode="HTML",
        )

# ── Start court in group ──────────────────────────────────────────────────────

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

    db.court_update(court_id, {"status": "in_session", "court_chat_id": court_chat_id, "current_speaker": "plaintiff"})

    await bot.send_message(
        court_chat_id,
        f"⚖️ <b>Заседание суда. Дело №{court_id}</b>\n\n<b>Состав:</b>\n{participants}",
        parse_mode="HTML",
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
        parse_mode="HTML",
    )

    if court.get("judge_id") and court.get("judge_name"):
        judge_kb = ReplyKeyboardMarkup(
            [[{"text": "🛑 Остановить"}, {"text": "⚖️ Принять решение"}]],
            resize_keyboard=True,
        )
        await bot.send_message(
            court_chat_id,
            f"💼 {mention(court['judge_name'], court['judge_id'])} — Вы Судья. Используйте клавиатуру для управления заседанием.",
            parse_mode="HTML",
            reply_markup=judge_kb,
        )

# ── Facts scheduler ───────────────────────────────────────────────────────────

fact_index = [random.randint(0, len(FACTS) - 1)]

async def send_facts(bot: Bot):
    groups = db.groups_all()
    fact = FACTS[fact_index[0] % len(FACTS)]
    fact_index[0] += 1
    for group in groups:
        try:
            await bot.send_message(
                group["chat_id"],
                f"💼 <b>Интересный факт:</b>\n\n{fact}",
                parse_mode="HTML",
            )
        except Exception:
            pass

# ── Keep-alive HTTP server ────────────────────────────────────────────────────

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *args):
        pass

def start_keepalive():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), KeepAliveHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Keep-alive HTTP server started on port {port}")

def self_ping():
    if not RENDER_URL:
        return
    def ping_loop():
        while True:
            time.sleep(14 * 60)
            try:
                requests.get(f"{RENDER_URL}/ping", timeout=10)
            except Exception:
                pass
    thread = threading.Thread(target=ping_loop, daemon=True)
    thread.start()

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    start_keepalive()
    self_ping()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler(["settings", "настройки"], cmd_settings))
    app.add_handler(CommandHandler("lawsuit", cmd_lawsuit))
    app.add_handler(ChatMemberHandler(on_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

    app.add_handler(CallbackQueryHandler(cb_create_court, pattern=r"^create_court:(\d+)$"))
    app.add_handler(CallbackQueryHandler(cb_verdict, pattern=r"^verdict:(plaintiff|defendant|draw):(\d+)$"))
    app.add_handler(CallbackQueryHandler(cb_cleanup, pattern=r"^cleanup:(\d+)$"))

    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r"^[🛑⚖️📋]"),
        handle_keyboard_button,
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lawsuit_message))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        lambda: asyncio.ensure_future(send_facts(app.bot)),
        "cron", hour="*/2", minute=0,
    )
    scheduler.start()

    logger.info("CaseSolve bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
