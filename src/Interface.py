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
from PyQt4 import QtGui
from PyQt4.Qt import *
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from PyQt4.QtNetwork import QHttp
from PyQt4 import QtWebKit
from PyQt4.QtCore import pyqtSignal

class MainWindow(QMainWindow):
    def __init__(self):        
        QMainWindow.__init__(self,None) 
        
class VisCanvas(QLabel):
    """
    Subclassing QLabel to a 'clicked' signal
    """
    def __init__(self, parent):
        QLabel.__init__(self, parent)
        
    def mouseReleaseEvent(self,ev):
        self.emit(SIGNAL('clicked()'))
        
class Interface(QObject):
    """
    The main application UI.
    """
    closing = pyqtSignal(name="closing")
    
    def __init__(self):
        super(Interface, self).__init__()
        
        self.radiodns_window = RadioDNSDialog()
        
        # Main application window
        self.main_window = MainWindow()
        self.main_window.setObjectName("main_window")
        self.main_window.setWindowTitle("RadioDNS - N900 FM")
        
        self.vis_image = VisCanvas(self.main_window)
        self.vis_image.setGeometry(QtCore.QRect(10, 30, 470, 360))
        self.vis_image.setAutoFillBackground(False)
        self.vis_image.setObjectName("vis_image")
#        self.vis_image.clicked.connect(self.slide_clicked)
        QObject.connect(self.vis_image, SIGNAL("clicked()"), self.slide_clicked)
        
        self.tuning_button = QtGui.QPushButton("Tuning", self.main_window)
        self.tuning_button.setGeometry(QtCore.QRect(500, 280, 291, 51))
        self.tuning_button.setObjectName("tuning_button")
        self.tuning_button.clicked.connect(self.display_tuner)
        
        self.radiodns_button = QtGui.QPushButton("RadioDNS", self.main_window)
        self.radiodns_button.setGeometry(QtCore.QRect(500, 340, 131, 51))
        self.radiodns_button.setObjectName("radiodns_button")
        self.radiodns_button.clicked.connect(self.radiodns_window.display)
        
        self.radioepg_button = QtGui.QPushButton("RadioEPG", self.main_window)
        self.radioepg_button.setGeometry(QtCore.QRect(650, 340, 141, 51))
        self.radioepg_button.setObjectName("radioepg_button")
        self.radioepg_button.setDisabled(True)
        
        self.vis_text = QtGui.QLabel(self.main_window)
        self.vis_text.setGeometry(QtCore.QRect(501, 85, 281, 171))
        self.vis_text.setWordWrap(True)
        self.vis_text.setObjectName("vis_text")
        
        icon_font = QtGui.QFont("Sans Serif", 14, QFont.Bold)
        
        self.ip_text = QtGui.QLabel(self.main_window)
        self.ip_text.setFont(icon_font)
        self.ip_text.setGeometry(QtCore.QRect(750, 10, 42, 32))
        self.ip_text.setObjectName("ip_text")
        self.ip_text.setAlignment(Qt.AlignCenter)
        self.ip_text.setStyleSheet("background-color: #999999; color: #000000")
        self.ip_text.setText("IP")
        
        self.fm_text = QtGui.QLabel(self.main_window)
        self.fm_text.setFont(icon_font)
        self.fm_text.setGeometry(QtCore.QRect(700, 10, 42, 32))
        self.fm_text.setObjectName("fm_text")
        self.fm_text.setAlignment(Qt.AlignCenter)
        self.fm_text.setStyleSheet("background-color: #999999; color: #000000")
        self.fm_text.setText("FM")        

        self.rssi_text = QtGui.QLabel(self.main_window)
        self.rssi_text.setFont(icon_font)
        self.rssi_text.setGeometry(QtCore.QRect(536, 15, 130, 20))
        self.rssi_text.setAlignment(Qt.AlignVCenter)
        self.rssi_text.setObjectName("rssi_text")
        self.rssi_text.setText("FM RSSI: ")
        self.rssi_text.setStyleSheet("color: #cecece")
        
        name_font = QtGui.QFont()
        name_font.setBold(True)
        
        self.ps_label = QtGui.QLabel(self.main_window)
        self.ps_label.setFont(name_font)
        self.ps_label.setGeometry(500, 50, 281, 31)
        self.ps_label.setAlignment(QtCore.Qt.AlignCenter)
        self.ps_label.setObjectName("ps_label")
  
        # Menubar
        self.menubar = QtGui.QMenuBar(self.main_window)
        self.menubar.setGeometry(QRect(0,0,800,21))
        self.menubar.setObjectName("menubar")
        
        # Create Menus
        self.menu_preset = QtGui.QMenu(self.menubar)
        self.menu_preset.setObjectName("menu_preset")
        self.menu_file = QtGui.QMenu(self.menubar)
        self.menu_file.setObjectName("menu_file")
        self.main_window.setMenuBar(self.menubar)
        
        # Create Menu Actions
        self.signal_mapper = QSignalMapper(self)
        self.presets = []
        for i in range (0,5):
            self.presets.insert(i,QAction("Preset &%s" % str(i+1), self))
            self.menu_preset.addAction(self.presets[i])
            self.menubar.addAction(self.menu_preset.menuAction())
            self.signal_mapper.setMapping(self.presets[i], i+1)
            self.connect(self.presets[i], SIGNAL("triggered()"), self.signal_mapper, SLOT("map()"))
        
        self.menu_store = QAction('&Store Station', self)
        self.menu_store.setStatusTip('Store the current station as a present')

        self.menu_file.addAction(self.menu_store)
        self.menubar.addAction(self.menu_preset.menuAction())
        
        self.menu_set_country = QAction('Set &Country',  self)
        self.menu_set_country.setStatusTip('Sets the ECC Code')

        self.menu_file.addAction(self.menu_set_country)
        self.menubar.addAction(self.menu_file.menuAction())

        self.menu_hybrid = QAction('&Hybrid Settings', self)
        self.menu_hybrid.setStatusTip('Settings for hybrid radio')

        self.menu_file.addAction(self.menu_hybrid)
        self.menubar.addAction(self.menu_file.menuAction())
        
        # Create HTTP handler for loading vis slides
        self.http = QHttp()
        self.http.done.connect(self.display_slide)
        self.link = None
        
        # Initialise Frequency Dialogue
        self.tuner = None
        
        # Initialise ECC Dialogue
        self.ecc_prompt = CountryDialog(self)
                
        # Display the GUI
        self.main_window.show()
        
    def update_vis_text(self, msg):
        """
        Update the RadioVIS text.
        """
        self.vis_text.setText(msg)
        
    def clear_vis_text(self):
        """
        Clear the RadioVIS text (on station change).
        """
        self.vis_text.setText("")
        
    def update_vis_slide(self, image, link):
        """
        Request new RadioVIS slide via HTTP
        """
        url = QUrl(image)
        self.link = QUrl(link)
        self.http.setHost(url.host())
        self.http.get(url.path())
     
    def update_rssi(self, text):
        """
        Updated the RSSI
        """
        self.rssi_text.setText("FM RSSI: %s " % text)
        
    def display_slide(self, status):
        """
        Display RadioVIS slide when loaded.
        """
        try:
            self.__imgData = self.http.readAll().data()
            self.__pixMap = QPixmap()
            self.__pixMap.loadFromData(self.__imgData)
            self.__rescaled = self.__pixMap.scaledToHeight(360)
            self.vis_image.setPixmap(self.__rescaled)            
        except:
            pass
        
    def slide_clicked(self):
        if self.link != None and self.link!="":
            self.web_view = QtWebKit.QWebView()
            self.web_view.load(self.link)
            self.web_view.setWindowTitle("Browser")
            self.web_view.show()  
        
    def display_tuner(self):
        """
        Show the tuning window.
        """
        self.tuner.show()
        
    def update_preset_labels(self, settings):
        """
        Updates the labels on the presets buttons.
        """
        for i in range(1,6):
            if settings.contains("preset%ititle" % i):
                self.presets[i-1].setText(settings.value("preset%ititle" % i).toString())
        return
             
