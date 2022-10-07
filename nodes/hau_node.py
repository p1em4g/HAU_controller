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

        # cоздаем базу данных (если она не существует) с навзанием как в конфиге
        db_handler = MySQLdbHandler(config.db_params)
        db_handler.create_database()

        self.hau_handler = HAUHandler(
            name="hau_handler",
        )
        self.add_device(self.hau_handler)

        # переменные для цикла прокачки КМ от пузырей
        self.bubble_expulsion_time1 = time(hour=5, minute=0, second=0) # время прокачки 1
        self.bubble_expulsion_time2 = time(hour=17, minute=0, second=0) # время прокачки 2
        self.expel_bubbles_flag = False
        self.first_pumping_completed = False
        self.second_pumping_completed = False
        self.expulsion_of_bubbles_pumping_time = timedelta(seconds=5)
        self.start_time = datetime.now()

        # переменные для цикла увлажнения КМ
        self.active_tank_number = 1  # РВ A1 - это 1, РВ А5 - это 2
        self.min_critical_pressure_in_tank = None #!!!НАДО ВВЕСТИ АДЕКВАТНОЕ ЗНАЧЕНИЕ!!!
        self.first_tank_water_amount = 1 #!!!НАДО ВВЕСТИ АДЕКВАТНОЕ ЗНАЧЕНИЕ!!!
        self.second_tank_water_amount = 1 #!!!НАДО ВВЕСТИ АДЕКВАТНОЕ ЗНАЧЕНИЕ!!!
        self.min_critical_pressure_in_root_module = 3.0 # !!!НАДО ВВЕСТИ АДЕКВАТНОЕ ЗНАЧЕНИЕ!!!

        self.humidify_active = False  # показывает, активен ли сейчас цикл прокачки

        self.pumpin_pause_time = timedelta(seconds=10)       # время паузы между дозами
        self.pumpin_time = timedelta(seconds=8) # время закачки дозы

        self.pumping_active = False # показыывет, включен ли насос
        self.pumping_start_time = None # показывает время послежнего запуска насоса
        self.pumping_pause_start_time = None # показывает время начала послежней паузы
        self.pumping_pause_active = False # показывает активна ли пауза (возможно, лишняя переменная)

        self.pump_active_time_counter = timedelta(seconds=0) # показывает сумарное время работы насоса
        self.humidify_active_time = timedelta(seconds=296) # показывает, сколько времени в сумме должен проработать насос

        # после прокачки некоторое время игнорируем показания ДД и просто спим
        self.humidify_sleeping = False
        self.humidify_sleeping_start_time = None

    def custom_preparation(self):
        self.expulsion_of_bubbles_timer = PeriodicCallback(self.expel_bubbles, 1000)
        self.root_module_humidify_timer = PeriodicCallback(self.humidify_root_module, 1000)

        self.expulsion_of_bubbles_timer.start()
        self.root_module_humidify_timer.start()

    def control(self):
        # если сейчас активных циклов нет, то выполнить циклы увлажнения КМ
        if not self.humidify_active:
            self.find_empty_tank()
        if not self.expel_bubbles_flag and not self.humidify_active:
            self.humidify_root_module(6, self.active_tank_number, 6) # клапан 6, датчик 6 - параметры для первого КМ
            self.humidify_root_module(4, self.active_tank_number, 5) # клапан 5, датчик 4 - параметры для второго КМ
        if not self.expel_bubbles_flag and not self.humidify_active:
            self.expel_bubbles()

    def find_empty_tank(self):
        print("INFO: ", datetime.now(), "Ищем пустой РВ")
    def expel_bubbles(self):
        if (((datetime.now().time() > self.bubble_expulsion_time1) and (self.first_pumping_completed == False)) \
            or ((datetime.now().time() > self.bubble_expulsion_time2) and (self.second_pumping_completed == False))) \
                and (self.expel_bubbles_flag == False):
            print("INFO: ", datetime.now(), "начинаем прокачку КМ от пузырей")

            self.hau_handler.control_valve(5, 0)
            print("INFO: ", datetime.now(), " клапан 5 закрыт")
            self.hau_handler.control_valve(6, 0) # закрываем клапаны
            print("INFO: ", datetime.now(), " клапан 6 закрыт")
            self.hau_handler.control_pump(6, 1)
            print("INFO: ", datetime.now(), " насос 6 включен")
            self.hau_handler.control_pump(7, 1)
            print("INFO: ", datetime.now(), " насос 7 включен")
            self.expel_bubbles_flag = True
        elif (self.expel_bubbles_flag == True) \
                and (datetime.now() - datetime.combine(date.today(), self.bubble_expulsion_time1)) > self.expulsion_of_bubbles_pumping_time:
            self.expel_bubbles_flag = False
            self.hau_handler.control_pump(6, 0)
            print("INFO: ", datetime.now(), " насос 6 выключен")
            self.hau_handler.control_pump(7, 0)
            print("INFO: ", datetime.now(), " насос 7 выключен")
            self.hau_handler.control_valve(5, 1) # открываем клапаны
            print("INFO: ", datetime.now(), " клапан 5 открыт")
            self.hau_handler.control_valve(6, 1)
            print("INFO: ", datetime.now(), " клапан 6 открыт")

            if self.first_pumping_completed == False:
                self.first_pumping_completed = True
                print("INFO: ", datetime.now(), " Первая прокачка КМ от пузырей выполнена")
            else:
                self.second_pumping_completed = True
                print("INFO: ", datetime.now()," Вторая прокачка КМ от пузырей выполнена")

        # обновление флагов для прокачек
        if self.first_pumping_completed and self.second_pumping_completed \
                and datetime.now().time() > time(hour=0, minute=0, second=0) \
                and datetime.now().time() < self.bubble_expulsion_time1:
            self.first_pumping_completed = False
            self.second_pumping_completed = False
            print("INFO: ", datetime.now(), " Флаги для прокачек КМ сброшены")

    # цикл увлажнения
    # если давление падает ниже некоторой границы, начинаем пркоачку из активного РВ
    # помогите
    def humidify_root_module(self, pressure_sensor_num, tank_num, valve_num):
        pressure = float(self.hau_handler.get_pressure(pressure_sensor_num))
        # если цикл пркоачки неактивен и давление ниже критического и мы не спим, то говорим что цикл прокачки начат
        if (not self.humidify_active) and pressure < self.min_critical_pressure_in_root_module and (not self.humidify_sleeping):
            print("INFO: ", datetime.now(), "Начат цикл увлажнения КМ")
            self.humidify_active = True
            self.hau_handler.control_valve(valve_num, 1)
            print("INFO: ", datetime.now(), " клапан {} открыт".format(valve_num))

            self.pumping_pause_start_time = datetime.now() - self.pumpin_pause_time  # костыль

        # если цикл пркоачки начат и насос в сумме проработал меньше чем надо то ...
        elif self.humidify_active and self.pump_active_time_counter < self.humidify_active_time:
            # если насос выключен и время паузы между дозами прошло, то включаем насос и записываем время его включения
            if not self.pumping_active and (datetime.now() - self.pumping_pause_start_time) >= self.pumpin_pause_time:
                print("INFO: ", datetime.now(), "Начата подача дозы")

                self.hau_handler.control_pump(tank_num, 1)
                print("INFO: ", datetime.now(), " насос {} включен".format(tank_num))

                self.pumping_active = True
                self.pumping_start_time = datetime.now()
            # если насос включен и время работы насоса больше, чем должно быть, выключаем насос
            elif self.pumping_active and (datetime.now() - self.pumping_start_time) >= self.pumpin_time:
                self.pump_active_time_counter += (datetime.now() - self.pumping_start_time) # добавляем время работы насоса в счетскик

                self.hau_handler.control_pump(tank_num, 0)
                print("INFO: ", datetime.now(), " насос {} выключен".format(tank_num))

                self.pumping_active = False
                self.pumping_pause_start_time = datetime.now()
                print("INFO: ", datetime.now(), "подача дозы закончена, начата пауза")
                print("INFO: ", datetime.now(), "сумарное время работы насоса за текущий цикл увлажнения: ", self.pump_active_time_counter)
        # если цикл прокачки активен и насос в сумме наработал больше, чем должен, то завершаем прокачку и начинаем спать
        elif self.humidify_active and self.pump_active_time_counter >= self.humidify_active_time:
            self.hau_handler.control_valve(valve_num, 0)
            print("INFO: ", datetime.now(), " клапан {} закрыт".format(valve_num))

            print("INFO: ", datetime.now(), "Увлажнение закончено, начат сон ", self.humidify_active_time, " секунд")
            self.humidify_active = False
            self.humidify_sleeping = True
            self.humidify_sleeping_start_time = datetime.now()
            self.pump_active_time_counter = timedelta(seconds=0)

        # если мы спим и спим дольше положенного времени, то отключаем режим сна
        # время сна равно времени сумарной работы насоса?
        elif self.humidify_sleeping and (datetime.now() - self.humidify_sleeping_start_time) > self.humidify_active_time:
            print("INFO: ", datetime.now(), "сон окончен")
            self.humidify_sleeping = False


if __name__ == "__main__":
    network = config.network

    n1 = HAUNode(network[0]['address'], list_of_nodes=network)
    n1.start()
    n1.join()
