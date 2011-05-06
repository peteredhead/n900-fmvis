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
from PyQt4.QtCore import QObject, pyqtSignal, QThread

import stomp

class RadioVIS(stomp.ConnectionListener, QObject):
    """
    Retrieve images and text using the RadioVIS protocol.
    """   
    new_text = pyqtSignal(str, name="text")
    new_image = pyqtSignal(str, str, name="image")
    connection = pyqtSignal(name="connection")
    subscribed = pyqtSignal(bool, name="subscribed")
    
    debug = pyqtSignal(str, name="debug")
    
    def __init__(self):
        QObject.__init__(self, parent = None)
        self.__conn = None
        self.__connected = False
        self.__base_topic = None
        self.__subscribed = False
        
    def set_station(self, ecc, pi, freq):
        """
        Set the station parameters (country code, pi code and frequency).
        """
        self.__base_topic = "/topic/fm/%s/%s/%05d" % (ecc, pi, freq*100)
    
    def connect(self, host, port):
        """
        Connect to the STOMP server on the specified host and port.
        """
        self.debug.emit("Connecting to stomp on %s - %s" % (host, port))
        self.__conn = stomp.Connection(host_and_ports=[(host, int(port))], user=None, passcode=None)
        self.__conn.set_listener(self.__class__.__name__, self)
        self.__conn.start()
        self.__conn.connect()
        
    def disconnect(self):
        """
        Disconnect from the STOMP server.
        """
        self.__conn.disconnect()
        self.__connected = False
        self.__base_topic = None
        self.__subscribed = False
        self.subscribed.emit(False)
        
    def connected(self):
        """
        Returns the STOMP server connection status.
        """
        return self.__connected
    
    def on_connected(self, headres, message):
        """
        Callback, initiated when connected.
        """
        self.debug.emit("Connected to stomp")
        self.__connected = True
        if self.__base_topic is not None:
            self.debug.emit("Subscribing to %s" % self.__base_topic+"/text")
            self.__conn.subscribe({'destination' : self.__base_topic+"/text", 'ack' : 'auto'})
            self.debug.emit("Subscribing to %s" % self.__base_topic+"/image")
            self.__conn.subscribe({'destination' : self.__base_topic+"/image", 'ack' : 'auto'})
            self.subscribed.emit(True)
            self.__subscribed = True
        else:
            self.debug.emit("No base_topic for subscription!")
            
            
    def on_disconnected(self, headers = None, message = None):
        """
        Callback, initiated when disconnected.
        """
        self.connect()
        
    def on_error(self, headers, message):
        """
        Callback, initiated when an error frame is received.
        """
        # Attempt reconnect?
        pass
    
    def on_message(self, headers, body):
        """
        Callback, initiated when a message frame is received.
        """
        if body[0:4] == "TEXT":
            text = body[5:]
            self.new_text.emit(text)
            return

        if body[0:4] == "SHOW":
            if "link" in headers:
                link = headers["link"]
            else:
                link = ""
            image = body[5:]
            self.new_image.emit(image, link)
        return      
            
    def is_subscribed(self):
        return self.__subscribed
    
        