import logging

from enum import StrEnum, Enum

from EventKit import (
    EKAlarm,
    EKEvent,  # type: ignore
    EKEventStore,  # type: ignore
    EKReminder,  # type: ignore
    EKEntityTypeReminder,  # type: ignore
    EKEntityTypeEvent,  # type: ignore
    EKCalendar,  # type: ignore
)
from Foundation import NSDate  # type: ignore

from datetime import date, datetime, time as dt_time, timedelta
from time import sleep, time

logger = logging.getLogger()


class NotProvided:
    pass


NOT_PROVIDED = NotProvided()

store = EKEventStore()

CALENDARS = list(store.calendarsForEntityType_(EKEntityTypeEvent))
REMINDERS = list(store.calendarsForEntityType_(EKEntityTypeReminder))

assert CALENDARS, "Unable to load calendars"


for _c in CALENDARS:
    logger.info(f"Found calendar: {_c.title()} ({_c.UUID()})")
logger.info(f"Found {len(CALENDARS)} calendar")


for _c in REMINDERS:
    logger.info(f"Found reminder: {_c.title()} ({_c.UUID()})")
logger.info(f"Found {len(REMINDERS)} calendar")

# Events
EVENT_CALENDAR = [cal for cal in CALENDARS if cal.title().lower() == "events"][0]

# G L
ACTIVITIES_CALENDAR = [
    cal
    for cal in CALENDARS
    if (cal.title().lower()[0] == "g" and cal.title().lower()[-1] == "l")
][0]

# Reminders
TODO_CALENDAR = [cal for cal in REMINDERS if cal.title().lower() == "todo"][0]


class ResultCompletion:
    def __init__(self):
        self.completed = False
        self.args = []
        self.kwargs = {}
        self.callback_wrapper = None

    def __call__(self, *args, **kwargs):
        self.args.extend(args)
        self.kwargs.update(kwargs)
        self.completed = True

    def wait(self, timeout=1, no_raise=False):  # 1 second
        time_threshold = (time() + timeout) if timeout > 0 else 9_999_999_999
        while not self.completed:
            sleep(0.1)
            if time() >= time_threshold:
                if no_raise:
                    break
                else:
                    raise RuntimeError()

    def wait_args(self, idx=None, *, timeout=1, no_raise=False):
        self.wait(timeout=timeout, no_raise=no_raise)
        if idx is not None:
            return self.args[idx]
        return self.args

    def callback(self):
        if self.completed:
            raise RuntimeError("Already completed")

        def f(*args, **kwargs):
            self(*args, **kwargs)

        self.callback_wrapper = f

        return f


def to_nsdate(d):
    if isinstance(d, datetime):
        ts = d.timestamp()
        return NSDate().initWithTimeIntervalSince1970_(ts)

    if isinstance(d, date):
        ts = datetime.combine(d, dt_time()).timestamp()
        return NSDate().initWithTimeIntervalSince1970_(ts)


def to_pytdatetime(tagged_date):
    return datetime.fromtimestamp(tagged_date.timeIntervalSince1970()) + timedelta(
        hours=8
    )


def to_pydate(tagged_date):
    return to_pytdatetime(tagged_date).date()


def query_calendar_for_event(
    cal: EKCalendar | list[EKCalendar] | str, look_forward: int = 365
):
    if isinstance(cal, list):
        cals = cal
    elif isinstance(cal, str):
        cals = []
        all_cals = store.calendarsForEntityType_(EKEntityTypeEvent)
        for c in all_cals:
            if c.title().lower() == cal.lower():
                cals.append(c)
                break
    else:
        cals = [cal]

    if len(cals) == 0:
        return []

    rc = ResultCompletion()

    p = store.predicateForEventsWithStartDate_endDate_calendars_(
        to_nsdate(date.today()),
        to_nsdate(date.today() + timedelta(days=look_forward)),
        cals,
    )
    store.enumerateEventsMatchingPredicate_usingBlock_(p, rc.callback())

    events = rc.wait_args(no_raise=True)

    return events


