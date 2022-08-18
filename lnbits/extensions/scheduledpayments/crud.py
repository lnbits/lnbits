from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import (
    CreateScheduleData,
    CreateScheduleEventData,
    Schedule,
    ScheduleEvent,
    UpdateScheduleData,
    UpdateScheduleEventData,
)


async def get_schedule(schedule_id: str) -> Optional[Schedule]:
    row = await db.fetchone(
        "SELECT * FROM scheduledpayments.schedule WHERE id = ?", (schedule_id,)
    )
    return Schedule.from_row(row) if row else None


async def delete_schedule(schedule_id: str) -> Optional[bool]:
    await db.execute(
        "DELETE FROM scheduledpayments.schedule WHERE id = ?", (schedule_id,)
    )
    return True


async def get_schedules_for_cron() -> List[Schedule]:
    rows = await db.fetchall("SELECT * FROM scheduledpayments.schedule")

    return [Schedule.from_row(row) for row in rows]


async def get_schedules(wallet_ids: Union[str, List[str]]) -> List[Schedule]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM scheduledpayments.schedule WHERE wallet IN ({q})",
        (*wallet_ids,),
    )

    return [Schedule.from_row(row) for row in rows]


async def create_schedule(wallet_id: str, data: CreateScheduleData) -> Schedule:
    schedule_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO scheduledpayments.schedule (id, wallet, recipient, famount, currency, interval, timezone, start_date, end_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            schedule_id,
            wallet_id,
            data.recipient,
            int(data.famount * 100),
            data.currency,
            data.interval,
            data.timezone,
            data.start_date,
            data.end_date,
        ),
    )

    schedule = await get_schedule(schedule_id)
    assert schedule, "Newly created schedule couldn't be retrieved"
    return schedule


async def update_schedule(wallet_id: str, data: UpdateScheduleData) -> Schedule:
    await db.execute(
        """
        UPDATE scheduledpayments.schedule 
        SET wallet = ?, recipient = ?, famount = ?, currency = ?, interval = ?, timezone = ?, start_date = ?, end_date = ?
        WHERE id = ?
        """,
        (
            wallet_id,
            data.recipient,
            int(data.famount * 100),
            data.currency,
            data.interval,
            data.timezone,
            data.start_date,
            data.end_date,
            data.id,
        ),
    )

    schedule = await get_schedule(data.id)
    assert schedule, "Newly updated schedule couldn't be retrieved"
    return schedule


async def get_events(wallet_ids: Union[str, List[str]]) -> List[ScheduleEvent]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"""
        SELECT * 
        FROM scheduledpayments.schedule_events se
        JOIN scheduledpayments.schedule s ON s.id = se.schedule_id 
        WHERE s.wallet IN ({q})
        """,
        (*wallet_ids,),
    )

    return [ScheduleEvent.from_row(row) for row in rows]


async def get_schedule_events(schedule_id: str) -> List[ScheduleEvent]:
    rows = await db.fetchall(
        f"SELECT * FROM scheduledpayments.schedule_events WHERE schedule_id = ?",
        (schedule_id,),
    )

    return [ScheduleEvent.from_row(row) for row in rows]


async def get_schedule_event(schedule_event_id: str) -> Optional[ScheduleEvent]:
    row = await db.fetchone(
        "SELECT * FROM scheduledpayments.schedule_events WHERE id = ?",
        (schedule_event_id,),
    )
    return ScheduleEvent.from_row(row) if row else None


async def create_schedule_event(data: CreateScheduleEventData) -> ScheduleEvent:
    schedule_event_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO scheduledpayments.schedule_events (id, schedule_id, amount, payment_hash, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            schedule_event_id,
            data.get("schedule_id"),
            data.get("amount"),
            data.get("payment_hash"),
            data.get("status"),
        ),
    )

    schedule_event = await get_schedule_event(schedule_event_id)
    assert schedule_event, "Newly created schedule event couldn't be retrieved"
    return schedule_event


async def update_schedule_event(data: UpdateScheduleEventData) -> ScheduleEvent:
    await db.execute(
        """
        UPDATE scheduledpayments.schedule_events
        SET schedule_id = ?, amount = ?, payment_hash = ?, status = ?
        WHERE id = ?
        """,
        (
            data.schedule_id,
            data.amount,
            data.payment_hash,
            data.status,
            data.id,
        ),
    )

    schedule_event = await get_schedule_event(data.id)
    assert schedule_event, "Newly updated schedule event couldn't be retrieved"
    return schedule_event
