"""
TODO: Add annotation option to add comments, session option to show multiple acquisitions in tabs, add sequence plot
"""
import argparse
import json
import logging
import os

import dash_bootstrap_components as dbc
import numpy as np
import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html
from dash_extensions import EventListener


def json_viewer_component(data):
    """Build JSON viewer."""
    if not isinstance(data, dict):
        raise ValueError("Input data must be a dictionary.")

    def build_nested_list(data):
        """Recursively builds a nested list for displaying objects and lists."""
        if isinstance(data, dict):
            return html.Ul([
                html.Li([
                    html.Span(f"{key}: ", style={'fontWeight': 'bold'}),
                    build_nested_list(value)
                ]) for key, value in data.items()
            ])
        elif isinstance(data, list):
            return html.Ul([
                html.Li(build_nested_list(item)) for item in data
            ])
        else:
            # Primitive values
            return html.Span(f"{data}", style={'color': 'gray'})

    # Create the list of primary keys
    primary_keys = []
    for key, value in data.items():
        # If the value is a dict or list, make it expandable
        if isinstance(value, (dict, list)):
            primary_keys.append(
                html.Details([
                    html.Summary(f"{key}", style={'cursor': 'pointer', 'fontWeight': 'bold'}),
                    build_nested_list(value)
                ])
            )
        else:
            # Directly display the value for primitive types
            primary_keys.append(html.Div([
                html.Span(f"{key}: ", style={'fontWeight': 'bold'}),
                html.Span(f"{value}", style={'color': 'gray'})
            ]))

    return html.Div(primary_keys, style={'margin': '10px'})


def data_viewer_component(data, app, viewer_id: str):
    """Create data viewer vomponent."""
    # Check if the image is 3D and determine the number of slices
    if data.ndim == 3:
        num_slices = data.shape[0]  # Number of slices in the stack
    elif data.ndim == 2:
        num_slices = 1  # Treat 2D as a single slice
    else:
        raise ValueError(f"Invalid image dimension: {data.shape}")

    # Calculate aspect ratio
    image_height, image_width = data.shape[-2:]
    aspect_ratio = image_width / image_height
    image_base_height = 500

    viewer_layout = dbc.Col([
        EventListener(
            html.Div(
                dcc.Graph(
                    id=f"{viewer_id}:image-graph",
                    # style={"marginBottom": "10px"},
                    config={
                        "scrollZoom": False,
                        "displaylogo": False,
                        'modeBarButtonsToAdd': [
                            'drawline',
                            'drawopenpath',
                            'drawcircle',
                            'drawrect',
                            'eraseshape',
                        ]
                    },
                ),
                id=f"{viewer_id}:image-graph-wrapper",
                style={
                    "display": "flex",  # Use Flexbox layout
                    "justifyContent": "center",  # Center horizontally
                    "alignItems": "center",  # Center vertically
                    "height": "100%",  # Ensure the wrapper uses full height
                    "width": "100%",   # Ensure the wrapper uses full width
                },
            ),
            id=f"{viewer_id}:image-events",
            # events=[{"event": "wheel"}],  # Correct event configuration
            events=[{"event": "wheel", "props": ["deltaY"]}]
        ),
        html.Div(
            dcc.RangeSlider(
                id=f"{viewer_id}:range-slider",
                min=0,
                max=1,
                step=0.01,
                value=[0, 1],
                marks={0: "0", 1: "1"},
                tooltip={
                    "always_visible": True,
                    "placement": "bottom",
                    "style": {"fontSize": "10px"}
                },
            ),
            style={"marginLeft": "20px"}
        ),
        dcc.Graph(
            id=f"{viewer_id}:histogram-graph",
            style={"height": "160px", "width": "100%", "paddingRight": "10px"},
            config={"scrollZoom": True, "displaylogo": False},
        ),
        dcc.Store(id=f"{viewer_id}:current-slice", data=num_slices // 2),
    ], className="text-center")

    @app.callback(
        Output(f"{viewer_id}:current-slice", "data"),
        Input(f"{viewer_id}:image-events", "event"),
        Input(f"{viewer_id}:current-slice", "data"),
    )
    def update_slice_on_wheel(event, current_slice):
        if event and "deltaY" in event:
            delta = event["deltaY"]
            # Interpret any scroll event as a single step
            step = 1 if delta > 0 else -1
            new_slice = min(max(current_slice + step, 0), num_slices - 1)  # Clamp to valid range
            # print(f"deltaY: {delta}, New Slice: {new_slice}")
            return new_slice

        return current_slice

    @app.callback(
        Output(f"{viewer_id}:image-graph", "figure"),
        Output(f"{viewer_id}:histogram-graph", "figure"),
        Input(f"{viewer_id}:range-slider", "value"),
        Input(f"{viewer_id}:current-slice", "data"),
    )
    def update_image(data_range, slice_index):
        # Select the current slice for 3D data
        if num_slices > 1:
            current_slice = data[slice_index]
        else:
            current_slice = data
        # Apply range-based contrast adjustment
        min_val, max_val = data_range
        adjusted_image = np.clip((current_slice - min_val) / (max_val - min_val), 0, 1)

        # Create image figure
        image_fig = go.Figure(data=go.Heatmap(
            z=adjusted_image,
            colorscale="gray",
            colorbar=dict(title="Intensity"),
        ))
        image_fig.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            # xaxis=dict(title="RO"),
            yaxis=dict(title=f"Slice: {slice_index+1}"),
            height=image_base_height,  # Adjust height to ensure clarity
            width=image_base_height*aspect_ratio,
            newshape_line_color='blue',
        )

        # Calculate histogram data for the current slice
        hist_values, bin_edges = np.histogram(current_slice, bins=400, range=(0, 1))
        # Create histogram figure
        hist_fig = go.Figure(data=go.Bar(
            x=bin_edges[:-1],
            y=hist_values,
            marker=dict(color='blue')
        ))
        hist_fig.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(title="Intensity", range=[0, 1]),
            yaxis=dict(title="Count"),
            newshape_line_color='blue',
        )

        return image_fig, hist_fig

    return viewer_layout


