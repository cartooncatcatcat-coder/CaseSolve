import { Bot } from "grammy";
import { qCourt, qWitness, qMsg } from "../db/index.js";
import { muteUser, unmuteUser, mention } from "../utils/helpers.js";

export function registerSessionHandlers(bot: Bot) {
  // Track messages and manage speaker turns during in_session
  bot.on("message", async (ctx) => {
    const chat = ctx.chat;
    if (chat.type === "private") return;

    const chatId = String(chat.id);
    const from = ctx.from;
    if (!from || from.is_bot) return;

    const court = qCourt.activeInChat(chatId);
    if (!court || court.status !== "in_session") return;

    // Track all messages for later cleanup
    qMsg.add(court.id, ctx.message.message_id, chatId);

    const fromId = from.id;

    // Judge and owner can always speak — no mute control
    if (court.judge_id && fromId === court.judge_id) return;
    if (court.owner_id && fromId === court.owner_id) return;

    const witnesses = qWitness.byCourt(court.id);
    const witnessIds = witnesses.map((w) => w.user_id);

    // Witnesses speak freely
    if (witnessIds.includes(fromId)) return;

    // Plaintiff's turn
    if (court.current_speaker === "plaintiff" && fromId === court.plaintiff_id) {
      await muteUser(ctx.api, chatId, court.plaintiff_id);
      await unmuteUser(ctx.api, chatId, court.defendant_id);
      qCourt.update(court.id, { current_speaker: "defendant" });

      await ctx.api.sendMessage(
        chatId,
        `🎤 Слово предоставляется ${mention(court.defendant_name, court.defendant_id)} (<b>Ответчик</b>).`,
        { parse_mode: "HTML" }
      );
      return;
    }

    // Defendant's turn
    if (court.current_speaker === "defendant" && fromId === court.defendant_id) {
      await muteUser(ctx.api, chatId, court.defendant_id);
      await unmuteUser(ctx.api, chatId, court.plaintiff_id);
      qCourt.update(court.id, { current_speaker: "plaintiff" });

      await ctx.api.sendMessage(
        chatId,
        `🎤 Слово снова предоставляется ${mention(court.plaintiff_name, court.plaintiff_id)} (<b>Истец</b>).`,
        { parse_mode: "HTML" }
      );
      return;
    }
  });

  // Detect when a witness leaves the court chat
  bot.on("message:left_chat_member", async (ctx) => {
    const chatId = String(ctx.chat.id);
    const leftUser = ctx.message.left_chat_member;
    if (!leftUser) return;

    const court = qCourt.activeInChat(chatId);
    if (!court) return;

    const witnesses = qWitness.byCourt(court.id);
    const witness = witnesses.find((w) => w.user_id === leftUser.id);

    if (witness && !witness.left_court) {
      qWitness.markLeft(court.id, leftUser.id);
      await ctx.api.sendMessage(
        chatId,
        `❕️ Свидетель ${mention(witness.user_name, witness.user_id)} покинул зал суда. Заседание продолжается.`,
        { parse_mode: "HTML" }
      );
    }
  });
}
