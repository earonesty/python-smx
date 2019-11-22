import os, time

from io import StringIO

from engines import engines

from tempfile import mkdtemp

import logging

logging.basicConfig(level=logging.INFO)

log = logging.getLogger("smx")
log.debug("TEST")

SECS = 2

for ename, tests in engines.items():

    for tname, test in tests.items():
        path = mkdtemp(prefix=ename + "." + tname)
        os.chdir(path)

        files = test["files"]
        for (name, val) in files.items():
            with open(name, "w") as f:
                f.write(val)

        command = test["command"]

        t = time.time()

        count = 0
        while time.time() < t + SECS:
            s = StringIO()
            command(s)
            count += 1

        print(name, SECS/count)
