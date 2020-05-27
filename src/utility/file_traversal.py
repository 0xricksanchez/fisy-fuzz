import os
import pathlib
import sys


def get_all_dirs_in_a_path(dir_path):
    only_dirs = ""
    for f in os.scandir(dir_path):
        if f.is_dir():
            only_dirs += ", " + str(f.path)
    only_dirs += ", " + str(dir_path)
    return only_dirs.lstrip(",").lstrip()


def get_all_files_in_a_path(dir_path):
    all_files = ""
    for path, subdirs, files in os.walk(dir_path):
        for name in files:
            all_files += ", " + str(pathlib.PurePath(path, name))
        for subs in subdirs:
            all_files += ", " + str(pathlib.PurePath(path, subs))
    return all_files.lstrip(",").lstrip()


def get_only_files_in_a_path(dir_path):
    only_files = ""
    for path, subdirs, files in os.walk(dir_path):
        for name in files:
            only_files += ", " + str(pathlib.PurePath(path, name))
    return only_files.lstrip(",").lstrip()


def get_all_links_in_a_path(dir_path):
    all_links = ""
    for path, subdirs, files in os.walk(dir_path):
        for name in files:
            full_path = pathlib.Path(path, name)
            if pathlib.Path.is_symlink(full_path):
                all_links += ", " + str(full_path)
    return all_links.lstrip(",").lstrip()


def main():
    results = ""
    try:
        if sys.argv[2] == "all":
            results = get_all_dirs_in_a_path(sys.argv[1])
            results += " <delim> {}".format(get_all_files_in_a_path(sys.argv[1]))
            results += " <delim> {}".format(get_only_files_in_a_path(sys.argv[1]))
            results += " <delim> {}".format(get_all_links_in_a_path(sys.argv[1]))
        elif sys.argv[2] == "dir":
            results = get_all_dirs_in_a_path(sys.argv[1])
        elif sys.argv[2] == "files":
            results += get_all_files_in_a_path(sys.argv[1])
        elif sys.argv[2] == "file":
            results += get_only_files_in_a_path(sys.argv[1])
        elif sys.argv[2] == "link":
            results += get_all_links_in_a_path(sys.argv[1])
        print(results)
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    sys.exit(main())
