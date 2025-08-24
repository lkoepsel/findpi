# findpi - A Raspberry Pi Identity Solution

**Formerly know as hello and rasp-mDNS**

## Description
This is a solution for identifying newly programmed, headless *Raspberry Pi (RPi)*'s on a large network. In large networks (*ex: community college*), the wireless network has a significant issue. As network is quite large, it can be difficult to readily identify a *RPi* which has recently joined the network, therefore making it almost impossible to connect to the *RPi*.

Recently, the Raspberry Pi Foundation released [Raspberry Pi Connect](https://www.raspberrypi.com/documentation/services/connect.html), which "*provides secure access to your Raspberry Pi from anywhere in the world.*" That's great, except for a couple of issues:
* You need to register. I understand why, however, its a burdensome step to solve such a simple problem.
* Its a *world-wide* solution. I was looking for a *local* solution, one which doesn't **require** connecting to the internet.

## The *findpi* Solution - Run a service on Raspberry Pi
A solution is to implement an auto-connecting application on startup, **on the remote *RPi***. This application will ping a local server (your PC or another *LAN-based* host *RPi*) with its host name and IP address. This ensures you have ready access to the remote *RPi* without having to go through determining its IP address. 

This solution will work due to the ability to save your server's IP address on the *RPi*, prior to boot. This means the *RPi* is trying to find you, instead of vice-versa. 

Once implemented, the steps to connect in a new network are:
1. Determine the IP address of your host system.
2. Using any platform, *Windows*, *macOS* or *Linux*, enter the IP address into a specific file on the *RPi* SD card.
3. Place the SD card in the RPi and power it up. Start the findpi_server application on your host system and wait for the *ping*.

## Installation
### 1. Requirements
#### 1.1 Host System (Your PC or a host *RPi*)
*Python* and the *flask* library. If you don't have *flask* installed and encounter the new Python requirement to run in a virtual environment...you may install it system-wide with *sudo apt install python3-flask* on *Debian* (or *Raspberry Pi Bookworm*).

#### 1.2. Raspberry Pi (remote *RPi*)
Raspberry Pi OS Bookworm (or later)

### 2. Create a findpi.service on the remote Raspberry Pi
Create a startup application, which will ping a server by *IP address* and report **its own** host name and IP address.

#### 2.1.. Create findpi.py
This is the program which executes as part of the *findpi.service*. Open a Python file, then copy/paste contents below into file:
```python
# open a file named findpi.py
sudo nano /usr/bin/findpi.py
```
Paste the following contents then Ctrl-S, to save and Ctrl-X to exit *nano*.
```python
import logging
import requests
import socket
import os
import sys
import time


def setup_logging():
    try:
        # Check if /boot/firmware is mounted
        hadtomount = False
        if not os.path.exists("/boot/firmware"):
            hadtomount = True
            mount_result = os.system("sudo mount /dev/mmcblk0p1 /boot/firmware")
            if mount_result != 0:
                print("ERROR: Failed to mount /boot/firmware", file=sys.stderr)
                sys.exit(10)  # Exit code 10: Mount failure

        # set logging to DEBUG, if messages aren't seen in log file
        logging.basicConfig(
            filename="/tmp/findpi.log",
            encoding="utf-8",
            format="%(asctime)s %(filename)s:%(levelname)s: %(message)s",
            level=logging.DEBUG,
        )

        return hadtomount
    except PermissionError:
        print("ERROR: Permission denied when setting up logging", file=sys.stderr)
        sys.exit(11)  # Exit code 11: Logging permission error
    except Exception as e:
        print(f"ERROR: Failed to setup logging: {str(e)}", file=sys.stderr)
        sys.exit(12)  # Exit code 12: General logging setup error


def find_ip_file():
    IP_file = "findpi_ip.txt"  # Name of the file containing the IP address
    # List of directories to search
    dirs_to_check = ["/boot", "/boot/firmware"]

    # Search for the file in the listed directories
    for dir_path in dirs_to_check:
        file_path = os.path.join(dir_path, IP_file)
        if os.path.isfile(file_path):
            try:
                with open(file_path, "r") as f:
                    ip = f.read().rstrip("\n")
                    logging.debug("IP address found in %s", file_path)
                return ip  # Return IP if found
            except IOError as e:
                logging.error("Error opening file: %s - %s", file_path, str(e))
                print(f"ERROR: Could not read {file_path}: {str(e)}", file=sys.stderr)
                sys.exit(20)  # Exit code 20: File read error

    # If we get here, file wasn't found
    error_msg = f"{IP_file} not found in {dirs_to_check}"
    logging.error(error_msg)
    print(f"ERROR: {error_msg}", file=sys.stderr)
    sys.exit(21)  # Exit code 21: IP file not found


def check_already_ran():
    """Check if we've already completed our 3 runs since boot"""
    completed_file = "/tmp/findpi_completed"

    if os.path.exists(completed_file):
        logging.info("Service has already completed 3 runs since boot. Exiting.")
        print("INFO: Service has already completed 3 runs since boot.")
        return True

    return False


def mark_completed():
    """Mark that we've completed our 3 runs"""
    completed_file = "/tmp/findpi_completed"
    try:
        with open(completed_file, "w") as f:
            f.write("completed")
        logging.info("Marked service as completed after 3 runs")
    except Exception as e:
        logging.error("Error marking completion: %s", str(e))


def send_findpi_request(ip, attempt_num):
    """Send a single findpi request"""
    try:
        # Get hostname and prepare request
        host_name = socket.gethostname()
        logging.debug("Host name: %s", host_name)

        url = "http://" + ip
        text = f"{host_name}"  # send hostname
        logging.debug("Attempt #%d - Sending request to: %s", attempt_num, url)

        data = {"text": text}

        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses

        logging.info(
            "Attempt #%d - SUCCESS: Status code: %s", attempt_num, response.status_code
        )
        logging.debug("Attempt #%d - Response: %s", attempt_num, response.text)
        return True

    except requests.exceptions.ConnectionError as e:
        error_msg = f"Attempt #%d - Connection error to {url}: {str(e)}"
        logging.error(error_msg)
        print(f"ERROR: {error_msg}", file=sys.stderr)
        return False

    except requests.exceptions.Timeout as e:
        error_msg = f"Attempt #%d - Request timed out to {url}: {str(e)}"
        logging.error(error_msg)
        print(f"ERROR: {error_msg}", file=sys.stderr)
        return False

    except requests.exceptions.HTTPError as e:
        error_msg = f"Attempt #%d - HTTP error from {url}: {str(e)}"
        logging.error(error_msg)
        print(f"ERROR: {error_msg}", file=sys.stderr)
        return False

    except requests.exceptions.RequestException as e:
        error_msg = f"Attempt #%d - Request failed to {url}: {str(e)}"
        logging.error(error_msg)
        print(f"ERROR: {error_msg}", file=sys.stderr)
        return False


def main():
    try:
        # Setup logging and mount if needed
        hadtomount = setup_logging()

        # Check if we've already completed our runs
        if check_already_ran():
            return 0

        logging.info("Starting findpi service - will attempt 3 times")

        # Find IP address
        ip = find_ip_file()

        # Unmount if we mounted TODO: Remove after tested
        # if hadtomount:
        #     umount_result = os.system("sudo umount /boot/firmware")
        #     if umount_result != 0:
        #         logging.warning("Failed to unmount /boot/firmware")

        # Make 3 attempts with delays
        success_count = 0
        for attempt in range(1, 4):  # 1, 2, 3
            logging.info("Starting attempt #%d of 3", attempt)

            success = send_findpi_request(ip, attempt)
            if success:
                success_count += 1

            # Wait 10 seconds before next attempt (except after the last one)
            if attempt < 3:
                logging.info("Waiting 10 seconds before next attempt...")
                time.sleep(10)

        # Mark as completed so we don't run again until reboot
        mark_completed()

        logging.info(
            "Completed all 3 attempts. Successful attempts: %d/3", success_count
        )
        print(f"INFO: Completed all 3 attempts. Successful attempts: {success_count}/3")

        return 0  # Always return 0 to prevent service restart

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        # Try to log if logging is set up
        try:
            logging.error(error_msg)
        except:
            pass
        print(f"ERROR: {error_msg}", file=sys.stderr)
        return 0  # Return 0 to prevent restart


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
```
*Ctrl-S* (save) *Ctrl-X* (exit)

#### 2.2. Add IP address of the host server to the remote *RPi* boot folder
This step identifies your PC by IP address to the Raspberry Pi:

##### **On your PC or host *RPi***

Run either server program (*simple_server.py or findpi_server.py*), and it will report the host IP address.
```bash
python -m findpi_server
Cleaned 12 test entries from database
 * Serving Flask app 'findpi_server'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.1.49:5000
Press CTRL+C to quit

```
The IP address to use, is the one **which is not 127.0.0.1**, in this case it is *192.168.1.49:5000*. 

##### **On the remote *RPi***

Open the file which will contain the IP address.

```bash
sudo nano /boot/firmware/findpi_ip.txt
```

Enter the only the numeric IP address of your PC WITHOUT a return at the end of the line. The file *findpi_ip.txt* will need to look like:

```bash
192.168.1.49:5000
```
*Ctrl-S* (save) *Ctrl-X* (exit)

**Note:** By storing the IP address in a file at */boot/firmware*, you may access the file on a macOS or Windows system. The *boot/firmware* folder shows up as a readable folder on either system called *bootfs*. This enables you to change the IP address on your PC then re-insert the SD card into the *RPi* to ping you at a new address. 

There is also a file on *boot/firmware* called *findpi.log*, which you can open with a text editor. It will contain the log entries for the *findpi.service*. Use these entries if you are having difficulty getting a ping from the *RPi.*

Due to some permissions issues, the findpi.log is created on both the /home/lkoepsel folder as /home/lkoepsel/findpi.log and /boot/firmware/findpi.log. The latter is copied from the former after the service runs. If your are attempting to read the file from a non-Raspberry Pi filesystem, then use /boot/firmware, otherwise, it might be easier to read the /home/lkoepsel version.

#### 2.3. Setup `systemd` unit file for findpi.py service
This will execute the *findpi.py* app, after all other startup services have been executed on the RPi. 

The service will log entries to */boot/firmware/findpi.log* on the *RPi* or */bootfs/findpi.log* when examining the SD card on a Mac/Windows system. Use it to determine any issues with the service.

You may use the command `journalctl -b`, to see all boot messages of the *RPi*. or use `journalctl -b | grep findpi`, to see all messages related to the service.

You can use the space bar, to quickly go through screens of lines. Look for the word DEBUG as the *findpi.py* application uses logging to print messages.

#### findpi.service
Same as above, use nano to create file, copy/paste contents below then exit *nano*. 

```bash
sudo nano /lib/systemd/system/findpi.service
```

Copy/paste contents below into the file:
```bash
[Unit]
Description=Ping a known server (findpi_ip.txt) with hostname and IP address (3 times per boot)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python /usr/bin/findpi.py
ExecStopPost=/bin/bash -c "sudo cp /tmp/findpi.log /boot/firmware/ "
Restart=no
StandardOutput=journal
StandardError=journal

# Define custom exit code messages
SuccessExitStatus=0
ExitStatusText=10:MOUNT_FAILURE 11:LOGGING_PERMISSION_ERROR 12:LOGGING_SETUP_ERROR 20:FILE_READ_ERROR 21:IP_FILE_NOT_FOUND 30:CONNECTION_ERROR 31:REQUEST_TIMEOUT 32:HTTP_ERROR 33:REQUEST_ERROR 99:UNEXPECTED_ERROR

[Install]
WantedBy=multi-user.target
```

Exit nano using *Ctrl-S* *Ctrl-X*

#### 2.4 Run the following commands to create service and test it. 

(*It helps to go to step 3 on your host system and confirm the findpi message appears*):

```bash
sudo chmod 644 /lib/systemd/system/findpi.service
sudo systemctl daemon-reload
# enable the service so that it runs on all subsequent systems boots
sudo systemctl start findpi.service
sudo systemctl status findpi.service
```

#### 2.5 Enable the service to run on startup. (IMPORTANT)
```bash
# if findpi.service is running well, then enable to run on boot
sudo systemctl enable findpi.service
```

Additional commands which will be helpful, later once the service is running:
```bash
# determine if the findpi.service is running
sudo systemctl status findpi.service

# stop the findpi.service, useful if you want to stop pinging server
sudo systemctl stop findpi.service

# restart the findpi.service, this will stop then start the service
sudo systemctl restart findpi.service
```
## Pick 3a or 3b below based on your needs.
### 3a. Simple Version (Good for single *RPi* connections)
The simple version is useful for single *RPi* connections. Using a terminal program on your PC, use one tab to connect to your findpi_server system (typically a host *RPi* or your PC) and the second tab to connect to the remote *RPi* in question. Once this repository is installed on the host *RPi*, follow the steps below:
1. Run `python -m simple_server` on the host *RPi*.
2. Ensure the remote *RPi* has the findpi.service running.
3. Reboot the remote *RPi*.

In your host tab, once the remote *RPi* has been rebooted, you should see the following:
```bash
...
* Running on http://192.168.1.49:5000
...
speedy
192.168.1.112 - - [29/Nov/2024 08:54:40] "POST / HTTP/1.1" 200 -
```

The *running on* message is the IP address of the server *RPi* and the two lines with *speedy* are the hostname and IP address of the remote *RPi*.

### 3b. Enhanced Version with Database: Run findpi_server.py
This enhanced version stores all connections in a SQLite database and provides a web interface showing hostnames, IP addresses, and timestamps. It includes several improvements:

- Persistent storage of connections in a SQLite database
- Local time display for each connection
- Clean web interface using MVP.css
- Command line options for cleaning database of old entries

#### Installation

The server can be started with the following options:
```bash
# Normal start
python findpi_server.py

# Reset database (clears all entries)
python findpi_server.py --reset
```

#### Features
- **Database Storage**: All connections are stored in a SQLite database (`messages.db`)
- **Local Time**: Timestamps are stored and displayed in local time
- **Web Interface**: Clean, responsive interface showing:
  - Hostname
  - IP Address
  - Last Update (MM/DD/YYYY HH:MM format)
- **Database Management**:
  - Automatic cleanup of test entries
  - Command line option to reset database
  - Persistent storage between server restarts

#### Security Notes
- The server listens on all network interfaces (0.0.0.0) to allow LAN connections
- Only runs on the local network, not exposed to the internet
- Database is stored locally and can be reset if needed

### NOTES
#### Permissions Issue
If you might get the following response:
```bash
python3 -m findpi_server
 * Serving Flask app 'findpi_server'
 * Debug mode: on
Permission denied
```

In the example above, I've changed the port from 80, the typical *http* port, which requires sudo permissions to *5000*.

#### Install Flask

Two Options:

##### Better: uv install
```bash
# install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
# source env
source $HOME/.local/bin/env
# initialize uv
uv init
# add flask
uv add flask
# run findpi server
uv run python findpi_server.py
```

##### Global Install 
If you need to install *flask*, and get the new *externally-managed-environment* as in:
```bash
error: externally-managed-environment

× This environment is externally managed
╰─> To install Python packages system-wide, try apt install
    python3-xyz, where xyz is the package you are trying to
    install....
```

I recommend you follow the advice on a Linux system and simply use *sudo apt install python3-flask*, to install *flask*.
 
#### Example Output of findpi_server.py:
```bash
python serverv2.py
 * Serving Flask app 'serverv2'
 * Debug mode: on
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:80
 * Running on http://192.168.1.124:80
Press CTRL+C to quit
 * Restarting with stat
 * Debugger is active!
 * Debugger PIN: 101-330-852
pitwo
192.168.1.76 - - [10/Feb/2024 16:16:36] "POST / HTTP/1.1" 200 -
pitwo
192.168.1.76 - - [10/Feb/2024 16:17:29] "POST / HTTP/1.1" 200 -
pisan
192.168.1.76 - - [11/Feb/2024 06:46:41] "POST / HTTP/1.1" 200 -
```
## Initial instance
There is a "chicken/egg" problem which can occur. If you can't initially connect to the *RPi*, how do you add the *findpi* solution?

1. My immediate solution is to connect 1:1 with the Raspberry Pi, using an ethernet cable. This creates a two element network, my PC and my *RPi*. Then apply the steps above.
2. Next up from that is to initially use the *RPi* in a small network, where its easier to connect.
3. A third solution is to create an installable image which already contains the findpi service. The make this the standard image you use, going forward. I'll detail the steps here:
### Creating a Raspberry Pi OS findpi image
*You will need to do this in a small network or tightly coupled setup as described in solution #1 above.*

1. Use Pi Imager to write the Raspberry Pi OS Lite (64-bit) to an SD card or USB drive. In the OS Customization tab, I've provided the hostname of *findpi* and as I know it will be my image, I add my publickey on the Services tab.
2. Once written, I put the SD card into my *RPi*, wait for it to boot sufficiently then login `ssh findpi.local`.
3. I follow the steps above, and once I've confirmed the service works well. I create a new image:
### Saving, shrinking and sending an image
I use a Linux laptop to perform the following steps. You can use your Raspberry Pi, however, you will need several smaller USB drives to hold the images prior to shrinking them.
```bash
# remove SD card or USB drive containing RPi image and place in Linux PC
# determine physical device
lsblk
# find specific drive "sdc", "sdd" which is the right size of RPi drive, use as input
sudo dd if=/dev/sdb of=./pibuildv3.img bs=1M status=progress
# shrink the size of the image to save space
sudo pishrink.sh -avz pibuildv3.img
wormhole send pibuildv3.img.gz
```

## Notes
1. If the *RPi* isn't connecting, it might be a problem with startup. The service logs to */boot/firmware/findpi.log*.  If you are unable to access the Pi, you may shutdown the *RPi* and examine the file via a Mac or Windows system. It will be at the root level of the */bootfs* folder.
1. If you are able to access the Pi, you may `cat /boot/firmware/findpi.log` or use `journalctl -b | grep findpi` to examine the startup log for *findpi.service* entries. 
1. Implementing the optional solution, allows you to change networks and identify your PC's new IP address. Mount the SD card on your PC and edit /bootfs/findpi_ip.txt, replacing the IP address with the new one. Put the SD card back into the *RPi*, run `python findpi_server.py` then boot the *RPi*. It will ping your server with its new address.
1. If you have multiple *RPI*'s and want to confirm which one is which, run `sudo du -h /`, which prints the size of all folders to the screen. This will make the green led light for several seconds.
1. When using *RPi Imager* software, use *Shift-Ctrl-X* to bring up the options screen.
1. Once you've confirmed you no longer need the *RPi* pinging the server, you can stop it with *sudo systemctl stop findpi.service*. The service is designed to stop running once it has successfully pinged a server.
1. As Windows has difficulty using *Bonjour*, you could consider nmap as an alternative to identify *Raspberry Pi*'s on your network. [nmap Windows Version](https://nmap.org/download.html#windows)