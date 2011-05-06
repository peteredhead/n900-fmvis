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
import DNS
from PyQt4.QtCore import QObject, pyqtSignal, QThread

class RadioDNSException(Exception):
    
    def __init__(self, msg):
        self.msg = msg
        
    def __str__(self):
        return repr(self.msg)

class RadioDNS(QObject):
    """
    Resolves DNS details for RadioDNS services.
    """
    msg = pyqtSignal(str, name="msg")
    no_radiodns = pyqtSignal(name = "no_radiodns")
    
    def __init__(self, country="ce1"):
        QObject.__init__(self, parent = None)
        DNS.ParseResolvConf()
        self.__country = country
        self.__fqdn = None
                
    def resolve_fqdn(self, pi, freq):
        """
        Resolve broadcast parameters against radiodns.org.
        """
        rdns = "%05d.%s.%s.fm.radiodns.org" % (freq * 100, pi, self.__country)
        self.msg.emit("Resolving %s" % rdns)
        try:
            r = DNS.DnsRequest(name=rdns, qtype='CNAME', timeout=6)
            a = r.req()
            cname = a.answers[0]["data"]
        except:
            self.msg.emit("No RadioDNS entry found.")
            self.no_radiodns.emit()
            raise RadioDNSException("Unable to find RadioDNS entry for %s" % rdns)
        self.__fqdn = cname
        self.msg.emit("Result from RadioDNS: %s" % self.__fqdn)
        return cname
    
    def resolve_application(self, application):
        """
        SRV lookup on domain.
        """
        if self.__fqdn is None: 
            raise RadioDNSException("Attempting to resolve application before fqdn")
        srv = "_%s._tcp.%s" % (application.lower(), self.__fqdn)
        self.msg.emit("Looking up SRV record %s" % srv)
        try:
            r = DNS.DnsRequest(name=srv, qtype='SRV', timeout=6)
            a = r.req()
        except:
            self.msg.emit("No record found matching application %s" % application)
            raise RadioDNSException("Unable to complete SRV lookup - %s" % srv)
        port = a.answers[0]["data"][2]
        server = a.answers[0]["data"][3]
        self.msg.emit("Found %s on server %s:%s" % (application, server, port))
        return server, port
    
    def reset(self):
        """
        Resets the FQDN (used when changing station).
        """
        self.__fqdn = None
        
    def set_ecc(self,ecc):
        """
        Resets the country code (ecc)
        """
        self.__country = ecc 
    