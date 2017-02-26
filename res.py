# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


__all__ = ['User']
__metaclass__ = PoolMeta


class User:
    __name__ = 'res.user'

    calendars = fields.One2Many('holidays.calendar', 'owner', 'Calendars')
