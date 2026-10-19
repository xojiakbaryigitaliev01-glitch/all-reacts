import os
import asyncio
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, ReactionTypeEmoji
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("reaction-bots")

PORT = int(os.environ.get("PORT", 10000))
BOTS_RAW = os.environ.get("BOTS", "")


class HealthHandler(BaseHTTPRequestHandler):
    """cron-job.org va Render uchun 200 OK javob beradi."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # har bir so'rovni logga yozmaslik uchun


def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info("Health server %s portida ishga tushdi", PORT)
    server.serve_forever()


def parse_bots(raw):
    """'token1|❤️,token2|🔥' ko'rinishidagi matnni ro'yxatga aylantiradi."""
    bots = []
    for item in raw.split(","):
        item = item.strip()
        if "|" not in item:
            continue
        token, emoji = item.rsplit("|", 1)
        token, emoji = token.strip(), emoji.strip()
        if token and emoji:
            bots.append((token, emoji))
    return bots


def make_reaction_handler(emoji):
    async def react(update: Update, context: ContextTypes.DEFAULT_TYPE):
        post = update.channel_post
        if post is None:
            return
        try:
            await context.bot.set_message_reaction(
                chat_id=post.chat_id,
                message_id=post.message_id,
                reaction=[ReactionTypeEmoji(emoji)],
            )
            logger.info("Post %s ga %s qo'yildi", post.message_id, emoji)
        except Exception as e:
            logger.error("Xato (post %s, %s): %s", post.message_id, emoji, e)

    return react


async def start_bot(token, emoji):
    app = ApplicationBuilder().token(token).build()
    app.add_handler(
        MessageHandler(filters.UpdateType.CHANNEL_POST, make_reaction_handler(emoji))
    )
    await app.initialize()
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.start()
    await app.updater.start_polling(allowed_updates=["channel_post"])
    logger.info("@%s (%s) ishga tushdi", app.bot.username, emoji)
    return app


async def main_async(bots):
    started = []
    for token, emoji in bots:
        try:
            app = await start_bot(token, emoji)
            started.append(app)
        except Exception as e:
            # Bitta noto'g'ri token butun botlarni to'xtatmasin
            logger.error("Bot ishga tushmadi (%s): %s", emoji, e)

    logger.info("%d/%d bot ishga tushdi", len(started), len(bots))
    await asyncio.Event().wait()  # botlar doim ishlab turishi uchun


def main():
    threading.Thread(target=run_health_server, daemon=True).start()

    bots = parse_bots(BOTS_RAW)
    if not bots:
        raise SystemExit("BOTS o'zgaruvchisi bo'sh yoki noto'g'ri")

    logger.info("%d ta bot ishga tushmoqda", len(bots))
    asyncio.run(main_async(bots))


if __name__ == "__main__":
    main()
