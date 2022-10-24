import asyncio

import crontools as ct
import httpx
import pendulum
from lnurl import decode as decode_lnurl
from pytz import timezone

from lnbits.core.services import PaymentFailure, pay_invoice
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis

from .crud import (
    create_schedule_event,
    get_schedule_events,
    get_schedules_for_cron,
    update_schedule_event,
)
from .utils import check_balance


async def wait_for_scheduled_payments():
    # sleep for 60 seconds at the start, wait for migrations etc to run.
    await asyncio.sleep(60)

    # start a new loop
    while True:
        # we want to execute once per minute
        await asyncio.gather(
            asyncio.sleep(60),
            run_scheduled_payments(),
        )


async def run_scheduled_payments():
    # fetch all the schedules
    schedules = await get_schedules_for_cron()

    for schedule in schedules:
        # run an individual schedule
        result = await run_scheduled_payment(schedule)

    return True


async def run_scheduled_payment(schedule):
    now = pendulum.now(schedule.timezone)

    # determine if the schedule starts in the future. If it does, skip
    if schedule.start_date:
        start_date = pendulum.parse(schedule.start_date, tz=schedule.timezone)

        if start_date > now:
            return True

    # determine if the schedule ends in the past. If it does, skip
    if schedule.end_date:
        end_date = pendulum.parse(schedule.end_date, tz=schedule.timezone)

        if end_date < now:
            return True

    # fetch all events for this schedule
    events = await get_schedule_events(schedule.id)

    # if no previous events, go back to 0
    if not events:
        lastrun = pendulum.from_timestamp(0, schedule.timezone)
    else:
        # sort the list by time desc
        sortedevents = sorted(
            events,
            key=lambda d: d.time,
            reverse=True,
        )

        lastevent = sortedevents[0]

        # the most recent event is now first in the list
        lastrun = pendulum.from_timestamp(lastevent.time, schedule.timezone)

        # if the last event is still in_progress, we should investigate
        if lastevent.status == "in_progress":
            # if the last run started > 5 minutes ago we should update the status
            if now > lastrun.add(minutes=5):
                lastevent.status = "Error: Timed Out"
                event = await update_schedule_event(data=lastevent)

            return True

    cron = ct.Crontab.parse(
        schedule.interval,
        tz=timezone(schedule.timezone),
    )

    # calculate when the next run should be
    nextrun = cron.next_fire_time(now=lastrun)

    # determine whether we should execute this schedule now
    if nextrun < now:
        print(f"{nextrun} < {now} fire!")

        amount_in_sats = await fiat_amount_as_satoshis(
            schedule.famount / 100, schedule.currency
        )

        event = await create_schedule_event(
            data={
                "schedule_id": schedule.id,
                "amount": amount_in_sats,
                "status": "in_progress",
            }
        )

        # check the user's balance and don't continue if they don't have enough
        if not await check_balance(schedule.wallet, amount_in_sats):
            event.status = f"Error: Balance too low to pay"
            event = await update_schedule_event(data=event)
            return False

        # users can enter bech32 encoded lnurl, or a lightning address like lnbits@lntips.com
        if schedule.recipient.upper().startswith("LNURL"):
            url = decode_lnurl(schedule.recipient)
        else:
            parts = schedule.recipient.split("@")

            if len(parts) != 2:
                event.status = f"Error: Bad Lightning Address"
                event = await update_schedule_event(data=event)
                return False

            username = parts[0]
            domain = parts[1]
            url = f"https://{domain}/.well-known/lnurlp/{username}"

        # process the lnurl
        async with httpx.AsyncClient() as client:
            try:
                # get the lnurl
                r = await client.get(url, follow_redirects=True)
                if r.is_error:
                    event.status = f"Error: loading {url}"
                    event = await update_schedule_event(data=event)
                    return False
                else:
                    resp = r.json()
                    if resp["tag"] != "payRequest":
                        event.status = f"Error: Wrong tag type {resp['tag']}"
                        event = await update_schedule_event(data=event)
                        return False
                    else:
                        # now send the amount to the designated callback url to get an invoice
                        r2 = await client.get(
                            resp["callback"],
                            follow_redirects=True,
                            params={
                                "amount": amount_in_sats * 1000,
                            },
                        )
                        resp2 = r2.json()
                        if r2.is_error:
                            event.status = "Error: loading callback"
                            event = await update_schedule_event(data=event)
                            return False
                        elif resp2.get("status") == "ERROR":
                            event.status = f"Error: {resp2['reason']}"
                            event = await update_schedule_event(data=event)
                            return False
                        else:
                            # pay the invoice generated by the lnurl
                            payment_hash = await pay_invoice(
                                wallet_id=schedule.wallet,
                                payment_request=resp2["pr"],
                                extra={
                                    "tag": "scheduledpayments",
                                    "schedule_id": schedule.id,
                                },
                            )
            except (ValueError, PermissionError, PaymentFailure) as e:
                event.status = "Error: Failed to pay invoice: " + str(e)
                event = await update_schedule_event(data=event)
                return False
            except Exception as e:
                event.status = "Error: Unexpected"
                event = await update_schedule_event(data=event)

        event.status = "complete"
        event.payment_hash = payment_hash
        event = await update_schedule_event(data=event)

        return True

    return True
