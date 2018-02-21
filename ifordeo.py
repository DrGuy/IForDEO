#/usr/bin/python
# the Irish Forest Disturbance from Earth Observation (IForDEO) Module
# By Guy Serbin, Environment, Soils, and Land Use Dept., CELUP, Teagasc, Johnstown Castle, Co. Wexford Y35 TC97, Ireland
# Email: Guy <dot> Serbin <at> teagasc <dot> ie
# This model was developed for the CForRep project

# 8 February 2018: Added DT4b function to better calculate continuum removal features between green-NIR and NIR-SWIR2 + code updates
# 8 February 2018: Updated help info in input parser

import os, sys, glob, shutil, argparse, datetime, numexpr, ieo
from ieo import ENVIfile
from pkg_resources import resource_filename, Requirement
from osgeo import gdal, ogr, osr
import numpy as np


if sys.version_info[0] == 2:
    import ConfigParser as configparser
else:
    import configparser

# bundled configuration and data
# config_path = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config'), 'ifordeo.ini')
# tileshppath = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'), 'IRL_tiles_30.shp')
# 
# config = configparser.ConfigParser()
# 
# if os.path.isfile(config_path):
#     print('Successfully located: {}'.format(config_path))
# else:
#     print('Failed to find: {}'.format(config_path))
# config.read(config_path)

# Access configuration data inside Python egg
config = configparser.ConfigParser()
config_location = resource_filename(Requirement.parse('ifordeo'), 'config/ifordeo.ini')
#config_file = 'ifordeo.ini'
#config_location = resource_stream(__name__, config_file)
#config_path = os.path.join(os.path.join(__name__, 'config'), 'ifordeo.ini')
#config_location = resource_stream(config_path)
#config_path = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config'), 'ifordeo.ini')
config.read(config_location)
tileshppath = ieo.NTS # resource_filename(Requirement.parse('ifordeo'), 'data/IRL_tiles_30.shp')

parser = argparse.ArgumentParser(description = 'Irish Forestry Disturbance from Earth Observation (IForDEO) module.', epilog = 'Setting both --dt4a and --dt4b to false will utilise the old DT4 function and will generate many more files.')
#parser.add_argument('-i', '--ieo', type = str, default = None, help = 'Alternate ieo module directory')
parser.add_argument('-c', '--calcdt4', action = "store_true", help = 'Calculate DT4 scenes.')
parser.add_argument('-a', '--dt4a', default = False, help = 'Use DT4a algorithm (default = False). Setting this to "True" will override --dt4b to "False".')
parser.add_argument('-b', '--dt4b', default = True, help = 'Use DT4b algorithm (default = True).')
parser.add_argument('-o', '--overwrite', action = "store_true", help = 'Overwrite existing files.')
parser.add_argument('-s', '--shp', type = str, default = tileshppath, help = 'National tile grid shapefile.')
parser.add_argument('-f', '--forestrymaskfile', type = str, default = config['DEFAULT']['forestrymaskfile'], help = 'National forestry mask file.')
parser.add_argument('--usemaskfile', type = bool, default = True, help = 'Use a national forestry mask file (default = True).')
parser.add_argument('--usecatfile', type = bool, default = True, help = 'Use local VRT catalog file for creating yearly classifications (default = True).')
parser.add_argument('--minforesttograss', type = int, default = 3000, help = 'Minimum scaled reflectance value for cutoff between forest and non-forest vegetation.')
parser.add_argument('--maxforesttograss', type = int, default = 4000, help = 'Maximum scaled reflectance value for cutoff between forest and non-forest vegetation.')
parser.add_argument('--increment', type = int, default = 250, help = 'Increment for scaled reflectance value for cutoff between forest and non-forest vegetation.')
parser.add_argument('--startyear', type = int, default = 1984, help = 'Year for which to start the analysis.')
parser.add_argument('--endyear', type = int, default = datetime.datetime.now().year, help = 'Year for which to end the analysis.')
parser.add_argument('--startday', type = int, default = 82, help = 'Day of year for which to start the analysis.')
parser.add_argument('--endday', type = int, default = 283, help = 'Day of year for which to end the analysis.')
parser.add_argument('--minpixels', type = int, default = 1000, help = 'Minimum number of clear land pixels in a Landsat scene required for DT4, DT4a, or DT4b classification.')
margs = parser.parse_args()


#try:
#    import ieo
#    from ieo import ENVIfile
#except:
#    # ieolocation = config['DEFAULT']['ieolocation']
#    if os.path.exists(config['DEFAULT']['ieolocation']):
#        sys.path.append(config['DEFAULT']['ieolocation'])
#        import ieo
#        from ieo import ENVIfile
#    else:
#        if margs.ieo:
#            dirname = margs.ieo
#        else:
#            dirname = input('Please input path to ieo module: ')
#        if os.path.isdir(dirname):
#            sys.path.append(dirname)
#            import ieo
#            from ieo import ENVIfile
#        else:
#            print('ERROR: ieo module not located, exiting.')
#            quit()
        
    
errorfile = os.path.join(ieo.logdir, config['DEFAULT']['errorlogfile'])

def logerror(f, message):
    if not os.path.exists(errorfile):
        with open(errorfile, 'w') as output:
            output.write('Time, File, Error\n')
    now = datetime.datetime.now()
    with open(errorfile, 'a') as output:
        output.write('{}, {}, {}\n'.format(now.strftime('%Y-%m-%d %H:%M:%S'), f, message))


def ESPAreprocess(SceneID, listfile):
    print('Adding scene {} for ESPA reprocessing to: {}'.format(SceneID, listfile))
    with open(listfile, 'a') as output:
        output.write('{}\n'.format(SceneID))

## ENVI file related

# Spatial variables

prj = osr.SpatialReference()
prj.SetProjection("EPSG:2157")

# Directory and file paths



# Shamelessly copied from http://pydoc.net/Python/spectral/0.17/spectral.io.envi/

# dtype_map = [('1', 'uint8'),                   # unsigned byte
#              ('2', 'int16'),                   # 16-bit int
#              ('3', 'int32'),                   # 32-bit int
#              ('4', 'float32'),                 # 32-bit float
#              ('5', 'float64'),                 # 64-bit float
#              ('6', 'complex64'),               # 2x32-bit complex
#              ('9', 'complex128'),              # 2x64-bit complex
#              ('12', 'uint16'),                 # 16-bit unsigned int
#              ('13', 'uint32'),                 # 32-bit unsigned int
#              ('14', 'int64'),                  # 64-bit int
#              ('15', 'uint64')]                 # 64-bit unsigned int
# envi_to_dtype = dict((k, np.dtype(v).char) for (k, v) in dtype_map)
# dtype_to_envi = dict(tuple(reversed(item)) for item in list(envi_to_dtype.items()))
dtype_to_envi = {
    'uint8': '1',                   # unsigned byte
    'int16': '2',                   # 16-bit int
    'int32': '3',                   # 32-bit int
    'float32': '4',                 # 32-bit float
    'float64': '5',                 # 64-bit float
    'complex64': '6',               # 2x32-bit complex
    'complex128': '9',              # 2x64-bit complex
    'uint16': '12',                 # 16-bit unsigned int
    'uint32': '13',                 # 32-bit unsigned int
    'int64': '14',                  # 64-bit int
    'uint64': '15'                 # 64-bit unsigned int
    }


headerfields = 'acquisition time,band names,bands,bbl,byte order,class lookup,class names,classes,cloud cover,complex function,coordinate system string,data gain values,data ignore value,data offset values,data reflectance gain values,data reflectance offset values,data type,default bands,default stretch,dem band,dem file,description,file type,fwhm,geo points,header offset,interleave,lines,map info, pixel size, product type, projection info,read procedures,reflectance scale factor,rpc info,samples,security tag,sensor type,solar irradiance,spectra names,sun azimuth,sun elevation,wavelength,wavelength units,x start,y start,z plot average,z plot range,z plot titles,defaultbasefilename'.split(',')

def getheaderdict(*args, **kwargs):
    rastertype = kwargs.get('rastertype', None)
    outdir = kwargs.get('outdir', None)
    tilename = kwargs.get('tilename', None)
    SceneID = kwargs.get('SceneID', None)
    year = kwargs.get('year', None)
    startyear = kwargs.get('startyear', None)
    endyear = kwargs.get('endyear', None)
    acqtime = kwargs.get('acqtime', None)
    foresttograss = kwargs.get('foresttograss', None)
    minforesttograss = kwargs.get('minforesttograss', None)
    maxforesttograss = kwargs.get('maxforesttograss', None)
    classname = kwargs.get('classname', None) # Not the same as classnames!
    observationtype = kwargs.get('observationtype', None) # Not the same as classnames!
    parentrasters = kwargs.get('parentrasters', None)
    
    headerdict = dict.fromkeys(headerfields)
    for key in headerdict.keys():
        headerdict[key] = None
    
    if parentrasters:
        headerdict['parentrasters'] = parentrasters
    
    if rastertype == 'DT4':
        headerdict['description'] = 'Decision tree classification for {}, foresttograss = {}'.format(SceneID, foresttograss)
        headerdict['band names'] = ['DT4']
        headerdict['classes'] = 10
        headerdict['class names'] = ['Unclassified', 'Water', 'Urban', 'Bog', 'Bare Soil', 'Heath', 'Grassland/ cropland', 'Young forest', 'Mature forest', 'Possible forest or green heath']
        headerdict['class lookup'] = [
            [0,     0,      0],   
            [0,     0,      255],   
            [200,   200,    200],   
            [255,   127,    80],   
            [160,   82,     45],   
            [218,   112,    214],   
            [0,     255,    0],   
            [165,   214,    0],   
            [0,     139,    0],   
            [0,     170,    100]]
        headerdict['defaultbasefilename'] = '{}_DT4class.dat'.format(SceneID)
        
    if rastertype == 'DT4a':
        headerdict['description'] = 'Decision tree classification for {}, foresttograss = {} - {}'.format(SceneID, minforesttograss, maxforesttograss)
        headerdict['band names'] = ['DT4a']
        headerdict['classes'] = 12
        headerdict['class names'] = ['Unclassified', 'Water', 'Urban', 'Bog', 'Bare Soil', 'Heath', 'Grassland/ cropland', 'Young forest', 'Mature forest', 'Possible forest or green heath', 'Forest/ grass/ crop', 'Forest/ green heath/ grass/ crop']
        headerdict['class lookup'] = [
            [0,     0,      0],   
            [0,     0,      255],   
            [200,   200,    200],   
            [255,   127,    80],   
            [160,   82,     45],   
            [218,   112,    214],   
            [0,     255,    0],   
            [165,   214,    0],   
            [0,     139,    0],   
            [0,     170,    100],
            [0,     200,    0],
            [0,     215,    150]]
        headerdict['defaultbasefilename'] = '{}_DT4aclass.dat'.format(SceneID)

    elif rastertype == 'DT4b':
        headerdict['description'] = 'Decision tree classification for {}, foresttograss = {} - {}'.format(SceneID, minforesttograss, maxforesttograss)
        headerdict['band names'] = ['DT4b']
        headerdict['classes'] = 12
        headerdict['class names'] = ['Unclassified', 'Water', 'Urban', 'Bog', 'Bare Soil', 'Heath', 'Grassland/ cropland', 'Young forest', 'Mature forest', 'Possible forest or green heath', 'Forest/ grass/ crop', 'Forest/ green heath/ grass/ crop']
        headerdict['class lookup'] = [
            [0,     0,      0],   
            [0,     0,      255],   
            [200,   200,    200],   
            [255,   127,    80],   
            [160,   82,     45],   
            [218,   112,    214],   
            [0,     255,    0],   
            [165,   214,    0],   
            [0,     139,    0],   
            [0,     170,    100],
            [0,     200,    0],
            [0,     215,    150]]
        headerdict['defaultbasefilename'] = '{}_DT4bclass.dat'.format(SceneID)    
    
    elif rastertype == 'YearlyDT4':
        headerdict['classes'] = 17
        headerdict['class names'] = ['Unclassified', 'Water', 'Urban', 'Grassland/ cropland', 'Bog/ heath', 'Forestry', 'Crop + bog', 'crop + forest', 'bog + forest', 'forest + urban', 'bog + urban', 'crop + urban', 'forest + water', 'bog + water', 'crop + water', 'urban + water', 'Three or more classes']
        headerdict['class lookup'] = [
            [0,     0,      0],
            [0,     0,      255],
            [200,   200,    200],
            [0,     255,    0],
            [160,   82,     45],
            [0,     139,    0],
            [80,    169,    23],
            [139,   197,    139],
            [160,   139,    45],
            [100,   139,    100],
            [255,   127,    80],
            [100,   200,    100],
            [0,     139,    100],
            [218,   112,    214],
            [0,     255,    200],
            [200,   200,    255],
            [75,    75,     75]]
        
        if year:
            headerdict['defaultbasefilename'] = 'DT4_class_{}_{}.dat'.format(year, tilename)
            if foresttograss:
                headerdict['description'] = 'Highest probability class for {}, foresttograss = {}'.format(year, foresttograss)
            else:
                headerdict['description'] = 'Highest probability class for {}'.format(year)
            headerdict['band names'] = ['Class {}'.format(year)]
                
        elif startyear and endyear:
            headerdict['defaultbasefilename'] = 'DT4_class_{}_{}_{}.dat'.format(startyear, endyear, tilename)
            headerdict['description'] = 'Highest probability class for {} - {}, foresttograss = {}'.format(startyear, endyear, foresttograss)
            headerdict['band names'] = ['Class {}-{}'.format(startyear, endyear)]
            
    elif rastertype == 'ForestryClass':
        headerdict['band names'] = ['{}'.format(year)]
        if foresttograss:
            headerdict['description'] = 'Forest classification {} for foresttograss = {}'.format(year, foresttograss)
        else:
            headerdict['description'] = 'Forest classification {}'.format(year)
        headerdict['classes'] = 4
        headerdict['class lookup'] = [
            [0,     0,      0], 
            [200,   200,    200], 
            [100,   255,    100], 
            [0,     139,    0]]
        headerdict['class names'] = ['No data', 'Not forest', 'Possible forest', 'Forest']
        headerdict['defaultbasefilename'] = 'forestryclass_{}_{}.dat'.format(year, tilename)
    
    elif rastertype == 'Highpos':
        headerdict['defaultbasefilename'] = 'Highpos_{}_{}.dat'.format(year, tilename)
        if foresttograss:
            headerdict['description'] = 'Highest probability class for {}, foresttograss = {}'.format(year, foresttograss)
        else:
            headerdict['description'] = 'Highest probability class for {}'.format(year)
        headerdict['band names'] = ['{} land cover class'.format(year)]
        headerdict['classes'] = 12
        headerdict['class lookup'] = [
            [0,     0,      0], 
            [0,     0,      255], 
            [200,   200,    200], 
            [0,     255,    0], 
            [160,   82,     45], 
            [0,     139,    0], 
            [0,     139,    100], 
            [80,    169,    23], 
            [139,   197,    139], 
            [160,   139,    45],
            [0,     200,    0],
            [0,     215,    150]]
        headerdict['class names'] = ['No data', 'Water', 'Urban', 'Crop or grassland', 'Bog or heathland', 'Forestry', 'Heathland or forest', 'Crop/grassland or bog', 'Crop/grassland or forest', 'Bog/heathland or forest', 'Forest/ grass/ crop', 'Forest/ green heath/ grass/ crop']
        
    elif rastertype == 'pct': # this uses 'classname', not 'classnames'
        headerdict['defaultbasefilename'] = '{}_pct_{}_{}.dat'.format(classname, year, tilename)
        if foresttograss:
            headerdict['description'] = '{} class probability for {}, foresttograss = {}'.format(classname, year, foresttograss)
        else:
            headerdict['description'] = '{} class probability for {}'.format(classname, year)
        headerdict['band names'] = ['{} {}'.format(classname, year)]
        
    elif rastertype == 'denominator':
        headerdict['defaultbasefilename'] = 'Obs_{}_{}.dat'.format(year, tilename)
        if foresttograss:
            headerdict['description'] = 'Number of observations for {}, foresttograss = {}'.format(year, foresttograss)
        else:
            headerdict['description'] = 'Number of observations for {}'.format(year)
        headerdict['band names'] = ['Observations for {}'.format(year)]
        
    elif rastertype == 'year':
        headerdict['defaultbasefilename'] = '{}_{}.dat'.format(observationtype, tilename)
        if foresttograss:
            headerdict['description'] = '{} year, foresttograss = {}'.format(observationtype, foresttograss)
        else:
            headerdict['description'] = '{} year'.format(observationtype)
        headerdict['band names'] = ['Year of {}'.format(observationtype)]
        
    elif rastertype == 'ForestryStatus':
        if foresttograss:
            headerdict['description'] = 'Forestry status change for {} - {}, foresttograss = {}'.format(startyear, endyear, foresttograss)
        else:
            headerdict['description'] = 'Forestry status change for {} - {}'.format(startyear, endyear)
        headerdict['defaultbasefilename'] = 'forestrystatus_{}.dat'.format(tilename)
        headerdict['classes'] = 8 # Class information for the header file
        headerdict['class lookup'] = [
            [0,     0,      0], 
            [200,   200,    200], 
            [100,   100,    100], 
            [255,   0,      0], 
            [115,   38,     0], 
            [255,   255,    0], 
            [0,     255,    0], 
            [0,     139,    0]]
        headerdict['class names'] = ['No data', 'Unforested', 'Forested (no change)', 'Deforestation', 'Possible deforestation', 'Recent clearcut', 'Reforestation', 'Afforestation']
        headerdict['band names'] = ['Forestry status']
  
    headerdict['pctclasses'] = {'forestry': 'Forestry', 'cropgrass':'Crop or grassland', 'bogheath':'Bog or heath', 'heathforest':'Heath or forest confusion', 'urban': 'Urban', 'water': 'Water', 'bogforest': 'Bog or forest confusion', 'cropbog': 'Crop or bog confusion'}
    headerdict['ready'] = True
    return headerdict

