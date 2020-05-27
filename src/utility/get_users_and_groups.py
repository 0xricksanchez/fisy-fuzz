import grp
import pwd
import sys


def get_groups():
    groups = ""
    for group in grp.getgrall():
        groups += ", " + group[0]
    return groups.lstrip(",").lstrip()


def get_users():
    users = ""
    for user in pwd.getpwall():
        users += ", " + user[0]
    return users.lstrip(",").lstrip()


def main():
    """
    Fetches the Users and Groups located on a system
    """
    grps = get_groups()
    usrs = get_users()
    result = usrs + " <delim> " + grps
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
