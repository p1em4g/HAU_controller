import sys
sys.path.append('..')

from plexus.nodes.node import BaseNode, PeriodicCallback

from devices.hau_handler import HAUHandler

from database_handler import MySQLdbHandler

import config
import time as time_for_sleep
from datetime import datetime, date, timedelta, time

class HAUNode(BaseNode):
    def __init__(self, endpoint: str, list_of_nodes: list, is_daemon: bool = True):
        super().__init__(endpoint, list_of_nodes, is_daemon)
        self._annotation = "humidification and aeration unit"

        # cоздаем базу данных (если она не существует) с навзанием как в конфиге
        self.db_handler = MySQLdbHandler(config.db_params)
        self.db_handler.create_database()

        # создадим базу данных для логов
        self.db_handler.create_log_table("info_logs")
        self.db_handler.add_log_in_table("info_logs", "hau_node",
                                    "INIT: Программа запущена. База данных создана.")

        self.exp_note = "24.01.2023: посадка первой планки"
        self.db_handler.add_log_in_table("info_logs", "hau_node","INIT: exp_note: {}".format(self.exp_note))

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
        self.hau_handler.control_pump(1, 0)
        self.hau_handler.control_pump(2, 0)
        self.hau_handler.control_pump(3, 0)
        self.hau_handler.control_pump(4, 0)
        self.hau_handler.control_pump(5, 0)
        self.hau_handler.control_pump(6, 0)
        self.hau_handler.control_pump(7, 0)
        print("INFO: ", datetime.now(),
              " Заданы начальные состояния клапанов и насосов. Клапан 3 открыт, 1,2,4-6 закрыты. Все насосы отключены.")
        self.db_handler.add_log_in_table("info_logs", "hau_node",
                                    "INIT:  Заданы начальные состояния клапанов и насосов. Клапан 3 открыт, "
                                    "1,2,4-6 закрыты. Все насосы отключены.")

        # Пауза для возможности экстренного отключения системы
        print("INFO: ", datetime.now(), "Далее ПАУЗА 5 секунд. (sleep)")
        self.db_handler.add_log_in_table("info_logs", "hau_node",
                                         "INIT:  Далее ПАУЗА 5 секунд. (sleep)")
        time_for_sleep.sleep(5)

        print("INFO: ", datetime.now(), "Пауза закончена")
        self.db_handler.add_log_in_table("info_logs", "hau_node",
                                         "INIT:  Пауза закончена")


        # var for expel bubbles
        self.bubble_expulsion_time1 = time(hour=5, minute=0, second=0)  # время прокачки 1
        self.bubble_expulsion_time2 = time(hour=17, minute=0, second=0)  # время прокачки 2

        # переменные для цикла увлажнения КМ
        self.humidify_status_1 = "wait" # wait, humidify
        self.humidify_status_2 = "wait"  # wait, humidify
        self.min_critical_pressure_in_root_module = 4.37  # 3,68 В соответсвует -0,75 кПа в КМ1


        self.pumping_pause_time = 9  # время паузы между дозами (seconds)
        self.pumping_time = 6 # время закачки дозы (seconds)

        self.pump_active_time_counter = 0  # показывает сумарное время работы насоса
        self.humidify_active_time = 149  # 297 c - 80 ml, 149 с - 40 мл показывает, сколько времени в сумме должен проработать насос

        self.db_handler.add_log_in_table("info_logs", "hau_node",
                                    (
                                        "INIT: min_critical_pressure_in_root_module = {}, pumpin_pause_time = {}, "
                                     "pumpin_time = {}, pump_active_time_counter = {}, humidify_active_time = {}"
                                     ).format(self.min_critical_pressure_in_root_module_1, self.pumping_pause_time,
                                              self.pumping_time, self.pump_active_time_counter,
                                              self.humidify_active_time))


    def custom_preparation(self):
        self.control_timer = PeriodicCallback(self.control, 1000)

        self.control_timer.start()

    def control(self):
        self.expel_bubbles()
        self.humidify_1()
        self.humidify_2()

    def humidify_1(self):
        valve_num = 6
        sensor_num = 3
        if self.humidify_status_1 == "wait":
            if self.hau_handler.get_pressure(sensor_num) < self.min_critical_pressure_in_root_module:
                self.humidify_status_1 = "humidify"
                return
        else:
            return

        if self.humidify_status_1 == "humidify":
            if self.pump_active_time_counter <= self.humidify_active_time:

                self.hau_handler.control_valve(valve_num, 1)
                self.hau_handler.control_pump(3, 1)
                time_for_sleep.sleep(self.pumping_time)
                self.hau_handler.control_pump(3, 0)
                self.hau_handler.control_valve(valve_num, 0)
                self.pump_active_time_counter += self.pumping_time
                time_for_sleep.sleep(self.pumping_pause_time)
                return
            else:
                self.pump_active_time_counter = 0
                self.humidify_status_1 = "wait"

    def humidify_2(self):
        valve_num = 6
        sensor_num = 3
        if self.humidify_status_2 == "wait":
            if self.hau_handler.get_pressure(sensor_num) < self.min_critical_pressure_in_root_module:
                self.humidify_status_2 = "humidify"
                return
        else:
            return

        if self.humidify_status_2 == "humidify":
            if self.pump_active_time_counter <= self.humidify_active_time:

                self.hau_handler.control_valve(valve_num, 1)
                self.hau_handler.control_pump(3, 1)
                time_for_sleep.sleep(self.pumping_time)
                self.hau_handler.control_pump(3, 0)
                self.hau_handler.control_valve(valve_num, 0)
                self.pump_active_time_counter += self.pumping_time
                time_for_sleep.sleep(self.pumping_pause_time)
                return
            else:
                self.pump_active_time_counter = 0
                self.humidify_status_2 = "wait"


    def expel_bubbles(self):
        if datetime.now().time() == self.bubble_expulsion_time1 or datetime.now().time() == self.bubble_expulsion_time2:
            self.hau_handler.control_pump(3, 0)

            self.hau_handler.control_valve(5, 0)
            self.hau_handler.control_valve(6, 0)
            self.hau_handler.control_pump(6, 1)
            self.hau_handler.control_pump(7, 1)
            time_for_sleep.sleep(600)

            self.hau_handler.control_pump(6, 0)
            self.hau_handler.control_pump(7, 0)






    def turn_off_all_pumps(self):
        self.hau_handler.control_pump(1,0)
        self.hau_handler.control_pump(2, 0)
        self.hau_handler.control_pump(3, 0)
        self.hau_handler.control_pump(4, 0)
        self.hau_handler.control_pump(5, 0)
        self.hau_handler.control_pump(6, 0)
        self.hau_handler.control_pump(7, 0)
        print("INFO: ", datetime.now(), "Произошло отключение всех насосов")
        self.db_handler.add_log_in_table("info_logs", "hau_node",
                                         "turn_off_all_pumps: Произошло отключение всех насосов")
        self.db_handler.add_log_in_table("info_logs", "hau_node", "PROGRAMM: Выполнение программы заверешно")

if __name__ == "__main__":
    network = config.network

    n1 = HAUNode(network[0]['address'], list_of_nodes=network)

    try:
        n1.start()
        n1.join()
    finally:
        n1.turn_off_all_pumps()