def getdictdata(*args, **kwargs):
    rastertype = kwargs.get('rastertype', None)
    outdir = kwargs.get('outdir', None)
    tilename = kwargs.get('tilename', None)
    SceneID = kwargs.get('SceneID', None)
    year = kwargs.get('year', None)
    startyear = kwargs.get('year', None)
    endyear = kwargs.get('endyear', None)
    acqtime = kwargs.get('acqtime', None)
    foresttograss = kwargs.get('foresttograss', None)
    minforesttograss = kwargs.get('minforesttograss', None)
    maxforesttograss = kwargs.get('maxforesttograss', None)
    classname = kwargs.get('classname', None) # Not the same as classnames!
    observationtype = kwargs.get('observationtype', None) # Not the same as classnames!
    bands = kwargs.get('bands', 1)
    
    d = getheaderdict(rastertype = rastertype, tilename = tilename, SceneID = SceneID, year = year, startyear = startyear, endyear = endyear, foresttograss = foresttograss, minforesttograss = minforesttograss, maxforesttograss = maxforesttograss, classname = classname, observationtype = observationtype)
    if d['description']:
        description = 'description = {} {}{}\n'.format('{', d['description'], '}')
        bandnamesstr = ''
        for i in range(len(d['band names'])):
            bandnamesstr += ' {},'.format(d['band names'][i])
        bandnames = 'band names = {}{}{}\n'.format('{', bandnamesstr[:-1], '}')
    else:
        description = 'description = { Raster data}\n'
        outstr=''
        for i in range(bands):
            outstr+=' Band {},'.format(i + 1)
        bandnames = 'band names = {} {}{}\n'.format('{', outstr[:-1], '}')
    
    outfilename = os.path.join(outdir,d['defaultbasefilename'])
    
    if d['classes']:
        classes = 'classes = {}\n'.format(d['classes'])
        outstr=''
        for x in d['class names']:
            outstr+=' {},'.format(x)
        classnames = 'class names = {} {}{}\n'.format('{', outstr[:-1], '}')
        outstr=''
        for i in d['class lookup']:
            for j in i:
                outstr+=' {},'.format(j)
        classlookup = 'class lookup = {} {}{}\n'.format('{', outstr[:-1], '}')
        classlookuptable = d['class lookup']
    else: 
        classlookuptable = None
    
    if acqtime or year:
        if acqtime:
            if not 'acquisition time' in acqtime:
                acquisitiontime = 'acquisition time = {}\n'.format(acqtime)
            else:
                acquisitiontime = acqtime
        else:
            acquisitiontime = 'acquisition time = {}-07-01\n'.format(year)
    else: acquisitiontime = None
    
    return description, bandnames, outfilename, classes, classnames, classlookup, classlookuptable, acquisitiontime

def writedata(data, rastertype, geoTrans, *args, **kwargs):
    outdir = kwargs.get('outdir', None)
    tilename = kwargs.get('tilename', None)
    SceneID = kwargs.get('SceneID', None)
    year = kwargs.get('year', None)
    startyear = kwargs.get('startyear', None)
    endyear = kwargs.get('endyear', None)
    acqtime = kwargs.get('acqtime', None)
    foresttograss = kwargs.get('foresttograss', None)
    minforesttograss = kwargs.get('minforesttograss', None)
    maxforesttograss = kwargs.get('maxforesttograss', None)
    classname = kwargs.get('classname', None) # Not the same as classnames!
    observationtype = kwargs.get('observationtype', None) # Not the same as classnames!
    rasters = kwargs.get('rasters', None) # List of rasters that were used to create these data.
    
    if rasters:
        if len(rasters) > 0 and isinstance(rasters, list):
            parentrasters = 'parent rasters = {'
            for raster in rasters:
                parentrasters += ' {},'.format(os.path.basename(raster))
            parentrasters = parentrasters[:-1] + '}\n'
        else:
            parentrasters = None
    else:
        parentrasters = None
    
    headerdict = getheaderdict(rastertype = rastertype, outdir = outdir, tilename = tilename, year = year, startyear = startyear, endyear = endyear, foresttograss = foresttograss, minforesttograss = minforesttograss, maxforesttograss = maxforesttograss, classname = classname, observationtype = observationtype, SceneID = SceneID, parentrasters = parentrasters)
    ENVIfile(data, rastertype, geoTrans = geoTrans, headerdict = headerdict, acqtime = acqtime, outdir = outdir).Save()
    
## General functions



def world2Pixel(geoMatrix, x, y):
  """
  Uses a gdal geomatrix (gdal.GetGeoTransform()) to calculate
  the pixel location of a geospatial coordinate
  """
  ulX = geoMatrix[0]
  ulY = geoMatrix[3]
  xDist = geoMatrix[1]
  yDist = geoMatrix[5]
  rtnX = geoMatrix[2]
  rtnY = geoMatrix[4]
  pixel = int((x - ulX) / xDist)
  line = int((ulY - y) / xDist)
  return (pixel, line)

def pixel2world(geoMatrix, pixel, line):
  """
  Uses a gdal geomatrix (gdal.GetGeoTransform()) to calculate
  the pixel location of a geospatial coordinate
  """
  ulX = geoMatrix[0]
  ulY = geoMatrix[3]
  xDist = geoMatrix[1]
  yDist = geoMatrix[5]
  rtnX = geoMatrix[2]
  rtnY = geoMatrix[4]
  x = xDist * float(pixel) + ulX
  y = yDist * float(line) + ulY
  return (x, y)

def getval(img, x, y):
    
    geoTrans = img.GetGeoTransform()
    cols = img.RasterXSize
    rows = img.RasterYSize
    # print(band.shape)
    px, py = world2Pixel(geoTrans, x, y)
    if px >= 0 and py >= 0 and px < cols and py < rows:
        band = img.GetRasterBand(1).ReadAsArray(px, py, 1, 1)
        # structval=img.ReadRaster(px, py, 1, 1) #Assumes 16 bit int aka 'short'
        # intval = struct.unpack('B' , structval) #use the 'short' format code (2 bytes) not int (4 bytes)
        # intval = intval[0]
        intval = band[0, 0]
    else:
        intval = 0
    return intval
    
def clipgdal(img):
    band = img.GetRasterBand(1).ReadAsArray()
    geoTrans = img.GetGeoTransform()
    print(band.shape)
    ulX, ulY = world2Pixel(geoTrans, UL[0], UL[1])
    lrX, lrY = world2Pixel(geoTrans, LR[0], LR[1])
    pxWidth = int(lrX - ulX)
    pxHeight = int(lrY - ulY)
    
    clip_array = band[ulY:lrY, ulX:lrX]
    return clip_array

def cleansignal(signal): # This assigns either a forestry/not forestry value to the signal on a per-pixel basis where data are missing or not sure.
    spikes = []
    locs = np.where(numexpr.evaluate("(signal == 0) | (signal == 2)"))
    signal[numexpr.evaluate("(signal == 15)")] = 1 
    for i in range(1, len(signal) - 1):
        if signal[i] in [1, 3] and signal[i - 1] in [1, 3] and signal[i] != signal[i - 1] and signal[i - 1] == signal[i + 1]: # locate spikes
            spikes.append(i)
    if len(spikes) > 0:
        for i in spikes:
            if i == 1:
                if signal[i + 1] == signal[i + 2]:
                    signal[i] = signal[i + 1]
                else: 
                    signal[i] = 3
            elif i > 1 and i < len(signal) - 2:
                if signal[i - 1] == signal[i - 2] and signal[i + 1] == signal[i + 2]:
                    signal[i] = signal[i - 1]
            if i > 1 and i < len(signal) - 2:
                if signal[i - 2] == signal[i - 1] or signal[i + 1] == signal[i + 2]:
                    signal[i] = signal[i - 1]
                elif signal[i - 2] in [1, 3] or signal[i + 2] in [1, 3]:
                    signal[i] = 3
            elif i == len(signal) - 2:
                if signal[i - 1] == signal[i - 2]:
                    signal[i] = signal[i - 1]
                else: 
                    signal[i] = 3
    while len(locs[0])>0:
        for i in locs[0]:
            if i == 0 and signal[1] in [1, 3]:
                signal[0] = signal[1]
            elif i == 1:
                if signal[0] in [1, 3]:
                    signal[1] = signal[0]
                elif signal[2] in [1, 3]:
                    signal[1] = signal[2]
            elif i > 1 and i < len(signal) - 2:
                if signal[i - 1] == signal[i + 1] and signal[i - 1] != signal[i] and signal[i - 1] in [1, 3]: # Assume point is the same as neighbors if they equal one another
                    signal[i] = signal[i - 1]
                elif signal[i] in [0, 2] and 3 in [signal[i - 1], signal[i + 1]]: # assume time point is forestry if before or after are forestry
                    signal[i] = 3
                elif signal[i] in [0, 2] and 1 in [signal[i - 1], signal[i + 1]]: # assume time point is forestry if before or after are forestry
                    signal[i] = 1
            elif i == len(signal) - 2:
                if signal[-3] == 3 or signal[-1] == 3:
                    signal[-2] = 3
                elif signal[-3] == 1 or signal[-1] == 1:
                    signal[-2] = 1
            elif i == len(signal) - 1 and signal[-2] in [1, 3]:
                signal[-1] = signal[-2]
        locs = None
        locs = np.where(numexpr.evaluate("(signal == 0) | (signal == 2)"))
    spikes=[]
    for i in range(1, len(signal) - 1):
        if signal[i] in [1, 3] and signal[i - 1] in [1, 3] and signal[i] != signal[i - 1] and signal[i - 1] == signal[i + 1]: # locate spikes
            spikes.append(i)
    if len(spikes)>0:
        for i in spikes:
            if i == 1:
                if signal[i + 1] == signal[i + 2]:
                    signal[i] = signal[i + 1]
                else: 
                    signal[i] = 3
            elif i > 1 and i < len(signal) - 2:
                if signal[i - 1] == signal[i - 2] and signal[i + 1] == signal[i + 2]:
                    signal[i] = signal[i - 1]
            if i > 1 and i < len(signal) - 2:
                if signal[i - 2] == signal[i - 1] or signal[i + 1] == signal[i + 2]:
                    signal[i] = signal[i - 1]
                elif signal[i - 2] in [1, 3] or signal[i + 2] in [1, 3]:
                    signal[i] = 3
            elif i == len(signal) - 2:
                if signal[i - 1] == signal[i - 2]:
                    signal[i] = signal[i - 1]
                else:
                    signal[i] = 3
    locs = None
    return signal

def lcchange(signal, years, endyear):
    # This function takes a signal containing no data/ not forest/ possible forest/ forest values and determines afforestation, reforestation, and clearcut years. It takes code that was originally in the calcyearlychange() function, and was created so that yearly time-series data from CSVs could also be analysed.
    startclassval = 0
    endclassval = 0
    afforestedval = 0
    clearcutval = 0
    reforestedval = 0
    status = 0
    statusyear = 0
    
    if (1 in signal or 3 in signal) and (0 in signal or 2 in signal):
                # print(signal)
        signal = cleansignal(np.array(signal)).tolist()
    startclassval = signal[0]  
    endclassval = signal[-1]
    if 3 in signal and 1 in signal:
        cut = False
        refor = False
        if signal[0] == 1:
            afforestedval = years[signal.index(next(i for i in signal[1:] if i == 3))]
        for i in range(len(years) - 1, 0,-1):
            print(i)
            if signal[i] == 3 and signal[i - 1] == 1:
                year = years[i]
                if year > afforestedval and (afforestedval > 0 or signal[0] == 3) and not refor:
                    reforestedval = year
                    refor = True 
            elif signal[i] == 1 and signal[i - 1] == 3:
                year = years[i]
                clearcutval = year
                cut = True
            if refor and cut:
                break
        diffyear=0
        if reforestedval > afforestedval:
            lastforest = reforestedval
        else:
            lastforest = afforestedval
        if clearcutval > lastforest: #reforested[y, x] and clearcut[y, x] > afforested[y, x]:
            diffyear = endyear - clearcutval # replace year
            if diffyear < 5:
                status = 5 # recent clearcut
            elif diffyear < 10:
                status = 4 # possible deforestation
            elif diffyear >= 10:
                status = 3 # deforested
            statusyear = clearcutval
        elif reforestedval > afforestedval:
            status = 6 # reforested
            statusyear = reforestedval
        elif afforestedval > 0:
            status = 7 # afforested
            statusyear = afforestedval
    elif 3 in signal and 0 not in signal:
        status = 2
    elif 1 in signal and 0 not in signal:
        status = 1
    return startclassval, endclassval, afforestedval, clearcutval, reforestedval, status, statusyear

