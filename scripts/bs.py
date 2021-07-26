#! /usr/bin/python3

import sys
sys.path.append('..')

from autolog.eso.periodlog import PeriodLog
from astropy.table import Column, MaskedColumn

log = PeriodLog.read('log.ecsv', format='ascii.ecsv')

self = log
table_type = 'dp_cat'

telescope = self.meta['telescope']
if night := self.meta.get('night', None):
    what = f'night of {night} at {telescope}'
elif period := self.meta.get('period', None):
    what = f'period {period} at {telescope}'
else:
    what = f'at {telescope}'

kept_keys = self.HTML_COLUMNS[table_type]
group_keys = self.HTML_ROW_GROUPS[table_type]
sort_keys = self.HTML_SORT_KEYS.get(table_type, [])
filter = self.HTML_ROW_FILTRES[table_type]
subtitle = self.HTML_CAPTIONS[table_type]
progress = self.HTML_PROGRESS.get(table_type, None)

units = [c.unit.name if c.unit else '' for c in self.itercols()]

summary = filter(self).summary(group_keys)

# Report progress as a function of total available time

if progress == 'time':
    for name in ['night_hours', 'twilight_hours']:
        fname = name[:-6] + '_fraction'
        fval = summary[name] / self.meta['ephemeris'][name]
        col = Column(fval, name=fname, format='.1%', unit=None)
        summary.add_column(col)
        kept_keys.append(fname)

if len(sort_keys) == 1:
    subtotals = summary.summary(sort_keys)
    for name in subtotals.colnames:
        if subtotals[name].dtype.char == 'U' and name not in sort_keys:
            subtotals[name] = 'all'
        if name == 'progress':
            exec = subtotals['executed']
            alloc = subtotals['allocated']
            subtotals['progress'] = exec / alloc
    for subtotal in subtotals:
        summary.add_row(subtotal)



if sort_keys:
    summary.sort(kept_keys)
    summary = summary.group_by(sort_keys)

summary = summary[kept_keys]

