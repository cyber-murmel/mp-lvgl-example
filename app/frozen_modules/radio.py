import asyncio
import lora
from machine import SPI, Pin
import random
from micropython import const
import random
import struct
import time

from lora_rd_settings import RECEIVER_ID, ACK_LENGTH, ACK_DELAY_MS, DEFAULT_LORA_CONFIG

SLEEP_BETWEEN_MS = (
    5000  # Main loop should sleep this long between sending data to the receiver
)

MAX_RETRIES = 4  # Retry each message this often if no ACK is received

# Initial retry is after this long. Increases by 1.25x each subsequent retry.
BASE_RETRY_TIMEOUT_MS = 1000

# Add random jitter to each retry period, up to this long. Useful to prevent two
# devices ending up in sync.
RETRY_JITTER_MS = 1500

# If reported RSSI value is lower than this, increase
# output power 1dBm
RSSI_WEAK_THRESH = -110

# If reported RSSI value is higher than this, decrease
# output power 1dBm
RSSI_STRONG_THRESH = -70

# IMPORTANT: Set this to the maximum output power in dBm that is permitted in
# your regulatory environment.
OUTPUT_MAX_DBM = 15
OUTPUT_MIN_DBM = -20

# Change _DEBUG to const(True) to get some additional debugging output
# about timing, RSSI, etc.
#
# For a lot more debugging detail, go to the modem driver and set _DEBUG there to const(True)
_DEBUG = const(False)

DEFAULT_RADIO_PARAMS = {
    "lora_cfg": DEFAULT_LORA_CONFIG,
    "spi": SPI("spi2", baudrate=2_000_000),
    "cs": Pin(("gpio1", 41 - 32)),
    "busy": Pin(("gpio1", 40 - 32)),
    "dio1": Pin(("gpio1", 39 - 32)),
    "reset": Pin(("gpio1", 42 - 32)),
    "dio3_tcxo_millivolts": 1800,
}


def get_modem():
    return lora.SX1262(**DEFAULT_RADIO_PARAMS)


def get_async_modem():
    return lora.AsyncSX1262(**DEFAULT_RADIO_PARAMS)


