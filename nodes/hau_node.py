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

        self.exp_note = "24.11.2022: Первая планка посажена 23.11.2022. Вторая 28.11.2022"
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

        # переменные для цикла прокачки КМ от пузырей
        self.bubble_expulsion_time1 = time(hour=5, minute=0, second=0) # время прокачки 1
        self.bubble_expulsion_time2 = time(hour=17, minute=0, second=0)  # время прокачки 2
        self.expel_bubbles_flag = False
        self.first_pumping_completed = True
        self.second_pumping_completed = False
        self.expulsion_of_bubbles_pumping_time = timedelta(seconds=600)  # время прокачки от пузырей 10 мин?
        self.start_time = datetime.now()

        self.db_handler.add_log_in_table("info_logs", "hau_node",
                                    ("INIT: Время первой прокачик КМ от пузырей {}, "
                                    "Время второй прокачки КМ от пузырей {}, "
                                    "Время прокачки {} ").format(self.bubble_expulsion_time1,
                                                                self.bubble_expulsion_time2,
                                                                self.expulsion_of_bubbles_pumping_time))

        # переменные для миксера
        self.tank_low_volume = 40  # ml
        self.tank_high_volume = 150  # ml

        self.tank_2_low_voltage = 2.40  # только для РВ2, т.к. он плохо отклаиброван
        self.tank_2_high_voltage = 2.70  # только для РВ2, т.к. он плохо отклаиброван

        self.low_conductivity = 1.2  # mSm/cm
        self.high_conductivity = 1.4  # mSm/cm # не участвует в коде
        self.filling_time = timedelta(seconds=148)
        self.mixing_time = timedelta(seconds=461)

        self.tank_1_empty = False
        self.tank_2_empty = False
        self.mixer_status = "waiting"
        # might be  "waiting", "mixing", "filling", "tank_is_empty"
        self.mix_timer = datetime.now()  # timer for counting time in mixing periods

        self.db_handler.add_log_in_table("info_logs", "hau_node",
                                    ("INIT: Переменные в миксере: tank_low_volume = {}, tank_high_volume = {}, "
                                    "tank_2_low_voltage = {},  tank_2_high_voltage = {}, low_conductivity = {}, "
                                    "high_conductivity = {}, filling_time = {}, mixing_time = {}").format(
                                        self.tank_low_volume, self.tank_high_volume, self.tank_2_low_voltage,
                                        self.tank_2_high_voltage, self.low_conductivity, self.high_conductivity,
                                        self.filling_time,self.mixing_time
                                    ))

        # переменные для РВ
        self.active_tank_number = 1  # РВ A1 - это 1, РВ А5 - это 2

        # переменные для цикла увлажнения КМ
        self.min_critical_pressure_in_root_module_1 = 4.37  # 3,68 В соответсвует -0,75 кПа в КМ1
        self.min_critical_pressure_in_root_module_2 = 4.37  # 3,42 В соответсвует -0,75 кПа в КМ2

        self.humidify_active_1 = False  # показывает, активен ли сейчас цикл прокачки
        self.humidify_active_2 = False

        self.pumpin_pause_time = timedelta(seconds=9)       # время паузы между дозами
        self.pumpin_time = timedelta(seconds=6)  # время закачки дозы

        self.pumping_active = False  # показыывет, включен ли насос
        self.pumping_start_time = None  # показывает время послежнего запуска насоса
        self.pumping_pause_start_time = None  # показывает время начала послежней паузы
        self.pumping_pause_active = False  # показывает активна ли пауза (возможно, лишняя переменная)

        self.pump_active_time_counter = timedelta(seconds=0)  # показывает сумарное время работы насоса
        self.humidify_active_time = timedelta(seconds=149)  # 297 c - 80 ml, 149 с - 40 мл показывает, сколько времени в сумме должен проработать насос

        self.db_handler.add_log_in_table("info_logs", "hau_node",
                                    (
                                        "INIT: min_critical_pressure_in_root_module = {}, pumpin_pause_time = {}, "
                                     "pumpin_time = {}, pump_active_time_counter = {}, humidify_active_time = {}"
                                     ).format(self.min_critical_pressure_in_root_module_1, self.pumpin_pause_time,
                                              self.pumpin_time, self.pump_active_time_counter,
                                              self.humidify_active_time))

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
                self.db_handler.add_log_in_table("info_logs", "hau_node",
                                            "MIXER: РВ1 опустошен. Кол-во воды: {}".format(tank_1_state))
                print("INFO: ", datetime.now(), " РВ1 опустошен. Кол-во воды: {}".format(tank_1_state))

                self.tank_1_empty = True
                self.mixer_status = "tank_is_empty"

                self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER:  Активный РВ: 2")
                print("INFO: ", datetime.now(), " Активный РВ: 2")

                self.active_tank_number = 2

                self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER:  mixer_status: tank_is_empty.")
                print("INFO: ", datetime.now(), " mixer_status: tank_is_empty.")
                return
            else:
                if tank_1_state >= self.tank_high_volume:
                    self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: РВ1 заполнен. Кол-во воды: {}".format(tank_1_state))
                    print("INFO: ", datetime.now(), " РВ1 заполнен. Кол-во воды: {}".format(tank_1_state))

                    self.tank_1_empty = False
                    return

            voltage = self.hau_handler.get_pressure(1)
            tank_2_state = 175.4 * voltage - 396.5  # unstable data from calibration experiment
            if voltage <= self.tank_2_low_voltage: # РВ2 плохо отклаиброван, поэтому сравнимать будет с напряжением
                self.db_handler.add_log_in_table("info_logs", "hau_node",
                                                 "MIXER: РВ2 опустошен. Кол-во воды: {} В".format(voltage))
                print("INFO: ", datetime.now(), " РВ2 опустошен. Кол-во воды: {} В".format(voltage))

                self.tank_2_empty = True
                self.mixer_status = "tank_is_empty"

                self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER:  Активный РВ: 1")
                print("INFO: ", datetime.now(), " Активный РВ: 1")

                self.active_tank_number = 1

                self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER:  mixer_status: tank_is_empty.")
                print("INFO: ", datetime.now(), " mixer_status: tank_is_empty.")
                return
            else:
                if voltage >= self.tank_2_high_voltage:
                    self.db_handler.add_log_in_table(
                        "info_logs", "hau_node", "MIXER: РВ2 заполнен. Показания датчика: {} В".format(voltage))
                    print("INFO: ", datetime.now(), " РВ2 заполнен. Показания датчика: {} В".format(voltage))

                    self.tank_2_empty = False
                    return

        # check "tank_is_empty" flag
        if self.mixer_status == "tank_is_empty":
            # check E in camera
            e_volts = self.hau_handler.get_conductivity()
            e = 0.405/(0.0681*e_volts*e_volts - 0.813*e_volts + 2.2)  # unstable data from calibration experiment
            if e <= self.low_conductivity:
                self.db_handler.add_log_in_table(
                    "info_logs", "hau_node", "MIXER:  В камере смешения низкая электропроводность: {}".format(e))
                print("INFO: ", datetime.now(), " В камере смешения низкая электропроводность: {}".format(e))
                # it means that we need to add doze of concentrated nutrient solution
                # firstly run N3 for 1 second - to add small dose of concentrated solution
                self.hau_handler.control_pump(3, 1)

                self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: Насос 3 включен")
                print("INFO: ", datetime.now(), " Насос 3 включен")
                # wait 1 second
                time_for_sleep.sleep(2)
                # stop N3
                self.hau_handler.control_pump(3, 0)

                self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: Насос 3 выключен")
                print("INFO: ", datetime.now(), " Насос 3 выключен")
                # then start mixing
                self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: Hачато перемешивание")
                print("INFO: ", datetime.now(), " Hачато перемешивание")

                self.hau_handler.control_pump(4, 1)

                print("INFO: ", datetime.now(), " Насос 4 включен")
                self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: Насос 4 включен")

                self.mix_timer = datetime.now()
                self.mixer_status = "mixing"

                self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: mixer_status: mixing")
                print("INFO: ", datetime.now(), " mixer_status: mixing")
                # then wait in background
                return
            else:
                self.db_handler.add_log_in_table(
                    "info_logs", "hau_node", "MIXER:  Электропроводность в камере смешения выше минимума: {}".format(e))
                print("INFO: ", datetime.now(), " Электропроводность в камере смешения выше минимума: {}".format(e))
                # solution is ready
                # lets fill the tank
                if self.tank_1_empty:
                    self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: Начинаем закачку воды в РВ1")
                    print("INFO: ", datetime.now(), " Начинаем закачку воды в РВ1")
                    # open valve 1
                    self.hau_handler.control_valve(1, 1)
                    self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER:  клапан 1 открыт")
                    print("INFO: ", datetime.now(), " клапан 1 открыт")
                    # start N5
                    self.hau_handler.control_pump(5, 1)
                    self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: насос 5 включен")
                    print("INFO: ", datetime.now(), " насос 5 включен")
                    self.mix_timer = datetime.now()
                    self.mixer_status = "filling"
                    self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: mixer_status: filling")
                    print("INFO: ", datetime.now(), " mixer_status: filling")
                    return

                if self.tank_2_empty:
                    self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: Начинаем закачку воды в РВ2")
                    print("INFO: ", datetime.now(), " Начинаем закачку воды в РВ2")
                    # open valve 2
                    self.hau_handler.control_valve(2, 1)
                    self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER:  клапан 2 открыт")
                    print("INFO: ", datetime.now(), " клапан 2 открыт")
                    # start N5
                    self.hau_handler.control_pump(5, 1)
                    self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: насос 5 включен")
                    print("INFO: ", datetime.now(), " насос 5 включен")
                    self.mix_timer = datetime.now()
                    self.mixer_status = "filling"
                    self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: mixer_status: filling")
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
                    or (voltage > self.tank_2_high_voltage):
                self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: Закачка в РВ окончена")
                print("INFO: ", datetime.now(), " Закачка в РВ окончена")
                # then time is come
                # stop filling
                self.hau_handler.control_pump(5, 0)
                self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: насос 5 выключен")
                print("INFO: ", datetime.now(), " насос 5 выключен")
                # close correct valve
                if self.tank_1_empty:
                    self.hau_handler.control_valve(1, 0)
                    self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: клапан 1 закрыт")
                    print("INFO: ", datetime.now(), " клапан 1 закрыт")

                if self.tank_2_empty:
                    self.hau_handler.control_valve(2, 0)
                    self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: клапан 2 закрыт")
                    print("INFO: ", datetime.now(), " клапан 2 закрыт")

                self.mixer_status = "waiting"
                self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: mixer_status: waiting")
                print("INFO: ", datetime.now(), " mixer_status: waiting")

        # check "mixing" flag
        if self.mixer_status == "mixing":
            # check timer
            if datetime.now() - self.mix_timer >= self.mixing_time:
                self.db_handler.add_log_in_table(
                    "info_logs", "hau_node", "MIXER: Время перемешивания вышло. Перемешивание окончено")
                print("INFO: ", datetime.now(), " Время перемешивания вышло. Перемешивание окончено")
                # then time is come
                # stop mixing
                self.hau_handler.control_pump(4, 0)
                self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: насос 4 выключен")
                print("INFO: ", datetime.now(), " насос 4 выключен")
                self.mixer_status = "tank_is_empty"
                self.db_handler.add_log_in_table("info_logs", "hau_node", "MIXER: tank_is_empty")
                print("INFO: ", datetime.now(), " mixer_status: tank_is_empty")
    def expel_bubbles(self):
        if (((datetime.now().time() > self.bubble_expulsion_time1) and (self.first_pumping_completed == False))
            or ((datetime.now().time() > self.bubble_expulsion_time2) and (self.second_pumping_completed == False))) \
                and (self.expel_bubbles_flag == False):
            self.db_handler.add_log_in_table("info_logs", "hau_node", "EXPEL_BUBBLES: начинаем прокачку КМ от пузырей")
            print("INFO: ", datetime.now(), "начинаем прокачку КМ от пузырей")

            self.hau_handler.control_valve(5, 0)
            self.db_handler.add_log_in_table("info_logs", "hau_node", "EXPEL_BUBBLES: клапан 5 закрыт")
            print("INFO: ", datetime.now(), " клапан 5 закрыт")
            self.hau_handler.control_valve(6, 0) # закрываем клапаны
            self.db_handler.add_log_in_table("info_logs", "hau_node", "EXPEL_BUBBLES: клапан 6 закрыт")
            print("INFO: ", datetime.now(), " клапан 6 закрыт")
            self.hau_handler.control_pump(6, 1)
            self.db_handler.add_log_in_table("info_logs", "hau_node", "EXPEL_BUBBLES: насос 6 включен")
            print("INFO: ", datetime.now(), " насос 6 включен")
            self.hau_handler.control_pump(7, 1)
            self.db_handler.add_log_in_table("info_logs", "hau_node", "EXPEL_BUBBLES: насос 7 включен")
            print("INFO: ", datetime.now(), " насос 7 включен")
            self.expel_bubbles_flag = True
        elif (self.expel_bubbles_flag == True) \
                and (datetime.now() - datetime.combine(date.today(), self.bubble_expulsion_time1)) > self.expulsion_of_bubbles_pumping_time:
            self.expel_bubbles_flag = False
            self.hau_handler.control_pump(6, 0)
            self.db_handler.add_log_in_table("info_logs", "hau_node", "EXPEL_BUBBLES: насос 6 выключен")
            print("INFO: ", datetime.now(), " насос 6 выключен")
            self.hau_handler.control_pump(7, 0)
            self.db_handler.add_log_in_table("info_logs", "hau_node", "EXPEL_BUBBLES: насос 7 выключен")
            print("INFO: ", datetime.now(), " насос 7 выключен")

            if self.first_pumping_completed == False:
                self.first_pumping_completed = True
                self.db_handler.add_log_in_table("info_logs", "hau_node",
                                                 "EXPEL_BUBBLES: Первая прокачка КМ от пузырей выполнена")
                print("INFO: ", datetime.now(), " Первая прокачка КМ от пузырей выполнена")
            else:
                self.second_pumping_completed = True
                self.db_handler.add_log_in_table("info_logs", "hau_node",
                                                 "EXPEL_BUBBLES: Вторая прокачка КМ от пузырей выполнена")
                print("INFO: ", datetime.now()," Вторая прокачка КМ от пузырей выполнена")


        # обновление флагов для прокачек
        if self.first_pumping_completed and self.second_pumping_completed \
                and datetime.now().time() > time(hour=0, minute=0, second=0) \
                and datetime.now().time() < self.bubble_expulsion_time1:
            self.first_pumping_completed = False
            self.second_pumping_completed = False
            self.db_handler.add_log_in_table("info_logs", "hau_node", "EXPEL_BUBBLES: Флаги для прокачек КМ сброшены")
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
        if (not self.humidify_active_1) and pressure < self.min_critical_pressure_in_root_module_1 and (not self.humidify_sleeping):
            self.db_handler.add_log_in_table(
                "info_logs", "hau_node", "HUMIDIFY: Начат цикл увлажнения КМ c клапаном {}".format(valve_num))
            print("INFO: ", datetime.now(), "Начат цикл увлажнения КМ c клапаном {}".format(valve_num))
            self.db_handler.add_log_in_table(
                "info_logs", "hau_node", "HUMIDIFY: Давление в трубке: {}".format(pressure))
            print("INFO: ", datetime.now(), "Давление в трубке: {}".format(pressure))
            self.humidify_active_1 = True
            self.hau_handler.control_valve(valve_num, 1)
            self.db_handler.add_log_in_table(
                "info_logs", "hau_node", "HUMIDIFY: клапан {} открыт".format(valve_num))
            print("INFO: ", datetime.now(), " клапан {} открыт".format(valve_num))

            self.pumping_pause_start_time = datetime.now() - self.pumpin_pause_time  # костыль

        # если цикл пркоачки начат и насос в сумме проработал меньше чем надо то ...
        elif self.humidify_active_1 and self.pump_active_time_counter < self.humidify_active_time:
            # если насос выключен и время паузы между дозами прошло, то включаем насос и записываем время его включения
            if not self.pumping_active and (datetime.now() - self.pumping_pause_start_time) >= self.pumpin_pause_time:
                self.db_handler.add_log_in_table("info_logs", "hau_node", "HUMIDIFY: Начата подача дозы")
                print("INFO: ", datetime.now(), "Начата подача дозы")

                self.hau_handler.control_pump(pump_num, 1)
                self.db_handler.add_log_in_table("info_logs", "hau_node", "HUMIDIFY: насос {} включен".format(pump_num))
                print("INFO: ", datetime.now(), " насос {} включен".format(pump_num))

                self.pumping_active = True
                self.pumping_start_time = datetime.now()
            # если насос включен и время работы насоса больше, чем должно быть, выключаем насос
            elif self.pumping_active and (datetime.now() - self.pumping_start_time) >= self.pumpin_time:
                self.pump_active_time_counter += (datetime.now() - self.pumping_start_time) # добавляем время работы насоса в счетскик

                self.hau_handler.control_pump(pump_num, 0)
                print("INFO: ", datetime.now(), " насос {} выключен".format(pump_num))
                self.db_handler.add_log_in_table("info_logs", "hau_node", "HUMIDIFY: насос {} выключен".format(pump_num))

                self.pumping_active = False
                self.pumping_pause_start_time = datetime.now()

                self.db_handler.add_log_in_table("info_logs", "hau_node", "HUMIDIFY: подача дозы закончена, начата пауза")
                print("INFO: ", datetime.now(), "подача дозы закончена, начата пауза")
                self.db_handler.add_log_in_table(
                    "info_logs", "hau_node", "HUMIDIFY: сумарное время работы насоса"
                                             " за текущий цикл увлажнения: {}".format(self.pump_active_time_counter))
                print("INFO: ", datetime.now(), "сумарное время работы насоса "
                                                "за текущий цикл увлажнения: {}".format(self.pump_active_time_counter))
        # если цикл прокачки активен и насос в сумме наработал больше, чем должен, то завершаем прокачку и начинаем спать
        elif self.humidify_active_1 and self.pump_active_time_counter >= self.humidify_active_time:
            self.hau_handler.control_valve(valve_num, 0)
            self.db_handler.add_log_in_table("info_logs", "hau_node", "HUMIDIFY: клапан {} закрыт".format(valve_num))
            print("INFO: ", datetime.now(), " клапан {} закрыт".format(valve_num))

            self.db_handler.add_log_in_table(
                "info_logs", "hau_node",
                "HUMIDIFY: Увлажнение закончено, начат сон {} секунд".format(self.humidify_active_time))
            print("INFO: ", datetime.now(), "Увлажнение закончено, начат сон {} секунд".format(self.humidify_active_time))
            self.db_handler.add_log_in_table("info_logs", "hau_node",
                                             "HUMIDIFY: Давление в трубке: {}".format(pressure))
            print("INFO: ", datetime.now(), "Давление в трубке: {}".format(pressure))

            self.humidify_active_1 = False
            self.humidify_sleeping = True
            self.humidify_sleeping_start_time = datetime.now()
            self.pump_active_time_counter = timedelta(seconds=0)

        # если мы спим и спим дольше положенного времени, то отключаем режим сна
        # время сна равно времени сумарной работы насоса?
        elif self.humidify_sleeping and (datetime.now() - self.humidify_sleeping_start_time) > self.humidify_active_time:
            self.db_handler.add_log_in_table("info_logs", "hau_node", "HUMIDIFY: сон окончен")
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
        if (not self.humidify_active_2) and pressure < self.min_critical_pressure_in_root_module_2 and (not self.humidify_sleeping):
            self.db_handler.add_log_in_table("info_logs", "hau_node",
                                             "HUMIDIFY_2: Начат цикл увлажнения КМ c клапаном {}".format(valve_num))
            print("INFO: ", datetime.now(), "Начат цикл увлажнения КМ c клапаном {}".format(valve_num))
            self.db_handler.add_log_in_table("info_logs", "hau_node",
                                             "HUMIDIFY_2: Давление в трубке: {}".format(pressure))
            print("INFO: ", datetime.now(), "Давление в трубке: {}".format(pressure))
            self.humidify_active_2 = True
            self.hau_handler.control_valve(valve_num, 1)
            self.db_handler.add_log_in_table("info_logs", "hau_node",
                                             "HUMIDIFY_2: клапан {} открыт".format(valve_num))
            print("INFO: ", datetime.now(), " клапан {} открыт".format(valve_num))

            self.pumping_pause_start_time = datetime.now() - self.pumpin_pause_time  # костыль

        # если цикл пркоачки начат и насос в сумме проработал меньше чем надо то ...
        elif self.humidify_active_2 and self.pump_active_time_counter < self.humidify_active_time:
            # если насос выключен и время паузы между дозами прошло, то включаем насос и записываем время его включения
            if not self.pumping_active and (datetime.now() - self.pumping_pause_start_time) >= self.pumpin_pause_time:
                self.db_handler.add_log_in_table("info_logs", "hau_node", "HUMIDIFY_2: Начата подача дозы")
                print("INFO: ", datetime.now(), "Начата подача дозы")

                self.hau_handler.control_pump(pump_num, 1)
                self.db_handler.add_log_in_table("info_logs", "hau_node",
                                                 "HUMIDIFY_2: насос {} включен".format(pump_num))
                print("INFO: ", datetime.now(), " насос {} включен".format(pump_num))

                self.pumping_active = True
                self.pumping_start_time = datetime.now()
            # если насос включен и время работы насоса больше, чем должно быть, выключаем насос
            elif self.pumping_active and (datetime.now() - self.pumping_start_time) >= self.pumpin_time:
                self.pump_active_time_counter += (datetime.now() - self.pumping_start_time) # добавляем время работы насоса в счетскик

                self.hau_handler.control_pump(pump_num, 0)
                self.db_handler.add_log_in_table("info_logs", "hau_node",
                                                 "HUMIDIFY_2: насос {} выключен".format(pump_num))
                print("INFO: ", datetime.now(), " насос {} выключен".format(pump_num))

                self.pumping_active = False
                self.pumping_pause_start_time = datetime.now()
                self.db_handler.add_log_in_table("info_logs", "hau_node",
                                                 "HUMIDIFY_2: подача дозы закончена, начата пауза")
                print("INFO: ", datetime.now(), "подача дозы закончена, начата пауза")
                self.db_handler.add_log_in_table(
                    "info_logs", "hau_node", "HUMIDIFY_2: сумарное время работы насоса "
                                             "за текущий цикл увлажнения: {}".format(self.pump_active_time_counter))
                print("INFO: ", datetime.now(), "сумарное время работы насоса "
                                                "за текущий цикл увлажнения: {}".format(self.pump_active_time_counter))
        # если цикл прокачки активен и насос в сумме наработал больше, чем должен, то завершаем прокачку и начинаем спать
        elif self.humidify_active_2 and self.pump_active_time_counter >= self.humidify_active_time:
            self.hau_handler.control_valve(valve_num, 0)
            self.db_handler.add_log_in_table("info_logs", "hau_node", "HUMIDIFY_2: клапан {} закрыт".format(valve_num))
            print("INFO: ", datetime.now(), " клапан {} закрыт".format(valve_num))

            self.db_handler.add_log_in_table(
                "info_logs", "hau_node",
                "HUMIDIFY_2: Увлажнение закончено, начат сон {} секунд".format(self.humidify_active_time))
            print("INFO: ", datetime.now(),
                  "Увлажнение закончено, начат сон {} секунд".format(self.humidify_active_time))
            self.db_handler.add_log_in_table("info_logs", "hau_node",
                                             "HUMIDIFY_2: Давление в трубке: {}".format(pressure))
            print("INFO: ", datetime.now(), "Давление в трубке: {}".format(pressure))

            self.humidify_active_2 = False
            self.humidify_sleeping = True
            self.humidify_sleeping_start_time = datetime.now()
            self.pump_active_time_counter = timedelta(seconds=0)

        # если мы спим и спим дольше положенного времени, то отключаем режим сна
        # время сна равно времени сумарной работы насоса?
        elif self.humidify_sleeping and (datetime.now() - self.humidify_sleeping_start_time) > self.humidify_active_time:
            self.db_handler.add_log_in_table("info_logs", "hau_node", "HUMIDIFY_2: сон окончен")
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
