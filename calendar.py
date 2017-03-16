# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import uuid
from dateutil import rrule, relativedelta
from dateutil.rrule import weekday, weekdays
from itertools import groupby

import datetime

from sql import Null

from trytond.model import Model, ModelSQL, ModelView, fields, Check, Unique
from trytond.tools import reduce_ids, grouped_slice
from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond.pool import Pool


__all__ = ['Calendar',
     'ReadUser', 'WriteUser',
     'Event', 'EventRDate', 'EventExDate',
     'RRuleMixin', 'EventRRule', 'EventExRule']


_weekday_map = {"MO": 0, "TU": 1, "WE": 2, "TH": 3,
                    "FR": 4, "SA": 5, "SU": 6}

def handle_byweekday_item(wday):
    if wday:
        n = w = None
        if '(' in wday:
            # If it's of the form TH(+1), etc.
            splt = wday.split('(')
            w = splt[0]
            n = int(splt[1][:-1])
        elif len(wday):
            # If it's of the form +1MO
            for i in range(len(wday)):
                if wday[i] not in '+-0123456789':
                    n = wday[:i] or None
                    w = wday[i:]
                    break
                n = wday[:i+1] or None
            if n:
                n = int(n)
        if w:
            return weekdays[_weekday_map[w]](n)
        else:
            return n


class Calendar(ModelSQL, ModelView):
    "Calendar"
    __name__ = 'holidays.calendar'
    name = fields.Char('Name', required=True, select=True)
    description = fields.Text('Description')
    parent =  fields.Many2One('holidays.calendar', 'Parent')
    childs = fields.One2Many('holidays.calendar', 'parent', 'Children')
    owner = fields.Many2One('res.user', 'Owner', select=True,
            domain=[('email', '!=', None)],
            help='The user must have an email')
    read_users = fields.Many2Many('holidays.calendar-read-res.user',
            'calendar', 'user', 'Read Users')
    write_users = fields.Many2Many('holidays.calendar-write-res.user',
            'calendar', 'user', 'Write Users')
    _get_name_cache = Cache('holidays_calendar.get_name')
    events = fields.One2Many('holidays.event', 'calendar', 'Events')

    @classmethod
    def __setup__(cls):
        super(Calendar, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('name_uniq', Unique(t, t.name),
                'The name of calendar must be unique.'),
            ]
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def create(cls, vlist):
        calendars = super(Calendar, cls).create(vlist)
        # Restart the cache for get_name
        cls._get_name_cache.clear()
        return calendars

    @classmethod
    def write(cls, calendars, values, *args):
        super(Calendar, cls).write(calendars, values, *args)
        # Restart the cache for get_name
        cls._get_name_cache.clear()

    @classmethod
    def delete(cls, calendars):
        super(Calendar, cls).delete(calendars)
        # Restart the cache for calendar
        cls._get_name_cache.clear()

    @classmethod
    def get_name(cls, name):
        '''
        Return the calendar id of the name
        '''
        calendar_id = cls._get_name_cache.get(name, default=-1)
        if calendar_id == -1:
            calendars = cls.search([
                ('name', '=', name),
                ], limit=1)
            if calendars:
                calendar_id = calendars[0].id
            else:
                calendar_id = None
            cls._get_name_cache.set(name, calendar_id)
        return calendar_id

    def calendar2dates(self, from_date=datetime.date.today(),
                             to_date=datetime.date.today()+relativedelta.relativedelta(years=1)):
        '''
        Get datetime instances values of all events objects of a calendar
        '''
        rs = []
        for e in self.events:
            if e.status not in ['cancelled',]:
                rs += e.event2dates(from_date=from_date, to_date=to_date)
        return rs

    def calendar2alldates(self, from_date=datetime.date.today(),
                            to_date=datetime.date.today()+relativedelta.relativedelta(years=1)):
        '''
        Get datetime instances values of all events objects of a calendar and his parents
        '''
        rs = []
        ids = [self]
        id = self.parent
        while id:
                ids.append(id)
                id = id.parent
        for calendar in ids:
            rs = [k for k, _ in groupby(sorted(rs + calendar.calendar2dates(from_date=from_date, to_date=to_date)))]
        return rs

    def calendar2dictdates(self, from_date=datetime.date.today(),
                                 to_date=datetime.date.today()+relativedelta.relativedelta(years=1)):
        '''
        Get a dict with datetime instances values of all events objects of a calendar
        '''
        rs = {}
        for e in self.events:
            if e.status not in ['cancelled',]:
                for dt in e.event2dates(from_date=from_date, to_date=to_date):
                    if dt.date() in rs:
                        rs[dt.date()] = rs[dt.date()].append([e.calendar.name, e.summary])
                    else:
                        rs[dt.date()] = [[e.calendar.name, e.summary],]
        return rs


