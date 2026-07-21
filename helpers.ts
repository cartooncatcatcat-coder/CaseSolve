import type { Api, RawApi } from "grammy";

/** Mention a user by first name with a tg://user?id= link */
export function mention(firstName: string, userId: number): string {
  return `<a href="tg://user?id=${userId}">${escapeHtml(firstName)}</a>`;
}

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export interface ParsedParticipants {
  plaintiff?: string;
  defendant?: string;
  witnesses: string[];
  judge?: string;
}

export function parseParticipants(text: string): ParsedParticipants {
  const result: ParsedParticipants = { witnesses: [] };
  const parts = text.split(";").map((p) => p.trim());
  for (const part of parts) {
    const lower = part.toLowerCase();
    const valueMatch = part.match(/@([\w]+)/);
    const value = valueMatch ? valueMatch[1] : undefined;
    if (!value) continue;
    if (lower.startsWith("истец")) result.plaintiff = value;
    else if (lower.startsWith("ответчик")) result.defendant = value;
    else if (lower.startsWith("свидетел")) result.witnesses.push(value);
    else if (lower.startsWith("судья")) result.judge = value;
  }
  return result;
}

export function parseWitnesses(text: string): string[] {
  const witnesses: string[] = [];
  const parts = text.split(";").map((p) => p.trim());
  for (const part of parts) {
    const match = part.match(/@([\w]+)/);
    if (match) witnesses.push(match[1]);
  }
  return witnesses;
}

export function isLawsuitCommand(text: string): boolean {
  return /^!\s*суд(\s|$)/iu.test(text.trim());
}

export function extractLawsuitTarget(text: string): string | null {
  const match = text.match(/!\s*суд\s+@([\w]+)/iu);
  return match ? match[1] : null;
}

/** Mute a user in a chat */
export async function muteUser(
  api: Api<RawApi>,
  chatId: string | number,
  userId: number
): Promise<void> {
  try {
    await api.restrictChatMember(chatId, userId, {
      can_send_messages: false,
      can_send_audios: false,
      can_send_documents: false,
      can_send_photos: false,
      can_send_videos: false,
      can_send_video_notes: false,
      can_send_voice_notes: false,
      can_send_polls: false,
      can_send_other_messages: false,
      can_add_web_page_previews: false,
    });
  } catch {
    // User may have left or bot lost rights — ignore
  }
}

/** Unmute a user in a chat */
export async function unmuteUser(
  api: Api<RawApi>,
  chatId: string | number,
  userId: number
): Promise<void> {
  try {
    await api.restrictChatMember(chatId, userId, {
      can_send_messages: true,
      can_send_audios: true,
      can_send_documents: true,
      can_send_photos: true,
      can_send_videos: true,
      can_send_video_notes: true,
      can_send_voice_notes: true,
      can_send_polls: true,
      can_send_other_messages: true,
      can_add_web_page_previews: true,
    });
  } catch {
    // Ignore
  }
}

/** Check if user is admin or owner */
export async function isAdminOrOwner(
  api: Api<RawApi>,
  chatId: string | number,
  userId: number
): Promise<boolean> {
  try {
    const member = await api.getChatMember(chatId, userId);
    return member.status === "administrator" || member.status === "creator";
  } catch {
    return false;
  }
}

/** Check if user is the owner (creator) */
export async function isOwner(
  api: Api<RawApi>,
  chatId: string | number,
  userId: number
): Promise<boolean> {
  try {
    const member = await api.getChatMember(chatId, userId);
    return member.status === "creator";
  } catch {
    return false;
  }
}

/** Get the chat owner user ID */
export async function getChatOwnerId(
  api: Api<RawApi>,
  chatId: string | number
): Promise<number | null> {
  try {
    const admins = await api.getChatAdministrators(chatId);
    const creator = admins.find((a) => a.status === "creator");
    return creator ? creator.user.id : null;
  } catch {
    return null;
  }
}

/** Resolve a username to user ID + first name within a chat */
export async function resolveUsername(
  api: Api<RawApi>,
  chatId: string | number,
  username: string
): Promise<{ id: number; firstName: string; username?: string } | null> {
  try {
    // getChatMember requires numeric user ID; we use getChat to resolve username
    const chat = await api.getChat("@" + username);
    if ("first_name" in chat) {
      return { id: chat.id, firstName: chat.first_name ?? "User", username: chat.username };
    }
    return null;
  } catch {
    return null;
  }
}

export function now(): number {
  return Math.floor(Date.now() / 1000);
}
