SPCM_ERROR_ORIGIN_MASK = 0x80000000
SPCM_ERROR_ORIGIN_LOCAL = 0x00000000
SPCM_ERROR_ORIGIN_REMOTE = 0x80000000
ERR_OK = 0x0000
ERR_INIT = 0x0001
ERR_NR = 0x0002
ERR_TYP = 0x0003
ERR_FNCNOTSUPPORTED = 0x0004
ERR_BRDREMAP = 0x0005
ERR_KERNELVERSION = 0x0006
ERR_HWDRVVERSION = 0x0007
ERR_ADRRANGE = 0x0008
ERR_INVALIDHANDLE = 0x0009
ERR_BOARDNOTFOUND = 0x000A
ERR_BOARDINUSE = 0x000B
ERR_EXPHW64BITADR = 0x000C
ERR_FWVERSION = 0x000D
ERR_SYNCPROTOCOL = 0x000E
ERR_KERNEL = 0x000F
ERR_LASTERR = 0x0010
ERR_ABORT = 0x0020
ERR_BOARDLOCKED = 0x0030
ERR_DEVICE_MAPPING = 0x0032
ERR_NETWORKSETUP = 0x0040
ERR_NETWORKTRANSFER = 0x0041
ERR_FWPOWERCYCLE = 0x0042
ERR_NETWORKTIMEOUT = 0x0043
ERR_BUFFERSIZE = 0x0044
ERR_RESTRICTEDACCESS = 0x0045
ERR_INVALIDPARAM = 0x0046
ERR_TEMPERATURE = 0x0047
ERR_FAN = 0x0048
ERR_REG = 0x0100
ERR_VALUE = 0x0101
ERR_FEATURE = 0x0102
ERR_SEQUENCE = 0x0103
ERR_READABORT = 0x0104
ERR_NOACCESS = 0x0105
ERR_POWERDOWN = 0x0106
ERR_TIMEOUT = 0x0107
ERR_CALLTYPE = 0x0108
ERR_EXCEEDSINT32 = 0x0109
ERR_NOWRITEALLOWED = 0x010A
ERR_SETUP = 0x010B
ERR_CLOCKNOTLOCKED = 0x010C
ERR_MEMINIT = 0x010D
ERR_POWERSUPPLY = 0x010E
ERR_ADCCOMMUNICATION = 0x010F
ERR_CHANNEL = 0x0110
ERR_NOTIFYSIZE = 0x0111
ERR_RUNNING = 0x0120
ERR_ADJUST = 0x0130
ERR_PRETRIGGERLEN = 0x0140
ERR_DIRMISMATCH = 0x0141
ERR_POSTEXCDSEGMENT = 0x0142
ERR_SEGMENTINMEM = 0x0143
ERR_MULTIPLEPW = 0x0144
ERR_NOCHANNELPWOR = 0x0145
ERR_ANDORMASKOVRLAP = 0x0146
ERR_ANDMASKEDGE = 0x0147
ERR_ORMASKLEVEL = 0x0148
ERR_EDGEPERMOD = 0x0149
ERR_DOLEVELMINDIFF = 0x014A
ERR_STARHUBENABLE = 0x014B
ERR_PATPWSMALLEDGE = 0x014C
ERR_XMODESETUP = 0x014D
ERR_AVRG_TDA = 0x014E
ERR_NOPCI = 0x0200
ERR_PCIVERSION = 0x0201
ERR_PCINOBOARDS = 0x0202
ERR_PCICHECKSUM = 0x0203
ERR_DMALOCKED = 0x0204
ERR_MEMALLOC = 0x0205
ERR_EEPROMLOAD = 0x0206
ERR_CARDNOSUPPORT = 0x0207
ERR_CONFIGACCESS = 0x0208
ERR_FIFOBUFOVERRUN = 0x0300
ERR_FIFOHWOVERRUN = 0x0301
ERR_FIFOFINISHED = 0x0302
ERR_FIFOSETUP = 0x0309
ERR_TIMESTAMP_SYNC = 0x0310
ERR_STARHUB = 0x0320
ERR_INTERNAL_ERROR = 0xFFFF


