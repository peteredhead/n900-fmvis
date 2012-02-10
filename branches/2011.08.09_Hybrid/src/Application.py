#! /usr/bin/env python

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
import os
from PyQt4 import *
from PyQt4 import QtGui
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from PyQt4.QtCore import pyqtSignal, SIGNAL

# Radio sources
FM_SOURCE = 0
IP_SOURCE = 1
    
#class MainWindow(QMainWindow):
#    def __init__(self):        
#        QMainWindow.__init__(self,None) 

class Application(QMainWindow):
    """
    The main application loop
    """
    
    def __init__(self):
        super(Application, self).__init__()
        QObject.__init__(self)       

        from Radio import Radio
        from RadioDNS import RadioDNS, RadioDNSException
        from RadioVIS import RadioVIS
        from RadioEPG import RadioEPG, XSI
        from Stream import Stream
        from Interface import VisCanvas, Interface, FrequencyDialogue, PresetDialog, CountryDialog, RadioDNSDialog, EPGDialog, EPGShowDialog
#        from XSI import , XSIParser
            
        self.settings = QSettings()
         
        # Need to get the hybrid delay now to initialise the radio
        self.delay = self.settings.value("delay").toFloat()[0]
          
        self.radio = Radio(self.delay)
        self.stream = Stream()
        self.xsi = XSI()
        self.xsi.debug.connect(self.debugger)
        self.xsi.xsi_parser.stream_url_found.connect(self.stream_url_found)

        self.radio.mixer.debug.connect(self.debugger)
        
        self.radiodns = RadioDNS()
        self.radiovis = RadioVIS()        
        self.source = FM_SOURCE
        self.pi = None
        self.required_pi = None
        self.ps = None
        self.frequency = None
        self.recalling_preset = False
        self.hybrid_enabled = False
        self.rssi_min = None
        self.rssi_max = None
        
        self.shortname = None
        self.fqdn = None
        self.id = None
        
        self.radiovis_found = False
        self.radioepg_found= False
        
        self.frequency_change_worker = FrequencyChangeWorker(self)
        self.frequency_change_worker.debug.connect(self.debugger)
        self.pi_change_worker = PIChangeWorker(self)
        self.ip_change_worker = IPChangeWorker(self)
        self.delay_start_worker = DelayStartWorker(self.radio.mixer, self)
#        self.update_stream_delayed = UpdateStreamDelayed(self)
#        self.update_stream_delayed.stream_url_found.connect(self.stream_url_found)
        
        self.frequency_change_worker.stop_stream.connect(self.stream.stop_stream)
        self.frequency_change_worker.reset_display.connect(self.reset_display)
        
        self.ui = Interface()
        self.ui.menu_store.triggered.connect(self.store_preset)
        self.ui.menu_set_country.triggered.connect(self.update_ecc)
#        self.ui.menu_exit.triggered.connect(self.exiting)
        
        self.ui.signal_mapper.mapped.connect(self.recall_preset)
        self.ui.ecc_prompt.ecc_changed.connect(self.ecc_changed)
        
        self.radiodns.msg.connect(self.ui.radiodns_window.append)
        self.radiodns.no_radiodns.connect(self.no_radiodns)
        
        self.radio.pi_change.connect(self.new_pi)
        self.radio.ps_change.connect(self.new_ps)
        self.radio.scan_done.connect(self.scan_complete)
        self.radio.rds_worker.rds_fail.connect(self.rds_fail)

        self.pi_change_worker.radioepg_available.connect(self.radioepg_available)
        self.pi_change_worker.radiovis_available.connect(self.radiovis_available)
        self.ip_change_worker.radioepg_available.connect(self.radioepg_available)
        self.ip_change_worker.radiovis_available.connect(self.radiovis_available)

        self.radiovis.new_text.connect(self.new_text)
        self.radiovis.new_image.connect(self.new_image)

        self.radio.debug.connect(self.debugger)
        self.radiovis.debug.connect(self.debugger)
        
        self.radioepg_dialog = EPGDialog(self.ui)
        self.radioepg = RadioEPG(self.radioepg_dialog)
        self.radioepg.debug.connect(self.debugger)
        self.radioepg_dialog.next_button.clicked.connect(self.radioepg.next_day)
        self.radioepg_dialog.prev_button.clicked.connect(self.radioepg.prev_day)
        self.ui.radioepg_button.clicked.connect(self.radioepg.display)
        
        self.stream.stream_playing.connect(self.ip_stream_playing)
            
