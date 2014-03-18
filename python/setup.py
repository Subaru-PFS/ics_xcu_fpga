from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext
import os.path
import numpy

ext_modules=[
    Extension("pyFPGA",
              ["fpga/pyFPGA.pyx"],
              library_dirs=['../c'],
              libraries=['fpga'],
              include_dirs=['../c', 
                            numpy.get_include()])
]

setup(
  name = "FPGA",
  cmdclass = {"build_ext": build_ext},
  ext_modules = ext_modules
)
