import re

class HAUAnswersParser:
    @classmethod
    def pump_answer_parser(cls, data_str):
        if re.search("b'Pump #.+ - OFF", data_str,):
            return 0
        elif re.search("b'Pump #.+ - ON", data_str,):
            return 1
        else:
            return None

    @classmethod
    def valve_answer_parser(cls, data_str):
        if re.search("b'Valve #.+ - CLOSE", data_str, ):
            return 0
        elif re.search("b'Valve #.+ - OPEN", data_str, ):
            return 1
        else:
            return None


if __name__ == "__main__":
    res = HAUAnswersParser.pump_answer_parser("(b'Pump #6 - OFF\r\n',)")
    print(res)

    res = HAUAnswersParser.valve_answer_parser("# 'data': (b'Valve #5 - CLOSE\\r\\n',))")
    print(res)
# 'data': "(b'Pump #6 - OFF\\r\\n',)",
#   'data': "(b'Pump #6 - ON\\r\\n',)",
#   'data': "(b'Valve #5 - OPEN\\r\\n',)",
# 'data': "(b'Valve #5 - CLOSE\\r\\n',)",
# b'Valve #5 - CLOSE
# 'data': "(b'usart cmd (  addr: 0x8E, cmd: 0x80 )\\r\\n',)",
