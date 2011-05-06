# This file is part of FMVis
#
# FMVis - A RadioVIS Client for the N900, using the internal FM Radio 
# Copyright (C) 2010 Global Radio
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import sys
sys.path.append("/opt/fmradio/components/fmradio")

from PyQt4.QtCore import QObject, pyqtSignal, QThread

from FMRadio import FMRadio, FMRadioUnavailableError
from SoundPipe import SoundPipe

        
class Radio(QObject):
    """
    Interface to the Radio
    """ 
    debug = pyqtSignal(str, name="debug")
    pi_change = pyqtSignal(str, name="pi_change")
    ps_change = pyqtSignal(str, name="ps_change")
    scan_done = pyqtSignal(name = "scan_done")
    
    def __init__(self):
        QObject.__init__(self, parent = None)
        self.__keep_alive = KeepAliveWorker()
        self.__radio = None
        self.__sound_pipe = SoundPipe()
        
        self.__current_pi = None
        self.__current_ps = None
        self.__pi_array = []
        self.__ps_array = []
        
        self.__scan_worker = ScanWorker(self)
        self.__station_watcher = StationWatcher(self)
        self.rds_worker = RDSWorker(self)
        
        self.__station_watcher.debug.connect(self.debugger)
        self.rds_worker.debug.connect(self.debugger)
        self.__scan_worker.debug.connect(self.debugger)
        
        self.rds_worker.pi_found.connect(self.pi_found)
        self.rds_worker.ps_found.connect(self.ps_found)
        
        self.__scan_worker.scan_complete.connect(self.scan_completed)      
        
    def debugger(self, msg):
        self.debug.emit(msg)
             
    def enable(self):
        """
        Initialise the FM Radio.
        """
        self.__keep_alive.ping()
        try:
            self.__radio = FMRadio(device="RX-51")
        except FMRadioUnavailableError:
            print "Unable to detect an FM Radio."
            sys.exit(1)
        self.__keep_alive.start()
        
        # Get frequency limits of device.
        low, high = self.__radio.get_frequency_range()
        self.low = low / 1000
        self.high = high / 1000
        
        self.debug.emit("Starting soundpipe")
        
        # Route audio to the headphones.
        self.__sound_pipe.on()
        self.__sound_pipe.use_speaker(False)
        self.__sound_pipe.set_speaker_volume(50)
        
    def disable(self):
        """
        Turns off the FM Radio.
        """
        self.__sound_pipe.off()
        self.__radio.close()
        self.__radio = None
        
    def tune(self, freq):
        """
        Tune the radio to a particular frequency
        """
        self.debug.emit("Tuning to %s" % freq)
        self.set_frequency(freq)
        self.debug.emit("Returned from set freq")
        self.__station_watcher.start()
        
    def get_high_frequency(self):
        """
        Returns the highest available frequency.
        """
        return self.high
    
    def get_low_frequency(self):
        """
        Returns the lowest available frequency.
        """
        return self.low
        
    def set_frequency(self, freq):
        """
        Tunes to a specific frequency.
        """
        self.debug.emit("Setting freq to %s" % freq)
        self.__station_watcher.stop()
        self.rds_worker.stop()
        if freq < self.low or freq > self.high: freq = self.low
        self.__radio.set_frequency(freq * 1000)
        return
        
    def get_frequency(self):
        """
        Returns the currently tuned frequency
        """
        freq = self.__radio.get_frequency() / 1000.0
        return freq
        
    def get_volume(self):
        return self.__radio.get_volume()
        
    def set_volume(self, left, right):
        self.__radio.set_volume(left, right)
        
    def station_found(self):
        """
        Returns true if a station is detected on the current frequency.    
        """
        self.debug.emit("station_found - %s" % self.__radio.is_signal_good())
        return self.__radio.is_signal_good()
    
    def scan_next(self):
        """
        Scans to find the next station.
        """
        self.volume_left, self.volume_right = self.__radio.get_volume()
        self.set_volume(1, 1)
        self.__scan_worker.start()
        
    def scan_completed(self):
        """
        Called when the Scan Worker has found the next station.
        """
#        self.emit(SIGNAL("scanCompleted()"))
        self.__radio.set_volume(self.volume_left, self.volume_right)
        self.scan_done.emit()
        self.rds_worker.start()
        
    def get_rds(self):
        """
        Gets the RDS information for the current station.
        """
        pi, ps, rt = self.__radio.get_rds()
        rds = {}
        pi = pi.strip()
        ps = ps.strip()
        rt = rt.strip()
        
        if len(pi) < 4:
            rds['pi'] = None
        else:
            rds['pi'] = pi
            
        if len(ps) > 1:
            rds['ps'] = ps
        else:
            rds['ps'] = None
            
        if len(rt) > 1:
            rds['rt'] = rt
        else:
            rds['rt'] = None
        
