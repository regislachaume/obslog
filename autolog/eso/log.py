from ..utils.date import night_to_date_range, add_seconds, date_to_night, \
                         total_seconds, total_hours
from ..utils.ephemeris import night_ephemeris 
from .date import night_to_period
from . import path
from .tapquery import NightQuery
from .allocation import Allocation
import datetime

from astropy.coordinates import EarthLocation
from ..utils.table import Table
from astropy.table import Column, MaskedColumn
from bs4 import Comment as BSComment, BeautifulSoup

import numpy as np
import shutil
import os
import json
import re

def linkify_pid(soup, *, link_type='archive'):
        
    pid_re = '[ 012][0-9]{2,3}\.[A-Z]-[0-9]{4}\([A-Z]\)'
    archive = 'http://archive.eso.org/wdb/wdb/eso/sched_rep_arc'
            
    for colnum, th in enumerate(soup.table.tr.find_all('th')):

        if th.get_text() in ['pid', 'used_pid']:
            break
    
    else:
        return
            
    for body in soup.table.find_all('tbody'):
        for tr in body.find_all('tr'):

            td = tr.find_all('td')[colnum]
            
            pid = td.get_text()
            if re.match(pid_re, pid):

                if link_type == 'archive':
                    url = f'{archive}/query?progid={pid}'
                elif link_type == 'local':
                    url = f'./{pid}'
                else:
                    return # nothing to do
        
                link = BS(f'<td><a href="{url}">{pid}</a></td>').td
                td.replace_with(link)

def linkify_night(soup, *, link_type='local'):

    for colnum, th in enumerate(soup.table.tr.find_all('th')):

        if th.get_text() in ['night', 'start date']:
            break
      
    else:
        return

    for body in soup.table.find_all('tbody'):
        for tr in body.find_all('tr'):

            td = tr.find_all('td')[colnum]
            night = td.get_text()

            if link_type == 'local':
                url = f'./{night}'
            else:
                return # nothing to do

            link = BS(f'<td><a href="{url}">{night}</a></td>').td
            td.replace_with(link)
           

def BS(arg):
    return BeautifulSoup(arg, features='lxml')

def rangify(x):
    a, b = min(x), max(x)
    if a == b:
        return a
    return f"{a} .. {b}" 

def join_dates(dates, upper_limit='open'):
   
    try: 
        dates = [datetime.date.fromisoformat(d) for d in dates]

        discont = [(dates[i + 1] - dates[i]).days > 1 
                                for i in range(len(dates) - 1)]
        discont = np.argwhere(discont)[:,0] + 1

        min_date = np.hstack([0, discont])      
        max_date = np.hstack([discont - 1, len(dates) - 1]) 
        
        intervals = []
            
        for mn, mx in zip(min_date, max_date):
            d1 = dates[mn]
            d2 = dates[mx]
            if upper_limit == 'open':
                d2 += datetime.timedelta(1)
            if d2 > d1:
                intervals.append(f"{d1}..{d2}")
            else:
                intervals.append(f"{d1}")
    except:
        intervals = np.unique(dates)

    return ', '.join(intervals)

def join_unique(x):
    
    x = [str(i) for i in np.unique(x)]
    
    for val in ['None', 'NONE']:
        if val in x:
            x.remove(val)

        
    return ' '.join(x)

def keep_track(log):
    return log[~log['slew'] & (log['sun_down_hours'] > 0)]

def keep_external(log):
    return log[~log['internal'] & (log['sun_down_hours'] > 0)]

def keep_target(log):
    targ, ins = log['target'], log['instrument']
    return log[~targ.mask & (targ != '') & (ins != '')]

def keep_all(log):
    return log

