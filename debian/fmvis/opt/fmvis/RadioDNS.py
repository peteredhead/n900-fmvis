import DNS
from PyQt4 import *
from PyQt4.QtCore import *

from ControlMessageListener import *

class RadioDNS():
    def __init__(self, country=None):
        DNS.ParseResolvConf()
        if country == None:
            self.country = "ce1"
        else:
            self.country = country
        
    def lookup(self, pi, freq):
        padFreq = (int(freq)) / 10
        rdns = "%05d.%s.%s.fm.radiodns.org" % (padFreq, pi.strip(), self.country)
        try:
            r = DNS.DnsRequest(name=rdns, qtype='CNAME')
            a = r.req()
            cname = a.answers[0]["data"]
        except:
            return "Unable to find DNS entry for %s" % rdns, None, None
        status = "Found CNAME: %s" % cname     
        srv = "_radiovis._tcp.%s" % cname
        try:
            r = DNS.DnsRequest(name=srv, qtype='SRV')
            a = r.req()
        except:
            return "Unable to complete SRV lookup on %s" % cname, None, None
        port = a.answers[0]["data"][2]
        server = a.answers[0]["data"][3]
        # Rancid bodge - sorry!
        if server == "vis.musicradio.com":
            port = "61613"
        return "RadioVIS is running on %s %s" % (server, port), server, port    
    
class RDNSWorker(QThread):
    def __init__(self, controller, ecc):
        QThread.__init__(self, parent = None)
        self.controller = controller
        self.rdnsCompleted = False    
        self.exiting = False
        self.radiodns = RadioDNS(ecc)    

    def __del__(self):
        self.exiting = True
#        self.wait()  

    def run(self): 
        self.exiting = False
        self.gotPi = False
        
        self.controller.visText.setText("Blah %s" % self.controller.oldPi )
        if self.controller.oldPi != None and self.controller.oldPi != "": 
            self.startVis(self.controller.oldPi)
        else:
            pi, ps, rt = self.controller.radio.get_rds()
            self.controller.visText.setText("Waiting for PI code")
            while pi.strip() == "0" and self.exiting == False:
                QThread.msleep(500)         
                pi, ps, rt = self.controller.radio.get_rds()
                if pi.strip() != "0":
                    self.gotPi = True
                if self.gotPi == True:
                    break
                if self.exiting == True:
                    return
            if self.gotPi == True:
                self.controller.visText.setText("Received PI Code: %s" % pi.strip())
                self.startVis(pi.strip())
            else:
                self.controller.visText.setText("Leaving thread")
                
    def stop(self):
        self.exiting = True
  
    def startVis(self, pi):
        self.rdnsCompleted = False
        freq = self.controller.radio.get_frequency()
        self.controller.visText.setText("Using PI %s" % pi)
        if self.rdnsCompleted == False and pi.strip() != "0":
            try:
                status, server, port = self.radiodns.lookup(pi, freq)
                if server == None:
                    self.controller.visText.setText(status)
                else:
                    self.rdnsCompleted = True
                    self.controller.visText.setText("Connecting to %s on port %s" % (server, port))
            except:
                self.controller.visText.setText("RadioDNS lookup failed")
        if self.controller.stompSubscribed == True:
            self.stompDisconnect()

        if self.rdnsCompleted == True:
            if server == None:
                self.emit(SIGNAL("subscribed(bool)"),False)
                return
            padFreq = (int(freq)) / 10
            topic = "/topic/fm/%s/%s/%05d" % (self.radiodns.country, pi.strip(), padFreq)
            self.controller.visText.setText("Subscribing to %s on %s %s" % (topic, server, port))
            self.stompConnect(server, port, topic)
        else:
            self.controller.visText.setText(status)
             
    def stompConnect(self, server, port, topic):
        self.stomp = ControlMessageListener(server, port, self.controller, self)   
        self.stomp.connect()
        self.stomp.add_topic("%s/text" % topic)
        self.stomp.add_topic("%s/image" % topic)
        self.emit(SIGNAL("subscribed(bool)"),True)
        return
    
    def stompDisconnect(self):
        try:
            self.stomp.disconnect()
        except:
            print "Disconnect failed"
        self.emit(SIGNAL("subscribed(bool)"),False)
        return    
            
    def newSlide(self, url, link):
        self.emit(SIGNAL("newSlide(QString, QString)"),url,link)