def drawProgressBar(percent, pixnum,numpixels, barLen = 40):
    sys.stdout.write("\r")
    progress = ""
    for i in range(barLen):
        if i < int(barLen * percent):
            progress += "="
        else:
            progress += " "
    sys.stdout.write("[ {} ] {:.2f}% ({}/{})".format(progress, percent * 100, pixnum, numpixels))
    sys.stdout.flush()

def getbadlist(*args, **kwargs):
    badlistfile = kwargs.get('badlist', ieo.badlandsat)
    badlist = []
    if os.path.isfile(badlistfile):
        with open(badlistfile, 'r') as lines:
            for line in lines:
                if len(line) >= 7:
                    badlist.append(line.rstrip())
    else:
        print('ERROR: file not found: {}'.format(badlistfile))
        logerror(badlistfile, 'File not found.')
    return badlist

def makereproctiledict(*args, **kwargs):
    if margs.dt4a:
        outsubdir = 'dt4a'
    elif margs.dt4b:
        outsubdir = 'dt4b'
    else:
        outsubdir = None
    startyear = kwargs.get('startyear', margs.startyear)
    endyear = kwargs.get('endyear', margs.endyear)
    badlistfile = kwargs.get('badlist', ieo.badlandsat)
    foresttograss = kwargs.get('foresttograss', outsubdir)
    if isinstance(foresttograss, int):
        foresttograss = int(foresttograss)
    probdir = os.path.join(os.path.join(config['DEFAULT']['baseoutputdir'], foresttograss), 'Probability')
    badlist = getbadlist()
    tiledict = {}
    year = startyear
    while year <= endyear:
        flist = glob.glob(os.path.join(probdir, 'Obs_{}_*.hdr'.format(year)))
        if len(flist) > 0:
            for f in flist:
                tilename = os.path.basename(f)[-7:-4]
                with open(f, 'r') as lines:
                    for line in lines:
                        if line.startswith('parent rasters'):
                            i = line.find('{') + 1
                            j = line.find('}')
                            fs = line.replace(' ','').split(',')
                            for fs1 in fs:
                                if fs1[9:16] in badlist:
                                    if not year in tiledict.keys():
                                        tiledict[year] = []
                                    if not tilename in tiledict[year]:
                                        tiledict[year].append(tilename)
        year += 1
    return tiledict

## Vector routines

def makeproclist(tilegeom, foresttograss, usecatfile, *args, **kwargs):
    # this function determines which processed DT4/a/b VRT files or scenes get used in calcprobabilityraster()
    year = kwargs.get('year', None) # limit to a specific year
    dt4a = kwargs.get('dt4a', margs.dt4a)
    dt4b = kwargs.get('dt4b', margs.dt4b)
    if margs.dt4a:
        outsubdir = 'dt4a'
    elif margs.dt4b:
        outsubdir = 'dt4b'
    else:
        outsubdir = str(foresttograss)
    badlist = getbadlist()
    proclist = []
#    if foresttograss:
    dirname = kwargs.get('dirname', os.path.join(config['DEFAULT']['baseoutputdir'], '{}'.format(outsubdir)))
#    else:
#        dirname = kwargs.get('dirname', os.path.join(config['DEFAULT']['baseoutputdir'], outsubdir))
    
    if not margs.usecatfile:
        sceneshp = kwargs.get('sceneshp', ieo.landsatshp)
    else:
        catshpdir = os.path.join(config['DEFAULT']['catdir'], 'shp')
#        if foresttograss:
#            sceneshp = os.path.join(catshpdir, '{}_proc.shp'.format(foresttograss))
#        else:
        sceneshp = os.path.join(catshpdir, '{}_proc.shp'.format(outsubdir))
    
    driver = ogr.GetDriverByName("ESRI Shapefile")
    
        
    ds = driver.Open(sceneshp, 0)
    layer = ds.GetLayer()
    for feature in layer:
        try:
            if usecatfile:
                f = feature.GetField('VRT')
                fyear = feature.GetField('Year')
            else:
                sceneid = feature.GetField('sceneID')
                if foresttograss: 
                    f = os.path.join(dirname, '{}_DT4class.dat'.format(sceneid))
                else:
                    f = os.path.join(dirname, '{}_{}class.dat'.format(sceneid, outsubdir))
                fyear = int(feature.GetField('acqDate')[:4])
            
            datestr = os.path.basename(f)[9:16]
            if (year == fyear or not year) and os.path.isfile(f):
                geom = feature.GetGeometryRef()
                if tilegeom.Intersect(geom) and not datestr in badlist:
                    proclist.append(f)
        except Exception as e:
            print('ERROR: {}: {}'.format(os.path.basename(sceneshp), e))
            logerror(sceneshp, e)
    layer = None
    return proclist

def makegrid(*args, **kwargs): # function deprecated: Further development will now occur as part of IEO 1.1.0 and higher
    import string
    minX = kwargs.get('minX', 418500.0)
    minY = kwargs.get('minY', 519000.0)
    maxX = kwargs.get('maxX', 769500.0)
    maxY = kwargs.get('maxY', 969000.0)
    xtiles = kwargs.get('xtiles', 12)
    ytiles = kwargs.get('ytiles', 15)
    outfile = kwargs.get('outfile', margs.shp)
    inshp = kwargs.get('inshape', config['vector']['irelandshp'])
    overwrite = kwargs.get('overwrite', margs.overwrite)
    
    if overwrite:
        flist = glob.glob(outfile.replace('.shp', '.*'))
        for f in flist:
            os.remove(f)
    
   # determine tile sizes
    dx = (maxX - minX) / xtiles
    dy = (maxY - minY) / ytiles
    
    # set up the shapefile driver
    driver = ogr.GetDriverByName("ESRI Shapefile")
    
    # Get input shapefile
    inDataSource = driver.Open(inshp, 0)
    inLayer = inDataSource.GetLayer()
    feat = inLayer.GetNextFeature()
    Ireland = feat.GetGeometryRef()
    
    # create the data source
    if os.path.exists(outfile):
        os.remove(outfile)
    data_source = driver.CreateDataSource(outfile)
    
    # create the layer
    layer = data_source.CreateLayer("Tiles", prj, ogr.wkbPolygon)
    
    # Add fields
    field_name = ogr.FieldDefn("Tile", ogr.OFTString)
    field_name.SetWidth(2)
    layer.CreateField(field_name)
    
    # Create the multipolygon
#    multipolygon = ogr.Geometry(ogr.wkbMultiPolygon)
    
    for i in range(xtiles):
        for j in range(ytiles):
            if ytiles > 9:
                tilename='{}{:02d}'.format(string.ascii_uppercase[i], j + 1)
            else:
                tilename='{}{}'.format(string.ascii_uppercase[i], j + 1)
            # if xtiles == 4 and ytiles ==5 and tilename != 'A5':
            mx = minX + i * dx
            X = mx + dx
            my = minY + j * dy
            Y = my + dy
            ring = ogr.Geometry(ogr.wkbLinearRing)
            ring.AddPoint(mx, my)
            ring.AddPoint(mx, Y)
            ring.AddPoint(X, Y)
            ring.AddPoint(X, my)
            ring.AddPoint(mx, my)
            # Create polygon
            poly = ogr.Geometry(ogr.wkbPolygon)
            poly.AddGeometry(ring)
            # add new geom to layer if it intersects Ireland shapefile
            p = Ireland.Intersect(poly)
#            print(p)
            if p:
                outFeature = ogr.Feature(layer.GetLayerDefn())
                outFeature.SetGeometry(poly)
                outFeature.SetField('Tile', tilename)
                layer.CreateFeature(outFeature)
                outFeature.Destroy
            
def checkintersect(tilegeom, extent):
    # Create bounding box for Landsat scene
    ring = ogr.Geometry(ogr.wkbLinearRing)
    ring.AddPoint(extent[0], extent[1])
    ring.AddPoint(extent[0], extent[3])
    ring.AddPoint(extent[2], extent[1])
    ring.AddPoint(extent[2], extent[3])
    ring.AddPoint(extent[0], extent[1])
    rasterGeometry = ogr.Geometry(ogr.wkbPolygon)
    rasterGeometry.AddGeometry(ring)
    return rasterGeometry.Intersect(tilegeom)
    

## Processing routines

coeffdict = {}
coeffdict['LT4'] = {'GRNIR':(0.662000 - 0.560000)/(0.830000 - 0.560000), 'NIRSWIR12':(2.215000 - 1.648000)/(2.215000 - 0.830000)}
coeffdict['LT5'] = {'GRNIR':(0.662000 - 0.560000)/(0.830000 - 0.560000), 'NIRSWIR12':(2.215000 - 1.648000)/(2.215000 - 0.830000)}
coeffdict['LE7'] = {'GRNIR':(0.662000 - 0.560000)/(0.835000 - 0.560000), 'NIRSWIR12':(2.206000 - 1.648000)/(2.206000 - 0.835000)}
coeffdict['LC8'] = {'GRNIR':(0.654600 - 0.561300)/(0.864600 - 0.561300), 'NIRSWIR12':(2.201000 - 1.609000)/(2.201000 - 0.864600)}

def dt4(infile, outdir, minpixels, foresttograss, *args, **kwargs):
    
    # By Guy Serbin, Spatial Analysis Unit, REDP, Teagasc National Food Research Centre, Ashtown, Dublin 15, Ireland.
    # This file will read in a Landsat 4 TM - 8 OLI file and perform a decision tree classification on it.
    # 
    # Variables:
    # infile - full path and filename of input reflectance file.
    # maskdir - directory containing fmask files
    # outdir - directory to output classifications
    # minpixels - minimum number of cloud-free land pizels needed for the analysis
    # [/overwrite] - if set, overwrite any existing files, otherwise skip.
    # 
    # This code was shamelessly adapted from an example in the ENVI help file.
    # This code makes use of the ENVI 5.x API.  It will not work in ealier versions.
    
    cfmaskfile = kwargs.get('fmask', None)
    fmaskdir = kwargs.get('fmaskdir', ieo.fmaskdir)
    overwrite = kwargs.get('overwrite', margs.overwrite)
    listfile = kwargs.get('listfile', None)
    
    basename = os.path.basename(infile)
    SceneID = basename[:21]
    NIRSWIR12 = coeffdict[basename[:3]]['NIRSWIR12']
    GRNIR = coeffdict[basename[:3]]['GRNIR']
    landsat = basename[2:3]
    if not cfmaskfile:
        cfmaskfile = os.path.join(fmaskdir, basename.replace('_ref_ITM', '_cfmask'))
        if not os.access(cfmaskfile, os.F_OK):
            cfmaskfile = cfmaskfile.replace('_cfmask', '_fmask')
            if not os.access(cfmaskfile, os.F_OK):
                print("There is no Fmask file for this scene, returning.")
                logerror(cfmaskfile, 'File missing.')
                if listfile:
                    ESPAreprocess(SceneID, listfile)
                return False, 'No Fmask'
    elif not fmaskdir and not cfmaskfile:
        print("Neither 'fmask' nor 'fmaskdir' have been defined for this scene, returning.")
        logerror(cfmaskfile, 'fmask or cfmask not defined.')
        return False, 'No Fmask'
    URI = os.path.join(outdir, basename.replace('_ref_ITM', '_DT4class'))
    if URI.endswith('.vrt'):
        URI = URI.replace('.vrt', '.dat')
    if os.access(URI, os.F_OK):
        if overwrite:
            print('Found existing output file, deleting associated files and overwriting.')
            files = glob.glob(URI.replace('.dat', '.*'))
            for f in files:
                os.remove(f)
        else:
            print('Found existing output file, skipping.')
            return False, 'Output exists'
  
    # Open Fmask file and use data to determine if scene is worth executing decision tree
    print("Found Fmask file {}, determining if scene is to be processed.".format(os.path.basename(cfmaskfile)))
    try: # Master Yoda: No. Try not. Do... or do not. There is no try.
        cfmask = gdal.Open(cfmaskfile)
        cfgt = cfmask.GetGeoTransform()
        cfmaskdata = cfmask.GetRasterBand(1).ReadAsArray()
        gooddata = np.sum(numexpr.evaluate("(cfmaskdata == 0)"))
        if gooddata < minpixels:
            print('There are an insufficient number of clear land pixels in this scene, returning.')
            cfmask = None
            gooddata = None
            return False, 'Insufficient pixels'
        else:
            print('A sufficient number of clear land pixels have been found in the scene, processing.')
            gooddata = None
    except Exception as e:
        print('There was an error in the Fmask file, logging and skipping scene: {}'.format(e))
        logerror(cfmaskfile, e) 
        if listfile:
            ESPAreprocess(SceneID, listfile)
        return False, 'Fmask error'
    try:
        acqtime = ''
        # Open main data set
        raster = gdal.Open(infile)
        
        # Get data acquisition time 
        if infile.endswith('.dat'):
            hdr = infile.replace('.dat', '.hdr')
        else:
            flist = glob.glob(os.path.join(ieo.srdir, 'L*{}.dat'.format(basename[9:21])))
            if len(flist) > 0:
                hdr = flist[0].replace('.dat', '.hdr')
            acqtime = '' # Attempt to extract acquisition time data from ENVI header of input file
        
            with open(hdr, 'r') as lines:
                for line in lines:
                    if 'acquisition time' in line:
                        acqtime = line
        if acqtime == '':
            datetuple = datetime.datetime.strptime(basename[9:16], '%Y%j')
            acqtime =  'acquisition time = {}T11:30:00Z\n'.format(datetuple.strftime('%Y-%m-%d'))
        
        # Get file geometry
        geoTrans = raster.GetGeoTransform()
        ns = cfmask.RasterXSize
        nl = cfmask.RasterYSize
        
        if landsat == '8': # bands += 1
            blue = raster.GetRasterBand(2).ReadAsArray()
            green  =raster.GetRasterBand(3).ReadAsArray()
            red = raster.GetRasterBand(4).ReadAsArray()
            NIR = raster.GetRasterBand(5).ReadAsArray()
            SWIR1 = raster.GetRasterBand(6).ReadAsArray()
            SWIR2 = raster.GetRasterBand(7).ReadAsArray()
        else:
            blue = raster.GetRasterBand(1).ReadAsArray()
            green = raster.GetRasterBand(2).ReadAsArray()
            red = raster.GetRasterBand(3).ReadAsArray()
            NIR = raster.GetRasterBand(4).ReadAsArray()
            SWIR1 = raster.GetRasterBand(5).ReadAsArray()
            SWIR2 = raster.GetRasterBand(6).ReadAsArray()
    
        # Execute decision tree
        data = np.zeros((nl, ns), dtype = np.uint8)
        goodpixels = np.zeros((nl, ns), dtype = np.uint8) 
        cfmaskdata[numexpr.evaluate("(cfmaskdata == 0) & ((blue <= 0) | (blue >= 10000) | (green <= 0) | (green >= 10000) | (red <= 0) | (red >= 10000) | (NIR <= 0) | (NIR >= 10000) | (SWIR1 <= 0) | (SWIR1 >= 10000) | (SWIR2 <= 0) | (SWIR2 >= 10000))")] = 5 # Mask to eliminate bad pixels not caught by Fmask
        
        data[numexpr.evaluate("((green > NIR) | (red > NIR)) & (cfmaskdata == 0)")] = 1 # Water
        data[numexpr.evaluate("(blue < 1000) & (green < 1000) & (red < 1000) & (NIR < 1000) & (SWIR1 < 1000) & (SWIR2 < 1000) & (cfmaskdata == 0) & (data == 0)")] = 2 # Urban
        data[numexpr.evaluate("((green > blue) & (green > red) & (green*4 < NIR) & (NIR > SWIR1) & (((NIR + SWIR2) * NIRSWIR12 -  SWIR1) > 0) & (NIR < foresttograss) & (cfmaskdata == 0)) & (data == 0)")] = 8 # Mature forest
        data[numexpr.evaluate("((green > blue) & (green > red) & (green*4 < NIR) & (NIR > SWIR1) & (((NIR + SWIR2) * NIRSWIR12 -  SWIR1) <= 0) & (NIR < foresttograss) & (cfmaskdata == 0)) & (data == 0)")] = 9 # Possible forest or green heath
        data[numexpr.evaluate("((green > blue) & (green > red) & (green*4 < NIR) & (NIR >= foresttograss) & (((NIR + SWIR2) * NIRSWIR12 -  SWIR1) > 0) & (cfmaskdata == 0)) & (data == 0)")] = 6 # Grassland or cropland
        data[numexpr.evaluate("(((((green + NIR) * GRNIR -  red) > 0)) & (((NIR + SWIR2) * NIRSWIR12 -  SWIR1) > 0) & (cfmaskdata == 0)) & (data == 0)")] = 7 # Young forest
        data[numexpr.evaluate("(((((green + NIR) * GRNIR -  red) > 0)) & (((NIR + SWIR2) * NIRSWIR12 -  SWIR1) <= 0) & (NIR > SWIR1) & (cfmaskdata == 0)) & (data == 0)")] = 5 # Heath
        data[numexpr.evaluate("(((((green + NIR) * GRNIR -  red) <= 0)) & (red < 1000) & (cfmaskdata == 0)) & (data == 0)")] = 3 # Bog
        data[numexpr.evaluate("(((((((green + NIR) * GRNIR -  red) <= 0)) & (red >= 1000)) | (((((green + NIR) * GRNIR -  red) > 0)) & (((NIR + SWIR2) * NIRSWIR12 -  SWIR1) <= 0))) & (cfmaskdata == 0)) & (data == 0)")] = 4 # Bare soil
    except Exception as e:
        print('There was an error with the reflectance data file, logging and skipping scene: {}'.format(e))
        logerror(infile, e)
        return False, 'Processing error'
    
    # Write output data to disk
    print('Writing data to disk.')
    parentrasters = [infile, cfmaskfile]
    writedata(data, 'DT4', geoTrans, foresttograss = foresttograss, acqtime = acqtime, SceneID = SceneID, outdir = outdir, rasters = parentrasters)
    
    # Close open files
    data = None
    raster = None
    cfmask = None
    print("Scene has been classified.")
    return True, 'Success'


