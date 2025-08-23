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
            filename="~/hello.log",
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
    IP_file = "hello_ip.txt"  # Name of the file containing the IP address
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
    completed_file = "/tmp/hello_completed"

    if os.path.exists(completed_file):
        logging.info("Service has already completed 3 runs since boot. Exiting.")
        print("INFO: Service has already completed 3 runs since boot.")
        return True

    return False


def mark_completed():
    """Mark that we've completed our 3 runs"""
    completed_file = "/tmp/hello_completed"
    try:
        with open(completed_file, "w") as f:
            f.write("completed")
        logging.info("Marked service as completed after 3 runs")
    except Exception as e:
        logging.error("Error marking completion: %s", str(e))


def send_hello_request(ip, attempt_num):
    """Send a single hello request"""
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

        logging.info("Starting hello service - will attempt 3 times")

        # Find IP address
        ip = find_ip_file()

        # Unmount if we mounted
        if hadtomount:
            umount_result = os.system("sudo umount /boot/firmware")
            if umount_result != 0:
                logging.warning("Failed to unmount /boot/firmware")

        # Make 3 attempts with delays
        success_count = 0
        for attempt in range(1, 4):  # 1, 2, 3
            logging.info("Starting attempt #%d of 3", attempt)

            success = send_hello_request(ip, attempt)
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
