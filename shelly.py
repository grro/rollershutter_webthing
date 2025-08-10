from requests import Session
from abc import ABC, abstractmethod
import logging
from typing import Optional



class Rollershutter(ABC):

    @abstractmethod
    def update_position(self, target_position: int) -> int:
        pass

    @abstractmethod
    def current_position(self) -> int:
        pass




class Shelly2(Rollershutter):

    def __init__(self, addr: str):
        self.__session = Session()
        self.addr = addr

    def current_position(self) -> int:
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

    def update_position(self, target_position: int) -> int:
        uri = self.addr + '/roller/0?go=to_pos&roller_pos=' + str(target_position)
        try:
            resp = self.__session.get(uri, timeout=30)
            resp.raise_for_status()
            return target_position
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




class ShellyRollershutter(Rollershutter):

    def __init__(self, addr: str):
        self.addr = addr
        self.device = None

    def update_position(self, target_position: int) -> int:
        if self.device is None:
            self.device = ShellyRollershutter.auto_select(self.addr)
        try:
            return self.device.update_position(target_position)
        except Exception as e:
            self.device = None
            raise e

    def current_position(self) -> int:
        if self.device is None:
            self.device = ShellyRollershutter.auto_select(self.addr)
        try:
            return self.device.current_position()
        except Exception as e:
            self.device = None
            raise e

    @staticmethod
    def auto_select(addr: str) -> Optional[Rollershutter]:
        try:
            s = Shelly2(addr)
            s.current_position()
            logging.info("detected shelly2PM or shelly25 running on " + addr)
            return s
        except Exception as e:
            pass

        logging.warning("unsupported shelly running on " + addr)
        return None