def DT4a(infile, outdir, minpixels, *args, **kwargs):
    
    # By Guy Serbin, Spatial Analysis Unit, REDP, Teagasc National Food Research Centre, Ashtown, Dublin 15, Ireland.
    # This file will read in a Landsat 4 TM - 8 OLI file and perform a decision tree classification on it.
    # 
    # Variables:
    # infile - full path and filename of input reflectance file.
    # maskdir - directory containing fmask files
    # outdir - directory to output classifications
    # minpixels - minimum number of cloud-free land pizels needed for the analysis
    # overwrite - if set, overwrite any existing files, otherwise skip.
    # 
    # This code was shamelessly adapted from an example in the ENVI help file.
    # This code makes use of the ENVI 5.x API.  It will not work in ealier versions.
    
    cfmaskfile = kwargs.get('fmask', None)
    fmaskdir = kwargs.get('fmaskdir', ieo.fmaskdir)
    overwrite = kwargs.get('overwrite', margs.overwrite)
    listfile = kwargs.get('listfile', None)
    minforesttograss = kwargs.get('minforesttograss', margs.minforesttograss)
    maxforesttograss = kwargs.get('maxforesttograss', margs.maxforesttograss)
    
    basename = os.path.basename(infile)
    SceneID = basename[:21]
    NIRSWIR12 = coeffdict[basename[:3]]['NIRSWIR12']
    GRNIR = coeffdict[basename[:3]]['GRNIR']
    landsat = basename[2:3]
    if not cfmaskfile:
        cfmaskfile = os.path.join(fmaskdir, basename.replace('_ref_ITM', '_cfmask'))
        if not os.access(cfmaskfile, os.F_OK):
            cfmaskfile = cfmaskfile.replace('_cfmask', '_fmask')
            if not os.access(cfmaskfile, os.F_OK):
                print("There is no Fmask file for this scene, returning.")
                logerror(cfmaskfile, 'File missing.')
                if listfile:
                    ESPAreprocess(SceneID, listfile)
                return False, 'No Fmask'
    elif not fmaskdir and not cfmaskfile:
        print("Neither 'fmask' nor 'fmaskdir' have been defined for this scene, returning.")
        logerror(cfmaskfile, 'fmask or cfmask not defined.')
        return False, 'No Fmask'
    URI = os.path.join(outdir, basename.replace('_ref_ITM', '_DT4class'))
    if URI.endswith('.vrt'):
        URI = URI.replace('.vrt', '.dat')
    if os.access(URI, os.F_OK):
        if overwrite:
            print('Found existing output file, deleting associated files and overwriting.')
            files = glob.glob(URI.replace('.dat', '.*'))
            for f in files:
                os.remove(f)
        else:
            print('Found existing output file, skipping.')
            return False, 'Output exists'
  
    # Open Fmask file and use data to determine if scene is worth executing decision tree
    print("Found Fmask file {}, determining if scene is to be processed.".format(os.path.basename(cfmaskfile)))
    try: # Master Yoda: No. Try not. Do... or do not. There is no try.
        cfmask = gdal.Open(cfmaskfile)
        cfgt = cfmask.GetGeoTransform()
        cfmaskdata = cfmask.GetRasterBand(1).ReadAsArray()
        gooddata = np.sum(numexpr.evaluate("(cfmaskdata == 0)"))
        if gooddata < minpixels:
            print('There are an insufficient number of clear land pixels in this scene, returning.')
            cfmask = None
            gooddata = None
            return False, 'Insufficient pixels'
        else:
            print('A sufficient number of clear land pixels have been found in the scene, processing.')
            gooddata = None
    except Exception as e:
        print('There was an error in the Fmask file, logging and skipping scene: {}'.format(e))
        logerror(cfmaskfile, e) 
        if listfile:
            ESPAreprocess(SceneID, listfile)
        return False, 'Fmask error'
    try:
        acqtime = ''
        # Open main data set
        raster = gdal.Open(infile)
        
        # Get data acquisition time 
        if infile.endswith('.dat'):
            hdr = infile.replace('.dat', '.hdr')
        else:
            flist = glob.glob(os.path.join(ieo.srdir, 'L*{}.dat'.format(basename[9:21])))
            if len(flist) > 0:
                hdr = flist[0].replace('.dat', '.hdr')
            acqtime = '' # Attempt to extract acquisition time data from ENVI header of input file
        
            with open(hdr, 'r') as lines:
                for line in lines:
                    if 'acquisition time' in line:
                        acqtime = line
        if acqtime == '':
            datetuple = datetime.datetime.strptime(basename[9:16], '%Y%j')
            acqtime =  'acquisition time = {}T11:30:00Z\n'.format(datetuple.strftime('%Y-%m-%d'))
        
        # Get file geometry
        geoTrans = raster.GetGeoTransform()
        ns = cfmask.RasterXSize
        nl = cfmask.RasterYSize
        
        if landsat == '8': # bands += 1
            blue = raster.GetRasterBand(2).ReadAsArray()
            green  =raster.GetRasterBand(3).ReadAsArray()
            red = raster.GetRasterBand(4).ReadAsArray()
            NIR = raster.GetRasterBand(5).ReadAsArray()
            SWIR1 = raster.GetRasterBand(6).ReadAsArray()
            SWIR2 = raster.GetRasterBand(7).ReadAsArray()
        else:
            blue = raster.GetRasterBand(1).ReadAsArray()
            green = raster.GetRasterBand(2).ReadAsArray()
            red = raster.GetRasterBand(3).ReadAsArray()
            NIR = raster.GetRasterBand(4).ReadAsArray()
            SWIR1 = raster.GetRasterBand(5).ReadAsArray()
            SWIR2 = raster.GetRasterBand(6).ReadAsArray()
    
        # Execute decision tree
        data = np.zeros((nl, ns), dtype = np.uint8)
        goodpixels = np.zeros((nl, ns), dtype = np.uint8) 
        cfmaskdata[numexpr.evaluate("(cfmaskdata == 0) & ((blue <= 0) | (blue >= 10000) | (green <= 0) | (green >= 10000) | (red <= 0) | (red >= 10000) | (NIR <= 0) | (NIR >= 10000) | (SWIR1 <= 0) | (SWIR1 >= 10000) | (SWIR2 <= 0) | (SWIR2 >= 10000))")] = 5 # Mask to eliminate bad pixels not caught by Fmask
        
        data[numexpr.evaluate("((green > NIR) | (red > NIR)) & (cfmaskdata == 0)")] = 1 # Water
        data[numexpr.evaluate("(blue < 1000) & (green < 1000) & (red < 1000) & (NIR < 1000) & (SWIR1 < 1000) & (SWIR2 < 1000) & (cfmaskdata == 0) & (data == 0)")] = 2 # Urban
        data[numexpr.evaluate("((green > blue) & (green > red) & (green*4 < NIR) & (NIR > SWIR1) & (((NIR + SWIR2) * NIRSWIR12 -  SWIR1) > 0) & (NIR < minforesttograss) & (cfmaskdata == 0)) & (data == 0)")] = 8 # Mature forest
        data[numexpr.evaluate("((green > blue) & (green > red) & (green*4 < NIR) & (NIR > SWIR1) & (((NIR + SWIR2) * NIRSWIR12 -  SWIR1) <= 0) & (NIR < minforesttograss) & (cfmaskdata == 0)) & (data == 0)")] = 9 # Possible forest or green heath
        data[numexpr.evaluate("((green > blue) & (green > red) & (green*4 < NIR) & (NIR > SWIR1) & (((NIR + SWIR2) * NIRSWIR12 -  SWIR1) > 0) & (NIR < maxforesttograss) & (cfmaskdata == 0)) & (data == 0)")] = 10 # Mature forest or crop confusion
        data[numexpr.evaluate("((green > blue) & (green > red) & (green*4 < NIR) & (NIR > SWIR1) & (((NIR + SWIR2) * NIRSWIR12 -  SWIR1) <= 0) & (NIR < maxforesttograss) & (cfmaskdata == 0)) & (data == 0)")] = 11 # Possible forest or green heath or crop confusion
        data[numexpr.evaluate("((green > blue) & (green > red) & (green*4 < NIR) & (NIR >= maxforesttograss) & (((NIR + SWIR2) * NIRSWIR12 -  SWIR1) > 0) & (cfmaskdata == 0)) & (data == 0)")] = 6 # Grassland or cropland
        data[numexpr.evaluate("(((((green + NIR) * GRNIR -  red) > 0)) & (((NIR + SWIR2) * NIRSWIR12 -  SWIR1) > 0) & (cfmaskdata == 0)) & (data == 0)")] = 7 # Young forest
        data[numexpr.evaluate("(((((green + NIR) * GRNIR -  red) > 0)) & (((NIR + SWIR2) * NIRSWIR12 -  SWIR1) <= 0) & (NIR > SWIR1) & (cfmaskdata == 0)) & (data == 0)")] = 5 # Heath
        data[numexpr.evaluate("(((((green + NIR) * GRNIR -  red) <= 0)) & (red < 1000) & (cfmaskdata == 0)) & (data == 0)")] = 3 # Bog
        data[numexpr.evaluate("(((((((green + NIR) * GRNIR -  red) <= 0)) & (red >= 1000)) | (((((green + NIR) * GRNIR -  red) > 0)) & (((NIR + SWIR2) * NIRSWIR12 -  SWIR1) <= 0))) & (cfmaskdata == 0)) & (data == 0)")] = 4 # Bare soil
    except Exception as e:
        print('There was an error with the reflectance data file, logging and skipping scene: {}'.format(e))
        logerror(infile, e)
        return False, 'Processing error'
    
    # Write output data to disk
    print('Writing data to disk.')
    parentrasters = [infile, cfmaskfile]
    writedata(data, 'DT4a', geoTrans, minforesttograss = minforesttograss, maxforesttograss = maxforesttograss, acqtime = acqtime, SceneID = SceneID, outdir = outdir, rasters = parentrasters)
    
    # Close open files
    data = None
    raster = None
    cfmask = None
    print("Scene has been classified.")
    return True, 'Success'


