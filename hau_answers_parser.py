import  re

class HAUAnswersParser:

    @classmethod
    def pump_answer_parser(cls, data_str):
        if "OFF" in data_str:
            return 0
        elif "ON" in data_str:
            return 1
        else:
            return None

    @classmethod
    def valve_answer_parser(cls, data_str):
        if "OPEN" in data_str:
            return 1
        elif "CLOSE" in data_str:
            return 0
        else:
            return None

    @classmethod
    def pressure_and_conductivity_answer_parser(cls, data_str):
        parsed_data = re.search(' \d\.\d\d', data_str)
        if parsed_data:
            return float(parsed_data.group())
        else:
            return None


if __name__ == "__main__":
    data = "'data': (b'Sensor #1 (ADC code: 549; ADC val: 2.61)\\r\\n',)"
    data2 = "b'Conductometr (ADC code: 1; ADC val: 0.00) \\r\\n',)"
    data4 = "b'Valve #6 - CLOSE\r\n'"
    data5 = "(b'Valve #6 - OPEN\r\n',)"
    data6 = " OPEN"
    print(HAUAnswersParser.valve_answer_parser(data4))
    a = re.match("OPEN", "(b'Valve #6 - OPEN\r\n',)")
    print(a)
