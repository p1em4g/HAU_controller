from plexus.nodes.node import BaseNode, PeriodicCallback

from devices.hau_handler import HAUHandler

from database_handler import MySQLdbHandler

import config
from datetime import datetime, date, time, timedelta

class HAUNode(BaseNode):
    def __init__(self, endpoint: str, list_of_nodes: list, is_daemon: bool = True):
        super().__init__(endpoint, list_of_nodes, is_daemon)
        self._annotation = "humidification and aeration unit"

        # cоздаем базу данных (если она не существует) с навзанием как в конфиге
        db_handler = MySQLdbHandler(config.db_params)
        db_handler.create_database()

        self.hau_handler = HAUHandler(
            name="hau_handler",
        )
        self.add_device(self.hau_handler)

        self.bubble_expulsion_time1 = time(hour=5, minute=0, second=0)
        self.bubble_expulsion_time2 = time(hour=17, minute=0, second=0)
        self.expel_bubbles_flag = False
        self.first_pumping_completed = False
        self.second_pumping_completed = False
        self.expulsion_of_bubbles_pumping_time = timedelta(seconds=3)
        self.start_time = datetime.now()


    def custom_preparation(self):
        self.expulsion_of_bubbles_timer = PeriodicCallback(self.expel_bubbles(), 1000)

        self.expulsion_of_bubbles_timer.start()

    def expel_bubbles(self):
        if (((datetime.now().time() > self.bubble_expulsion_time1) and (self.first_pumping_completed == False)) \
            or ((datetime.now().time() > self.bubble_expulsion_time2) and (self.second_pumping_completed == False))) \
                and (self.expel_bubbles_flag == False):
            self.hau_handler.valve_controller(5, 0)
            self.hau_handler.valve_controller(6, 0) # закрываем клапаны
            self.hau_handler.pump_controller(6, 1)
            self.hau_handler.pump_controller(7, 1)
            self.expel_bubbles_flag = True
        elif (self.expel_bubbles_flag == True) and (datetime.now() - datetime.combine(date.today(), self.bubble_expulsion_time1)) > self.expulsion_of_bubbles_pumping_time:
            self.expel_bubbles_flag = False
            self.hau_handler.pump_controller(6, 0)
            self.hau_handler.pump_controller(7, 0)
            self.hau_handler.valve_controller(5, 1) # открываем клапаны
            self.hau_handler.valve_controller(6, 1)

            if self.first_pumping_completed == False:
                self.first_pumping_completed = True
            else:
                self.second_pumping_completed = True


if __name__ == "__main__":
    network = config.network

    n1 = HAUNode(network[0]['address'], list_of_nodes=network)
    n1.start()
    n1.join()