def DT4b(infile, outdir, minpixels, *args, **kwargs):
    
    # By Guy Serbin, Spatial Analysis Unit, REDP, Teagasc National Food Research Centre, Ashtown, Dublin 15, Ireland.
    # This funtion is modified from DT4a with corrections for estimated continuum removal values. It will process a LEDAPS-processed Landsat 4 TM - 8 OLI file and perform a decision tree classification on it.
    # 
    # Variables:
    # infile - full path and filename of input reflectance file.
    # maskdir - directory containing fmask files
    # outdir - directory to output classifications
    # minpixels - minimum number of cloud-free land pizels needed for the analysis
    # overwrite - if set, overwrite any existing files, otherwise skip.
    
    cfmaskfile = kwargs.get('fmask', None)
    fmaskdir = kwargs.get('fmaskdir', ieo.fmaskdir)
    overwrite = kwargs.get('overwrite', margs.overwrite)
    listfile = kwargs.get('listfile', None)
    minforesttograss = kwargs.get('minforesttograss', margs.minforesttograss)
    maxforesttograss = kwargs.get('maxforesttograss', margs.maxforesttograss)
    
    basename = os.path.basename(infile)
    SceneID = basename[:21]
    NIRSWIR12 = coeffdict[basename[:3]]['NIRSWIR12']
    GRNIR = coeffdict[basename[:3]]['GRNIR']
    landsat = basename[2:3]
    if not cfmaskfile:
        cfmaskfile = os.path.join(fmaskdir, basename.replace('_ref_ITM', '_cfmask'))
        if not os.access(cfmaskfile, os.F_OK):
            cfmaskfile = cfmaskfile.replace('_cfmask', '_fmask')
            if not os.access(cfmaskfile, os.F_OK):
                print("There is no Fmask file for this scene, returning.")
                logerror(cfmaskfile, 'File missing.')
                if listfile:
                    ESPAreprocess(SceneID, listfile)
                return False, 'No Fmask'
    elif not fmaskdir and not cfmaskfile:
        print("Neither 'fmask' nor 'fmaskdir' have been defined for this scene, returning.")
        logerror(cfmaskfile, 'fmask or cfmask not defined.')
        return False, 'No Fmask'
    URI = os.path.join(outdir, basename.replace('_ref_ITM', '_DT4class'))
    if URI.endswith('.vrt'):
        URI = URI.replace('.vrt', '.dat')
    if os.access(URI, os.F_OK):
        if overwrite:
            print('Found existing output file, deleting associated files and overwriting.')
            files = glob.glob(URI.replace('.dat', '.*'))
            for f in files:
                os.remove(f)
        else:
            print('Found existing output file, skipping.')
            return False, 'Output exists'
  
    # Open Fmask file and use data to determine if scene is worth executing decision tree
    print("Found Fmask file {}, determining if scene is to be processed.".format(os.path.basename(cfmaskfile)))
    try: # Master Yoda: No. Try not. Do... or do not. There is no try.
        cfmask = gdal.Open(cfmaskfile)
        cfgt = cfmask.GetGeoTransform()
        cfmaskdata = cfmask.GetRasterBand(1).ReadAsArray()
        gooddata = np.sum(numexpr.evaluate("(cfmaskdata == 0)"))
        if gooddata < minpixels:
            print('There are an insufficient number of clear land pixels in this scene, returning.')
            cfmask = None
            gooddata = None
            return False, 'Insufficient pixels'
        else:
            print('A sufficient number of clear land pixels have been found in the scene, processing.')
            gooddata = None
    except Exception as e:
        print('There was an error in the Fmask file, logging and skipping scene: {}'.format(e))
        logerror(cfmaskfile, e) 
        if listfile:
            ESPAreprocess(SceneID, listfile)
        return False, 'Fmask error'
    try:
        acqtime = ''
        # Open main data set
        raster = gdal.Open(infile)
        
        # Get data acquisition time 
        if infile.endswith('.dat'):
            hdr = infile.replace('.dat', '.hdr')
        else:
            flist = glob.glob(os.path.join(ieo.srdir, 'L*{}.dat'.format(basename[9:21])))
            if len(flist) > 0:
                hdr = flist[0].replace('.dat', '.hdr')
            acqtime = '' # Attempt to extract acquisition time data from ENVI header of input file
        
            with open(hdr, 'r') as lines:
                for line in lines:
                    if 'acquisition time' in line:
                        acqtime = line
        if acqtime == '':
            datetuple = datetime.datetime.strptime(basename[9:16], '%Y%j')
            acqtime =  'acquisition time = {}T11:30:00Z\n'.format(datetuple.strftime('%Y-%m-%d'))
        
        # Get file geometry
        geoTrans = raster.GetGeoTransform()
        ns = cfmask.RasterXSize
        nl = cfmask.RasterYSize
        
        if landsat == '8': # bands += 1
            blue = raster.GetRasterBand(2).ReadAsArray()
            green  =raster.GetRasterBand(3).ReadAsArray()
            red = raster.GetRasterBand(4).ReadAsArray()
            NIR = raster.GetRasterBand(5).ReadAsArray()
            SWIR1 = raster.GetRasterBand(6).ReadAsArray()
            SWIR2 = raster.GetRasterBand(7).ReadAsArray()
        else:
            blue = raster.GetRasterBand(1).ReadAsArray()
            green = raster.GetRasterBand(2).ReadAsArray()
            red = raster.GetRasterBand(3).ReadAsArray()
            NIR = raster.GetRasterBand(4).ReadAsArray()
            SWIR1 = raster.GetRasterBand(5).ReadAsArray()
            SWIR2 = raster.GetRasterBand(6).ReadAsArray()
    
        # Execute decision tree
        data = np.zeros((nl, ns), dtype = np.uint8)
        goodpixels = np.zeros((nl, ns), dtype = np.uint8) 
        cfmaskdata[numexpr.evaluate("(cfmaskdata == 0) & ((blue <= 0) | (blue >= 10000) | (green <= 0) | (green >= 10000) | (red <= 0) | (red >= 10000) | (NIR <= 0) | (NIR >= 10000) | (SWIR1 <= 0) | (SWIR1 >= 10000) | (SWIR2 <= 0) | (SWIR2 >= 10000))")] = 5 # Mask to eliminate bad pixels not caught by Fmask
        
        data[numexpr.evaluate("((green > NIR) | (red > NIR)) & (cfmaskdata == 0)")] = 1 # Water
        data[numexpr.evaluate("(blue < 1000) & (green < 1000) & (red < 1000) & (NIR < 1000) & (SWIR1 < 1000) & (SWIR2 < 1000) & (cfmaskdata == 0) & (data == 0)")] = 2 # Urban
        data[numexpr.evaluate("((green > blue) & (green > red) & (green*4 < NIR) & (NIR > SWIR1) & ((SWIR2 - (SWIR2 - NIR) * NIRSWIR12 -  SWIR1) > 0) & (NIR < minforesttograss) & (cfmaskdata == 0)) & (data == 0)")] = 8 # Mature forest
        data[numexpr.evaluate("((green > blue) & (green > red) & (green*4 < NIR) & (NIR > SWIR1) & ((SWIR2 - (SWIR2 - NIR) * NIRSWIR12 -  SWIR1) <= 0) & (NIR < minforesttograss) & (cfmaskdata == 0)) & (data == 0)")] = 9 # Possible forest or green heath
        data[numexpr.evaluate("((green > blue) & (green > red) & (green*4 < NIR) & (NIR > SWIR1) & ((SWIR2 - (SWIR2 - NIR) * NIRSWIR12 -  SWIR1) > 0) & (NIR < maxforesttograss) & (cfmaskdata == 0)) & (data == 0)")] = 10 # Mature forest or crop confusion
        data[numexpr.evaluate("((green > blue) & (green > red) & (green*4 < NIR) & (NIR > SWIR1) & ((SWIR2 - (SWIR2 - NIR) * NIRSWIR12 -  SWIR1) <= 0) & (NIR < maxforesttograss) & (cfmaskdata == 0)) & (data == 0)")] = 11 # Possible forest or green heath or crop confusion
        data[numexpr.evaluate("((green > blue) & (green > red) & (green*4 < NIR) & (NIR >= maxforesttograss) & ((SWIR2 - (SWIR2 - NIR) * NIRSWIR12 -  SWIR1) > 0) & (cfmaskdata == 0)) & (data == 0)")] = 6 # Grassland or cropland
        data[numexpr.evaluate("(((((NIR - green) * GRNIR + green -  red) > 0)) & ((SWIR2 - (SWIR2 - NIR) * NIRSWIR12 -  SWIR1) > 0) & (cfmaskdata == 0)) & (data == 0)")] = 7 # Young forest
        data[numexpr.evaluate("(((((NIR - green) * GRNIR + green -  red) > 0)) & ((SWIR2 - (SWIR2 - NIR) * NIRSWIR12 -  SWIR1) <= 0) & (NIR > SWIR1) & (cfmaskdata == 0)) & (data == 0)")] = 5 # Heath
        data[numexpr.evaluate("(((((NIR - green) * GRNIR + green -  red) <= 0)) & (red < 1000) & (cfmaskdata == 0)) & (data == 0)")] = 3 # Bog
        data[numexpr.evaluate("(((((((NIR - green) * GRNIR + green -  red) <= 0)) & (red >= 1000)) | (((((NIR - green) * GRNIR + green -  red) > 0)) & ((SWIR2 - (SWIR2 - NIR) * NIRSWIR12 -  SWIR1) <= 0))) & (cfmaskdata == 0)) & (data == 0)")] = 4 # Bare soil
    except Exception as e:
        print('There was an error with the reflectance data file, logging and skipping scene: {}'.format(e))
        logerror(infile, e)
        return False, 'Processing error'
    
    # Write output data to disk
    print('Writing data to disk.')
    parentrasters = [infile, cfmaskfile]
    writedata(data, 'DT4b', geoTrans, minforesttograss = minforesttograss, maxforesttograss = maxforesttograss, acqtime = acqtime, SceneID = SceneID, outdir = outdir, rasters = parentrasters)
    
    # Close open files
    data = None
    raster = None
    cfmask = None
    print("Scene has been classified.")
    return True, 'Success'


def calcprobabilityraster(tile, scenelist, foresttograss, year, *args, **kwargs):
    numyears = kwargs.get('numyears', 1)
    overwrite = kwargs.get('overwrite', margs.overwrite)
    dt4a = kwargs.get('dt4a', margs.dt4a)
    dt4b = kwargs.get('dt4b', margs.dt4b)
    if margs.dt4a:
        outsubdir = 'dt4a'
    elif margs.dt4b:
        outsubdir = 'dt4b'
    else:
        outsubdir = str(foresttograss)
#    if foresttograss:
#        indir = kwargs.get('indir', os.path.join(config['DEFAULT']['baseoutputdir'], str(foresttograss)))
#    else:
    indir = kwargs.get('indir', os.path.join(config['DEFAULT']['baseoutputdir'], outsubdir))
    outdir = kwargs.get('outdir', os.path.join(indir, 'Probability'))
    numyears = kwargs.get('numyears', 1)
    
    if not os.path.isdir(indir):
        print('Error: input directory is missing: {}'.format(indir))
        return None
        
    if not os.access(outdir, os.F_OK):
        os.mkdir(outdir)
    
    rasters = []
    for y in range(numyears):
        for scene in scenelist:
            if str(year + y) in scene:
                rasters.append(scene)
    
    if len(rasters) > 0:
        tilename = tile.GetField('Tile')
        headerdict = getheaderdict(rastertype = 'Highpos', year = year, tilename = tilename, foresttograss = foresttograss)
        maj = os.path.join(outdir, headerdict['defaultbasefilename'])
        if not overwrite and os.access(maj, os.F_OK):
            print('The pass command will be activated for calcprobabilityraster().')
            pass
        else:
            numfiles = len(rasters)
            tilegeom = tile.GetGeometryRef()
            minX, maxX, minY, maxY = tilegeom.GetEnvelope()
            geoTrans = (minX, 30, 0.0, maxY, 0.0, -30)
            cols = int((maxX - minX) / 30) # number of samples or columns
            rows = int((maxY - minY) / 30) # number of lines or rows
            print('Found {} rasters, calculating majority land class for year {} and writing to: {}'.format(numfiles, year, maj))
            dims = [minX, maxY, maxX, minY]
            
            print('Output columns: {}'.format(cols))
            print('Output rows: {}'.format(rows))
            forestry = np.zeros((rows, cols), dtype = np.uint8)
            cropgrass = np.zeros((rows, cols), dtype = np.uint8)
            bogheath = np.zeros((rows, cols), dtype = np.uint8)
            heathforest = np.zeros((rows, cols), dtype = np.uint8)
            urban = np.zeros((rows, cols), dtype = np.uint8)
            water = np.zeros((rows, cols), dtype = np.uint8)
            if not foresttograss:
                forestcrop = np.zeros((rows, cols), dtype = np.uint8)
                forestcropheath = np.zeros((rows, cols), dtype = np.uint8)
            denominator = np.zeros((rows, cols), dtype = np.uint8)
            for i in range(numfiles):
                r = rasters[i]
                print('Opening file: {}'.format(os.path.basename(r)))
                src_ds = gdal.Open(r)
                gt = src_ds.GetGeoTransform()
                extent = [gt[0], gt[3], gt[0] + gt[1] * src_ds.RasterXSize, gt[3] + gt[5] * src_ds.RasterYSize]
#                if checkintersect(tilegeom, extent):
                ul = [max(dims[0], extent[0]), min(dims[1], extent[1])]
                lr = [min(dims[2], extent[2]), max(dims[3], extent[3])]
                px, py = world2Pixel(geoTrans, ul[0], ul[1])
                if px < 0:
                    px = 0
                if py < 0:
                    py = 0
                plx, ply = world2Pixel(geoTrans, lr[0], lr[1])
                if plx >= extent[0]:
                    plx = extent[0]-1
                if ply >= extent[1]:
                    ply = extent[1]-1
                pX, pY = pixel2world(geoTrans, px, py)
                plX, plY = pixel2world(geoTrans, plx, ply)
                ulx,uly = world2Pixel(gt, pX, pY)
                if ulx < 0:
                    ulx = 0
                lrx,lry = world2Pixel(gt, plX, plY)
                if lrx >= src_ds.RasterXSize:
                    lrx = src_ds.RasterXSize - 1 
                if uly >= src_ds.RasterYSize:
                    uly = src_ds.RasterYSize - 1
                if lry < 0:
                    lry = 0 
                
                dx = plx-px + 1
                dy = ply-py + 1
                band = np.zeros((rows, cols), dtype = np.uint8)
                band[py:ply, px:plx] = src_ds.GetRasterBand(1).ReadAsArray(ulx, uly, dx - 1, dy - 1)
                
                forestry[numexpr.evaluate('((band == 7) | (band == 8))')] += 1
                cropgrass[numexpr.evaluate('((band == 4) | (band == 6))')] += 1
                bogheath[numexpr.evaluate('((band == 3) | (band == 5))')] += 1
                heathforest[numexpr.evaluate('(band == 9)')] += 1
                urban[numexpr.evaluate('(band == 2)')] += 1
                water[numexpr.evaluate('(band == 1)')] += 1
                if not foresttograss:
                    forestcrop[numexpr.evaluate('(band == 10)')] += 1
                    forestcropheath[numexpr.evaluate('(band == 11)')] += 1
                denominator[numexpr.evaluate('((band >= 1) & (band <= 11) )')] += 1
                del band
                del src_ds
                
            eval_ind = numexpr.evaluate('(bogheath == forestry)')
            bogforest = np.zeros((rows, cols), dtype = np.int8)
            bogforest[eval_ind] = (np.add(bogheath[eval_ind], forestry[eval_ind])) #.astype(np.int16)
