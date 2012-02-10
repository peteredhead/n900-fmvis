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
import gobject, pygst
pygst.require("0.10")
import gst
from PyQt4.QtCore import QObject, QThread, pyqtSignal
import os

LIVE_AUDIO = 0
DELAY_AUDIO = 1
BUFFERING_AUDIO = 2

class Mixer(QObject):
    """
    Class to handle routing audio routing, buffering and muting
    """
    
    debug = pyqtSignal(str, name="debug")
    delay_ready = pyqtSignal(name="delay_ready")
    
    def __init__(self, delay):
        QObject.__init__(self, parent = None)
        
        self.audio_state = LIVE_AUDIO
        self.delay_switch_worker = DelaySwitchWorker(self)
        self.delay_switch_worker.switch_feed.connect(self.play_from_buffer)
        self.delay_switch_worker.debug.connect(self.debugger)
        self.seconds = delay
        self.debug.emit("Using delay of %s seconds" % delay)
        # Live Player
        self.live_player = gst.Pipeline("liveline")
        self.live_source = gst.element_factory_make("pulsesrc", "live_source")
        self.live_player.add(self.live_source)
        self.live_queue = gst.element_factory_make("queue", "live_queue")
        self.live_player.add(self.live_queue)
        self.live_sink = gst.element_factory_make("pulsesink", "live_sink")
        self.live_player.add(self.live_sink)
        self.live_source.link(self.live_queue)
        self.live_queue.link(self.live_sink)
       
        # Delay Player
        self.delay_player = gst.Pipeline("pipeline")     
        self.delay_source = gst.element_factory_make("pulsesrc", "delay_source")
        self.delay_player.add(self.delay_source)
        self.delay_queue = gst.element_factory_make("queue", "delay_queue")
        
        self.delay_queue.set_property("max-size-time",0)
        self.delay_queue.set_property("max-size-buffers",0)
        self.delay_queue.set_property("max-size-bytes",0)
        self.delay_queue.set_property("min-threshold-time",long(self.seconds * 1000000000))
        self.delay_queue.set_property("leaky","no")
        self.delay_player.add(self.delay_queue)
        self.delay_sink = gst.element_factory_make("pulsesink", "delay_sink")
        self.delay_player.add(self.delay_sink)
        self.delay_source.link(self.delay_queue)
        self.delay_queue.link(self.delay_sink)
        
        self.loop = gobject.MainLoop()
#        gobject.threads_init()     
                     
    def start(self):
        """
        Enable PGA Line2 and capture audio from PGA
        """
        # Set input source
        self.set_mixer_property('Input Select', 'ADC')      
        # Enable line
        self.set_mixer_property('Left PGA Mixer Line2L Switch', 'on')
        self.set_mixer_property('Right PGA Mixer Line2R Switch', 'on')
        self.set_mixer_property('PGA Capture Volume', '0,0')  
        # Set headphone output       
        self.set_mixer_property('Jack Function', 'Headset')
        self.set_mixer_property('Left DAC_L1 Mixer Line Switch', 'on')
        self.set_mixer_property('Left DAC_L1 Mixer HP Switch', 'off')
        self.set_mixer_property('Right DAC_R1 Mixer Line Switch', 'on')
        self.set_mixer_property('Right DAC_R1 Mixer HP Switch', 'off')
        self.set_mixer_property('HP DAC Playback Volume', '5,5')
        self.set_mixer_property('Speaker Function', '0')
        self.set_mixer_property('PGA Capture Switch', 'on')
        self.set_mixer_property('PCM Playback Volume', '90')

        self.live_player.set_state(gst.STATE_PLAYING)
