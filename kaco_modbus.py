#!/usr/bin/python3
#
# fetch kaco inverter data, only for old/simple kaco inverters (single phase)
# based on https://github.com/ardexa/kaco-inverters/blob/master/kaco_ardexa.py

from __future__ import print_function
import sys
import time
import os
import serial

DEBUG = 0
serial_device = "/dev/ttyUSB0"
bus_addresses = "1 2 3 4 5 6 7 8"
log_dir = "/var/www/html/kaco"

# logs all inverters to outputdir, set DEBUG = 3 to see all messages
# use discovery() to test inverters

# These values are the Kaco Status Codes
STATUS_CODES = {'0': 'start', '1': 'self-test', '2': 'shutdown', '3': 'constant voltage', '4': 'mpp-track', '5': 'mpp-no-track',
                      '6': 'wait-feed-in', '7': 'wait-self-test', '8': 'test-relays', '10': 'over-temperature', '11': 'excess-power',
                      '12': 'overload-shutdown', '13': 'overvolts-shutdown', '14': 'grid-fail', '15': 'night', '18': 'RCD-shutdown',
                      '19': 'insulation-error', '30': 'measure-error', '31': 'RCD-error', '32': 'self-test error', '33': 'feedin-error',
                      '34': 'comms-error', '-999': 'no-response'}

KACO_HEADER = "Address,Status,UpvV,IpvA,PpvW,UnV,InA,PnW,TdeviceC,EdailyWh,Checksum,DeviceType,EtotalKwh\n"
KACO = 'kaco'

#~~~~~~~~~~~~~~~~~~~   START Functions ~~~~~~~~~~~~~~~~~~~~~~~

def open_serial_port(serial_dev):
    """Open the serial port and flush the buffers"""
    # open serial port
    serial_port = serial.Serial(port=serial_dev, baudrate=9600, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=3)
    # Flush the inputs and outputs
    serial_port.flushInput()
    serial_port.flushOutput()

    return serial_port


def read_inverter(inverter_addr, serial_port):
    """Attempt to read data from the inverter"""
    # Flush the inputs and outputs
    serial_port.flushInput()
    serial_port.flushOutput()

    # Kaco inverter expects a '#{inv_Numb}\r' command to get data
    inv_command = '#' + inverter_addr + '0\r\n'

    # Encode the command
    enc_cmd = inv_command.encode()
    if DEBUG:
        print("Sending the command to the RS485 port: {} encoded as: {}".format(inv_command.replace('\r', ''), enc_cmd))
    serial_port.write(enc_cmd)

    # wait 1 second. Do not make it less than that
    time.sleep(1)

    # read answer line
    response = ''
    while serial_port.in_waiting > 0:
        part = serial_port.read(serial_port.in_waiting)
        response += part.decode("iso-8859-1")

    if DEBUG > 2:
        print("Received the following data: {}".format(response.replace('\r', '\n')))

    return response


def write_line(raw_line, inverter_addr, discovery):
    """Parse the values returned by the inverter and write them to file"""
    # Find the start token
    start_index = raw_line.find('*')
    if start_index == -1:
        if DEBUG:
            print("Could not find the start token for {}".format(inverter_addr))
        return False

    # Extract everything from the index.
    sub_string = raw_line[start_index:]

    # Split everything into an array using spaces
    items = sub_string.split()

    # Check that the first token is as required
    if items[0] != '*' + inverter_addr + '0':
        print("Line seems to be corrupted")
        return False

    items[0] = inverter_addr

    # Check that the list contains at least noe items
    if len(items) < 12:
        if DEBUG > 1:
            print("Some elements appear to be missing from the inverter raw data")
        return False

    items[1] = items[1] + '_' + STATUS_CODES[items[1]]
    items[10] = str(ord(items[10]))

    if DEBUG > 1:
        print("Raw inverter line list: {}".format(items))

    inverter_line = ','.join(items)

    if discovery or DEBUG:
        print("\nAddress: ", inverter_addr)
        tl_header_items = KACO_HEADER.split(',')
        for i in range(len(items)):
            print('\t%-50s %50s' % (tl_header_items[i].strip(), items[i]))

    inverter_line = time.strftime("%H:%M:%S") + ',' + inverter_line + '\n'

    if DEBUG > 1:
        print("log entry: {}".format(inverter_line))

    # Write the log entry, as a date entry in the log directory
    date_str = time.strftime("%Y-%m-%d")
    log_file = log_dir + '/'+ date_str + ".csv"

    if os.path.exists(log_file) != True:
        with open(log_file, 'a') as fd:
            fd.write('Time,' + KACO_HEADER)

    with open(log_file,'a') as fd:
        fd.write(inverter_line)

    return True



#~~~~~~~~~~~~~~~~~~~   END Functions ~~~~~~~~~~~~~~~~~~~~~~~
# Check script is run as root
if os.geteuid() != 0:
    print("You need to have root privileges to run this script, or as \'sudo\'. Exiting.")
    sys.exit(2)

# If the logging directory doesn't exist, create it
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

start_time = time.time()
# Open the serial port
serial_port = open_serial_port(serial_device)

# check every inverter, max 5 tries each
for inverter_addr in bus_addresses.split():
    if int(inverter_addr) < 10:
        inverter_addr = "0" + inverter_addr

    count = 5
    while count >= 1:
        time.sleep(1)
        result = read_inverter(inverter_addr, serial_port)
        success = write_line(result, inverter_addr, False)
        if success:
            break
        count = count - 1

serial_port.close()

elapsed_time = time.time() - start_time
if DEBUG:
    print("This request took: {} seconds.".format(elapsed_time))