class AsyncRadio:
    def __init__(self, modem, device_id):
        self.modem = modem
        self.device_id = device_id
        self.counter = 0
        self.output_power = DEFAULT_LORA_CONFIG[
            "output_power"
        ]  # start with common settings power level
        self.rx_ack = None  # reuse the ack message object when we can
        self.mutex = asyncio.Lock()

        print(f"Sender initialized with ID 0x{device_id:04x}")
        random.seed(device_id)
        self.adjust_output_power(0)  # set the initial value within MIN/MAX

        modem.calibrate()

    async def recv_continuous(self, callback, timeout_ms=100):
        # Async task which receives packets from the AsyncModem recv_continuous()
        # iterator, checks if they are valid, and send back an ACK if needed.
        #
        # On each successful message, we await callback() to allow the application
        # to do something with the data. Callback args are sender_id (as int) and the bytes
        # of the message payload.

        last_counters = {}  # Track the last counter value we got from each sender ID
        ack_buffer = bytearray(ACK_LENGTH)  # reuse the same buffer for ACK packets
        skipped_packets = 0  # Counter of skipped packets

        while True:
            await self.mutex.acquire()

            rx = await self.modem.recv(timeout_ms)
            if not rx:
                self.mutex.release()
                continue
            # Filter 'rx' packet to determine if it's valid for our application
            if len(rx) < 7:  # 4 byte header plus 1 byte checksum
                print("Invalid packet length")
                self.mutex.release()
                continue

            sender_id, receiver_id, counter, data_len = struct.unpack("<HHBB", rx)
            csum = rx[-1]

            if len(rx) != data_len + 7:
                print("Invalid length in payload header")
                self.mutex.release()
                continue

            calc_csum = sum(b for b in rx[:-1]) & 0xFF
            if csum != calc_csum:
                print(f"Invalid checksum. calc={calc_csum:#x} received={csum:#x}")
                self.mutex.release()
                continue

            # Packet is valid!

            if not receiver_id in (0, self.device_id):
                # Packet is not for us
                self.mutex.release()
                continue

            if _DEBUG:
                print(
                    f"RX {data_len} byte message RSSI {rx.rssi} at timestamp {rx.ticks_ms}"
                )

            # Send the ACK
            struct.pack_into(
                "<HHBBb", ack_buffer, 0, RECEIVER_ID, sender_id, counter, csum, rx.rssi
            )

            if receiver_id != 0:
                # Time send to start as close to ACK_DELAY_MS after message was received as possible
                tx_at_ms = time.ticks_add(rx.ticks_ms, ACK_DELAY_MS)
                tx_done = await self.modem.send(ack_buffer, tx_at_ms=tx_at_ms)

                if _DEBUG:
                    tx_time = time.ticks_diff(tx_done, tx_at_ms)
                    expected = self.modem.get_time_on_air_us(ACK_LENGTH) / 1000
                    print(
                        f"ACK TX {tx_at_ms}ms -> {tx_done}ms took {tx_time}ms expected {expected}"
                    )

            # Check if the data we received is fresh or stale
            if sender_id not in last_counters:
                print(f"New device id {sender_id:#x}")
            elif last_counters[sender_id] == counter:
                print(f"Duplicate packet received from 0x{sender_id:04x}")
                self.mutex.release()
                continue
            elif counter != 1:
                # If the counter from this sender has gone up by more than 1 since
                # last time we got a packet, we know there is some packet loss.
                #
                # (ignore the case where the new counter is 1, as this probably
                # means a reset.)
                delta = (counter - 1 - last_counters[sender_id]) & 0xFF
                if delta:
                    print(f"Skipped/lost {delta} packets from {sender_id:#x}")
                    skipped_packets += delta

            last_counters[sender_id] = counter

            self.mutex.release()
            await callback(sender_id, rx[6:-1])

    async def send(self, data, receiver_id=0, adjust_output_power=True):
        await self.mutex.acquire()

        # Send a packet of sensor data to the receiver reliably.
        #
        # Returns True if data was successfully sent and ACKed, False otherwise.
        #
        # If adjust_output_power==True then increase or decrease output power
        # according to the RSSI reported in the ACK packet.
        self.counter = (self.counter + 1) & 0xFF

        # Prepare the simple payload with header and checksum
        # See README for a summary of the simple data message format
        payload = bytearray(len(data) + 7)
        struct.pack_into(
            "<HHBB", payload, 0, self.device_id, receiver_id, self.counter, len(data)
        )
        payload[6:-1] = data
        payload[-1] = sum(b for b in payload) & 0xFF

        # Calculate the time on air (in milliseconds) for an ACK packet
        ack_packet_ms = self.modem.get_time_on_air_us(ACK_LENGTH) // 1000 + 1
        timeout = BASE_RETRY_TIMEOUT_MS

        print(f"Sending {len(payload)} bytes")

        if receiver_id == 0:
            await self.modem.send(payload)
            self.mutex.release()
            return True
        else:
            # Send the payload, until we receive an acknowledgement or run out of retries
            for _ in range(MAX_RETRIES):
                sent_at = await self.modem.send(payload)

                # We expect the receiver of a valid message to start sending the ACK
                # approximately ACK_DELAY_MS after receiving the message (to allow
                # the sender time to reconfigure the modem.)
                #
                # We start receiving as soon as we can, but allow up to
                # ACK_DELAY_MS*2 of total timing leeway - plus the time on air for
                # the packet itself
                maybe_ack = await self.modem.recv(
                    ack_packet_ms + ACK_DELAY_MS * 2, rx_packet=self.rx_ack
                )

                # Check if the packet we received is a valid ACK
                rssi = self._ack_is_valid(maybe_ack, payload[-1])

                if rssi is not None:  # ACK is valid
                    self.rx_ack == maybe_ack

                    delta = time.ticks_diff(maybe_ack.ticks_ms, sent_at)
                    print(
                        f"ACKed with RSSI {rssi}, {delta}ms after sent "
                        + f"(skew {delta - ACK_DELAY_MS - ack_packet_ms}ms)"
                    )

                    if adjust_output_power:
                        if rssi > RSSI_STRONG_THRESH:
                            self.adjust_output_power(-1)
                        elif rssi < RSSI_WEAK_THRESH:
                            self.adjust_output_power(1)
                    self.mutex.release()
                    return True

                # Otherwise, prepare to sleep briefly and then retry
                next_try_at = time.ticks_add(sent_at, timeout)
                sleep_time = time.ticks_diff(
                    next_try_at, time.ticks_ms()
                ) + random.randrange(RETRY_JITTER_MS)
                if sleep_time > 0:
                    self.modem.sleep()
                    await asyncio.sleep_ms(sleep_time)

                # add 25% timeout for next iteration
                timeout = (timeout * 5) // 4

            print(f"Failed, no ACK after {MAX_RETRIES} retries.")
            if adjust_output_power:
                self.adjust_output_power(2)
            self.modem.calibrate_image()  # try and improve the RX sensitivity for next time
            self.mutex.release()
            return False

    def _ack_is_valid(self, maybe_ack, csum):
        # Private function to verify if the RxPacket held in 'maybe_ack' is a valid ACK for the
        # current device_id and counter value, and provided csum value.
        #
        # If it is, returns the reported RSSI value from the packet.
        # If not, returns None
        if (not maybe_ack) or len(maybe_ack) != ACK_LENGTH:
            return None

        base_id, ack_id, ack_counter, ack_csum, rssi = struct.unpack(
            "<HHBBb", maybe_ack
        )

        if (
            base_id != RECEIVER_ID
            or ack_id != self.device_id
            or ack_counter != self.counter
            or ack_csum != csum
        ):
            return None

        return rssi

    def adjust_output_power(self, delta_dbm):
        # Adjust the modem output power by +/-delta_dbm, max of OUTPUT_MAX_DBM
        #
        # (note: the radio may also apply its own power limit internally.)
        new = max(min(self.output_power + delta_dbm, OUTPUT_MAX_DBM), OUTPUT_MIN_DBM)
        self.output_power = new
        print(f"New output_power {new}/{OUTPUT_MAX_DBM} (delta {delta_dbm})")
        self.modem.configure({"output_power": self.output_power})
