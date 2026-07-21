import { Bot, InlineKeyboard } from "grammy";
import {
  qCourt,
  qGroup,
  qOwnerSession,
  qAdminSession,
  qWitness,
  now,
} from "../db/index.js";
import {
  mention,
  isLawsuitCommand,
  extractLawsuitTarget,
  isAdminOrOwner,
  getChatOwnerId,
  resolveUsername,
  parseParticipants,
  parseWitnesses,
  muteUser,
  unmuteUser,
} from "../utils/helpers.js";

// ── Lawsuit from regular participants ─────────────────────────────────────────

export async function handleUserLawsuit(ctx: any): Promise<void> {
  const chat = ctx.chat;
  const from = ctx.from;
  if (!from) return;
  const text: string = ctx.message?.text ?? "";

  let targetId: number | null = null;
  let targetFirstName = "";
  let targetUsername: string | null = null;

  if (ctx.message?.reply_to_message) {
    const replied = ctx.message.reply_to_message.from;
    if (!replied || replied.is_bot) {
      await ctx.reply("❕️ Нельзя подать в суд на бота.");
      return;
    }
    targetId = replied.id;
    targetFirstName = replied.first_name;
    targetUsername = replied.username ?? null;
  } else {
    const username = extractLawsuitTarget(text);
    if (!username) {
      await ctx.reply(
        "❔️ Укажите ответчика.\n\nПример:\n<code>! суд @username</code>\nили ответьте командой <code>! суд</code> на сообщение участника.",
        { parse_mode: "HTML" }
      );
      return;
    }
    const resolved = await resolveUsername(ctx.api, chat.id, username);
    if (!resolved) {
      await ctx.reply(`❕️ Не удалось найти @${username} в Telegram.`);
      return;
    }
    if (resolved.id === from.id) {
      await ctx.reply("❕️ Вы не можете подать в суд на самого себя.");
      return;
    }
    targetId = resolved.id;
    targetFirstName = resolved.firstName;
    targetUsername = resolved.username ?? null;
  }

  if (!targetId || targetId === from.id) {
    await ctx.reply("❕️ Вы не можете подать в суд на самого себя.");
    return;
  }

  const existing = qCourt.awaitingInOrigin(String(chat.id));
  if (existing) {
    await ctx.reply("❕️ В этом чате уже идёт создание суда. Ожидайте завершения.");
    return;
  }

  const ownerId = await getChatOwnerId(ctx.api, chat.id);
  if (!ownerId) {
    await ctx.reply("❕️ Не удалось определить владельца группы. Убедитесь, что бот является администратором.");
    return;
  }

  const groupRow = qGroup.get(String(chat.id));
  if (!groupRow?.owner_id) qGroup.setOwner(ownerId, String(chat.id));

  const court = qCourt.create({
    origin_chat_id: String(chat.id),
    court_chat_id: null,
    plaintiff_id: from.id,
    plaintiff_name: from.first_name,
    plaintiff_username: from.username ?? null,
    defendant_id: targetId,
    defendant_name: targetFirstName,
    defendant_username: targetUsername,
    judge_id: null,
    judge_name: null,
    owner_id: ownerId,
    status: "pending",
    current_speaker: null,
    announcement_msg_id: null,
    created_at: now(),
  });

  const keyboard = new InlineKeyboard().text("⚖️ Создать суд", `create_court:${court.id}`);

  const msg1 = await ctx.reply(
    `‼️\n${mention(from.first_name, from.id)} вызывает в суд ${mention(targetFirstName, targetId)}.\n‼️`,
    { parse_mode: "HTML", reply_markup: keyboard }
  );

  qCourt.update(court.id, { announcement_msg_id: msg1.message_id });

  // Notify owner 1 second later
  global.setTimeout(async () => {
    try {
      const ownerMember = await ctx.api.getChatMember(chat.id, ownerId);
      const ownerUser = ownerMember.user;
      await ctx.api.sendMessage(
        chat.id,
        `✔️\nВызван ${mention(ownerUser.first_name, ownerId)} (Владелец группы).\nОжидайте создания Суда.\n✔️`,
        { parse_mode: "HTML" }
      );
    } catch {
      await ctx.api.sendMessage(
        chat.id,
        "✔️\nВладелец группы уведомлён. Ожидайте создания Суда.\n✔️"
      );
    }
  }, 1000);
}

