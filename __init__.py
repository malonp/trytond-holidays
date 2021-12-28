# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from .calendar import *
from .report import *
from .res import *


def register():
    Pool.register(
        Calendar,
        ReadUser,
        WriteUser,
        Event,
        EventRDate,
        EventExDate,
        EventRRule,
        EventExRule,
        User,
        module='holidays',
        type_='model',
    )
    Pool.register(OcurrencesList, module='holidays', type_='report')
