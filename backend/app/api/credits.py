import os
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Optional
from uuid import UUID
import math

from backend.app.core.database import get_db
from backend.app.core.auth import get_current_active_user
from backend.app.models import Project, User, CreditTransaction
from backend.app.schemas import (
    UserResponse, CreditTransactionResponse,
    PaginatedResponse,
)

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("/balance", response_model=dict)
async def get_credit_balance(
    current_user: User = Depends(get_current_active_user),
):
    return {"credits": current_user.credits}


@router.get("/transactions", response_model=PaginatedResponse)
async def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(CreditTransaction).where(CreditTransaction.user_id == current_user.id)
    count_query = select(func.count(CreditTransaction.id)).where(CreditTransaction.user_id == current_user.id)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    query = query.order_by(desc(CreditTransaction.created_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    transactions = result.scalars().all()
    
    return PaginatedResponse(
        items=[CreditTransactionResponse.model_validate(t) for t in transactions],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size > 0 else 0,
    )


@router.post("/purchase", response_model=UserResponse)
async def purchase_credits(
    amount: int,
    payment_method_id: str,  # In real app, integrate with Stripe
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    
    if os.getenv("PAYMENTS_ENABLED", "false").lower() not in ("true", "1"):
        raise HTTPException(status_code=503, detail="Credit purchases are unavailable until a payment processor is configured.")
    raise HTTPException(status_code=503, detail="Payment processing is not configured.")
    
    transaction = CreditTransaction(
        user_id=current_user.id,
        amount=amount,
        transaction_type="purchase",
        description=f"Purchased {amount} credits",
    )
    db.add(transaction)
    
    await db.flush()
    await db.refresh(current_user)
    return current_user


# Admin endpoint for credit management
@router.post("/admin/grant", response_model=UserResponse)
async def admin_grant_credits(
    user_id: UUID,
    amount: int,
    description: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.credits += amount
    transaction = CreditTransaction(
        user_id=user.id,
        amount=amount,
        transaction_type="bonus",
        description=description,
    )
    db.add(transaction)
    
    await db.flush()
    await db.refresh(user)
    return user