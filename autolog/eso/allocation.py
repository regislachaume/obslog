from autolog.eso import path
from autolog.utils.io import table_from_excel
from autolog.eso.date import period_start, period_end

from datetime import date as Date
import os
import re
import numpy as np
import codecs
import shutil

from autolog.utils.table import Table, BS
from bs4 import Comment as BSComment

class Allocation(Table):
        
    ESO_SCHEDULE_URL = 'http://archive.eso.org/wdb/wdb/eso/sched_rep_arc/query'

    _INSTANCES = {}

    @classmethod
    def read(cls, *, telescope, period, rootdir='.',
                                wwwdir='/data/www/twoptwo.com'): 
        
        key = (telescope, period)
        if alloc := cls._INSTANCES.get(key, None):
            return alloc

        filename = path.filename(telescope, period=period,
                log_type='program', ext='xls', rootdir=rootdir)

        alloc = table_from_excel(filename, cls=cls) 
        fixes = table_from_excel(filename, sheetnum=1)

        alloc.meta = dict(
            rootdir = rootdir,
            wwwdir = wwwdir,
            filename = filename,
            telescope = telescope,
            period = period,
            pid_fixes = fixes,
            cross_reference = {pid: pid for pid in alloc['PID']}
        )
 
        for row in alloc:
            pid = row['PID']
            for id in alloc['Identifiers']:
                alloc.meta['cross_reference'][id] = pid

        for name in ['Airmass', 'Seeing', 'Hours']:
            alloc[name].format = '.1f'

        cls._INSTANCES[key] = alloc
 
        return alloc

    def lookup(self, log_entry):

        pid, object, ob_name = log_entry['used_pid', 'object', 'ob_name']
        instrument = log_entry['instrument']
        date = log_entry['ob_start']
        
        # Look if it has been observed with a wrong PID.  The fixes table is
        # manually maintained by a 2.2m SA for transient/target-dependent
        # issues.
               
        for fix in self.meta['pid_fixes']:
            
            if fix['Used PID'] in pid:
                
                obj, name = fix['Object', 'OB name']
                d1, d2 = fix['Start date', 'End date']
                
                if (obj != '' and not re.search(obj, object) or
                    name != '' and not re.search(name, ob_name) or
                    d1 != '' and date < d1 or
                    d2 != '' and date > d2):
                    continue

                pid = fix['Nominal PID']
                break

        pid =  self.meta['cross_reference'].get(pid, pid)

        indices = self['PID'] == pid
        if any(indices):
            return self[indices].copy()[0]

        return self._unidentified(pid=pid, instrument=instrument)

    def new_program(self, *, pid, title, instrument='', pi='', tac=''):

        new = self[-1:].copy()[0]
        
        new['PID'] = pid
        new['Title'] = title
        new['TAC'] = tac
        new['PI'] = pi 
        new['Instrument'] = instrument
        new['Identifiers'] = ''
        new['Link'] = 'no'

        return new

    def _unidentified(self, pid, instrument):

        return self.new_program(pid=pid, instrument=instrument, 
                    title='unidentified program')

    @classmethod
    def archive_link(cls, pid):
                
        link = '{}?progid={}'.format(cls.ESO_SCHEDULE_URL, pid)

        return link
    
    @classmethod
    def local_link(cls, pid):

        pid = ''.join(re.split('[-().]', pid)[2:3])
        link = f"./{pid}.pdf"

        return link

    def save(self, format='html', omit=True):
        
        if omit:
            alloc = alloc[alloc['Link'] == 'omit']
        else:
            alloc = self
        
        if format == 'html':
            ext = 'shtml'
            format = 'ascii.html'
            alloc = self.group_by('TAC')
        else:
            ext = 'csv'
            format = 'ascii.ecsv'

        filename = self.get_filename(ext=ext, makedirs=True)
        
        self.write(filename, format=format)

    def as_beautiful_soup(self, caption=None, exclude_names=['Identifiers']):
      
        period = self.meta['period']
        telescope = self.meta['telescope']
        doc_title = f"{telescope} time allocation for period {period}"
 
        today = Date.today().isoformat()
        start = period_start(period, format='iso')
        end = period_end(period, format='iso')

        if not caption:
            caption = f"{doc_title} ({start} to {end}). Last modified {today}."

        htmldict=dict(
            title=doc_title,
            h1=doc_title,
            caption=caption,
            table_class='horizontal',
            cssfiles=['/2.2m/navbar.css', '/2.2m/twoptwo.css']
        )

        soup = super().as_beautiful_soup(exclude_names=exclude_names, 
                                htmldict=htmldict)

        # locate columns
        th = soup.tr.find_all('th')
        ipid = np.argwhere(['PID' in t for t in th])[0,0]
        ititle = np.argwhere(['Title' in t for t in th])[0,0]
        ilink = np.argwhere(['Link' in t for t in th])[0,0]
        icritical = np.argwhere(['Time-critical' in t for t in th])[0,0]

        # remove unused col headers
        th[ilink].extract()
        th[icritical].extract()

        for tr in soup.find_all('tr')[1:]:

            td = tr.find_all('td')

            # zeros are for unspecified values

            for t in td:
                if len(t.contents) and t.contents[0] in ['0', '0.0', '0.00']:
                    t.contents[0] = ''

            pid = td[ipid]
            link = td[ilink]
            critical = td[icritical]
            title = td[ititle]
            
            id = pid.contents[0]
            url = link.contents[0].strip() if link.contents else ''
 
            # replace programme title with linked programme title
            
            if url and url not in ['omit', 'no']:
                if url[0:7] not in ['http://', 'https:/']:
                    url = f"proposals/{url}"
                td = BS(f'<td><a href="{url}">{title.contents[0]}</a><td>').td
                title.replace_with(td)
               
            # put link on pid 

            if '(' in id: 
                url = self.archive_link(id)
                td = BS(f'<td><a href="{url}">{id}</a><td>').td
                pid.replace_with(td)
            
            if 'yes' in critical:
                tr['class'] = 'timecritical' 

            critical.extract()
            link.extract()
        
        navbar = '#include virtual="/2.2m/navbar.shtml"'
        soup.body.insert(0, BSComment(navbar))
        
        return soup

    def get_filename(self, makedirs=False, ext='xls', www=False):

        period = self.meta.get('period', None)
        night = self.meta.get('night', None)
        telescope = self.meta['telescope']
        if www:
            rootdir = self.meta['wwwdir']
        else:
            rootdir = self.meta['rootdir']

        return path.filename(telescope, log_type='program', period=period, 
            rootdir=rootdir, makedirs=makedirs, ext=ext)
                    
    def publish(self):

        source = self.get_filename(ext='shtml')
        dest = self.get_filename(ext='shtml', www=True, makedirs=True)

        source_dir = os.path.join(os.path.dirname(source), 'proposals')
        dest_dir = os.path.join(os.path.dirname(dest), 'proposals')

        shutil.copy2(source, dest)
        try:
            shutil.copytree(source_dir, dest_dir, dirs_exist_ok=True)
        except:
            pass