def query_events(
    start_date: str, end_date: str, calendar_name: str = None, return_object=False
):
    if calendar_name == "EVENTS":
        calendar = [EVENT_CALENDAR]
    elif calendar_name == "ACTIVITIES":
        calendar = [ACTIVITIES_CALENDAR]
    else:
        calendar = [ACTIVITIES_CALENDAR, EVENT_CALENDAR]

    start = datetime.fromisoformat(start_date).date()
    end = datetime.fromisoformat(end_date).date()

    rc = ResultCompletion()

    p = store.predicateForEventsWithStartDate_endDate_calendars_(
        to_nsdate(start),
        to_nsdate(end),
        calendar,
    )
    store.enumerateEventsMatchingPredicate_usingBlock_(p, rc.callback())

    events = rc.wait_args()

    if return_object:
        return events

    ret = f"""
| Event ID | Date | Name | Notes |
|------|------|-----|
"""

    results = [
        f"| {e.calendarItemIdentifier()} | {to_pydate(e.startDate())} | {e.title()} | {e.displayNotes() or ''} |"
        for e in events
    ]

    ret += "\n".join(results)

    return ret


def query_reminders(return_obj=False):
    pred = store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(
        None, None, [TODO_CALENDAR]
    )
    # pred = store.predicateForRemindersInCalendars_([Reminders.TODO.value])

    events = store.remindersMatchingPredicate_(pred)

    values = sorted(
        [
            (
                None if e.dueDate() is None else to_pydate(e.dueDate()),
                e.calendarItemIdentifier(),
                e.title(),
            )
            for e in events
        ],
        key=lambda v: (v[0] or date(2999, 12, 31)),
    )

    if return_obj:
        return values

    results = [
        f"| {v[1]} | {v[2]} | {'' if v[0] is None else v[0].isoformat()} |"
        for v in values
    ]

    ret = f"""
| Reminder ID | Date | Title |
|------|------|-----|
"""

    ret += "\n".join(results)

    return ret


def update_event(
    uuid: str,
    title: str = NOT_PROVIDED,
    start_datetime: str = NOT_PROVIDED,
    end_datetime: str = NOT_PROVIDED,
    notes: str = NOT_PROVIDED,
    is_all_day: bool = NOT_PROVIDED,
    calendar_name: str = NOT_PROVIDED,
):
    event = store.eventWithIdentifier_(uuid)
    if not event:
        return f"No event with UUID: {uuid}"

    if start_datetime is not NOT_PROVIDED:
        start = datetime.fromisoformat(start_datetime)
        event.setStartDate_(to_nsdate(start))

    if end_datetime is not NOT_PROVIDED:
        end = datetime.fromisoformat(end_datetime)
        event.setStartDate_(to_nsdate(end))

    if is_all_day is not NOT_PROVIDED:
        event.setAllDay_(True)

    if title is not NOT_PROVIDED:
        event.setTitle_(title)

    if notes is not NOT_PROVIDED:
        event.setDisplayNotes_(str(notes))

    if calendar_name is not NOT_PROVIDED:
        if calendar_name == "EVENTS":
            event.setCalendar_(EVENT_CALENDAR)
        elif calendar_name == "ACIVITIES":
            event.setCalendar_(ACTIVITIES_CALENDAR)

    store.saveEvent_span_error_(event, True, None)

    return "DONE"


def create_event(
    calendar_name: str,
    title: str,
    start_datetime: str,
    end_datetime: str | None = None,
    notes: str | None = None,
    is_all_day: bool = False,
    return_object=False,
):
    if calendar_name == "EVENTS":
        calendar = EVENT_CALENDAR
    elif calendar_name == "ACTIVITIES":
        calendar = ACTIVITIES_CALENDAR
    else:
        return f"calendar_name must be one of ['EVENTS', 'ACTIVITIES']"

    event = EKEvent().initWithEventStore_(store)

    start = datetime.fromisoformat(start_datetime)
    end = (
        datetime.fromisoformat(end_datetime)
        if end_datetime
        else start + timedelta(hours=1)
    )

    event.setTitle_(title)
    event.setStartDate_(to_nsdate(start))
    if is_all_day:
        event.setAllDay_(True)

    event.setEndDate_(to_nsdate(end))
    event.setCalendar_(calendar)

    if notes:
        event.setDisplayNotes_(str(notes))

    store.saveEvent_span_error_(event, True, None)

    if return_object:
        return event

    return f"DONE, {calendar_name} UUID: {event.calendarItemIdentifier()}"


def update_reminder(
    uuid: str,
    due_date: str = NOT_PROVIDED,
    title: str = NOT_PROVIDED,
    notes: str = NOT_PROVIDED,
):
    reminder = store.reminderWithIdentifier_(uuid)

    if due_date is not NOT_PROVIDED:
        dt = datetime.fromisoformat(due_date)
        reminder.setDueDate_(to_nsdate(dt.date()))

    if title is not NOT_PROVIDED:
        reminder.setTitle_(title)

    if notes is not NOT_PROVIDED:
        reminder.setDisplayNotes_(notes)

    store.saveReminder_commit_error_(reminder, True, None)

    return "DONE"


