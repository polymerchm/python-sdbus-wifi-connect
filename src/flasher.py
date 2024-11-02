"""
this program runs in the background (as a service)

when running, it will flash an LED attached to the 
designated GPIO pin to alert the user that the system 
is in hotspsot mode

"""

import os, getopt, sys, signal
import atexit
from math import pow, log10
from time import sleep
import RPi.GPIO as GPIO


def string_to_int(s, default):
    try:
        return int(s)
    except ValueError:
        return default

def signal_handler(arg1, arg2):
    global enabled


def cleanup():
    GPIO.cleanup()


def main(pin: int, on: float | int, off: float | int, steps: int)->None:
    #initialize GPIO
    if not pin in [12, 13, 18, 19]:
        print("better to use hawdware PWM")
        sys.exit(0)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.OUT)
    LED = GPIO.PWM(pin, 100)
    fade_factor = float(steps) * log10(2)/log10(steps)
    ramp_step_time = float(on)/float(steps)
    LED.start(0)
    up_ramp = [100*pow(2, level/fade_factor - 1)/steps for level in range(steps)]
    down_ramp = [100*pow(2, level/fade_factor - 1)/steps for level in range(steps,0,-1)]
    while enabled:
        for level in up_ramp:
            LED.ChangeDutyCycle(level)
            sleep(ramp_step_time)
        for level in down_ramp:
            LED.ChangeDutyCycle(level)
            sleep(ramp_step_time)
        #insure level is zero
        LED.ChangeDutyCycle(0)
        sleep(off)
    LED.ChangeDutyCycle(0)
    LED.stop()
    GPIO.cleanup()



if __name__ == "__main__":
    atexit.register(cleanup)
    enabled: bool = True
    GPIO_PIN = 18
    ON_DURATION = 2 # seconds
    OFF_DURATION = 0.1 
    STEPS = 200 #

    usage = ''\
f'Command line args: \n'\
f'  -p GPIO PIN                  Default: {GPIO_PIN} \n'\
f'  -o On duration               Default: {ON_DURATION} \n'\
f'  -f Off duration              Default: {OFF_DURATION} \n'\
f'  -s Steps                     Default: {STEPS} \n'\
f'  -h Show help.\n'

    try:
        opts, args = getopt.getopt(sys.argv[1:], "p:o:f:s:h")
    except getopt.GetoptError:
        print("Error in arguments")
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            print(usage)
            sys.exit()

        elif opt in ("-o"):
            ON_DURATION = string_to_int(arg, ON_DURATION)

        elif opt in ("-p"):
            GPIO_PIN = string_to_int(arg, GPIO_PIN)

        elif opt in ("-f"):
            OFF_DURATION = string_to_int(arg, OFF_DURATION)

        elif opt in ("-s"):
            STEPS = string_to_int(arg, STEPS)

    try:
        main(pin=GPIO_PIN, on=ON_DURATION, off=OFF_DURATION, steps=STEPS)
    except KeyboardInterrupt:
        sys.exit()
