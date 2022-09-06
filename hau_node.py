from plexus.nodes.node import BaseNode, PeriodicCallback

from devices.hau_handler import HAUHandler

from database_handler import MySQLdbHandler

import config


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

        self.pressure_sensor_time = 1000
        self.pump_time = 10 * 1000
        self.pump_state = False
        self.timer = 0


    def custom_preparation(self):
        self.pressure_sensor_timer = PeriodicCallback(self.get_pressure(), self.pressure_sensor_time)
        self.pump_timer = PeriodicCallback(self.pump_control, self.pressure_sensor_timer)

        self.pressure_sensor_timer.start()
        self.pump_timer.start()

    def get_pressure(self):
        self.hau_handler.pressure_getter(2)

    def pump_control(self):
        self.timer += 1
        if self.pump_state == False:
            self.hau_handler.pump_controller(7, 1)
            self.pump_state = True
        elif self.pump_state == True and self.timer > self.pump_time:
            self.hau_handler.pump_controller(7, 0)
            self.pump_state = False
            self.pressure_sensor_timer.stop()
            self.pump_timer.stop()


if __name__ == "__main__":
    network = config.network

    n1 = HAUNode(network[0]['address'], list_of_nodes=network)
    n1.start()
    n1.join()