class FrequencyDialogue(QtGui.QDialog):
    
    """
    Displays the radio tuning dialogue.
    """
    def __init__(self, parent=None):
        QtGui.QDialog.__init__(self, parent = None, modal = 1)

        self.setWindowTitle("Tuning")
        
        #  Layouts
        self.verticalLayoutWidget = QtGui.QWidget(self)
        self.verticalLayoutWidget.setGeometry(QtCore.QRect(9, 9, 781, 181))
        self.verticalLayoutWidget.setObjectName("verticalLayoutWidget")
        self.verticalLayout = QtGui.QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")

        # Frequency Label
        self.freq_label = QtGui.QLabel(self.verticalLayoutWidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.freq_label.sizePolicy().hasHeightForWidth())
        self.freq_label.setSizePolicy(sizePolicy)
        self.freq_label.setObjectName("freq_label")
        self.freq_label.setText("xxx.xMHz")
        self.horizontalLayout_2.addWidget(self.freq_label)
        
        # Spacer
        spacerItem = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem)
        
        # PS Label
        self.ps_label = QtGui.QLabel(self.verticalLayoutWidget)
        self.ps_label.setObjectName("ps_label")
        
        # Spacer
        self.horizontalLayout_2.addWidget(self.ps_label)
        spacerItem1 = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem1)

        # Scan Button
        self.scan_button = QtGui.QPushButton("Scan", self.verticalLayoutWidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(60)
        sizePolicy.setVerticalStretch(60)
        sizePolicy.setHeightForWidth(self.scan_button.sizePolicy().hasHeightForWidth())
        self.scan_button.setSizePolicy(sizePolicy)
        self.scan_button.setObjectName("scan_button")
        self.horizontalLayout_2.addWidget(self.scan_button)
        
        # Layout
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        
        # Step down button
        self.step_down_button = QtGui.QPushButton("<", self.verticalLayoutWidget)
        self.step_down_button.setObjectName("step_down_button")
        self.horizontalLayout.addWidget(self.step_down_button)
        
        # Slider 
        self.freq_slider = QtGui.QSlider(self.verticalLayoutWidget)
        self.freq_slider.setOrientation(QtCore.Qt.Horizontal)
        self.freq_slider.setObjectName("freq_slider")
        self.horizontalLayout.addWidget(self.freq_slider)
        
        # Steup up button 
        self.step_up_button = QtGui.QPushButton(">",self.verticalLayoutWidget)
        self.step_up_button.setObjectName("step_up_button")
        self.horizontalLayout.addWidget(self.step_up_button)
        self.verticalLayout.addLayout(self.horizontalLayout)

    def set_limits(self, min, max):
        """
        Sets the min and max tuning range of the radio.
        """
        self.freq_slider.setMinimum(min*10)
        self.freq_slider.setMaximum(max*10)
        self.freq_slider.setTickPosition(3)
        self.freq_slider.setTickInterval(1)

    def set_frequency(self, freq):
        """
        Sets the slider position and frequency label.
        """
        self.freq_slider.setValue(float(freq)*10)
        self.freq_label.setText(freq)
        
class PresetDialog(QtGui.QMessageBox):
    """
    Prompts which preset position to save current station to.
    """
    update_preset = pyqtSignal(int, name="update_preset")
    
    def __init__(self, settings):
        QtGui.QMessageBox.__init__(self)
        self.presets = []
        self.settings = settings
        self.rendered = False
    
    def prompt(self):
        if not self.rendered:
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
                self.rendered = True       
        
        QtGui.QMessageBox.exec_(self)     
        try:
            self.presetNumber = int(self.presets.index(self.clickedButton())+1)
            self.update_preset.emit(self.presetNumber)
        except:
            return
        
class CountryDialog(QtGui.QWidget):
    """
    Popup menu to set the ECC.
    """
    ecc_changed = pyqtSignal(str, name = "ecc_changed")
    
    def __init__(self, controller, parent=None):
        QtGui.QWidget.__init__(self, parent)
    
    def show_dialog(self, old_ecc):
        if old_ecc == None:
            old_ecc = ""
        ecc, ok = QtGui.QInputDialog.getText(self, 'Set Country', 'Please enter the country code:', text=old_ecc)    
        if ok:
            self.ecc_changed.emit(ecc)
            
class RadioDNSDialog(QtGui.QMessageBox):
    """
    Displays information regarding RadioDNS lookups.
    """
    def __init__(self):
        QtGui.QMessageBox.__init__(self)
        self.details = []
        
    def append(self, msg):
        self.details.append(str(msg))
        
    def reset(self):
        self.details = []
        
    def display(self):
        self.setWindowTitle("RadioDNS Details")
        self.setText("\n".join(self.details))
        QtGui.QMessageBox.exec_(self)    
        
class EPGDialog(QtGui.QDialog): 
    """
    Displays the RadioEPG Window
    """
    def __init__(self, parent=None):
        QtGui.QDialog.__init__(self, parent = None)

        self.setWindowTitle("RadioEPG")
        self.verticalLayoutWidget = QtGui.QWidget(self)
        self.verticalLayoutWidget.setGeometry(QtCore.QRect(10, 10, 780, 331))
        self.verticalLayoutWidget.setObjectName("verticalLayoutWidget")
        self.verticalLayout = QtGui.QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.prev_button = QtGui.QPushButton("<<", self.verticalLayoutWidget)
        self.prev_button.setObjectName("prev_button")
        self.horizontalLayout.addWidget(self.prev_button)
        self.date_label = QtGui.QLabel(self.verticalLayoutWidget)
        self.date_label.setAlignment(QtCore.Qt.AlignCenter)
        self.date_label.setObjectName("date_label")
        self.horizontalLayout.addWidget(self.date_label)
        self.next_button = QtGui.QPushButton(">>", self.verticalLayoutWidget)
        self.next_button.setObjectName("next_button")
        self.horizontalLayout.addWidget(self.next_button)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.schedule_list = QtGui.QListWidget(self.verticalLayoutWidget)
        self.schedule_list.setObjectName("schedule_list")
        self.verticalLayout.addWidget(self.schedule_list)
 
class EPGShowDialog(QtGui.QMessageBox):
    """
    Displays show details.
    """
    def __init__(self):
        QtGui.QMessageBox.__init__(self)
        self.details = [] 
        
    def display(self, msg):
        self.setWindowTitle("Show Details")
        self.setText(msg)
        QtGui.QMessageBox.exec_(self)        

class HybridDialog(QtGui.QDialog):
    """
    Displays the Hyrbid Radio settings window
    """
    
    hybrid_settings_updated = pyqtSignal(bool, int, int, float, name="hybrid_settings_updated")
    
    def __init__(self, parent=None):
        QtGui.QDialog.__init__(self, parent = None)
        
        self.setWindowTitle("Hybrid Radio Settings")
        self.layoutWidget = QtGui.QWidget(self)
        self.layoutWidget.setGeometry(QtCore.QRect(10, 10, 780, 331))
        self.layoutWidget.setObjectName("layoutWidget")
        self.formLayout = QtGui.QFormLayout(self.layoutWidget)
        self.enabled_checkbox = QtGui.QCheckBox()
        self.rssi_min_input = QtGui.QLineEdit()
        self.rssi_max_input = QtGui.QLineEdit()
        self.delay_input = QtGui.QLineEdit()
        self.save_button = QtGui.QPushButton("Save")
        self.formLayout.addRow("Enabled", self.enabled_checkbox)
        self.formLayout.addRow("RSSI Low Setpoint", self.rssi_min_input)
        self.formLayout.addRow("RSSI High Setpoint", self.rssi_max_input)
        self.formLayout.addRow("Delay (s)", self.delay_input)
        self.formLayout.addRow(self.save_button)
        self.save_button.released.connect(self.save_settings)
        
    def save_settings(self):
        self.hybrid_settings_updated.emit(self.enabled_checkbox.isChecked(), int(self.rssi_min_input.text()), int(self.rssi_max_input.text()), float(self.delay_input.text()))
 
