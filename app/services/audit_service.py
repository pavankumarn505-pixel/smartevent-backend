from sqlalchemy.orm import Session

from ..models import AuditLog


def create_audit_log(
    db: Session,
    user_id: int | None,
    action: str,
    description: str,
    resource_type: str | None = None,
    resource_id: int | None = None,
    ip_address: str | None = None,
):
    """
    Create an audit log record.

    The caller is responsible for committing the transaction.
    """

    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        description=description,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
    )

    db.add(audit_log)

    return audit_log