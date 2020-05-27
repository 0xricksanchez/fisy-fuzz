import os
import sys
import glob


def find_latest_core():
    # find /var/crash -name "core*" -print0 | xargs -0 ls -t | head -n1
    list_of_files = glob.glob("/var/crash/*")
    list_of_files = [file for file in list_of_files if file.startswith("/var/crash/core")]
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file


def main():
    f = find_latest_core()
    print(f)


if __name__ == "__main__":
    sys.exit(main())
