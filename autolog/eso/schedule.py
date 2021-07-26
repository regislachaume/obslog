from autolog.utils.table import Table
from autolog.utils.io import table_from_excel
from autolog.utils.ephemeris import night_ephemeris
from autolog.eso import path
from autolog.eso import log 
from autolog.utils.telescope import parse_telescope

import numpy as np
import copy
import re
from astropy.table import MaskedColumn
        
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
        'date'=['date'],
        'support'=['support', 'tac', 'pi'],
    )
    HTML_COLUMNS = OrderedDict(
        'date'=['-night_no'],
        'support'=['support', 'date', 'tac', 'pi', 'observer'],
    )
    HTML_SORT_KEYS = OrderedDict(
        'support'=['support'],
    )
    LOG_TYPES = OrderedDict(
        'schedule'=['date'],
        'support'=['support']
    )

    @classmethod
    def read(cls, *, telescope, period, rootdir='.', 
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
        n_night = np.ones((len(night),), dtype=int)
        n_night = Column(n_night, name='n_night')
        schedule.add_column(n_night)

        # parse supports, one row for each
        for i, row in reversed(enumerate(schedule)):
            supports = row['supports']
            if ',' not in row['supports']:
                continue
            supports = re.split('\s*,\s*', supports)
            row['supports'] = supports[0]
            for s in supports[1:]:
                new_row = copy.copy(row)  
                new_row[supports] = s
                schedule.insert_row(i, new_row)

        # check if more than 1 dark/night/... span in any night
        for name, (start, end) in EPHEMERIS_TIME_SPANS.items():
            
            nspan = max(len(e[name]) for e in ephems)
            print(name, nspan)
 
            for i in range(2, nspan + 1):
                for bound in [start, end]: 
                    col = MaskedColumn(schedule[name], name=f'{bound} {i}')
                    schedule.add_column(col)

        for row, ephem in zip(schedule, ephems):

            night = row['date']

            for name, (start, end) in EPHEMERIS_TIME_SPANS.items():
                
                time = ephem[name]
                if len(time):
                    row[start] = time[0][0]
                    row[end] = time[0][1]                

                for i in range(2, len(time) + 1):
                    row[f"{start} {i}"] = time[i][0]
                    row[f"{end} {i}"] = time[i][1]

            row['fli'] = ephem['moon_illumination']

        cls._INSTANCES[key] = schedule

        schedule.meta['period'] = period
        schedule.meta['telescope'] = telescope
        schedule.meta['site'] = site
    
        return schedule

    def save(self, format='csv'):

        filename = self.get_filename('schedule', ext=ext, makedirs=True)

        if format == 'csv':
            ext = 'csv'
            format = 'ascii.ecsv'
        elif format == 'html':
            ext = 'shtml'
            format = 'ascii.html'

        filename = self.get_filename('schedule', ext=ext, makedirs=True)

        self.write(filename, overwrite=overwrite, format=format)

    def publish(self):

        source = self.get_filename('schedule', ext='shtml')
        dest = self.get_filename('schedule', ext='shtml', www=True, makedirs=True)

        shutil.copy2(source, dest)

    def as_beautiful_soup(self, htmldict={}):

        tel, per = self.meta['telescope'], self.meta['period']
        start, end = self['date'][[0, -1]]
        htmldict=dict(
            **htmldict,
            caption='Schedule for ESO period P{per} (from {start} to {end}) at {tel}',
            title=f'Schedule for ESO period P{per} at {tel}',
            h1=f'Schedule for ESO period P{per} at {tel}',
            table_class='horizontal',
            cssfiles=[f'/{tel}/style/navbar.css',
                      f'/{tel}/style/twoptwo.css']
        )
        
        summary.__class__ = Table # want to keep groups!
        soup = summary.as_beautiful_soup(htmldict=htmldict, **kwargs)

        # flag lines by tac       
        for tr in soup.find_all('tr'):
            tac = tr.find_all('td')[1].contents[0]
            tr.class_[tac.lower()]

        #
 
        return soup

