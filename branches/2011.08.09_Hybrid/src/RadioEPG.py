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
from PyQt4 import *
from PyQt4.QtCore import *
from PyQt4.QtCore import QThread, QObject, pyqtSignal
from PyQt4.QtGui import *

# THE FOLLOW TWO MODULES NED ADDING TO POSTINST
import iso8601
import isodate

import urllib2
from xml.dom.minidom import parse, parseString

import datetime
from Interface import EPGShowDialog

class RadioEPG(QObject):
    """
    RadioEPG Interface
    """
    debug = pyqtSignal(str, name="debug")
    
    def __init__(self, ui):
        QObject.__init__(self, parent = None)
        self.path = None
        self.baseurl = None
        self.epg_parser = EPGParser()
        self.epg_parser.epg_ready.connect(self.display_epg)
        self.epg_parser.epg_error.connect(self.epg_fail)
        self.schedule_date = None
        self.programmes = {}
        self.ui = ui
        self.show_dialog = EPGShowDialog()
        self.ui.schedule_list.itemClicked.connect(self.display_show)
            
    def debugger(self, msg):
        self.debug.emit(msg)    
        
    def display(self):
        """
        Display the EPG UI
        """
        self.ui.show()
        if self.schedule_date is None:
            self.today()
        
    def set_server(self, server):
        """
        Set the EPG server
        """
        self.baseurl = "http://%s%s" % (server, self.path)
        
    def set_station_fm(self, ecc, pi, freq):
        """
        Set the station FM parameters for which EPG is to be retrieved
        """
        self.path = "/fm/%s/%s/%05d" % (ecc, pi, freq * 100)
    
    def set_station_ip(self, id):
        """
        Set the station IP parameters for which EPG is to be retrieved
        """
        self.baseurl = "/ip/%s" % id
    
    def today(self):
        """
        Return schedule for the current day
        """
        self.schedule_date = datetime.date.today()
        self.load_epg()
    
    def next_day(self):
        """
        Increment day by one and return schedule
        """
        if self.schedule_date is None:
            self.schedule_date = datetime.date.today() + datetime.timedelta(days=1)
        else:
            self.schedule_date = self.schedule_date + datetime.timedelta(days=1)
        self.load_epg()

    def prev_day(self):
        """
        Decrement day by one and return schedule
        """
        if self.schedule_date is None:
            self.schedule_date = datetime.date.today() - datetime.timedelta(days=1)
        else:
            self.schedule_date = self.schedule_date - datetime.timedelta(days=1)
        self.load_epg()
    
    def load_epg(self):
        """
        Load EPG for the required day
        """
        self.ui.schedule_list.clear()
        self.ui.schedule_list.addItem("Loading EPG Data")
        filename = "%s_PI.xml" % self.schedule_date.strftime("%Y%m%d")
        url = "%s/%s" % (self.baseurl, filename)
        display_date = self.schedule_date.strftime('%d/%m/%Y')
        self.ui.date_label.setText(display_date)      
        self.debug.emit("About to try and load %s" % url)
        self.epg_parser.set_url(url)
        self.epg_parser.start()
    
    def display_epg(self, programmes):
        """
        Once EPG data is loaded, display on device
        """
        self.debug.emit("Call back to display_epg")
        self.ui.schedule_list.clear()
        self.programmes = programmes
        for programme in programmes:
            start_time = iso8601.parse_date(str(programme['startTime']))
            if start_time.day != self.schedule_date.day: continue
            line = "%s\t%s" % (start_time.strftime("%H:%M"), programme['mediumName'])
            self.ui.schedule_list.addItem(line)
    
    def epg_fail(self):
        """
        Triggered when the EPG XML fails to load
        """
        self.ui.schedule_list.clear()
        self.ui.schedule_list.addItem("Unable to obtain EPG data.")
    
    def display_show(self, item):
        """
        Give more in depth information for a specific show
        """
        pos = self.ui.schedule_list.indexFromItem(item).row()
        programme = self.programmes[pos]
        title = programme['longName']
        desc = programme['description']
        start_time = iso8601.parse_date(str(programme['startTime']))
        duration = isodate.parse_duration(str(programme['duration']))
        end_time = start_time + duration
        time_slot = "%s - %s" % (start_time.strftime("%H:%M"), end_time.strftime("%H:%M"))
        msg = "%s\n%s\n\n%s" % (title, time_slot, desc)
        self.show_dialog.display(msg)  
    
