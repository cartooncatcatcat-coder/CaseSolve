import cron from "node-cron";
import { FACTS } from "../data/facts.js";
import { qGroup } from "../db/index.js";

let factIndex = Math.floor(Math.random() * FACTS.length);

function getNextFact(): string {
  const fact = FACTS[factIndex % FACTS.length];
  factIndex++;
  return fact;
}

export function startFactsScheduler(bot: any) {
  // Every 2 hours at minute 0
  cron.schedule("0 */2 * * *", async () => {
    const groups = qGroup.all().filter((g) => g.chat_id);
    const fact = getNextFact();

    for (const group of groups) {
      try {
        await bot.api.sendMessage(
          group.chat_id,
          `💼 <b>Интересный факт:</b>\n\n${fact}`,
          { parse_mode: "HTML" }
        );
      } catch {
        // Bot may have been removed from the group — skip silently
      }
    }
  });

  console.log("⏰ Facts scheduler started (every 2 hours)");
}
