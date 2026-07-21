import { Bot } from "grammy";
import { qGroup, qOwnerSession, now } from "../db/index.js";
import { getChatOwnerId } from "../utils/helpers.js";

const COMMANDS_TEXT = `
<b>⚖️ Доступные команды:</b>

<b>Для участников:</b>
• <code>! суд @username</code> — подать иск против участника
• <code>! суд</code> (в ответ на сообщение) — подать иск против автора
• <code>/lawsuit @username</code> — альтернативная команда

<b>Для администраторов/владельца:</b>
• <code>! суд</code> или <code>/lawsuit</code> — создать суд вручную (выбор всех участников)

<b>В личных сообщениях (для владельца):</b>
• <code>/настройки</code> или <code>/settings</code> — настроить чат для проведения судов

<b>Справка:</b>
• <code>/help</code> — показать это сообщение
`.trim();

export function registerWelcomeHandlers(bot: Bot) {
  // Bot added to a group / bot's status changed
  bot.on("my_chat_member", async (ctx) => {
    const chat = ctx.chat;
    if (!chat || (chat.type !== "group" && chat.type !== "supergroup")) return;

    const newStatus = ctx.myChatMember.new_chat_member.status;
    if (newStatus !== "member" && newStatus !== "administrator") return;

    qGroup.upsert(String(chat.id), "title" in chat ? (chat.title ?? null) : null, null);

    const ownerId = await getChatOwnerId(ctx.api, chat.id);
    if (ownerId) qGroup.setOwner(ownerId, String(chat.id));

    await ctx.api.sendMessage(
      chat.id,
      `⚖️ <b>Приветствую! Я — CaseSolve.</b>\n\nПомогаю организовать справедливое разбирательство при конфликтах в группе.\n\n${COMMANDS_TEXT}`,
      { parse_mode: "HTML" }
    );
  });

  // Someone added the bot to a group
  bot.on("message:new_chat_members", async (ctx) => {
    const botId = ctx.me.id;
    const newMembers = ctx.message.new_chat_members;
    if (!newMembers.some((m) => m.id === botId)) return;

    const chat = ctx.chat;
    qGroup.upsert(String(chat.id), "title" in chat ? (chat.title ?? null) : null, null);

    const ownerId = await getChatOwnerId(ctx.api, chat.id);
    if (ownerId) qGroup.setOwner(ownerId, String(chat.id));
  });

  // /start in DM
  bot.command("start", async (ctx) => {
    if (ctx.chat.type !== "private") return;
    await ctx.reply(
      `⚖️ <b>Добро пожаловать в CaseSolve!</b>\n\nЯ — бот для организации судебных разбирательств в Telegram-группах.\n\nДобавьте меня в группу с правами администратора, и я помогу справедливо разрешить любой конфликт.\n\n${COMMANDS_TEXT}`,
      { parse_mode: "HTML" }
    );
  });

  // /help anywhere
  bot.command("help", async (ctx) => {
    await ctx.reply(COMMANDS_TEXT, { parse_mode: "HTML" });
  });

  // /settings or /настройки in DM
  bot.command(["settings", "настройки"], async (ctx) => {
    if (ctx.chat.type !== "private") {
      return ctx.reply("⚙️ Настройки доступны только в личных сообщениях с ботом.");
    }

    await ctx.reply(
      `⚙️ <b>Настройка зала суда</b>\n\nПерешлите любое сообщение из группы, которую хотите назначить <b>залом суда</b>.\n\nВажно: бот должен быть администратором в этой группе.\n\n<i>Ожидаю пересланное сообщение...</i>`,
      { parse_mode: "HTML" }
    );

    qOwnerSession.set(ctx.from!.id, "awaiting_court_group_global", null, now());
  });
}
