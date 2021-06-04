from ..utils.date import night_to_date_range, add_seconds, date_to_night, \
                         total_seconds, total_hours
from ..utils.ephemeris import night_ephemeris 
from .date import night_to_period
from . import path
from .tapquery import NightQuery

from pyvo.dal import tap
from astropy.coordinates import EarthLocation
from ..utils.table import Table
from astropy.table import Column
from bs4 import Comment as BSComment

import numpy as np
import shutil
import os
import json
import re

def rangify(x):
    a, b = min(x), max(x)
    if a == b:
        return a
    return f"{a} .. {b}" 

def join(x):
    x = np.unique(x).tolist()
    for val in [None, 'NONE']:
        if val in x:
            x.remove(val)
    return ' '.join(x)

class Log(Table):

    def summary(self, keys=['prog_id']):

        grouped = self.group_by(keys)

        descriptions = []
        names = []
        units = [c.unit for c in grouped.columns.values()]
        formats = [c.format for c in grouped.columns.values()]

        # sequence number -> total number of merged OBs/templates/exposures

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
                elif name[-3:] == '_no':
                    value = len(values)
                elif name[0:2] == 'n_': # it's an average already
                    value = sum(values)
                elif name in ['night', 'period']:
                    value = rangify(values)
                elif col.dtype.char == 'U':
                    value = join(values)
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

        return log

