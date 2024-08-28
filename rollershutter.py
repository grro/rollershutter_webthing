import logging
from requests import Session
from typing import List
from abc import ABC, abstractmethod
from threading import Thread
from time import sleep




class Shelly25:

    def __init__(self, addr: str):
        self.__session = Session()
        self.addr = addr

    def query(self) -> int:
        uri = self.addr + '/roller/0'
        try:
            resp = self.__session.get(uri, timeout=30)
            try:
                data = resp.json()
                current_pos = data['current_pos']
                return current_pos
            except Exception as e:
                raise Exception("called " + uri + " got " + str(resp.status_code) + " " + resp.text + " " + str(e))
        except Exception as e:
            self.__renew_session()
            raise Exception("called " + uri + " got " + str(e))

    def position(self, target_postion: int) -> int:
        uri = self.addr + '/roller/0?go=to_pos&roller_pos=' + str(target_postion)
        try:
            resp = self.__session.get(uri, timeout=30)
            resp.raise_for_status()
            return target_postion
        except Exception as e:
            self.__renew_session()
            raise Exception("called " + uri + " got " + str(e))

    def __renew_session(self):
        logging.info("renew session for " + self.addr)
        try:
            self.__session.close()
        except Exception as e:
            logging.warning(str(e))
        self.__session = Session()




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

    def __init__(self, name: str, addr: str):
        self.__is_running = True
        self.__position = 0
        self.__shelly = Shelly25(addr)
        super().__init__(name)
        logging.info("shutter " + name + " connected (" + addr + ")")

    @property
    def position(self) -> int:
        return self.__position

    def set_position(self, target_position: int):
        logging.info(self.name + " setting position=" + str(target_position))
        self.__position = self.__shelly.position(target_position)
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
            self.__position = self.__shelly.query()
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
        positions = [shutter.position for shutter in self.__shutter]
        total = sum(positions)
        if total == 0:
            return 0
        else:
            return int(total/len(positions))

    def set_position(self, target_position: int):
        [shutter.set_position(target_position) for shutter in self.__shutter]