#        self.ui.update_source(" FM ")
              
        self.ui.closing.connect(self.exiting)
#        self.aboutToQuit.connect(self.exiting)
        
    def debugger(self, msg):
        """
        Outputs debug messages to console
        """
        print "DEBUG - %s" % msg   
       
    def main(self):
        """
        Main application loop
        """
        
        from Interface import FrequencyDialogue, PresetDialog, CountryDialog, HybridDialog
        from Radio import RSSIWorker
        
        # Load in any stored settings
        
        self.ecc = self.settings.value("ecc").toString()
        start_freq = "%.2f" % self.settings.value("lastFreq").toFloat()[0]
        self.ui.ps_label.setText("%.1fMHz" % float(start_freq))       
                
        self.hybrid_enabled = self.settings.value("hybrid_enabled").toBool()
        rssi_min = self.settings.value("rssi_min").toInt()[0]   
        rssi_max = self.settings.value("rssi_max").toInt()[0]       
        
        if rssi_min is None or rssi_min == 0: rssi_min = -100
        if rssi_max is None or rssi_max == 0: rssi_max = -90
        if self.delay is None or self.delay == 0: self.delay = 11
        
        # Set up the RSSI Worker thread
        self.rssi_worker = RSSIWorker(rssi_min, rssi_max, self)
        self.rssi_worker.debug.connect(self.debugger)
        self.rssi_worker.rssi_updated.connect(self.update_rssi)
        self.rssi_worker.fm_signal_bad.connect(self.switch_to_ip)
        self.rssi_worker.fm_signal_good.connect(self.switch_to_fm)
        
        # Show the Country prompt if no ECC is set
        if self.ecc is None or len(self.ecc) <1: self.ui.ecc_prompt.show_dialog(self.ecc)
        
        # If no frequency is set, set one
        if start_freq is None or start_freq < 87:
            start_freq = 96.3
        self.frequency = start_freq

        self.radio.enable()
        
        # Initialise tuner UI
        self.ui.tuner = FrequencyDialogue(self.ui)
        self.ui.tuner.set_limits(self.radio.get_low_frequency(), self.radio.get_high_frequency())
        self.ui.tuner.set_frequency(start_freq)
        self.ui.tuner.freq_slider.valueChanged.connect(self.change_freq)
        self.ui.update_preset_labels(self.settings)
        self.ui.tuner.step_down_button.released.connect(self.step_down)
        self.ui.tuner.step_up_button.released.connect(self.step_up)
        self.ui.tuner.scan_button.released.connect(self.scan)

        # Initialise Presets UI
        self.presets_dialog = PresetDialog(self.settings)
        self.presets_dialog.update_preset.connect(self.write_preset)

        # Inistialise Hybrid Settings UI
        self.hybrid_dialog = HybridDialog()
        self.hybrid_dialog.hybrid_settings_updated.connect(self.update_hybrid_settings)
        self.hybrid_dialog.enabled_checkbox.setChecked(self.hybrid_enabled)
        self.hybrid_dialog.rssi_min_input.setText("%d" % rssi_min)
        self.hybrid_dialog.rssi_max_input.setText("%d" % rssi_max)
        self.hybrid_dialog.delay_input.setText("%.1f" % self.delay)
        self.ui.menu_hybrid.triggered.connect(self.hybrid_dialog.show)
        
        # Do the things
        self.radio.tune(self.frequency)
        self.rssi_worker.start()
        self.radio.mixer.start()
    
    def exiting(self):
        """
        Cleanly exit the application
        """
        self.debugger("Application closing")
        self.radio.disable()
        self.frequency_change_worker.quit()
        self.pi_change_worker.quit()
        sys.exit(1)
        
    def new_pi(self, pi, from_preset = False):
        """
        When a new PI code is received, retry the RadioDNS lookup
        """
        if pi == self.pi: return
        self.pi = pi
        
        # If we've recalled a preset, make sure the station is the expected one
        if self.stream is not None and self.required_pi is not None:
            
            if pi != self.required_pi:
                self.debugger("Found PI (%s) does not match preset PI(%s)" % (pi, self.required_pi))
                self.ui.vis_text.setText("Station found, but the PI code does not match the preset")
                self.radio.use_fm = False
                self.radio.lock_to_fm = False
                self.switch_to_ip()
            else:
                self.debugger("Found PI (%s) matches preset PI(%s)" % (pi, self.required_pi))
                self.radio.use_fm = True
                if not from_preset: self.pi_change_worker.start()
        else:
            
            if not from_preset: self.pi_change_worker.start()
        
    def new_text(self, text):
        """
        Called to update the RadioVIS Text.
        """
        self.ui.update_vis_text(text)
        
    def new_image(self, image, link):
        """
        Called to update the RadioVIS Slide.
        """
        self.ui.update_vis_slide(image, link)
        
    def new_ps(self, ps):
        """
        Triggered when a new PS Name is detected.
        """
        if ps == self.ps: return 
        self.ps = ps
        if self.source == FM_SOURCE:
            self.ui.tuner.ps_label.setText(ps)
            self.ui.ps_label.setText(ps)
        self.debugger("New PS name %s found" % ps)
      
    def update_rssi(self, rssi):
        """
        Update the RSSI display
        """    
        self.radio.rssi = rssi
        self.ui.update_rssi("%s" % rssi)
        if rssi < self.rssi_worker.set_point_low: 
            self.ui.fm_text.setStyleSheet("background-color: #ff4a4a; color: #000000")
        elif rssi > self.rssi_worker.set_point_high:
            self.ui.fm_text.setStyleSheet("background-color: #5fff4a; color: #000000")
        else:
            self.ui.fm_text.setStyleSheet("background-color: #ffd74a; color: #000000")
          
    def step_up(self):
        """ 
        Tune up by 0.1MHz.
        """
        self.change_freq((float(self.frequency) + 0.1) * 10)
        
    def step_down(self):
        """ 
        Tune down by 0.1MHz.
        """
        self.change_freq((float(self.frequency) - 0.1) * 10)
        
    def scan(self):
        """
        Start scanning for the next station.
        """
        self.ui.tuner.scan_button.setDisabled(True)
        self.radio.scan_next()
        
    def scan_complete(self):
        """
        Called when scan finds a station.
        """
        self.ui.tuner.scan_button.setEnabled(True)
        self.frequency = self.radio.get_frequency()
        self.ui.tuner.set_frequency(self.frequency)
        self.frequency_change_worker.start()

    def change_freq(self, freq):
        """
        Tune to specified frequency.
        """
        self.frequency = freq/10.0
        # Next bit required to stop preset settings being cleared
        if self.recalling_preset:
            self.recalling_preset = False
        else:
            self.frequency_change_worker.start()    
    
    def reset_display(self):
        self.ui.tuner.ps_label.setText("")
        if self.radiovis.is_subscribed():
            self.radiovis.disconnect()
        self.ui.vis_text.clear()
        self.ui.vis_image.clear()
        self.ui.ps_label.setText("%.1fMHz" % float(self.frequency))
        self.ui.radiodns_window.reset()
        self.ui.radioepg_button.setDisabled(True)
        
        if self.radio.station_found():
            self.ui.vis_text.setText("Waiting for PI Code")
        self.radioepg.ui.schedule_list.clear()
        
        self.ui.ip_text.setStyleSheet("background-color: #999999; color: #000000")
        self.ui.fm_text.setStyleSheet("background-color: #999999; color: #000000")
    
    def recall_preset(self, preset):
        """
        Set station to a stored frequnecy and PI code.
        """
        self.debugger("Recalling preset %s" % preset)
        self.recalling_preset = True
        freq = self.settings.value("preset%ifreq" % preset).toFloat()[0]
        freq = int(freq*100)/100.0
        self.fqdn = None
        self.shortname = None
        if freq > 0:
            
            self.radio.set_frequency(freq)
            
            self.ui.tuner.set_frequency("%.1f" % freq)
            self.pi = None
            self.required_pi = self.settings.value("preset%ipi" % preset).toString()
            
            stream_url = self.settings.value("preset%iurl" % preset).toString()
            
            self.stream.stop_stream()
            
            self.reset_display()
            self.radio.mixer.live_audio()
            self.source = FM_SOURCE
            self.radio.station_watcher.start()
            
            self.radioepg_found = False
            self.radiovis_found = False
            
            if stream_url is not None:    
                self.debugger("Recalled %s from preset" % stream_url)
                self.shortname = self.settings.value("preset%ishortname" % preset).toString()
                self.fqdn = self.settings.value("preset%ifqdn" % preset).toString()
                self.id = self.settings.value("preset%iid" % preset).toString()
                self.debugger("Loaded fqdn %s" % self.fqdn)
                self.stream_url_found(stream_url, self.shortname, self.fqdn, self.id)
        else:
            self.ui.vis_text.setText("There is no station stored in this preset.")
    
    def store_preset(self):
        """
        Launches the store preset dialog.
        """
        self.presets_dialog.prompt()
    
    def write_preset(self, preset):
        """
        Stores the current station in the specified preset
        """
        self.settings.setValue("preset%ifreq" % preset, self.frequency)
        self.settings.setValue("preset%ipi" % preset, self.pi)
        self.settings.setValue("preset%iurl" % preset, self.stream.source)
        self.settings.setValue("preset%ishortname" % preset, self.shortname)
        self.settings.setValue("preset%ifqdn" % preset, self.fqdn)
        self.settings.setValue("preset%ifqdn" % preset, self.id)
        if self.ps is not None:
            self.settings.setValue("preset%ititle" % preset, self.ps)
        elif self.shortname is not None:
            self.settings.setValue("preset%ititle" % preset, self.shortname)
        else:
            self.settings.setValue("preset%ititle" % preset, "Preset %i" % preset)
        self.ui.update_preset_labels(self.settings)

    def update_ecc(self):
        """
        Launch country selection dialog.
        """
        self.ui.ecc_prompt.show_dialog(str(self.ecc).lower())
        
    def ecc_changed(self, ecc):
        """
        User has entered a new country code
        """
        self.ecc = ecc
        self.settings.setValue("ecc", ecc)
        
    def update_hybrid_settings(self, enabled, rssi_min, rssi_max, delay):
        """
        Triggered when the hybrid settings dialog is closed
        """
        self.debugger("Updating hybrid settings") 
        self.hybrid_enabled = enabled
        self.rssi_worker.set_point_low = rssi_min
        self.rssi_worker.set_point_high = rssi_max
        if delay != self.delay:
            import os
            os.system('dbus-send --type=method_call --dest=org.freedesktop.Notifications /org/freedesktop/Notifications org.freedesktop.Notifications.SystemNoteInfoprint string:"Please restart the application to update the delay setting"')
             
        self.delay = delay
        self.settings.setValue("hybrid_enabled", enabled)
        self.settings.setValue("rssi_min", rssi_min)
        self.settings.setValue("rssi_max", rssi_max)
        self.settings.setValue("delay", delay)
        self.hybrid_dialog.hide()
               
    def rds_fail(self):
        """
        Retrigger RDS watcher on the event of a failure.
        """
        if self.radio.station_found() and self.pi == None:
            self.radio.rds_worker.start()
        
    def no_radiodns(self):
        """
        Called when the RadioDNS lookup fails.
        """
        self.ui.vis_text.setText("No RadioDNS services available")
    
    def radiovis_available(self, server, port, transport):
        """
        Called when a RadioVIS service is found
        """
        if self.radiovis_found: return
        self.debugger("RadioVIS service found")
        self.radiovis_found = True
        if transport == "fm": self.radiovis.set_station_fm(self.ecc, self.pi, self.radio.get_frequency())
        if transport == "ip": self.radiovis.set_station_ip(self.id)
        
        self.radiovis.connect(server, port)
    
    def radioepg_available(self, server, transport):
        """
        Called when a RadioEPG service is found 
        """
        if self.radioepg_found: return
        self.debugger("RadioEPG service found")
        self.radioepg_found = True
        if transport == "fm": self.radioepg.set_station_fm(self.ecc, self.pi, self.radio.get_frequency())
        if transport == "ip": self.radioepg.set_station_ip(self.id)
        self.radioepg.set_server(server)
        self.ui.radioepg_button.setEnabled(True)
        self.xsi.set_server(server)
        if transport == "fm": self.xsi.lookup_stream_from_fm(self.ecc, self.pi, self.radio.get_frequency())
                
    def stream_url_found(self, url, shortname, fqdn, id):
        """
        Called when a url has been found from either XSI or preset
        """
        self.debugger("Found url for this station: %s" % url)
        if self.source != IP_SOURCE:
            self.ui.ip_text.setStyleSheet("background-color: #ff4a4a; color: #000000")
        self.stream.set_source(url)
        self.shortname = shortname
        self.ui.ps_label.setText(shortname)
        self.id = id
        if self.hybrid_enabled: self.delay_start_worker.start() 
            
    def switch_to_fm(self):
        """"
        Switch radio source to FM
        """
        if self.source != FM_SOURCE and self.radio.use_fm:
            os.system('dbus-send --type=method_call --dest=org.freedesktop.Notifications /org/freedesktop/Notifications org.freedesktop.Notifications.SystemNoteInfoprint string:"Switching to FM Audio"')
            self.debugger("** SWITCHING TO FM **")
            self.debugger("Stopping stream")
            self.stream.stop_stream()
            self.debugger("Unmuting radio")
            self.radio.mixer.unmute_radio()
            self.source = FM_SOURCE
            self.ui.ip_text.setStyleSheet("background-color: #ff4a4a; color: #000000")    
