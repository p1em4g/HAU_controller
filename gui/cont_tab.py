import dash_bootstrap_components as dbc
from dash import html
from dash import dcc
import config

cont_tab = html.Div([
    html.Div(children = [

        dbc.Row([
            dbc.Col(html.Div([
                dbc.InputGroup([dbc.InputGroupText("endpoint"), dbc.Input(id = "endpoint_input",placeholder="address", value=config.endpoint)])
            ])),
            dbc.Col(html.Div([
                            dbc.InputGroup(
                                [
                                    dbc.InputGroupText("node_address"),
                                    dbc.Select(
                                        id='node_address_dropdown',
                                        options=[
                                            {"label": config.network[0][x], "value": config.network[0][x]} for x in config.network[0]
                                        ]),
                                ]),
                            ])),
            dbc.Col(html.Div([dbc.Button("get_devices",id = 'get_commands_button', color="primary", className="me-1")]), width=1),
            dbc.Col(html.Div([dbc.Textarea(id = "connect_status_textaria", className="mb-3", placeholder="A Textarea",disabled = True),])),
            ]),



    ],style = {"border-bottom":"1px solid black"}),

    html.Div(children = [
        dbc.Row([
            dbc.Col(html.Div([
                dbc.InputGroup(
                    [
                        dbc.InputGroupText("Device"),
                        dbc.Select(
                            id = 'device_dropdown',

                        ),

                    ]
                ),
            ])),

            dbc.Col(html.Div([
                dbc.InputGroup(
                    [
                        dbc.InputGroupText("Command"),
                        dbc.Select(
                            id = 'command_dropdown',

                        ),

                    ]
                ),
            ])),

            dbc.Col(html.Div([dbc.InputGroup([dbc.InputGroupText("Arguments"), dbc.Input(id = 'command_arguments_input',placeholder="")])])),
            dbc.Col(html.Div([dbc.Button("SEND",id = 'send_button', color="primary", className="me-1")])),

        ])
    ],style = {"border-bottom":"1px solid black"}),

    html.Div(children=[
        dcc.Textarea(
            id='output_textarea',
            value='Textarea',
            style={'width': '100%', 'height': 500},
        ),
    ],style = {"margin-top":"1%"}),
])