#        self.loop.run()

        self.debug.emit("Mixer Started")

    def stop(self):
        """
        Disable PGA line 2 and route audio from mic
        """
        self.set_mixer_property('Left DAC_L1 Mixer Line Switch', 'on')
        self.set_mixer_property('Left DAC_L1 Mixer HP Switch', 'off')
        self.set_mixer_property('Right DAC_R1 Mixer Line Switch', 'on')
        self.set_mixer_property('Right DAC_R1 Mixer HP Switch', 'off')
        # Disable line 2
        self.set_mixer_property('Left PGA Mixer Line2L Switch', "off")
        self.set_mixer_property('Right PGA Mixer Line2R Switch', "off")
        self.set_mixer_property('Left PGA Mixer Line1L Switch', 'on')
        self.set_mixer_property('Right PGA Mixer Line1R Switch', 'on')
        # Set input source
        self.set_mixer_property('PGA Capture Switch', 'off')
        self.set_mixer_property('Input Select', '"Digital Mic"')
        self.set_mixer_property('PGA Capture Volume', '40,40')  
       
        self.delay_player.set_state(gst.STATE_NULL)
        self.live_player.set_state(gst.STATE_NULL)
        self.loop.quit()
        
    def live_audio(self):
        """
        Play live FM audio
        """
        if self.audio_state != LIVE_AUDIO:
            self.debug.emit("++> LIVE AUDIO")
            self.live_player.set_state(gst.STATE_PLAYING)
            self.delay_player.set_state(gst.STATE_NULL)
            self.audio_state = LIVE_AUDIO
#       
    def delay_audio(self):
        """
        Start buffering FM audio
        """
        if self.audio_state == LIVE_AUDIO:
            self.debug.emit("++> DELAY AUDIO")
            self.delay_switch_worker.set_delay(self.seconds)
            
            self.audio_state = BUFFERING_AUDIO
            os.system('dbus-send --type=method_call --dest=org.freedesktop.Notifications /org/freedesktop/Notifications org.freedesktop.Notifications.SystemNoteInfoprint string:"Enabling Audio Buffer"')
            self.delay_player.set_state(gst.STATE_PLAYING)
            self.delay_switch_worker.start()
        
    def play_from_buffer(self):
        """
        Play FM audio from buffer
        """
        if self.audio_state == BUFFERING_AUDIO:
            self.debug.emit("++> PLAY FROM BUFFER")
            self.live_player.set_state(gst.STATE_NULL)
            os.system('dbus-send --type=method_call --dest=org.freedesktop.Notifications /org/freedesktop/Notifications org.freedesktop.Notifications.SystemNoteInfoprint string:"Switched to Delayed Audio"')
            self.audio_state = DELAY_AUDIO
            self.delay_ready.emit()
        
    def set_headphone_level(self, level):
        """
        Set headphone level
        """
        self.set_mixer_property("Line DAC Playback Volume", "%d,%d" % (((level / 100.0) * 63), ((level / 100.0) * 63)))

    def set_mixer_property(self, prop, val):
        """
        Set amixer properties via the command line
        """
        cmd = "amixer -q -c0 cset iface=MIXER,name='%s' %s" % (prop, val)
        os.system(cmd)

    def mute_radio(self):
        """
        Mutes the radio sink
        """
        self.delay_sink.set_property("mute", True)      
        
    def unmute_radio(self):
        """
        Unmute the radio sink
        """
        self.delay_sink.set_property("mute", False)
        
    def debugger(self, msg):
        self.debug.emit(msg)  
        
class DelaySwitchWorker(QThread):
    """
    Thread to switch to the delayed feed after a given duration
    """
    
    switch_feed = pyqtSignal(name="switch_feed")
    debug = pyqtSignal(str, name="debug")
    
    def __init__(self, parent = None):
        QThread.__init__(self, parent)
        self.exiting = False
        self.delay = None
        
    def __del__(self):
        self.exiting = True
        self.wait()    
    
    def set_delay(self, delay):
        self.delay = delay
    
    def run(self):
        self.current_delay = 0
        while not self.exiting and self.current_delay < self.delay:
            self.current_delay = self.current_delay + 0.5
            QThread.msleep(500)
        if not self.exiting:
            self.switch_feed.emit()
            