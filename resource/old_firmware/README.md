# M5Stack StampS3 Zirconia Sensor Monitor & Pump Controller

This project turns an M5Stack StampS3 into a wireless monitor for a zirconia oxygen sensor and a controller for a pump, using Bluetooth Low Energy (BLE). It is designed to be robust, with a state machine, non-blocking error handling, and a structured logging system.

## Features

- **Multi-Sensor Measurement**:
    - **Internal ADC**: Measures a voltage from a 1/4 voltage divider.
    - **External I2C ADC (ADS1115)**:
        - Reads Zirconia sensor Ip voltage (Ain0).
        - Reads sensor heater RTD resistance (Ain1).
        - Reads Zirconia sensor output voltage (Ain2).
- **State-based Pump Control**:
    - Manages a pump driver connected to a GPIO pin.
    - Control is state-based (`ON`/`OFF`) rather than a simple toggle.
    - Can be controlled remotely via BLE or physically by pressing the built-in button (`BtnA`).
- **Robust Operation**:
    - **State Machine**: The firmware operates on a state machine (`SystemStateFlags`) that tracks pump status, BLE connection, and ADC faults.
    - **I2C Decoupling**: Handles I2C connection errors gracefully. If the external ADC is disconnected at startup, the system remains operational and attempts to recover.
    - **Interrupt-driven Button**: `BtnA` uses a hardware interrupt to ensure user input is responsive even if the main loop is temporarily blocked.
- **Advanced Logging**:
    - A dedicated logger provides structured, color-coded serial output with timestamps, log levels, and module names for easy debugging.
- **Enhanced Status Indicator**:
    - The on-board RGB LED provides detailed visual feedback on the system's operational status, including voltage levels and BLE connectivity. See the [Status LED Indicator](#status-led-indicator) section for details.

## Hardware & Software Components

### Hardware
- **Microcontroller**: M5Stack StampS3 / S3A
- **External ADC**: Adafruit ADS1115
- **Sensors**: Zirconia Oxygen Sensor with heater
- **Actuator**: Pump Driver

### Software
- **Framework**: Arduino
- **Project Environment**: PlatformIO
- **Key Libraries**:
    - `M5Unified`: Core library for M5Stack devices.
    - `Adafruit_ADS1X15`: For communication with the external ADC.
    - `FastLED`: For controlling the on-board RGB LED.
    - `ESP32 BLE`: For all Bluetooth Low Energy functionalities.

## BLE Communication Specification

### Control Service (`0000180F-...`)
- **Pump Control Characteristic (`00002A19-...`)**
    - **Properties**: `WRITE`
    - **Usage**: Write a single byte to control the pump.
        - `0x55`: Turns the pump ON.
        - `0xAA`: Turns the pump OFF.

### Monitoring Service (`0000181A-...`)
- **Sensor Data Characteristic (`00002A58-...`)**
    - **Properties**: `NOTIFY`
    - **Usage**: Periodically notifies a 20-byte data packet containing the current sensor and system status.
    - **Packet Structure**:
        - **Bytes 0-3**: `internalVoltage` (float)
        - **Bytes 4-7**: `zirconiaIpVoltage` (float)
        - **Bytes 8-11**: `heaterRtdResistance` (float)
        - **Bytes 12-15**: `zirconiaOutputVoltage` (float)
        - **Bytes 16-19**: `systemState` (uint32_t, bitmask of `SystemStateFlags`)

## System States (`SystemStateFlags`)

The firmware's behavior is governed by a bitmask of state flags.
- `STATE_PUMP_ON` (Bit 0): The pump is currently active.
- `STATE_BLE_CONNECTED` (Bit 1): A BLE client is connected.
- `STATE_FAULT_ADC` (Bit 2): A fault has been detected with the external ADC.

## Status LED Indicator

The system status is indicated by the on-board RGB LED with the following priority:

| Priority | State | Trigger Condition | LED Display |
| :--- | :--- | :--- | :--- |
| **Special** | **Startup** | During `setup()` | **Solid White** |
| **1 (Highest)** | **Hard Error** | ADC initialization/read fails | **Blinking Red** |
| **2** | **Low Voltage** | `Vip <= 0.8V` | **Blinking Yellow** |
| **2** | **High Voltage** | `Vip >= 0.92V` | **Blinking Orange** |
| **2** | **Adjusting** | `0.8V < Vip < 0.89V` or `0.91V < Vip < 0.92V` | **Color Gradient** (Yellow-Green-Orange) |
| **2** | **Target Achieved** | Voltage enters `0.89V`~`0.91V` and stays for 3s | **3 Short Green Flashes** (one-time notification) |
| **3** | **Stable & Idle** | Voltage is stable in the target range | **(Switches to BLE Status Display)** |
| ↳ | *BLE Advertising* | ↳ and BLE is not connected | **Two short blue flashes** every 2s |
| ↳ | *BLE Connected* | ↳ and BLE is connected | **Slow breathing blue light** |

## Known Issues

- **Runtime I2C Disconnect**: A physical disconnection of the I2C bus during operation will cause the main loop to block indefinitely due to a limitation in the underlying libraries. The device will become unresponsive and require a manual power cycle to recover. The button interrupt will not be able to trigger a reset in this state.

## Development & Testing

### Web BLE Test App (`ble_test.html`)

A simple web application is available for quick testing and real-time visualization of sensor data.

**How to Use:**

1.  **Start a local server**: In the project's root directory, run `python -m http.server`.
2.  **Open in Browser**: Open a compatible browser (Chrome or Edge) and navigate to `http://localhost:8000/ble_test.html`.
3.  **Connect**: Click the "Connect to BLE Device" button and select the `M5STAMP-MONITOR` device from the list.

### Future Enhancements

The core functionality of the prototype is complete. The following are potential enhancements to further improve the web application's usability and maintainability.

#### 1. Code Refactoring
-   **Goal**: Improve code maintainability and organization.
-   **Action**: Separate the HTML, CSS, and JavaScript into their own dedicated files (`index.html`, `style.css`, `app.js`). This is a standard best practice and will make future development easier.

#### 2. Data Export Feature
-   **Goal**: Allow users to save collected sensor data for later analysis.
-   **Action**: Implement an "Export to CSV" button that compiles the data currently in the chart and downloads it as a CSV file.

#### 3. View State Persistence
-   **Goal**: Preserve the user's view settings across sessions.
-   **Action**: Use `localStorage` to save and restore additional user settings, such as the selected time span and the visibility state of each dataset in the chart legend.

#### 4. **[CRITICAL]** Resolve Serial Re-connection Issue
-   **Status**: Unresolved. Attempts to re-connect to a serial device after disconnection result in an "Error: Failed to execute 'open' on 'SerialPort': The port is already open." This indicates the browser is not fully releasing the port after `serialPort.close()` or there's a timing issue with re-opening the same port object. This is a high-priority bug that needs to be addressed for reliable serial functionality.