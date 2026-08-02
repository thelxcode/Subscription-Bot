import logging
import time
from pymongo import AsyncMongoClient, ASCENDING, errors
from config import Config

logger = logging.getLogger(__name__)

class PaymentDatabase:
    def __init__(self):
        self.db_url = Config.DB_URL
        self.client = None
        self.db = None
        self.users = None        # Stores user access levels
        self.payments = None     # Matches input UTRs with verified bank SMS UTRs

    async def connect(self):
        try:
            self.client = AsyncMongoClient(self.db_url, serverSelectionTimeoutMS=5000)
            await self.client.admin.command("ping")
            
            self.db = self.client["UPI_Automation_DB"]
            self.users = self.db["PremiumUsers"]
            self.payments = self.db["UtrLedger"]

            # Unique index on UTR ensures no single payment can ever be double-claimed
            await self.payments.create_index([("utr", ASCENDING)], unique=True)
            await self.users.create_index([("user_id", ASCENDING)], unique=True)
            
            logger.info("✅ MongoDB Connected successfully for UPI system.")
        except Exception as e:
            logger.error(f"❌ Database connection error: {e}")
            raise e

    async def register_user_utr(self, user_id: int, utr: str, expected_amount: float) -> str:
        """Executed when user submits their 12-digit UTR in chat."""
        try:
            # Check if this UTR was already recorded by an incoming bank SMS alert
            existing_sms = await self.payments.find_one({"utr": utr, "type": "sms_alert"})
            
            if existing_sms:
                if float(existing_sms["amount"]) == expected_amount:
                    # Instant match found! Bank SMS arrived before user input. Unlock premium.
                    await self.set_user_premium(user_id, duration_days=30)
                    await self.payments.update_one({"utr": utr}, {"$set": {"status": "claimed", "user_id": user_id}})
                    return "instant_success"
                return "amount_mismatch"

            # If bank SMS hasn't arrived yet, save user claim as pending
            await self.payments.insert_one({
                "utr": utr,
                "user_id": user_id,
                "amount": expected_amount,
                "type": "user_claim",
                "status": "pending",
                "timestamp": time.time()
            })
            return "pending"
        except errors.DuplicateKeyError:
            return "already_exists"

    async def process_bank_sms(self, utr: str, extracted_amount: float) -> int | None:
        """Executed automatically when the Android app hits the server Webhook."""
        try:
            # Check if a user is already waiting for this specific UTR validation
            waiting_claim = await self.payments.find_one({"utr": utr, "type": "user_claim", "status": "pending"})
            
            if waiting_claim:
                if float(waiting_claim["amount"]) == extracted_amount:
                    # Match found! User was waiting. Upgrade them.
                    user_id = waiting_claim["user_id"]
                    await self.set_user_premium(user_id, duration_days=30)
                    await self.payments.update_one({"utr": utr}, {"$set": {"status": "claimed", "type": "sms_alert"}})
                    return user_id # Returns ID to prompt bot notification
                else:
                    await self.payments.update_one({"utr": utr}, {"$set": {"status": "disputed_amount"}})
                    return None

            # If user hasn't claimed it yet, log the incoming SMS money chunk for later fast matching
            await self.payments.insert_one({
                "utr": utr,
                "amount": extracted_amount,
                "type": "sms_alert",
                "status": "unclaimed",
                "timestamp": time.time()
            })
            return None
        except errors.DuplicateKeyError:
            logger.warning(f"⚠️ Duplicate webhook data ignored for UTR: {utr}")
            return None

    async def set_user_premium(self, user_id: int, duration_days: int):
        expiry = time.time() + (duration_days * 86400)
        await self.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_premium": True, "expiry_time": expiry}},
            upsert=True
        )

    async def check_premium_status(self, user_id: int) -> bool:
        user = await self.users.find_one({"user_id": user_id})
        if not user or not user.get("is_premium"):
            return False
        if time.time() > user.get("expiry_time", 0):
            # Subscription expired naturally
            await self.users.update_one({"user_id": user_id}, {"$set": {"is_premium": False}})
            return False
        return True