#            writedata(bogforest, 'pct', geoTrans, foresttograss = foresttograss, year = year, tilename = tilename, outdir = outdir, classname = 'bogforest', rasters = rasters)
            eval_ind = None
            
            eval_ind = numexpr.evaluate('(cropgrass == forestry)')
            cropforest = np.zeros((rows, cols), dtype = np.int8)
            cropforest[eval_ind] = (np.add(cropgrass[eval_ind], forestry[eval_ind])) #.astype(np.int16)
#            writedata(cropforest, 'pct', geoTrans, foresttograss = foresttograss, year = year, tilename = tilename, outdir = outdir, classname = 'cropforest', rasters = rasters)
            eval_ind = None
            
            cropbog = np.zeros((rows, cols), dtype = np.int8)
            eval_ind = numexpr.evaluate('(cropgrass == bogheath)')
            cropbog[eval_ind] = (np.add(cropgrass[eval_ind], bogheath[eval_ind])) #.astype(np.int16)
#            writedata(cropbog, 'pct', geoTrans, foresttograss = foresttograss, year = year, tilename = tilename, outdir = outdir, classname = 'cropbog', rasters = rasters)            
            eval_ind = None
            
#            denominator = np.sum([forestry + cropgrass + bogheath + heathforest + urban + water],axis=0).astype(dtype = np.float32)
            writedata(denominator.astype(np.int16), 'denominator', geoTrans, foresttograss = foresttograss, year = year, tilename = tilename, outdir = outdir, rasters = rasters)
            
            eval_ind = numexpr.evaluate('(denominator > 0)')
            
            if foresttograss:
                rastersets = [forestry, cropgrass, bogheath, heathforest, urban, water, bogforest, cropforest, cropbog]
                rasternames = ['forestry', 'cropgrass', 'bogheath', 'heathforest', 'urban', 'water', 'bogforest', 'cropforest', 'cropbog']
            else:
                rastersets = [forestry, cropgrass, bogheath, heathforest, urban, water, bogforest, cropforest, cropbog, forestcrop, forestcropheath]
                rasternames = ['forestry', 'cropgrass', 'bogheath', 'heathforest', 'urban', 'water', 'bogforest', 'cropforest', 'cropbog', 'forestcrop', 'forestcropheath']
            
            for data, dataname in zip(rastersets, rasternames):
                outdata = np.zeros((rows, cols), dtype = np.uint16)
                outdata[eval_ind] = (10000 * np.divide(data[eval_ind].astype(np.float32), denominator[eval_ind].astype(dtype = np.float32))).astype(np.int16)
                writedata(outdata, 'pct', geoTrans, foresttograss = foresttograss, year = year, tilename = tilename, outdir = outdir, classname = dataname, rasters = rasters)
                del outdata
            eval_ind = None
            
#            forestry[eval_ind] = (10000 * np.divide(forestry[eval_ind], denominator[eval_ind])).astype(np.int16)
#            writedata(forestry, 'pct', geoTrans, foresttograss = foresttograss, year = year, tilename = tilename, outdir = outdir, classname = 'forestry', rasters = rasters)
#            
#            cropgrass[eval_ind] = (10000 * np.divide(cropgrass[eval_ind], denominator[eval_ind])).astype(np.int16)
#            writedata(cropgrass, 'pct', geoTrans, foresttograss = foresttograss, year = year, tilename = tilename, outdir = outdir, classname = 'cropgrass', rasters = rasters)
#            
#            bogheath[eval_ind] = (10000 * np.divide(bogheath[eval_ind], denominator[eval_ind])).astype(np.int16)
#            writedata(bogheath, 'pct', geoTrans, foresttograss = foresttograss, year = year, tilename = tilename, outdir = outdir, classname = 'bogheath', rasters = rasters)
#            
#            heathforest[eval_ind] = (10000 * np.divide(heathforest[eval_ind], denominator[eval_ind])).astype(np.int16)
#            writedata(heathforest, 'pct', geoTrans, foresttograss = foresttograss, year = year, tilename = tilename, outdir = outdir, classname = 'heathforest', rasters = rasters)
#            
#            urban[eval_ind] = (10000 * np.divide(urban[eval_ind], denominator[eval_ind])).astype(np.int16)
#            writedata(urban, 'pct', geoTrans, foresttograss = foresttograss, year = year, tilename = tilename, outdir = outdir, classname = 'urban', rasters = rasters)
#            
#            water[eval_ind] = (10000 * np.divide(water[eval_ind], denominator[eval_ind])).astype(np.int16)
#            writedata(water, 'pct', geoTrans, foresttograss = foresttograss, year = year, tilename = tilename, outdir = outdir, classname = 'water', rasters = rasters)
            
            
            if foresttograss:
                highpos = np.argmax([np.zeros((rows, cols), dtype = np.int16), water, urban, cropgrass, bogheath, forestry, heathforest,  cropbog, cropforest, bogforest], axis = 2)
            else:
                highpos = np.argmax([np.zeros((rows, cols), dtype = np.int16), water, urban, cropgrass, bogheath, forestry, heathforest,  cropbog, cropforest, bogforest, forestcrop, forestcropheath], axis = 2)
            writedata(highpos, 'Highpos', geoTrans, foresttograss = foresttograss, year = year, tilename = tilename, outdir = outdir, rasters = rasters)
            del denominator
            del eval_ind
            del forestry
            del cropgrass
            del bogheath
            del heathforest
            del urban
            del water
            del highpos
            del bogforest
            del cropforest
            del cropbog
            del tile
            
    else:
        print('No rasters found for {}'.format(year))
        outdir = None
    return outdir


def Yearlydt4(indir, year, tilename, foresttograss, *args, **kwargs):
    
    # By Guy Serbin, Spatial Analysis Unit, REDP, Teagasc National Food Research Centre, Ashtown, Dublin 15, Ireland.
    # This file will read in a Landsat 4 TM - 8 OLI file and perform a decision tree classification on it.
    # 
    # Variables:
    # infile - full path and filename of input reflectance file.
    # maskdir - directory containing fmask files
    # outdir - directory to output classifications
    # minpixels - minimum number of cloud-free land pizels needed for the analysis
    # [/overwrite] - if set, overwrite any existing files, otherwise skip.
    # 
    # This code was shamelessly adapted from an example in the ENVI help file.
    # This code makes use of the ENVI 5.x API.  It will not work in ealier versions.
    # outdir = kwargs.get('outdir', None)
    yearoffset = kwargs.get('yearoffset', None)
    overwrite = kwargs.get('overwrite', margs.overwrite)
    
    print('Now calculating yearly DT4 classification for tile {}.'.format(tilename))
    
    if yearoffset:
        startyear = year
        endyear = year + yearoffset - 1
        bogheathURI = os.path.join(indir, '{}_pct_{}_{}_{}.dat'.format('bogheath', year, endyear, tilename))
        heathforestURI = os.path.join(indir, '{}_pct_{}_{}_{}.dat'.format('heathforest', year, endyear, tilename))
        bogforestURI = os.path.join(indir, '{}_pct_{}_{}_{}.dat'.format('bogforest', year, endyear, tilename))
        forestryURI = os.path.join(indir, '{}_pct_{}_{}_{}.dat'.format('forestry', year, endyear, tilename))
        cropgrassURI = os.path.join(indir, '{}_pct_{}_{}_{}.dat'.format('cropgrass', year, endyear, tilename))
        urbanURI = os.path.join(indir, '{}_pct_{}_{}_{}.dat'.format('urban', year, endyear, tilename))
        waterURI = os.path.join(indir, '{}_pct_{}_{}_{}.dat'.format('water', year, endyear, tilename))
        URI = os.path.join(indir, '{}_pct_{}_{}_{}.dat'.format('DT4_class', year, endyear, tilename))
    
    else:
        startyear = None
        endyear = None
        bogheathURI = os.path.join(indir, '{}_pct_{}_{}.dat'.format('bogheath', year, tilename))
        heathforestURI = os.path.join(indir, '{}_pct_{}_{}.dat'.format('heathforest', year, tilename))
        bogforestURI = os.path.join(indir, '{}_pct_{}_{}.dat'.format('bogforest', year, tilename))
        forestryURI = os.path.join(indir, '{}_pct_{}_{}.dat'.format('forestry', year, tilename))
        cropgrassURI = os.path.join(indir, '{}_pct_{}_{}.dat'.format('cropgrass', year, tilename))
        urbanURI = os.path.join(indir, '{}_pct_{}_{}.dat'.format('urban', year, tilename))
        waterURI = os.path.join(indir, '{}_pct_{}_{}.dat'.format('water', year, tilename))
        URI = os.path.join(indir, '{}_pct_{}_{}.dat'.format('DT4_class', year, tilename))
        parentrasters = [bogheathURI, heathforestURI, bogforestURI, forestryURI, cropgrassURI, urbanURI, waterURI]
    
    if os.path.exists(URI):
        if overwrite:
            print('Found existing output file, deleting associated files and overwriting.')
            files = glob.glob(URI.replace('.dat', '.*'))
            for f in files:
                os.remove(f)
        else:
            print('Found existing output file, skipping.')
            return        
    
    for file in parentrasters:
        if not os.access(file, os.F_OK):
            print("Returning as file is missing: {}".format(file))
            return
    
    # Open files
    forestryRaster = gdal.Open(forestryURI)
    bogheathRaster = gdal.Open(bogheathURI)
    heathforestRaster = gdal.Open(heathforestURI)
    cropgrassRaster = gdal.Open(cropgrassURI)
    waterRaster = gdal.Open(waterURI)
    urbanRaster = gdal.Open(urbanURI)
    bogforestRaster = gdal.Open(bogforestURI)
    
    # Get file geometry from forestry dataset
    geoTrans = forestryRaster.GetGeoTransform() 
    ns = forestryRaster.RasterXSize
    nl = forestryRaster.RasterYSize
    
    # Get data from open files
    forestry = forestryRaster.GetRasterBand(1).ReadAsArray()
    heathforest = heathforestRaster.GetRasterBand(1).ReadAsArray()
    bogforest = bogforestRaster.GetRasterBand(1).ReadAsArray()
    bogheath = bogheathRaster.GetRasterBand(1).ReadAsArray()
    cropgrass = cropgrassRaster.GetRasterBand(1).ReadAsArray()
    water = waterRaster.GetRasterBand(1).ReadAsArray()
    urban = urbanRaster.GetRasterBand(1).ReadAsArray()
    
    if not foresttograss:
        forestcropURI = os.path.join(indir, '{}_pct_{}_{}.dat'.format('forestcrop', year, tilename))
        forestcropheathURI = os.path.join(indir, '{}_pct_{}_{}.dat'.format('forestcropheath', year, tilename))
        forestcropRaster = gdal.Open(forestcropURI)
        forestcropheathRaster = gdal.Open(forestcropheathURI)
        forestcrop = forestcropRaster.GetRasterBand(1).ReadAsArray()
        forestcropheath = forestcropheathRaster.GetRasterBand(1).ReadAsArray()
        
    # rasters = [water,urban,cropgrass,bogheath,forestry]
    
    # Execute decision tree
    
    eval_ind = numexpr.evaluate("(forestry >= bogheath)")
    eval_ind2 = numexpr.evaluate("(forestry > cropgrass)")
    eval_ind3 = numexpr.evaluate("(forestry < bogheath)")
    eval_ind4 = numexpr.evaluate("((cropgrass < bogheath) & (forestry < bogheath))")
    eval_ind7 = numexpr.evaluate("((cropgrass >= bogheath) & (forestry <= cropgrass))")
    eval_ind5 = numexpr.evaluate("((cropgrass < forestry) & (forestry >= bogheath))")
    eval_ind6 = numexpr.evaluate("(forestry <= cropgrass)")
    eval_ind8 = numexpr.evaluate("((forestry == bogheath) & (forestry == cropgrass))")
    
    forestry[eval_ind] += bogforest[eval_ind]
    forestry[eval_ind] += heathforest[eval_ind]
    bogheath[eval_ind3] += bogforest[eval_ind3]
    bogheath[eval_ind3] += heathforest[eval_ind3]
    
    if not foresttograss:
        forestry[eval_ind2] += forestcrop[eval_ind2]
        forestry[eval_ind5] += forestcropheath[eval_ind5]
        bogheath[eval_ind4] += forestcropheath[eval_ind4]
        bogheath[eval_ind8] += forestcropheath[eval_ind8]
        cropgrass[eval_ind7] += forestcropheath[eval_ind7]
        cropgrass[eval_ind6] += forestcrop[eval_ind6]
        
    eval_ind = None
    eval_ind2 = None
    eval_ind3 = None
    eval_ind4 = None
    eval_ind5 = None
    eval_ind6 = None 
    eval_ind7 = None
    eval_ind8 = None
            
    data = np.zeros((nl, ns), dtype = np.uint8)
    data[numexpr.evaluate("(forestry < bogforest) & (bogforest > bogheath) & (bogforest > cropgrass) & (bogforest > urban) & (bogforest > water) & (data == 0)")] = 8 # bog + forest
    data[numexpr.evaluate("(water > bogheath) & (water > forestry) & (water > urban) & (cropgrass < water) & (data == 0)")] = 1 # water
    data[numexpr.evaluate("(urban > bogheath) & (urban > forestry) & (water < urban) & (cropgrass < urban) & (data == 0)")] = 2 # urban
    data[numexpr.evaluate("(cropgrass > bogheath) & (cropgrass > forestry) & (cropgrass > urban) & (cropgrass > water) & (data == 0)")] = 3 # crop or grass
    data[numexpr.evaluate("(cropgrass < bogheath) & (bogheath > forestry) & (bogheath > urban) & (bogheath > water) & (data == 0)")] = 4 # bog or heath
    data[numexpr.evaluate("(forestry > bogheath) & (cropgrass < forestry) & (forestry > urban) & (forestry > water) & (data == 0)")] = 5 # forestry
    data[numexpr.evaluate("(cropgrass == bogheath) & (bogheath > forestry) & (bogheath > urban) & (bogheath > water) & (data == 0)")] = 6 # crop + bog
    data[numexpr.evaluate("(cropgrass == forestry) & (bogheath < forestry) & (forestry > urban) & (forestry > water) & (data == 0)")] = 7 # crop + forest
    data[numexpr.evaluate("(forestry == bogheath) & (bogheath > cropgrass) & (bogheath > urban) & (bogheath > water) & (data == 0)")] = 8 # bog + forest
    data[numexpr.evaluate("(forestry == urban) & (urban > cropgrass) & (bogheath < urban) & (urban > water) & (data == 0)")] = 9 # forest + urban
    data[numexpr.evaluate("(urban == bogheath) & (bogheath > forestry) & (bogheath > cropgrass) & (bogheath > water) & (data == 0)")] = 10 # bog + urban
    data[numexpr.evaluate("(cropgrass == urban) & (bogheath < urban) & (urban > forestry) & (urban > water) & (data == 0)")] = 11 # crop + urban
    data[numexpr.evaluate("(forestry == water) & (water > cropgrass) & (bogheath < water) & (urban < water) & (data == 0)")] = 12 # forest + water
    data[numexpr.evaluate("(water == bogheath) & (bogheath > forestry) & (bogheath > urban) & (bogheath > cropgrass) & (data == 0)")] = 13 # bog + water
    data[numexpr.evaluate("(cropgrass == water) & (bogheath < water) & (water > forestry) & (urban < water) & (data == 0)")] = 14 # crop + water
    data[numexpr.evaluate("(urban == water) & (water > forestry) & (water > cropgrass) & (bogheath < water) & (data == 0)")] = 15 # urban + water
    data[numexpr.evaluate("((urban > 0.0) | (water > 0.0) | (forestry > 0.0) | (cropgrass > 0.0) | (bogheath > 0.0)) & (data == 0)")] = 16 # three or more classes
    
    # Write output data to disk
    print('Writing data to disk.')
    writedata(data, 'YearlyDT4', geoTrans, foresttograss = foresttograss, year = year, startyear = startyear, endyear = endyear, tilename = tilename, outdir = indir, rasters = parentrasters)
    
    # Closing files
    data = None
    forestryRaster = None
    heathforestRaster = None
    bogheathRaster = None
    cropgrassRaster = None
    urbanRaster = None
    waterRaster = None
    forestcropRaster = None
    forestcropheathraster = None
    eval_ind = None
    print("Scene has been classified.")


