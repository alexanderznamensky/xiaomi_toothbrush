"""Parser for Xiaomi MiBeacon toothbrush data.

Supported device: Xiaomi/Soocare SMI-T501 (soocare.toothbrush.1501)
Product ID: 0x1FF3

This device uses encrypted MiBeacon packets during brushing.
The encryption format appears to be non-standard and differs from
the standard MiBeacon v4/v5 format used by other Xiaomi devices.

Current implementation detects brushing state based on packet type:
- Non-encrypted short packet (11 bytes, FC=0x5910) = IDLE
- Encrypted long packet (22 bytes, FC=0x5958) = BRUSHING

Duration is calculated by measuring time between state changes.

TODO: Decryption not yet implemented. The bindkey is correct but
the encryption format needs further reverse engineering.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)


@dataclass
class XiaomiToothbrushData:
    """Parsed data from Xiaomi toothbrush."""

    is_brushing: bool = False
    battery_percent: int | None = None
    brushing_duration: int | None = None  # seconds
    raw_data: str = ""


class XiaomiToothbrushParser:
    """Parser for Xiaomi SMI-T501 toothbrush BLE advertisements."""

    # MiBeacon frame control flags
    FC_ENCRYPTED = 0x08
    FC_MAC_INCLUDE = 0x10

    def __init__(self, bindkey: str | None = None) -> None:
        """Initialize the parser.
        
        Args:
            bindkey: 32-character hex string (16 bytes) encryption key.
                     Currently not used as decryption is not implemented.
        """
        self._bindkey = bytes.fromhex(bindkey) if bindkey else None

    def parse_advertisement(
        self, service_data: dict[str, bytes | str]
    ) -> XiaomiToothbrushData | None:
        """Parse BLE advertisement data from Xiaomi toothbrush."""
        xiaomi_uuid = "0000fe95-0000-1000-8000-00805f9b34fb"

        if xiaomi_uuid in service_data:
            raw_data = service_data[xiaomi_uuid]
        else:
            for uuid, data in service_data.items():
                raw_data = data
                break
            else:
                return None

        if isinstance(raw_data, str):
            try:
                data = bytes.fromhex(raw_data)
            except ValueError:
                return None
        else:
            data = raw_data

        return self._parse_mibeacon(data)

    def _parse_mibeacon(self, data: bytes) -> XiaomiToothbrushData | None:
        """Parse MiBeacon frame.
        
        SMI-T501 packet structure:
        
        IDLE packet (11 bytes):
        [0-1]  Frame Control: 0x5910 (not encrypted)
        [2-3]  Product ID: 0x1FF3
        [4]    Frame Counter
        [5-10] MAC address
        
        BRUSHING packet (22 bytes):
        [0-1]  Frame Control: 0x5958 (encrypted)
        [2-3]  Product ID: 0x1FF3
        [4]    Frame Counter
        [5-10] MAC address
        [11-14] Encrypted data (4 bytes)
        [15-17] Nonce extension / Object ID (060000)
        [18-21] MIC (4 bytes)
        """
        if len(data) < 5:
            return None

        result = XiaomiToothbrushData(raw_data=data.hex())

        frame_control = int.from_bytes(data[0:2], byteorder="little")
        is_encrypted = bool(frame_control & self.FC_ENCRYPTED)

        # Determine brushing state based on packet type
        if is_encrypted and len(data) > 15:
            result.is_brushing = True
        else:
            result.is_brushing = False

        return result
