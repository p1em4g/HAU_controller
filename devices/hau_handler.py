import time

from plexus.nodes.command import Command
from plexus.devices.base_device import BaseDevice
from plexus.nodes.message import Message

import serial

from database_handler import MySQLdbHandler
from hau_answers_parser import HAUAnswersParser
import config


class HAUHandler(BaseDevice):
    def __init__(self, name):
        super().__init__(name)
        self._description = "this is device to control humidification and aeration unit"

        dev = "/dev/serial/by-id/usb-1a86_USB2.0-Serial-if00-port0"
        baud = 9600
        timeout = 1
        self.ser = serial.Serial(port=dev, baudrate=baud, timeout=timeout)
        time.sleep(2)

        # команда для управления насосами
        pump_mode = Command(
            name="pump_mode",
            annotation="pump_number: 1 to 6, state: 0 or 1",
            input_kwargs={"pump_number": "int", "state": "int"},              # state 0 or 1
            output_kwargs={"answer": "str"},
            action=self.control_pump
        )
        self.add_command(pump_mode)

        # команда для управления клапанами
        valve_mode = Command(
            name="valve_mode",
            annotation="valve_number: 1 to 6, state: 0 or 1",
            input_kwargs={"valve_number": "int", "state": "int"},  # state 0 or 1
            output_kwargs={"answer": "str"},
            action=self.control_valve
        )
        self.add_command(valve_mode)

        # переменные, которые хранят состояние светодиодов
        self.red_led_state = "00"
        self.white_led_state = "00"

        # команда для управления красными светодиодами
        red_led_mode = Command(
            name="red_led_mode",
            annotation="board_number: 8C or 8E, led_state: 00 to FF",
            # board_number # 8C or 8E,  led_state 00 - FF
            input_kwargs={"board_number": "str", "red_led_state": "str"},
            output_kwargs={"answer": "str"},
            action=self.control_red_led
        )
        self.add_command(red_led_mode)

        # команда для управления белыми светодиодами
        white_led_mode = Command(
            name="white_led_mode",
            annotation="board_number: 8C or 8E, led_state: 00 to FF",
            # board_number # 8C or 8E,  led_state 00 - FF
            input_kwargs={"board_number": "str", "white_led_state": "str"},
            output_kwargs={"answer": "str"},
            action=self.control_white_led
        )
        self.add_command(white_led_mode)

        # команда для управления вентилятором
        fan_mode = Command(
            name="fan_mode",
            annotation="board_number: 8C or 8E, state: 00 to FF",
            # board_number 8C or 8E, state 00 - FF
            input_kwargs={"board_number": "str", "state": "str"},
            output_kwargs={"answer": "str"},
            action=self.control_fan
        )
        self.add_command(fan_mode)

        # команда для чтения данных с датчиков температур на платах освещения
        read_led_temp = Command(
            name="read_led_temp",
            annotation="board_number: 8C or 8E, sensor_number: 0 or 1",
            # board_number 8C or 8E, sensor_number 1 или 0
            input_kwargs={"board_number": "str", "sensor_number": "int"},
            output_kwargs={"answer": "str"},
            action=self.get_led_temp
        )
        self.add_command(read_led_temp)

        # команда для чтения данных с датчиков давления
        get_pressure = Command(
            name="get_pressure",
            annotation="sensor_number: 1 to 4",
            input_kwargs={"sensor_number": "int"},
            output_kwargs={"answer": "str"},
            action=self.get_pressure
        )
        self.add_command(get_pressure)

        # команда для чтения данных с кондуктометра
        get_conductivity = Command(
            name="get_conductivity",
            annotation="get_conductivity",
            output_kwargs={"answer": "str"},
            action=self.get_conductivity
        )
        self.add_command(get_conductivity)

        # команда для записи конфигурационных параметров для платы кондуктомтера (хз что это значит)
        write_conductometer_params = Command(
            name="write_conductometer_params",
            annotation="hz chto eto, udachi",
            action=self.conductometer_params_writer,
            input_kwargs={"arg": "int"},
            output_kwargs={"answer": "str"},
        )
        self.add_command(write_conductometer_params)

        # cоздаем таблицы в базе для каждого сенсора
        self.db_handler = MySQLdbHandler(config.db_params)

        # this creates (7 - 1) pump tables in loop
        for num in range(1, 8):
            self.db_handler.create_data_table(sensor_name="pump{}".format(num))

        # this creates (7 - 1) valve tables in loop
        for num in range(1, 7):
            self.db_handler.create_data_table(sensor_name="valve{}".format(num))

        self.db_handler.create_data_table(sensor_name="red_led_8C")
        self.db_handler.create_data_table(sensor_name="white_led_8C")

        self.db_handler.create_data_table(sensor_name="red_led_8E")
        self.db_handler.create_data_table(sensor_name="white_led_8E")

        self.db_handler.create_data_table(sensor_name="fan_8C")

        self.db_handler.create_data_table(sensor_name="fan_8E")

        self.db_handler.create_data_table(sensor_name="temp1_8C")
        self.db_handler.create_data_table(sensor_name="temp2_8C")

        self.db_handler.create_data_table(sensor_name="temp1_8E")
        self.db_handler.create_data_table(sensor_name="temp2_8E")

        for num in range(1, 5):
            self.db_handler.create_data_table(sensor_name="pressure{}".format(num))

        self.db_handler.create_data_table(sensor_name="conductivity")

    # метод класса для отправки команд в последовательный порт (надо вынести в другой файл)
    @classmethod
    def send_command(cls, com: str, serial_dev):
        serial_dev.flushInput()
        serial_dev.flushOutput()
        serial_dev.write(com.encode("utf-8"))
        echo = None
        if serial_dev.readable():
            echo = serial_dev.read(100)
        return echo,  # ans

    # метод для отправки команд насосам
    def control_pump(self, pump_number, state, ):
        try:
            command = "p{0}{1}\n".format(pump_number, state)
            answer = str(HAUHandler.send_command(com=command, serial_dev=self.ser))

            self._status = "works\n{}".format(answer)

            self.db_handler.add_data_in_table("pump{}".format(pump_number),
                                              int(HAUAnswersParser.pump_answer_parser(answer)))

            return answer
        except Exception as e:
            self._status = "error\n{}".format(e)
            return e

    # метод для отправки команд клапанам
    def control_valve(self, valve_number, state, ):
        try:
            command = "v{0}{1}\n".format(valve_number, state)
            answer = str(HAUHandler.send_command(com=command, serial_dev=self.ser))

            self._status = "works\n{}".format(answer)

            self.db_handler.add_data_in_table("valve{}".format(valve_number),
                                              int(HAUAnswersParser.valve_answer_parser(answer)))

            return answer
        except Exception as e:
            self._status = "error\n{}".format(e)
            return e

    # метод для отправки команд белым cветодиодам
    # table name - white_led_{board_number}
    def control_white_led(self, board_number : str, white_led_state : str):
        try:
            self.white_led_state = white_led_state
            command = "o{0}80{1}{2}\n".format(board_number, self.red_led_state, self.white_led_state)
            answer = HAUHandler.send_command(com=command, serial_dev=self.ser)

            self._status = "works\n{}".format(answer)

            # проверка на то, что в ответе есть кусок ожидаемой нами строки,
            # строка ответа одинаковая для всех команд на светодиоды
            if "cmd: 0x80" in str(answer):
                self.db_handler.add_data_in_table("white_led_{}".format(board_number), int(self.white_led_state, 16))

            return answer
        except Exception as e:
            self._status = "error\n{}".format(e)
            return e


    # метод для отправки команд красным cветодиодам
    def control_red_led(self, board_number : str, red_led_state : str):
        try:
            self.red_led_state = red_led_state
            command = "o{0}80{1}{2}\n".format(board_number, self.red_led_state, self.white_led_state)
            answer = HAUHandler.send_command(com=command, serial_dev=self.ser)

            self._status = "works\n{}".format(answer)

            # проверка на то, что в ответе есть кусок ожидаемой нами строки,
            # строка ответа одинаковая для всех команд на светодиоды
            if "cmd: 0x80" in str(answer):
                self.db_handler.add_data_in_table("red_led_{}".format(board_number), int(self.red_led_state, 16))

            return answer
        except Exception as e:
            self._status = "error\n{}".format(e)
            return e

    # метод для отправки команд вентилятору
    def control_fan(self, board_number : str, state : str):
        try:
            command = "o{0}4000{1}\n".format(board_number, state)
            answer = HAUHandler.send_command(com=command, serial_dev=self.ser)

            self._status = "works\n{}".format(answer)

            if "cmd: 0x40" in str(answer):
                self.db_handler.add_data_in_table("fan_{}".format(board_number), int(state, 16))

            return answer
        except Exception as e:
            self._status = "error\n{}".format(e)
            return e

    # метод для чтения данных с датчиков температур на платах освещения
    def get_led_temp(self, board_number, sensor_number):
        try:
            command = "o{0}20000{1}\n".format(board_number, sensor_number)
            answer = HAUHandler.send_command(com=command, serial_dev=self.ser)

            self._status = "works\n{}".format(answer)
            return answer

        except Exception as e:
            self._status = "error\n{}".format(e)
            return e

    # метод для чтения данных с датчиков давления
    def get_pressure(self, sensor_number):
        try:
            command = "s{}\n".format(sensor_number)
            answer = HAUHandler.send_command(com=command, serial_dev=self.ser)
            self._status = "works\n{}".format(answer)

            parsed_answer = HAUAnswersParser.pressure_and_conductivity_answer_parser(str(answer))
            if parsed_answer:
                self.db_handler.add_data_in_table("pressure{}".format(sensor_number), parsed_answer)

            return answer

        except Exception as e:
            self._status = "error\n{}".format(e)
            return e

    # метод для чтения данных с кондуктометра
    def get_conductivity(self):
        try:
            command = "r\n"
            answer = HAUHandler.send_command(com=command, serial_dev=self.ser)
            self._status = "works\n{}".format(answer)

            parsed_answer = HAUAnswersParser.pressure_and_conductivity_answer_parser(str(answer))
            if parsed_answer != None:
                self.db_handler.add_data_in_table("conductivity", parsed_answer)

            return answer

        except Exception as e:
            self._status = "error\n{}".format(e)
            return e

    # метод для записи конфигурационных параметров для платы кондуктомтера (хз что это значит)
    def conductometer_params_writer(self, arg):
        try:
            command = "w{}\n".format(arg)
            answer = HAUHandler.send_command(com=command, serial_dev=self.ser)

            self._status = "works\n{}".format(answer)
            return answer
        except Exception as e:
            self._status = "error\n{}".format(e)
            return e