#        self.debug.emit("pi: %s" % pi)
#        self.debug.emit("ps: %s" % ps)
#        self.debug.emit("rt: %s" % rt) 
        return rds
    
    def pi_found(self, new_pi):
        """
        Signals any change in PI Code
        """
        self.pi_change.emit(new_pi)
                
    def ps_found(self, new_ps):
        """
        Signals any change in PS Name
        """
        self.ps_change.emit(new_ps)
    
class ScanWorker(QThread):
    """
    Threaded class to scan the FM band.
    """     
    scan_complete = pyqtSignal(name="scan_complete")
    debug = pyqtSignal(str, name="debug")
            
    def __init__(self, radio):
        QThread.__init__(self, parent = None)
        self.exiting = False
        self.__is_scanning = False
        self.__radio = radio
        
    def __del__(self):
        self.exiting = True
        self.wait()
        
    def run(self):
        current_freq = self.__radio.get_frequency() + 0.15
        self.__is_scanning = True
        for scan_freq in range(current_freq*10, self.__radio.get_high_frequency()*10, 1):
            self.__radio.set_frequency(scan_freq/10.0)
            if self.__radio.station_found():
                self.__is_scanning = False
            if (not self.__is_scanning): break
        if self.__is_scanning == False:
            self.scan_complete.emit()
        else:
            for scan_freq in range((self.__radio.get_low_frequency()+0.5)*10, current_freq*10, 1):
                self.__radio.set_frequency(scan_freq/10.0)
                if self.__radio.station_found():
                    self.__is_scanning = False
                if (not self.__is_scanning): break
        self.__is_scanning = False
        self.scan_complete.emit()
        
    def stop(self):
        self.__is_scanning = False
         
class StationWatcher(QThread):
    """
    Monitors the current frequency to detect the presence of a station.
    """
    debug = pyqtSignal(str, name="debug")
    
    def __init__(self, radio):
        QThread.__init__(self, parent = None)
        self.__radio = radio
        self.exiting = False
        self.__retuned = False
        
    def __del__(self):
        self.exiting = True
        self.wait()
              
    def run(self):
        self.exiting = False
        self.debug.emit("Station watcher start")
        self.__retuned = False
        found = self.__radio.station_found()
        self.debug.emit("Station watcher: found = %s" % found)
        while found == False and self.__retuned == False:
            QThread.sleep(3)
            found = self.__radio.station_found()
            self.debug.emit("Station watcher: found = %s" % found)
#        self.__radio.rds_worker.stop()
        self.__radio.rds_worker.start()
    
    def stop(self):
        self.__retuned = True                
       
class RDSWorker(QThread):
    """
    Monitors the current station for a change in PS Name or PI Code
    """ 
    debug = pyqtSignal(str, name="debug")
    pi_found = pyqtSignal(str, name="pi_found")
    ps_found = pyqtSignal(str, name="ps_found")
    rds_fail = pyqtSignal()
        
    def __init__(self, radio):
        QThread.__init__(self, parent = None)
        self.__radio = radio
        self.exiting = False
                
    def __del__(self):
        self.debug("RDSWorker Stopping")
        self.exiting = True
        self.wait()
        
    def run(self):  
        self.exiting = False    
        self.debug.emit("RDSWorker Started")  
        while self.exiting == False:
#        while 1:
            rds = self.__radio.get_rds()
            if rds['pi'] is not None:
                self.pi_found.emit(rds['pi'])
            if rds['ps'] is not None:
                self.ps_found.emit(rds['ps'])
            QThread.sleep(2)
        self.debug.emit("RDSWorker Bombing Out")
        self.rds_fail.emit()
            
    def stop(self):
        self.exiting = True
                      
class KeepAliveWorker(QThread):
    """
    Sends pings periodically to the hardware to keep the radio enabled.
    """
    def __init__(self, parent = None):
        import dbus
        QThread.__init__(self, parent)
        bus = dbus.SystemBus()
        obj = bus.get_object("de.pycage.FMRXEnabler", "/de/pycage/FMRXEnabler")
        self.enabler = dbus.Interface(obj, "de.pycage.FMRXEnabler")
        self.exiting = False
        
    def __del__(self):
        self.exiting = True
        self.wait()
        
    def run(self):
        self.enabler.request()
        QThread.sleep(14)
        
    def ping(self):
        self.enabler.request()          
                    