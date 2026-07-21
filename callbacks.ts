import { Bot, InlineKeyboard } from "grammy";
import { qCourt, qWitness, qOwnerSession, qMsg, now } from "../db/index.js";
import { mention, muteUser, unmuteUser, isOwner } from "../utils/helpers.js";

export function registerCallbackHandlers(bot: Bot): void {
  // Owner presses "Создать суд"
  bot.callbackQuery(/^create_court:(\d+)$/, async (ctx) => {
    const courtId = Number(ctx.match[1]);
    const from = ctx.from;

    const court = qCourt.byId(courtId);
    if (!court) {
      await ctx.answerCallbackQuery({ text: "❕️ Суд не найден.", show_alert: true });
      return;
    }
    if (court.status !== "pending") {
      await ctx.answerCallbackQuery({ text: "⚖️ Этот суд уже обрабатывается.", show_alert: true });
      return;
    }

    const ownerCheck = await isOwner(ctx.api, court.origin_chat_id, from.id);
    if (!ownerCheck) {
      await ctx.answerCallbackQuery({
        text: "❕️ Только владелец группы может создать суд.",
        show_alert: true,
      });
      return;
    }

    await ctx.answerCallbackQuery();
    qCourt.update(courtId, { status: "awaiting_court" });

    try {
      await ctx.editMessageReplyMarkup({ reply_markup: new InlineKeyboard() });
    } catch { /* ignore */ }

    await ctx.api.sendMessage(
      court.origin_chat_id,
      `✔️ ${mention(from.first_name, from.id)} открывает судебное заседание.\n\n` +
      `<i>Укажите свидетелей (до 5 человек) или напишите «нет», если свидетелей нет.</i>\n\n` +
      `Формат: <code>Свидетель: @username; Свидетель: @username</code>`,
      { parse_mode: "HTML" }
    );

    qOwnerSession.set(
      from.id,
      "awaiting_witnesses",
      JSON.stringify({ courtId, originChatId: court.origin_chat_id }),
      now()
    );
  });

  // Judge: "Принять решение"
  bot.hears("⚖️ Принять решение", async (ctx) => {
    if (ctx.chat.type === "private") return;
    const from = ctx.from;
    if (!from) return;
    const chatId = String(ctx.chat.id);

    const court = qCourt.activeInChat(chatId);
    if (!court || court.judge_id !== from.id || court.status !== "in_session") return;

    const witnesses = qWitness.byCourt(court.id);
    const allUsers = [court.plaintiff_id, court.defendant_id, ...witnesses.map((w) => w.user_id)];
    for (const uid of allUsers) await muteUser(ctx.api, chatId, uid);

    qCourt.update(court.id, { status: "deliberation" });

    await ctx.reply(
      `🔒 <b>Суд удаляется в совещательную комнату.</b>\n\nВсе участники временно лишены слова. Ожидайте решения судьи.`,
      { parse_mode: "HTML", reply_markup: { remove_keyboard: true } }
    );

    if (court.judge_name && court.judge_id) {
      await ctx.api.sendMessage(
        chatId,
        `💼 ${mention(court.judge_name, court.judge_id)} — когда будете готовы огласить решение, нажмите кнопку ниже.`,
        {
          parse_mode: "HTML",
          reply_markup: {
            keyboard: [[{ text: "📋 Огласить решение" }]],
            resize_keyboard: true,
          },
        }
      );
    }
  });

  // Judge: "Огласить решение"
  bot.hears("📋 Огласить решение", async (ctx) => {
    if (ctx.chat.type === "private") return;
    const from = ctx.from;
    if (!from) return;
    const chatId = String(ctx.chat.id);

    const court = qCourt.activeInChat(chatId);
    if (!court || court.judge_id !== from.id || court.status !== "deliberation") return;

    await ctx.reply("⚖️ Судья выносит решение. Выберите вердикт:", {
      reply_markup: {
        keyboard: [
          [{ text: "⚖️ Виновен Истец" }, { text: "⚖️ Виновен Ответчик" }],
          [{ text: "🤝 Ничья" }],
        ],
        resize_keyboard: true,
      },
    });
  });

  // Judge verdict: Guilty
  bot.hears(/^⚖️ Виновен (Истец|Ответчик)$/, async (ctx) => {
    if (ctx.chat.type === "private") return;
    const from = ctx.from;
    if (!from) return;
    const chatId = String(ctx.chat.id);

    const court = qCourt.activeInChat(chatId);
    if (!court || court.judge_id !== from.id || court.status !== "deliberation") return;

    const m = ctx.match as RegExpMatchArray;
    const isPlaintiffGuilty = m[1] === "Истец";
    const guiltyId = isPlaintiffGuilty ? court.plaintiff_id : court.defendant_id;
    const guiltyName = isPlaintiffGuilty ? court.plaintiff_name : court.defendant_name;
    const innocentId = isPlaintiffGuilty ? court.defendant_id : court.plaintiff_id;
    const innocentName = isPlaintiffGuilty ? court.defendant_name : court.plaintiff_name;

    qCourt.update(court.id, { status: "concluded" });

    const keyboard = new InlineKeyboard().text(
      "🗑 Удалить историю и участников",
      `cleanup_court:${court.id}`
    );

    await ctx.reply(
      `⚖️ <b>Решение суда — Дело №${court.id}</b>\n\n` +
      `Судья ${mention(court.judge_name ?? "Судья", court.judge_id ?? 0)} выносит вердикт:\n\n` +
      `🔴 <b>Виновен:</b> ${mention(guiltyName, guiltyId)}\n` +
      `✅ <b>Оправдан:</b> ${mention(innocentName, innocentId)}\n\n` +
      `<i>Наказание определяет судья в соответствии с правилами группы.</i>`,
      { parse_mode: "HTML", reply_markup: keyboard }
    );

    await ctx.api.sendMessage(chatId, "⚖️ Заседание завершено.", {
      reply_markup: { remove_keyboard: true },
    });
  });

  // Judge verdict: Draw
  bot.hears("🤝 Ничья", async (ctx) => {
    if (ctx.chat.type === "private") return;
    const from = ctx.from;
    if (!from) return;
    const chatId = String(ctx.chat.id);

    const court = qCourt.activeInChat(chatId);
    if (!court || court.judge_id !== from.id || court.status !== "deliberation") return;

    qCourt.update(court.id, { status: "concluded" });

    const keyboard = new InlineKeyboard().text(
      "🗑 Удалить историю и участников",
      `cleanup_court:${court.id}`
    );

    await ctx.reply(
      `⚖️ <b>Решение суда — Дело №${court.id}</b>\n\n` +
      `Судья ${mention(court.judge_name ?? "Судья", court.judge_id ?? 0)} выносит вердикт:\n\n` +
      `🤝 <b>Ничья.</b> Стороны признаны равно правыми.\n\n` +
      `<i>Конфликт урегулирован мирным путём.</i>`,
      { parse_mode: "HTML", reply_markup: keyboard }
    );

    await ctx.api.sendMessage(chatId, "⚖️ Заседание завершено.", {
      reply_markup: { remove_keyboard: true },
    });
  });

  // Judge: "Остановить"
  bot.hears("🛑 Остановить", async (ctx) => {
    if (ctx.chat.type === "private") return;
    const from = ctx.from;
    if (!from) return;
    const chatId = String(ctx.chat.id);

    const court = qCourt.activeInChat(chatId);
    if (!court || court.judge_id !== from.id) return;

    qCourt.update(court.id, { status: "stopped" });

    const witnesses = qWitness.byCourt(court.id);
    const allUsers = [court.plaintiff_id, court.defendant_id, ...witnesses.map((w) => w.user_id)];
    for (const uid of allUsers) await unmuteUser(ctx.api, chatId, uid);

    await ctx.reply(
      `🛑 <b>Заседание суда прекращено</b> по решению судьи.\n\nДело №${court.id} закрыто без вынесения вердикта.`,
      { parse_mode: "HTML", reply_markup: { remove_keyboard: true } }
    );
  });

  // Cleanup court (kick + delete messages)
  bot.callbackQuery(/^cleanup_court:(\d+)$/, async (ctx) => {
    const courtId = Number(ctx.match[1]);
    const from = ctx.from;

    const court = qCourt.byId(courtId);
    if (!court?.court_chat_id) {
      await ctx.answerCallbackQuery({ text: "❕️ Суд не найден.", show_alert: true });
      return;
    }

    const ownerCheck = await isOwner(ctx.api, court.origin_chat_id, from.id);
    const isJudge = court.judge_id === from.id;
    if (!ownerCheck && !isJudge) {
      await ctx.answerCallbackQuery({
        text: "❕️ Только владелец или судья могут очистить зал суда.",
        show_alert: true,
      });
      return;
    }

    await ctx.answerCallbackQuery();
    const chatId = court.court_chat_id;

    try {
      await ctx.editMessageReplyMarkup({ reply_markup: new InlineKeyboard() });
    } catch { /* ignore */ }

    await ctx.api.sendMessage(chatId, "🗑 <b>Завершение заседания. Зал суда очищается...</b>", {
      parse_mode: "HTML",
    });

    const witnesses = qWitness.byCourt(courtId);
    const toKick = [
      court.plaintiff_id,
      court.defendant_id,
      ...(court.judge_id ? [court.judge_id] : []),
      ...witnesses.map((w) => w.user_id),
    ];

    for (const uid of toKick) {
      if (uid === court.owner_id) continue;
      try {
        await ctx.api.banChatMember(chatId, uid);
        await ctx.api.unbanChatMember(chatId, uid);
      } catch { /* ignore */ }
    }

    const messages = qMsg.byCourt(courtId);
    for (const m of messages) {
      try {
        await ctx.api.deleteMessage(m.chat_id, m.message_id);
      } catch { /* ignore */ }
    }

    await ctx.api.sendMessage(
      chatId,
      `✔️ <b>Суд завершён.</b>\n\nДело №${courtId} закрыто. Участники удалены из зала суда.`,
      { parse_mode: "HTML" }
    );
  });
}