def forestryclass(tilename, foresttograss, year, *args, **kwargs):
    dt4a = kwargs.get('dt4a', margs.dt4a)
    dt4b = kwargs.get('dt4b', margs.dt4b)
    if margs.dt4a:
        outsubdir = 'dt4a'
    elif margs.dt4b:
        outsubdir = 'dt4b'
    else:
        outsubdir = str(foresttograss)
#    if foresttograss:
#        indir = kwargs.get('indir', os.path.join(config['DEFAULT']['baseoutputdir'], r'{}\Probability'.format(foresttograss)))
#        outdir = kwargs.get('outdir', os.path.join(config['DEFAULT']['baseoutputdir'], r'{}\Probability\Forestry'.format(foresttograss)))
#    else:
    indir = kwargs.get('indir', os.path.join(config['DEFAULT']['baseoutputdir'], r'{}\Probability'.format(outsubdir)))
    outdir = kwargs.get('outdir', os.path.join(config['DEFAULT']['baseoutputdir'], r'{}\Probability\Forestry'.format(outsubdir)))
    print('Now calculating forestry classes for tile {}.'.format(tilename))
    if not os.path.exists(outdir):
        os.mkdir(outdir)
    infile = kwargs.get('infile', os.path.join(indir, 'DT4_class_{}_{}.dat'.format(year, tilename)))
    overwrite = kwargs.get('overwrite', margs.overwrite)
    headerdict = getheaderdict(rastertype = 'ForestryClass', year = year, tilename = tilename, foresttograss = foresttograss)
    outfile = os.path.join(outdir, headerdict['defaultbasefilename'])
    if not overwrite and os.access(outfile, os.F_OK):
        print('{} exists and no overwrite has been set, skipping.'.format(os.path.basename(outfile)))
        return
    remap = [[1, 4, 1], [5, 5, 3], [7, 9, 2], [12, 12, 2], [6, 6, 1], [10, 11, 1], [13, 16, 1]]
    img = gdal.Open(infile)
    band = img.GetRasterBand(1).ReadAsArray()
    dx = band.shape[1]
    dy = band.shape[0]
    geoTrans = img.GetGeoTransform()
    outraster = np.zeros(band.shape, dtype = np.uint8)
    for r in remap:
        a = r[0]
        b = r[1]
        outraster[numexpr.evaluate("(band>=a)&(band<=b)")] = r[2]
    writedata(outraster, 'ForestryClass', geoTrans, foresttograss = foresttograss, year = year, tilename = tilename, outdir = outdir, rasters = [infile])
    band = None
    img = None
    outraster = None


def calcyearlychange(tilename, foresttograss, *args, **kwargs):
    dt4a = kwargs.get('dt4a', margs.dt4a)
    dt4b = kwargs.get('dt4b', margs.dt4b)
    if margs.dt4a:
        outsubdir = 'dt4a'
    elif margs.dt4b:
        outsubdir = 'dt4b'
    else:
        outsubdir = str(foresttograss)
#    if foresttograss:
#        indir = kwargs.get('indir', os.path.join(config['DEFAULT']['baseoutputdir'], r'{}\Probability\Forestry'.format(foresttograss)))
#    else:
    indir = kwargs.get('indir', os.path.join(config['DEFAULT']['baseoutputdir'], r'{}\Probability\Forestry'.format(outsubdir)))
    outdir = kwargs.get('outdir', os.path.join(indir, 'Change'))
    startyear = kwargs.get('startyear', 1984)
    endyear = kwargs.get('endyear', margs.endyear)
    overwrite = kwargs.get('overwrite', margs.overwrite)
    opp = kwargs.get('opp', False)
#    usemaskfile = kwargs.get('usemaskfile', True)
    years = list(range(startyear, endyear + 1))
    
    print('Now calculating yearly change maps for tile {}.'.format(tilename))
    geoTrans = None
    ns = 0
    nl = 0
    pixnum = 1
    
    if not os.access(indir, os.F_OK):
        print('Error: input directory is missing: {}'.format(indir))
        return
    
    print('Reading files from: {}'.format(indir))
    
    print('Files will be written to: {}'.format(outdir))
    if not os.access(outdir, os.F_OK):
        os.mkdir(outdir)
    
    headerdict = getheaderdict(rastertype = 'year', tilename = tilename, foresttograss = foresttograss, observationtype = 'reforested')
    outfile = os.path.join(outdir, headerdict['defaultbasefilename'])
    if not overwrite and os.access(outfile, os.F_OK):
        print('{} exists and no overwrite has been set, skipping.'.format(os.path.basename(outfile)))
        return
    files = []
    parentrasters = []
    print(len(years))

    for year in years:
        if opp:
            fname = os.path.join(indir, '{}_{}_forestryclass.dat'.format(tilename, year))
        else:
            fname = os.path.join(indir, 'forestryclass_{}_{}.dat'.format(year, tilename))
        if os.access(fname, os.F_OK):
            parentrasters.append(fname)
            files.append(gdal.Open(fname))
            if not geoTrans:
                geoTrans = files[0].GetGeoTransform()
                ns = files[0].RasterXSize
                nl = files[0].RasterYSize
                if margs.usemaskfile:
                    ULx, ULy = pixel2world(geoTrans, 0, 0)
                    mask_ds = gdal.Open(margs.forestrymaskfile)
                    mask_gt = mask_ds.GetGeoTransform()
                    mx, my = world2Pixel(mask_gt, ULx, ULy)
                    print('mx = {}, my = {}, ns = {}, nl = {}'.format(mx, my, ns, nl))
                    mask = mask_ds.GetRasterBand(1).ReadAsArray()
                    print('mask dimensions: {}'.format(mask.shape))
                    mvals = np.where(numexpr.evaluate('(mask == 1)'))
                    # print(mvals.shape)
                    yvals = mvals[0].tolist()
                    xvals = mvals[1].tolist()
                    mvals = None
                    print('Total xvals = {}, yvals = {}'.format(len(xvals), len(yvals)))
                else:
                    yvals = list(range(nl))
                    xvals = list(range(ns))
                numpixels = ns * nl
                
        else:
            files.append(0)
    startclass = np.zeros((nl, ns), dtype = np.uint8)
    endclass = np.zeros((nl, ns), dtype = np.uint8)
    statusmap = np.zeros((nl, ns), dtype = np.uint8)
    clearcut = np.zeros((nl, ns), dtype = np.uint16)
    afforested = np.zeros((nl, ns), dtype = np.uint16)
    statusyearmap = np.zeros((nl, ns), dtype = np.uint16)
    reforested = np.zeros((nl, ns), dtype = np.uint16)
    if margs.usemaskfile:
        numpixels = len(xvals)
    
    x = 0
    y = 0
    for i in range(numpixels):
        if margs.usemaskfile:        
            mx = xvals[i]
            my = yvals[i]
            X, Y = pixel2world(mask_gt, mx, my)
            x, y = world2Pixel(geoTrans, X, Y)
        
        if x >= 0 and x < ns and y >= 0 and y < nl:
            signal=[]
            for i in range(len(files)):
                if files[i] != 0:
                    band = files[i].GetRasterBand(1).ReadAsArray(x, y, 1, 1)
                    if band:
                        signal.append(band[0, 0])
                    else:
                        signal.append(0)
                else:
                    signal.append(0)
            if (1 in signal or 3 in signal) and (0 in signal or 2 in signal):
                # print(signal)
                signal = cleansignal(np.array(signal)).tolist()
            startclass[y, x] = signal[0]  
            endclass[y, x] = signal[-1]
            if 3 in signal and 1 in signal:
                cut = False
                refor = False
                if signal[0] == 1:
                    afforested[y, x] = years[signal.index(next(i for i in signal[1:] if i == 3))]
                for i in range(len(years) - 1, 0,-1):
                    if signal[i] == 3 and signal[i - 1] == 1:
                        year = years[i]
                        if year > afforested[y, x] and (afforested[y, x] > 0 or signal[0] == 3) and not refor:
                            reforested[y, x] = year
                            refor = True 
                    elif signal[i] == 1 and signal[i - 1] == 3:
                        year = years[i]
                        clearcut[y, x] = year
                        cut = True
                    if refor and cut:
                        break
                diffyear=0
                if reforested[y, x] > afforested[y, x]:
                    lastforest = reforested[y, x]
                else:
                    lastforest = afforested[y, x]
                if clearcut[y, x] > lastforest: #reforested[y, x] and clearcut[y, x] > afforested[y, x]:
                    diffyear = endyear - clearcut[y, x] # replace year
                    if diffyear < 5:
                        statusmap[y, x] = 5 # recent clearcut
                    elif diffyear < 10:
                        statusmap[y, x] = 4 # possible deforestation
                    elif diffyear >= 10:
                        statusmap[y, x] = 3 # deforested
                    statusyearmap[y, x] = clearcut[y, x]
                elif reforested[y, x] > afforested[y, x]:
                    statusmap[y, x] = 6 # reforested
                    statusyearmap[y, x] = reforested[y, x]
                elif afforested[y, x] > 0:
                    statusmap[y, x] = 7 # afforested
                    statusyearmap[y, x] = afforested[y, x]
            elif 3 in signal and 0 not in signal:
                statusmap[y, x] = 2
            elif 1 in signal and 0 not in signal:
                statusmap[y, x] = 1
        
        if pixnum % 10000 == 0:
            drawProgressBar((float(pixnum) / float(numpixels)), pixnum, numpixels)

        if not margs.usemaskfile:
            x += 1
            if x == ns:
                y += 1
                x = 0
        pixnum += 1 
    
    for i in range(len(files)): # close open files 
        files[i] = None
        mask = None
        mask_ds = None
    print('Writing files to disk.')
    writedata(startclass, 'ForestryClass', geoTrans, foresttograss = foresttograss, year = startyear, outdir = outdir, tilename = tilename, rasters =  parentrasters)
    writedata(endclass, 'ForestryClass', geoTrans, foresttograss = foresttograss, year = endyear, outdir = outdir, tilename = tilename, rasters =  parentrasters)
    writedata(statusmap, 'ForestryStatus', geoTrans, foresttograss = foresttograss, outdir = outdir, tilename = tilename, startyear = startyear, endyear = endyear, rasters =  parentrasters)
    writedata(clearcut, 'year', geoTrans, foresttograss = foresttograss, outdir = outdir, tilename = tilename, observationtype = 'clearcut', rasters =  parentrasters)
    writedata(afforested, 'year', geoTrans, foresttograss = foresttograss, outdir = outdir, tilename = tilename, observationtype = 'afforested', rasters =  parentrasters)
    writedata(statusyearmap, 'year', geoTrans, foresttograss = foresttograss, outdir = outdir, tilename = tilename, observationtype = 'statusyearmap', rasters =  parentrasters)
    writedata(reforested, 'year', geoTrans, foresttograss = foresttograss, outdir = outdir, tilename = tilename, observationtype = 'reforested', rasters =  parentrasters)
    
    startclass = None
    endclass = None
    statusmap = None
    clearcut = None
    afforested = None
    statusyearmap = None
    reforested = None   
    
def proctile(tile, foresttograss, *args, **kwargs):
    # indir = kwargs.get('indir', os.path.join(config['DEFAULT']['baseoutputdir'], '%d\Probability{}'.format(foresttograss)))
    startyear = kwargs.get('startyear', margs.startyear)
    endyear = kwargs.get('endyear', margs.endyear)
    overwrite = kwargs.get('overwrite', margs.overwrite)
    probabilityonly = kwargs.get('probabilityonly', False)
    yearlyonly = kwargs.get('yearlyonly', False)
    fconly = kwargs.get('fconly', False) 
    yearlychangeonly = kwargs.get('yearlychangeonly', False)
    yearlychange = kwargs.get('yearlychange', True)
    usecatfile = kwargs.get('usecatfile', True)
    badlistfile = kwargs.get('badlist', ieo.badlandsat)
    prob = True
    fc = True
    yc = True
    yearly = True
    probdir = os.path.join(os.path.join(config['DEFAULT']['baseoutputdir'], str(foresttograss)), 'Probability')
    tilename = tile.GetField('Tile')
    dt4a = kwargs.get('dt4a', margs.dt4a)
    dt4b = kwargs.get('dt4b', margs.dt4b)
    if margs.dt4a:
        outsubdir = 'dt4a'
    elif margs.dt4b:
        outsubdir = 'dt4b'
    else:
        outsubdir = str(foresttograss)
    
    if dt4b:
        print('Now processing DT4b classifications for Tile {} for the years: {} - {}.'.format(tilename, startyear, endyear))
    elif foresttograss:
        print('Now processing DT4 classifications for Tile {} for the years: {} - {}, foresttograss = {}.'.format(tilename, startyear, endyear, foresttograss))
    else:
        print('Now processing DT4a classifications for Tile {} for the years: {} - {}.'.format(tilename, startyear, endyear))
    tilegeom = tile.GetGeometryRef()
