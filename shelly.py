from requests import Session
from abc import ABC, abstractmethod
import logging
from time import sleep
from typing import Optional
from dataclasses import dataclass




class Rollershutter(ABC):

    @abstractmethod
    def measure(self) -> Optional[Measure]:
        pass




class Shelly25(Rollershutter):

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



class ShellyRollershutter(Rollershutter):

    def __init__(self, addr: str):
        self.device = Rollershutter.auto_select(addr)

    def measure(self) -> Optional[Measure]:
        return self.device.measure()

    @staticmethod
    def auto_select(addr: str) -> Optional[Rollershutter]:
        try:
            s = Shelly1pro(addr)
            s.measure()
            logging.info("detected shelly1pro running on " + addr)
            return s
        except Exception as e:
            pass

        try:
            s = Shelly1pm(addr)
            s.measure()
            logging.info("detected shelly1pm running on " + addr)
            return s
        except Exception as e:
            pass

        try:
            s = ShellyPmMini(addr)
            s.measure()
            logging.info("detected shellyPmMini running on " + addr)
            return s
        except Exception as e:
            pass

        try:
            s = Shelly3em(addr)
            s.measure()
            logging.info("detected shelly3em running on " + addr)
            return s
        except Exception as e:
            pass

        logging.warning("unsupported shelly running on " + addr)
        return None



