import sys
sys.path.append('..')

import time

from plexus.nodes.node import BaseNode, PeriodicCallback
from devices.hau_handler import HAUHandler
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

        self.tank_low_volume = 80  # ml
        self.tank_high_volume = 150  # ml
        self.low_conductivity = 1.2  #  mSm/cm временно понизим нижний порог
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

        # зададим начальное положение клапанов
        self.hau_handler.control_valve(1, 0)
        self.hau_handler.control_valve(2, 0)
        self.hau_handler.control_valve(3, 1)
        self.hau_handler.control_valve(4, 0)
        self.hau_handler.control_valve(5, 0)
        self.hau_handler.control_valve(6, 0)
        print("INFO: ", datetime.datetime.now(), " Заданы начальные состояния клапанов. Клапан 3 открыт, 1,2,4-6 закрыты.")

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
            voltage = self.hau_handler.get_pressure(2)  # датчики давлений в РВ перепутаны
            tank_1_state = 175.4*voltage - 396.5  # unstable data from calibration experiment
            if tank_1_state <= self.tank_low_volume:
                print("INFO: ", datetime.datetime.now(), " РВ1 опустошен. Кол-во воды: {}".format(tank_1_state))
                self.tank_1_empty = True
                self.mixer_status = "tank_is_empty"
                print("INFO: ", datetime.datetime.now(), " mixer_status: tank_is_empty.")
                return
            else:
                if tank_1_state >= self.tank_high_volume:
                    print("INFO: ", datetime.datetime.now(), " РВ1 заполнен. Кол-во воды: {}".format(tank_1_state))
                    self.tank_1_empty = False
                    return

            voltage = self.hau_handler.get_pressure(1)
            tank_2_state = 175.4 * voltage - 396.5  # unstable data from calibration experiment
            if tank_2_state <= self.tank_low_volume:
                print("INFO: ", datetime.datetime.now(), " РВ2 опустошен. Кол-во воды: {}".format(tank_2_state))
                self.tank_2_empty = True
                self.mixer_status = "tank_is_empty"
                print("INFO: ", datetime.datetime.now(), " mixer_status: tank_is_empty.")
                return
            else:
                if tank_2_state >= self.tank_high_volume:
                    print("INFO: ", datetime.datetime.now(), " РВ2 заполнен. Кол-во воды: {}".format(tank_1_state))
                    self.tank_2_empty = False
                    return

        # check "tank_is_empty" flag
        if self.mixer_status == "tank_is_empty":
            # check E in camera
            e_volts = self.hau_handler.get_conductivity()
            e = 0.405/(0.0681*e_volts*e_volts - 0.813*e_volts + 2.2)  # unstable data from calibration experiment
            if e <= self.low_conductivity:
                print("INFO: ", datetime.datetime.now(), " В камере смешения низкая электропроводность: {}".format(e))
                # it means that we need to add doze of concentrated nutrient solution
                # firstly run N3 for 1 second - to add small dose of concentrated solution
                self.hau_handler.control_pump(3, 1)
                print("INFO: ", datetime.datetime.now(), " асос 3 включен")
                # wait 1 second
                time.sleep(1)
                # stop N3
                self.hau_handler.control_pump(3, 0)
                print("INFO: ", datetime.datetime.now(), " Насос 3 выключен")
                # then start mixing
                print("INFO: ", datetime.datetime.now(), " Hачато перемешивание")
                self.hau_handler.control_pump(4, 1)
                print("INFO: ", datetime.datetime.now(), " Насос 4 вкключен")
                self.mix_timer = datetime.datetime.now()
                self.mixer_status = "mixing"
                print("INFO: ", datetime.datetime.now(), " mixer_status: mixing")
                # then wait in background
                return
            else:
                print("INFO: ", datetime.datetime.now(), " Электропроводность в камере смешения выше минимума: {}".format(e))
                # solution is ready
                # lets fill the tank
                if self.tank_1_empty:
                    print("INFO: ", datetime.datetime.now(), " Начинаем закачку воды в РВ1")
                    # open valve 1
                    self.hau_handler.control_valve(1, 1)
                    print("INFO: ", datetime.datetime.now(), " клапан 1 открыт")
                    # start N5
                    self.hau_handler.control_pump(5, 1)
                    print("INFO: ", datetime.datetime.now(), " насос 5 включен")
                    self.mix_timer = datetime.datetime.now()
                    self.mixer_status = "filling"
                    return

                if self.tank_2_empty:
                    print("INFO: ", datetime.datetime.now(), " Начинаем закачку воды в РВ2")
                    # open valve 2
                    self.hau_handler.control_valve(2, 1)
                    print("INFO: ", datetime.datetime.now(), " клапан 2 открыт")
                    # start N5
                    self.hau_handler.control_pump(5, 1)
                    print("INFO: ", datetime.datetime.now(), " насос 5 включен")
                    self.mix_timer = datetime.datetime.now()
                    self.mixer_status = "filling"
                    print("INFO: ", datetime.datetime.now(), " mixer_status: filling")
                    return

        # check "filling" flag
        if self.mixer_status == "filling":
            # check timer
            if datetime.datetime.now() - self.mix_timer >= self.filling_time:
                print("INFO: ", datetime.datetime.now(), " Время закачки вышло. Закачка окончена")
                # then time is come
                # stop filling
                self.hau_handler.control_pump(5, 0)
                print("INFO: ", datetime.datetime.now(), " насос 5 выключен")
                # close correct valve
                if self.tank_1_empty:
                    self.hau_handler.control_valve(1, 0)
                    print("INFO: ", datetime.datetime.now(), " клапан 1 закрыт")

                if self.tank_2_empty:
                    self.hau_handler.control_valve(2, 0)
                    print("INFO: ", datetime.datetime.now(), " клапан 2 закрыт")

                self.mixer_status = "waiting"
                print("INFO: ", datetime.datetime.now(), " mixer_status: waiting")

        # check "mixing" flag
        if self.mixer_status == "mixing":
            # check timer
            if datetime.datetime.now() - self.mix_timer >= self.mixing_time:
                print("INFO: ", datetime.datetime.now(), " Время перемешивания вышло. Перемешивание окончено")
                # then time is come
                # stop mixing
                self.hau_handler.control_pump(4, 0)
                print("INFO: ", datetime.datetime.now(), " насос 4 выключен")
                self.mixer_status = "tank_is_empty"
                print("INFO: ", datetime.datetime.now(), " mixer_status: tank_is_empty")


if __name__ == "__main__":
    network = config.network

    n1 = HAUNode(network[0]['address'], list_of_nodes=network)
    n1.start()
    n1.join()
