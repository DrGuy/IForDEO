#/usr/bin/python
# -*- coding: utf-8 -*-
"""
Created on Wed Aug  3 15:16:51 2016

@author: gserbin.admin
"""

import os, sys, glob, datetime, argparse, shutil, ieo
from subprocess import Popen
from pkg_resources import resource_filename, Requirement
from osgeo import ogr, osr

if sys.version_info[0] == 2:
    import ConfigParser as configparser
else:
    import configparser

# Access configuration data inside Python egg
config = configparser.ConfigParser()
config_location = resource_filename(Requirement.parse('ifordeo'), 'config/ifordeo.ini')
#config_file = 'ifordeo.ini'
#config_location = resource_stream(__name__, config_file)
#config_path = os.path.join(os.path.join(__name__, 'config'), 'ifordeo.ini')
#config_location = resource_stream(config_path)
#config_path = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config'), 'ifordeo.ini')
config.read(config_location)

parser = argparse.ArgumentParser()
parser.add_argument('-o', '--overwrite', action = "store_true", help = 'Overwrite existing files.')
parser.add_argument('-r', '--rootdir', type = str, default = config['DEFAULT']['baseoutputdir'], help = 'Base directory for IForDEO classification files.')
parser.add_argument('--minforesttograss', type = int, default = 3000, help = 'Minimum value for forest to grass cutoff.')
parser.add_argument('--maxforesttograss', type = int, default = 4000, help = 'Maximum value for forest to grass cutoff.')
parser.add_argument('--increment', type = int, default = 250, help = 'Increment value for forest to grass cutoff.')
parser.add_argument('--dt4a', type = bool, default = True, help = 'Use new DT4a data files.')
parser.add_argument('-l', '--listonly', action = "store_true", help = 'Rewrite catalog lists, but not VRTs.')
parser.add_argument('-u', '--update', action = "store_true", help = 'Update VRTs and lists for new scenes.')
parser.add_argument('-f', '--fix', action = "store_true", help = 'Fix shapefiles only.')
margs = parser.parse_args()

catdir = config['DEFAULT']['catdir'] # os.path.join(margs.rootdir,'Catalog')
#print(catdir)

target = osr.SpatialReference()
target.ImportFromEPSG(2157) # Irish Transverse Mercator ERTS-89
# Create Shapefile
driver = ogr.GetDriverByName("ESRI Shapefile")

def makefilelist(dirname, datetuple):
    flist = glob.glob(os.path.join(dirname, 'L*%s*.dat'%datetuple.strftime('%Y%j')))
    filelist = []
    if len(flist) >= 2:
        if len(flist) == 2 and os.path.basename(flist[0])[6:9] == os.path.basename(flist[1])[6:9]:
            filelist = None
            return filelist
        path = int(os.path.basename(flist[0])[3:6])
        
        if path == 207 or path == 208:
            row = 21
        else:
            row = 22
        while row < 25:
            fs = [f for f in flist if '%d%03d'%(path,row) in f]
            if len(fs) == 1:
                filelist.append(fs[0])
            elif len(fs) > 1:
                fs = [f for f in flist if ('%d%03d'%(path,row) in f and not 'ESA' in f)]
                if len(fs) > 0:
                    filelist.append(max(fs))
            row += 1
    elif len(filelist) == 1: # This logs single scenes for a date into the CSV file without further processing
        catfile = os.path.join(catdir, '{}_proc.csv'.format(dirname[:4]))
        print('Only one file found for this date. Logging {} in {}'.format(os.path.basename(filelist[0]),os.path.basename(catfile))) 
        writetocsv(catfile, filelist[0], filelist, datetuple)
    if len(filelist) < 2:
        filelist = None
    return filelist

def makevrtfilename(outdir, filelist):
    numscenes = len(filelist)
    basename = os.path.basename(filelist[0]).replace('.dat','.vrt')
    startrow = basename[8:9]
    endrow = os.path.basename(filelist[-1])[8:9]
    outbasename = '%s%d%s%s%s'%(basename[:6],numscenes,startrow,endrow,basename[9:])
    vrtfilename = os.path.join(outdir, outbasename)
    return vrtfilename

def writetocsv(catfile, vrt, filelist, datetuple):
    scenelist = ['None'] * 4
    path = None
    for f in filelist:
        sceneID = os.path.basename(f)[:21]
        i = int(sceneID[7:9]) - 21
        scenelist[i] = sceneID
        if not path:
            path = sceneID[3:6]
    header = 'Date,Year,DOY,Path,R021,R022,R023,R024,VRT'    
    if not os.path.isfile(catfile): # creates catalog file if missing
        with open(catfile,'w') as output:
            output.write('%s\n'%header)    
    outline = '%s,%s,%s,%s'%(datetuple.strftime('%Y-%m-%d'),datetuple.strftime('%Y'),datetuple.strftime('%j'),scenelist[0][3:6])
    for s in scenelist:
        outline += ',%s'%s
    with open(catfile,'a') as output:
        output.write('{},{}\n'.format(outline,vrt))
    