// ── Lawsuit from admin/owner ──────────────────────────────────────────────────

export async function handleAdminLawsuit(ctx: any): Promise<void> {
  const chat = ctx.chat;
  const from = ctx.from;
  if (!from) return;

  const existing = qCourt.awaitingInOrigin(String(chat.id));
  if (existing) {
    await ctx.reply("❕️ В этом чате уже идёт создание суда.");
    return;
  }

  await ctx.reply(
    `❔️\n<b>Кто участвует в этом суде?</b>\n\nВведите участников в следующем формате:\n` +
    `<code>Истец: @username; Ответчик: @username; Свидетель: @username; Судья: @username</code>\n\n` +
    `<i>Свидетелей можно до пяти. Судья и свидетели — необязательны. Минимум — Истец и Ответчик.</i>\n❕️`,
    { parse_mode: "HTML" }
  );

  qAdminSession.set(from.id, String(chat.id), "awaiting_participants", null, now());
}

// ── Register handlers ─────────────────────────────────────────────────────────

export function registerLawsuitHandlers(bot: Bot): void {
  bot.on("message:text", async (ctx) => {
    if (ctx.chat.type === "private") return;

    const text = ctx.message.text ?? "";
    const from = ctx.from;
    if (!from) return;

    // Admin awaiting participant input
    const adminSession = qAdminSession.get(from.id, String(ctx.chat.id));
    if (adminSession?.state === "awaiting_participants") {
      await handleAdminParticipantsInput(ctx, adminSession);
      return;
    }

    // Owner awaiting witnesses
    const ownerSession = qOwnerSession.get(from.id);
    if (ownerSession?.state === "awaiting_witnesses" && !isLawsuitCommand(text) && !text.startsWith("/lawsuit")) {
      await handleWitnessesInput(ctx, ownerSession);
      return;
    }

    if (!isLawsuitCommand(text) && !text.startsWith("/lawsuit")) return;

    const isAdmin = await isAdminOrOwner(ctx.api, ctx.chat.id, from.id);
    if (isAdmin) {
      await handleAdminLawsuit(ctx);
    } else {
      await handleUserLawsuit(ctx);
    }
  });

  bot.command("lawsuit", async (ctx) => {
    if (ctx.chat.type === "private") {
      await ctx.reply("⚖️ Команда /lawsuit используется только в группах.");
      return;
    }
    const from = ctx.from;
    if (!from) return;

    const isAdmin = await isAdminOrOwner(ctx.api, ctx.chat.id, from.id);
    if (isAdmin) {
      await handleAdminLawsuit(ctx);
    } else {
      await handleUserLawsuit(ctx);
    }
  });

  // Forwarded messages in DM for court group setup
  bot.on("message:forward_origin", async (ctx) => {
    if (ctx.chat.type !== "private") return;
    const from = ctx.from;
    if (!from) return;

    const ownerSession = qOwnerSession.get(from.id);
    if (!ownerSession) return;

    if (
      ownerSession.state === "awaiting_court_group_global" ||
      ownerSession.state === "awaiting_court_group"
    ) {
      await handleCourtGroupForward(ctx, ownerSession);
    }
  });
}

// ── Admin participant input ───────────────────────────────────────────────────

