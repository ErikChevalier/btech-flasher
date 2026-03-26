# BTECH BF-F8HP Pro Firmware Flasher

A native Linux tool for flashing `.kdhx` firmware files to the BTECH BF-F8HP Pro handheld radio, eliminating the need for Wine or a Windows VM.

## Status

**Untested** — this tool was developed against a unit with a faulty programming cable (broken RX line). The protocol implementation has been verified via dry-run packet construction and CRC validation, but has not yet been tested against a live radio with a working cable. Use at your own risk.

## Requirements

- Python 3.10+
- [pyserial](https://pypi.org/project/pyserial/) (`pip install pyserial`)
- A BTECH PC03 FTDI programming cable (or compatible K1 2-pin Kenwood cable)
- Your user must be in the `dialout` group for serial port access:
  ```
  sudo usermod -aG dialout $USER
  ```

## Usage

### Flash firmware

1. Download the firmware bundle from [baofengtech.com](https://baofengtech.com) (includes the `.kdhx` file)
2. Put the radio in bootloader mode:
   - Power off the radio
   - Hold **SK1** (top side button) + **SK2** (bottom side button) — not PTT
   - While holding both, turn the power/volume knob to power on
   - Screen stays blank, green Rx LED lights up
3. Run:
   ```
   python3 flash_firmware.py /dev/ttyUSB0 BTECH_V0.53_260116.kdhx
   ```

### Dry run (verify packets without a radio)

```
python3 flash_firmware.py --dry-run none BTECH_V0.53_260116.kdhx
```

### Diagnostics (test serial communication)

```
python3 flash_firmware.py --diag /dev/ttyUSB0
```

## Protocol

The BTECH bootloader uses a simple packetized serial protocol at 115200 baud (8N1).

### Packet format

```
[0xAA][cmd][seed][lenH][lenL][data...][crcH][crcL][0xEF]
```

- **0xAA** — header
- **cmd** — command byte
- **seed** — sequence number / argument
- **lenH:lenL** — data length (big-endian 16-bit)
- **data** — payload (0 to 65535 bytes)
- **crcH:crcL** — CRC-16/CCITT over cmd+seed+len+data (poly 0x1021, init 0x0000)
- **0xEF** — trailer

### Manual download sequence

When the radio is already in bootloader mode (user held SK1+SK2 during power on):

| Step | Command | Byte | Payload |
|------|---------|------|---------|
| 1 | Handshake | 0x01 | `"BOOTLOADER"` (10 bytes) |
| 2 | Announce chunks | 0x04 | 1 byte: total number of 1024-byte chunks |
| 3 | Send data (repeat) | 0x03 | 1024 bytes of firmware per chunk |
| 4 | End | 0x45 | (none) |

Each command expects an ACK response: same packet format with `cmdArgs = 0x06`.

### Error codes

| Code | Meaning |
|------|---------|
| 0xE1 | Handshake code error (fatal) |
| 0xE2 | Data verification error (retryable, up to 5 attempts) |
| 0xE3 | Incorrect address error (fatal) |
| 0xE4 | Flash write error (fatal) |
| 0xE5 | Command error (fatal) |

## License

MIT
