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

        # переменные для цикла прокачки КМ от пузырей
        self.bubble_expulsion_time1 = time(hour=5, minute=0, second=0)
        self.bubble_expulsion_time2 = time(hour=17, minute=0, second=0)
        self.expel_bubbles_flag = False
        self.first_pumping_completed = False
        self.second_pumping_completed = False
        self.expulsion_of_bubbles_pumping_time = timedelta(seconds=5)
        self.start_time = datetime.now()

        # переменные для цикла увлажнения КМ
        self.active_tank_number = 1  # РВ A1 - это 1, РВ А5 - это 2

    def custom_preparation(self):
        self.expulsion_of_bubbles_timer = PeriodicCallback(self.expel_bubbles, 1000)

        self.expulsion_of_bubbles_timer.start()

    def expel_bubbles(self):
        if (((datetime.now().time() > self.bubble_expulsion_time1) and (self.first_pumping_completed == False)) \
            or ((datetime.now().time() > self.bubble_expulsion_time2) and (self.second_pumping_completed == False))) \
                and (self.expel_bubbles_flag == False):
            self.hau_handler.valve_controller(5, 0)
            print("INFO: клапан 5 закрыт")
            self.hau_handler.valve_controller(6, 0) # закрываем клапаны
            print("INFO: клапан 6 закрыт")
            self.hau_handler.pump_controller(6, 1)
            print("INFO: насос 6 включен")
            self.hau_handler.pump_controller(7, 1)
            print("INFO: насос 7 включен")
            self.expel_bubbles_flag = True
        elif (self.expel_bubbles_flag == True) \
                and (datetime.now() - datetime.combine(date.today(), self.bubble_expulsion_time1)) > self.expulsion_of_bubbles_pumping_time:
            self.expel_bubbles_flag = False
            self.hau_handler.pump_controller(6, 0)
            print("INFO: насос 6 выключен")
            self.hau_handler.pump_controller(7, 0)
            print("INFO: насос 7 выключен")
            self.hau_handler.valve_controller(5, 1) # открываем клапаны
            print("INFO: клапан 5 открыт")
            self.hau_handler.valve_controller(6, 1)
            print("INFO: клапан 6 открыт")

            if self.first_pumping_completed == False:
                self.first_pumping_completed = True
                print("INFO: Первая прокачка КМ от пузырей выполнена")
            else:
                self.second_pumping_completed = True
                print("INFO: Вторая прокачка КМ от пузырей выполнена")

        # обновление флагов для прокачек
        if self.first_pumping_completed == True and self.second_pumping_completed == True \
                and datetime.now().time() > time(hour=0, minute=0, second=0) \
                and datetime.now().time() < self.bubble_expulsion_time1:
            self.first_pumping_completed = False
            self.second_pumping_completed = False
            print("INFO: Флаги для прокачек КМ сброшены")

    # цикл увлажнения
    # если давление падает ниже некоторой границы, начинаем пркоачку из активного РВ
    #
if __name__ == "__main__":
    network = config.network

    n1 = HAUNode(network[0]['address'], list_of_nodes=network)
    n1.start()
    n1.join()
