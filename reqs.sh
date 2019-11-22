#!/bin/bash

pip install pytest>=3.6
# install pytest-cov first, which should pull in the right deps
pip install pytest-cov pytest-xdist codecov
