import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import serial.tools.list_ports
import threading

class PicoSerialGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Pico Serial Terminal")
        self.serial_port = None
        self.alive = False

        self.setup_widgets()

    def setup_widgets(self):
        # Port selection
        port_frame = tk.Frame(self.root)
        port_frame.pack(pady=5)

        self.port_var = tk.StringVar()
        self.port_dropdown = ttk.Combobox(port_frame, textvariable=self.port_var, width=30)
        self.refresh_ports()
        self.port_dropdown.pack(side=tk.LEFT)

        connect_btn = ttk.Button(port_frame, text="Connect", command=self.connect_serial)
        connect_btn.pack(side=tk.LEFT, padx=5)

        disconnect_btn = ttk.Button(port_frame, text="Disconnect", command=self.disconnect_serial)
        disconnect_btn.pack(side=tk.LEFT, padx=5)

        # Serial output area
        self.output_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, width=80, height=20, state=tk.DISABLED)
        self.output_area.pack(padx=10, pady=10)

        # Input area
        input_frame = tk.Frame(self.root)
        input_frame.pack(pady=5)

        self.input_var = tk.StringVar()
        self.input_entry = tk.Entry(input_frame, textvariable=self.input_var, width=60)
        self.input_entry.pack(side=tk.LEFT, padx=5)
        self.input_entry.bind("<Return>", self.send_command)

        send_btn = ttk.Button(input_frame, text="Send", command=self.send_command)
        send_btn.pack(side=tk.LEFT)

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]
        self.port_dropdown['values'] = port_list
        if port_list:
            self.port_var.set(port_list[0])

    def connect_serial(self):
        port = self.port_var.get()
        if not port:
            messagebox.showerror("Error", "No port selected")
            return

        try:
            self.serial_port = serial.Serial(port, 115200, timeout=0.1)
            self.alive = True
            self.output("Connected to {}".format(port))
            self.thread = threading.Thread(target=self.read_serial, daemon=True)
            self.thread.start()
        except serial.SerialException as e:
            messagebox.showerror("Connection Error", str(e))

    def disconnect_serial(self):
        self.alive = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.output("Disconnected")

    def read_serial(self):
        while self.alive:
            try:
                if self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode(errors='ignore').strip()
                    if line:
                        self.root.after(0, self.output, line)
            except Exception as e:
                self.output(f"[Error] {e}")
                break

    def send_command(self, event=None):
        if self.serial_port and self.serial_port.is_open:
            cmd = self.input_var.get()
            self.serial_port.write((cmd + '\n').encode())
            self.input_var.set("")  # Clear input
        else:
            messagebox.showwarning("Warning", "Not connected to any port")

    def output(self, text):
        self.output_area.configure(state=tk.NORMAL)
        self.output_area.insert(tk.END, text + '\n')
        self.output_area.see(tk.END)
        self.output_area.configure(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = PicoSerialGUI(root)
    root.mainloop()
