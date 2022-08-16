import time

from plexus.nodes.command import Command
from plexus.devices.base_device import BaseDevice
import serial

from database_handler import MySQLdbHandler
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
            action=self.pump_controller
        )
        self.add_command(pump_mode)

        # команда для управления клапанами
        valve_mode = Command(
            name="valve_mode",
            annotation="valve_number: 1 to 6, state: 0 or 1",
            input_kwargs={"valve_number": "int", "state": "int"},  # state 0 or 1
            output_kwargs={"answer": "str"},
            action=self.valve_controller
        )
        self.add_command(valve_mode)

        # команда для управления красными светодиодами
        red_led_mode = Command(
            name="red_led_mode",
            annotation="board_number: 8C or 8E, led_state: 00 to FF",
            # board_number # 8C or 8E,  led_state 00 - FF
            input_kwargs={"board_number": "str", "red_led_state": "str"},
            output_kwargs={"answer": "str"},
            action=self.red_led_controller
        )
        self.add_command(red_led_mode)

        # команда для управления белыми светодиодами
        white_led_mode = Command(
            name="white_led_mode",
            annotation="board_number: 8C or 8E, led_state: 00 to FF",
            # board_number # 8C or 8E,  led_state 00 - FF
            input_kwargs={"board_number": "str", "white_led_state": "str"},
            output_kwargs={"answer": "str"},
            action=self.white_led_controller
        )
        self.add_command(white_led_mode)

        # команда для управления вентилятором
        fan_mode = Command(
            name="fan_mode",
            annotation="board_number: 8C or 8E, state: 00 to FF",
            # board_number 8C or 8E, state 00 - FF
            input_kwargs={"board_number": "str", "state": "str"},
            output_kwargs={"answer": "str"},
            action=self.fan_controller
        )
        self.add_command(fan_mode)

        # команда для чтения данных с датчиков температур на платах освещения
        read_led_temp = Command(
            name="read_led_temp",
            annotation="board_number: 8C or 8E, sensor_number: 0 or 1",
            # board_number 8C or 8E, sensor_number 1 или 0
            input_kwargs={"board_number": "str", "sensor_number": "int"},
            output_kwargs={"answer": "str"},
            action=self.led_temp_reader
        )
        self.add_command(read_led_temp)

        # команда для чтения данных с датчиков давления
        get_pressure = Command(
            name="get_pressure",
            annotation="sensor_number: 1 to 4",
            input_kwargs={"sensor_number": "int"},
            output_kwargs={"answer": "str"},
            action=self.pressure_getter
        )
        self.add_command(get_pressure)

        # команда для чтения данных с кондуктометра
        get_conductivity = Command(
            name="get_conductivity",
            annotation="get_conductivity",
            output_kwargs={"answer": "str"},
            action=self.conductivity_getter
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

        # this creates (7 - 1) pumps in loop
        for num in range(1,7):
            self.db_handler.create_data_table(sensor_name="pump{}".format(num))

        # db_handler.create_data_table("valve")
        # db_handler.create_data_table("led")  # надо разделить на две команды
        # db_handler.create_data_table("fan")
        # db_handler.create_data_table("led_temp") # будет несколько таблиц
        # db_handler.create_data_table("pressure") # будет несколько таблиц
        # db_handler.create_data_table("conductivity")

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
    def pump_controller(self, pump_number, state,):
        try:
            command = "p{0}{1}\n".format(pump_number, state)
            answer = HAUHandler.send_command(com=command, serial_dev=self.ser)

            self._status = "works\n{}".format(answer)

            self.db_handler.add_data_in_table("pump{}".format(pump_number), int(state))

            return answer
        except Exception as e:
            self._status = "error\n{}".format(e)
            return e

    # метод для отправки команд клапанам
    def valve_controller(self, valve_number, state,):
        try:
            command = "v{0}{1}\n".format(valve_number, state)
            answer = HAUHandler.send_command(com=command, serial_dev=self.ser)

            self._status = "works\n{}".format(answer)
            return answer
        except Exception as e:
            self._status = "error\n{}".format(e)
            return e

    # метод для отправки команд белым cветодиодам
    def white_led_controller(self, board_number, white_led_state):
        try:
            command = "o{0}8000{1}\n".format(board_number, white_led_state)
            answer = HAUHandler.send_command(com=command, serial_dev=self.ser)

            self._status = "works\n{}".format(answer)
            return answer
        except Exception as e:
            self._status = "error\n{}".format(e)
            return e


    # метод для отправки команд красным cветодиодам
    def red_led_controller(self, board_number, red_led_state):
        try:
            command = "o{0}80{1}00\n".format(board_number, red_led_state)
            answer = HAUHandler.send_command(com=command, serial_dev=self.ser)

            self._status = "works\n{}".format(answer)
            return answer
        except Exception as e:
            self._status = "error\n{}".format(e)
            return e

    # метод для отправки команд вентилятору
    def fan_controller(self, board_number, state):
        try:
            command = "o{0}4000{1}\n".format(board_number, state)
            answer = HAUHandler.send_command(com=command, serial_dev=self.ser)

            self._status = "works\n{}".format(answer)
            return answer
        except Exception as e:
            self._status = "error\n{}".format(e)
            return e

    # метод для чтения данных с датчиков температур на платах освещения
    def led_temp_reader(self, board_number, sensor_number):
        try:
            command = "o{0}20000{1}\n".format(board_number, sensor_number)
            answer = HAUHandler.send_command(com=command, serial_dev=self.ser)

            self._status = "works\n{}".format(answer)
            return answer

        except Exception as e:
            self._status = "error\n{}".format(e)
            return e

    # метод для чтения данных с датчиков давления
    def pressure_getter(self, sensor_number):
        try:
            command = "s{}\n".format(sensor_number)
            answer = HAUHandler.send_command(com=command, serial_dev=self.ser)

            self._status = "works\n{}".format(answer)
            return answer

        except Exception as e:
            self._status = "error\n{}".format(e)
            return e

    # метод для чтения данных с кондуктометра
    def conductivity_getter(self):
        try:
            command = "r\n"
            answer = HAUHandler.send_command(com=command, serial_dev=self.ser)

            self._status = "works\n{}".format(answer)
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
