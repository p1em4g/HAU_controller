import time

from plexus.nodes.node import BaseNode, PeriodicCallback
from hau_handler import HAUHandler
from database_handler import MySQLdbHandler
import config
import numpy as np
from time import sleep
import datetime


class HAUNode(BaseNode):
    def __init__(self, endpoint: str, list_of_nodes: list, is_daemon: bool = True):
        super().__init__(endpoint, list_of_nodes, is_daemon)
        self._annotation = "humidification and aeration unit"

        # cоздаем базу данных (если она не существует) с навзанием как в конфиге
        db_handler = MySQLdbHandler(config.db_params)
        db_handler.create_database()

        self.tank_low_volume = 0  # ml
        self.tank_high_volume = 200  # ml
        self.low_conductivity = 1.5  #  mSm/cm
        self.high_conductivity = 2.5  # mSm/cm
        self.filling_time = datetime.timedelta(seconds=148)
        self.mixing_time = datetime.timedelta(seconds=461)

        self.tank_1_empty = False
        self.tank_2_empty = False
        self.mixer_status = "waiting"
        # might be  "waiting", "mixing", "filling", "tank_is_empty"
        self.mix_timer = datetime.datetime.now()  # timer for counting time in mixing periods

        self.hau_handler = HAUHandler(
            name="hau_handler",
        )
        self.add_device(self.hau_handler)

    def custom_preparation(self):
        self.mixer_routine = PeriodicCallback(self.mixer, 3000)
        self.mixer_routine.start()

    def mixer(self):
        # main function of mixing routine to call periodically

        # check "waiting" flag
        if self.mixer_status == "waiting":
            # firstly lets update data from tanks
            # it is global variables to use them in other periodical callbacks

            # РВ A1 - это 1, РВ А5 - это 2
            voltage = self.hau_handler.get_pressure(1)
            tank_1_state = 175.4*voltage - 396.5  # unstable data from calibration experiment
            if tank_1_state <= self.tank_low_volume:
                self.tank_1_empty = True
                self.mixer_status = "tank_is_empty"
                return
            else:
                if tank_1_state >= self.tank_high_volume:
                    self.tank_1_empty = False
                    return

            voltage = self.hau_handler.get_pressure(2)
            tank_2_state = 175.4 * voltage - 396.5  # unstable data from calibration experiment
            if tank_2_state <= self.tank_low_volume:
                self.tank_2_empty = True
                self.mixer_status = "tank_is_empty"
                return
            else:
                if tank_2_state >= self.tank_high_volume:
                    self.tank_2_empty = False
                    return

        # check "tank_is_empty" flag
        if self.mixer_status == "tank_is_empty":
            # check E in camera
            e_volts = self.hau_handler.get_conductivity()
            e = 0.405/(0.0681*e_volts*e_volts - 0.813*e_volts + 2.2)  # unstable data from calibration experiment
            if e <= self.low_conductivity:
                # it means that we need to add doze of concentrated nutrient solution
                # firstly run N3 for 1 second - to add small dose of concentrated solution
                self.hau_handler.control_pump(3, 1)
                # wait 1 second
                time.sleep(1)
                # stop N3
                self.hau_handler.control_pump(3, 0)
                # then start mixing
                self.hau_handler.control_pump(4, 1)
                self.mix_timer = datetime.datetime.now()
                self.mixer_status = "mixing"
                # then wait in background
                return
            else:
                # solution is ready
                # lets fill the tank
                if self.tank_1_empty:
                    # open valve 1
                    self.hau_handler.control_valve(1, 1)
                    # start N5
                    self.hau_handler.control_pump(5, 1)
                    self.mix_timer = datetime.datetime.now()
                    self.mixer_status = "filling"
                    return

                if self.tank_2_empty:
                    # open valve 2
                    self.hau_handler.control_valve(2, 1)
                    # start N5
                    self.hau_handler.control_pump(5, 1)
                    self.mix_timer = datetime.datetime.now()
                    self.mixer_status = "filling"
                    return

        # check "filling" flag
        if self.mixer_status == "filling":
            # check timer
            if datetime.datetime.now() - self.mix_timer >= self.filling_time:
                # then time is come
                # stop filling
                self.hau_handler.control_pump(5, 0)
                # close correct valve
                if self.tank_1_empty:
                    self.hau_handler.control_valve(1, 0)

                if self.tank_2_empty:
                    self.hau_handler.control_valve(2, 0)

                self.mixer_status = "waiting"

        # check "mixing" flag
        if self.mixer_status == "mixing":
            # check timer
            if datetime.datetime.now() - self.mix_timer >= self.mixing_time:
                # then time is come
                # stop mixing
                self.hau_handler.control_pump(4, 0)
                self.mixer_status = "tank_is_empty"


if __name__ == "__main__":
    network = config.network

    n1 = HAUNode(network[0]['address'], list_of_nodes=network)
    n1.start()
    n1.join()
