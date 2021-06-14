import xlrd
import numpy as np
from astropy import table

def numeric_values(col):

    # Column is considered numeric if there are numbers and empty ('') cells.

    mask = [c == '' for c in col]

    if (not all(mask) and any(mask) and
        all(type(c) in [int, float] or c == '' for c in col)):

        col = [0 if c == '' else c for c in col]
        
        return np.ma.masked_array(col, mask=mask)

    # Otherwise, let

    return np.array(col)
    
def table_from_excel(filename, start_row=0, start_col=0,
                                layout='vertical', cls=table.Table,
                                sheetnum=0):
    
    with xlrd.open_workbook(filename) as book:
        page = book.sheets()[sheetnum]
    
    ncols, nrows = page.ncols, page.nrows
    cols = []
    records, dtype = [], []
    
    if layout in ['vertical', 'columns']:
        names = page.row_values(start_row, start_col, ncols)
        cols = [page.col_values(c, start_row + 1, nrows)
                              for c in range(start_col, ncols)]
    else:
        names = page.col_values(start_col, start_row, nrows)
        cols = [page.row_values(r, start_col + 1, ncols)
                              for r in range(start_row, nrows)]

    cols = [numeric_values(col) for col in cols]

    return cls(cols, names=names)