async function handleAdminParticipantsInput(ctx: any, session: any): Promise<void> {
  const text = ctx.message.text ?? "";
  const chat = ctx.chat;
  const from = ctx.from;
  if (!from) return;

  const parsed = parseParticipants(text);

  if (!parsed.plaintiff || !parsed.defendant) {
    await ctx.reply(
      "❕️ Необходимо указать минимум <b>Истца</b> и <b>Ответчика</b>.\n\nПример:\n<code>Истец: @username; Ответчик: @username</code>",
      { parse_mode: "HTML" }
    );
    return;
  }

  if (parsed.witnesses.length > 5) {
    await ctx.reply("❕️ Максимальное количество свидетелей — 5.");
    return;
  }

  const plaintiffUser = await resolveUsername(ctx.api, chat.id, parsed.plaintiff);
  const defendantUser = await resolveUsername(ctx.api, chat.id, parsed.defendant);

  if (!plaintiffUser) { await ctx.reply(`❕️ Не найден @${parsed.plaintiff}.`); return; }
  if (!defendantUser) { await ctx.reply(`❕️ Не найден @${parsed.defendant}.`); return; }

  let judgeId: number | null = null;
  let judgeName: string | null = null;
  if (parsed.judge) {
    const judgeUser = await resolveUsername(ctx.api, chat.id, parsed.judge);
    if (judgeUser) { judgeId = judgeUser.id; judgeName = judgeUser.firstName; }
  }

  const ownerId = await getChatOwnerId(ctx.api, chat.id);

  const court = qCourt.create({
    origin_chat_id: String(chat.id),
    court_chat_id: null,
    plaintiff_id: plaintiffUser.id,
    plaintiff_name: plaintiffUser.firstName,
    plaintiff_username: plaintiffUser.username ?? null,
    defendant_id: defendantUser.id,
    defendant_name: defendantUser.firstName,
    defendant_username: defendantUser.username ?? null,
    judge_id: judgeId,
    judge_name: judgeName,
    owner_id: ownerId,
    status: "awaiting_court",
    current_speaker: null,
    announcement_msg_id: null,
    created_at: now(),
  });

  for (const wUsername of parsed.witnesses) {
    const wUser = await resolveUsername(ctx.api, chat.id, wUsername);
    if (wUser) {
      qWitness.add({ court_id: court.id, user_id: wUser.id, user_name: wUser.firstName, username: wUser.username ?? null });
    }
  }

  qAdminSession.clear(from.id, String(chat.id));

  const groupRow = qGroup.get(String(chat.id));
  if (groupRow?.court_chat_id) {
    await startCourtInGroup(ctx, court.id, groupRow.court_chat_id);
  } else {
    qOwnerSession.set(
      from.id,
      "awaiting_court_group",
      JSON.stringify({ courtId: court.id, originChatId: String(chat.id) }),
      now()
    );
    await ctx.reply(
      "❔️ <b>В каком чате провести суд?</b>\n\nПерешлите любое сообщение из группы, где должен пройти суд.\n\nВажно: бот должен быть администратором в той группе.",
      { parse_mode: "HTML" }
    );
  }
}

// ── Owner witness input ───────────────────────────────────────────────────────

async function handleWitnessesInput(ctx: any, session: any): Promise<void> {
  const from = ctx.from;
  if (!from) return;
  const text = ctx.message.text ?? "";
  const data = session.data ? JSON.parse(session.data) : {};
  const courtId: number = data.courtId;
  if (!courtId) return;

  const court = qCourt.byId(courtId);
  if (!court) return;

  const usernames = parseWitnesses(text);
  if (usernames.length > 5) {
    await ctx.reply("❕️ Максимальное количество свидетелей — 5.");
    return;
  }

  for (const username of usernames) {
    const resolved = await resolveUsername(ctx.api, court.origin_chat_id, username);
    if (resolved) {
      qWitness.add({ court_id: courtId, user_id: resolved.id, user_name: resolved.firstName, username: resolved.username ?? null });
    }
  }

  qOwnerSession.clear(from.id);

  const groupRow = qGroup.get(court.origin_chat_id);
  if (groupRow?.court_chat_id) {
    await startCourtInGroup(ctx, courtId, groupRow.court_chat_id);
  } else {
    qOwnerSession.set(
      from.id,
      "awaiting_court_group",
      JSON.stringify({ courtId, originChatId: court.origin_chat_id }),
      now()
    );
    await ctx.reply(
      "❔️ <b>В каком чате провести суд?</b>\n\nПерешлите любое сообщение из группы, где должен пройти суд.\n\nВажно: бот должен быть администратором в этой группе.",
      { parse_mode: "HTML" }
    );
  }
}

// ── Court group forward ───────────────────────────────────────────────────────

