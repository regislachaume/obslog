import xlrd
import numpy as np
from astropy import table

def table_from_excel(filename, cls=table.Table, **kwargs):

    arr = structured_array_from_excel(filename, **kwargs)

    return cls(arr)

def structured_array_from_excel(filename, start_row=0, start_col=0,
                                layout='vertical', cls=np.recarray,
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
        cols = [page.col_values(r, start_col + 1, ncols)
                              for r in range(start_row, nrows)]
    
    return structured_array(cols=cols, names=names, cls=cls)

def structured_array(records=None, cols=None, names=None, dtypes=None,
                     cls=np.ndarray):
    
    if cols == None:
        cols = [c for c in zip(*records)]
        if names is None:
            names = records[0].dtype.names
    
    if dtypes == None:
        dtypes = [None for c in cols]
    
    cols = [np.asarray(c, dtype=t) for c, t  in zip(cols, dtypes)]
    dtype = [(n, c.dtype) for n, c in zip(names, cols)]
    shape = (len(cols[0]),)
    arr = np.ndarray(shape=shape, dtype=dtype)
    
    for n, c in zip(names, cols):
        arr[n] = c
    
    arr = arr.view(type=cls, dtype=(np.record, arr.dtype))
    
    return arr