#    if prob:
    
    forestrydir = os.path.join(probdir, 'Forestry')
    changedir = os.path.join(forestrydir, 'Change')
    forestrystatusfile = os.path.join(changedir, 'forestrystatus_{}.dat'.format(tilename))
    if not os.path.isfile(forestrystatusfile) or overwrite:
        if not yearlychangeonly:
            for year in range(startyear, endyear+1):
                print('Now getting scene list to process for year: {}'.format(year))
                scenelist = makeproclist(tilegeom, foresttograss, usecatfile, year = year, badlistfile = badlistfile)
                if len(scenelist) > 0:
                    print('A total of {} scenes were found to process. Calculating probability rasters.'.format(len(scenelist)))
                    probdir = calcprobabilityraster(tile, scenelist, foresttograss, year, overwrite = overwrite)
                    if probdir:
                        print('Determining YearlyDT4 classes.')
                        Yearlydt4(probdir, year, tilename, foresttograss, overwrite = overwrite)
                        print('Determining forestry class.')
                        forestryclass(tilename, foresttograss, year, overwrite = overwrite)
                else:
                    print('Error: no scenes found to process.') 
        if yearlychange:
            print('Now calculating yearly change for tile {}.'.format(tilename))
            calcyearlychange(tilename, foresttograss, overwrite = overwrite)
    else:
        print('Overwrite has not been set or {} does not exist, skipping.'.format(os.path.basename(forestrystatusfile)))
           
    
def makemaps(*args, **kwargs):
    shp = kwargs.get('shp', margs.shp)
    dt4a = kwargs.get('dt4a', margs.dt4a) #
    dt4b = kwargs.get('dt4b', margs.dt4b)
    minforesttograss = kwargs.get('minforesttograss', margs.minforesttograss)
    maxforesttograss = kwargs.get('maxforesttograss', margs.maxforesttograss)
    increment = kwargs.get('increment', margs.increment)
    overwrite = kwargs.get('overwrite', margs.overwrite)
    probabilityonly = kwargs.get('probabilityonly', False)
    yearlyonly = kwargs.get('yearlyonly', False)
    fconly = kwargs.get('fconly', False)
    yearlychangeonly = kwargs.get('yearlychangeonly', False)
    usetile = kwargs.get('usetile', None)
    yearlychange = kwargs.get('yearlychange', True)
    reproctiles = kwargs.get('reproctiles', False)
    startyear = kwargs.get('startyear', margs.startyear)
    endyear = kwargs.get('endyear', margs.endyear)
    
    if not os.path.isfile(shp) and not os.path.dirname(shp) == ieo.gdb_path:
        print('ERROR: AIRT is missing: {}'.format(shp))
        logerror('shp', 'Missing shapefile.')
        return
    
    if reproctiles:
        tiledict = makereproctiledict(startyear = startyear, endyear = endyear)
    
    if shp.endswith('shp'): # Enable use of tiles now available in IEO 1.1.0
        driver1 = ogr.GetDriverByName("ESRI Shapefile")
        ds = driver1.Open(shp, 0)
        tiles = ds.GetLayer()
    else:
        driver1 = ogr.GetDriverByName("FileGDB")
        gdb, lname = os.path.split(shp)
        ds = driver1.Open(gdb, 0)
        tiles = ds.GetLayer(lname)
    
    if dt4a or dt4b:
        foresttograss = None
        if dt4b:
            print('Now processing tiles using the DT4b algorithm.')
        else:
            print('Now processing tiles using the DT4a algorithm.')
        for tile in tiles:
            print('Now using tile: {}'.format(tile.GetField('Tile')))
            if usetile:
                if tile.GetField('Tile') == usetile:
                    proctile(tile, foresttograss, overwrite = overwrite, yearlychange = yearlychange, yearlychangeonly = yearlychangeonly, dt4a = dt4a, dt4b = dt4b) # , probabilityonly = probabilityonly, yearlyonly = yearlyonly, fconly = fconly, 
            elif reproctiles:
                years = sorted(list(tiledict.keys()))
                for year in years:
                    if tile.GetField('Tile') in tiledict[year]:
                        proctile(tile, foresttograss, overwrite = overwrite, yearlychange = yearlychange, startyear = year, endyear = year, yearlychangeonly = yearlychangeonly, dt4a = dt4a, dt4b = dt4b)
            else:
                proctile(tile, foresttograss, overwrite = overwrite, yearlychangeonly = yearlychangeonly, dt4a = dt4a, dt4b = dt4b)
        print('All tiles have been processed.')
        tiles.ResetReading()
    else:
        foresttograss = minforesttograss
        while foresttograss <= maxforesttograss:
            print('Now processing tiles for foresttograss = {}.'.format(foresttograss))
            for tile in tiles:
                if usetile:
                    if tile.GetField('Tile') == usetile:
                        proctile(tile, foresttograss, overwrite = overwrite, yearlychange = yearlychange, yearlychangeonly = yearlychangeonly, dt4a = dt4a, dt4b = dt4b) # , probabilityonly = probabilityonly, yearlyonly = yearlyonly, fconly = fconly, yearlychangeonly = yearlychangeonly
                elif reproctiles:
                    years = sorted(list(tiledict.keys()))
                    for year in years:
                        if tile.GetField('Tile') in tiledict[year]:
                            proctile(tile, foresttograss, overwrite = overwrite, yearlychange = yearlychange, startyear = year, endyear = year, yearlychangeonly = yearlychangeonly, dt4a = dt4a, dt4b = dt4b)
                else:
                    proctile(tile, foresttograss, overwrite = overwrite, yearlychangeonly = yearlychangeonly, dt4a = dt4a, dt4b = dt4b)
            print('All tiles have been processed for foresttograss = {}.'.format(foresttograss))
            tiles.ResetReading()
            foresttograss += increment
    ds = None
    print('All maps have been created.')

## batch functions

def cleandir(d, *args, **kwargs):
    # This function deletes files. It should only be called if --overwrite is set
    deldt4s = kwargs.get('deldt4s', False)
    
    subdirs = ['Probability', 'Forestry', 'Change']
    dname = d
    if deldt4s:
        dirs = [d, os.path.join(d, 'vrt')]
    else:
        dirs = []
    
    for s in subdirs:
        dirs.append(os.path.join(dname, s))
        dname = dirs[-1]
    
    for dname in dirs:    
        if os.path.isdir(dname):
            flist = glob.glob(os.path.join(dname, '*'))
            if len(flist) > 0:
                print('Now deleting files in: {}'.format(dname))
                for f in flist:
                    if os.path.isfile(f):
                        os.remove(f)

def batchdt4(*args, **kwargs):
    # updated 8 February 2018 to include DT4b algorithm as new default
    indir = kwargs.get('indir', ieo.srdir)
    invrtdir = os.path.join(indir, 'vrt')
    fmaskdir = kwargs.get('fmaskdir', ieo.fmaskdir)
    fmaskvrtdir = os.path.join(fmaskdir, 'vrt')
    outbasedir = kwargs.get('outbasedir', config['DEFAULT']['baseoutputdir'])
    startyear = kwargs.get('startyear', margs.startyear)
    endyear = kwargs.get('endyear', margs.endyear)
    yearoffset = kwargs.get('yearoffset', 5)
    startday = kwargs.get('startday', margs.startday)
    endday = kwargs.get('endday', margs.endday) 
    path = kwargs.get('path', None)
    row = kwargs.get('row', None)
    minforesttograss = kwargs.get('minforesttograss', margs.minforesttograss)
    maxforesttograss = kwargs.get('maxforesttograss', margs.maxforesttograss)
    minpixels = kwargs.get('minpixels', margs.minpixels)
    increment = kwargs.get('increment',  margs.increment)
    overwrite = kwargs.get('overwrite', margs.overwrite)
    listfile = kwargs.get('listfile', os.path.join(os.path.join(ieo.catdir, 'LEDAPS_processing_lists'), 'LEDAPS_list_{}.txt'.format(datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))))
    dt4a = kwargs.get('dt4a', margs.dt4a)
    dt4b = kwargs.get('dt4b', margs.dt4b)
    
    if dt4a or dt4b:
        foresttograss = None
        incs = 1
    else:
        foresttograss = minforesttograss    
        incs = (maxforesttograss - minforesttograss) / increment + 1
    filelist = []
        
    lastday = datetime.datetime.strptime('{}{:03}'.format(endyear, endday), '%Y%j')
    today = datetime.datetime.today()
    
    if path and row:
        flist = glob.glob(os.path.join(indir, 'L*{:03}{:03}*_ref_ITM.dat'.format(path, row)))
    elif path:
        flist = glob.glob(os.path.join(indir, 'L*{:03}*_ref_ITM.dat'.format(path)))
    else:
        flist = glob.glob(os.path.join(indir, 'L*_ref_ITM.dat'))
    if len(flist) > 0:
        print('A total of {} scenes have been identified. Now searching for appropriate dates and Fmask files.'.format(len(flist)))
        for f in flist:
#                        f = flist[0]
            year = int(os.path.basename(f)[9:13])
            doy = int(os.path.basename(f)[13:16])
            if ((year >= startyear) and (year <= endyear) and (doy >= startday) and (doy <= endday)):
                fmask = None
                basename = os.path.basename(f)
                cfmask = os.path.join(fmaskdir, basename.replace('_ref_ITM', '_cfmask'))
                if os.path.exists(cfmask):
                    fmask = cfmask
                elif os.path.exists(cfmask.replace('_cfmask', '_fmask')):
                    fmask = cfmask.replace('_cfmask', '_fmask')
                if fmask:
                    filelist.append([f, fmask])
    else:
        print('No scenes were found to process. Returning.')
        return
        
    print('\n')
    numfiles = int(len(filelist) * incs)
    filenum = 1
    print('Total files: {}'.format(numfiles))
    
    if dt4b:
        outdirs = [os.path.join(outbasedir, 'dt4b')]
    elif dt4a:
        outdirs = [os.path.join(outbasedir, 'dt4a')]
    else:
        outdirs = []
        while foresttograss <= maxforesttograss:
            outdirs.append(os.path.join(outbasedir, str(foresttograss)))
    for outdir in outdirs:    
        if not os.access(outdir, os.F_OK):
            print("Creating directory: {}".format(outdir))
            os.mkdir(outdir)
        
        probdir = os.path.join(outdir, 'Probability')
        if not os.access(probdir, os.F_OK):
            print("Creating directory: {}".format(probdir))
            os.mkdir(probdir)
        if overwrite: # Delete any existing files for this foresttograss value
            cleandir(outdir, deldt4s = True)
            
    for f in filelist:
        foresttograss = minforesttograss
        for outdir in outdirs:
            if not dt4a and not dt4b:
                foresttograss = int(os.path.basename(outdir))
            breakloop = False # Breaks while loop for Fmask issues 
#            outdir = os.path.join(outbasedir, str(foresttograss))
            basename = os.path.basename(f[0])
            ref = f[0]
            fmask = f[1]
            print('Processing scene {}, number {} of {}.'.format(basename[:21], filenum, numfiles))
            retry = True
            errors = 0
            while retry and errors < 5:
                if dt4b:
                    success, msg = DT4b(ref, outdir, minpixels, minforesttograss = minforesttograss, maxforesttograss = maxforesttograss, fmask = fmask, overwrite = overwrite, listfile = listfile)
                elif dt4a:
                    success, msg = DT4a(ref, outdir, minpixels, minforesttograss = minforesttograss, maxforesttograss = maxforesttograss, fmask = fmask, overwrite = overwrite, listfile = listfile)
                else:
                    success, msg = dt4(ref, outdir, minpixels, foresttograss, fmask = fmask, overwrite = overwrite, listfile = listfile)
                if success:
                    retry = False
                elif not success and msg in ['Insufficient pixels', 'No Fmask', 'Output exists']:
                    print('There was an error with the scene: {}. Skipping.'.format(msg))
#                    filelist.pop(filelist.index(f))
                    if msg in ['Insufficient pixels', 'No Fmask']:
                        breakloop = True
                    retry = False
                else:
                    print('There was an error with SceneID {}: {}.'.format(basename[:21], msg))
                    errors += 1
                    if errors <= 5:
                        print('Retry {}/5'.format(errors))
            if breakloop:
                break
            foresttograss += increment
        filenum += 1
 
def batchmultiyeardt4(*args, **kwargs):
    
    indir = kwargs.get('indir', ieo.srdir)
    fmaskdir = kwargs.get('fmaskdir', ieo.fmaskdir)
    outbasedir = kwargs.get('outbasedir', config['DEFAULT']['baseoutputdir'])
    startyear = kwargs.get('startyear', margs.startyear)
    endyear = kwargs.get('endyear', margs.endyear)
    startday = kwargs.get('startday', 82)
    endday = kwargs.get('endday', 283) 
    path = kwargs.get('path', None)
    row = kwargs.get('row', None)
    foresttograss = kwargs.get('minforesttograss', margs.minforesttograss)
    maxforesttograss = kwargs.get('maxforesttograss', margs.maxforesttograss)
    minpixels = kwargs.get('minpixels', margs.minpixels)
    increment = kwargs.get('increment', margs.increment)
    overwrite = kwargs.get('overwrite', margs.overwrite)
    yearoffset = kwargs.get('yearoffset', 5)
    
    while foresttograss <= maxforesttograss:
        outdir = os.path.join(outbasedir, foresttograss)
        if not os.access(outdir, os.F_OK):
            print('Creating directory: {}'.format(outdir))
            os.mkdir(outdir)
        
        probdir = os.path.join(outdir, 'Probability')
        if not os.access(probdir, os.F_OK):
            print('Creating directory: {}'.format(probdir))
            os.mkdir(probdir)
        
        for year in range(startyear, endyear+1):
            print('Processing files for year {}'.format(year))
            Yearlydt4(probdir, year, fbase, foresttograss, overwrite = overwrite)
        
        year = startyear
        while year <= endyear:
            finalyear = year + yearoffset - 1
            Yearlydt4(probdir, year, fbase, foresttograss, endyear = finalyear, overwrite = overwrite)
            year += yearoffset
        
        foresttograss += increment

                                        
## main

def main():
#    overwrite = margs.overwrite
    if margs.dt4a:
        margs.dt4b = False
    if margs.calcdt4:
        
       batchdt4(overwrite = margs.overwrite) 
       import ifordeovrt
       ifordeovrt.margs.overwrite = True
       ifordeovrt.batchvrts()
    # if computername == 'HCAX378':
    #     if margs.calcdt4:
    #         print('Calculating DT4 classifications.')
    #         batchdt4(overwrite = overwrite)
    #     tileshp = r'D:\Spatial Analysis Unit\Analysis\CForRep\Working\Classifications\IRL_tiles_45.shp'
    #     if not os.path.exists(tileshp):
    #         makegrid(outfile = tileshp)
    makemaps(overwrite = margs.overwrite, shp = margs.shp)

if __name__ == '__main__':
    main()
    

