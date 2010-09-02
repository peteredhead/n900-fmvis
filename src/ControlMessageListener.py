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

import stomp 

class ControlMessageListener(stomp.ConnectionListener):
    def __init__(self, host, port, controller, worker, username=None, password=None):
        self.__host = host
        self.__port = int(port)
        self.__username = username
        self.__password = password
        self.__connected = False
        self.__topics = {}
        self.__conn = None
        self.controller = controller
        self.worker = worker
        
    def connect(self):
        self.__conn = stomp.Connection(host_and_ports=[(self.__host, self.__port)], user=self.__username, passcode=self.__password)
        self.__conn.set_listener(self.__class__.__name__, self)
        self.__conn.start()
        self.__conn.connect()
        for topic in self.__topics.keys(): 
            self.__conn.subscribe({'destination' : topic, 'ack' : 'auto'})
    
    def add_topic(self, topic):
        if self.__conn is not None and self.__conn.is_connected(): 
            self.__conn.subscribe({'destination' : topic, 'ack' : 'auto'})
            
    def on_connected(self, headers, message):
        print "control message listener connected to %s:%d" % (self.__host, self.__port)
        
    def on_disconnected(self, headers=None, message=None):
        print "disconnected from %s:%d" % (self.__host, self.__port)
        self.connect()
        
    def on_error(self, headers, message):
        print "Stomp received an error: %s" % message
        
    def disconnect(self):
        self.__conn.disconnect()
        
    def connected(self):
        return self.__connected
    
    def on_message(self, headers, body):
        if body[0:4] == "TEXT":
            self.controller.visText.setText(body[5:])
            return  
        if body[0:4] == "SHOW":
            if "link" in headers:
                
                link = headers["link"]
            else:
                link = ""
            self.worker.newSlide(body[5:], link)
            return  