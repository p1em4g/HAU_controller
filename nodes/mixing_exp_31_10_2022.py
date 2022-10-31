import sys
sys.path.append('..')
from plexus.nodes.node import BaseNode, PeriodicCallback

from devices.hau_handler import HAUHandler

from database_handler import MySQLdbHandler

import config
from datetime import datetime, date, time, timedelta
import time as tm

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

        self.db_handler.create_log_table("info_logs")
        self.db_handler.add_log_in_table("info_logs", "hau_node",
                                         "INIT: Программа запущена. База данных создана.")

        self.state = "checking" # checking, mixing, pumping
        self.low_conductivity = 1.5
        self.pumping = False
        self.mixing = True
        self.pumping_time = 143
        self.mixing_time = 420

    def custom_preparation(self):
        self.expulsion_of_bubbles_timer = PeriodicCallback(self.pump, 500)

        self.expulsion_of_bubbles_timer.start()

    def pump(self):
        e_volts = self.hau_handler.get_conductivity()
        e = 0.405 / (0.0681 * e_volts * e_volts - 0.813 * e_volts + 2.2)
        if e < self.low_conductivity and self.state == "checking":
            print("INFO: ", datetime.now(), "conductivity: {}".format(e))
            self.db_handler.add_log_in_table("info_logs", "hau_node", "conductivity: {}".format(e))

            self.hau_handler.control_pump(3, 1)

            print("INFO: ", datetime.now(), "Pump 3 ON")
            self.db_handler.add_log_in_table("info_logs", "hau_node", "Pump 3 ON")

            tm.sleep(2)
            self.hau_handler.control_pump(3, 1)

            print("INFO: ", datetime.now(), "Pump 3 OFF")
            self.db_handler.add_log_in_table("info_logs", "hau_node", "Pump 3 OFF")

            self.state = "mixing"

            print("INFO: ", datetime.now(), "state = mixing")
            self.db_handler.add_log_in_table("info_logs", "hau_node", "state = mixing")

        elif self.state == "checking":
            print("INFO: ", datetime.now(), "conductivity: {}".format(e))
            self.db_handler.add_log_in_table("info_logs", "hau_node", "conductivity: {}".format(e))

            self.state = "pumping"

            print("INFO: ", datetime.now(), "state = pumping")
            self.db_handler.add_log_in_table("info_logs", "hau_node", "state = pumping")

        if self.state == "mixing":
            self.hau_handler.control_pump(4, 1)

            print("INFO: ", datetime.now(), "Pump 4 ON")
            self.db_handler.add_log_in_table("info_logs", "hau_node", "Pump 4 ON")

            tm.sleep(self.mixing_time)
            self.hau_handler.control_pump(4, 0)

            print("INFO: ", datetime.now(), "Pump 4 OFF")
            self.db_handler.add_log_in_table("info_logs", "hau_node", "Pump 4 OFF")

            self.state = "checking"

            print("INFO: ", datetime.now(), "state = checking")
            self.db_handler.add_log_in_table("info_logs", "hau_node", "state = checking")

        if self.state == "pumping":
            self.hau_handler.control_pump(5, 1)

            print("INFO: ", datetime.now(), "Pump 5 ON")
            self.db_handler.add_log_in_table("info_logs", "hau_node", "Pump 5 ON")

            tm.sleep(self.pumping_time)
            self.hau_handler.control_pump(5, 0)

            print("INFO: ", datetime.now(), "Pump 5 OFF")
            self.db_handler.add_log_in_table("info_logs", "hau_node", "Pump 5 OFF")

            self.state = "mixing"

            print("INFO: ", datetime.now(), "state = mixing")
            self.db_handler.add_log_in_table("info_logs", "hau_node", "state = mixing")


if __name__ == "__main__":
    network = config.network

    n1 = HAUNode(network[0]['address'], list_of_nodes=network)
    n1.start()
    n1.join()