#        else:
#            self.debugger("Ignoring switch to FM request")
        
    def switch_to_ip(self):
        """
        Switch radio source to IP
        """
        if self.source != IP_SOURCE and self.hybrid_enabled:
            if self.stream.source is None:
                self.debugger("No stream currently available for this station")
                return
            if self.radio.lock_to_fm: return
            self.radio.mixer.delay_switch_worker.quit()
            os.system('dbus-send --type=method_call --dest=org.freedesktop.Notifications /org/freedesktop/Notifications org.freedesktop.Notifications.SystemNoteInfoprint string:"Switching to IP Stream"')
            self.debugger("** SWITCHING TO IP **")
            self.debugger("Starting stream")
            self.source = IP_SOURCE
            self.ui.ip_text.setStyleSheet("background-color: #ffd74a; color: #000000")
            if self.ps is None and self.shortname is not None: self.ui.ps_label.setText(self.shortname)
            
            if self.fqdn is not None and len(self.fqdn) > 0 and self.id is not None: 
                self.debugger("Launching ip_change worker with %s and %s" % (self.id, self.fqdn))
                self.ip_change_worker.set_params(self.id, self.fqdn)
                self.ip_change_worker.start()
                
            self.stream.play_stream()            
#        else:
#            self.debugger("Ignoring switch to IP request")
        
    def ip_stream_playing(self):
        """
        Called once the IP stream has buffered and is playing
        """
        self.debugger("IP stream playing, muting radio")
        self.ui.ip_text.setStyleSheet("background-color: #5fff4a; color: #000000")
        self.radio.mixer.mute_radio()
     
    def goodbye(self):
        """
        Quit the application.
        """
        self.radio.disable()
        sys.exit()
        
