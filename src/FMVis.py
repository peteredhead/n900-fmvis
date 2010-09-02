#! /usr/bin/env python

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

from PyQt4 import *
from PyQt4 import QtGui
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from PyQt4.QtNetwork import QHttp
from PyQt4 import QtWebKit

import dbus
#import time
import ImageQt
#import StringIO
from FMRadio import FMRadio, FMRadioUnavailableError
from SoundPipe import SoundPipe
import DNS
from ControlMessageListener import *
from RadioDNS import *

stations = []
sound_pipe = SoundPipe()
   
class RadioWorker(QThread):
    def __init__(self, parent = None):
        QThread.__init__(self, parent)
        self.exiting = False
        self.keepAlive = KeepAlive()   
        
    def __del__(self):
        self.exiting = True
        self.wait() 
        
    def run(self):
        self.keepAlive.ping()
        QThread.sleep(14)
 
class KeepAlive():
    def __init__(self):
        bus = dbus.SystemBus()
        obj = bus.get_object("de.pycage.FMRXEnabler", "/de/pycage/FMRXEnabler")
        self.enabler = dbus.Interface(obj, "de.pycage.FMRXEnabler")   
    
    def ping(self):
        self.enabler.request()

class PSWorker(QThread):
    def __init__(self, controller):
        QThread.__init__(self, parent = None)
        self.controller = controller
        self.exiting = False
        
    def run(self):
        pi, ps, rt = self.controller.radio.get_rds()
        while ps.strip() == "":
            pi, ps, rt = self.controller.radio.get_rds()
            QThread.sleep(5)
        self.emit(SIGNAL("ps(QString)"), ps)
                  
    def __del__(self):
        self.exiting = True
        self.wait()  
 
class MainWindow(QMainWindow):
    def __init__(self):        
        QMainWindow.__init__(self,None) 
        
class StompSignal(QObject):
    def __init__(self):
        super(StompSignal, self).__init__()
    
    def stop(self):
        self.emit(SIGNAL("stompStop()"))

class VisCanvas(QLabel):
    def __init__(self, parent):
        QLabel.__init__(self, parent)
        
    def mouseReleaseEvent(self,ev):
        self.emit(SIGNAL('clicked()'))
        
