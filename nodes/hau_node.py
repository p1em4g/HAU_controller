import sys
sys.path.append('..')

from plexus.nodes.node import BaseNode, PeriodicCallback

from devices.hau_handler import HAUHandler

from database_handler import MySQLdbHandler

import config
import  time as time_for_sleep
from datetime import datetime, date, timedelta, time

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

        # зададим начальное положение клапанов
        self.hau_handler.control_valve(1, 0)
        self.hau_handler.control_valve(2, 0)
        self.hau_handler.control_valve(3, 1)
        self.hau_handler.control_valve(4, 0)
        self.hau_handler.control_valve(5, 0)
        self.hau_handler.control_valve(6, 0)
        print("INFO: ", datetime.now(),
              " Заданы начальные состояния клапанов. Клапан 3 открыт, 1,2,4-6 закрыты.")

        # переменные для цикла прокачки КМ от пузырей
        self.bubble_expulsion_time1 = time(hour=5, minute=0, second=0) # время прокачки 1
        self.bubble_expulsion_time2 = time(hour=17, minute=0, second=0) # время прокачки 2
        self.expel_bubbles_flag = False
        self.first_pumping_completed = False
        self.second_pumping_completed = False
        self.expulsion_of_bubbles_pumping_time = timedelta(seconds=5)
        self.start_time = datetime.now()

        # переменные для миксера
        self.tank_low_volume = 40  # ml
        self.tank_high_volume = 190  # ml
        self.low_conductivity = 1.2  # mSm/cm временно понизим нижний порог
        self.high_conductivity = 2.5  # mSm/cm
        self.filling_time = timedelta(seconds=148)
        self.mixing_time = timedelta(seconds=461)

        self.tank_1_empty = False
        self.tank_2_empty = False
        self.mixer_status = "waiting"
        # might be  "waiting", "mixing", "filling", "tank_is_empty"
        self.mix_timer = datetime.now()  # timer for counting time in mixing periods

        # переменные для РВ
        self.active_tank_number = 1  # РВ A1 - это 1, РВ А5 - это 2

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
        self.mixer()
        # если какой то цикл активен, то продолжаем крутить именно его
        if self.humidify_active_1:
            self.humidify_root_module_1()
        elif self.humidify_active_2:
            self.humidify_root_module_2()
        elif self.expel_bubbles_flag:
            self.expel_bubbles()

        if not (self.expel_bubbles_flag or self.humidify_active_1 or self.humidify_active_2):
            self.humidify_root_module_1()

        if not (self.expel_bubbles_flag or self.humidify_active_1 or self.humidify_active_2):
            self.humidify_root_module_2()

        if not (self.expel_bubbles_flag or self.humidify_active_1 or self.humidify_active_2):
            self.expel_bubbles()

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
                print("INFO: ", datetime.now(), " РВ1 опустошен. Кол-во воды: {}".format(tank_1_state))
                self.tank_1_empty = True
                self.mixer_status = "tank_is_empty"
                print("INFO: ", datetime.now(), " Активный РВ: 2")
                self.active_tank_number = 2
                print("INFO: ", datetime.now(), " mixer_status: tank_is_empty.")
                return
            else:
                if tank_1_state >= self.tank_high_volume:
                    print("INFO: ", datetime.now(), " РВ1 заполнен. Кол-во воды: {}".format(tank_1_state))
                    self.tank_1_empty = False
                    return

            voltage = self.hau_handler.get_pressure(1)
            tank_2_state = 175.4 * voltage - 396.5  # unstable data from calibration experiment
            if tank_2_state <= self.tank_low_volume:
                print("INFO: ", datetime.now(), " РВ2 опустошен. Кол-во воды: {}".format(tank_2_state))
                self.tank_2_empty = True
                self.mixer_status = "tank_is_empty"
                print("INFO: ", datetime.now(), " Активный РВ: 1")
                self.active_tank_number = 1
                print("INFO: ", datetime.now(), " mixer_status: tank_is_empty.")
                return
            else:
                if tank_2_state >= self.tank_high_volume:
                    print("INFO: ", datetime.now(), " РВ2 заполнен. Кол-во воды: {}".format(tank_1_state))
                    self.tank_2_empty = False
                    return

        # check "tank_is_empty" flag
        if self.mixer_status == "tank_is_empty":
            # check E in camera
            e_volts = self.hau_handler.get_conductivity()
            e = 0.405/(0.0681*e_volts*e_volts - 0.813*e_volts + 2.2)  # unstable data from calibration experiment
            if e <= self.low_conductivity:
                print("INFO: ", datetime.now(), " В камере смешения низкая электропроводность: {}".format(e))
                # it means that we need to add doze of concentrated nutrient solution
                # firstly run N3 for 1 second - to add small dose of concentrated solution
                self.hau_handler.control_pump(3, 1)
                print("INFO: ", datetime.now(), " Насос 3 включен")
                # wait 1 second
                time_for_sleep.sleep(2)
                # stop N3
                self.hau_handler.control_pump(3, 0)
                print("INFO: ", datetime.now(), " Насос 3 выключен")
                # then start mixing
                print("INFO: ", datetime.now(), " Hачато перемешивание")
                self.hau_handler.control_pump(4, 1)
                print("INFO: ", datetime.now(), " Насос 4 вкключен")
                self.mix_timer = datetime.now()
                self.mixer_status = "mixing"
                print("INFO: ", datetime.now(), " mixer_status: mixing")
                # then wait in background
                return
            else:
                print("INFO: ", datetime.now(), " Электропроводность в камере смешения выше минимума: {}".format(e))
                # solution is ready
                # lets fill the tank
                if self.tank_1_empty:
                    print("INFO: ", datetime.now(), " Начинаем закачку воды в РВ1")
                    # open valve 1
                    self.hau_handler.control_valve(1, 1)
                    print("INFO: ", datetime.now(), " клапан 1 открыт")
                    # start N5
                    self.hau_handler.control_pump(5, 1)
                    print("INFO: ", datetime.now(), " насос 5 включен")
                    self.mix_timer = datetime.now()
                    self.mixer_status = "filling"
                    return

                if self.tank_2_empty:
                    print("INFO: ", datetime.now(), " Начинаем закачку воды в РВ2")
                    # open valve 2
                    self.hau_handler.control_valve(2, 1)
                    print("INFO: ", datetime.now(), " клапан 2 открыт")
                    # start N5
                    self.hau_handler.control_pump(5, 1)
                    print("INFO: ", datetime.now(), " насос 5 включен")
                    self.mix_timer = datetime.now()
                    self.mixer_status = "filling"
                    print("INFO: ", datetime.now(), " mixer_status: filling")
                    return

        # check "filling" flag
        if self.mixer_status == "filling":
            # check timer
            voltage = self.hau_handler.get_pressure(2)  # датчики давлений в РВ перепутаны
            tank_1_state = 175.4 * voltage - 396.5  # unstable data from calibration experiment
            voltage = self.hau_handler.get_pressure(1)  # датчики давлений в РВ перепутаны
            tank_2_state = 175.4 * voltage - 396.5  # unstable data from calibration experiment
            if (datetime.now() - self.mix_timer >= self.filling_time) or (tank_1_state > self.tank_high_volume) \
                    or (tank_2_state > self.tank_high_volume):
                print("INFO: ", datetime.now(), " Закачка в РВ окончена")
                # then time is come
                # stop filling
                self.hau_handler.control_pump(5, 0)
                print("INFO: ", datetime.now(), " насос 5 выключен")
                # close correct valve
                if self.tank_1_empty:
                    self.hau_handler.control_valve(1, 0)
                    print("INFO: ", datetime.now(), " клапан 1 закрыт")

                if self.tank_2_empty:
                    self.hau_handler.control_valve(2, 0)
                    print("INFO: ", datetime.now(), " клапан 2 закрыт")

                self.mixer_status = "waiting"
                print("INFO: ", datetime.now(), " mixer_status: waiting")

        # check "mixing" flag
        if self.mixer_status == "mixing":
            # check timer
            if datetime.now() - self.mix_timer >= self.mixing_time:
                print("INFO: ", datetime.now(), " Время перемешивания вышло. Перемешивание окончено")
                # then time is come
                # stop mixing
                self.hau_handler.control_pump(4, 0)
                print("INFO: ", datetime.now(), " насос 4 выключен")
                self.mixer_status = "tank_is_empty"
                print("INFO: ", datetime.now(), " mixer_status: tank_is_empty")
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
    def humidify_root_module_1(self):
        pressure_sensor_num = 3
        valve_num = 6
        if self.active_tank_number == 1:
            pump_num = 2
        else: # тогда self.active_tank_number == 2, иначе быть не может
            pump_num = 1

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

                self.hau_handler.control_pump(pump_num, 1)
                print("INFO: ", datetime.now(), " насос {} включен".format(pump_num))

                self.pumping_active = True
                self.pumping_start_time = datetime.now()
            # если насос включен и время работы насоса больше, чем должно быть, выключаем насос
            elif self.pumping_active and (datetime.now() - self.pumping_start_time) >= self.pumpin_time:
                self.pump_active_time_counter += (datetime.now() - self.pumping_start_time) # добавляем время работы насоса в счетскик

                self.hau_handler.control_pump(pump_num, 0)
                print("INFO: ", datetime.now(), " насос {} выключен".format(pump_num))

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
        pressure_sensor_num = 4
        valve_num = 5
        if self.active_tank_number == 1:
            pump_num = 2
        else: # тогда self.active_tank_number == 2, иначе быть не может
            pump_num = 1

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

                self.hau_handler.control_pump(pump_num, 1)
                print("INFO: ", datetime.now(), " насос {} включен".format(pump_num))

                self.pumping_active = True
                self.pumping_start_time = datetime.now()
            # если насос включен и время работы насоса больше, чем должно быть, выключаем насос
            elif self.pumping_active and (datetime.now() - self.pumping_start_time) >= self.pumpin_time:
                self.pump_active_time_counter += (datetime.now() - self.pumping_start_time) # добавляем время работы насоса в счетскик

                self.hau_handler.control_pump(pump_num, 0)
                print("INFO: ", datetime.now(), " насос {} выключен".format(pump_num))

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
