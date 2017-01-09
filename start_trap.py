from goprohero import GoProHero
from wireless import Wireless

import sys
import socket
import struct
import signal
import time
import threading

# After this period expires, we start checking for ongoing movement
MIN_VIDEO_LENGTH = 10 #seconds

#
# Network Setup
#
IFACE = 'wlan0'
GOPRO_IP = '10.5.5.9'
GOPRO_SSID = 'Valtor'
GOPRO_PASS = 'ninjacam'
#GOPRO_SSID = 'vulcan'
#GOPRO_PASS = 'cellardoor'
GOPRO_MAC = 'd6d919ee4133'
network = Wireless(IFACE)
##########################################

#
# GPIO setup
#
import pigpio
pigpio.start()
GPIO_PIN = 11
pigpio.set_mode(GPIO_PIN, pigpio.INPUT)
###########################################

camera = None
#
# The Main loop
#
def main_loop():
    global camera
    camera = GoProHero(password=GOPRO_PASS)


    # Record a 5 second test video, just to signal the user that
    # Raspberry Pi has booted up and that this program is running. This is useful
    # as feedback, when your Pi is not connected to a monitor or a terminal
    #
    print "Motion video trap reporting for duty. Your camera should take a test video now..."
    start_recording()
    time.sleep(5)
    stop_recording()

    # Start monitoring GPIO pin for a rising edge
    start_gpio_monitor()

    # Loop forever
    print "Starting main loop..."
    while True:
        time.sleep(10)



def timestamp():
    return time.strftime('%l:%M:%S%p on %b %d, %Y')

def start_recording():
    send_record_command("on")
    print "%s: Video started" % timestamp()

def stop_recording():
    send_record_command("off")
    print "%s: Video stopped" % timestamp()

def send_record_command(state):
    global camera
    if ( camera.command("record", state) == False ):
        wake_on_lan()
        camera.command("record", state)


#
# This is a threaded callback summoned when rising edge is detected
#
lock = threading.Lock()
def movement_detected(gpio, level, tick):
    with lock:
            stop_gpio_monitor() # Stop GPIO pin monitoring

            start_recording() # Record for MIN_VIDEO_LENGTH seconds

            consider_stopping() # Block until we should stop recording

            stop_recording() # Stop 

            start_gpio_monitor() # Restart GPIO pin monitoring

            
gpioCallbackControl = None
def start_gpio_monitor():
    global gpioCallbackControl
    gpioCallbackControl = pigpio.callback(GPIO_PIN, pigpio.RISING_EDGE, movement_detected)

def stop_gpio_monitor():
    global gpioCallbackControl
    gpioCallbackControl.cancel()

#
# Blocks until it's time to stop recording
#
def consider_stopping():
    # Sleep for duration of the video
    time.sleep(MIN_VIDEO_LENGTH)

    # Start checking - is there still motion?
    while pigpio.read(GPIO_PIN):
        print "  %s: Movement still detected..." % timestamp()
        time.sleep(5) # Every 5 seconds

    # Unblock when motion stops

# 
# Make sure we are connected to GoPro's wifi
#
def check_wifi():
    print "Currently connected to: %s" % (get_current_ssid())

    if get_current_ssid() != GOPRO_SSID:
        print "Connecting to %s" % GOPRO_SSID
        network.connect(ssid=GOPRO_SSID, password=GOPRO_PASS)
        print "Now connected to: %s" % (get_current_ssid())

    return get_current_ssid() == GOPRO_SSID


def get_current_ssid():
	return network.current().split(' ', 1)[0]

#
# Puts the camera to sleep
#
def go_to_sleep():
    global camera
    if ( camera.command("power", "sleep") == False ):
        wake_on_lan()
        camera.command("power", "sleep")


# 
# Sends the Wake-on-LAN Magic Packet to UDP port 9 on the GoPro.
# This is necessary to wake up the GoPro if it is sleeping
#
def wake_on_lan():
    """ Switches on remote computers using WOL. """
    global GOPRO_MAC
    print "%s: Sending Wake-On-Lan packet..." % timestamp()
 
    # Check GOPRO_MAC format and try to compensate.
    if len(GOPRO_MAC) == 12:
        pass
    elif len(GOPRO_MAC) == 12 + 5:
        sep = GOPRO_MAC[2]
        GOPRO_MAC = GOPRO_MAC.replace(sep, '')
    else:
        raise ValueError('Incorrect MAC address format')
    # Pad the synchronization stream.
    data = ''.join(['FFFFFFFFFFFF', GOPRO_MAC * 20])
    send_data = ''
 
    # Split up the hex values and pack.
    for i in range(0, len(data), 2):
        send_data = ''.join([send_data,
                             struct.pack('B', int(data[i: i + 2], 16))])
 
    # Broadcast it to the LAN.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(send_data, (GOPRO_IP, 9))

    # Wait for the camera to boot up
    time.sleep(7)


 
#
# Graceful Exit
#
def ctrl_c_handler(signal, frame):
    print 'Cleaning up...'
    pigpio.stop()
    sys.exit(0)
    

signal.signal(signal.SIGINT, ctrl_c_handler)

if __name__ == '__main__':
    try:
        if check_wifi():
            main_loop()
    finally:
        ctrl_c_handler(None, None)

