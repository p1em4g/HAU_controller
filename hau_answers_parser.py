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

# red
# b'usart cmd (  addr: 0x8C, cmd: 0x80 )\\r\\n',
# b'usart cmd (  addr: 0x8C, cmd: 0x80 )\\r\\n',
# b'usart cmd (  addr: 0x8E, cmd: 0x80 )\\r\\n',
# white
# b'usart cmd (  addr: 0x8C, cmd: 0x80 )\\r\\n',


# b'usart cmd (  addr: 0x8E, cmd: 0x20 )\\r\\n    posv_temp: 23.84 ( "
#           "dat1: 0xAA, dat2: 0xAA, dat3: 0x64, dat'
