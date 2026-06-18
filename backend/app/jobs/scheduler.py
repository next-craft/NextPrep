import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
logger = logging.getLogger(__name__)

# No scheduled jobs in the passkey-verified model: transactions complete instantly when
# the buyer enters the code, so there is nothing to abandon or expire. The scheduler is
# kept wired into the app lifespan as the home for any future background job.
