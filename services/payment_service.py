# services/payment_service.py
import json
import asyncio
import logging
from yookassa import Payment

async def check_payment(payment_id: str) -> tuple[bool, dict]:
    payment = json.loads((Payment.find_one(payment_id)).json())
    while payment['status'] == 'pending':
        payment = json.loads((Payment.find_one(payment_id)).json())
        await asyncio.sleep(10)
    if payment['status'] == 'succeeded':
        logging.info("SUCCESS RETURN")
        return True, payment
    else:
        logging.info("BAD RETURN")
        return False, {}