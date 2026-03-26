#!/usr/bin/env python3
"""
GUI frontend for the BTECH BF-F8HP Pro firmware flasher.
"""

import threading
import glob
import wx
import flash_firmware as fw
import serial


class FlasherFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="BTECH BF-F8HP Pro Firmware Flasher", size=(500, 380))
        self.SetMinSize((500, 380))

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Firmware file
        file_sizer = wx.BoxSizer(wx.HORIZONTAL)
        file_sizer.Add(wx.StaticText(panel, label="Firmware:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.file_path = wx.TextCtrl(panel)
        file_sizer.Add(self.file_path, 1, wx.EXPAND | wx.RIGHT, 5)
        browse_btn = wx.Button(panel, label="Browse...")
        browse_btn.Bind(wx.EVT_BUTTON, self.on_browse)
        file_sizer.Add(browse_btn, 0)
        sizer.Add(file_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # COM port
        port_sizer = wx.BoxSizer(wx.HORIZONTAL)
        port_sizer.Add(wx.StaticText(panel, label="Port:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.port_combo = wx.ComboBox(panel, style=wx.CB_DROPDOWN)
        self.refresh_ports()
        port_sizer.Add(self.port_combo, 1, wx.EXPAND | wx.RIGHT, 5)
        refresh_btn = wx.Button(panel, label="Refresh")
        refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh)
        port_sizer.Add(refresh_btn, 0)
        sizer.Add(port_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        sizer.AddSpacer(10)

        # Progress bar
        self.progress = wx.Gauge(panel, range=100)
        sizer.Add(self.progress, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        sizer.AddSpacer(5)

        # Status log
        self.log = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        self.log.SetFont(wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        sizer.Add(self.log, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        sizer.AddSpacer(10)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.flash_btn = wx.Button(panel, label="Flash Firmware")
        self.flash_btn.Bind(wx.EVT_BUTTON, self.on_flash)
        btn_sizer.Add(self.flash_btn, 0, wx.RIGHT, 10)
        self.diag_btn = wx.Button(panel, label="Run Diagnostics")
        self.diag_btn.Bind(wx.EVT_BUTTON, self.on_diag)
        btn_sizer.Add(self.diag_btn, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        panel.SetSizer(sizer)
        self.Centre()

    def refresh_ports(self):
        ports = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
        self.port_combo.Set(ports)
        if ports:
            self.port_combo.SetSelection(0)

    def on_refresh(self, event):
        self.refresh_ports()

    def on_browse(self, event):
        dlg = wx.FileDialog(self, "Select firmware file", wildcard="Firmware files (*.kdhx)|*.kdhx|All files (*)|*",
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.file_path.SetValue(dlg.GetPath())
        dlg.Destroy()

    def log_msg(self, msg):
        wx.CallAfter(self.log.AppendText, msg + "\n")

    def set_progress(self, pct):
        wx.CallAfter(self.progress.SetValue, int(pct))

    def set_buttons(self, enabled):
        wx.CallAfter(self.flash_btn.Enable, enabled)
        wx.CallAfter(self.diag_btn.Enable, enabled)

    def on_flash(self, event):
        port = self.port_combo.GetValue()
        firmware_path = self.file_path.GetValue()

        if not port:
            wx.MessageBox("Select a serial port.", "Error", wx.OK | wx.ICON_ERROR)
            return
        if not firmware_path:
            wx.MessageBox("Select a firmware file.", "Error", wx.OK | wx.ICON_ERROR)
            return

        dlg = wx.MessageDialog(self,
            "Make sure the radio is in bootloader mode:\n\n"
            "1. Power off the radio\n"
            "2. Hold SK1 + SK2 (top and bottom side buttons)\n"
            "3. Turn power knob to turn on\n"
            "4. Screen stays blank, green LED lights up\n\n"
            "Do not disconnect the radio or cable during the update!\n\n"
            "Ready to flash?",
            "Confirm", wx.YES_NO | wx.ICON_WARNING)
        if dlg.ShowModal() != wx.ID_YES:
            dlg.Destroy()
            return
        dlg.Destroy()

        self.log.Clear()
        self.progress.SetValue(0)
        self.set_buttons(False)
        threading.Thread(target=self._flash_thread, args=(port, firmware_path), daemon=True).start()

    def _flash_thread(self, port, firmware_path):
        try:
            with open(firmware_path, "rb") as f:
                firmware = f.read()

            import math
            fw_size = len(firmware)
            total_chunks = math.ceil(fw_size / 1024)
            self.log_msg(f"Firmware: {firmware_path}")
            self.log_msg(f"Size: {fw_size} bytes, {total_chunks} chunks")
            self.log_msg(f"Port: {port}")
            self.log_msg("")

            ser = serial.Serial(
                port=port, baudrate=115200, bytesize=8,
                parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                timeout=2.0, write_timeout=2.0
            )
            ser.dtr = True
            ser.rts = True
            import time
            time.sleep(0.1)
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            self.log_msg("[1/3] Bootloader handshake...")
            fw.send_command(ser, fw.CMD_HANDSHAKE, 0, b"BOOTLOADER")
            self.log_msg("  OK")

            self.log_msg(f"[2/3] Sending firmware ({total_chunks} chunks)...")
            fw.send_command(ser, fw.CMD_UPDATE_DATA_PACKAGES, 0, bytes([total_chunks]))

            for i in range(total_chunks):
                offset = i * 1024
                chunk = firmware[offset:offset + 1024]
                fw.send_command(ser, fw.CMD_UPDATE, i & 0xFF, chunk)
                pct = ((i + 1) / total_chunks) * 100
                self.set_progress(pct)
                if (i + 1) % 10 == 0 or i == total_chunks - 1:
                    self.log_msg(f"  {pct:.0f}% ({i + 1}/{total_chunks})")

            self.log_msg("[3/3] Finalizing...")
            fw.send_command(ser, fw.CMD_UPDATE_END, 0)
            ser.close()
            self.log_msg("  OK")
            self.log_msg("")
            self.log_msg("Firmware update complete!")
            self.log_msg("Power cycle the radio and check Menu > Radio Info.")
            wx.CallAfter(wx.MessageBox, "Firmware update complete!", "Success", wx.OK | wx.ICON_INFORMATION)

        except Exception as e:
            self.log_msg(f"\nERROR: {e}")
            self.log_msg("Radio may need to be power cycled and put back in bootloader mode.")
            wx.CallAfter(wx.MessageBox, f"Flash failed:\n{e}", "Error", wx.OK | wx.ICON_ERROR)
        finally:
            self.set_buttons(True)

    def on_diag(self, event):
        port = self.port_combo.GetValue()
        if not port:
            wx.MessageBox("Select a serial port.", "Error", wx.OK | wx.ICON_ERROR)
            return

        self.log.Clear()
        self.progress.SetValue(0)
        self.set_buttons(False)
        threading.Thread(target=self._diag_thread, args=(port,), daemon=True).start()

    def _diag_thread(self, port):
        try:
            import time

            self.log_msg(f"Running diagnostics on {port}...")
            self.log_msg("")

            ser = serial.Serial(
                port=port, baudrate=115200, bytesize=8,
                parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                timeout=1.0
            )
            ser.dtr = True
            ser.rts = True
            time.sleep(0.1)

            self.log_msg(f"  Baud: {ser.baudrate}, DTR: {ser.dtr}, RTS: {ser.rts}")
            self.log_msg(f"  CTS: {ser.cts}, DSR: {ser.dsr}")
            self.log_msg("")

            self.log_msg("Sending CMD_HANDSHAKE...")
            packet = fw.build_packet(fw.CMD_HANDSHAKE, 0, b"BOOTLOADER")
            self.log_msg(f"  TX: {packet.hex()}")
            ser.reset_input_buffer()
            ser.write(packet)
            ser.flush()

            self.set_progress(50)
            time.sleep(1.0)
            avail = ser.in_waiting
            if avail:
                data = ser.read(avail)
                self.log_msg(f"  RX ({avail} bytes): {data.hex()}")
                self.log_msg("")
                self.log_msg("Radio is responding! Flash should work.")
            else:
                self.log_msg("  RX: no data")
                self.log_msg("")
                self.log_msg("Radio did not respond.")
                self.log_msg("Check: cable, bootloader mode, serial port.")

            ser.close()
            self.set_progress(100)

        except Exception as e:
            self.log_msg(f"\nERROR: {e}")
        finally:
            self.set_buttons(True)


def main():
    app = wx.App()
    frame = FlasherFrame()
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()
