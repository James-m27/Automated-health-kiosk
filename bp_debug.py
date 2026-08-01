import time
import serial
import numpy as np
from hardware_api import BloodPressureMonitor

def run_interactive_debugger():
    print("========================================")
    print("   BLOOD PRESSURE DIAGNOSTIC TERMINAL   ")
    print("========================================")
    
    # 1. Initialize the hardware API (This sets up the Pi's GPIO)
    try:
        hw_bp = BloodPressureMonitor()
        print("[System] Hardware API loaded. GPIO initialized.")
    except Exception as e:
        print(f"[Error] Failed to load hardware API: {e}")
        return

    duration = 75  # Seconds to record
    
    # 2. Wait for user input
    print("\nReady. Place the cuff on your arm and sit completely still.")
    input("Press [ENTER] to trigger the pump and start recording...")
    
    print("\n[Hardware] Firing pump trigger...")
    hw_bp.trigger_pump()
    
    raw_buffer = []
    start_time = time.time()
    
    # 3. Monitor the live stream
    try:
        with serial.Serial(hw_bp.port, hw_bp.baudrate, timeout=1) as ser:
            ser.reset_input_buffer()
            print(f"[Serial] Listening on {hw_bp.port} at {hw_bp.baudrate} baud...")
            print("----------------------------------------")
            
            while time.time() - start_time < duration:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('ascii', errors='ignore').strip()
                    if line.isdigit():
                        val = int(line)
                        raw_buffer.append(val)
                        
                        # Print a sample every ~0.25 seconds so you can watch the curve visually
                        if len(raw_buffer) % 25 == 0:
                            elapsed = time.time() - start_time
                            # Create a simple visual bar graph in the terminal
                            bar = "|" + "=" * int(val / 10)
                            print(f"{elapsed:04.1f}s | ADC: {val:03d} {bar}")
                            
    except Exception as e:
        print(f"\n[Error] Serial connection failed: {e}")
        return

    print("----------------------------------------")
    print("[System] Data collection complete. Crunching math...\n")
    
    # 4. Save raw data just in case
    raw_data = np.array(raw_buffer)
    np.savetxt("debug_raw_data.csv", raw_data, delimiter=",")
    
    # 5. Execute the Robust Processing Logic
    if len(raw_data) < 500:
        print("[Result] FAILED: Not enough data collected (Check serial wiring).")
        return

    active_data = np.array([x for x in raw_data if x > 50])
    
    if len(active_data) < 500:
        print("[Result] FAILED: Op-amp never woke up (Data stayed below 50).")
        return
        
    adc_zero = np.median(active_data[:500])
    peak_inflation_index = np.argmax(active_data)
    post_peak_data = active_data[peak_inflation_index:]
    
    threshold = adc_zero + 20
    end_indices = np.where(post_peak_data < threshold)[0]
    
    if len(end_indices) > 0:
        dump_index = end_indices[0]
        slice_end = max(0, dump_index - 50)
        deflation_data = post_peak_data[:slice_end]
        print(f"[Math] Dump valve detected. Sliced array at index {dump_index}.")
    else:
        deflation_data = post_peak_data[:-400]
        print("[Math] Dump valve not detected. Applied hard 400-sample tail slice.")
        
    if len(deflation_data) < 200:
        print("[Result] FAILED: Deflation phase too short to analyze.")
        return
        
    pressure_array = (deflation_data - adc_zero) * 0.56 
    
    try:
        # Utilize the processor from the hardware_api
        sys, dia = hw_bp.processor.calculate_bp(deflation_data, pressure_array)
        
        print("========================================")
        print(f"  FINAL BLOOD PRESSURE: {sys} / {dia} mmHg")
        print("========================================")
        print(f"  Calculated Baseline (0 mmHg): {adc_zero:.1f} ADC")
        print(f"  Peak Inflation: {np.max(active_data)} ADC")
        print(f"  Deflation Samples Analyzed: {len(deflation_data)}")
        print("========================================")
        print("Raw array saved to 'debug_raw_data.csv' for analysis.")
        
    except Exception as e:
        print(f"[Result] SciPy Processing crashed: {e}")

if __name__ == "__main__":
    run_interactive_debugger()