class FrequencyChangeWorker(QThread):
    """
    Thread to handle frequency changes.
    """
    
    stop_stream = pyqtSignal(name="stop_stream")
    reset_display = pyqtSignal(name="reset_display")
    debug = pyqtSignal(str, name="debug")
    
    def __init__(self, parent):
        QThread.__init__(self, parent = None)
        self.parent = parent
        self.exiting = False
 
    def __del__(self):
        self.exiting = True
        self.wait()
        
    def run(self):
        self.debug.emit("!!!! Starting FrequencyChangeWorker")
        import traceback
        traceback.print_stack()

        freq = self.parent.frequency
        
        # Reset all the things!
        self.parent.ui.tuner.freq_label.setText(str(freq))
        self.parent.pi = None
        self.parent.ps = None
        self.parent.required_pi = None
        self.parent.shortname = None
        self.parent.fqdn = None
        self.id = None
        self.parent.radiovis_found = False
        self.parent.radioepg_found = False
        
        self.parent.xsi.xsi_parser.quit()
        self.parent.stream.set_source(None)
        
        self.parent.radio.tune(freq)
        self.parent.settings.setValue("lastFreq", freq)      
        
        self.parent.radioepg.schedule_date = None
        self.parent.radio.lock_to_fm = True
         
        self.reset_display.emit()     
        self.stop_stream.emit()

        self.parent.radio.station_watcher.start()
        