async function handleCourtGroupForward(ctx: any, session: any): Promise<void> {
  const from = ctx.from;
  if (!from) return;

  let courtChatId: string | null = null;
  const fwd = ctx.message.forward_origin;
  if (fwd?.type === "channel") {
    courtChatId = String((fwd as any).chat.id);
  } else if ((ctx.message as any).forward_from_chat) {
    courtChatId = String((ctx.message as any).forward_from_chat.id);
  }

  if (!courtChatId) {
    await ctx.reply("❕️ Не удалось определить чат. Перешлите сообщение из группы.");
    return;
  }

  try {
    const botMember = await ctx.api.getChatMember(courtChatId, ctx.me.id);
    if (botMember.status !== "administrator" && botMember.status !== "creator") {
      await ctx.reply("❕️ Бот не является администратором в этом чате. Добавьте бота и повторите.");
      return;
    }
  } catch {
    await ctx.reply("❕️ Бот не состоит в этом чате или не имеет доступа к нему.");
    return;
  }

  const data = session.data ? JSON.parse(session.data) : {};

  if (session.state === "awaiting_court_group_global") {
    await ctx.reply(
      "✔️ Зал суда принят!\n\nТеперь перешлите сообщение из группы, <b>откуда</b> будут поступать иски.",
      { parse_mode: "HTML" }
    );
    qOwnerSession.set(from.id, "awaiting_origin_group", JSON.stringify({ courtChatId }), now());
    return;
  }

  if (session.state === "awaiting_court_group" && data.courtId) {
    const originChatId: string = data.originChatId;
    qGroup.setCourtChat(courtChatId, originChatId);
    qCourt.update(data.courtId, { court_chat_id: courtChatId, status: "awaiting_witnesses" });
    qOwnerSession.clear(from.id);
    await ctx.reply("✔️ Чат для суда сохранён!");
    await startCourtInGroup(ctx, data.courtId, courtChatId);
  }
}

// ── Start court in court group ────────────────────────────────────────────────

export async function startCourtInGroup(ctx: any, courtId: number, courtChatId: string): Promise<void> {
  const court = qCourt.byId(courtId);
  if (!court) return;

  const witnesses = qWitness.byCourt(courtId);

  let participantsText = `${mention(court.plaintiff_name, court.plaintiff_id)} — Истец\n`;
  participantsText += `${mention(court.defendant_name, court.defendant_id)} — Ответчик\n`;
  if (court.judge_id && court.judge_name) {
    participantsText += `${mention(court.judge_name, court.judge_id)} — Судья\n`;
  } else {
    participantsText += "<i>Судья не назначен</i>\n";
  }
  for (const w of witnesses) {
    participantsText += `${mention(w.user_name, w.user_id)} — Свидетель\n`;
  }

  qCourt.update(courtId, { status: "awaiting_witnesses", court_chat_id: courtChatId });

  await ctx.api.sendMessage(
    courtChatId,
    `⚖️ <b>Заседание суда. Дело №${courtId}</b>\n\n<b>Состав:</b>\n${participantsText}\n<i>Подготовка к началу заседания...</i>`,
    { parse_mode: "HTML" }
  );

  await muteUser(ctx.api, courtChatId, court.plaintiff_id);
  await muteUser(ctx.api, courtChatId, court.defendant_id);
  for (const w of witnesses) await muteUser(ctx.api, courtChatId, w.user_id);

  global.setTimeout(() => {
    void beginCourtSession(ctx.api, courtId, courtChatId);
  }, 3000);
}

async function beginCourtSession(api: any, courtId: number, courtChatId: string): Promise<void> {
  const court = qCourt.byId(courtId);
  if (!court) return;

  qCourt.update(courtId, { status: "in_session", current_speaker: "plaintiff" });
  await unmuteUser(api, courtChatId, court.plaintiff_id);

  await api.sendMessage(
    courtChatId,
    `⚖️ <b>Суд начат!</b>\n\n🎤 Слово предоставляется ${mention(court.plaintiff_name, court.plaintiff_id)} (<b>Истец</b>).\n\n<i>После вашего сообщения слово перейдёт к Ответчику.</i>`,
    { parse_mode: "HTML" }
  );

  if (court.judge_id && court.judge_name) {
    await api.sendMessage(
      courtChatId,
      `💼 ${mention(court.judge_name, court.judge_id)} — Вы Судья. У вас активна клавиатура управления заседанием.`,
      {
        parse_mode: "HTML",
        reply_markup: {
          keyboard: [[{ text: "🛑 Остановить" }, { text: "⚖️ Принять решение" }]],
          resize_keyboard: true,
        },
      }
    );
  }
}
