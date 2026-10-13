
import sqlite3

conn = sqlite3.connect("smartEvent.db")

try:
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(payments)")
    }

    migrations = {
        "refund_status": (
            "ALTER TABLE payments "
            "ADD COLUMN refund_status VARCHAR(20) "
            "NOT NULL DEFAULT 'NONE'"
        ),
        "refund_amount": (
            "ALTER TABLE payments "
            "ADD COLUMN refund_amount FLOAT "
            "NOT NULL DEFAULT 0"
        ),
        "refund_transaction_id": (
            "ALTER TABLE payments "
            "ADD COLUMN refund_transaction_id VARCHAR(255)"
        ),
        "refunded_at": (
            "ALTER TABLE payments "
            "ADD COLUMN refunded_at DATETIME"
        ),
    }

    for column, sql in migrations.items():
        if column not in columns:
            conn.execute(sql)
            print(f"Added column: {column}")
        else:
            print(f"Already exists: {column}")

    conn.commit()
    print("Refund database migration completed.")

except Exception:
    conn.rollback()
    raise

finally:
    conn.close()
