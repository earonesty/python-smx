#!/bin/sh
set -eu
python -m pytest -n 4 -v --cov=smx smx/*.py "$@"
