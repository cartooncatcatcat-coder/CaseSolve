import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DB_PATH = process.env.DB_PATH ?? path.join(__dirname, "../../data/db.json");

// Ensure data directory exists
const dataDir = path.dirname(DB_PATH);
if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Court {
  id: number;
  origin_chat_id: string;
  court_chat_id: string | null;
  plaintiff_id: number;
  plaintiff_name: string;
  plaintiff_username: string | null;
  defendant_id: number;
  defendant_name: string;
  defendant_username: string | null;
  judge_id: number | null;
  judge_name: string | null;
  owner_id: number | null;
  status: string; // pending | awaiting_court | awaiting_witnesses | in_session | deliberation | concluded | stopped
  current_speaker: string | null; // 'plaintiff' | 'defendant'
  announcement_msg_id: number | null;
  created_at: number;
}

export interface Witness {
  id: number;
  court_id: number;
  user_id: number;
  user_name: string;
  username: string | null;
  left_court: boolean;
}

export interface GroupRow {
  chat_id: string;
  title: string | null;
  owner_id: number | null;
  court_chat_id: string | null;
}

export interface CourtMessage {
  id: number;
  court_id: number;
  message_id: number;
  chat_id: string;
}

export interface OwnerSession {
  owner_id: number;
  state: string;
  data: string | null;
  updated_at: number;
}

export interface AdminSession {
  user_id: number;
  chat_id: string;
  state: string;
  data: string | null;
  updated_at: number;
}

// ── In-memory store ───────────────────────────────────────────────────────────

interface Store {
  courts: Court[];
  witnesses: Witness[];
  groups: GroupRow[];
  courtMessages: CourtMessage[];
  ownerSessions: OwnerSession[];
  adminSessions: AdminSession[];
  _nextIds: { courts: number; witnesses: number; courtMessages: number };
}

function emptyStore(): Store {
  return {
    courts: [],
    witnesses: [],
    groups: [],
    courtMessages: [],
    ownerSessions: [],
    adminSessions: [],
    _nextIds: { courts: 1, witnesses: 1, courtMessages: 1 },
  };
}

let store: Store = emptyStore();

// Load existing data
if (fs.existsSync(DB_PATH)) {
  try {
    const raw = fs.readFileSync(DB_PATH, "utf-8");
    store = { ...emptyStore(), ...JSON.parse(raw) };
  } catch {
    store = emptyStore();
  }
}

function save() {
  fs.writeFileSync(DB_PATH, JSON.stringify(store, null, 2), "utf-8");
}

// Auto-save every 10 seconds to avoid data loss on crash
setInterval(save, 10_000).unref();

// ── Court helpers ─────────────────────────────────────────────────────────────

export const qCourt = {
  create(data: Omit<Court, "id">): Court {
    const court: Court = { id: store._nextIds.courts++, ...data };
    store.courts.push(court);
    save();
    return court;
  },

  byId(id: number): Court | undefined {
    return store.courts.find((c) => c.id === id);
  },

  update(id: number, patch: Partial<Court>) {
    const idx = store.courts.findIndex((c) => c.id === id);
    if (idx !== -1) {
      store.courts[idx] = { ...store.courts[idx], ...patch };
      save();
    }
  },

  activeInChat(chatId: string): Court | undefined {
    return store.courts.find(
      (c) => c.court_chat_id === chatId && !["concluded", "stopped"].includes(c.status)
    );
  },

  awaitingInOrigin(chatId: string): Court | undefined {
    return store.courts.find(
      (c) =>
        c.origin_chat_id === chatId &&
        ["pending", "awaiting_court", "awaiting_witnesses"].includes(c.status)
    );
  },
};

// ── Witness helpers ───────────────────────────────────────────────────────────

export const qWitness = {
  add(data: Omit<Witness, "id" | "left_court">): Witness {
    const w: Witness = { id: store._nextIds.witnesses++, left_court: false, ...data };
    store.witnesses.push(w);
    save();
    return w;
  },

  byCourt(courtId: number): Witness[] {
    return store.witnesses.filter((w) => w.court_id === courtId);
  },

  active(courtId: number): Witness[] {
    return store.witnesses.filter((w) => w.court_id === courtId && !w.left_court);
  },

  markLeft(courtId: number, userId: number) {
    const w = store.witnesses.find((w) => w.court_id === courtId && w.user_id === userId);
    if (w) { w.left_court = true; save(); }
  },
};

// ── Group helpers ─────────────────────────────────────────────────────────────

export const qGroup = {
  upsert(chatId: string, title: string | null, ownerId: number | null) {
    const existing = store.groups.find((g) => g.chat_id === chatId);
    if (existing) {
      existing.title = title;
    } else {
      store.groups.push({ chat_id: chatId, title, owner_id: ownerId, court_chat_id: null });
    }
    save();
  },

  setOwner(ownerId: number, chatId: string) {
    const g = store.groups.find((g) => g.chat_id === chatId);
    if (g) { g.owner_id = ownerId; save(); }
  },

  setCourtChat(courtChatId: string, chatId: string) {
    const g = store.groups.find((g) => g.chat_id === chatId);
    if (g) { g.court_chat_id = courtChatId; save(); }
    else { store.groups.push({ chat_id: chatId, title: null, owner_id: null, court_chat_id: courtChatId }); save(); }
  },

  get(chatId: string): GroupRow | undefined {
    return store.groups.find((g) => g.chat_id === chatId);
  },

  all(): GroupRow[] {
    return store.groups;
  },
};

// ── CourtMessage helpers ──────────────────────────────────────────────────────

export const qMsg = {
  add(courtId: number, messageId: number, chatId: string) {
    store.courtMessages.push({ id: store._nextIds.courtMessages++, court_id: courtId, message_id: messageId, chat_id: chatId });
    // Don't save on every message — auto-save handles it
  },

  byCourt(courtId: number): CourtMessage[] {
    return store.courtMessages.filter((m) => m.court_id === courtId);
  },
};

// ── Owner session helpers ─────────────────────────────────────────────────────

export const qOwnerSession = {
  set(ownerId: number, state: string, data: string | null, updatedAt: number) {
    const existing = store.ownerSessions.find((s) => s.owner_id === ownerId);
    if (existing) {
      existing.state = state;
      existing.data = data;
      existing.updated_at = updatedAt;
    } else {
      store.ownerSessions.push({ owner_id: ownerId, state, data, updated_at: updatedAt });
    }
    save();
  },

  get(ownerId: number): OwnerSession | undefined {
    return store.ownerSessions.find((s) => s.owner_id === ownerId);
  },

  clear(ownerId: number) {
    store.ownerSessions = store.ownerSessions.filter((s) => s.owner_id !== ownerId);
    save();
  },
};

// ── Admin session helpers ─────────────────────────────────────────────────────

export const qAdminSession = {
  set(userId: number, chatId: string, state: string, data: string | null, updatedAt: number) {
    const existing = store.adminSessions.find((s) => s.user_id === userId && s.chat_id === chatId);
    if (existing) {
      existing.state = state;
      existing.data = data;
      existing.updated_at = updatedAt;
    } else {
      store.adminSessions.push({ user_id: userId, chat_id: chatId, state, data, updated_at: updatedAt });
    }
    save();
  },

  get(userId: number, chatId: string): AdminSession | undefined {
    return store.adminSessions.find((s) => s.user_id === userId && s.chat_id === chatId);
  },

  clear(userId: number, chatId: string) {
    store.adminSessions = store.adminSessions.filter((s) => !(s.user_id === userId && s.chat_id === chatId));
    save();
  },
};

export function now(): number {
  return Math.floor(Date.now() / 1000);
}
