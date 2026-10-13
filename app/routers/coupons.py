
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import Coupon, User
from ..schemas import (
    CouponCreate,
    CouponResponse,
    CouponValidateRequest,
    CouponValidateResponse,
)

router = APIRouter(
    prefix="/coupons",
    tags=["Coupons"]
)


def require_admin(current_user: User):
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Only administrators can manage coupons"
        )


def get_current_time():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def validate_coupon(coupon: Coupon):
    if not coupon.is_active:
        raise HTTPException(
            status_code=400,
            detail="This coupon is inactive"
        )

    expiry = coupon.expiry_date

    # Handle dates stored with or without timezone information.
    if expiry.tzinfo is not None:
        expiry = expiry.astimezone(timezone.utc).replace(tzinfo=None)

    if expiry <= get_current_time():
        raise HTTPException(
            status_code=400,
            detail="This coupon has expired"
        )

    if coupon.used_count >= coupon.usage_limit:
        raise HTTPException(
            status_code=400,
            detail="This coupon has reached its usage limit"
        )


@router.post(
    "/",
    response_model=CouponResponse,
    status_code=201
)
def create_coupon(
    coupon_data: CouponCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_admin(current_user)

    code = coupon_data.coupon_code.strip().upper()

    if not code:
        raise HTTPException(
            status_code=400,
            detail="Coupon code cannot be empty"
        )

    if coupon_data.discount_type == "PERCENTAGE":
        if coupon_data.discount_value > 100:
            raise HTTPException(
                status_code=400,
                detail="Percentage discount cannot exceed 100"
            )

    if coupon_data.expiry_date.tzinfo is not None:
        expiry = coupon_data.expiry_date.astimezone(
            timezone.utc
        ).replace(tzinfo=None)
    else:
        expiry = coupon_data.expiry_date

    if expiry <= get_current_time():
        raise HTTPException(
            status_code=400,
            detail="Expiry date must be in the future"
        )

    existing_coupon = (
        db.query(Coupon)
        .filter(Coupon.coupon_code == code)
        .first()
    )

    if existing_coupon:
        raise HTTPException(
            status_code=400,
            detail="Coupon code already exists"
        )

    coupon = Coupon(
        coupon_code=code,
        discount_type=coupon_data.discount_type,
        discount_value=coupon_data.discount_value,
        minimum_booking_amount=coupon_data.minimum_booking_amount,
        expiry_date=expiry,
        usage_limit=coupon_data.usage_limit,
        used_count=0,
        is_active=True
    )

    db.add(coupon)
    db.commit()
    db.refresh(coupon)

    return coupon


@router.get(
    "/",
    response_model=list[CouponResponse]
)
def list_coupons(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_admin(current_user)

    return (
        db.query(Coupon)
        .order_by(Coupon.id.desc())
        .all()
    )


@router.post(
    "/validate",
    response_model=CouponValidateResponse
)
def validate_coupon_code(
    request: CouponValidateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    code = request.coupon_code.strip().upper()

    coupon = (
        db.query(Coupon)
        .filter(Coupon.coupon_code == code)
        .first()
    )

    if coupon is None:
        raise HTTPException(
            status_code=404,
            detail="Coupon code not found"
        )

    validate_coupon(coupon)

    if request.booking_amount < coupon.minimum_booking_amount:
        raise HTTPException(
            status_code=400,
            detail=(
                "Booking amount must be at least "
                f"{coupon.minimum_booking_amount:.2f}"
            )
        )

    if coupon.discount_type == "PERCENTAGE":
        discount = (
            request.booking_amount
            * coupon.discount_value
            / 100
        )
    else:
        discount = coupon.discount_value

    # Never allow the discount to exceed the booking amount.
    discount = min(discount, request.booking_amount)

    # Round monetary values to two decimal places.
    discount = round(discount, 2)
    final_amount = round(
        request.booking_amount - discount,
        2
    )

    return CouponValidateResponse(
        coupon_code=coupon.coupon_code,
        discount_type=coupon.discount_type,
        discount_value=coupon.discount_value,
        booking_amount=request.booking_amount,
        discount_amount=discount,
        final_amount=final_amount,
        message="Coupon applied successfully"
    )
