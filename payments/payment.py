# payment.py
import re
import logging
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import PaymentDatabase

logger = logging.getLogger(__name__)

# Initialize instance targeting the central system configuration definitions
db = PaymentDatabase()

# Price mapping metrics configuration variables
PREMIUM_AMOUNT = 1000.00
UPI_ID = "yourvpa@okaxis"  # Change this to your personal UPI ID
UPI_NAME = "Your Name"     # Change this to your Bank Account Name

@Client.on_message(filters.command("buy") & filters.private)
async def buy_premium_cmd(bot, message):
    """
    Generates the dynamic visual payment intent interface targeting user profile records.
    """
    try:
        user_id = message.from_user.id
        
        # Check active status matrix constraints
        is_premium = await db.check_premium_status(user_id)
        if is_premium:
            return await message.reply_text("✨ Aapka premium status pehle se active hai!")

        # Generate structural standard UPI string interface parameters
        upi_string = f"upi://pay?pa={UPI_ID}&pn={UPI_NAME.replace(' ', '%20')}&am={PREMIUM_AMOUNT}&tn=TG_{user_id}"
        
        # Pull instant scannable structural asset strings from global public rendering engine interfaces
        qr_api_url = f"https://qrserver.com{upi_string}"

        text = (
            "💳 <b>Premium Subscription (30 Days)</b>\n\n"
            f"💵 <b>Amount:</b> <code>₹{PREMIUM_AMOUNT}</code>\n\n"
            "👇 <b>Payment Karne Ke Tarike:</b>\n"
            "1. Niche diye gaye QR Code ko scan karein.\n"
            "2. Ya fir mobile me niche diye gaye button par click karein.\n\n"
            "⚠️ <b>Zaroori Notification:</b> Payment hone ke baad screen par aane wala "
            "<b>12-Digit UTR Number / UPI Ref No.</b> copy kar lein aur use yahan enter karein."
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Pay via GPay/PhonePe", url=upi_string)],
            [InlineKeyboardButton("⌨️ Enter UTR Number", callback_data="input_utr")]
        ])
        
        await message.reply_photo(
            photo=qr_api_url,
            caption=text,
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"❌ Error rendering payment display interface: {e}")
        await message.reply_text("⚠️ Payment interface initiate karne me dikkat aayi.")


@Client.on_callback_query(filters.regex("input_utr"))
async def prompt_utr_input(bot, callback_query):
    """
    Prompts user text layers to submit the core 12 digit token text blocks directly.
    """
    try:
        await callback_query.message.reply_text(
            "📝 Kripya apna <b>12-Digit UPI UTR / Transaction Reference Number</b> directly text me send karein:\n\n"
            "<i>Example: 312456789012</i>",
            parse_mode=enums.ParseMode.HTML
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"❌ Callback transition query failure: {e}")


@Client.on_message(filters.private & filters.text & ~filters.command(["start", "buy"]))
async def handle_utr_submission(bot, message):
    """
    Intercepts user-submitted text fields to capture and match structural 12 digit integer strings.
    """
    try:
        user_id = message.from_user.id
        input_text = message.text.strip()

        # Isolate evaluation layers to 12 digit blocks to prevent cross interference with general prompts
        if not re.fullmatch(r"\d{12}", input_text):
            return  # Allow normal structural text streams to pass safely without interception drops

        utr = input_text
        await message.reply_text("⏳ UTR verification process chal raha hai, kripya thoda intezar karein...")

        # Process record transaction claim configurations inside MongoDB
        result = await db.register_user_utr(user_id, utr, PREMIUM_AMOUNT)

        if result == "instant_success":
            await message.reply_text(
                "🎉 <b>Payment Verified Automatically!</b>\n\n"
                "✨ Aapka Premium Subscription 30 dinon ke liye successfully active kar diya gaya hai. "
                "Saari premium privileges unlock ho chuki hain!",
                parse_mode=enums.ParseMode.HTML
            )
        elif result == "pending":
            await message.reply_text(
                "⏳ <b>Bank Confirmation Pending:</b>\n\n"
                "Aapka UTR record ho gaya hai par aapke bank se automatic SMS credit alert aana baki hai. "
                "Jaise hi bank se notification aayega, aapka plan <b>2 second me auto-active</b> ho jayega. "
                "Aapko is chat me alert mil jayega.",
                parse_mode=enums.ParseMode.HTML
            )
        elif result == "amount_mismatch":
            await message.reply_text("❌ <b>Verification Failed:</b> Is UTR par aaya hua amount aapke selected plan amount se match nahi karta.")
        elif result == "already_exists":
            await message.reply_text("⚠️ Is UTR Number ko pehle hi claim kiya ja chuka hai.")
            
    except Exception as e:
        logger.error(f"❌ Core processing error inside payment pipeline interface handlers: {e}")
        await message.reply_text("⚠️ Processing me dikkat aayi. Kripya thoda samay baad dobara koshish karein.")


