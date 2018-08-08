FWS Commutation Offset Search
-----------------------------

Requires: 
* Python 3.5+
* [aerotech](https://github.com/klauer/aerotech)
* doCommand and scopedata_socket2 to be on the drive


Usage
-----

```bash
$ python calibrate_fws.py
usage: calibrate_fws.py [-h] [--axis AXIS] [--comm COMM] [--scope SCOPE]
                        host start stop step
calibrate_fws.py: error: the following arguments are required: host, start, stop, step

$ python calibrate_fws.py 192.168.1.16 315 345 5

# Scans from 315 to 345 in increments of 5 degree steps on axis @0 (the default)

```

The last command will generate a simple text file with the scan results.
To view the results, run:

```bash
$ python plot_fws_calibration.py results-315-345.txt
```