def create_reminder(
    title: str,
    due_date: str = None,
    notes: str = None,
):
    r = EKReminder.reminderWithEventStore_(store)

    r.setTitle_(title)

    if due_date:
        dt = datetime.fromisoformat(due_date)
        r.setDueDate_(to_nsdate(dt))

    if notes:
        r.setDisplayNotes_(notes)

    r.setCalendar_(TODO_CALENDAR)

    store.saveReminder_commit_error_(r, True, None)

    return f"DONE, Reminder UUID: {r.calendarItemIdentifier()}"


def add_pay_rent():
    cals = store.calendarsForEntityType_(EKEntityTypeReminder)
    for cal in cals:
        if cal.title() == "Todo":
            break

    pred = store.predicateForRemindersInCalendars_([cal])
    events = store.remindersMatchingPredicate_(pred)

    for e in events:
        if e.title() == "Pay Rent" and e.completionDate() is None:
            dd = to_pydate(e.dueDate())
            if dd.day > 10:
                print(e)
                d2 = dd.replace(day=1)
                wk = d2.weekday()
                if wk == 6:
                    final_date = d2 + timedelta(days=6)
                elif wk == 5:
                    final_date = d2 + timedelta(days=7)
                else:
                    final_date = d2 + timedelta(days=5 - wk)

                e.setDueDate_(to_nsdate(final_date))
                store.saveReminder_commit_error_(e, True, None)


if __name__ == "__main__":
    pass
    # cals = store.calendarsForEntityType_(EKEntityTypeEvent)
    # for cal in cals:
    #    if cal.title() == "GUO":
    #        break
    # else:
    #    assert False
    # dates = [
    #     (datetime(2026, 1, 1), "New Year’s Day"),
    #     (datetime(2026, 2, 16), "Eve of Lunar New Year"),
    #     (datetime(2026, 2, 17), "Lunar New Year"),
    #     (datetime(2026, 2, 18), "Lunar New Year"),
    #     (datetime(2026, 3, 13), "Staff Training"),
    #     (datetime(2026, 3, 20), "Eve of Hari Raya (half day)"),
    #     (datetime(2026, 3, 21), "Hari Raya Puasa"),
    #     (datetime(2026, 4, 3), "Good Friday"),
    #     (datetime(2026, 5, 1), "Labour Day"),
    #     (datetime(2026, 5, 27), "Hari Raya Haji"),
    #     (datetime(2026, 5, 31), "Vesak Day"),
    #     (datetime(2026, 7, 10), "Staff Training"),
    #     (datetime(2026, 8, 9), "National Day"),
    #     (datetime(2026, 9, 4), "Teacher’s Day"),
    #     (datetime(2026, 10, 2), "Children’s Day"),
    #     (datetime(2026, 11, 8), "Deepavali"),
    #     (datetime(2026, 11, 18), "Teacher’s Training"),
    #     (datetime(2026, 12, 11), "Spring Cleaning"),
    #     (datetime(2026, 12, 24), "Eve of Christmas"),
    #     (datetime(2026, 12, 25), "Christmas Day"),
    # ]

    # for start_date, desc in dates:
    #     print(desc)
    #     create_event(
    #         desc,
    #         start_date.isoformat(),
    #         is_all_day=False,
    #         cal=Calendars.ALEX.value,
    #         notes=Tag.SCHOOL_HOLIDAY.value,
    #     )


# if False:
#     title: str = "adsf"
#     due_date: date = date(2025, 11, 25)

#     r = EKReminder()
#     r.setDueDate_(to_nsdate(due_date))
#     r.setTitle_(title)

#     r = store.reminderWithIdentifier_("B1542A35-A124-4617-826D-60E49EBA3176")
#     r = EKReminder()


#     >>> tz
#     GMT+0800 (GMT+8) offset 28800
#     >>>

#     from icloud.calendar import *

#     r = EKReminder.reminderWithEventStore_(store)

#     from Foundation import NSTimeZone
#     # tz = NSTimeZone.timeZoneForSecondsFromGMT_(0)
#     r.setTimeZone_(NSTimeZone.timeZoneWithName_('UTC'))
#     r.setDueDate_(to_nsdate(date(2025, 12, 30)))
#     r.setTitle_('test 3')
#     r.setCalendar_(Reminders.TODO.value)

#     store.saveReminder_commit_error_(r, True, None)
