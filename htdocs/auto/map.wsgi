"""Mapping Interface"""
import sys
import datetime
from io import BytesIO

import numpy as np
import memcache
from paste.request import parse_formvars
from matplotlib.patches import Polygon
import matplotlib.colors as mpcolors
from geopandas import read_postgis
import cartopy.crs as ccrs
from pyiem.plot.use_agg import plt
from pyiem.plot.geoplot import MapPlot
from pyiem.plot.colormaps import james, james2
from pyiem.util import get_dbconn
from pyiem.dep import RAMPS

V2NAME = {
    'avg_loss': 'Detachment',
    'qc_precip': 'Precipitation',
    'avg_delivery': 'Hillslope Soil Loss',
    'avg_runoff': 'Runoff'}
V2MULTI = {
    'avg_loss': 4.463,
    'qc_precip': 1. / 25.4,
    'avg_delivery': 4.463,
    'avg_runoff': 1. / 25.4,
    }
V2UNITS = {
    'avg_loss': 'tons/acre',
    'qc_precip': 'inches',
    'avg_delivery': 'tons/acre',
    'avg_runoff': 'inches',
    }


def make_map(huc, ts, ts2, scenario, v):
    """Make the map"""
    plt.close()
    # suggested for runoff and precip
    if v in ['qc_precip', 'avg_runoff']:
        # c = ['#ffffa6', '#9cf26d', '#76cc94', '#6399ba', '#5558a1']
        cmap = james()
    # suggested for detachment
    elif v in ['avg_loss']:
        # c =['#cbe3bb', '#c4ff4d', '#ffff4d', '#ffc44d', '#ff4d4d', '#c34dee']
        cmap = james2()
    # suggested for delivery
    elif v in ['avg_delivery']:
        # c =['#ffffd2', '#ffff4d', '#ffe0a5', '#eeb74d', '#ba7c57', '#96504d']
        cmap = james2()

    pgconn = get_dbconn('idep')
    cursor = pgconn.cursor()

    title = "for %s" % (ts.strftime("%-d %B %Y"),)
    if ts != ts2:
        title = "for period between %s and %s" % (ts.strftime("%-d %b %Y"),
                                                  ts2.strftime("%-d %b %Y"))
    projection = ccrs.Mercator()

    # Check that we have data for this date!
    cursor.execute("""
        SELECT value from properties where key = 'last_date_0'
    """)
    lastts = datetime.datetime.strptime(cursor.fetchone()[0], '%Y-%m-%d')
    floor = datetime.date(2007, 1, 1)
    if ts > lastts.date() or ts2 > lastts.date() or ts < floor:
        plt.text(0.5, 0.5, "Data Not Available\nPlease Check Back Later!",
                 fontsize=20, ha='center')
        ram = BytesIO()
        plt.savefig(ram, format='png', dpi=100)
        plt.close()
        ram.seek(0)
        return ram.read(), False
    if huc is None:
        huclimiter = ''
    elif len(huc) == 8:
        huclimiter = " and substr(i.huc_12, 1, 8) = '%s' " % (huc, )
    elif len(huc) == 12:
        huclimiter = " and i.huc_12 = '%s' " % (huc, )
    df = read_postgis("""
    WITH data as (
      SELECT huc_12, sum("""+v+""")  as d from results_by_huc12
      WHERE scenario = %s and valid between %s and %s
      GROUP by huc_12)

    SELECT ST_Transform(simple_geom, %s) as geom,
    coalesce(d.d, 0) * %s as data
    from huc12 i LEFT JOIN data d
    ON (i.huc_12 = d.huc_12) WHERE i.scenario = %s
    """ + huclimiter + """
    """, pgconn, params=(scenario, ts.strftime("%Y-%m-%d"),
                         ts2.strftime("%Y-%m-%d"), projection.proj4_init,
                         V2MULTI[v], scenario), geom_col='geom')
    minx, miny, maxx, maxy = df['geom'].total_bounds
    buf = 10000.  # 10km
    pts = ccrs.Geodetic().transform_points(
        projection, np.asarray([minx - buf, maxx + buf]),
        np.asarray([miny - buf, maxy + buf]))
    m = MapPlot(axisbg='#EEEEEE', nologo=True, sector='custom',
                south=pts[0, 1], north=pts[1, 1],
                west=pts[0, 0], east=pts[1, 0],
                projection=projection,
                title='DEP %s by HUC12 %s' % (V2NAME[v], title),
                caption='Daily Erosion Project')
    if ts == ts2:
        # Daily
        bins = RAMPS['english'][0]
    else:
        bins = RAMPS['english'][1]
    norm = mpcolors.BoundaryNorm(bins, cmap.N)
    for _, row in df.iterrows():
        p = Polygon(row['geom'].exterior,
                    fc=cmap(norm([row['data'], ]))[0], ec='k',
                    zorder=2, lw=.1)
        m.ax.add_patch(p)

    lbl = [round(_, 2) for _ in bins]
    if huc is not None:
        m.drawcounties()
        m.drawcities()
    m.draw_colorbar(bins, cmap, norm, units=V2UNITS[v],
                    clevlabels=lbl)
    ram = BytesIO()
    plt.savefig(ram, format='png', dpi=100)
    plt.close()
    ram.seek(0)
    return ram.read(), True


def main(environ):
    """Do something fun"""
    form = parse_formvars(environ)
    year = form.get('year', 2015)
    month = form.get('month', 5)
    day = form.get('day', 5)
    year2 = form.get('year2', year)
    month2 = form.get('month2', month)
    day2 = form.get('day2', day)
    scenario = int(form.get('scenario', 0))
    v = form.get('v', 'avg_loss')
    huc = form.get('huc')

    ts = datetime.date(int(year), int(month), int(day))
    ts2 = datetime.date(int(year2), int(month2), int(day2))
    mckey = "/auto/map.py/%s/%s/%s/%s/%s" % (huc, ts.strftime("%Y%m%d"),
                                             ts2.strftime("%Y%m%d"), scenario,
                                             v)
    mc = memcache.Client(['iem-memcached:11211'], debug=0)
    res = mc.get(mckey)
    hostname = environ.get("SERVER_NAME", "")
    if not res or hostname == "dailyerosion.local":
        # Lazy import to help speed things up
        res, do_cache = make_map(huc, ts, ts2, scenario, v)
        sys.stderr.write("Setting cache: %s\n" % (mckey,))
        if do_cache:
            mc.set(mckey, res, 3600)
    return res


def application(environ, start_response):
    """Our mod-wsgi handler"""
    output = main(environ)
    response_headers = [('Content-type', 'image/png')]
    start_response('200 OK', response_headers)

    return [output]


if __name__ == '__main__':
    make_map(None, datetime.date(2017, 12, 25), datetime.date(2017, 12, 25), 0,
             'qc_precip')