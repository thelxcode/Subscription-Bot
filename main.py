# main.py (Combining FastAPI Webhook + Kurigram Engine)
import asyncio
import uvicorn
import re
from fastapi import FastAPI, Request, Response
from pyrogram import Client
from config import Config
from database import PaymentDatabase

app = FastAPI()
db = PaymentDatabase()

# Initialize Kurigram client asynchronously
bot_client = Client(
    "payment_bot_session",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=dict(root="plugins") # Points to commands/payment handlers directory
)

@app.on_event("startup")
async def startup_services():
    await db.connect()
    await bot_client.start()
    print("🤖 Kurigram Engine and Database started successfully.")

@app.on_event("shutdown")
async def shutdown_services():
    await bot_client.stop()

@app.post("/bank-sms-webhook")
async def receive_sms_payload(request: Request):
    payload = await request.json()
    sms_text = payload.get("message", "") 
    
    # Simple Indian banking text structure filters
    amount_match = re.search(r"(?:Rs\.?|INR)\s*([\d,]+\.\d{2})", sms_text, re.IGNORECASE)
    utr_match = re.search(r"(\d{12})", sms_text)
    
    if amount_match and utr_match:
        amount = float(amount_match.group(1).replace(",", ""))
        utr = utr_match.group(1)
        
        # Execute cross match check inside MongoDB layer
        activated_user = await db.process_bank_sms(utr, amount)
        
        # 🔥 CRITICAL CONNECTION: If a user was waiting for this payment, send them a Telegram alert instantly!
        if activated_user:
            try:
                await bot_client.send_message(
                    chat_id=activated_user,
                    text="🎉 <b>Bank SMS Alert Received!</b>\n\n"
                         "Aapka pending transaction confirm ho gaya hai! Premium features instantly active kar diye gaye hain.",
                    parse_mode="html"
                )
            except Exception as e:
                print(f"Failed to alert user {activated_user} via bot network: {e}")
                
    return Response(status_code=200)

if __name__ == "__main__":
    # Runs the FastAPI server alongside Kurigram async loop tasks safely
    uvicorn.run(app, host="0.0.0.0", port=8080)
