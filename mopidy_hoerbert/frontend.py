import logging
import traceback
import pykka
import time
import threading
from mopidy import core
from .gpio_manager import GPIOManager
from humanfriendly import format_timespan

logger = logging.getLogger(__name__)


class GpioFrontend(pykka.ThreadingActor, core.CoreListener):

    def __init__(self, config, core):
        super(GpioFrontend, self).__init__()
        self.core = core
        self.sleep_time = False
        self.config = config['hoerbert']
        self.gpio_manager = GPIOManager(self, config['hoerbert'])

        self.playlists = {}
        self.currentPlaylist = -1

        self.gpio_manager.register_rotary_encode(
            'volume',
            self.config["pin_button_volume_up"],
            self.config["pin_button_volume_down"],
            self.config["volume_steps"]
        )

        self.gpio_manager.register_button(self.config["pin_button_play"], 'play')
        self.gpio_manager.register_button(self.config["pin_button_sleep"], 'sleep')

        #self.gpio_manager.register_button(26, 'Fav8 - GPIO-' + str(26))
        #self.gpio_manager.register_button(16, 'Fav7 - GPIO-' + str(16))
        #self.gpio_manager.register_button(13, 'Play/Pause - GPIO-' + str(13))
        #self.gpio_manager.register_button(12, 'Fav5 - GPIO-' + str(12))
        #self.gpio_manager.register_button(6, 'Sleep - GPIO-' + str(6))
        #self.gpio_manager.register_button(5, 'Fav9 - GPIO-' + str(5))
        #self.gpio_manager.register_button(7, 'Fav4 - GPIO-' + str(7))
        #self.gpio_manager.register_button(8, 'Fav1 - GPIO-' + str(8))
        #self.gpio_manager.register_button(11, 'Fav6 - GPIO-' + str(11))
        #self.gpio_manager.register_button(25, 'Fav2 - GPIO-' + str(25))
        #self.gpio_manager.register_button(9, 'Fav3 - GPIO-' + str(9))

        self.handle_sleep_timer()

    def handle_sleep_timer(self):
        for playlist in self.core.playlists.playlists.get():
            for i in range(1, 10):
                if self.config['playlist_' + str(i)] in playlist.name:
                    if i not in self.playlists:
                        logger.info('Playlist found for ' + str(i) + ' Button: ' + playlist.name)
                    self.playlists[i] = playlist

        if self.sleep_time != False:
            if self.sleep_time > time.time():
                logger.info(format_timespan(self.sleep_time - time.time()) + ' until sleep')
            else:
                logger.info('going to sleep')
                self.sleep_time = False
                self.core.playback.pause()
        self.sleep_handle_thread = threading.Timer(15, self.handle_sleep_timer)
        self.sleep_handle_thread.start()

    def on_failure(exception_type, exception_value, traceback):
        self.sleep_handle_thread.cancel()

    def on_stop(self):
        self.sleep_handle_thread.cancel()

    def playback_state_changed(self, old_state, new_state):
        return
        if new_state == core.PlaybackState.PLAYING:
            self.gpio_manager.set_led(True)
        else:
            self.gpio_manager.set_led(False)

    def input(self, input_event):
        try:
            if input_event['key'] == 'volume':
                current = self.core.playback.volume.get()
                current += input_event["value"]
                if current > 100:
                    current = 100
                if current < 0:
                    current = 0
                logger.info('Volume: ' + str(current))
                self.core.playback.volume = current
            elif input_event['key'] == 'sleep':
                logger.info('starting sleep timer')
                self.sleep_time = time.time() + (self.config['sleep_time'] * 60)
                if self.core.playback.state.get() == core.PlaybackState.PAUSED:
                    logger.info('resuming playback')
                    self.core.playback.play()
            elif input_event['key'] == 'play':
                if self.core.playback.state.get() == core.PlaybackState.PLAYING:
                    logger.info('pausing playback')
                    self.core.playback.pause()
                else:
                    logger.info('resuming playback')
                    self.core.playback.play()
            elif self.playlists[input_event['key']]:
                playlist = self.playlists[input_event['key']]
                if self.currentColor == input_event['key']:
                    current_track = self.core.playback.get_current_track().get()
                    if input_event['long']:
                        for position in self.core.tracklist.get_tl_tracks().get():
                            if current_track.album.name != position.track.album.name:
                                logger.info('Skipping to next Album in Playlist "' + position.track.name)
                                self.core.playback.play(tlid=position.tlid)
                                return
                        self.core.playback.play(tlid=1)
                    else:
                        logger.info('Skipping to next Track in Album "' + current_track.album.name)
                        self.core.playback.next()
                else:
                    logger.info('Switching to Playlist "' + playlist.name)
                    self.currentColor = input_event['key']
                    self.core.tracklist.clear()
                    self.core.tracklist.add(playlist.tracks)
                    self.core.playback.play()

        except Exception:
            traceback.print_exc()