class Radio(QObject):
    def __init__(self):   
        super(Radio, self).__init__()
        self.widget = MainWindow()     
        self.widget.setObjectName("FMWidget")
        self.widget.setWindowTitle("FM RadioVIS")
        self.centralwidget = QWidget(self.widget)
        self.centralwidget.setObjectName("centralwidget")
        self.visImage = VisCanvas(self.centralwidget)
        self.visImage.setGeometry(QRect(30, 20, 470, 360))
        self.visImage.setObjectName("visImage")
        self.visText = QLabel(self.centralwidget)
        self.visText.setGeometry(QRect(30, 390, 751, 31))
        self.visText.setText("")
        self.visText.setWordWrap(True)
        self.visText.setObjectName("visText")
        self.verticalLayoutWidget = QWidget(self.centralwidget)
        self.verticalLayoutWidget.setGeometry(QRect(520, 70, 251, 321))
        self.verticalLayoutWidget.setObjectName("verticalLayoutWidget")
        self.verticalLayout = QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.psLabel = QLabel(self.verticalLayoutWidget)
        font = QFont()
        font.setPointSize(26)
        self.psLabel.setFont(font)
        self.psLabel.setAlignment(Qt.AlignCenter)
        self.psLabel.setObjectName("psLabel")
        self.verticalLayout.addWidget(self.psLabel)
        self.freqLabel = QLabel(self.verticalLayoutWidget)
        self.freqLabel.setAlignment(Qt.AlignCenter)
        self.freqLabel.setObjectName("freqLabel")
        self.verticalLayout.addWidget(self.freqLabel)
        self.freqSlider = QSlider(self.verticalLayoutWidget)
        self.freqSlider.setOrientation(Qt.Horizontal)
        self.freqSlider.setObjectName("freqSlider")
        self.verticalLayout.addWidget(self.freqSlider)
        self.scanButton = QPushButton("Scan", self.verticalLayoutWidget)
        self.scanButton.setObjectName("scanButton")
        self.verticalLayout.addWidget(self.scanButton)    
        self.widget.setCentralWidget(self.centralwidget)
        
        # Menubar
        menubar = QtGui.QMenuBar(self.widget)
        menubar.setGeometry(QRect(0, 0, 800, 21))
        menubar.setObjectName("menubar")
        
        # Create Menus
        menuPreset = QtGui.QMenu(menubar)
        menuPreset.setObjectName("menuPreset")
        menuFile = QtGui.QMenu(menubar)
        menuFile.setObjectName("menuFile")
        self.widget.setMenuBar(menubar)
        
        # Create Actions
        self.signalMapper = QSignalMapper(self)
        self.presets = []
        for i in range (0,5):
            self.presets.insert(i,QAction("Preset &%s" % str(i+1), self))
            menuPreset.addAction(self.presets[i])
            menubar.addAction(menuPreset.menuAction())
            self.signalMapper.setMapping(self.presets[i], i+1)
            self.connect(self.presets[i], SIGNAL("triggered()"), self.signalMapper, SLOT("map()"))
        self.connect(self.signalMapper, SIGNAL("mapped(int)"), self.recallPreset)
        
        self.menuStore = QAction('&Store Station', self)
        self.menuStore.setStatusTip('Store the current station as a present')
        self.connect(self.menuStore, SIGNAL("triggered()"), self.storePreset)
        menuFile.addAction(self.menuStore)
        menubar.addAction(menuPreset.menuAction())
        
        self.menuSetCountry = QAction('Set &Country',  self)
        self.menuSetCountry.setStatusTip('Sets the ECC Code')
        self.connect(self.menuSetCountry, SIGNAL("triggered()"), self.launchECCMenu)
        menuFile.addAction(self.menuSetCountry)
        menubar.addAction(menuFile.menuAction())
        
        self.menuExit = QAction('&Exit', self)
        self.menuExit.setStatusTip('Exits the application')
        self.connect(self.menuExit, SIGNAL("triggered()"), self.goodbye)
        menuFile.addAction(self.menuExit)
        menubar.addAction(menuFile.menuAction())
        
        menuPreset.setTitle(QtGui.QApplication.translate("MainWindow", "Presets", None, QtGui.QApplication.UnicodeUTF8))
        menuFile.setTitle(QtGui.QApplication.translate("MainWindow", "File", None, QtGui.QApplication.UnicodeUTF8))
        self.widget.show()

        self.settings = QSettings()
        self.ecc = self.settings.value("ecc").toString()
        self.startFreq = self.settings.value("lastFreq").toFloat()[0]
        self.oldPi = None
        if self.ecc == None:
            self.launchECCMenu()
        self.conn = None
        self.http = QHttp()
        self.link = None    
        self.radioThread = RadioWorker()
        self.stompSubscribed = False
        self.freqThread = FreqWorker(self)
        self.dnsThread = RDNSWorker(self, self.ecc)     
        self.psThread = PSWorker(self)
        self.scanThread = ScanWorker(self, self.ecc)
        self.stompSig = StompSignal() 
        
        self.updatePresetLabels()
        
        QObject.connect(self.visImage, SIGNAL("clicked()"), self.slideClicked)
        QObject.connect(self.dnsThread, SIGNAL("newSlide(QString, QString)"), self.loadImage)
        QObject.connect(self.dnsThread, SIGNAL("subscribed(bool)"),self.subscriptionStatus)
        QObject.connect(self.psThread, SIGNAL("ps(QString)"), self.updatePS)
        QObject.connect(self.scanThread, SIGNAL("scanComplete()"), self.scanComplete)
#        QObject.connect(self.quitButton,SIGNAL("clicked()"),self.goodbye)
        QObject.connect(self.scanButton,SIGNAL("clicked()"),self.scanNext)
        QObject.connect(self.freqSlider,SIGNAL("valueChanged(int)"),self.changeFreq)
        QObject.connect(self.http, SIGNAL("done(bool)"),self.showImage)
        QObject.connect(self, SIGNAL("stompStop()"), self.dnsThread.stompDisconnect)
        
        
    def recallPreset(self, preset):
        self.presetName = "preset%ifreq" % preset
        self.presetFreq = self.settings.value(self.presetName).toFloat()
        if self.presetFreq[0]>0:
            self.dnsThread.stop()