class PIChangeWorker(QThread):
    """
    Thread to handle PI code changes.
    """
    radioepg_available = pyqtSignal(str, str, name = "radioepg_available")
    radiovis_available = pyqtSignal(str, int, str, name = "radiovis_available")
    
    def __init__(self, parent):
        QThread.__init__(self, parent = None)
        self.parent = parent
        self.exiting = False
        self.pi = None
        
    def __del__(self):
        self.exiting = True
        self.wait()
        
    def run(self):
        pi = self.parent.pi
        freq = self.parent.radio.get_frequency()
        self.parent.radiodns.set_ecc(self.parent.ecc)
        if not self.parent.radiovis.connected():
            self.parent.ui.vis_text.setText("PI Code found, performing RadioDNS lookup.")
        try:
            cname = self.parent.radiodns.resolve_fqdn(pi, freq)       
            try:
                epg_server, epg_port = self.parent.radiodns.resolve_application('radioepg')              
                self.radioepg_available.emit(epg_server, "fm")
            except:
                # No RadioEPG available
                pass
            try:
                vis_server, vis_port = self.parent.radiodns.resolve_application('radiovis')
                self.radiovis_available.emit(vis_server, vis_port, "fm")
            except:
                # No RadioVIS available
                pass    
        except:
            # No RadioDNS available
            pass
       