class ReadUser(ModelSQL):
    'Calendar - read - User'
    __name__ = 'holidays.calendar-read-res.user'
    calendar = fields.Many2One('holidays.calendar', 'Calendar',
            ondelete='CASCADE', required=True, select=True)
    user = fields.Many2One('res.user', 'User', ondelete='CASCADE',
            required=True, select=True)


class WriteUser(ModelSQL):
    'Calendar - write - User'
    __name__ = 'holidays.calendar-write-res.user'
    calendar = fields.Many2One('holidays.calendar', 'Calendar',
            ondelete='CASCADE', required=True, select=True)
    user = fields.Many2One('res.user', 'User', ondelete='CASCADE',
            required=True, select=True)


class Event(ModelSQL, ModelView):
    "Event"
    __name__ = 'holidays.event'
    _rec_name = 'uuid'
    uuid = fields.Char('UUID', required=True,
            help='Universally Unique Identifier', select=True)
    calendar = fields.Many2One('holidays.calendar', 'Calendar',
            required=True, select=True, ondelete="CASCADE")
    summary = fields.Char('Summary')
    sequence = fields.Integer('Sequence', required=True)
    description = fields.Text('Description')
    dtstart = fields.Date('Start Date', required=True, select=True)
    dtend = fields.Date('End Date', select=True)
    status = fields.Selection([
        ('tentative', 'Tentative'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ], 'Status', required=True)
    rdates = fields.One2Many('holidays.event.rdate', 'event',
        'Recurrence Dates')
    rrules = fields.One2Many('holidays.event.rrule', 'event',
        'Recurrence Rules')
    exdates = fields.One2Many('holidays.event.exdate', 'event',
        'Exception Dates')
    exrules = fields.One2Many('holidays.event.exrule', 'event',
        'Exception Rules')

    @classmethod
    def __setup__(cls):
        super(Event, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('uuid_recurrence_uniq',
                Unique(t, t.uuid, t.calendar),
                'UUID must be unique in a calendar.'),
            ]

    @staticmethod
    def default_uuid():
        return str(uuid.uuid4())

    @staticmethod
    def default_sequence():
        return 0

    @classmethod
    def write(cls, *args):
        cursor = Transaction().cursor

        actions = iter(args)
        args = []
        for events, values in zip(actions, actions):
            values = values.copy()
            if 'sequence' in values:
                del values['sequence']
            args.extend((events, values))

        super(Event, cls).write(*args)

        table = cls.__table__()

        for sub_ids in grouped_slice(events, cursor.IN_MAX):
            red_sql = reduce_ids(table.id, sub_ids)
            cursor.execute(*table.update(
                    columns=[table.sequence],
                    values=[table.sequence + 1],
                    where=red_sql))

    @classmethod
    def copy(cls, events, default=None):
        if default is None:
            default = {}

        new_events = []
        for event in events:
            current_default = default.copy()
            current_default.setdefault('uuid', cls.default_uuid())
            new_events.extend(super(Event, cls).copy([event],
                    default=current_default))
        return new_events

    def event2dates(self, from_date=datetime.date.today(),
                          to_date=datetime.date.today()+relativedelta.relativedelta(years=1)):
        '''
        Get datetime instances values of a event object
        '''
        from_date = max(filter(None, [self.dtstart, from_date]))
        if to_date and from_date > to_date:
            return []

        rs = rrule.rruleset(cache=True)
        if to_date or self.dtend:
            rs.exrule(rrule.rrule(rrule.DAILY,
                                dtstart=   min(filter(None, [to_date, self.dtend])),
                                ))
        if self.rrules:
            for rr in self.rrules:
                rs.rrule(rrule.rrule(rr.freq_num,
                                dtstart=   from_date,
                                interval=  rr.interval if rr.interval else 1,
                                wkst=      rr.wkst.upper() if rr.wkst else None,
                                count=     rr.count,
                                until=     min(rr.until or to_date, to_date) if not rr.count else None,
                                bysetpos=  (int(i) for i in (rr.bysetpos or '').split(',') if i),
                                bymonth=   (int(i) for i in (rr.bymonth or '').split(',') if i),
                                bymonthday=(int(i) for i in (rr.bymonthday or '').split(',') if i),
                                byyearday= (int(i) for i in (rr.byyearday or '').split(',') if i),
                                byweekno=  (int(i) for i in (rr.byweekno or '').split(',') if i),
                                byweekday= (handle_byweekday_item(i) for i in (rr.byday or '').split(',') if i),
                                byeaster=  (int(i) for i in (rr.byeaster or '').split(',') if i),
                                ))
        if self.exrules:
            for ex in self.exrules:
                rs.exrule(rrule.rrule(ex.freq_num,
                                dtstart=   from_date,
                                interval=  ex.interval if ex.interval else 1,
                                wkst=      ex.wkst.upper() if ex.wkst else None,
                                count=     ex.count,
                                until=     ex.until,
                                bysetpos=  (int(i) for i in (ex.bysetpos or '').split(',') if i),
                                bymonth=   (int(i) for i in (ex.bymonth or '').split(',') if i),
                                bymonthday=(int(i) for i in (ex.bymonthday or '').split(',') if i),
                                byyearday= (int(i) for i in (ex.byyearday or '').split(',') if i),
                                byweekno=  (int(i) for i in (ex.byweekno or '').split(',') if i),
                                byweekday= (handle_byweekday_item(i) for i in (ex.byday or '').split(',') if i),
                                byeaster=  (int(i) for i in (ex.byeaster or '').split(',') if i),
                                ))
        if self.rdates:
            rs.rrule([datetime.datetime(rd.date.year,
                                    rd.date.month,
                                    rd.date.day) for rd in self.rdates if rd.date >= from_date])
        if self.exdates:
            rs.exrule([datetime.datetime(ex.date.year,
                                    ex.date.month,
                                    ex.date.day) for ex in self.exdates])
        if not (self.rdates or self.rrules or self.exdates or self.exrules):
            rs.rrule(rrule.rrule(rrule.DAILY,
                                dtstart=   from_date,
                                count=     1 if not self.dtend else None,
                                until=     self.dtend,
                                ))

        return rs


class EventRDate(ModelSQL, ModelView):
    'Recurrence Date'
    __name__ = 'holidays.event.rdate'
    _rec_name = 'datetime'
    date = fields.Date('Date', required=True)
    event = fields.Many2One('holidays.event', 'Event', ondelete='CASCADE',
            select=True, required=True)

    @classmethod
    def create(cls, vlist):
        Event = Pool().get('holidays.event')
        to_write = []
        for values in vlist:
            if values.get('event'):
                # Update write_date of event
                to_write.append(values['event'])
        if to_write:
            Event.write(Event.browse(to_write), {})
        return super(EventRDate, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        Event = Pool().get('holidays.event')

        actions = iter(args)
        events = []
        for event_rdates, values in zip(actions, actions):
            events += [x.event for x in event_rdates]
            if values.get('event'):
                events.append(Event(values['event']))
        if events:
            # Update write_date of event
            Event.write(events, {})
        super(EventRDate, cls).write(*args)

    @classmethod
    def delete(cls, event_rdates):
        pool = Pool()
        Event = pool.get('holidays.event')
        events = [x.event for x in event_rdates]
        if events:
            # Update write_date of event
            Event.write(events, {})
        super(EventRDate, cls).delete(event_rdates)


class EventExDate(EventRDate):
    'Exception Date'
    __name__ = 'holidays.event.exdate'
    _table = 'holidays_event_exdate'  # Needed to override EventRDate._table


class RRuleMixin(Model):
    _rec_name = 'freq'
    freq = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ], 'Frequency', required=True)
    freq_num=fields.Function(fields.Integer('Frequency Value'),
        getter='get_freq_num')
    interval = fields.Integer('Interval')
    wkst = fields.Selection([
        (None, ''),
        ('su', 'Sunday'),
        ('mo', 'Monday'),
        ('tu', 'Tuesday'),
        ('we', 'Wednesday'),
        ('th', 'Thursday'),
        ('fr', 'Friday'),
        ('sa', 'Saturday'),
        ], 'Week Day', sort=False)
    count = fields.Integer('Count')
    until = fields.Date('Until Date')
    bysetpos = fields.Char('By Position')
    bymonth = fields.Char('By Month')
    bymonthday = fields.Char('By Month Day')
    byyearday = fields.Char('By Year Day')
    byweekno = fields.Char('By Week Number')
    byday = fields.Char('By Day')
    byeaster = fields.Char('By Easter')

    @classmethod
    def __setup__(cls):
        super(RRuleMixin, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('until_count_only_one',
                Check(t,
                    (t.until == Null) | (t.count == Null) | (t.count == 0)),
                'Only one of "until" and "count" can be set.'),
            ]
        cls._error_messages.update({
                'invalid_bysetpos': (
                    'Invalid "By Position" in recurrence rule "%s"'),
                'invalid_bymonth': (
                    'Invalid "By Month" in recurrence rule "%s"'),
                'invalid_bymonthday': ('Invalid "By Month Day" in recurrence '
                    'rule "%s"'),
                'invalid_byyearday': ('Invalid "By Year Day" in recurrence '
                    'rule "%s"'),
                'invalid_byweekno': ('Invalid "By Week Number" in recurrence '
                    'rule "%s"'),
                'invalid_byday': 'Invalid "By Day" in recurrence rule "%s"',
                'invalid_byeaster': ('Invalid "By Easter" in recurrence '
                    'rule "%s"'),
                })

    @classmethod
    def get_freq_num(cls, rules, name):
        return dict([ (r.id, {
                              'yearly':  rrule.YEARLY,
                              'monthly': rrule.MONTHLY,
                              'weekly':  rrule.WEEKLY,
                              'daily':   rrule.DAILY,
                             }[r.freq] if r.freq else None) for r in rules ])

    @classmethod
    def validate(cls, rules):
        super(RRuleMixin, cls).validate(rules)
        for rule in rules:
            rule.check_bysetpos()
            rule.check_bymonth()
            rule.check_bymonthday()
            rule.check_byyearday()
            rule.check_byweekno()
            rule.check_byday()
            rule.check_byeaster()

    def check_bysetpos(self):
        if self.bysetpos:
            for setposday in self.bysetpos.split(','):
                try:
                    setposday = int(setposday)
                except Exception:
                    setposday = -1000
                if not (abs(setposday) >= 1 and abs(setposday) <= 366):
                    self.raise_user_error('invalid_bysetpos', (self.rec_name,))

    def check_bymonth(self):
        if self.bymonth:
            for monthnum in self.bymonth.split(','):
                try:
                    monthnum = int(monthnum)
                except Exception:
                    monthnum = -1
                if not (monthnum >= 1 and monthnum <= 12):
                    self.raise_user_error('invalid_bymonth', (self.rec_name,))

    def check_bymonthday(self):
        if self.bymonthday:
            for monthdaynum in self.bymonthday.split(','):
                try:
                    monthdaynum = int(monthdaynum)
                except Exception:
                    monthdaynum = -100
                if not (abs(monthdaynum) >= 1 and abs(monthdaynum) <= 31):
                    self.raise_user_error('invalid_bymonthday', (
                            self.rec_name,))

    def check_byyearday(self):
        if self.byyearday:
            for yeardaynum in self.byyearday.split(','):
                try:
                    yeardaynum = int(yeardaynum)
                except Exception:
                    yeardaynum = -1000
                if not (abs(yeardaynum) >= 1 and abs(yeardaynum) <= 366):
                    self.raise_user_error('invalid_byyearday',
                        (self.rec_name,))

    def check_byweekno(self):
        if self.byweekno:
            for weeknum in self.byweekno.split(','):
                try:
                    weeknum = int(weeknum)
                except Exception:
                    weeknum = -100
                if not (abs(weeknum) >= 1 and abs(weeknum) <= 53):
                    self.raise_user_error('invalid_byweekno', (self.rec_name,))

    def check_byday(self):
        if self.byday:
            for wday in self.byday.split(','):
                n = w = None
                try:
                    if '(' in wday:
                        # If it's of the form TH(+1), etc.
                        splt = wday.split('(')
                        w = splt[0]
                        n = int(splt[1][:-1])
                    elif len(wday):
                        # If it's of the form +1MO
                        for i in range(len(wday)):
                            if wday[i] not in '+-0123456789':
                                n = wday[:i] or None
                                w = wday[i:]
                                break
                            n = wday[:i+1] or None
                        if n:
                            n = int(n)
                except Exception:
                    self.raise_user_error('invalid_byday', (self.rec_name,))
                if (w and w.strip() not in ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']) or \
                    (not w and n and (n<0 or n>6)):
                    self.raise_user_error('invalid_byday', (self.rec_name,))

    def check_byeaster(self):
        if self.byeaster:
            for easternum in self.byeaster.split(','):
                try:
                    easternum = int(easternum)
                except Exception:
                    easternum = -1000
                if not (abs(easternum) <= 366):
                    self.raise_user_error('invalid_byeaster',
                        (self.rec_name,))


class EventRRule(RRuleMixin, ModelSQL, ModelView):
    'Recurrence Rule'
    __name__ = 'holidays.event.rrule'
    event = fields.Many2One('holidays.event', 'Event', ondelete='CASCADE',
            select=True, required=True)

    @classmethod
    def create(cls, vlist):
        Event = Pool().get('holidays.event')
        to_write = []
        for values in vlist:
            if values.get('event'):
                # Update write_date of event
                to_write.append(values['event'])
        if to_write:
            Event.write(Event.browse(to_write), {})
        return super(EventRRule, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        Event = Pool().get('holidays.event')

        actions = iter(args)
        events = []
        for event_rrules, values in zip(actions, actions):
            events += [x.event for x in event_rrules]
            if values.get('event'):
                events.append(Event(values['event']))
        if events:
            # Update write_date of event
            Event.write(events, {})
        super(EventRRule, cls).write(*args)

    @classmethod
    def delete(cls, event_rrules):
        pool = Pool()
        Event = pool.get('holidays.event')
        events = [x.event for x in event_rrules]
        if events:
            # Update write_date of event
            Event.write(events, {})
        super(EventRRule, cls).delete(event_rrules)


class EventExRule(EventRRule):
    'Exception Rule'
    __name__ = 'holidays.event.exrule'
    _table = 'holidays_event_exrule'  # Needed to override EventRRule._table