def fixshps():
    foresttograss = margs.minforesttograss    
    while foresttograss <= margs.maxforesttograss:
        catshpdir = os.path.join(catdir, 'shp')
        if not os.path.isdir(catshpdir):
            os.mkdir(catshpdir)
        catshp = os.path.join(catshpdir, '{}_proc.shp'.format(foresttograss))
        print('Fixing shapefile: {}'.format(os.path.basename(catshp)))
        writetoshp(catshp, fix = True)
        foresttograss += margs.increment

def writetoshp(catshp, *args, **kwargs):
    vrt = kwargs.get('vrt', None)
    filelist = kwargs.get('filelist', None)
    datetuple = kwargs.get('datetuple', None)
    fix = kwargs.get('fix', False)
    
    src_ds = driver.Open(ieo.landsatshp, 0)
    inlayer = src_ds.GetLayer()
    
    if not fix:
        ftg = os.path.basename(os.path.dirname(filelist[0]))
#        print(filelist[0])    
        path = int(os.path.basename(filelist[0])[3:6])
    
#    featlist= []
        scenelist = []
        scenelist = ['None'] * 4
        for f in filelist:
            sceneID = os.path.basename(f)[:21]
            i = int(sceneID[7:9]) - 21
            scenelist[i] = sceneID
    if not os.path.isfile(catshp):
        data_source = driver.CreateDataSource(catshp)
        layer = data_source.CreateLayer("VRT shapes for {}".format(ftg), target, ogr.wkbPolygon)
        layer.CreateField(ogr.FieldDefn('Date', ogr.OFTDate))
        layer.CreateField(ogr.FieldDefn('Year', ogr.OFTInteger))
        layer.CreateField(ogr.FieldDefn('DOY', ogr.OFTInteger))
        layer.CreateField(ogr.FieldDefn('Path', ogr.OFTInteger))
        layer.CreateField(ogr.FieldDefn('R021', ogr.OFTString))
        layer.CreateField(ogr.FieldDefn('R022', ogr.OFTString))
        layer.CreateField(ogr.FieldDefn('R023', ogr.OFTString))
        layer.CreateField(ogr.FieldDefn('R024', ogr.OFTString))
        layer.CreateField(ogr.FieldDefn('VRT', ogr.OFTString))
    else:
        data_source = driver.Open(catshp, 1)
        layer = data_source.GetLayer()
    if not fix:
        outfeature = ogr.Feature(layer.GetLayerDefn())
        outfeature.SetField('Date', datetuple.strftime('%Y-%m-%d'))
        outfeature.SetField('Year', datetuple.year)
        outfeature.SetField('DOY', int(datetuple.strftime('%j')))
        outfeature.SetField('Path', path)
        for a, b in zip(['R021', 'R022', 'R023', 'R024'], scenelist):
            outfeature.SetField(a, b)
        outfeature.SetField('VRT', vrt)
        outgeom = prepfootprint(inlayer, scenelist)
        outfeature.SetGeometry(outgeom)
        layer.CreateFeature(outfeature)
    else:
        for feat in layer:
            vrt = feat.GetField('VRT')
            if os.path.isfile(vrt):
                print('Processing VRT: {}'.format(vrt))
                scenelist = [feat.GetField('R021'), feat.GetField('R022'), feat.GetField('R023'), feat.GetField('R024')]
                outgeom = prepfootprint(inlayer, scenelist)
                feat.SetGeometry(outgeom)
                layer.SetFeature(feat)
    src_ds = None
    data_source = None
    
def prepfootprint(inlayer, scenelist):
    numscenes = 4 - scenelist.count('None')
    print('Number of scenes = {}'.format(numscenes))
    pointdict = {'X': [], 'Y': [], 'XY': []}
    inlayer.ResetReading()
    for feature in inlayer:
        if feature.GetField("sceneID") in scenelist:
            
#            fit = inlayer.GetFeature(feature)
            geom = feature.GetGeometryRef()
#            if numscenes > 1:
            pointdict = getpoints(geom, pointdict)
