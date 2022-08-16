import dash
from dash import html

import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State

from plexus.nodes.message import Message

import json

from pprint import pformat

from cont_tab import cont_tab
from command_sender import CommandSender

devices = {}

app = dash.Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])

app.layout = html.Div([
    dbc.Tabs([
        dbc.Tab(cont_tab, label='control_panel')
    ])
])


@app.callback(
    Output("device_dropdown", 'options'),
    State("endpoint_input", "value"),
    State("node_address_dropdown", "value"),
    Input("get_commands_button", "n_clicks")
)
def get_devices(endpoin, node_address, n_clicks):
    if endpoin and node_address and n_clicks:
        answer = CommandSender.send_command(addr=node_address, device=node_address, command="info", endpoint=endpoin)
        global devices
        devices = Message.parse_zmq_msg(answer)[1]["data"]["devices"]
        options = [
            {"label": x, "value": x} for x in devices
        ]
        return options


@app.callback(
    Output("command_dropdown", 'options'),
    Input("device_dropdown", 'value')
)
def get_commands(device):
    if device:
        options = [
            {"label": x, "value": x} for x in devices[device]["commands"]
        ]
        return options


@app.callback(
    Output("command_arguments_input", "value"),
    Input("device_dropdown", 'value'),
    Input("command_dropdown", 'value'),
)
def get_arguments(device, command):
    if device and command:
        return str(devices[device]["commands"][command]['input_kwargs']).replace("'", "\"")


@app.callback(
    Output("output_textarea", "value"),
    State("device_dropdown", 'value'),
    State("command_dropdown", 'value'),
    State("command_arguments_input", "value"),
    State("endpoint_input", "value"),
    State("node_address_dropdown", "value"),
    Input("send_button", "n_clicks")
)
def send_command(device, command, arguments, endpoint, node_address, n_clicks):
    if device and command and arguments:
        try:
            data = json.loads(arguments)
        except:
            data = None

        answer = CommandSender.send_command(
            addr=node_address,
            device=device,
            command=command,
            data=data,
            endpoint=endpoint
        )
        return pformat(Message.parse_zmq_msg(answer))


if __name__ == '__main__':
    app.run_server(debug=True)
