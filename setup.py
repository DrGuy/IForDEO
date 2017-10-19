#!/usr/bin/env python
import os, sys
from setuptools import setup, find_packages

# create configuration for installation if missing

configdir = os.path.join(os.path.dirname(__file__),'config')
if not os.path.isdir(configdir):
    os.mkdir(configdir)

ini = os.path.join(configdir, 'ifordeo.ini')
if not os.path.isfile(ini):
    with open(ini, 'w') as output:
        output.write('[DEFAULT]\n')
        output.write('errorlogfile = ifordeo_errors.log\n')
        x = input('Please input the base directory for output data: ')
        output.write('baseoutputdir = %s\n'%(x))
        y = input('Please input the IForDEO data catalog directory (not the same as the IEO\n. If not set, will use %s): '%os.path.join(x,'Catalog'))
        if len(y) == 0 or not os.path.isdir(y):
            y = os.path.join(x, 'Catalog')
        output.write('catdir = %s\n'%y)
        y = input('Please input the location of the forestry raster mask file (optional, but highly recommended): ')
        output.write('forestrymaskfile = %s\n'%y)
        output.write('[vector]\n')
        y = input('Please input the location of a shapefile for all of Ireland (optional): ')
        output.write('irelandshp = %s\n'%y)
        
    
setup(
    # Application name:
    name='ifordeo',

    # Version number:
    version='1.0.0',

    # Application author details:
    author='Guy Serbin',

    license = open('LICENSE').read(),

    description = 'Ireland Forest Disturbance from Earth Observation library.',
    long_description = open('README.md').read(),

    classifiers = [
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.1',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Scientific/Engineering :: GIS'
    ],

    # Scripts
    # Moves the script to the user's bin directory so that it can be executed.
    # Usage is 'download_espa_order.py' not 'python download_espa_order.py'
    scripts = ['ifordeo.py', 'ifordeovrt.py'],
    packages = ['.', 'config', 'data'],
    package_data={'config': ['*',], 'data': ['*',]},
    # Dependent packages (distributions)
    install_requires=[
        'numexpr',
        'numpy',
        'gdal', 
        'ieo'
    ],
)
