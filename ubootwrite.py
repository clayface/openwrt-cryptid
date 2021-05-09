#!/usr/bin/env python2.7
#
# simple tool to upload data to the RAM of linux systems running the U-Boot bootloader
#
# This is a modified version of ubootwrite. The original code can be downloaded from github:
# <https://github.com/HorstBaerbel/ubootwrite>
#
# Basically it can only be GPLv3, because brntool is.

# -*- coding: utf-8 -*-
from __future__ import division #1/2 = float, 1//2 = integer, python 3.0 behaviour in 2.6, to make future port to 3 easier.
from __future__ import print_function
from optparse import OptionParser
import os
import struct
import sys
import zlib
import time

debug = False
if not debug:
	import serial

# The maximum size to transfer if we can determinate the size of the file (if input data comes from stdin).
MAX_SIZE = 2 ** 30
LINE_FEED = "\n"

# Wait for the prompt
def getprompt(ser, addr, verbose, shell):
	# Send a command who does not produce a result so when receiving the next line feed, only show the prompt will be returned
	# Flushing read buffer
	if not shell:
		buf = ""
		while True:
			oldbuf = buf
			buf = ser.read(256);
			combined = str(oldbuf)+str(buf)
			#if "cdp: machid 4971" in combined:
			if "late_init: machid 4971" in combined:
				ser.write(str.encode("xyzzy"));
				while ser.read(256):
					   pass
				break

	if verbose:
		print("Waiting for a prompt...")
	while True:
		# Write carriage return and wait for a response
		ser.write(str.encode(LINE_FEED))
		# Read the response
		buf = ser.read(256);
		if (buf.endswith(b"> ") or buf.endswith(b"# ")):
			print("Prompt is '" + str(buf[2:]) + "'")
			# The prompt returned starts with a line feed. This is the echo of the line feed we send to get the prompt.
			# We keep this linefeed
			return buf
		else:
			# Flush read buffer
			while True:
				buf = ser.read(256)
				if (buf.endswith(b"> ") or buf.endswith(b"# ")):
					print("Prompt is '" + str(buf[2:]) + "'")
	 		   			# The prompt returned starts with a line feed. This is the echo of the line feed we send to get the prompt.
					# We keep this linefeed
					return buf
				pass

# Wait for the prompt and return True if received or False otherwise 
def writecommand(ser, command, prompt, verbose):

	# Write the command and a line feed, so we must get back the command and the prompt
	ser.write(str.encode(command + LINE_FEED))
	buf = ser.read(len(command))
	if (buf.decode("utf-8") != command):
		if verbose:
			print("Echo command not received. Instead received '" + buf.decode("utf-8") + "'")
		return False

	if verbose:
		print("Waiting for prompt...")

	buf = ser.read(len(prompt))
	if (buf == prompt):
		if verbose:
			print("Ok, prompt received")
		return True
	else:
		if verbose:
			print("Prompt '" + str(prompt) + "' not received. Instead received '" + str(buf) + "'")
		return False

def memwrite(ser, path, size, start_addr, verbose, debug, shell):
	if not debug:
		prompt = getprompt(ser, start_addr, verbose, shell)

	if (path == "-"):
		fd = sys.stdin
		if (size <= 0):
			size = MAX_SIZE
	else:
		fd = open(path,"rb")
		if (size <= 0):
			# Get the size of the file
			fd.seek(0, os.SEEK_END);
			size = fd.tell();
			fd.seek(0, os.SEEK_SET);

	addr = start_addr
	bytes_read = 0
	startTime = time.time();
	bytesLastSecond = 0
	while (bytes_read < size):
		if ((size - bytes_read) > 4):
			read_bytes = fd.read(4);
		else:
			read_bytes = fd.read(size - bytes_read);

		# the MR33 mw command needs each 4 byte block reversed
		read_bytes = read_bytes[::-1];

		if (len(read_bytes) == 0):
			if (path == "-"):
				size = bytes_read
			break

		bytesLastSecond += len(read_bytes)
		bytes_read += len(read_bytes)

		while (len(read_bytes) < 4):
			read_bytes = b'\x00'+read_bytes

		(val, ) = struct.unpack(">L", read_bytes)
		read_bytes = "".format(val)

		str_to_write = "mw {0:08x} {1:08x}".format(addr, val)
		if verbose:
			print("Writing:'" + str_to_write + "' at:", "0x{0:08x}".format(addr))
		if debug:
			str_to_write = struct.pack(">L", int("{0:08x}".format(val), 16))
		else:
			if not writecommand(ser, str_to_write, prompt, verbose):
				print("Found an error, so aborting")
				fd.close()
				return
			# Print progress
			currentTime = time.time();
			if ((currentTime - startTime) > 1):
				percent=(bytes_read * 100) / size
				speed=bytesLastSecond / (currentTime - startTime) / 1024
				eta=round((size - bytes_read) / bytesLastSecond / (currentTime - startTime))
				print("\rProgress {0:3.1f}%,  {1:3.1f}kb/s, ETA {2:0}s ".format(percent,speed,eta))
				bytesLastSecond = 0
				startTime = time.time();

		# Increment address
		addr += 4

	fd.close()

	if (bytes_read != size):
		print("Error while reading file '", fd.name, "' at offset " + bytes_read)
		return False
	else:
		print("\rProgress 100%				")
		writecommand(ser, "go {0:08x}".format(start_addr), prompt, verbose)
		return True

def upload(ser, path, size, start_addr, verbose, debug, shell):
#	while True:
	print("Waiting for device...")
	ret = memwrite(ser, path, size, start_addr, verbose, debug, shell)
	print("Done")
#		if ret:
#			shell = True
#			buf = ""
#			while True:
#				oldbuf = buf
#				buf = ser.read(256);
#				if buf:
#					print("COM: %s" % buf.decode("utf-8"));
#
#					combined = str(oldbuf)+str(buf)
#					if "ERROR: can't get kernel image!" in combined:
#						print("Retry...")
#						break
#
#					if "Hello from MR33 U-BOOT" in combined:
#					return
#				pass
#		pass
	return

def main():
	optparser = OptionParser("usage: %prog [options]", version = "%prog 0.2 mr33")
	optparser.add_option("--verbose", action = "store_true", dest = "verbose", help = "be verbose", default = False)
	optparser.add_option("--shell", action = "store_true", dest = "shell", help = "already have shell", default = False)
	optparser.add_option("--serial", dest = "serial", help = "specify serial port", default = "/dev/ttyUSB0", metavar = "dev")
	optparser.add_option("--write", dest = "write", help = "write mem from file", metavar = "path")
	optparser.add_option("--addr", dest = "addr", help = "mem address", default = "0x42000000", metavar = "addr")
	optparser.add_option("--size", dest = "size", help = "# bytes to write", default = "0", metavar = "size")
	(options, args) = optparser.parse_args()
	if (len(args) != 0):
		optparser.error("incorrect number of arguments")

	if not debug:
		ser = serial.Serial(options.serial, 115200, timeout=0.1)
	else:
		ser = open(options.write + ".out", "wb")

	if debug:
		prompt = getprompt(ser, options.verbose, options.shell)
		writecommand(ser, "mw 42000000 01234567", prompt, options.verbose)
		buf = ser.read(256)
		print("buf = '" + buf + "'")
		return

	if options.write:
		upload(ser, options.write, int(options.size, 0), int(options.addr, 0), options.verbose, debug, options.shell)

	return

if __name__ == '__main__':
	main()
