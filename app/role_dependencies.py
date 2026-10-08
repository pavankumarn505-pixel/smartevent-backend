from fastapi import Depends, HTTPException, status

from .dependencies import get_current_user
from .models import User


# =========================================================
# REQUIRE ORGANIZER
# =========================================================

def require_organizer(
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "ORGANIZER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organizer access required"
        )

    return current_user


# =========================================================
# REQUIRE ADMIN
# =========================================================

def require_admin(
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return current_user


# =========================================================
# REQUIRE ORGANIZER OR ADMIN
# =========================================================

def require_organizer_or_admin(
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["ORGANIZER", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organizer or Admin access required"
        )

    return current_user