def dashboard_app(data_dir):
    """Build the dashboard main app."""
    # Validate directories
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"The data directory {data_dir} does not exist.")

    # print("Loading data from directory: ", data_dir)

    if not os.path.exists(img_file := os.path.join(data_dir, "image.npy")):
        raise FileNotFoundError(f"Image data file not found at {img_file}")

    if not os.path.exists(ksp_file := os.path.join(data_dir, "kspace.npy")):
        raise FileNotFoundError(f"K-space data file not found at {ksp_file}")

    # Set Log level
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    img_data = np.load(img_file)
    # Normalize image data to the range [0, 1]
    img_data = np.abs(img_data)
    img_data = (img_data - np.min(img_data)) / (np.max(img_data) - np.min(img_data))

    ksp_data = np.load(ksp_file)
    ksp_data = np.abs(ksp_data)

    # Load metadata from a JSON file
    meta_file = os.path.join(data_dir, "meta.json")
    if not os.path.exists(meta_file):
        raise FileNotFoundError(f"Meta information file not found at {meta_file}")
    with open(meta_file, "r") as f:
        meta_info = json.load(f)

    # Create Dash app
    app = Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])
    app.title = "Nexus Dashboard"

    app.layout = dbc.Container([
        html.H3(f"Acquisition ID: {os.path.basename(os.path.normpath(data_dir))}", className="text-left"),
        # A row with two columns
        dbc.Row([
            # First column: Meta data viewer
            dbc.Col(
                [
                    html.H5("Metadata Viewer", className="text-left mb-3"),
                    # Scrollable JSON viewer
                    dbc.Card(
                        json_viewer_component(meta_info),  # Foldable JSON viewer
                        style={
                            'overflow': 'auto',
                            'maxHeight': '650px',
                            'padding': '10px',
                            'marginRight': '10px',
                        }
                    )
                ],
                width=4,
            ),
            dbc.Col([
                html.H5("Image Magnitude", className="text-left"),
                data_viewer_component(img_data, app, "img"),
            ], width=4),
            dbc.Col([
                html.H5("K-space Magnitude", className="text-left"),
                data_viewer_component(ksp_data, app, "ksp"),
            ], width=4)
        ]),
    ], fluid=True, style={"marginTop": "10px", "paddingLeft": "20px", "paddingRight": "20px"})

    return app


def main():
    """Parse arguments and start the dashboard server."""
    parser = argparse.ArgumentParser(description="Generate an HTML dashboard for Nexus console acquisition data.")
    parser.add_argument(
        "-p", "--data_path",
        required=True,
        type=str,
        help="Directory containing the image data and metadata."
    )
    parser.add_argument(
        "-d", "--debug_mode",
        required=False,
        default=False,
        type=bool,
        help="Flag indicating if dashboard should run in debug mode."
    )

    args = parser.parse_args()
    app = dashboard_app(args.data_path)
    app.run_server(debug=args.debug_mode, use_reloader=False)


if __name__ == '__main__':
    main()
