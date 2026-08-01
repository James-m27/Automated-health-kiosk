# Smart Health Kiosk - Automated Vital Sign Screening

This repository contains the firmware and graphical user interface for a Raspberry Pi-based Smart Health Kiosk. The system provides an automated, self-service platform for capturing preliminary human vital signs, including core body temperature, heart rate, blood oxygen saturation (SpO2), and blood pressure.

## System Architecture

The software architecture is built entirely in Python 3 and deployed on a Raspberry Pi 3 running a Linux-based OS. It utilizes an asynchronous threading model to prevent UI freezing during complex hardware polling (such as oscillometric NIBP calculations) and features an isolated hardware API to manage multiple communication protocols (I2C, UART, and direct GPIO).

## File Overview

* **`Main.py`**: The primary executable. Contains the `customtkinter` Graphical User Interface, state machine logic for the guided screening steps, and the background thread manager.
* **`hardware_api.py`**: The custom hardware abstraction layer. Handles all direct sensor communication, fallback simulation logic for fault tolerance, and the Digital Signal Processing (DSP) pipeline for the blood pressure module.
* **`bp_debug.py`**: A standalone diagnostic script used for testing the serial data stream and calibrating the NIBP DSP algorithms.
* **`printertest.py`**: A diagnostic script for testing the 9600 baud UART connection to the ESC/POS thermal printer.
* **`max30102.py`**: I2C hardware driver for the MAX30102 pulse oximeter and heart rate sensor. *(See Acknowledgements)*
* **`hrcalc.py`**: Algorithmic processor for calculating SpO2 and Heart Rate from raw IR/Red light absorption data. *(See Acknowledgements)*
* **`bp_input.ino`**: C++ firmware for the Arduino Nano. Handles the strict 100Hz analog-to-digital sampling of the NIBP pressure transducer and streams the raw data via USB serial (115200 baud) to the Raspberry Pi for signal processing.

## Hardware Dependencies

This firmware is specifically written to interface with the following hardware via the `hardware_api.py` wrapper:
*   **Raspberry Pi 3** (Central Compute)
*   **MAX30102** (Heart Rate & SpO2 - I2C)
*   **MLX90614** (Non-Contact Infrared Temperature - I2C)
*   **Custom NIBP Module** (Oscillometric Blood Pressure - UART via Arduino Nano)
*   **ESC/POS Thermal Printer** (Receipt Output - UART)
*   **7-Inch Touchscreen Display** (User Interface)

## Acknowledgements & External Libraries

The `max30102.py` and `hrcalc.py` files utilized in this project are open-source drivers originally authored by **doug-burrell**. They have been included in this repository to ensure out-of-the-box functionality of the pulse oximetry hardware. The original repository and documentation for these specific files can be found here: [https://github.com/doug-burrell/max30102](https://github.com/doug-burrell/max30102)
