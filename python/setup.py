from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext
import os.path

ext_modules=[
    Extension("pyFPGA",
              ["ccdFPGA/pyFPGA.pyx"],
              library_dirs=['../c'],
              libraries=['fpga'],
              include_dirs=['../c', 
                            '/home/pfs/anaconda/lib/python2.7/site-packages/numpy/core/include'])
]

setup(
  name = "FPGA",
  cmdclass = {"build_ext": build_ext},
  ext_modules = ext_modules
)
