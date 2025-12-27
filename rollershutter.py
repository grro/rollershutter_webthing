import logging
from datetime import datetime
from time import sleep
from typing import List
from abc import ABC, abstractmethod
from threading import Thread
from time import sleep
from shelly import ShellyRollershutter



class Shutter(ABC):

    def __init__(self, name: str):
        self.name = name
        self.__listeners = set()

    def add_listener(self, listener):
        self.__listeners.add(listener)

    def _notify_listeners(self):
        [listener() for listener in self.__listeners]

    def start(self):
        pass

    def stop(self):
        pass

    @abstractmethod
    def position(self) -> int:
        pass

    @abstractmethod
    def set_position(self, target_position: int):
        pass



class RollerShutter(Shutter):

    def __init__(self, name: str, addr: str, reverse_directions: bool):
        self.__is_running = True
        self.__position = 0
        self.__reverse_directions = reverse_directions
        self.__shelly = ShellyRollershutter(addr)
        super().__init__(name)
        try:
            logging.info("shutter " + name + " connected. Current pos: " + str(self.__shelly.current_position()) + " (" + addr + "). reverse_directions=" + str(self.__reverse_directions))
        except Exception as e:
            logging.error("shutter " + name + " could not connect to " + addr + ". Error: " + str(e))

    @property
    def position(self) -> int:
        if self.__reverse_directions:
            return 100 - self.__position
        else:
            return self.__position

    def set_position(self, target_position: int):
        logging.info(self.name + " setting position=" + str(target_position))
        if self.__reverse_directions:
            self.__position = self.__shelly.update_position(100-target_position)
        else:
            self.__position = self.__shelly.update_position(target_position)
        self._notify_listeners()

    def start(self):
        Thread(target=self.__sync_loop, daemon=True).start()

    def stop(self):
        self.__is_running = False

    def __sync_loop(self):
        while self.__is_running:
            try:
                self.__sync()
                self._notify_listeners()
                sleep(3.03)
            except Exception as e:
                logging.warning("error occurred on sync " + str(e))
                sleep(3)

    def __sync(self) -> bool:
        try:
            self.__position = self.__shelly.current_position()
            return True
        except Exception as e:
            return False



class RollerShutters(Shutter):

    def __init__(self, name: str, shutters: List[RollerShutter]):
        self.__shutter = shutters
        [shutter.add_listener(self._notify_listeners) for shutter in shutters]
        super().__init__(name)

    @property
    def position(self) -> int:
        positions = []
        for shutter in self.__shutter:
            try:
                positions.append(shutter.position)
            except Exception as e:
                logging.error("error getting position for " + shutter.name + ": " + str(e))

        total = sum(positions)
        if total == 0:
            return 0
        else:
            return int(total/len(positions))

    def set_position(self, target_position: int):
        for shutter in self.__shutter:
            try:
                shutter.set_position(target_position)
            except Exception as e:
                logging.error("error setting position for " + shutter.name + ": " + str(e))