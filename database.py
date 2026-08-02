# database.py
import logging
import time
from pymongo.asynchronous.client import AsyncMongoClient
from pymongo import ASCENDING, errors
from config import Config

logger = logging.getLogger(__name__)

class PaymentDatabase:
    def __init__(self):
        self.db_url = Config.DB_URL
        self.client = None
        self.db = None
        self.users = None        # Stores premium user subscriptions
        self.payments = None     # Holds user claims and bank SMS ledger documents

    async def connect(self):
        """Initializes native PyMongo async connection pool and establishes indices."""
        try:
            self.client = AsyncMongoClient(
                self.db_url,
                serverSelectionTimeoutMS=5000,
                maxPoolSize=30,
                minPoolSize=5,
                connectTimeoutMS=4000
            )
            # Handshake verification check using the new awaitable command execution
            await self.client.admin.command("ping")
            
            self.db = self.client["UPI_Automation_DB"]
            self.users = self.db["PremiumUsers"]
            self.payments = self.db["UtrLedger"]

            # Unique tracking indices prevent dirty double-claims under high race-conditions
            await self.payments.create_index([("utr", ASCENDING)], unique=True)
            await self.users.create_index([("user_id", ASCENDING)], unique=True)
            
            logger.info("✅ MongoDB Connected successfully via PyMongo Async API.")
        except Exception as e:
            logger.error(f"❌ Database cluster bootstrap error: {e}")
            raise e

    async def ensure_connection(self):
        """Lazy initializer fallback helper to retain open pool health statuses."""
        if not self.client:
            await self.connect()

    async def register_user_utr(self, user_id: int, utr: str, expected_amount: float) -> str:
        """
        Executed when a user manually inputs their 12-digit UTR in chat.
        Checks if the bank SMS has already arrived, else logs as pending.
        """
        await self.ensure_connection()
        try:
            # Look up if this exact transaction hash was captured by the webhook first
            existing_sms = await self.payments.find_one({"utr": utr, "type": "sms_alert"})
            
            if existing_sms:
                if float(existing_sms["amount"]) == expected_amount:
                    # Target matches! Promote user instantly without delay loops
                    await self.set_user_premium(user_id, duration_days=30)
                    await self.payments.update_one(
                        {"utr": utr}, 
                        {"$set": {"status": "claimed", "user_id": user_id}}
                    )
                    return "instant_success"
                return "amount_mismatch"

            # Log user submission placeholder record into ledger mapping data fields
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
        """
        Executed natively via background server webhooks when your device syncs.
        Cross-checks if any user is currently waiting on confirmation records.
        """
        await self.ensure_connection()
        try:
            # Query if a pending claim matches the incoming payload criteria
            waiting_claim = await self.payments.find_one({"utr": utr, "type": "user_claim", "status": "pending"})
            
            if waiting_claim:
                if float(waiting_claim["amount"]) == extracted_amount:
                    # Validation success! Return user identity payload indices
                    user_id = waiting_claim["user_id"]
                    await self.set_user_premium(user_id, duration_days=30)
                    await self.payments.update_one(
                        {"utr": utr}, 
                        {"$set": {"status": "claimed", "type": "sms_alert"}}
                    )
                    return user_id 
                else:
                    await self.payments.update_one({"utr": utr}, {"$set": {"status": "disputed_amount"}})
                    return None

            # If user hasn't submitted their form yet, log the record ahead of time
            await self.payments.insert_one({
                "utr": utr,
                "amount": extracted_amount,
                "type": "sms_alert",
                "status": "unclaimed",
                "timestamp": time.time()
            })
            return None
        except errors.DuplicateKeyError:
            logger.warning(f"⚠️ Duplicate payload block ignored for current webhook tracking UTR: {utr}")
            return None

    async def set_user_premium(self, user_id: int, duration_days: int):
        """Grants access rights or overwrites current runtime subscription timelines."""
        await self.ensure_connection()
        expiry = time.time() + (duration_days * 86400)
        await self.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_premium": True, "expiry_time": expiry}},
            upsert=True
        )

    async def check_premium_status(self, user_id: int) -> bool:
        """Evaluates operational access grants and clears expired accounts autonomously."""
        await self.ensure_connection()
        user = await self.users.find_one({"user_id": user_id})
        if not user or not user.get("is_premium"):
            return False
        
        if time.time() > user.get("expiry_time", 0):
            # Lifecycle threshold breached, reset mapping access matrices
            await self.users.update_one({"user_id": user_id}, {"$set": {"is_premium": False}})
            return False
        return True
