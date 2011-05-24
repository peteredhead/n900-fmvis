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

from PyQt4 import *
from PyQt4 import QtGui
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from PyQt4.QtCore import pyqtSignal

class MainWindow(QMainWindow):
    def __init__(self):        
        QMainWindow.__init__(self,None) 

class Application(QMainWindow):
    """
    The main application loop
    """
    def __init__(self):
        super(Application, self).__init__()
        QObject.__init__(self)       

        self.radio = Radio()
        self.radiodns = RadioDNS()
        self.radiovis = RadioVIS()        
      
        self.pi = None
        self.ps = None
        self.frequency = None
        self.frequency_change_worker = FrequencyChangeWorker(self)
        self.pi_change_worker = PIChangeWorker(self)
        
        self.ui = Interface()
        self.ui.menu_store.triggered.connect(self.store_preset)
        self.ui.menu_set_country.triggered.connect(self.update_ecc)
        self.ui.menu_exit.triggered.connect(self.goodbye)
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
        
    def debugger(self, msg):
        print "DEBUG - %s" % msg   
       
    def main(self):
        
        # Load in any stored settings
        self.settings = QSettings()
        self.ecc = self.settings.value("ecc").toString()
        start_freq = self.settings.value("lastFreq").toFloat()[0]
        
        if self.ecc is None or len(self.ecc) <1: self.ui.ecc_prompt.show_dialog(self.ecc)
        
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

        self.radio.tune(self.frequency)
        
    def new_pi(self, pi):
        """
        When a new PI code is received, retry the RadioDNS lookup
        """
        if pi == self.pi: return
        self.pi = pi     
        self.pi_change_worker.run()
        
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
        self.ui.tuner.ps_label.setText(ps)
        self.ui.ps_label.setText(ps)
        print "New PS name %s found." % ps
          
    def step_up(self):
        """ 
        Tune up by 0.1MHz.
        """
        self.change_freq((self.frequency + 0.1) * 10)
        
    def step_down(self):
        """ 
        Tune down by 0.1MHz.
        """
        self.change_freq((self.frequency - 0.1) * 10)
        
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
        self.frequency_change_worker.start()    
    
    def recall_preset(self, preset):
        """
        Set station to a stored frequnecy and PI code.
        """
        freq = self.settings.value("preset%ifreq" % preset).toFloat()[0]
        freq = int(freq*100)/100.0
        if freq > 0:
            self.radio.set_frequency(freq)
            self.ui.tuner.set_frequency(freq)
            pi = self.settings.value("preset%ipi" % preset).toString()
            if pi is not None:
                self.new_pi(pi)
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
        if self.ps is not None:
            self.settings.setValue("preset%ititle" % preset, self.ps)
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
    
    def radiovis_available(self, server, port):
        self.radiovis.set_station(self.ecc, self.pi, self.radio.get_frequency())
        self.radiovis.connect(server, port)
    
    def radioepg_available(self, server):
        self.radioepg.set_station(self.ecc, self.pi, self.radio.get_frequency())
        self.radioepg.set_server(server)
        self.ui.radioepg_button.setEnabled(True)
        
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
    def __init__(self, parent):
        QThread.__init__(self, parent = None)
        self.parent = parent
        self.exiting = False
 
    def __del__(self):
        self.exiting = True
        self.wait()
        
    def run(self):
        freq = self.parent.frequency
        self.parent.ui.tuner.freq_label.setText(str(freq))
        self.parent.pi = None
        self.parent.ps = None
        self.parent.ui.tuner.ps_label.setText("")
        
        self.parent.radio.tune(freq)
        
        if self.parent.radiovis.is_subscribed():
            self.parent.radiovis.disconnect()
            self.parent.ui.vis_text.clear()
            self.parent.ui.vis_image.clear()
            
        self.parent.ui.ps_label.setText("%.1fMHz" % freq)
        self.parent.ui.radiodns_window.reset()
        self.parent.ui.radioepg_button.setDisabled(True)
        self.parent.settings.setValue("lastFreq", freq)
        if self.parent.radio.station_found():
            self.parent.ui.vis_text.setText("Waiting for PI Code")
        self.parent.radioepg.ui.schedule_list.clear()
        self.parent.radioepg.schedule_date = None

class PIChangeWorker(QThread):
    """
    Thread to handle PI code changes.
    """
    radioepg_available = pyqtSignal(str, name = "radioepg_available")
    radiovis_available = pyqtSignal(str, int, name = "radiovis_available")
    
    def __init__(self, parent):
        QThread.__init__(self, parent = None)
        self.parent = parent
        self.exiting = False
        self.pi = None
        
    def __del__(self):
        self.exiting = False
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
#                self.parent.radioepg.set_station(self.parent.ecc, pi, freq)
##                self.parent.radioepg.set_server(epg_server)
#                self.parent.ui.radioepg_button.setEnabled(True)
                self.radioepg_available.emit(epg_server)
            except:
                # No RadioEPG available
                pass
            try:
                vis_server, vis_port = self.parent.radiodns.resolve_application('radiovis')
#                self.parent.radiovis.set_station(self.parent.ecc, pi, freq)
#                self.parent.radiovis.connect(vis_server, vis_port)
                self.radiovis_available.emit(vis_server, vis_port)
            except:
                # No RadioVIS available
                pass    
        except:
            # No RadioDNS available
            pass
                   
if __name__ == "__main__":
    app = QApplication(sys.argv)

    from Radio import Radio
    from RadioDNS import RadioDNS, RadioDNSException
    from RadioVIS import RadioVIS
    from RadioEPG import RadioEPG
    from Interface import *
        
    QCoreApplication.setOrganizationName("Global Radio");
    QCoreApplication.setOrganizationDomain("http://www.thisisglobal.com");
    QCoreApplication.setApplicationName("RadioDNS FM");
    
    application = Application()
    application.main()
    
    sys.exit(app.exec_())
