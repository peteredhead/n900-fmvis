# pyFMRadio
# Module for controlling the tea5761 FM radio chip in the Nokia N800.
# Copyright (C) 2007 - 2008 Martin Grimme  <martin.grimme _AT_ lintegra.de>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307  USA


# make 'from FMRadio import *' safe
__all__ = ["FMRadio", "FMRadioError", "FMRadioUnavailableError",
           "FMRadioOperationNotSupportedError"]


import struct
from fcntl import ioctl
import os
import time


__VERSION__ = 0.22


# kernel definitions for ioctl commands
_IOC_NRBITS   = 8
_IOC_TYPEBITS = 8
_IOC_SIZEBITS = 14
_IOC_DIRBITS  = 2

_IOC_NRSHIFT   = 0
_IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
_IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
_IOC_DIRSHIFT  = _IOC_SIZESHIFT + _IOC_SIZEBITS

_IOC_WRITE = 1
_IOC_READ  = 2

_IOC  = lambda d,t,nr,size: (d << _IOC_DIRSHIFT) | (ord(t) << _IOC_TYPESHIFT) | \
                            (nr << _IOC_NRSHIFT) | (size << _IOC_SIZESHIFT)
_IOW  = lambda t,nr,size: _IOC(_IOC_WRITE, t, nr, size)
_IOR  = lambda t,nr,size: _IOC(_IOC_READ, t, nr, size)
_IOWR = lambda t,nr,size: _IOC(_IOC_READ | _IOC_WRITE, t, nr, size)

# V4L2 stuff for accessing the tuner driver
_VIDIOC_G_TUNER     = _IOWR('V', 29, 84)
_VIDIOC_G_AUDIO     = _IOR ('V', 33, 52)
_VIDIOC_S_AUDIO     = _IOW ('V', 34, 52)
_VIDIOC_G_FREQUENCY = _IOWR('V', 56, 44)
_VIDIOC_S_FREQUENCY = _IOW ('V', 57, 44)
_VIDIOC_G_CTRL      = _IOWR('V', 27, 8)
_VIDIOC_S_CTRL      = _IOWR('V', 28, 8)

# tuner capabilities
_V4L2_TUNER_CAP_LOW    = 0x0001
_V4L2_TUNER_CAP_NORM_  = 0x0002
_V4L2_TUNER_CAP_STEREO = 0x0010
_V4L2_TUNER_CAP_LANG2  = 0x0020
_V4L2_TUNER_CAP_SAP    = 0x0020
_V4L2_TUNER_CAP_LANG1  = 0x0040

# rxsubchans flags
_V4L2_TUNER_SUB_MONO   = 0x0001
_V4L2_TUNER_SUB_STEREO = 0x0002
_V4L2_TUNER_SUB_LANG2  = 0x0004
_V4L2_TUNER_SUB_SAP    = 0x0004
_V4L2_TUNER_SUB_LANG1  = 0x0008

# audmode values
_V4L2_TUNER_MODE_MONO        = 0x0000
_V4L2_TUNER_MODE_STEREO      = 0x0001
_V4L2_TUNER_MODE_LANG2       = 0x0002
_V4L2_TUNER_MODE_SAP         = 0x0002
_V4L2_TUNER_MODE_LANG1       = 0x0003
_V4L2_TUNER_MODE_LANG1_LANG2 = 0x0004

# audio capabilities
_V4L2_AUDCAP_STEREO = 0x00001
_V4L2_AUDCAP_AVL    = 0x00002

# audio mode flags
_V4L2_AUDMODE_AVL   = 0x00001

# user-class control IDs defined by V4L2
_V4L2_CTRL_CLASS_USER = 0x00980000
_V4L2_CID_BASE        = _V4L2_CTRL_CLASS_USER | 0x900
_V4L2_CID_FM_BAND     = _V4L2_CID_BASE + 0
_V4L2_CID_AUDIO_MUTE  = _V4L2_CID_BASE + 9

# mixer control constants
_SOUND_MIXER_FMRADIO         = 0x06
_SOUND_MIXER_READ            = 0x80044D00
_SOUND_MIXER_WRITE           = 0xC0044D00

# the devices we directly talk to
_RADIO_DEV = "/dev/radio1"
_MIXER_DEV = "/dev/mixer"

# signal scanning parameters
_SIGNAL_LOCK_TIME = 0.1
_SIGNAL_TRIES = 1
_SIGNAL_SAMPLE_SLEEP = 0.005
_SIGNAL_THRESHOLD = 20
_SCAN_STEP_KHZ = 50



class FMRadioError(StandardError):
    """
    Base class for FMRadio-related exceptions.
    """
    pass

class FMRadioUnavailableError(FMRadioError):
    """
    Exception to throw if the radio is unavailable.
    """
    pass
    
