import sys
sys.path.append('..')

from plexus.nodes.node import BaseNode, PeriodicCallback

from devices.hau_handler import HAUHandler

from database_handler import MySQLdbHandler

import config
from datetime import datetime, date, time, timedelta

class HAUNode(BaseNode):

    def __init__(self, endpoint: str, list_of_nodes: list, is_daemon: bool = True):
        super().__init__(endpoint, list_of_nodes, is_daemon)
        self._annotation = "humidification and aeration unit"

        #cоздаем базу данных (если она не существует) с названием как в конфиге
        db_handler = MySQLdbHandler(config.db_params)
        db_handler.create_database()

        self.hau_handler = HAUHandler(
            name="hau_handler",
        )
        self.add_device(self.hau_handler)

        self.pumping = False
        self.mixing = True
        self.pumping_time = timedelta(seconds=143)
        self.mixing_time = timedelta(seconds=420)
        self.pumping_start_time = datetime.now()
        self.mixing_start_time = datetime.now() - self.mixing_time


    def custom_preparation(self):
        self.expulsion_of_bubbles_timer = PeriodicCallback(self.pump, 500)

        self.expulsion_of_bubbles_timer.start()

    def pump(self):
        if self.pumping == False and self.mixing == True and (datetime.now() - self.mixing_start_time) >= self.mixing_time:
            self.hau_handler.control_pump(4, 0)
            print("INFO: ", datetime.now(), " насос 4 выключен")
            self.mixing = False

            conductivity = self.hau_handler.get_conductivity()
            print("INFO: ", datetime.now(), "Данные с кондуктометра ПОСЛЕ перемешивания: ", conductivity)
            self.hau_handler.control_pump(5, 1)

            print("INFO: ", datetime.now(), " насос 5 включен")
            self.pumping_start_time = datetime.now()
            self.pumping = True
        elif self.pumping == True and self.mixing == False and (datetime.now() - self.pumping_start_time >= self.pumping_time):
            self.hau_handler.control_pump(5, 0)
            print("INFO: ", datetime.now(), " насос 5 выключен")
            self.pumping = False

            conductivity = self.hau_handler.get_conductivity()
            print("INFO: ", datetime.now(), "Данные с кондуктометра ДО перемешивания: ", conductivity)

            self.hau_handler.control_pump(4, 1)
            print("INFO: ", datetime.now(), " насос 4 включен")
            self.mixing_start_time = datetime.now()
            self.mixing = True





if __name__ == "__main__":
    network = config.network

    n1 = HAUNode(network[0]['address'], list_of_nodes=network)
    n1.start()
    n1.join()
