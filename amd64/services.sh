#!/bin/bash
set -m

python3 ImageColorsClassificationApplication.py &
python3 Runner.py  

fg %1