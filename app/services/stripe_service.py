import os

import stripe
from dotenv import load_dotenv


load_dotenv()

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")

if not STRIPE_SECRET_KEY:
    raise ValueError(
        "STRIPE_SECRET_KEY is not configured in .env"
    )

stripe.api_key = STRIPE_SECRET_KEY


def create_checkout_session(
    event_title: str,
    ticket_price: float,
    ticket_quantity: int,
    booking_id: int
):
    total_amount = int(
        ticket_price * ticket_quantity * 100
    )

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],

        line_items=[
            {
                "price_data": {
                    "currency": "inr",
                    "product_data": {
                        "name": event_title
                    },
                    "unit_amount": total_amount
                },
                "quantity": 1
            }
        ],

        mode="payment",

        success_url=(
            "http://localhost:5173/"
            "?payment=success"
        ),

        cancel_url=(
            "http://localhost:5173/"
            "?payment=cancelled"
        ),

        metadata={
            "booking_id": str(booking_id)
        }
    )

    return session