# Translation of error codes from spectrum documentation
error_translation: dict[int, str] = {
    ERR_OK: "Execution OK, no error.",
    ERR_INIT: "An error occurred when initializing the given card. Either the card has already been opened by another process or an hardware error occurred.",
    ERR_TYP: "Initialization only: The type of board is unknown. This is a critical error. Please check whether the board is correctly plugged in the slot and whether you have the latest driver version.",
    ERR_FNCNOTSUPPORTED: "This function is not supported by the hardware version.",
    ERR_BRDREMAP: "The board index re map table in the registry is wrong. Either delete this table or check it carefully for double values.",
    ERR_KERNELVERSION: "The version of the kernel driver is not matching the version of the DLL. Please do a complete re-installation of the hardware driver. This error normally only occurs if someone copies the driver library and the kernel driver manually.",
    ERR_HWDRVVERSION: "The hardware needs a newer driver version to run properly. Please install the driver that was delivered together with the card.",
    ERR_ADRRANGE: "One of the address ranges is disabled (fatal error), can only occur under Linux.",
    ERR_INVALIDHANDLE: "The used handle is not valid.",
    ERR_BOARDNOTFOUND: "A card with the given name has not been found.",
    ERR_BOARDINUSE: "A card with given name is already in use by another application.",
    ERR_EXPHW64BITADR: "Express hardware version not able to handle 64 bit addressing -> update needed.",
    ERR_FWVERSION: "Firmware versions of synchronized cards or for this driver do not match -> update needed.",
    ERR_SYNCPROTOCOL: " Synchronization protocol versions of synchronized cards do not match -> update needed",
    ERR_LASTERR: "Old error waiting to be read. Please read the full error information before proceeding. The driver is locked until the error information has been read.",
    ERR_BOARDINUSE: "Board is already used by another application. It is not possible to use one hardware from two different programs at the same time.",
    ERR_ABORT: "Abort of wait function. This return value just tells that the function has been aborted from another thread. The driver library is not locked if this error occurs.",
    ERR_BOARDLOCKED: "The card is already in access and therefore locked by another process. It is not possible to access one card through multiple processes. Only one process can access a specific card at the time.",
    ERR_DEVICE_MAPPING: "The device is mapped to an invalid device. The device mapping can be accessed via the Control Center.",
    ERR_NETWORKSETUP: "The network setup of a digitizerNETBOX has failed.",
    ERR_NETWORKTRANSFER: "The network data transfer from/to a digitizerNETBOX has failed.",
    ERR_NETWORKTIMEOUT: "A network timeout has occurred.",
    ERR_FWPOWERCYCLE: "Power cycle (PC off/on) is needed to update the card's firmware (a simple OS reboot is not sufficient !)",
    ERR_BUFFERSIZE: "The buffer size is not sufficient (too small).",
    ERR_RESTRICTEDACCESS: "The access to the card has been intentionally restricted.",
    ERR_INVALIDPARAM: "An invalid parameter has been used for a certain function.",
    ERR_TEMPERATURE: "The temperature of at least one of the card's sensors measures a temperature, that is too high for the hardware.",
    ERR_REG: "The register is not valid for this type of board.",
    ERR_VALUE: "The value for this register is not in a valid range. The allowed values and ranges are listed in the board specific documentation.",
    ERR_FEATURE: "Feature (option) is not installed on this board. It's not possible to access this feature if it's not installed.",
    ERR_SEQUENCE: "Command sequence is not allowed. Please check the manual carefully to see which command sequences are possible.",
    ERR_READABORT: "Data read is not allowed after aborting the data acquisition.",
    ERR_NOACCESS: "Access to this register is denied. This register is not accessible for users.",
    ERR_TIMEOUT: "A timeout occurred while waiting for an interrupt. This error does not lock the driver.",
    ERR_CALLTYPE: "The access to the register is only allowed with one 64 bit access but not with the multiplexed 32 bit (high and low double word) version.",
    ERR_EXCEEDSINT32: "The return value is int32 but the software register exceeds the 32 bit integer range. Use double int32 or int64 accesses instead, to get correct return values.",
    ERR_NOWRITEALLOWED: "The register that should be written is a read-only register. No write accesses are allowed.",
    ERR_SETUP: "The programmed setup for the card is not valid. The error register will show you which setting generates the error message. This error is returned if the card is started or the setup is written.",
    ERR_CLOCKNOTLOCKED: "Synchronization to external clock failed: no signal connected or signal not stable. Please check external clock or try to use a different sampling clock to make the PLL locking easier.",
    ERR_MEMINIT: "On-board memory initialization error. Power cycle the PC and try another PCIe slot (if possible). In case that the error persists, please contact Spectrum support for further assistance.",
    ERR_POWERSUPPLY: "On-board power supply error. Power cycle the PC and try another PCIe slot (if possible). In case that the error persists, please contact Spectrum support for further assistance.",
    ERR_ADCCOMMUNICATION: "Communication with ADC failed.P ower cycle the PC and try another PCIe slot (if possible). In case that the error persists, please contact Spectrum support for further assistance.",
    ERR_CHANNEL: "The channel number may not be accessed on the board: Either it is not a valid channel number or the channel is not accessible due to the current setup (e.g. Only channel 0 is accessible in interlace mode)", 
    ERR_NOTIFYSIZE: "The notify size of the last spcm_dwDefTransfer call is not valid. The notify size must be a multiple of the page size of 4096. For data transfer it may also be a fraction of 4k in the range of 16, 32, 64, 128, 256, 512, 1k or 2k. For ABA and timestamp the notify size can be 2k as a minimum.",
    ERR_RUNNING: "The board is still running, this function is not available now or this register is not accessible now.",
    ERR_ADJUST: "Automatic card calibration has reported an error. Please check the card inputs.",
    ERR_PRETRIGGERLEN: "The calculated pretrigger size (resulting from the user defined posttrigger values) exceeds the allowed limit.",
    ERR_DIRMISMATCH: "The direction of card and memory transfer mismatch. In normal operation mode it is not possible to transfer data from PC memory to card if the card is an acquisition card nor it is possible to transfer data from card to PC memory if the card is a generation card.",
    ERR_POSTEXCDSEGMENT: "The posttrigger value exceeds the programmed segment size in multiple recording/ABA mode. A delay of the multiple recording segments is only possible by using the delay trigger!",
    ERR_SEGMENTINMEM: "Memsize is not a multiple of segment size when using Multiple Recording/Replay or ABA mode. The programmed segment size must match the programmed memory size.",
    ERR_MULTIPLEPW: "Multiple pulsewidth counters used but card only supports one at the time.",
    ERR_NOCHANNELPWOR: "The channel pulsewidth on this card can't be used together with the OR conjunction. Please use the AND conjunction of the channel trigger sources.",
    ERR_ANDORMASKOVRLAP: "Trigger AND mask and OR mask overlap in at least one channel. Each trigger source can only be used either in the AND mask or in the OR mask, no source can be used for both.",
    ERR_ANDMASKEDGE: "One channel is activated for trigger detection in the AND mask but has been programmed to a trigger mode using an edge trigger. The AND mask can only work with level trigger modes.",
    ERR_ORMASKLEVEL: "One channel is activated for trigger detection in the OR mask but has been programmed to a trigger mode using a level trigger. The OR mask can only work together with edge trigger modes.",
    ERR_EDGEPERMOD: "This card is only capable to have one programmed trigger edge for each module that is installed. It is not possible to mix different trigger edges on one module.",
    ERR_DOLEVELMINDIFF: "The minimum difference between low output level and high output level is not reached.",
    ERR_STARHUBENABLE: "The card holding the star-hub must be enabled when doing synchronization.",
    ERR_PATPWSMALLEDGE: "Combination of pattern with pulsewidth smaller and edge is not allowed.",
    ERR_XMODESETUP: "The chosen setup for (SPCM_X0_MODE .. SPCM_X19_MODE) is not valid. See hardware manual for details.",
    ERR_AVRG_TDA: "Setup for Average LSA Mode not valid. Check Threshold and Replacement values for chosen AVRGMODE.",
    ERR_PCICHECKSUM: "The check sum of the card information has failed. This could be a critical hardware failure. Restart the system and check the connection of the card in the slot.",
    ERR_MEMALLOC: "Internal memory allocation failed. Please restart the system and be sure that there is enough free memory.",
    ERR_EEPROMLOAD: "Timeout occurred while loading information from the on-board EEProm. This could be a critical hardware failure. Please restart the system and check the PCI connector.",
    ERR_CARDNOSUPPORT: "The card that has been found in the system seems to be a valid Spectrum card of a type that is supported by the driver but the driver did not find this special type internally. Please get the latest driver from www.spectrum-instrumentation.com and install this one.",
    ERR_CONFIGACCESS: "Internal error occured during config writes or reads. Please contact Spectrum support for further assistance.",
    ERR_FIFOHWOVERRUN: "FIFO acquisition: Hardware buffer overrun in FIFO mode. The complete on-board memory has been filled with data and data wasn't transferred fast enough to PC memory.FIFO replay: Hardware buffer underrun in FIFO mode. The complete on-board memory has been replayed and data wasn't transferred fast enough from PC memory. If acquisition or replay throughput is lower than the theoretical bus throughput, check the application buffer setup.",
    ERR_FIFOFINISHED: "FIFO transfer has been finished, programmed data length has been transferred completely.",
    ERR_TIMESTAMP_SYNC: "Synchronization to timestamp reference clock failed. Please check the connection and the signal levels of the reference clock input.",
    ERR_STARHUB: "The auto routing function of the Star-Hub initialization has failed. Please check whether all cables are mounted correctly.",
    ERR_INTERNAL_ERROR: "Internal hardware error detected. Please check for driver and firmware update of the card.",
}