#            else:
#                outgeom = geom
#                break
#    if numscenes > 1:
    ULpos = pointdict['Y'].index(max(pointdict['Y']))
    URpos = pointdict['X'].index(max(pointdict['X']))
    LRpos = pointdict['Y'].index(min(pointdict['Y']))
    LLpos = pointdict['X'].index(min(pointdict['X']))
    points = [pointdict['XY'][ULpos], pointdict['XY'][URpos], pointdict['XY'][LRpos], pointdict['XY'][LLpos], pointdict['XY'][ULpos]]
    ring = ogr.Geometry(ogr.wkbLinearRing)
    for point in points:
        ring.AddPoint(point[0], point[1])
    # Create polygon
    outgeom = ogr.Geometry(ogr.wkbPolygon)
    
    outgeom.AddGeometry(ring)
    return outgeom

def getpoints(geom, pointdict):
#    geom = feature.GetGeometryRef()
    ring = geom.GetGeometryRef(0)
    points = ring.GetPointCount()
#    print(points)
#    print('{}:'.format(feature.GetField(fn)))
    for i in range(points - 1):
        point = ring.GetPoint(i)
        pointdict['X'].append(point[0])
        pointdict['Y'].append(point[1])
        pointdict['XY'].append(point)
    return pointdict

def makevrt(filelist, catfile, catshp, vrt, datetuple):
    basename = os.path.basename(vrt)
    print('Now creating VRT: %s'%basename)
    proclist = ['gdalbuildvrt','-srcnodata','0',vrt]    
#    scenelist.append(vrt)
    for f in filelist:
        if os.path.isfile(f):
            proclist.append(f)
    p = Popen(proclist)
    print(p.communicate())
    writetocsv(catfile, vrt, filelist, datetuple)
    writetoshp(catshp, vrt = vrt, filelist = filelist, datetuple = datetuple)

def updatevrt(dirname, catfile, catshp, datetuple):
    vrtdir = os.path.join(dirname,'vrt')
    flist = makefilelist(dirname, datetuple)
    if flist:
        vrt = makevrtfilename(vrtdir, flist)
        makevrt(flist, catfile, catshp, vrt, datetuple)

def batchnewvrts(*args, **kwargs):
    global catdir
    dirname = kwargs.get('dirname', None)
    dirlist = kwargs.get('dirlist', None)
    subdirs = kwargs.get('subdirs', None)
    overwrite = kwargs.get('overwrite', False)
    
    if dirname:
        dirlist = [dirname]
    elif subdirs:        
        dirlist = []
        for subdir in subdirs:
            dirlist.append(os.path.join(margs.rootdir,subdir))
    
    for d in dirlist:
        print('Now searching for files in: {}'.format(d))
        filedict = {}
        subdir = os.path.basename(d)
        if subdir == 'DT4a':
            filelist = glob.glob(os.path.join(d,'L*DT4aclass.dat'))
        else:
            filelist = glob.glob(os.path.join(d,'L*DT4class.dat'))
        if len(filelist) > 0:
            for f in filelist:
                SceneID = os.path.basename(f)[:21]
                if not SceneID[9:16] in filedict.keys():
                    filedict[SceneID[9:16]] = [f]
                filedict[SceneID[9:16]].append(f)
            datelist = list(filedict.keys())
            datelist.sort()
            catfile = os.path.join(catdir, '{}_proc.csv'.format(subdir))
            catshpdir = os.path.join(catdir, 'shp')
            if not os.path.isdir(catshpdir):
                os.mkdir(catshpdir)
            catshp = os.path.join(catshpdir, '{}_proc.shp'.format(subdir))
            if overwrite and os.path.isfile(catshp):
                now = datetime.datetime.now()
                catshpbakdir = os.path.join(catshpdir, 'bak')
                if not os.path.isdir(catshpbakdir):
                    os.mkdir(catshpbakdir)
                catshpbakdir = os.path.join(catshpbakdir, now.strftime('%Y%m%d-%H%M%S'))
                if not os.path.isdir(catshpbakdir):
                    os.mkdir(catshpbakdir)
                catshpfilelist = glob.glob(catshp[:-3] + '*')
                if len(catshpfilelist) > 0:
                    for f1 in catshpfilelist:
                        if os.path.isfile(f1):
                            shutil.move(f1, catshpbakdir)
            if os.path.isfile(catfile):
                now = datetime.datetime.now()
                bak = catfile.replace('.csv','.{}.bak'.format(now.strftime('%Y%m%d-%H%M%S')))
                shutil.move(catfile, bak)
