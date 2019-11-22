#!/bin/bash

# install pytest-cov first, which should pull in the right deps
pip install pytest-cov pytest-xdist codecov
pip install pytest>=4.4
