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

        # переменные для РВ
        self.active_tank_number = 1  # РВ A1 - это 1, РВ А5 - это 2
        self.min_critical_pressure_in_tank = None #!!!НАДО ВВЕСТИ АДЕКВАТНОЕ ЗНАЧЕНИЕ!!!
        self.first_tank_water_amount = 1 #!!!НАДО ВВЕСТИ АДЕКВАТНОЕ ЗНАЧЕНИЕ!!!
        self.second_tank_water_amount = 1 #!!!НАДО ВВЕСТИ АДЕКВАТНОЕ ЗНАЧЕНИЕ!!!

        # переменные для цикла увлажнения КМ
        self.min_critical_pressure_in_root_module = 3.0 # !!!НАДО ВВЕСТИ АДЕКВАТНОЕ ЗНАЧЕНИЕ!!!

        self.humidify_active_1 = False  # показывает, активен ли сейчас цикл прокачки
        self.humidify_active_2 = False

        self.pumpin_pause_time = timedelta(seconds=9)       # время паузы между дозами
        self.pumpin_time = timedelta(seconds=6) # время закачки дозы

        self.pumping_active = False # показыывет, включен ли насос
        self.pumping_start_time = None # показывает время послежнего запуска насоса
        self.pumping_pause_start_time = None # показывает время начала послежней паузы
        self.pumping_pause_active = False # показывает активна ли пауза (возможно, лишняя переменная)

        self.pump_active_time_counter = timedelta(seconds=0) # показывает сумарное время работы насоса
        self.humidify_active_time = timedelta(seconds=296) # показывает, сколько времени в сумме должен проработать насос

        # после прокачки некоторое время игнорируем показания ДД и просто спим
        self.humidify_sleeping = False
        self.humidify_sleeping_start_time = None

        #переменные для цикла перемешивания и наполнения РВ
        self.filling_active = False

    def custom_preparation(self):
        self.control_timer = PeriodicCallback(self.control, 1000)

        self.control_timer.start()

    def control(self):
        # если какой то цикл активен, то продолжаем крутить именно его
        if self.humidify_active_1:
            self.humidify_root_module_1()
        elif self.humidify_active_2:
            self.humidify_root_module_2()
        elif self.expel_bubbles_flag:
            self.expel_bubbles()


        if not (self.humidify_active_1 or self.humidify_active_2):
            self.find_empty_tank()

        if not (self.expel_bubbles_flag or self.humidify_active_1 or self.humidify_active_2):
            self.humidify_root_module_1()

        if not (self.expel_bubbles_flag or self.humidify_active_1 or self.humidify_active_2):
            self.humidify_root_module_2()

        if not self.expel_bubbles_flag and not self.humidify_active_1:
            self.expel_bubbles()

    def find_empty_tank(self):
        print("INFO: ", datetime.now(), "Ищем пустой РВ")
        tank_pressure_1 = self.hau_handler.get_pressure(2) # датчики в РВ перепутаны. В рв 1, датчик 2 и наоборот
        tank_pressure_2 = self.hau_handler.get_pressure(1) # датчики в РВ перепутаны. В рв 1, датчик 2 и наоборот
        if tank_pressure_1 <= self.min_critical_pressure_in_tank and not self.filling_active:
            print("INFO: ", datetime.now(), "Давление в РВ1 ниже критического. Давление: {}".format(tank_pressure_1))
            self.active_tank_number = 2
            print("INFO: ", datetime.now(), "Активный резервуар - РВ2")
        if tank_pressure_2 <= self.min_critical_pressure_in_tank and not self.filling_active:
            print("INFO: ", datetime.now(), "Давление в РВ2 ниже критического. Давление: {}".format(tank_pressure_2))
            self.active_tank_number = 1
            print("INFO: ", datetime.now(), "Активный резервуар - РВ1")

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


    # цикл перемешивания и наполнения РВ
    def fill_tank(self):
        pass

    # цикл увлажнения
    # если давление падает ниже некоторой границы, начинаем пркоачку из активного РВ
    # помогите
    def humidify_root_module_1(self):
        tank_num = self.active_tank_number
        pressure_sensor_num = 3
        valve_num = 6
        pressure = float(self.hau_handler.get_pressure(pressure_sensor_num))
        # если цикл пркоачки неактивен и давление ниже критического и мы не спим, то говорим что цикл прокачки начат
        if (not self.humidify_active_1) and pressure < self.min_critical_pressure_in_root_module and (not self.humidify_sleeping):
            print("INFO: ", datetime.now(), "Начат цикл увлажнения КМ c клапаном {}".format(valve_num))
            print("INFO: ", datetime.now(), "Давление в трубке: {}".format(pressure))
            self.humidify_active_1 = True
            self.hau_handler.control_valve(valve_num, 1)
            print("INFO: ", datetime.now(), " клапан {} открыт".format(valve_num))

            self.pumping_pause_start_time = datetime.now() - self.pumpin_pause_time  # костыль

        # если цикл пркоачки начат и насос в сумме проработал меньше чем надо то ...
        elif self.humidify_active_1 and self.pump_active_time_counter < self.humidify_active_time:
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
        elif self.humidify_active_1 and self.pump_active_time_counter >= self.humidify_active_time:
            self.hau_handler.control_valve(valve_num, 0)
            print("INFO: ", datetime.now(), " клапан {} закрыт".format(valve_num))

            print("INFO: ", datetime.now(), "Увлажнение закончено, начат сон ", self.humidify_active_time, " секунд")
            print("INFO: ", datetime.now(), "Давление в трубке: {}".format(pressure))

            self.humidify_active_1 = False
            self.humidify_sleeping = True
            self.humidify_sleeping_start_time = datetime.now()
            self.pump_active_time_counter = timedelta(seconds=0)

        # если мы спим и спим дольше положенного времени, то отключаем режим сна
        # время сна равно времени сумарной работы насоса?
        elif self.humidify_sleeping and (datetime.now() - self.humidify_sleeping_start_time) > self.humidify_active_time:
            print("INFO: ", datetime.now(), "сон окончен")
            self.humidify_sleeping = False

    #точно такой же метод, как и предыдущий, но для другого КМ. Это было самым быстрым решением проблемы(навреное)
    def humidify_root_module_2(self):
        tank_num = self.active_tank_number
        pressure_sensor_num = 4
        valve_num = 5
        pressure = float(self.hau_handler.get_pressure(pressure_sensor_num))
        # если цикл пркоачки неактивен и давление ниже критического и мы не спим, то говорим что цикл прокачки начат
        if (not self.humidify_active_2) and pressure < self.min_critical_pressure_in_root_module and (not self.humidify_sleeping):
            print("INFO: ", datetime.now(), "Начат цикл увлажнения КМ c клапаном {}".format(valve_num))
            print("INFO: ", datetime.now(), "Давление в трубке: {}".format(pressure))
            self.humidify_active_2 = True
            self.hau_handler.control_valve(valve_num, 1)
            print("INFO: ", datetime.now(), " клапан {} открыт".format(valve_num))

            self.pumping_pause_start_time = datetime.now() - self.pumpin_pause_time  # костыль

        # если цикл пркоачки начат и насос в сумме проработал меньше чем надо то ...
        elif self.humidify_active_2 and self.pump_active_time_counter < self.humidify_active_time:
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
        elif self.humidify_active_2 and self.pump_active_time_counter >= self.humidify_active_time:
            self.hau_handler.control_valve(valve_num, 0)
            print("INFO: ", datetime.now(), " клапан {} закрыт".format(valve_num))

            print("INFO: ", datetime.now(), "Увлажнение закончено, начат сон ", self.humidify_active_time, " секунд")
            print("INFO: ", datetime.now(), "Давление в трубке: {}".format(pressure))

            self.humidify_active_2 = False
            self.humidify_sleeping = True
            self.humidify_sleeping_start_time = datetime.now()
            self.pump_active_time_counter = timedelta(seconds=0)

        # если мы спим и спим дольше положенного времени, то отключаем режим сна
        # время сна равно времени сумарной работы насоса?
        elif self.humidify_sleeping and (datetime.now() - self.humidify_sleeping_start_time) > self.humidify_active_time:
            print("INFO: ", datetime.now(), "сон окончен")
            self.humidify_sleeping = False

    def turn_off_all_pumps(self):
        self.hau_handler.control_pump(1,0)
        self.hau_handler.control_pump(2, 0)
        self.hau_handler.control_pump(3, 0)
        self.hau_handler.control_pump(4, 0)
        self.hau_handler.control_pump(5, 0)
        self.hau_handler.control_pump(6, 0)
        self.hau_handler.control_pump(7, 0)
        print("INFO: ", datetime.now(), "Произошло отключение всех насосов")

if __name__ == "__main__":
    network = config.network

    n1 = HAUNode(network[0]['address'], list_of_nodes=network)

    try:
        n1.start()
        n1.join()
    finally:
        n1.turn_off_all_pumps()
