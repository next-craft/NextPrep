import logging
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing
from app.models.seller_rating import SellerRating
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import (
    CompleteTransactionResponse,
    RatingResponse,
    TransactionListItem,
)

logger = logging.getLogger(__name__)

# Verified-transaction count at which a seller earns the verification badge.
VERIFICATION_BADGE_THRESHOLD = 10


def attempts_message(remaining: int) -> str:
    if remaining == 1:
        return "Incorrect passkey. 1 attempt remaining."
    return f"Incorrect passkey. {remaining} attempts remaining."


async def record_failed_attempt(redis, listing_id: str, buyer_id: str) -> int:
    """Atomically increment the buyer's attempt counter for this listing and
    refresh its 7-day TTL. Returns the new attempt count."""
    attempts_key = f"passkey_attempts:{listing_id}:{buyer_id}"
    pipe = redis.pipeline()
    pipe.incr(attempts_key)
    pipe.expire(attempts_key, 604800)  # 7 days
    count, _ = await pipe.execute()
    return count


async def complete_transaction(
    db: AsyncSession, listing: Listing, buyer_id: str
) -> CompleteTransactionResponse:
    """Mark the listing SOLD and record a verified transaction. The passkey has
    already been verified by the caller. This is the sole completion mechanism —
    the platform processes no payment.

    Winner-selection is atomic (UPDATE ... WHERE is_available): only one buyer can
    close a listing, so a second concurrent verify gets a clean 409.
    """
    seller_id = listing.seller_id

    listing_result = await db.execute(
        update(Listing)
        .where(
            Listing.id == listing.id,
            Listing.is_available == True,  # noqa: E712
            Listing.passkey_invalidated == False,  # noqa: E712
        )
        .values(
            is_available=False,
            sold_at=func.now(),
            passkey_invalidated=True,
            passkey_invalidated_at=func.now(),
        )
        .returning(Listing.id)
    )
    if not listing_result.fetchone():
        raise HTTPException(409, "This listing has already been sold.")

    transaction = Transaction(
        listing_id=listing.id,
        buyer_id=UUID(buyer_id),
        seller_id=seller_id,
    )
    db.add(transaction)

    # Reputation counters — incremented in the same DB transaction as the sale.
    await db.execute(
        update(User).where(User.id == seller_id).values(books_sold=User.books_sold + 1)
    )
    # Award the badge once the seller crosses the threshold. Runs after the increment
    # above, so it sees the new books_sold value within this transaction.
    await db.execute(
        update(User)
        .where(User.id == seller_id, User.books_sold >= VERIFICATION_BADGE_THRESHOLD)
        .values(is_verified=True)
    )
    await db.execute(
        update(User).where(User.id == UUID(buyer_id)).values(books_bought=User.books_bought + 1)
    )

    seller_name = (
        await db.execute(select(User.full_name).where(User.id == seller_id))
    ).scalar_one_or_none() or "Seller"

    await db.flush()  # transaction.id needed for the response
    txn_id = transaction.id
    await db.commit()

    logger.info(
        "transaction_completed listing=%s buyer=%s seller=%s transaction=%s",
        listing.id, buyer_id, seller_id, txn_id,
    )
    return CompleteTransactionResponse(
        transaction_id=txn_id,
        seller_id=seller_id,
        seller_name=seller_name,
        listing_title=listing.title,
    )


async def get_my_transactions(db: AsyncSession, user_id: str) -> list[TransactionListItem]:
    """The caller's verified transactions as buyer and seller, newest first. Joins the
    listing title (NULL when the listing was deleted) and the seller's name, and flags
    whether the caller (as buyer) can still rate this transaction."""
    uid = UUID(user_id)
    result = await db.execute(
        select(Transaction, Listing.title, User.full_name, SellerRating.id)
        .outerjoin(Listing, Transaction.listing_id == Listing.id)
        .join(User, Transaction.seller_id == User.id)
        .outerjoin(
            SellerRating,
            (SellerRating.transaction_id == Transaction.id) & (SellerRating.rated_by == uid),
        )
        .where((Transaction.buyer_id == uid) | (Transaction.seller_id == uid))
        .order_by(Transaction.created_at.desc())
    )
    items: list[TransactionListItem] = []
    for txn, title, seller_name, rating_id in result.all():
        is_buyer = txn.buyer_id == uid
        items.append(
            TransactionListItem(
                id=txn.id,
                role="buyer" if is_buyer else "seller",
                listing_title=title,
                created_at=txn.created_at,
                seller_id=txn.seller_id,
                seller_name=seller_name,
                can_rate=is_buyer and rating_id is None,
            )
        )
    return items


async def rate_seller(
    db: AsyncSession, transaction_id: UUID, buyer_id: str, rating: int, review: str | None
) -> RatingResponse:
    """Record the buyer's 1-5 rating (+ optional review) for a verified transaction and
    recompute the seller's average. Buyer-only, once per transaction (DB-enforced)."""
    txn = await db.get(Transaction, transaction_id)
    if not txn:
        raise HTTPException(404, "Transaction not found.")
    if str(txn.buyer_id) != buyer_id:
        raise HTTPException(403, "Only the buyer can rate this transaction.")

    db.add(
        SellerRating(
            transaction_id=transaction_id,
            rated_by=UUID(buyer_id),
            seller_id=txn.seller_id,
            rating=rating,
            review=review,
        )
    )
    try:
        await db.flush()
    except IntegrityError:
        # uq_rating_transaction_rater — already rated.
        await db.rollback()
        raise HTTPException(409, "You have already rated this transaction.")

    # Recompute the denormalised average from all of this seller's verified ratings.
    avg = (
        await db.execute(
            select(func.avg(SellerRating.rating)).where(SellerRating.seller_id == txn.seller_id)
        )
    ).scalar_one()
    await db.execute(update(User).where(User.id == txn.seller_id).values(seller_rating=avg))
    await db.commit()

    logger.info("seller_rated transaction=%s seller=%s", transaction_id, txn.seller_id)
    return RatingResponse(
        transaction_id=transaction_id,
        rating=rating,
        review=review,
        seller_rating=round(float(avg), 2) if avg is not None else None,
    )