#            self.visText.setText("Tuning to %s" % self.settings.value("preset%ititle" % preset).toString())
            self.oldPi = str(self.settings.value("preset%ipi" % preset).toString())
            print "oldPi is set to %s" % self.oldPi
            self.changeFreqLabel(self.presetFreq[0])
            self.changeFreq(self.presetFreq[0])
        else:
            self.visText.setText("There is no station stored in the selected preset")
        return
        
    def storePreset(self):
        self.presetPrompt = PresetDialog(self)               
        
    def writePreset(self, preset):
        self.presetName = "preset%ifreq" % preset
        freq = self.radio.get_frequency()
        self.settings.setValue(self.presetName, freq)
        pi, ps, rt = self.radio.get_rds()
        if pi.strip() == "":
            self.settings.setValue("preset%ipi" % preset, None)
        else:
            self.settings.setValue("preset%ipi" % preset, pi.strip())
        if ps.strip() == "":
            self.settings.setValue("preset%ititle" % preset, "Preset %i" % preset)
        else:
            self.settings.setValue("preset%ititle" % preset, ps.strip())
        self.updatePresetLabels()
                
    def updatePresetLabels(self):
        for i in range(1,6):
            if self.settings.contains("preset%ititle" % i):
                self.presets[i-1].setText(self.settings.value("preset%ititle" % i).toString())
        return
        
    def launchECCMenu(self):
        self.eccPrompt = CountryDialog(self)
        self.eccPrompt.showDialog(self.ecc)    
       
    def updateECC(self, newecc):
        if QString.toLower(newecc) == self.ecc:
            return
        else:
            self.settings.setValue("ecc", QString.toLower(newecc))
            self.ecc = QString.toLower(newecc)
            return
        
    def updatePS(self, ps):
        self.psLabel.setText(ps)
        self.psThread.quit()

    def loadImage(self,value,link):    
        url = QUrl(value)
        self.link = QUrl(link)
        self.http.setHost(url.host())
        self.http.get(url.path())
    
    def showImage(self):
        try:
            self.__imgData = self.http.readAll().data()
#            self.__pil_image = Image.open(StringIO.StringIO(self.__imgData))          
#            if self.__pil_image.format == "JPG":
#                self.__qimage = ImageQt.ImageQt(self.__pil_image.resize((470,360)))
#                self.__pixmap = QPixmap.fromImage(self.__qimage)
#                self.visImage.setPixmap(self.__pixmap)
            self.__pixMap = QPixmap()
            self.__pixMap.loadFromData(self.__imgData)
            self.__rescaled = self.__pixMap.scaledToHeight(360)
            self.visImage.setPixmap(self.__rescaled)            
        except:
            print "Failed to display image"
        
    def slideClicked(self):
        if self.link != None and self.link!="":
            self.webView = QtWebKit.QWebView()
            self.webView.load(self.link)
            self.webView.setWindowTitle("Browser")
            self.webView.show()    
        
    def subscriptionStatus(self,value):
        self.stompSubscribed = value
    
    def stompStop(self):
        self.emit(SIGNAL("stompStop()"))
    
    def changeFreq(self, f):
        self.newFreq = f
        self.freqThread.start()
        return      

    def changeFreqLabel(self, f):
        if f < 10000:
            newFreq = f * 100
        else:
            newFreq = f
        self.freqLabel.setText("%0.1f MHz" % (newFreq / 1000.0))
        self.freqSlider.setValue(newFreq / 100)   
        return 

    def scanNext(self):
        self.freqLabel.setText("Scanning...")
        self.scanButton.setDisabled(True)
        self.volume_left, self.volume_right = self.radio.get_volume()
        self.radio.set_volume(1)
        self.psLabel.clear()
        self.scanThread.start()

    def scanComplete(self):
        self.scanThread.quit()
        freq = self.radio.get_frequency()
        self.radio.set_volume(self.volume_left, self.volume_right)
        self.scanButton.setEnabled(True)
        self.changeFreqLabel(freq)
        self.changeFreq(freq)
        
    def main(self):
        keepAlive = KeepAlive()
        keepAlive.ping()
        try:
            self.radio = FMRadio(device="RX-51")
        except FMRadioUnavailableError:
            print "Your device doesn't seem to have a FM radio..."
            sys.exit(1)
    
#        QApplication.connect(self.widget, SIGNAL("lastWindowClosed()"), self.goodbye())
        
        self.radioThread.start()
        self.low, self.high = self.radio.get_frequency_range()
        self.freqSlider.setMinimum(self.low/100)
        self.freqSlider.setMaximum(self.high/100)
        self.freqSlider.setTickPosition(3)
        self.freqSlider.setTickInterval(10)
        
        sound_pipe.on()
        sound_pipe.use_speaker(False)
        sound_pipe.set_speaker_volume(50)
        
        if self.startFreq < self.low or self.startFreq > self.high:
            self.startFreq = self.low
        
        self.radio.set_frequency(self.startFreq)
        self.freqSlider.setValue(self.startFreq / 100)
        dotFreq = "%0.1f MHz" % (self.startFreq / 1000.0)   
        self.freqLabel.setText(dotFreq)    
        self.dnsThread.start()
        
    def goodbye(self):
        print "Goodbye!"
        self.radioThread.quit()
        sound_pipe.off()
        self.radio.close()
        self.radio = None
        sys.exit()

