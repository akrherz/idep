""" Setup the necessary directory structure, so that other codes need not """
import psycopg2
import os
import sys

SCENARIO = sys.argv[1]

PGCONN = psycopg2.connect(database='idep', host='iemdb')
cursor = PGCONN.cursor()

PREFIXES = 'env  man  prj  run  slp  sol  wb'.split()

def do(huc12):
    """ Directory creator! """
    for prefix in PREFIXES:
        d = "/i/%s/%s/%s/%s" % (SCENARIO, prefix, huc12[:8], huc12[8:])
        if not os.path.isdir(d):
            os.makedirs(d)

if __name__ == '__main__':
    # Go Main Go
    cursor.execute("""SELECT distinct huc_12 from flowpaths
    WHERE scenario = %s""", (SCENARIO,))
    for row in cursor:
        do( row[0] )