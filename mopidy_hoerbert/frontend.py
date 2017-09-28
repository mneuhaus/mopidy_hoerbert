import logging
import traceback
import pykka
import time
import threading
from mopidy import core
from .gpio_manager import GPIOManager
from humanfriendly import format_timespan
from RPi import GPIO
from time import sleep
from mpd import MPDClient

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
        self.update_playlists_registry()
        self.core.playback.volume = 10
        self.volume = 10

        # self.gpio_manager.register_rotary_encode(
        #     'volume',
        #     self.config["pin_button_volume_up"],
        #     self.config["pin_button_volume_down"],
        #     self.config["volume_steps"]
        # )

        self.gpio_manager.register_button(self.config["pin_button_play"], 'play', longpress=False)
        self.gpio_manager.register_button(self.config["pin_button_sleep"], 'sleep', longpress=False)
        for i in range(1, 10):
            self.gpio_manager.register_button(
                self.config['pin_button_playlist_' + str(i)], "playlist_" + str(i))

        self.handle_sleep_timer()
        self.volume_handle_thread = StoppableThread(target=self.handle_volume)
        self.volume_handle_thread.start()
        self.update_volume()

    def handle_sleep_timer(self):
        self.update_playlists_registry()
        if self.sleep_time != False:
            if self.sleep_time > time.time():
                logger.info(format_timespan(self.sleep_time - time.time()) + ' until sleep')
            else:
                logger.info('going to sleep')
                self.sleep_time = False
                self.core.playback.pause()
        self.sleep_handle_thread = threading.Timer(15, self.handle_sleep_timer)
        self.sleep_handle_thread.start()

    def update_volume(self):
        if self.core.playback.volume.get() != self.volume:
            logger.info('updating volume: ' + str(self.volume))
            self.core.playback.volume = self.volume
        self.update_volume_thread = threading.Timer(0.1, self.update_volume)
        self.update_volume_thread.start()

    def handle_volume(self):
            clk = 4
            dt = 17

            GPIO.setmode(GPIO.BCM)
            GPIO.setup(clk, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(dt, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            longWaitCounter = 0
            longWaitThreshold = 3
            longWaitTime = 0.01
            shortWaitTime = 0.0001
            volumeSteps = 2
            clkLastState = GPIO.input(clk)

            try:
                while not self.volume_handle_thread.stopped():
                    clkState = GPIO.input(clk)
                    dtState = GPIO.input(dt)
                    if clkState != clkLastState:
                        volume = self.volume
                        if dtState != clkState:
                            volume += volumeSteps
                        else:
                            volume -= volumeSteps

                        if volume > 100:
                            volume = 100
                        if volume < 0:
                            volume = 0
                        self.volume = volume
                        longWaitCounter = 0
                        #logger.info('internal volume: ' + str(self.volume))
                    clkLastState = clkState
                    longWaitCounter += 1
                    if longWaitCounter > (longWaitThreshold / shortWaitTime):
                        sleep(longWaitTime)
                    else:
                        sleep(shortWaitTime)
            finally:
                GPIO.cleanup()

    def update_playlists_registry(self):
        for playlist in self.core.playlists.playlists.get():
            for i in range(1, 10):
                playlist_identifier = 'playlist_' + str(i)
                if self.config[playlist_identifier] in playlist.name:
                    if playlist_identifier not in self.playlists:
                        logger.info('Playlist found for ' + str(i) + ' Button: ' + playlist.name)
                    self.playlists[playlist_identifier] = playlist

    def on_failure(exception_type, exception_value, traceback):
        self.sleep_handle_thread.cancel()
        self.update_volume_thread.cancel()

    def on_stop(self):
        self.sleep_handle_thread.cancel()
        self.volume_handle_thread.stop()
        self.update_volume_thread.cancel()

    def playback_state_changed(self, old_state, new_state):
        return
        if new_state == core.PlaybackState.PLAYING:
            self.gpio_manager.set_led(True)
        else:
            self.gpio_manager.set_led(False)

    def input(self, input_event):
        logger.info(input_event['key'])
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
                if self.currentPlaylist == input_event['key']:
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
                    self.currentPlaylist = input_event['key']
                    self.core.tracklist.clear()
                    self.core.tracklist.add(playlist.tracks)
                    self.core.playback.play()

        except Exception:
            traceback.print_exc()


class StoppableThread(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    def __init__(self, *args, **kwargs):
        super(StoppableThread, self).__init__(*args, **kwargs)
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()
