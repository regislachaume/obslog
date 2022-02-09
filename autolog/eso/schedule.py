from autolog.utils.table import Table
from autolog.utils.io import table_from_excel
from autolog.utils.ephemeris import night_ephemeris
from autolog.eso import path
from autolog.eso import log 
from autolog.utils.telescope import parse_telescope

from collections import OrderedDict
import numpy as np
import copy
import re
from astropy.table import MaskedColumn, Column
        
EPHEMERIS_COLUMNS = {
    'sun set': ('sun set time', '<U5'),
    'sun rise': ('sun rise time', '<U5'),
    'night start': ('astronomical night start time', '<U5'),
    'night end': ('astrononomical night end time', '<U5'),
    'fli': ('fractional lunar illumation at midnight', '<f4'), 
    'dark start': ('start time of dark conditions', '<U5'),
    'dark end': ('end time of dark conditions', '<U5'),
}
EPHEMERIS_TIME_SPANS = {
    'sun_down_time': ('sun set', 'sun rise'),
    'night_time': ('night start', 'night end'),
    'dark_time': ('dark start', 'dark end'),
}

class Schedule(log.Log):

    _INSTANCES = {}

    HTML_ROW_GROUPS = OrderedDict(
        date=['date'],
        support=['support', 'date'],
    )
    HTML_COLUMNS = OrderedDict(
        date=['-n_night', '-night_no'],
        support=['support', 'date', 'tac', 'pi', 'observer', 'n_night'],
    )
    HTML_SORT_KEYS = OrderedDict(
        support=['support'],
    )
    LOG_TYPES = OrderedDict(
        schedule=['date'],
        support=['support']
    )

    def shifts(self):

        rows = []

        support = [s for s in self['support'] if s]
        tios = np.unique(np.hstack([tios.split(', ') for tios in support]))
        
        for tio in tios:
            on_duty = [tio in support for support in self['support']]
            duty = self[on_duty]
            date_ranges = np.array(log.join_dates(duty['date']).split(', '))
            for row in duty:
                date = row['date']
                dates = date_ranges[[d[:10] <= date < d[12:] for d in date_ranges]]
                rows.append((tio, dates[0], row[1], row[2], row[4], row[-1])) 
           
        names = ('support', 'date', 'tac', 'pi', 'observer', 'n_night') 

        support = type(self)(rows=rows, names=names, meta=self.meta)

        return support

    @classmethod
    def read(cls, *, telescope: str, period: int, rootdir='.', 
                wwwdir='/data/www/twoptwo.com'):
        
        key = (telescope, period)
    
        site, telescopes = parse_telescope(telescope)
        telescope = telescopes[0]

        if schedule := cls._INSTANCES.get(key, None):
            return schedule

        filename = path.filename(telescope, period=period,
                log_type='schedule', ext='xlsx', rootdir=rootdir)
       
        schedule = table_from_excel(filename, header=0, cls=cls) 

        # retrieve the date part only
        schedule['date'] = [d[0:10] for d in schedule['date']]

        # retrieve all schedules
        ephems = [night_ephemeris(telescope, night) 
                                for night in schedule['date']]


        # add ephemeris columns
        for name, (desc, dtype) in EPHEMERIS_COLUMNS.items():
            col = MaskedColumn(name=name, description=desc, dtype=dtype,
                    length=len(schedule), mask=True)
            schedule.add_column(col)
        schedule['fli'].format = '.0%'
       
        # add number of nights 
        n_night = np.ones((len(schedule),), dtype=int)
        n_night = Column(n_night, name='n_night')
        schedule.add_column(n_night)

        # check if more than 1 dark/night/... span in any night
        for name, (start, end) in EPHEMERIS_TIME_SPANS.items():
            
            nspan = max(len(e[name]) for e in ephems)
            # print(name, nspan)
 
            for i in range(2, nspan + 1):
                for bound in [start, end]: 
                    col = MaskedColumn(schedule[name], name=f'{bound} {i}')
                    schedule.add_column(col)

        for row, ephem in zip(schedule, ephems):

            night = row['date']

            for name, (start, end) in EPHEMERIS_TIME_SPANS.items():
                
                time = ephem[name]
                if len(time):
                    row[start] = time[0][0][11:16] # hh:mm only
                    row[end] = time[0][1][11:16]                

                for i in range(2, len(time) + 1):
                    row[f"{start} {i}"] = time[i][0][11:16]
                    row[f"{end} {i}"] = time[i][1][11:16]

            row['fli'] = ephem['moon_illumination']

        cls._INSTANCES[key] = schedule

        schedule.meta['period'] = period
        schedule.meta['telescope'] = telescope
        schedule.meta['site'] = site
        schedule.meta['rootdir'] = rootdir
        schedule.meta['wwwdir'] = wwwdir
    
        return schedule