class FMRadioOperationNotSupportedError(FMRadioError):
    """
    Exception to throw when calling an unsupported operation.
    """
    pass



class FMRadio(object):
    """
    Class for controlling the radio.
    """

    # FM bands
    FM_BAND_EUR = 0
    FM_BAND_JPN = 1
    

    def __init__(self):
        
        self.__is_scanning = False
        
        import dbus
        bus = dbus.SystemBus()
        obj = bus.get_object("de.pycage.FMRXEnabler", "/de/pycage/FMRXEnabler")
        enabler = dbus.Interface(obj, "de.pycage.FMRXEnabler")
        status, device = enabler.request()
 
        try:
            self.__fd = os.open(_RADIO_DEV, os.O_RDONLY)
        except OSError:
            raise FMRadioUnavailableError("FM radio is not available.")

        self.__tuner = self.__get_tuner()
        self.__factor = (self.__tuner["capability"] & _V4L2_TUNER_CAP_LOW) \
                        and 16 or 0.016        
        self.__freq_range = (self.__tuner["rangelow"] / self.__factor,
                             self.__tuner["rangehigh"] / self.__factor)
        self.set_mute(False)

        
    def __get_tuner(self):
        """
        Returns information about the tuner.
        """         
        data = ioctl(self.__fd, _VIDIOC_G_TUNER, struct.pack("84x"))
        fields = struct.unpack("L32sLLLLLLll4L", data)
        tuner = { "index": fields[0],
                  "name": fields[1],
                  "type": fields[2],
                  "capability": fields[3],
                  "rangelow": fields[4],
                  "rangehigh": fields[5],
                  "rxsubchans": fields[6],
                  "audmode": fields[7],
                  "signal": fields[8],
                  "afc": fields[9] }        
        
        return tuner
        
    def close(self):
        """
        Closes the radio and powers off the FM tuner chip.
        """
        self.cancel_scanning()        
        self.set_mute(True)
        os.close(self.__fd)
              
    def set_fm_band(self, band):
        """
        Sets the FM band to the given value. This allows to switch between
        US/Europe and Japanese FM bands. Setting the FM band is not supported
        on Nokia's standard kernel, and will require a special patch.
        
        See https://bugs.maemo.org/show_bug.cgi?id=2249 for more.
        """
        
        assert band in (self.FM_BAND_EUR, self.FM_BAND_JPN)
        
        inp = struct.pack("Ll", _V4L2_CID_FM_BAND, band)
        try:        
            ioctl(self.__fd, _VIDIOC_S_CTRL, inp)
        except:
            raise FMRadioOperationNotSupportedError(
                      "FM tuner driver does not support switching the FM band")
        
        # changing the FM band invalidates our stored frequency range so that
        # we have to read it again
        self.__tuner = self.__get_tuner()
        self.__freq_range = (self.__tuner["rangelow"] / self.__factor,
                             self.__tuner["rangehigh"] / self.__factor)        
        
        
    def get_fm_band(self):
        """
        Returns the current FM band. This is either FM_BAND_EUR for the
        US/Europe FM band and FM_BAND_JPN for the Japanese FM band.
        """
        
        inp = struct.pack("Ll", _V4L2_CID_FM_BAND, 0)
        try:
            data = ioctl(self.__fd, _VIDIOC_G_CTRL, inp)
        except:
            # we may assume that if the operation is unsupported, the band
            # is set to US/Europe
            band = self.FM_BAND_EUR
        else:
            fields = struct.unpack("Ll", data)
            band = fields[1]
        
        return band
        
        
    def get_frequency_range(self):
        """
        Returns the supported frequency range as a (low, high) tuple.
        The range depends on the selected FM band.
        """
    
        low, high = self.__freq_range
        return (low, high)
        
        
    def get_frequency(self):
        """
        Returns the current frequency value.
        """

        inp = struct.pack("LLL8L",
                          self.__tuner["index"],
                          self.__tuner["type"],
                          0, 0, 0, 0, 0, 0, 0, 0, 0)
        data = ioctl(self.__fd, _VIDIOC_G_FREQUENCY, inp)
        fields = struct.unpack("LLL8L", data)
        freq = fields[2]
        freq = int(freq / self.__factor / float(_SCAN_STEP_KHZ) + 0.5) * \
               _SCAN_STEP_KHZ
        
        return freq
        
        
    def set_frequency(self, freq):
        """
        Sets the frequency to the given value.
        """

        self.cancel_scanning()

        low, high = self.__freq_range
        # a frequency of 0 tells the FM tuner to power down
        assert(freq == 0 or low <= freq <= high)

        inp = struct.pack("LLL8L",
                          self.__tuner["index"],
                          self.__tuner["type"],
                          int(freq * self.__factor), 0, 0, 0, 0, 0, 0, 0, 0)
        ioctl(self.__fd, _VIDIOC_S_FREQUENCY, inp)
        
        
    def get_volume(self):
        """
        Returns the current volume value as left channel, right channel.
        """

        mixer = os.open(_MIXER_DEV, os.O_RDONLY)
        data = ioctl(mixer, _SOUND_MIXER_READ | _SOUND_MIXER_FMRADIO, "\x00\x00")
        os.close(mixer)
        left, right = struct.unpack("bb", data)

        return (left, right)
        
        
    def set_volume(self, left, right = -1):
        """
        Sets the current volume for left and right channels. Omit the value
        for the right channel to set both channels to the same value.
        """

        if (right == -1): right = left
        assert(0 <= left <= 100 and 0 <= right <= 100)

        mixer = os.open(_MIXER_DEV, os.O_RDONLY)
        inp = struct.pack("bb", left, right)
        ioctl(mixer, _SOUND_MIXER_WRITE | _SOUND_MIXER_FMRADIO, inp)
        os.close(mixer)
        
        
    def set_mute(self, value):
        """
        Mutes or unmutes the radio. This does not affect the volume settings.
        """  
        inp = struct.pack("Ll", _V4L2_CID_AUDIO_MUTE, value and 1 or 0)
        ioctl(self.__fd, _VIDIOC_S_CTRL, inp)
        
        
    def get_signal_strength(self):
        """
        Returns the current signal strength as a value between 0 and 100.
        """

        # algorithm adapted from fmscan by Russell Kroll
        time.sleep(_SIGNAL_LOCK_TIME)
        totsig = 0
        for i in range(_SIGNAL_TRIES):            
            tuner = self.__get_tuner()            
            signal = tuner["signal"]
            totsig += signal
            time.sleep(_SIGNAL_SAMPLE_SLEEP)
        #end for
        
        perc = totsig / float(0xffff * _SIGNAL_TRIES)
        
        return perc * 100
        
        
    def is_signal_good(self):
        """
        Returns whether the current signal strength is good enough.
        """
    
        return (self.get_signal_strength() > _SIGNAL_THRESHOLD)
        
        
    def scan(self, cb = None):
        """
        Scans for stations and returns a list of the frequencies of the
        stations found.
        If you pass a callback function, it will be called at every step.
        The signature of the callback must be: f(freq, is_station)
        """

        if (self.__is_scanning): return []
        
        stations = []
        low, high = self.get_frequency_range()
        self.__is_scanning = True
        for freq in range(low, high + 1, _SCAN_STEP_KHZ):
            self.set_frequency(freq)
            is_good = self.is_signal_good()
            if (is_good): stations.append(freq)
            if (cb):
                try:
                    cb(freq, is_good)
                except:
                    pass
            #end if
            if (not self.__is_scanning): break
        #end for
        self.__is_scanning = False
        
        return stations

    
    def __scan_next(self, scan_to, step, cb):
        """
        Scans for the next station.
        A station is recognized on the peak of signal strength
        (RISING -> FALLING) when the signal
        strength is high enough.
        """
    
        FALLING = 0
        RISING = 1       

        current = self.get_frequency()
        if (self.__is_scanning): return current
        
        prev_freq = current
        prev_strength = self.get_signal_strength()
        
        mode = FALLING
        self.__is_scanning = True
        for freq in range(current + step, scan_to, step):
            self.set_frequency(freq)
            strength = self.get_signal_strength()
            
            if (prev_strength > strength):
                if (mode == RISING):
                    # found peak
                    if (prev_strength > _SIGNAL_THRESHOLD):
                        self.set_frequency(prev_freq)
                        return freq
                    
                else:
                    mode = FALLING
            else:
                mode = RISING

            if (cb):
                try:
                    cb(freq)
                except:
                    pass
            #end if
                
            prev_freq = freq
            prev_strength = strength
            
            if (not self.__is_scanning): break
        #end for
        self.__is_scanning = False
        
        return current


    def scan_previous(self, cb = None):
        """
        Scans for the previous radio station and returns its frequency.
        If no station was found, the current frequency will be returned instead.
        """

        low, high = self.get_frequency_range()
        return self.__scan_next(low, -_SCAN_STEP_KHZ, cb)

        
        
    def scan_next(self, cb = None):
        """
        Scans for the next radio station and returns its frequency.
        If no station was found, the current frequency will be returned instead.        
        """

        low, high = self.get_frequency_range()
        return self.__scan_next(high, _SCAN_STEP_KHZ, cb)
        
        
    def cancel_scanning(self):
        """
        Cancels scanning for stations.
        """
    
        self.__is_scanning = False
        
