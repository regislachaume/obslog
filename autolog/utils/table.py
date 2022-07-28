from astropy.table import Table as _Table

import numpy as np
from bs4 import BeautifulSoup
from io import StringIO
import os

def BS(arg):
    return BeautifulSoup(arg, features='lxml')

class Table(_Table):

    def as_beautiful_soup(self, *, htmldict={}, **kwargs):
      
        title = htmldict.pop('title', None)
        h1 = htmldict.pop('h1', None)
        h2 = htmldict.pop('h2', None)
        caption = htmldict.pop('caption', None)
        lang = htmldict.pop('lang', 'en')

        # HTML writer doesn't honour include/exclude names?!?

        tab = self 
       
        units = [col.unit.name if col.unit else '' for col in tab.itercols()]
 
        if include_names := kwargs.pop('include_names', None):
            tab = tab[include_names]

        if exclude_names := kwargs.pop('exclude_names', None):
            names = [n for n in tab.colnames if n not in exclude_names]
            tab = tab[names]

        # Table with header only, add units

        with StringIO() as fh:
            _Table(tab[0:0]).write(fh, format='ascii.html', 
                                    htmldict=htmldict, **kwargs)
            html = fh.getvalue()
        soup = BS(html)
        table = soup.table 

        for th, col in zip(table.find_all('th'), tab.itercols()):
            desc = col.description
            if desc:
                th['title'] = desc

        units = [col.unit.name if col.unit else '' for col in tab.itercols()]
        if any(units):
            line = ''.join(f"<th>{col.unit.name if col.unit else ''}</th>" 
                        for col in tab.itercols())
            line = f"<tr>{line}</tr>"
            table.thead.append(BS(line).tr)

        if caption:
            cap = BS(f'<caption>{caption}</caption>').caption
            table.insert(0, cap)

        # Write each group in a tbody
        for group in tab.groups:
            with StringIO() as fh:
                _Table(group).write(fh, format='ascii.html', 
                    htmldict=htmldict, **kwargs)
                html = fh.getvalue()
            tbody = BS(html).table
            thead = tbody.thead.extract()
            tbody.name = 'tbody'
            table.append(tbody) 

        meta = soup.find_all('meta')
        for m in meta:
            if 'charset' in m.get('content', ''):
                m.extract()

        soup.html['lang'] = lang 

        if title:

            title = BS(f'<title>{title}</title>').title
            soup.head.append(title)

        if h1:

            h1 = BS(f'<h1>{h1}</h1>').h1
            soup.body.insert(0, h1)
        
        if h2:

            h2 = BS(f'<h2>{h2}</h2>').h2
            soup.body.insert(1, h2)

        return soup

    @classmethod
    def read(cls, input, *, format, **kwargs):

        tab = super().read(input, format=format, **kwargs)

        # eliminate fake row
        if format == 'ascii.ecsv':
            tab = tab[:-1]

        return tab
        

    def write(self, output, *, format, **kwargs):

        if format in ['ascii.html', 'html']:
            
            overwrite = kwargs.pop('overwrite', False)
            
            soup = self.as_beautiful_soup(**kwargs)
            text = "<!DOCTYPE html>\n"
            text += soup.prettify()

            if isinstance(output, str):
                if not overwrite and os.path.exists(output):
                    raise RuntimeError('cannot overwrite existing file')
                with open(output, 'w') as fh:
                    fh.write(text)
            else:
                fh = output
                fh.write(text)

        elif format == 'ascii.ecsv':
            
            print('Saving to ascii.ecsv')    
            # ensure str column width is preserved

            fake_row = np.zeros((), dtype=self.dtype)
            for name in fake_row.dtype.names:
                d = fake_row[name].dtype
                if d.char in 'SU':
                    padding = 'x' * (d.itemsize // d.alignment)
                    fake_row[name] = padding
            self.add_row(fake_row.tolist())    
            try:
                super().write(output, format=format, 
                    serialize_method='data_mask', **kwargs)
            except Exception as e:
                self.remove_row(-1)
                raise e

            self.remove_row(-1)

        else:
            
            super().write(output, format=format, **kwargs)
