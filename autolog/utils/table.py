from astropy.table import Table as _Table

from bs4 import BeautifulSoup
from io import StringIO

def BS(arg):
    return BeautifulSoup(arg, features='lxml')

class Table(_Table):

    def as_beautiful_soup(self, *, caption=None, standalone=False,
            lang='en', htmldict={}, **kwargs):
       
        tab = self
       
        # HTML writer doesn't honour include/exclude names?!?
 
        if include_names := kwargs.pop('include_names', None):
            tab = tab[include_names]

        if exclude_names := kwargs.pop('exclude_names', None):
            names = [n for n in tab.colnames if n not in exclude_names]
            tab = tab[names]

        # Table with header only

        with StringIO() as fh:
            _Table(tab[0:0]).write(fh, format='ascii.html', 
                                    htmldict=htmldict, **kwargs)
            html = fh.getvalue()
        soup = BS(html)
        table = soup.table  

        if caption:
            cap = BS(f'<caption>{caption}</caption>').caption
            table.insert(0, cap)

        # Write each group in a tbody

        for group in tab.groups:
            print(kwargs)
            with StringIO() as fh:
                _Table(group).write(fh, format='ascii.html', **kwargs)
                html = fh.getvalue()
            tbody = BS(html).table
            tbody.thead.extract()
            tbody.name = 'tbody'
            table.append(tbody) 

        if standalone:
            return soup.table

        meta = soup.find_all('meta')
        for m in meta:
            if 'charset' in m.get('content', ''):
                m.extract()

        soup.html['lang'] = lang 

        return soup

    def write(self, output, *, format, caption=None, **kwargs):

        if format in ['ascii.html', 'html']:

            htmldict = kwargs.pop('htmldict', {})
            soup = self.as_beautiful_soup(caption=caption, **htmldict)
            text = "<!DOCTYPE html>\n"
            text += soup.prettify()

            if isinstance(output, str):
                fh = open(output, 'w')
            else:
                fh = output
            fh.write(text)

        else:
    
            super().write(output, format=format, **kwargs)
