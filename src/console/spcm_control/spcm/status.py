"""Spectrum card status register translations and descriptions from user manual."""

from console.spcm_control.spcm._constants import (
    M2STAT_CARD_PRETRIGGER,
    M2STAT_CARD_READY,
    M2STAT_CARD_SEGMENT_PRETRG,
    M2STAT_CARD_TRIGGER,
    M2STAT_DATA_BLOCKREADY,
    M2STAT_DATA_END,
    M2STAT_DATA_ERROR,
    M2STAT_DATA_OVERRUN,
)

# Dictionary of status registers
status_reg: dict[int, str] = {
    M2STAT_CARD_PRETRIGGER: "M2STAT_CARD_PRETRIGGER",
    M2STAT_CARD_TRIGGER: "M2STAT_CARD_TRIGGER",
    M2STAT_CARD_READY: "M2STAT_CARD_READY",
    M2STAT_CARD_SEGMENT_PRETRG: "M2STAT_CARD_SEGMENT_PRETRG",
    M2STAT_DATA_BLOCKREADY: "M2STAT_DATA_BLOCKREADY",
    M2STAT_DATA_END: "M2STAT_DATA_END",
    M2STAT_DATA_OVERRUN: "M2STAT_DATA_OVERRUN",
    M2STAT_DATA_ERROR: "M2STAT_DATA_ERROR",
}

# Dictionary of status register descriptions
status_reg_desc: dict[int, str] = {
    M2STAT_CARD_PRETRIGGER: "Acquisition modes only: the first pretrigger area has been filled. In Multi/ABA/Gated acquisition this status is set only for the first segment and will be cleared at the end of the acquisition.",
    M2STAT_CARD_TRIGGER: "The first trigger has been detected",
    M2STAT_CARD_READY: "The card has finished its run and is ready",
    M2STAT_CARD_SEGMENT_PRETRG: "This flag will be set for each completed pretrigger area including the first one of a Single acquisition. Additionally for a Multi/ABA/Gated acquisition of M4i/M4x/M2p only, this flag will be set when the pretrigger area of a segment has been filled and will be cleared after the trigger for a segment has been detected.",
    M2STAT_DATA_BLOCKREADY: "The next data block as defined in the notify size is available. It is at least the amount of data available but it also can be more data.",
    M2STAT_DATA_END: "The data transfer has completed. This status information will only occur if the notify size is set to zero.",
    M2STAT_DATA_OVERRUN: "The data transfer had on overrun (acquisition) or underrun (replay) while doing FIFO transfer.",
    M2STAT_DATA_ERROR: "An internal error occurred while doing data transfer.",
}
