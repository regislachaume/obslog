from ..utils.date import night_to_date_range, add_seconds, date_to_night, \
                         total_seconds, total_hours
from ..utils.ephemeris import night_ephemeris 
from .date import night_to_period
from . import path
from .tapquery import NightQuery
from .allocation import Allocation


from pyvo.dal import tap
from astropy.coordinates import EarthLocation
from ..utils.table import Table
from astropy.table import Column
from bs4 import Comment as BSComment, BeautifulSoup

import numpy as np
import shutil
import os
import json
import re


def BS(arg):
    return BeautifulSoup(arg, features='lxml')


def rangify(x):
    a, b = min(x), max(x)
    if a == b:
        return a
    return f"{a} .. {b}" 

def join(x):
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
    obj, ins = log['object'], log['instrument']
    return log[~obj.mask & ~ins.mask & (obj != '') & (ins != '')]

def keep_all(log):
    return log

class Log(Table):

    HTML_CAPTIONS = {
        'pid': 'summary of programme execution',
        'object': 'summary of target observations',
        'ob_start': 'detailed log',
        'night': 'summary of nights',
    }
    HTML_ROW_FILTRES = {
        'pid': keep_external,
        'object': keep_target,
        'ob_start': keep_external,
        'night': keep_external,
    }

    def fix_pids(self):
            
        if not (period := self.meta.get('period', None)):
            return
        
        telescope = self.meta['telescope']
        allocation = Allocation.read(telescope=telescope, period=period)

        if 'pid' not in self.colnames:
            index = np.argwhere(['used_pid' == n for n in self.colnames])[0,0]
            self.add_column(self['used_pid'], name='nom_pid', index=index)
        
        for i, log_entry in enumerate(self):
            
            used_pid = log_entry['used_pid']
            prog = allocation.lookup(log_entry)
            pid, pi = prog['PID', 'PI']

            log_entry['pid'] = pid
            log_entry['pi'] = pi

    def save(self, log_type='log', overwrite=False, format='csv'):

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

    def publish(self, log_type='log'):

        source = self.get_filename(log_type, ext='shtml')
        dest = self.get_filename(log_type, ext='shtml', www=True, makedirs=True)

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

        log_type = htmldict.get('log_type', 'log')

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
        
    def _as_bs_helper(self, *, table_type, htmldict={}, **kwargs):

        # Scalar call for detail.  

        telescope = self.meta['telescope']
        if night := self.meta.get('night', None):
            what = f'night of {night} at {telescope}'
        elif period := self.meta.get('period', None):
            what = f'period {period} at {telescope}'
        else:
            what = f'at {telescope}'
       
        kept_keys = self.HTML_COLUMNS[table_type]
        group_keys = self.HTML_ROW_GROUPS[table_type]
        sort_keys = self.HTML_SORT_KEYS[table_type]
        filter = self.HTML_ROW_FILTRES[table_type] 
        subtitle = self.HTML_CAPTIONS[table_type]

        units = [c.unit.name if c.unit else '' for c in self.itercols()]

        summary = filter(self).summary(group_keys)

        if sort_keys:
            summary = summary.group_by(sort_keys)

        summary = summary[kept_keys]

        # Shorten some keys / values for visual compactness
 
        for key in ['ob_start', 'ob_end']:
            if key in summary.colnames:
                summary[key] = [s[11:16] for s in summary[key]]

        for key in summary.colnames:
            if '_hours' in key:
                summary[key].name = key[:-6] + '_t'
            elif 'tel_ambi_' in key:
                summary[key].name = key[9:]
            elif 'tel_' in key:
                summary[key].name = key[4:]

        caption = f"{subtitle} for {what}"

        tel = telescope.split('-')[-1]

        log_type = htmldict.get('log_type', 'log')
        log_type = log_type[0].upper() + log_type[1:]

        doc_title = f"{log_type} for {what}"
        htmldict=dict(
            **htmldict,
            caption=caption,
            title=doc_title,
            h1=doc_title,
            h2=subtitle,
            table_class='horizontal',
            cssfiles=[f'/{tel}/navbar.css', 
                      f'/{tel}/twoptwo.css']
        )

        summary.__class__ = Table # want to keep groups!
        soup = summary.as_beautiful_soup(htmldict=htmldict, **kwargs)

        navbar = f'#include virtual="/{tel}/navbar.shtml"'
        soup.body.insert(0, BSComment(navbar))

        # If above night level, place a link to lower level
        if sort_keys and sort_keys[0] == 'night' and kept_keys[0] == 'night':
            for group in soup.table.find_all('tbody'):
                tr1 = group.tr
                text = tr1.td.get_text()
                link = BS(f'<td><a href="./{text}">{text}</a></td>').td
                tr1.td.replace_with(link)

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

            descriptions.append(desc)
            names.append(name)

        # averaging / merging depending on column

        rows = []
        for group in grouped.groups:
            
            row = []
            for col in group.columns.values():
                
                name, values = col.name, col.data
     
                if name[-6:] == '_start':
                    value = min(values)
                elif name[-4:] == '_end':
                    value = max(values)
                elif name[-6:] == '_hours' or name in ['exposure']:
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
                    value = join(values)
                elif col.dtype.char == '?':
                    value = values[0]
                    if any(values != value):
                        text = f"cannot average booleans in column {name}"
                        raise RuntimeError(text)
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

