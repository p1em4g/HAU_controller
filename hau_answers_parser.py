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
        if "CLOSE" in data_str:
            return 0
        elif "OPEN" in data_str:
            return 1
        else:
            return None

    @classmethod
    def pressure_answer_parser(cls, data_str):
        parsed_data = re.search(' \d\.\d\d', data_str)
        if parsed_data:
            return float(parsed_data.group())
        else:
            return None


if __name__ == "__main__":
    data = "'data': (b'Sensor #1 (ADC code: 549; ADC val: 2.61)\\r\\n',)"
    data2 = 'dfsdfsf'
    print(HAUAnswersParser.pressure_answer_parser(data2))
