from astropy.table import Table as _Table

from bs4 import BeautifulSoup
from io import StringIO

def BS(arg):
    return BeautifulSoup(arg, features='lxml')

class Table(_Table):

    def as_beautiful_soup(self, *, htmldict={}, **kwargs):
      
        print('Table.as_beautiful_soup')
 
        tab = self

        title = htmldict.pop('title', None)
        h1 = htmldict.pop('h1', None)
        h2 = htmldict.pop('h2', None)
        caption = htmldict.pop('caption', None)
        lang = htmldict.pop('lang', 'en')
 
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
        print(tab.groups)
        for group in tab.groups:
            with StringIO() as fh:
                _Table(group).write(fh, format='ascii.html', **kwargs)
                html = fh.getvalue()
            tbody = BS(html).table
            tbody.thead.extract()
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
