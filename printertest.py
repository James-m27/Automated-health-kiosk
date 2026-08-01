import serial
import time

def manual_hex_test():
    port_name = "/dev/serial0" 
    baud_rate = 9600 

    try:
        print(f"Opening {port_name}...")
        with serial.Serial(port_name, baud_rate, timeout=2) as printer:
            
            # 1. Initialize Printer (ESC @ -> Hex: 1B 40)
            print("Sending Initialization (1B 40)...")
            printer.write(b'\x1b\x40')
            time.sleep(0.5) 
            5
            # 2. Lower Peak Current Demand (ESC 7 -> Hex: 1B 37 n1 n2 n3)
            # Default is \x09 \x50 \x02. 
            # We are lowering n1 (max heating dots) from \x09 to \x03 to drastically reduce the current spike.
            print("Reducing peak current demand (1B 37 03 50 02)...")
            printer.write(b'\x1b\x37\x03\x78\x02')
            time.sleep(0.2)
            
            # 3. Trigger Official Self-Test (DC2 T -> Hex: 12 54)
            print("Triggering internal self-test (12 54)...")
            printer.write(b'\x12\x54')
            
            printer.flush()
            print("Commands flushed to printer successfully!")
            
    except serial.SerialException as e:
        print(f"\n[!] Serial Error: {e}")
    except Exception as e:
        print(f"\n[!] Unexpected Error: {e}")

if __name__ == "__main__":
    manual_hex_test()
