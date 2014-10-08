import psycopg2

DBCONN = psycopg2.connect(database='wepp')
cursor = DBCONN.cursor()

def read_slope(fn):
    lines = open(fn).readlines()
    data = []
    for line in lines:
        if len(line.strip()) == 0 or line[0] == '#':
            continue
        data.append(line)
    fplen = data[2].split()[0]
    xs = []
    slp = []
    travel = 0
    for i in range(3, len(data), 2):
        slen = float(data[i].split()[1])
        nums = data[i+1].replace(",", "").split()
        for pos in nums[0:len(nums):2]:
            xs.append( float(pos) * slen + travel )
        for pos in nums[1:len(nums):2]:
            slp.append( float(pos) )
        travel += slen
    h2 = [0]
    x2 = [0]
    for x, s in zip(xs, slp):
        h2.append( h2[-1] + (x - x2[-1]) * (0- s) )
        x2.append( x )

    return x2, h2


cursor.execute("""SELECT id, model_twp from nri where model_twp = 'T82NR05E'""")

slopes1 = {}
for row in cursor:
    x2,y2 = read_slope("/mnt/idep/data/slopes/%s.slp" % (row[0],))
    if not slopes1.has_key(row[1]):
        slopes1[ row[1] ] = []
    slopes1[ row[1] ].append(  (y2[-1] - y2[0]) / (x2[0] - x2[-1]) )
    print row[0], x2[-1], slopes1[row[1]][-1]
    
for modeltwp in slopes1.keys():
    print slopes1[modeltwp]
    print '%s,%s' % (modeltwp, sum(slopes1[modeltwp]) / float(len(slopes1[modeltwp])))
