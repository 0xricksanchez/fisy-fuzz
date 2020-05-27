import os
import sys
import pathlib


def main():
    # python3 cleaner.py crash_dumps/
    subfolders = sorted([f.path for f in os.scandir(sys.argv[1]) if f.is_dir()])
    for entry in subfolders:
        try:
            file_list_in_entry = [f for f in os.listdir(entry) if os.path.isfile(os.path.join(entry, f))]
            vmcore = list(filter(lambda element: "vmcore" in element, file_list_in_entry))[0]
            pathlib.Path(os.path.join(entry, vmcore)).unlink()
        except:
            continue


if __name__ == "__main__":
    sys.exit(main())
