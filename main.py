import re
import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from pyrogram import Client
from config import Config
from database import PaymentDatabase

# Configure detailed runtime application logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Core instances initialization
db = PaymentDatabase()

# Initialize Kurigram client asynchronously matching your project root structure
bot_client = Client(
    "payment_bot_session",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=dict(root="plugins")  # Hooks your commands & copy files instantly
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages explicit startup and shutdown lifecycles safely
    colocated within the exact same shared async thread task pool.
    """
    # ─── STARTUP ROUTINE ───
    try:
        logger.info("⏳ Connecting to MongoDB cluster instances...")
        await db.connect()
        
        logger.info("⏳ Initializing Kurigram MTProto client session engine...")
        await bot_client.start()
        
        logger.info("✅ Core application services running successfully.")
    except Exception as e:
        logger.critical(f"❌ Critical system startup pipeline failure: {e}")
        raise e
        
    yield  # Server serves endpoints continuously here
    
    # ─── SHUTDOWN ROUTINE ───
    logger.info("⏳ Initiating graceful drainage of network socket routines...")
    try:
        await bot_client.stop()
        logger.info("🔌 Kurigram MTProto network loop closed.")
    except Exception as e:
        logger.error(f"⚠️ Error closing bot connection pool: {e}")


# Initialize FastAPI app injecting modern lifespan hooks explicitly
app = FastAPI(lifespan=lifespan)


@app.post("/bank-sms-webhook")
async def receive_sms_payload(request: Request):
    """
    Intercepts and parses real-time text streams from your Android 
    SMS forwarder, extracting currency values and 12-digit UPI UTR blocks.
    """
    try:
        payload = await request.json()
        sms_text = payload.get("message", "")
        
        if not sms_text:
            logger.warning("⚠️ Received a webhook ping payload with empty text body.")
            return Response(status_code=200)

        logger.info(f"📩 Processing Incoming Bank Alert String: '{sms_text}'")

        # Regex models supporting standard Indian Bank (SBI, HDFC, ICICI, etc.) structural alerts
        amount_match = re.search(r"(?:Rs\.?|INR)\s*([\d,]+\.\d{2})", sms_text, re.IGNORECASE)
        utr_match = re.search(r"(\d{12})", sms_text)

        if amount_match and utr_match:
            # Parse decimal and clean thousands/lakh formatting strings cleanly
            amount = float(amount_match.group(1).replace(",", ""))
            utr = utr_match.group(1)
            
            logger.info(f"🔎 Extracted Verification Data -> UTR: {utr} | Amount: ₹{amount}")

            # Cross match against ledger documents natively in MongoDB
            activated_user = await db.process_bank_sms(utr, amount)

            # Core Connection: Instant verification callback alerts
            if activated_user:
                try:
                    await bot_client.send_message(
                        chat_id=activated_user,
                        text=(
                            "🎉 <b>Bank SMS Alert Received!</b>\n\n"
                            "Aapka pending transaction confirm ho gaya hai! Premium "
                            "features instantly active kar diye gaye hain."
                        ),
                        parse_mode=enums.ParseMode.HTML
                    )
                    logger.info(f"🚀 Success! Telegram notification pushed out to User ID: {activated_user}")
                except Exception as tg_err:
                    logger.error(f"❌ Failed to deliver instant activation update to chat context {activated_user}: {tg_err}")
            else:
                logger.info(f"💾 Transaction logged inside ledger dataset. Waiting for user allocation claims.")
        else:
            logger.warning("⚠️ Text formatting did not yield both valid money limits and a 12-digit numeric block.")

    except Exception as general_err:
        logger.error(f"❌ Error operating core incoming server webhook framework: {general_err}")
        
    # Return 200 HTTP code so your Android application doesn't cycle endless retry errors
    return Response(status_code=200)


if __name__ == "__main__":
    # Binding server across common public endpoints inside ASGI loop boundaries
    uvicorn.run(app, host="0.0.0.0", port=8080)
    
