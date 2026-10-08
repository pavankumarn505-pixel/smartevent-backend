import os
import uuid

import qrcode


# Folder where QR images will be stored
QR_FOLDER = "qr_codes"

# Create folder if it does not exist
os.makedirs(QR_FOLDER, exist_ok=True)


def generate_ticket_code():
    """
    Generate a unique ticket code.
    """
    return f"TKT-{uuid.uuid4().hex[:12].upper()}"


def generate_qr_code(ticket_code: str):
    """
    Generate a QR image for the ticket code.
    """

    file_name = f"{ticket_code}.png"

    file_path = os.path.join(
        QR_FOLDER,
        file_name
    )

    qr = qrcode.make(ticket_code)

    qr.save(file_path)

    # URL used by the frontend/browser
    qr_url = f"/qr_codes/{file_name}"

    return qr_url

