from . import path
from ..utils.io import table_from_excel
from .date import period_start, period_end

from datetime import date as Date
import os
import re
import numpy as np
import codecs

from ..utils.table import Table, BS
from bs4 import Comment as BSComment

class Allocation(Table):
        
    ESO_SCHEDULE_URL = 'http://archive.eso.org/wdb/wdb/eso/sched_rep_arc/query'
    SITE_URL = 'http://www.astro.puc.cl/2.2m/'    
    SITE_DIR = 'lachaume@black:~/2.2m'

    @classmethod
    def read(cls, *, telescope, period, rootdir='.', honour_omit=True):
        
        filename = path.filename(telescope, name='allocation', ext='xls', 
                rootdir=rootdir, period=period)

        alloc = table_from_excel(filename, cls=cls) 
        fixes = table_from_excel(filename, sheetnum=1)

        if honour_omit:
            alloc = alloc[alloc['Link'] != 'omit']
        
        alloc.meta = dict(
            rootdir = rootdir,
            filename = filename,
            html = path.filename(telescope, name='allocation', ext='html',
                rootdir=rootdir, period=period),
            telescope = telescope,
            period = period,
            url = "{cls.SITE_URL}/schedule/P{period}/P{period}.xls",
            fixes = fixes,
            cross_reference = {pid: pid for pid in alloc['PID']}
        )
 
        for row in alloc:
            pid = row['PID']
            for id in alloc['Identifiers']:
                alloc.meta['cross_reference'][id] = pid

        for name in ['Airmass', 'Seeing', 'Hours']:
            alloc[name].format = '.1f'
 
        return alloc 

    def lookup(self, pid, target=None, date=None, ins=None):

        # Look if it has been observed with a wrong PID.
        # The fixes table is manually maintained by a 2.2m SA for
        # transient/target-dependent issues.
        
        if target is not None or date is not None:
            # print(self.corr)
            
            for line in self.meta['fixes']:
                
                if line['PID'] in pid:
                    
                    t = line['Target']
                    d1, d2 = line['Start'], line['End']
                    
                    if (t != '' and not re.search(t, target) or
                       d1 != '' and date < d1 or
                       d2 != '' and date > d2):
                        continue
                    pid = line['Nominal PID']
                    break

        pid =  self.meta['cross_reference'].get(pid, pid)

        indices = self['PID'] == pid
        if any(indices):
            return self[indices][0]

        return self.unidentified_programme()

    def unidentified_programme(self):

        unid = self[-1].copy()
        unid['TAC'] = 'N/A'
        unid['PID'] = pid
        unid['Title'] = 'Unidentified programme'
        unid['Investigator'] = 'N/A'
        unid['Name'] = ''
        unid['Instrument'] = ins
        unid['Identifiers'] = ''
        unid['Link'] = 'no'

        return unid

    @classmethod
    def archive_link(cls, pid):
                
        link = '{}?progid={}'.format(cls.ESO_SCHEDULE_URL, pid)

        return link
    
    @classmethod
    def local_link(cls, pid):

        pid = ''.join(re.split('[-().]', pid)[2:3])
        link = f"./{pid}.pdf"

        return link

    def save_as_html(self, overwrite=False):

        filename = self.meta['html']
        self.write(filename, overwrite=overwrite, format='ascii.html')

    def as_beautiful_soup(self, caption=None, exclude_names=['Identifiers'],
            standalone=False):
      
        period = self.meta['period']
        telescope = self.meta['telescope']
        doc_title = f"{telescope} time allocation for period {period}"
 
        today = Date.today().isoformat()
        start = period_start(period, format='iso')
        end = period_end(period, format='iso')

        if not caption:
            caption = f"{doc_title} ({start} to {end}). Last modified {today}."

        htmldict=dict(
            table_class='horizontal',
            cssfiles=['../../navbar.css', '../../twoptwo.css']
        )

        soup = super().as_beautiful_soup(caption=caption, 
                    standalone=standalone,
                    exclude_names=exclude_names, htmldict=htmldict)

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
            
            # replace programme title with linked programme title
            
            if 'no' not in link and 'omit' not in link:
                if 'yes' in link:
                    url = self.local_link(id)
                else: 
                    url = link.contents[0]
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
        
        if not standalone:
            
            dtitle = BS(f'<title>{doc_title}</title>').title
            soup.head.append(dtitle)
          
            h1 = BS(f'<h1>{doc_title}</h1>').h1
            soup.body.insert(0, h1)

            navbar = '#include virtual="../../navbar.shtml"'
            soup.body.insert(0, BSComment(navbar))
        
        return soup

    def publish(self):

        period = self.meta['period']
        rootdir = self.meta['rootdir']
        remote = f"{self.SITE_DIR}/programs/P{period:03}"
        html = self.meta['html']
        dir = os.path.dirname(html)
        os.system(f"scp -r {html} {remote}/index.shtml")
