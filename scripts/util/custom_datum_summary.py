"""Generate DEP for a custom datum."""
from calendar import month_abbr

from pyiem.dep import read_env
from pyiem.util import get_dbconn
from geopandas import read_file
import pandas as pd
from pandas.io.sql import read_sql
from tqdm import tqdm


def main():
    """Go Main Go."""
    dbconn = get_dbconn("idep")
    # Load custom shapefile
    gpd = read_file("/tmp/Catchment_headwaters_w_LK.shp")
    result = []
    for _, row in tqdm(gpd.iterrows(), total=len(gpd.index)):
        # Find flowpaths intersecting the shape bounds
        df = read_sql(
            "SELECT huc_12, fpath, ST_Length(geom) as len from flowpaths "
            "where scenario = 0 and ST_Intersects(geom, "
            "ST_Transform(ST_SetSRID(ST_GeomFromEWKT(%s), 26915), 5070))",
            dbconn,
            params=(row["geometry"].wkt,),
            index_col=None,
        )
        if df.empty:
            continue
        res = {"fpcount": len(df.index), "CATCH_ID": row["CATCH_ID"]}
        # Read all the envs, include row count
        envs = []
        for _, fp in df.iterrows():
            envfn = (
                f"/i/0/env/{fp['huc_12'][:8]}/{fp['huc_12'][8:]}/"
                f"{fp['huc_12']}_{fp['fpath']}.env"
            )
            envdf = read_env(envfn)
            envdf["key"] = f"{fp['huc_12']}_{fp['fpath']}"
            envdf["delivery"] = envdf["sed_del"] / fp["len"]
            envs.append(envdf)
        envdf = pd.concat(envs)
        envdf["month"] = envdf["date"].dt.month
        # HUC 12 Annual Soils Loss, Precipitation and RunOff for 2008-2019
        genvdf = envdf.groupby(by=["key", "year"]).sum().groupby("year").mean()
        for year in range(2008, 2020):
            ydf = genvdf.loc[year]
            for col in ["delivery", "precip", "runoff"]:
                res[f"{col}_{year}"] = float(ydf[col])
        # HUC 12 and headwater lake catchments monthly Soils Loss,
        # Precipitation and RunOff for 2019
        env2019 = envdf[envdf["year"] == 2019]
        genv2019 = (
            env2019.groupby(by=["key", "month"]).sum().groupby("month").mean()
        )
        for month in range(1, 10):  # ran on Oct 6th
            mdf = genv2019.loc[month]
            for col in ["delivery", "precip", "runoff"]:
                res[f"{col}_{year}_{month_abbr[month]}"] = float(mdf[col])
        result.append(res)

    # Dump out
    df = pd.DataFrame(result)
    df.to_csv("dep_data.csv", index=False, float_format="%.4f")


if __name__ == "__main__":
    main()