class EPGParser(QThread):
    """
    Threaded class to download and parse EPG XML
    """
    
    debug = pyqtSignal(str, name="debug")
    epg_ready = pyqtSignal(list, name="epg_ready")
    epg_error = pyqtSignal(name="epg_error")
    
    def __init__(self):
        QThread.__init__(self, parent = None)
        self.__url = None
        self.exiting = None
        
    def __del__(self):
        self.exiting = True
        self.wait()
        
    def set_url(self, url):
        self.__url = url  
        
    def run(self):
        self.exiting = False       
        try:
            request = urllib2.Request(self.__url)
            response = urllib2.urlopen(request)
            xml = response.read()      
            programmes = []
            dom = parseString(xml)
            progs = dom.getElementsByTagName('programme')
            for prog in progs:
                programme = {}
                programme['mediumName'] = prog.getElementsByTagName('epg:mediumName')[0].firstChild.nodeValue.strip()
                programme['longName'] = prog.getElementsByTagName('epg:longName')[0].firstChild.nodeValue.strip()
                programme['startTime'] = prog.getElementsByTagName('epg:time')[0].attributes['time'].value
                programme['duration'] = prog.getElementsByTagName('epg:time')[0].attributes['duration'].value
                programme['description'] = prog.getElementsByTagName('epg:longDescription')[0].firstChild.nodeValue.strip()
                programmes.append(programme)
            self.epg_ready.emit(programmes)
        except:
            self.epg_error.emit()
 
class XSI(QObject):
    """
    Class to get alternative sources for the specifed station)\
    """
    
    debug = pyqtSignal(str, name="debug")
    
    def __init__(self):
        QObject.__init__(self, parent = None)
#        self.xsi_location = "http://luigi.thisisglobal.com/epg_min.xml"
        self.xsi_location = None
        self.xsi_parser = XSIParser()
        self.xsi_parser.debug.connect(self.debugger)
        
    def set_server(self, server):
        self.xsi_location = "http://%s/radiodns/epg/XSI.xml" % server
        
    def lookup_stream_from_fm(self, ecc, pi, freq):
        """
        Uses FM bearers to find a stream
        """
        if self.xsi_location == None: return
        self.xsi_parser.set_url(self.xsi_location)
        self.xsi_parser.set_fm_bearer(ecc, pi, freq)
        self.debug.emit("Starting XSI Parser")
        self.xsi_parser.start()
        self.debug.emit("XSI parser running")
        
    def debugger(self, msg):
        self.debug.emit(msg)  
    
class XSIParser(QThread):
    """
    Threaded class to download and parse XSI
    """
    
    stream_url_found = pyqtSignal(str, str, str, str, name="stream_url_found")
    debug = pyqtSignal(str, name="debug")
    
    def __init__(self):
        QThread.__init__(self, parent = None)
        self.__url = None
        self.exiting = False
        
    def __del__(self):
        self.exiting = True
        self.wait()
        
    def set_url(self, url):
        self.__url = url
    
    def set_fm_bearer(self, ecc, pi, freq):
        self.fm_bearer = "fm:%s.%s.%05d" % (ecc, pi, freq * 100)
        self.debug.emit("Searching XSI for bearer: %s" % self.fm_bearer)
        
    def run(self):
        self.exiting = False
        if not self.__url: return 
        if not self.fm_bearer: return
        
        try:
            request = urllib2.Request(self.__url)
            self.debug.emit("Loading %s" % self.__url)
            response = urllib2.urlopen(request)
            xml = response.read()
            self.dom = parseString(xml)
            stream_url = None
            id = None
            shortname = None
            fqdn = None
            matching_bearers = [node for node in self.dom.getElementsByTagName("serviceID")  if node.attributes['id'].value == self.fm_bearer]
            for b in matching_bearers:
                service =  b.parentNode
            
            try: 
                shortname = service.getElementsByTagName("epg:shortName")[0].firstChild.nodeValue.strip()                
            except Exception, err:
                self.debug.emit("%s" % err)
                # No shortname available
                pass
            try:
                fqdn = service.getElementsByTagName("radiodns")[0].getAttribute("fqdn")
                id = service.getElementsByTagName("radiodns")[0].getAttribute("serviceIdentifier")
            except Exception, err:
                # No fqdn available
                pass
            ip_bearers = [node for node in service.getElementsByTagName("serviceID") if node.getAttribute('mime') == "audio/mpeg"]
            for ip_bearer in ip_bearers:
                if ip_bearer.attributes['id'].value.find('http://') >= 0: stream_url = ip_bearer.attributes['id'].value
            if stream_url is not None: self.stream_url_found.emit(stream_url, shortname, fqdn, id)
        except Exception, err:
            self.debug.emit("%s" % err)
        
 