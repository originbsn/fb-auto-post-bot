"""
FB Auto Post Bot - Telegram Bot Main Entry Point
รับ link / ข้อความ / รูปภาพ แล้วสร้างบทความและโพสต์ Facebook อัตโนมัติ
"""

import os
import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

from content_pipeline import ContentPipeline
from image_handler import ImageHandler
from facebook_poster import FacebookPoster

# Load environment
load_dotenv()

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_CONTENT = 0
WAITING_FOR_IMAGE = 1
REVIEWING_ARTICLE = 2

# Session storage (in-memory per user)
user_sessions: dict = {}


def get_session(user_id: int) -> dict:
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "source_text": None,
            "source_url": None,
            "user_image_path": None,
            "article": None,
            "image_path": None,
            "status": "idle",
        }
    return user_sessions[user_id]


def reset_session(user_id: int):
    user_sessions[user_id] = {
        "source_text": None,
        "source_url": None,
        "user_image_path": None,
        "article": None,
        "image_path": None,
        "status": "idle",
    }


# ─── Command Handlers ────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """คำสั่ง /start แนะนำการใช้งาน"""
    text = (
        "🤖 *FB Auto Post Bot*\n\n"
        "ส่งข้อมูลมาให้ฉัน แล้วฉันจะสร้างบทความและโพสต์ Facebook ให้คุณอัตโนมัติ!\n\n"
        "📌 *วิธีใช้งาน:*\n"
        "1️⃣ ส่ง *Link* บทความหรือเว็บไซต์\n"
        "2️⃣ ส่ง *ข้อความ/ข้อมูล* ที่ต้องการเขียนบทความ\n"
        "3️⃣ ส่ง *รูปภาพ* พร้อม caption (ถ้ามี)\n"
        "4️⃣ หรือส่งทั้ง link + รูปภาพพร้อมกัน\n\n"
        "📋 *คำสั่ง:*\n"
        "/start - แสดงเมนูนี้\n"
        "/new - เริ่มสร้างโพสต์ใหม่\n"
        "/cancel - ยกเลิกการทำงานปัจจุบัน\n"
        "/status - ดูสถานะการทำงาน\n\n"
        "💡 *เริ่มเลย!* ส่ง link หรือข้อความมาได้เลยครับ"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
    return WAITING_FOR_CONTENT


async def new_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """คำสั่ง /new เริ่มโพสต์ใหม่"""
    user_id = update.effective_user.id
    reset_session(user_id)
    await update.message.reply_text(
        "✨ *เริ่มสร้างโพสต์ใหม่!*\n\n"
        "ส่ง link, ข้อความ, หรือรูปภาพมาได้เลยครับ\n"
        "(สามารถส่งหลายอย่างพร้อมกันได้)\n\n"
        "พิมพ์ /done เมื่อส่งข้อมูลครบแล้ว",
        parse_mode="Markdown",
    )
    return WAITING_FOR_CONTENT


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """คำสั่ง /cancel ยกเลิก"""
    user_id = update.effective_user.id
    reset_session(user_id)
    await update.message.reply_text(
        "❌ ยกเลิกแล้วครับ\n\nส่งข้อมูลใหม่ได้เลย หรือพิมพ์ /new เพื่อเริ่มใหม่"
    )
    return WAITING_FOR_CONTENT


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """คำสั่ง /status ดูสถานะ"""
    user_id = update.effective_user.id
    session = get_session(user_id)
    status_text = session.get("status", "idle")
    status_map = {
        "idle": "💤 ว่าง - รอรับข้อมูล",
        "processing": "⚙️ กำลังประมวลผล...",
        "reviewing": "👀 รอการยืนยัน",
        "posting": "📤 กำลังโพสต์ Facebook...",
        "done": "✅ โพสต์สำเร็จ",
        "error": "❌ เกิดข้อผิดพลาด",
    }
    await update.message.reply_text(
        f"📊 *สถานะปัจจุบัน:* {status_map.get(status_text, status_text)}",
        parse_mode="Markdown",
    )


# ─── Message Handlers ────────────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """รับข้อความ/link จากผู้ใช้"""
    user_id = update.effective_user.id
    session = get_session(user_id)
    text = update.message.text.strip()

    # ตรวจสอบว่าเป็น URL หรือข้อความ
    if text.startswith("http://") or text.startswith("https://"):
        session["source_url"] = text
        await update.message.reply_text(
            f"🔗 รับ Link แล้ว!\n`{text[:80]}{'...' if len(text) > 80 else ''}`\n\n"
            "📷 ส่งรูปภาพเพิ่มเติมได้ (ถ้ามี) หรือพิมพ์ /done เพื่อเริ่มสร้างบทความ",
            parse_mode="Markdown",
        )
    else:
        # เป็นข้อความ/ข้อมูล
        if session["source_text"]:
            session["source_text"] += "\n\n" + text
        else:
            session["source_text"] = text
        await update.message.reply_text(
            "📝 รับข้อความแล้ว!\n\n"
            "📷 ส่งรูปภาพเพิ่มเติมได้ (ถ้ามี) หรือพิมพ์ /done เพื่อเริ่มสร้างบทความ"
        )
    return WAITING_FOR_CONTENT


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """รับรูปภาพจากผู้ใช้"""
    user_id = update.effective_user.id
    session = get_session(user_id)

    # ดาวน์โหลดรูปภาพ
    photo = update.message.photo[-1]  # ขนาดใหญ่สุด
    file = await context.bot.get_file(photo.file_id)

    # สร้าง directory สำหรับเก็บรูป
    img_dir = Path(f"temp_images/{user_id}")
    img_dir.mkdir(parents=True, exist_ok=True)
    img_path = str(img_dir / f"user_image_{photo.file_id}.jpg")

    await file.download_to_drive(img_path)
    session["user_image_path"] = img_path

    # รับ caption ถ้ามี
    caption = update.message.caption
    if caption:
        if session["source_text"]:
            session["source_text"] += "\n\n" + caption
        else:
            session["source_text"] = caption

    await update.message.reply_text(
        "🖼️ รับรูปภาพแล้ว!\n\n"
        "ส่ง link หรือข้อความเพิ่มเติมได้ หรือพิมพ์ /done เพื่อเริ่มสร้างบทความ"
    )
    return WAITING_FOR_CONTENT


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """รับไฟล์รูปภาพ (document) จากผู้ใช้"""
    user_id = update.effective_user.id
    session = get_session(user_id)
    doc = update.message.document

    if doc.mime_type and doc.mime_type.startswith("image/"):
        file = await context.bot.get_file(doc.file_id)
        img_dir = Path(f"temp_images/{user_id}")
        img_dir.mkdir(parents=True, exist_ok=True)
        ext = doc.file_name.split(".")[-1] if doc.file_name else "jpg"
        img_path = str(img_dir / f"user_image_{doc.file_id}.{ext}")
        await file.download_to_drive(img_path)
        session["user_image_path"] = img_path

        await update.message.reply_text(
            "🖼️ รับไฟล์รูปภาพแล้ว!\n\n"
            "ส่ง link หรือข้อความเพิ่มเติมได้ หรือพิมพ์ /done เพื่อเริ่มสร้างบทความ"
        )
    else:
        await update.message.reply_text("⚠️ รองรับเฉพาะไฟล์รูปภาพครับ")
    return WAITING_FOR_CONTENT


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """คำสั่ง /done เริ่มประมวลผล"""
    user_id = update.effective_user.id
    session = get_session(user_id)

    if not session["source_url"] and not session["source_text"] and not session["user_image_path"]:
        await update.message.reply_text(
            "⚠️ ยังไม่ได้ส่งข้อมูลมาเลยครับ!\n\n"
            "กรุณาส่ง link, ข้อความ, หรือรูปภาพก่อน"
        )
        return WAITING_FOR_CONTENT

    session["status"] = "processing"
    processing_msg = await update.message.reply_text(
        "⚙️ *กำลังประมวลผล...*\n\n"
        "🔍 อ่านเนื้อหา...\n"
        "✍️ สร้างบทความ...\n"
        "🖼️ จัดการรูปภาพ...\n\n"
        "รอสักครู่นะครับ (ประมาณ 30-60 วินาที)",
        parse_mode="Markdown",
    )

    try:
        pipeline = ContentPipeline()
        image_handler = ImageHandler()

        # Step 1: สร้างบทความ
        await processing_msg.edit_text(
            "⚙️ *กำลังประมวลผล...*\n\n"
            "✅ รับข้อมูลแล้ว\n"
            "🔍 กำลังอ่านเนื้อหา...",
            parse_mode="Markdown",
        )

        article_data = await pipeline.generate_article(
            url=session["source_url"],
            text=session["source_text"],
        )

        session["article"] = article_data

        # Step 2: จัดการรูปภาพ
        await processing_msg.edit_text(
            "⚙️ *กำลังประมวลผล...*\n\n"
            "✅ สร้างบทความแล้ว\n"
            "🖼️ กำลังจัดการรูปภาพ...",
            parse_mode="Markdown",
        )

        image_path = await image_handler.get_image(
            url=session["source_url"],
            article_content=article_data["long_post"],
            article_title=article_data["title"],
            user_image_path=session["user_image_path"],
            scraped_images=article_data.get("images", []),
        )
        session["image_path"] = image_path

        session["status"] = "reviewing"

        # Step 3: แสดงตัวอย่างให้ review
        await processing_msg.delete()
        await send_preview(update, context, user_id, session, article_data, image_path)

    except Exception as e:
        logger.error(f"Error processing for user {user_id}: {e}", exc_info=True)
        session["status"] = "error"
        await processing_msg.edit_text(
            f"❌ *เกิดข้อผิดพลาด:*\n`{str(e)[:200]}`\n\n"
            "กรุณาลองใหม่อีกครั้ง หรือพิมพ์ /new เพื่อเริ่มใหม่",
            parse_mode="Markdown",
        )

    return REVIEWING_ARTICLE


async def send_preview(update, context, user_id, session, article_data, image_path):
    """ส่งตัวอย่างบทความให้ผู้ใช้ review"""
    title = article_data.get("title", "ไม่มีชื่อ")
    short_post = article_data.get("short_post", "")
    long_post = article_data.get("long_post", "")

    preview_text = (
        f"✅ *สร้างบทความสำเร็จ!*\n\n"
        f"📌 *หัวข้อ:* {title}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 *Short Post (โพสต์สั้น):*\n"
        f"{short_post[:300]}{'...' if len(short_post) > 300 else ''}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📰 *Long Post (บทความเต็ม):*\n"
        f"{long_post[:400]}{'...' if len(long_post) > 400 else ''}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🖼️ รูปภาพ: {'✅ พร้อมแล้ว' if image_path else '❌ ไม่มีรูป'}"
    )

    keyboard = [
        [
            InlineKeyboardButton("📤 โพสต์ Short Post", callback_data="post_short"),
            InlineKeyboardButton("📰 โพสต์ Long Post", callback_data="post_long"),
        ],
        [
            InlineKeyboardButton("📤 โพสต์ทั้งคู่", callback_data="post_both"),
        ],
        [
            InlineKeyboardButton("🔄 สร้างใหม่", callback_data="regenerate"),
            InlineKeyboardButton("❌ ยกเลิก", callback_data="cancel_post"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # ส่งรูปภาพ (ถ้ามี)
    if image_path and Path(image_path).exists():
        with open(image_path, "rb") as img_file:
            await update.message.reply_photo(
                photo=img_file,
                caption=preview_text[:1024],
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )
    else:
        await update.message.reply_text(
            preview_text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )


# ─── Callback Query Handler ───────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """จัดการปุ่มกด"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    session = get_session(user_id)
    data = query.data

    if data == "cancel_post":
        reset_session(user_id)
        await query.edit_message_caption(
            caption="❌ ยกเลิกแล้วครับ\n\nพิมพ์ /new เพื่อเริ่มใหม่"
        ) if query.message.photo else await query.edit_message_text(
            "❌ ยกเลิกแล้วครับ\n\nพิมพ์ /new เพื่อเริ่มใหม่"
        )
        return WAITING_FOR_CONTENT

    elif data == "regenerate":
        await query.edit_message_caption(
            caption="🔄 กำลังสร้างบทความใหม่..."
        ) if query.message.photo else await query.edit_message_text(
            "🔄 กำลังสร้างบทความใหม่..."
        )
        # Reset article แต่เก็บ source ไว้
        session["article"] = None
        session["image_path"] = None
        await done(update, context)
        return REVIEWING_ARTICLE

    elif data in ("post_short", "post_long", "post_both"):
        session["status"] = "posting"
        article = session.get("article", {})
        image_path = session.get("image_path")

        poster = FacebookPoster()
        results = []

        try:
            if data in ("post_short", "post_both"):
                short_result = await poster.post(
                    message=article.get("short_post", ""),
                    image_path=image_path,
                )
                results.append(f"📱 Short Post: ✅ โพสต์แล้ว\n🔗 {short_result.get('post_url', '')}")

            if data in ("post_long", "post_both"):
                long_result = await poster.post(
                    message=article.get("long_post", ""),
                    image_path=image_path if data == "post_long" else None,
                )
                results.append(f"📰 Long Post: ✅ โพสต์แล้ว\n🔗 {long_result.get('post_url', '')}")

            session["status"] = "done"
            result_text = "\n\n".join(results)

            edit_fn = query.edit_message_caption if query.message.photo else query.edit_message_text
            await edit_fn(
                f"🎉 *โพสต์สำเร็จ!*\n\n{result_text}\n\n"
                "พิมพ์ /new เพื่อสร้างโพสต์ใหม่",
                parse_mode="Markdown",
            )

        except Exception as e:
            logger.error(f"Facebook post error: {e}", exc_info=True)
            session["status"] = "error"
            edit_fn = query.edit_message_caption if query.message.photo else query.edit_message_text
            await edit_fn(
                f"❌ *โพสต์ไม่สำเร็จ:*\n`{str(e)[:300]}`\n\n"
                "กรุณาตรวจสอบ Facebook Token และลองใหม่",
                parse_mode="Markdown",
            )

        reset_session(user_id)
        return WAITING_FOR_CONTENT


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env")

    app = Application.builder().token(token).build()

    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("new", new_post),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
            MessageHandler(filters.PHOTO, handle_photo),
            MessageHandler(filters.Document.IMAGE, handle_document),
        ],
        states={
            WAITING_FOR_CONTENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
                MessageHandler(filters.PHOTO, handle_photo),
                MessageHandler(filters.Document.IMAGE, handle_document),
                CommandHandler("done", done),
            ],
            REVIEWING_ARTICLE: [
                CallbackQueryHandler(handle_callback),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
            CommandHandler("new", new_post),
        ],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("🤖 FB Auto Post Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
