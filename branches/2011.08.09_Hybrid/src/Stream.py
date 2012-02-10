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
from PyQt4.QtCore import QObject, pyqtSignal
from PyQt4.phonon import Phonon
 
class Stream(QObject):
    """
    Class to play the radio via IP streams
    """
    
    stream_playing = pyqtSignal(name="stream_playing")
 
    def __init__(self):
        QObject.__init__(self, parent = None)
        self.media_player = None
        self.source = None
 
    def delayed_init(self):
        """
        Delayed initialisation of class
        """
        if not self.media_player:
            self.media_player = Phonon.MediaObject(self)
            audio_output = Phonon.AudioOutput(Phonon.MusicCategory, self)
            Phonon.createPath(self.media_player, audio_output)
            self.media_player.stateChanged.connect(self.state_changed)
 
    def set_source(self, url):
        """
        Sets the source URL of the stream
        """
        self.source = url
 
    def play_stream(self):
        """
        Start the stream
        """
        if not self.source: pass
        self.delayed_init()
        phonon_source = Phonon.MediaSource(self.source) 
        self.media_player.setCurrentSource(phonon_source)        
        self.media_player.play()
        
    def stop_stream(self):
        """
        Stop the stream
        """
        if self.media_player:
            self.media_player.stop()

    def state_changed(self, new_state):
        """
        Monitors for changes in state of the media player
        """
        if new_state == Phonon.PlayingState:
            self.stream_playing.emit()