#            if os.path.isfile(catshp):    
#                flist = glob.glob(catshp.replace('.shp','.*'))
#                for f in flist:
#                    os.remove(f)
            vrtdir = os.path.join(d,'vrt')
            if not os.path.isdir(vrtdir):
                os.mkdir(vrtdir)
            if overwrite:
                flist = glob.glob(os.path.join(vrtdir, '*'))
                if len(flist) > 0:
                    for f1 in flist:
                        if os.path.isfile(f1):
                            os.remove(f1)
            
            for f in datelist:
                datetuple = datetime.datetime.strptime(f,'%Y%j')
                numfiles = len(filedict[f])
                if numfiles > 1:
                    filedict[f].sort()
                    vrt = makevrtfilename(vrtdir, filedict[f])
                    print('Now processing: {}'.format(os.path.basename(vrt)))
                    makevrt(filedict[f], catfile, catshp, vrt, datetuple)
                elif numfiles == 1:
                    vrt = filedict[0]
                    print('Writing to catalog file {}: {}'.format(os.path.basename(catfile), os.path.basename(vrt)))
                    writetocsv(catfile, vrt, filedict[f], datetuple)
                else:
                    print('ERROR: No files found for date {}.'.format(f))

def batchvrts():
    today = datetime.datetime.today()
    
    # rootdir = r'D:\Spatial Analysis Unit\Archive\Landsat'
#    rootdir = margs.rootdir
    subdirs = []
    if margs.dt4a:
        foresttograss = None
        subdirs.append('DT4a')
    else:
        foresttograss = margs.minforesttograss
        while foresttograss <= margs.maxforesttograss:
            subdirs.append(str(foresttograss))
            foresttograss += margs.increment
        
    dirlist = []
    
    if not os.path.isdir(catdir):
        os.mkdir(catdir)
    for subdir in subdirs:
        dirlist.append(os.path.join(margs.rootdir, subdir))
    
    batchnewvrts(dirlist = dirlist, overwrite = margs.overwrite)
    '''
#    print(dirlist)
    if margs.overwrite: # not margs.listonly and 
        batchnewvrts(dirlist = dirlist)
                
    elif margs.update: # margs.listonly or 
        for subdir in subdirs:
            d = os.path.join(margs.rootdir,subdir)
            vrtdir = os.path.join(d,'vrt')
            catfile = os.path.join(catdir, '{}_proc.csv'.format(subdir))
            catshpdir = os.path.join(catdir, 'shp')
            if not os.path.isdir(catshpdir):
                os.mkdir(catshpdir)
            catshp = os.path.join(catshpdir, '{}_proc.shp'.format(subdir))
            print('Now processing: {}'.format(os.path.basename(catfile)))
            bak = '{}.{}.bak'.format(catfile, today.strftime('%Y%m%d-%H%M%S'))
            shutil.move(catfile, bak)
            datelist = []
            with open(bak, 'r') as lines:
                for line in lines:
                    if not line.startswith('Date'):
                        linelist = line.strip('\n').split(',')
                        datetuple = datetime.datetime.strptime('{}{}'.format(linelist[1],linelist[2]),'%Y%j')
                        filelist = glob.glob(os.path.join(d,'L*{}{}*.dat'.format(linelist[1],linelist[2])))
                        basename = os.path.basename(linelist[8])
                        if margs.update:
                            if (len(filelist) == 1 and basename[6:7] == '0') or (len(filelist) == int(basename[6:7])):
                                with open(catfile,'a') as output:
                                    output.write(line)  
                                datelist.append('{}{}'.format(linelist[1],linelist[2]))
                            else:
                                updatevrt(d, catfile, catshp, datetuple)
                                datelist.append('{}{}'.format(linelist[1],linelist[2]))
                        else:
                            vrtlist = glob.glob(os.path.join(vrtdir,'L*{}{}*.vrt'.format(linelist[1],linelist[2])))
                            if len(vrtlist) == 0:
                                vrt = makevrtfilename(d, filelist)
                            else:
                                vrt = vrtlist[0]
                            writetocsv(catfile, vrt, filelist, datetime.datetime.strptime('{}{}'.format(linelist[1],linelist[2]),'%Y%j')) 
                    else:
                        with open(catfile,'w') as output:
                            output.write(line)
            if margs.update:
                print('Searching for new scenes.')
                filelist = glob.glob(os.path.join(d,'L*.dat'))
                newlist = []
                for f in filelist:
                    if not os.path.basename(f)[9:16] in datelist:
                        newlist.append(os.path.basename(f)[9:16])
                if len(newlist) > 0:
                    print('New files have been found, processing.')
                    for n in newlist:
                        datetuple = datetime.datetime.strptime(n,'%Y%j')
                        updatevrt(d, catfile, catshp, datetuple)
                        
                    
    '''
    print('Processing complete.')

def main():
    if margs.fix:
        fixshps()
    else:
        batchvrts()

if __name__ == '__main__':
    main()