class Log(Table):

    HTML_CAPTIONS = {
        'pid': 'summary of programme execution',
        'object': 'list of observed targets',
        'ob_start': 'detailed observing log',
        'night': 'observed programmes in each night',
        'dp_cat': 'summary of telescope use',
        'date': 'schedule',
        'support': 'shifts',
    }
    HTML_TITLES = {
        'target': 'list of targets',
        'log': 'observing logs',
    }
    HTML_ROW_FILTRES = {
        'pid': keep_external,
        'object': keep_target,
        'ob_start': keep_external,
        'night': keep_external,
        'dp_cat': keep_external,
        'date': keep_all,
        'support': keep_all,
    }
    HTML_PROGRESS = { }

    def fix_pids(self):
           
        # print('fix_pids') 
        if not (period := self.meta.get('period', None)):
            return

        if not 'used_pid' in self.colnames:
            return

        # print('will fix pids')
        
        telescope = self.meta['telescope']
        allocation = Allocation.read(telescope=telescope, period=period)

        if 'pid' not in self.colnames:
            index = np.argwhere(['used_pid' == n for n in self.colnames])[0,0]
            self.add_column(self['used_pid'], name='pid', index=index)

        if 'tac' not in self.colnames:
            tac = np.full(len(self), '', dtype='<U12')
            tac = np.ma.masked_array(tac, mask=True)
            self.add_column(tac, name='tac', index=0)
        
        for i, log_entry in enumerate(self):
           
            used_pid = log_entry['used_pid']
            prog = allocation.lookup(log_entry)
            pid, pi, tac, ins = prog['PID', 'PI', 'TAC', 'Instrument']

            log_entry['instrument'] = ins
            log_entry['pid'] = pid
            log_entry['pi'] = pi
            log_entry['tac'] = tac
            
            #if used_pid == '0107.A-9033(A)':
            #    print(used_pid, prog, pid, log_entry['pid'], pi) 
           
    def default_log_type(self):

        return list(self.LOG_TYPES.keys())[0]

    def save(self, log_type=None, overwrite=False, format='csv'):

        if  log_type is None:
            log_type = self.default_log_type()

        if format == 'csv':
            ext = 'csv'
            format = 'ascii.ecsv'
            kwargs = {}
        elif format == 'html':
            ext = 'shtml'
            format = 'ascii.html'
            kwargs = dict(htmldict=dict(log_type=log_type))

        filename = self.get_filename(log_type, ext=ext, makedirs=True)

        self.write(filename, overwrite=overwrite, format=format, **kwargs)

    def publish(self, log_type=None):

        if  log_type is None:
            log_type = self.default_log_type()
        
        source = self.get_filename(log_type, ext='shtml')
        dest = self.get_filename(log_type, ext='shtml', www=True, makedirs=True)
        print(f'publish: {source} {dest}')
        shutil.copy2(source, dest)

    def get_filename(self, log_type, makedirs=False, ext='csv', www=False):

        period = self.meta.get('period', None)
        night = self.meta.get('night', None)
        telescope = self.meta['telescope'] 
        if www:
            rootdir = self.meta['wwwdir']
        else:
            rootdir = self.meta['rootdir']
        
        return path.filename(telescope, log_type=log_type, rootdir=rootdir, 
            makedirs=makedirs, period=period, night=night, ext=ext)
    
    def as_beautiful_soup(self, htmldict={}, **kwargs):

        deflog = list(self.LOG_TYPES.keys())[0]
        log_type = htmldict.get('log_type', deflog)

        table_types = [key for key in self.LOG_TYPES[log_type]]
        soup = self._as_bs_helper(table_type=table_types[0], 
                                        htmldict=htmldict, **kwargs)

        for table_type in table_types[1:]:
            table = self._as_bs_helper(table_type=table_type,
                                        htmldict=htmldict, **kwargs)
            soup.body.append(table.h2)
            soup.body.append(table.table)

        if len(table_types) == 1:
            soup.h2.extract()

        return soup

    def process_kept_keys(self, table_type):

        all = self.colnames
        names = self.HTML_COLUMNS.get(table_type, None).copy()

        if names is None:
            
            kept = all

        elif names[0][0] == '-':
            
            names = [n[1:] for n in names]
            kept = [a for a in all if a not in names]

        else:

            kept = names

        return names

    def get_kept_keys(self, table_type):
        
        all_keys = self.colnames
        kept_keys = self.HTML_COLUMNS.get(table_type, all_keys).copy()

        if kept_keys[0][0] == '-':
            removed_keys = [k.removeprefix('-') for k in kept_keys]
            kept_keys = all_keys
            for key in removed_keys:
                if key in kept_keys:
                    kept_keys.remove(key.strip('-'))

        return kept_keys

    def _as_bs_helper(self, *, table_type, htmldict={}, **kwargs):

        # Scalar call for detail.  

        telescope = self.meta['telescope']
        if night := self.meta.get('night', None):
            what = f'night of {night} at {telescope}'
        elif period := self.meta.get('period', None):
            what = f'period {period} at {telescope}'
        else:
            what = f'at {telescope}'
       
        kept_keys = self.get_kept_keys(table_type)
        group_keys = self.HTML_ROW_GROUPS[table_type]
        sort_keys = self.HTML_SORT_KEYS.get(table_type, [])
        filter = self.HTML_ROW_FILTRES[table_type] 
        subtitle = self.HTML_CAPTIONS[table_type]
        progress = self.HTML_PROGRESS.get(table_type, None)

        units = [c.unit.name if c.unit else '' for c in self.itercols()]

        summary = filter(self)
        summary = summary.summary(group_keys)
            
        # Report progress as a function of total available time

        if progress == 'time':
            for name in ['night_hours', 'twilight_hours']:
                fname = name[:-6] + '_fraction'
                fval = summary[name] / self.meta['ephemeris'][name]
                col = Column(fval, name=fname, format='.1%', unit=None)
                summary.add_column(col)
                kept_keys.append(fname)

        # report progress as a function of allocated time

        if progress == 'allocation' and (p := self.meta.get('period', None)):
        
            telescope = self.meta['telescope']
            allocation = Allocation.read(telescope=telescope, period=p)

            # add unobserved programmes so that their null completion is
            # reported ;-)

            for line in allocation[allocation['Link'] != 'omit']:
                tac, pid, pi, ins = line['TAC', 'PID', 'PI', 'Instrument']
                if pid not in summary['pid']:
                    empty_row = np.zeros_like(summary[-1])
                    empty_row['pid'] = pid
                    empty_row['tac'] = tac
                    empty_row['pi'] = pi
                    empty_row['instrument'] = ins
                    summary.add_row(empty_row.tolist())
        
            # add execution %.  Tricky part: GROND with PID ~ 9099 has 15% 
            # of night time so don't count non-night observations.

            night_hours = self.meta['ephemeris']['night_hours']
            allocated = np.array([allocation.allocated_hours(pid, night_hours)
                    for pid in summary['pid']])
            allocated = np.ma.masked_array(allocated, mask=allocated==0)
            
            col = MaskedColumn(allocated, name='allocated', format='.0f')
            col.unit = 'h'
            summary.add_column(col) 
 
            executed = summary['sun_down_hours'].data.copy()
            grond_pid = f"0{p}.A-9099(A)"
            lineno = np.argwhere([grond_pid == pid for pid in summary['pid']])
            if len(lineno):
                lineno = lineno[0][0]
                executed[lineno] = summary['night_hours'][lineno]

            progress = executed / allocated

            col = Column(executed, name='executed', unit='h')
            summary.add_column(col)
    
            col = MaskedColumn(progress, name='progress', format='.0%')
            summary.add_column(col)
            
            kept_keys +=  ['allocated', 'progress']
        
        # add a subtotal line in each group

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

        # Group rows and keep only the most interesting columns
                        
        if sort_keys:
            summary.sort(kept_keys)
            summary = summary.group_by(sort_keys)

        summary = summary[kept_keys]

        today = datetime.date.today().strftime('%Y-%m-%d')
        caption = f"{subtitle} for {what} (updated on {today})"

        tel = telescope.split('-')[-1]

        log_type = htmldict.get('log_type', 'log')
        Log_type = log_type[0].upper() + log_type[1:]

        doc_title = self.HTML_TITLES.get(log_type, Log_type)
        doc_title = f"{doc_title} for {what}"

        htmldict=dict(
            **htmldict,
            caption=caption,
            title=doc_title,
            h1=doc_title,
            h2=subtitle,
            table_class='horizontal',
            cssfiles=[f'/{tel}/style/navbar.css', 
                      f'/{tel}/style/twoptwo.css']
        )

        summary.__class__ = Table # want to keep groups!
        soup = summary.as_beautiful_soup(htmldict=htmldict, **kwargs)

        navbar = f'#include virtual="/{tel}/style/navbar.shtml"'
        soup.body.insert(0, BSComment(navbar))

        # Some links to details
        if table_type == 'night':
            linkify_night(soup, link_type='local')
        elif table_type == 'start date':
            linkify_night(soup, link_type='archive')

        elif table_type == 'pid':
            linkify_pid(soup, link_type='archive')
 
        return soup

    def summary(self, keys=['pid']):

        grouped = self.group_by(keys)

        descriptions = []
        names = []

        # sequence number -> total number of merged 
        # OBs/templates/exposures

        for col in grouped.columns.values():
            
            name, desc = col.name, col.description
            if desc:
                desc = re.sub('The ', '', desc)  

            if '_no' in name:
                desc = re.sub(' sequence.*', '', col.description)
                desc = f"Number of {desc}s"
                name = f"n_{name[:-3]}"
                if name == 'n_ob':
                    desc = 'total number of observing blocks'
                elif name == 'n_exp':
                    desc = 'total number of exposures'
                elif name == 'n_tpl':
                    desc = 'total number of observing templates'

            descriptions.append(desc)
            names.append(name)

        # averaging / merging depending on column

        def reduce(fun, val):
            if np.ma.is_masked(val):
                return np.ma.masked
            return fun(val)

        rows = []
        for group in grouped.groups:
            
            row = []
            for col in group.columns.values():
                
                name, values = col.name, col.data
    
                if name == 'date':
                    value = join_dates(values, upper_limit='open')
                elif name[-6:] in [' start', '_start', 'sun_set']:
                    value = reduce(min, values)
                elif name[-4:] in [' end', '_end', 'sun_rise']:
                    value = reduce(max, values)
                elif col.unit and col.unit.physical_type == 'time':
                    value = sum(values)
                elif name == 'exp_no':
                    value = len(np.unique(group['exp_start']))
                elif name == 'tpl_no':
                    value = len(np.unique(group['tpl_start']))
                elif name == 'ob_no':
                    value = len(np.unique(group['ob_start']))
                elif name[0:2] == 'n_': # it's an average already
                    value = sum(values)
                elif col.dtype.char == 'U':
                    value = join_unique(values)
                elif col.dtype.char == '?':
                    value = values[0]
                    if any(values != value):
                        value = np.mean(values)
                else:
                    value = np.mean(values)
                
                row.append(value)

            rows.append(row)

        cls = type(self)
        log = cls(rows=rows, names=names, descriptions=descriptions,
                meta=self.meta)

        for name in log.colnames:
            if name in self.colnames:
                log[name].format = self[name].format
                log[name].unit = self[name].unit

        return log

