import json
import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
model_name = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

client = OpenAI(api_key=api_key) if api_key else None


def classify_query(message: str) -> dict:
    """
    Convert the user's message into a supported chatbot intent.
    """

    if client is None:
        return {
            "intent": "support",
            "category": None,
            "location": None,
            "start_date": None,
            "end_date": None,
        }

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": """
You classify queries for the SmartEvent event-booking application.

Return only a JSON object with these fields:
- intent: events, bookings, or support
- category: event category or null
- location: requested location or null
- start_date: YYYY-MM-DD or null
- end_date: YYYY-MM-DD or null

Use events for event discovery.
Use bookings for requests to view the user's bookings.
Use support for ticket problems or general help.

Never invent event or booking information.
The application retrieves real information from its database.
""",
            },
            {"role": "user", "content": message},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    content = response.choices[0].message.content

    if not content:
        raise ValueError("The AI returned an empty response.")

    result = json.loads(content)

    if result.get("intent") not in {"events", "bookings", "support"}:
        result["intent"] = "support"

    return result


def generate_support_reply(message: str) -> str:
    """
    Generate general ticket-support guidance.
    """

    if client is None:
        return (
            "For ticket issues, open your booking details and check the "
            "booking status. If payment succeeded but your ticket is missing, "
            "keep your payment reference and booking ID ready for support. "
            "Do not share passwords, OTPs, or payment card details."
        )

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": """
You are the SmartEvent support assistant.
Give concise, helpful guidance about event bookings and tickets.
Do not claim to issue refunds, cancel bookings, or change payment status.
Never ask users for passwords, OTPs, or complete payment-card details.
For account-specific problems, direct the user to the authenticated
booking details or the application's support team.
""",
            },
            {"role": "user", "content": message},
        ],
        temperature=0.3,
    )

    return response.choices[0].message.content or (
        "Please check your booking details or contact SmartEvent support."
    )