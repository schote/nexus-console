from setuptools import setup, find_packages

setup(
  name='console',
  version='0.0.1',
  author='David Schote',
  author_email='david.schote@ptb.de',
  packages=find_packages(),
  install_requires=[
    'matplotlib',
    'pypulseq',
    'numpy',
    'pydantic',
    'ipykernel',
    'PyYAML'
  ],
  description='MRI console application to control Spectrum Instrumentation devices. Console interprets pulseq sequences and provides a ScanHub interface.',
)