# Acquisition

An acquisition is executed by [`AcquisitionControl.run`][console.spcm_control.acquisition_control.AcquisitionControl.run] after the sequence has been calculated by `set_sequence`. The AWG replays the calculated sequence while the digitizer records one gate per ADC event. Each average is a complete replay of the sequence.

## Sequence of operations

```mermaid
---
config:
  fontFamily: Inter, sans-serif
  # Larger text; narrower participants and margins keep the diagram from being scaled down
  sequence:
    actorFontSize: 18
    messageFontSize: 18
    noteFontSize: 18
    width: 120
    actorMargin: 30
  # Replaces Material's sequence diagram styles for this diagram: participants coloured like the
  # other diagrams (host software blue, measurement cards orange), lifelines and loop borders neutral.
  # Mermaid drops a themeCSS that contains ">", hence descendant instead of child selectors.
  themeCSS: |
    .actor { fill: var(--md-mermaid-sequence-actor-bg-color); stroke: var(--md-mermaid-sequence-actor-border-color) }
    text.actor tspan { fill: var(--md-mermaid-sequence-actor-fg-color); font-family: var(--md-mermaid-font-family) }
    rect.actor[name=AC], rect.actor[name=TX], rect.actor[name=RX], rect.actor[name=P] { fill: #2f6bff22; stroke: #2f6bff }
    rect.actor[name=AWG], rect.actor[name=DIG] { fill: #e67e2222; stroke: #e67e22 }
    .actor-line { stroke: var(--md-default-fg-color) }
    .messageLine0, .messageLine1 { stroke: var(--md-mermaid-sequence-message-line-color) }
    .messageText { fill: var(--md-mermaid-sequence-message-fg-color); stroke: none; font-family: var(--md-mermaid-font-family) !important }
    #arrowhead path { fill: var(--md-mermaid-sequence-message-line-color); stroke: none }
    .loopLine { fill: var(--md-mermaid-sequence-loop-bg-color); stroke: var(--md-default-fg-color--light) }
    .loopText, .loopText tspan { fill: var(--md-mermaid-sequence-loop-fg-color); stroke: none; font-family: var(--md-mermaid-font-family) !important }
    .labelBox { fill: var(--md-mermaid-sequence-label-bg-color); stroke: none }
    .sequenceNumber { fill: var(--md-mermaid-sequence-number-fg-color) }
    defs #sequencenumber { fill: var(--md-mermaid-sequence-number-bg-color) !important }
---
sequenceDiagram
    autonumber
    participant AC as AcquisitionControl
    participant TX as TxCard
    participant RX as RxCard
    participant P as RxProcessor
    participant AWG
    participant DIG as Digitizer

    AC->>TX: Set gradient offsets
    AC->>RX: Start operation
    RX->>DIG: Start card, wait for ADC gates
    RX-->>AC: Ready
    AC->>TX: Start operation
    TX->>AWG: Fill ring buffer and start replay
    par AWG thread
        loop Until the replay buffer is transferred
            AWG-->>TX: Chunk consumed
            TX->>AWG: Refill chunk
        end
    and Digitizer thread
        loop For each ADC event
            AWG->>DIG: ADC gate and phase reference
            DIG->>RX: Timestamps and gate data
            RX->>P: Submit RxData
        end
    and Main thread
        AC->>AC: Wait for all gates
    end
    AC->>TX: Stop operation
    AC->>RX: Stop operation
    AC->>TX: Reset gradient offsets
    AC->>P: Collect processed RxData
```

Steps 2–14 are executed once per average; the next average starts after `averaging_delay`. Averages are not summed, each `RxData` carries its `average_index`.

| Steps | Description |
|---|---|
| 1, 15 | The gradient offsets of the acquisition parameters are written to the offset registers of AWG channels 1–3 before the first average and reset to zero after the last. |
| 2–5 | The digitizer is started first and waits for the first ADC gate. As soon as its thread is ready, the AWG is started; it uses a software trigger, so the replay begins immediately. |
| 6–8 | The AWG replays the sequence while the TX thread refills the ring buffer (see [AWG: FIFO streaming](#awg-fifo-streaming)). |
| 9–11 | The ADC gates and the phase reference embedded in the replay buffer (see [Sequence calculation](sequence-calculation.md#replay-buffer)) trigger the gated recording of the digitizer (see [Digitizer: gated recording](#digitizer-gated-recording)). Each gate is submitted for processing while the acquisition continues (see [Postprocessing](postprocessing.md)). |
| 12 | The main thread polls the number of received gates every 100 ms and reports the progress to the optional `progress_callback`. The average ends when all gates are received, or after a timeout of 5 s plus the sequence duration. |
| 13, 14 | Both cards are stopped as soon as the last gate is received, so blocks after the last ADC event (e.g. a final TR delay) are not necessarily played out completely. |
| 16 | The processed `RxData` of all averages are collected in order. |

## AWG: FIFO streaming mode

| Parameter | Value |
|---|---|
| Ring buffer | Page-aligned DMA buffer in host memory; size of the replay buffer rounded up to whole chunks, at most 1 GiB |
| Chunk size | Notify size of the DMA transfer: 1/16 of the ring buffer, at least 4 KiB. The driver signals each consumed chunk. |
| Start (step 6) | The ring buffer is filled completely before the card is started, so sequences that fit into it are transferred at once |
| Refill (steps 7–8) | One chunk of the replay buffer each time the card has consumed one |
| End | The last chunk is zero-padded, so all outputs return to 0 V |

Sequences longer than the on-board memory are replayed without interruption as long as the host transfers the data faster than the card replays them (see [Console hardware](hardware.md#workstation)).

## Digitizer: gated recording mode

| Parameter | Value |
|---|---|
| Trigger (step 9) | Rising edge of the ADC gate at X1; the card records while the gate is high |
| Timestamps (step 10) | Start and end of each gate; their difference gives the number of samples of the gate |
| Data buffer (step 10) | 1 GiB DMA ring buffer in host memory, notify size 4 KiB; the wrap-around at the end of the buffer is handled during readout |
| Pre-trigger | 8 samples per gate, removed during readout |
| Phase reference (step 11) | Bit 15 of channel 0 during the first ≤ 1000 samples of the gate; stored separately in `RxData` and removed from the analog data |
