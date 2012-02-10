#! /usr/bin/env python

# import radio stuff
from FMRadio import FMRadio, FMRadioUnavailableError


stations = []


def scan_cb(freq, is_station):
    """
    Callback for scanning for stations. This callback is called for every
    frequency and tells you if a radio station was found.
    """

    print "scanning @ %0.2f MHz" % (freq / 1000.0),
    if (is_station):
        print "STATION FOUND"
        stations.append(freq)
    else:
        print ""
        
        

# open the radio
try:
    radio = FMRadio()
except FMRadioUnavailableError:
    # radio not available
    print "Your device doesn't seem to have a FM radio..."
    import sys; sys.exit(1)
    
# get frequency range; currently only the US/Europe frequency band is supported
# by the driver
low, high = radio.get_frequency_range()
print "Frequency range: %0.2f - %0.2f MHz" % (low / 1000.0, high / 1000.0)

# scan for radio stations
radio.scan(scan_cb)

# if we have found some stations, start playing
if (stations):
    radio.set_volume(50)
        
    print "Now listen to the radio."
    for freq in stations:
        print "Tuning in %0.2f MHz." % (freq / 1000.0)
        radio.set_frequency(freq)                
        import time; time.sleep(3)

else:
    print "No radio stations found. The signal is too weak."

# don't forget to shutdown the radio; this will also power down the radio chip
print "Switching off the radio."
radio.close()

