import plexus.utils.console_client_api as ccapi
from plexus.nodes.message import Message
import pprint

import config


class CommandSender:
    @classmethod
    def send_command(cls, addr, device, command, data=None, network=None, endpoint=None):
        hello_msg = Message(
            addr=addr,
            device=device,
            command=command,
            data=data
        )

        user_api = ccapi.PlexusUserApi(
            endpoint=endpoint or config.endpoint,
            list_of_nodes=network or config.network
        )

        ans = user_api.send_msg(hello_msg)

        return ans


if __name__ == "__main__":
    addr = "tcp://10.9.0.12:5666"
    device = "hau_handler"
    command = "get_pressure"
    data = {"sensor_number": "2"}
    network = [
        {"address": "tcp://10.9.0.12:5666",
        "address1": "tcp://10.9.0.7:5568", }
    ]
    endpoint = "tcp://10.9.0.7:5668"

    ans = CommandSender.send_command(
        addr=addr,
        device=device,
        command=command,
        data=data,
        network=network,
        endpoint=endpoint
    )
    print(ans)
    print(Message.parse_zmq_msg(ans))
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(Message.parse_zmq_msg(ans))
