from machine import Pin, PWM, ADC
import utime
import _thread
import sys
import select

LED_PIN = 25  # Onboard LED pin
led = Pin(LED_PIN, Pin.OUT)

# Pin definitions
ADC_PIN = 27  # GPIO27_ADC1: Voltage feedback input (20V to 3.3V voltage divider)
PWM_PIN = 28  # GPIO28_ADC2: PWM output to buck converter
EN_PIN = 20   # GPIO20: Enable pin for buck converter

# Constants
DEFAULT_PWM_FREQ = 100000  # 100 kHz default PWM frequency
DEFAULT_DUTY = 50          # 50% default duty cycle
DEFAULT_VOLTAGE = 5.0      # 5.0V default target voltage
MAX_ADC_VALUE = 65535      # Maximum value of ADC (16-bit)
ADC_REFERENCE = 3.3        # ADC reference voltage
VOLTAGE_DIVIDER_RATIO = 20.0 / 3.3  # 20V input gives 3.3V at ADC

# Global variables
pwm_frequency = DEFAULT_PWM_FREQ
duty_cycle = DEFAULT_DUTY
target_voltage = DEFAULT_VOLTAGE
feedback_mode = False
command_queue = []
lock = _thread.allocate_lock()

# Initialize hardware
adc = ADC(Pin(ADC_PIN))
pwm = PWM(Pin(PWM_PIN))
en = Pin(EN_PIN, Pin.OUT)
uart = machine.UART(0, 115200)  # Add this at the top (global or inside the function)

def setup_hardware():
    """Initialize the hardware components"""
    pwm.freq(pwm_frequency)
    pwm.duty_u16(int(duty_cycle * 655.35))  # Convert percentage to 16-bit duty cycle
    en.value(1)  # Enable the buck converter
    
def read_voltage():
    """Read the actual output voltage from ADC"""
    adc_value = adc.read_u16()
    voltage = (adc_value / MAX_ADC_VALUE) * ADC_REFERENCE * VOLTAGE_DIVIDER_RATIO
    return voltage

def set_duty_cycle(duty):
    """Set PWM duty cycle (0-100%)"""
    global duty_cycle
    if 0 <= duty <= 100:
        duty_cycle = duty
        pwm_value = int(duty * 655.35)  # Convert percentage (0-100) to 16-bit (0-65535)
        pwm.duty_u16(pwm_value)
        return True
    return False

def set_pwm_frequency(freq):
    """Set PWM frequency in Hz"""
    global pwm_frequency
    if 1 <= freq <= 5000000:  # 1Hz to 5MHz
        pwm_frequency = freq
        pwm.freq(freq)
        return True
    return False

def set_target_voltage(voltage):
    """Set target voltage for feedback mode"""
    global target_voltage
    if 0 < voltage <= 20:  # Assuming max voltage is 20V as per voltage divider
        target_voltage = voltage
        return True
    return False

def print_help():
    """Print available commands"""
    print("Available commands:")
    print("  PWM=<NUM>          : Set PWM frequency in Hz (1-5000000)")
    print("  DUTY=<NUM>         : Set duty cycle in % (0-100)")
    print("  VOLTAGE=<FLOAT_NUM>: Set target voltage and activate feedback mode")
    print("  MODE=MANUAL        : Disable feedback mode")
    print("  MODE=FEEDBACK      : Enable feedback mode")
    print("  STATUS             : Display current status")
    print("  HELP               : Show this help")

