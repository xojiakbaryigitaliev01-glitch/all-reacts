import os
import random
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
        pass


def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info("Health server %s portida ishga tushdi", PORT)
    server.serve_forever()


def parse_bots(raw):
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
        await asyncio.sleep(random.uniform(1, 8))  # botlar bir vaqtda urmasin
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
    app = (
        ApplicationBuilder()
        .token(token)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .get_updates_connect_timeout(30)
        .get_updates_read_timeout(30)
        .build()
    )
    app.add_handler(
        MessageHandler(filters.UpdateType.CHANNEL_POST, make_reaction_handler(emoji))
    )
    await app.initialize()
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.start()
    await app.updater.start_polling(allowed_updates=["channel_post"])
    logger.info("@%s (%s) ishga tushdi", app.bot.username, emoji)
    return app


async def start_with_retry(token, emoji, attempts=3):
    for i in range(1, attempts + 1):
        try:
            return await start_bot(token, emoji)
        except Exception as e:
            logger.warning("%s-urinish: %s ishga tushmadi: %s", i, emoji, e)
            await asyncio.sleep(5 * i)
    logger.error("%s bot %s urinishdan keyin ham ishga tushmadi", emoji, attempts)
    return None


async def main_async(bots):
    started = []
    for token, emoji in bots:
        app = await start_with_retry(token, emoji)
        if app:
            started.append(app)
        await asyncio.sleep(2)  # botlarni ketma-ket ulash

    logger.info("%d/%d bot ishga tushdi", len(started), len(bots))
    await asyncio.Event().wait()


def main():
    threading.Thread(target=run_health_server, daemon=True).start()

    bots = parse_bots(BOTS_RAW)
    if not bots:
        raise SystemExit("BOTS o'zgaruvchisi bo'sh yoki noto'g'ri")

    logger.info("%d ta bot ishga tushmoqda", len(bots))
    asyncio.run(main_async(bots))


if __name__ == "__main__":
    main()