class FreqWorker(QThread):
    def __init__(self, controller):
        QThread.__init__(self, parent = None)
        self.controller = controller
        self.exiting = False
 
    def __del__(self):
        self.exiting = True
        self.wait()
        
    def run(self):
#        self.controller.dnsThread.terminate()
        self.controller.dnsThread.stop()
        self.controller.scanThread.stop()
        self.controller.visImage.clear()
        self.controller.psLabel.clear()
        if self.controller.stompSubscribed == True:
            self.controller.visText.clear()
            self.controller.stompSubscribed = False
            self.controller.stompStop()  
        self.controller.updatePS("")
        f = self.controller.newFreq
        if f < 10000:
            newFreq = f * 100
        else:
            newFreq = f    
        self.controller.freqLabel.setText("%0.1f MHz" % (newFreq / 1000.0))      
        self.controller.radio.set_frequency(newFreq)
        self.controller.settings.setValue("lastFreq", newFreq)
        if self.controller.radio.is_signal_good():
            print "Calling threads"
            self.controller.psThread.start()
#            self.controller.dnsThread.wait()
            self.controller.dnsThread.start()
        return

class ScanWorker(QThread):
    def __init__(self, controller, ecc):
        QThread.__init__(self, parent = None)
        self.controller = controller
        self.exiting = False
            
    def __del__(self):
        self.exiting = True
        self.wait()  
        
    def run(self):
        currentFreq = self.controller.radio.get_frequency() + 100
        self.__is_scanning = True
        for scanFreq in range(currentFreq, self.controller.high + 1, 100):
            self.controller.radio.set_frequency(scanFreq, False)
            is_good = self.controller.radio.is_signal_good()
            if (is_good): 
                self.__is_scanning = False
            if (not self.__is_scanning): break   
        if self.__is_scanning == False:
            self.emit(SIGNAL("scanComplete()"))
        else:
            for scanFreq in range(self.controller.low + 1, currentFreq, 100):
                self.controller.radio.set_frequency(scanFreq, False)
                if (not self.__is_scanning): break
                is_good = self.controller.radio.is_signal_good()
                if (is_good): 
                    self.__is_scanning = False
                if (not self.__is_scanning): break         
        self.__is_scanning = False
        self.emit(SIGNAL("scanComplete()"))

    def stop(self):
        self.__is_scanning = False
        
class PresetDialog(QtGui.QMessageBox):
    def __init__(self, controller):
        QtGui.QMessageBox.__init__(self)
        self.presets = []
        self.settings = QSettings()
        self.setWindowTitle("Store Station")
        self.setText("Please select a preset to replace")
        self.setOrientation(Qt.Vertical)
        for i in range (0,5):
            if self.settings.contains("preset%ititle" % (i+1)):
                label = self.settings.value("preset%ititle" % (i+1)).toString()
            else:
                label = "Preset %i" % (i+1)
            self.presets.insert(i,QtGui.QPushButton(label))
            self.addButton(self.presets[i], QtGui.QMessageBox.ActionRole)       
        self.addButton(QtGui.QMessageBox.Cancel)
        QtGui.QMessageBox.exec_(self)     
        try:
            self.presetNumber = int(self.presets.index(self.clickedButton())+1)
            controller.writePreset(self.presetNumber)
        except:
            return
        
class CountryDialog(QtGui.QWidget):
    def __init__(self, controller, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.setGeometry(300, 300, 350, 80)
        self.setWindowTitle('InputDialog')
        self.button = QtGui.QPushButton('Dialog', self)
        self.button.setFocusPolicy(Qt.NoFocus)
        self.button.move(20, 20)
        self.connect(self.button, SIGNAL('clicked()'), self.showDialog)
        self.setFocus()
        self.label = QtGui.QLineEdit(self)
        self.label.move(130, 22)
        self.controller = controller
        self.text = None
    
    def showDialog(self, oldEcc):
        if oldEcc == None:
            oldEcc = ""
        self.text, ok = QtGui.QInputDialog.getText(self, 'Set Country', 'Please enter the country code:', text=oldEcc)    
        if ok:
            self.label.setText(str(self.text))
            print self.text
            self.controller.updateECC(self.text)

if __name__ == '__main__':

    app = QApplication(sys.argv)
    QCoreApplication.setOrganizationName("Global Radio");
    QCoreApplication.setOrganizationDomain("http://www.thisisglobal.com");
    QCoreApplication.setApplicationName("RadioVIS FM");

    radioApp = Radio()
    radioApp.main()
    
    app.exec_()
    sys.exit()