def process_command(cmd):
    """Process a command from USB serial"""
    global feedback_mode
    cmd = cmd.strip().upper()
    
    if not cmd:  # Skip empty commands
        return
    
    if cmd.startswith("PWM="):
        try:
            freq = int(cmd.split("=")[1])
            if set_pwm_frequency(freq):
                print("PWM frequency set to {} Hz".format(freq))
            else:
                print("Invalid PWM frequency. Use 1-5000000 Hz")
        except ValueError:
            print("Invalid PWM command format. Use PWM=<NUM>")
    
    elif cmd.startswith("DUTY="):
        try:
            duty = float(cmd.split("=")[1])
            if set_duty_cycle(duty):
                print("Duty cycle set to {}%".format(duty))
            else:
                print("Invalid duty cycle. Use 0-100%")
        except ValueError:
            print("Invalid DUTY command format. Use DUTY=<NUM>")
    
    elif cmd.startswith("VOLTAGE="):
        try:
            voltage = float(cmd.split("=")[1])
            if set_target_voltage(voltage):
                print("Target voltage set to {}V".format(voltage))
                feedback_mode = True
                print("Feedback mode activated")
            else:
                print("Invalid voltage. Use 0-20V")
        except ValueError:
            print("Invalid VOLTAGE command format. Use VOLTAGE=<FLOAT_NUM>")
    
    elif cmd == "MODE=MANUAL":
        feedback_mode = False
        print("Manual mode activated")
    
    elif cmd == "MODE=FEEDBACK":
        feedback_mode = True
        print("Feedback mode activated")
    
    elif cmd == "STATUS":
        current_voltage = read_voltage()
        print("Status:")
        print("  Mode: {}".format('Feedback' if feedback_mode else 'Manual'))
        print("  Frequency: {} Hz".format(pwm_frequency))
        print("  Duty: {}%".format(duty_cycle))
        print("  Target: {}V".format(target_voltage))
        print("  Actual: {:.2f}V".format(current_voltage))
    
    elif cmd == "HELP":
        print_help()
    
    else:
        print("Unknown command: {}".format(cmd))
        print("Type HELP for available commands")

def feedback_control():
    """PID-like controller for voltage regulation"""
    global duty_cycle
    
    led_state = False
    last_blink_time = utime.ticks_ms()
    
    # Simple controller parameters
    Kp = 5.0  # Proportional gain
    Ki = 0.2  # Integral gain
    
    integral = 0
    prev_time = utime.ticks_ms()
    
    while True:
        # Blink LED every 500ms
        now = utime.ticks_ms()
        if utime.ticks_diff(now, last_blink_time) >= 500:
            led_state = not led_state
            led.value(led_state)
            last_blink_time = now
        
        if feedback_mode:
            current_voltage = read_voltage()
            current_time = utime.ticks_ms()
            dt = utime.ticks_diff(current_time, prev_time) / 1000.0  # Convert to seconds
            
            # Calculate error
            error = target_voltage - current_voltage
            
            # Integral term with anti-windup
            integral += error * dt
            integral = max(-10, min(10, integral))  # Limit integral term
            
            # Calculate control output (duty cycle adjustment)
            output = Kp * error + Ki * integral
            
            # Update duty cycle with limits
            new_duty = duty_cycle + output
            new_duty = max(0, min(100, new_duty))  # Ensure duty cycle stays within 0-100%
            
            # Apply new duty cycle if significantly different
            if abs(new_duty - duty_cycle) > 0.1:
                set_duty_cycle(new_duty)
            
            prev_time = current_time
        
        # Process any commands in the queue
        with lock:
            while command_queue:
                cmd = command_queue.pop(0)
                process_command(cmd)
        
        # Small delay to prevent CPU hogging
        utime.sleep_ms(10)

def command_listener():
    """Listen for commands from USB serial"""
    while True:
        try:
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                cmd = sys.stdin.readline().strip()
                if cmd:  # Process only non-empty commands
                    with lock:
                        command_queue.append(cmd)
        except Exception as e:
            print("Error reading command: {}".format(e))
        utime.sleep_ms(10)

def main():
    #wait for 5 seconds
    for i in range(50):
        led.toggle()
        utime.sleep_ms(100)
        
    """Main function"""
    print("\nBuck Converter Controller for RP2040")
    print("-------------------------------------")
    print_help()
    print()
    
    setup_hardware()
    
    # Start the command listener thread
    _thread.start_new_thread(command_listener, ())
    
    # Run the feedback control loop in the main thread
    feedback_control()

if __name__ == "__main__":
    main()