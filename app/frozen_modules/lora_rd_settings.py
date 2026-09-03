DEFAULT_LORA_CONFIG = {
    "freq_khz": 869525,
    "sf": 10,
    "bw": "62.5",  # kHz
    "preamble_len": 12,
    "crc_en": True,
    "coding_rate": 8,
    "output_power": 10,
    "implicit_header": False,
    "syncword": 0x12,
}

# Single receiver has a fixed 16-bit ID value (senders each have a unique value).
RECEIVER_ID = 0xFFFF

# Length of an ACK message in bytes.
ACK_LENGTH = 7

# Send the ACK this many milliseconds after receiving a valid message
#
# This can be quite a bit lower (25ms or so) if wakeup times are short
# and _DEBUG is turned off on the modems (logging to UART delays everything).
ACK_DELAY_MS = 100
