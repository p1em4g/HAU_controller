import time, sys, os

from plexus.nodes.command import Command
from plexus.devices.base_device import BaseDevice
import serial


class HAUHandler(BaseDevice):
    """
    """
    def __init__(self, name):
        super().__init__(name)
        self._description = "this is device to control humidification and aeration unit"

        dev = "/dev/ttyUSB0"
        baud = 9600
        timeout = 1
        self.ser = serial.Serial(port=dev, baudrate=baud, timeout=timeout)
        time.sleep(2)

        pump_command = Command(
            name="pump_command",
            annotation="pump_command",
            output_kwargs={"state": "int", "pump_number": "int",},
            action = self.pump_controller
        )
        self.add_command(pump_command)

    @classmethod
    def send_command(cls, com: str, serial_dev):
        serial_dev.flushInput()
        serial_dev.flushOutput()
        serial_dev.write(com.encode("utf-8"))
        echo = None
        if serial_dev.readable():
            echo = serial_dev.read(100)
            # ans = serial_dev.read(70)
            # print(echo)
            # print(ans)
        return echo,  # ans

    def pump_controller(self, state, pump_number):
        try:
            command = "p{0}{1}\n".format(pump_number, state)
            answer = HAUHandler.send_command(com=command, serial_dev=self.ser)

            self._status = "works\n{}".format(answer)

        except Exception as e:
            self._status = "error\n{}".format(e)
            return e


# if __name__ == "__main__":
    # c = BMP180Sensor("bmp1")
    # print(c.call("info"))
    # print(c.call("get_state"))
    # while True:
    #     print(c.call("get_temperature"))
    #     time.sleep(1)
    #     print(c.call("get_temp_and_press"))
    #     time.sleep(1)
    # c.call("start")

    # c = DHT11("dht11")
    # print(c.call('gd'))
    # print(DHT11.call("gd"))