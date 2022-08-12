from plexus.nodes.node import BaseNode, PeriodicCallback

from devices.hau_handler import HAUHandler

import config


class HAUNode(BaseNode):
    """

    """
    def __init__(self, endpoint: str, list_of_nodes: list, is_daemon: bool = True):
        super().__init__(endpoint, list_of_nodes, is_daemon)
        self._annotation = "humidification and aeration unit"

        self.hau_handler = HAUHandler(
            name="hau_handler",
        )
        self.add_device(self.hau_handler)

    def custom_preparation(self):
       pass


if __name__ == "__main__":
    network = config.network or [{"address": "tcp://10.9.0.12:5666",}]

    n1 = HAUNode(network[0]['address'], list_of_nodes=network)
    n1.start()
    n1.join()