class IPChangeWorker(QThread):
    """
    Thread to handle RadioDNS app lookup for IP streams
    """
    radioepg_available = pyqtSignal(str, str, name = "radioepg_available")
    radiovis_available = pyqtSignal(str, int, str, name = "radiovis_available")
    
    def __init__(self, parent):
        QThread.__init__(self, parent = None)
        self.parent = parent
        self.exiting = False
        self.id = None
        self.fqdn = None
        
    def __del__(self):
        self.exiting = True
        self.wait()
        
    def set_params(self, id, fqdn):
        self.id = id
        self.fqdn = fqdn
        
    def run(self):
        if self.fqdn is None or self.id is None: return
        self.parent.radiodns.set_fqdn(self.fqdn)
        try:
            epg_server, epg_port = self.parent.radiodns.resolve_application('radioepg')              
            self.radioepg_available.emit(epg_server, "ip")
        except:
            # No RadioEPG available
            pass
        try:
            vis_server, vis_port = self.parent.radiodns.resolve_application('radiovis')
            self.radiovis_available.emit(vis_server, vis_port, "ip")
        except:
            # No RadioVIS available
            pass    
            
class DelayStartWorker(QThread):
    """
    Thread to start mixer delay
    """
    def __init__(self, mixer, parent):
        QThread.__init__(self, parent = None)
        self.exiting = False
        self.mixer = mixer
        
    def __del__(self):
        self.exiting = True
        self.wait()
        
    def run(self):
        self.mixer.delay_audio()
                  
class App(QApplication):
    def __init__(self, *args):
        QApplication.__init__(self, *args)
        QCoreApplication.setOrganizationName("Global Radio");
        QCoreApplication.setOrganizationDomain("http://www.thisisglobal.com");
        QCoreApplication.setApplicationName("RadioDNS FM");
        
#        self.connect(self, SIGNAL("lastWindowClosed()"), self.exterminate )      
#        self.connect(self, SIGNAL("aboutToQuit()"), self.exterminate )     
#        
        self.application = Application()
           
        self.application.main()

    def exterminate( self ):
        print "Exiting app..."
        self.application.exiting()
        self.exit(0)

def main(args):
    global app
    app = App(args)
    QObject.connect(app, SIGNAL("aboutToQuit()"), app.exterminate )    
    app.exec_()

if __name__ == "__main__":
    main(sys.argv)
                       
#