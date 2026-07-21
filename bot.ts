import { Bot } from "grammy";
import { registerWelcomeHandlers } from "./handlers/welcome.js";
import { registerLawsuitHandlers } from "./handlers/lawsuit.js";
import { registerCallbackHandlers } from "./handlers/callbacks.js";
import { registerSessionHandlers } from "./handlers/session.js";
import { qOwnerSession, qGroup, qCourt, now } from "./db/index.js";
import { startCourtInGroup } from "./handlers/lawsuit.js";

const TOKEN = process.env.TOKEN_BOT;
if (!TOKEN) {
  throw new Error("TOKEN_BOT environment variable is not set. Set it in Render dashboard.");
}

export const bot = new Bot(TOKEN);

// ── Global error handler ──────────────────────────────────────────────────────
bot.catch((err) => {
  console.error(`[Bot Error] Update ${err.ctx.update.update_id}:`, err.error);
});

// ── Register handlers (order matters — more specific first) ───────────────────
registerWelcomeHandlers(bot);
registerLawsuitHandlers(bot);
registerCallbackHandlers(bot);
registerSessionHandlers(bot);

// ── Handle forwarded messages in DM for "awaiting_origin_group" state ─────────
bot.on("message:forward_origin", async (ctx) => {
  if (ctx.chat.type !== "private") return;
  const from = ctx.from!;

  const session = qOwnerSession.get(from.id);
  if (!session || session.state !== "awaiting_origin_group") return;

  const data = session.data ? JSON.parse(session.data) : {};

  let originChatId: string | null = null;
  const fwd = ctx.message.forward_origin;
  if (fwd?.type === "channel") {
    originChatId = String((fwd as any).chat.id);
  } else if ((ctx.message as any).forward_from_chat) {
    originChatId = String((ctx.message as any).forward_from_chat.id);
  }

  if (!originChatId) {
    return ctx.reply("❕️ Не удалось определить группу. Перешлите сообщение из нужного чата.");
  }

  qGroup.setCourtChat(data.courtChatId, originChatId);
  qOwnerSession.clear(from.id);

  await ctx.reply(
    `✔️ Готово! Зал суда привязан к группе.\n\nТеперь при создании суда в этой группе заседания будут проходить в указанном чате.`
  );
});

// ── Handle "нет" / "Нет" (skip witnesses) ─────────────────────────────────────
bot.hears(/^нет$/i, async (ctx) => {
  const from = ctx.from!;
  const session = qOwnerSession.get(from.id);
  if (!session || session.state !== "awaiting_witnesses") return;

  const data = session.data ? JSON.parse(session.data) : {};
  qOwnerSession.clear(from.id);

  const court = qCourt.byId(data.courtId);
  if (!court) return;

  const groupRow = qGroup.get(court.origin_chat_id);
  if (groupRow?.court_chat_id) {
    await startCourtInGroup(ctx, data.courtId, groupRow.court_chat_id);
  } else {
    qOwnerSession.set(
      from.id,
      "awaiting_court_group",
      JSON.stringify({ courtId: data.courtId, originChatId: court.origin_chat_id }),
      now()
    );
    await ctx.reply(
      "❔️ <b>В каком чате провести суд?</b>\n\nПерешлите любое сообщение из нужной группы.",
      { parse_mode: "HTML" }
    );
  }
});

export default bot;
