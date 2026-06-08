import logging
from datetime import datetime
from typing import List, Callable, Set
from abc import ABC, abstractmethod
from threading import Thread
from time import sleep

from shelly import ShellyRollershutter


class Shutter(ABC):

    def __init__(self, name: str):
        self.__name = name
        self.__listeners: Set[Callable[['Shutter'], None]] = set()

    def register_listener(self, listener: Callable[['Shutter'], None]):
        self.__listeners.add(listener)

    def _notify_listeners(self, shutter: 'Shutter'):
        for listener in self.__listeners:
            listener(shutter)

    def start(self):
        pass

    def stop(self):
        pass

    @property
    def name(self) -> str:
        return self.__name

    @property
    @abstractmethod
    def last_pos_update(self) -> datetime:
        pass

    @property
    @abstractmethod
    def position(self) -> int:
        pass

    @abstractmethod
    def set_position(self, target_position: int):
        pass


class RollerShutter(Shutter):

    def __init__(self, name: str, addr: str, reverse_directions: bool):
        super().__init__(name)
        self.__is_running = True
        self.__raw_position = 0
        self.__last_pos_update = datetime.now()
        self.__reverse_directions = reverse_directions
        self.__shelly = ShellyRollershutter(addr)

        try:
            # Safely get initial position on startup
            pos = self.__shelly.current_position()
            if pos is not None:
                self.__raw_position = pos
            logging.info(f"Shutter {name} connected. Current pos: {self.position} ({addr}). reverse_directions={self.__reverse_directions}")
        except Exception as e:
            logging.error(f"Shutter {name} could not connect to {addr}. Error: {e}")

    @property
    def position(self) -> int:
        if self.__reverse_directions:
            return 100 - self.__raw_position
        return self.__raw_position

    @property
    def last_pos_update(self) -> datetime:
        return self.__last_pos_update

    def set_position(self, target_position: int):
        logging.info(f"{self.name} setting position={target_position}")

        raw_target = 100 - target_position if self.__reverse_directions else target_position

        try:
            new_pos = self.__shelly.update_position(raw_target)
            if new_pos is not None:
                self.__raw_position = new_pos
            self.__last_pos_update = datetime.now()
            self._notify_listeners(self)
        except Exception as e:
            logging.error(f"Error setting position for {self.name}: {e}")

    def start(self):
        self.__is_running = True
        Thread(target=self.__sync_loop, daemon=True, name=f"Sync-{self.name}").start()

    def stop(self):
        self.__is_running = False

    def __sync_loop(self):
        while self.__is_running:
            try:
                self.__sync()
                sleep(3.03)
            except Exception as e:
                logging.warning(f"Error occurred on sync loop for {self.name}: {e}")
                sleep(3)

    def __sync(self):
        try:
            pos = self.__shelly.current_position()
            # Only update and notify IF the position actually changed
            if pos is not None and pos != self.__raw_position:
                self.__raw_position = pos
                self.__last_pos_update = datetime.now()
                self._notify_listeners(self)
        except Exception as e:
            logging.warning(f"Error occurred getting current position for {self.name}: {e}")


class RollerShutters(Shutter):

    def __init__(self, name: str, shutters: List[RollerShutter]):
        super().__init__(name)
        self.__shutters = shutters

        for shutter in self.__shutters:
            shutter.register_listener(self._notify_listeners)

    @property
    def position(self) -> int:
        positions = []
        for shutter in self.__shutters:
            try:
                positions.append(shutter.position)
            except Exception as e:
                logging.error(f"Error getting position for {shutter.name}: {e}")

        if not positions:
            return 0
        return int(sum(positions) / len(positions))

    @property
    def last_pos_update(self) -> datetime:
        if not self.__shutters:
            return datetime.now()
        return max(shutter.last_pos_update for shutter in self.__shutters)

    def set_position(self, target_position: int):
        for shutter in self.__shutters:
            try:
                shutter.set_position(target_position)
            except Exception as e:
                logging.error(f"Error setting position for {shutter.name}: {e}")

    def start(self):
        for shutter in self.__shutters:
            shutter.start()

    def stop(self):
        for shutter in self.__shutters:
            shutter.stop()