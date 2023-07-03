# Copyright (C) 2023, BRAIN-LINK UG (haftungsbeschränkt). All Rights Reserved.
# SPDX-License-Identifier: GPL-3.0-only OR LicenseRef-ScanHub-Commercial
# %%
"""Utility function to create a sequence plot with plotly."""

from dataclasses import dataclass

import numpy as np
import plotly.graph_objects as go  # type: ignore
from pypulseq import Sequence  # type: ignore


@dataclass
class TraceData:
    """Numpy model for trace data."""

    x: list[float]
    y: list[float]
    name: str


def get_sequence_plot(
    seq: Sequence, time_range: tuple[float, float] = (0.0, np.inf), time_factor=1e3
) -> list[TraceData]:
    """Compute a sequence dictionary from pulseq sequence object.

    Parameters
    ----------
    seq
        pypulseq sequence object
    time_range, optional
        time span of the sequence plot, by default (0., np.inf)
    time_factor, optional
        time prefix, by default 1e3

    Returns
    -------
        list of plot data models
    """
    # Empty lists for RX and TX channel: [Time, Magnitude, Phase]
    rx_data: list[list] = [[0.0], [0.0], [0.0]]
    tx_data: list[list[float]] = [[0.0], [0.0], [0.0]]

    # Empty gradient channel dictionary: {channel: [Time, Magnitude]}
    gradients: dict[str, list[list]] = {
        channel: [[0.0], [0.0]] for channel in ["gx", "gy", "gz"]
    }

    t_0 = 0.0

    for idx in range(len(seq.block_events.keys())):
        block = seq.get_block(idx + 1)
        is_valid = time_range[0] <= t_0 <= time_range[1]
        if is_valid:
            # ADC event
            if adc := block.adc:
                adc_duration = adc.dwell * (adc.num_samples + 0.5)
                rx_data[0] += list(
                    np.cumsum([t_0, adc.delay, 0, adc_duration, 0]) * time_factor
                )
                rx_data[1] += [0.0, 0.0, 1.0, 1.0, 0.0]

            # RF event
            if rf_data := block.rf:
                time_points = rf_data.t + rf_data.delay
                tx_data[0] += list(
                    np.round(time_factor * (t_0 + time_points), 2).astype(float)
                )
                tx_data[1] += list(np.round(np.abs(rf_data.signal), 2).astype(float))
                tx_data[2] += list(
                    np.round(
                        np.angle(
                            rf_data.signal
                            * np.exp(1j * rf_data.phase_offset)
                            * np.exp(1j * 2 * np.pi * rf_data.t * block.rf.freq_offset)
                        ),
                        2,
                    ).astype(float)
                )

            # Gradient event
            for channel in gradients.keys():
                if gradient_block := getattr(block, channel):
                    if gradient_block.type == "grad":
                        time_points = np.array(
                            [
                                gradient_block.delay,
                                *gradient_block.tt + gradient_block.delay,
                                gradient_block.shape_dur,
                            ]
                        )
                        waveform = 1e-3 * np.array(
                            [
                                gradient_block.first,
                                *gradient_block.waveform,
                                gradient_block.last,
                            ]
                        )
                    else:
                        time_points = np.cumsum(
                            [
                                0,
                                gradient_block.delay,
                                gradient_block.rise_time,
                                gradient_block.flat_time,
                                gradient_block.fall_time,
                            ]
                        )
                        waveform = (
                            1e-3 * gradient_block.amplitude * np.array([0, 0, 1, 1, 0])
                        )

                    gradients[channel][0] += list(
                        np.round(time_factor * (t_0 + time_points), 2).astype(float)
                    )
                    gradients[channel][1] += list(np.round(waveform, 2).astype(float))

        # Update current time offset
        t_0 += float(seq.block_durations[idx])

    # Set all channels back to zero
    tx_data[0] += [tx_data[0][-1], seq.duration()[0] * time_factor]
    tx_data[1] += [0.0, 0.0]
    rx_data[0] += [rx_data[0][-1], seq.duration()[0] * time_factor]
    rx_data[1] += [0.0, 0.0]
    for grad in gradients.values():
        grad[0] += [grad[0][-1], seq.duration()[0] * time_factor]
        grad[1] += [0.0, 0.0]

    return generate_plotly_figure(
        [
            TraceData(x=tx_data[0], y=tx_data[1], name="Tx"),
            TraceData(x=rx_data[0], y=rx_data[1], name="Rx"),
            TraceData(x=gradients["gx"][0], y=gradients["gx"][1], name="Gx"),
            TraceData(x=gradients["gy"][0], y=gradients["gy"][1], name="Gy"),
            TraceData(x=gradients["gz"][0], y=gradients["gz"][1], name="Gz"),
        ]
    )


def generate_plotly_figure(traces: list[TraceData]):
    """Generate plotly figure of traces.

    Parameters
    ----------
    traces
        List of trace data

    Returns
    -------
        Plotly figure
    """
    fig = go.Figure()
    for k, trace in enumerate(traces):
        fig.add_trace(
            go.Scatter(
                x=trace.x,
                y=trace.y,
                name=trace.name,
                yaxis=f"y{len(traces)-k}",
                mode="lines",
            )
        )

    fig.update_layout(
        autosize=False,
        width=1600,
        height=900,
        xaxis={
            "ticks": "outside",
            "title": "Time (ms)",
            "rangeslider": {"autorange": True},
        },
        yaxis={"domain": [0.0, 0.15]},
        yaxis2={"domain": [0.2, 0.35]},
        yaxis3={"domain": [0.4, 0.55]},
        yaxis4={"domain": [0.6, 0.75]},
        yaxis5={"domain": [0.8, 0.95]},
    )

    return fig


# %%