##############################################################################
#
#    GNU Condo: The Free Management Condominium System
#    Copyright (C) 2016- M. Alonso <port02.server@gmail.com>
#
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


from trytond.pool import Pool
from trytond.report import Report

import datetime
from dateutil import relativedelta


__all__ = ['OcurrencesList']


class OcurrencesList(Report):
    __name__ = 'holidays.ocurrences_list'

    @classmethod
    def get_context(cls, records, data):
        report_context = super(OcurrencesList, cls).get_context(records, data)

        pool = Pool()

        cal_ids = data['ids']
        Calendar = pool.get('holidays.calendar')

        for id in data['ids']:
            while Calendar(id).parent:
                cal_ids += [Calendar(id).parent]
                id = Calendar(id).parent
 
        calendaries = Calendar.search([
                    ('id', 'in', cal_ids),
                ], order=[('id', 'ASC')])

        ocurrences = {}
        for c in calendaries:
            ocurrences.update(c.calendar2dictdates(from_date=datetime.date.today()+relativedelta.relativedelta(month=1, day=1),
                                                   to_date=datetime.date.today()+relativedelta.relativedelta(years=2)))

        report_context['ocurrences'] = ocurrences

        return report_context
