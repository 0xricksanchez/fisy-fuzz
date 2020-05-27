import sys
import hashlib


def pure_trace(core_dump):
    with open(core_dump, "r") as f:
        data = f.read()
    panic_name = data.split("panic:")[1].split(":")[0].strip().split("\n")[0].strip()
    pure_stack_backtrace = data.split("KDB: stack backtrace:")[1].split("Uptime:")[0].strip()
    rem_noise = ""
    for line in pure_stack_backtrace.split("\n"):
        rem_noise += line.split("at")[1].lstrip() + "\n"
    # print(rem_noise)
    return panic_name, rem_noise


def write_sum(return_val):
    with open("/var/crash/sha256sum.txt", "w") as f:
        f.write("; ".join(return_val))


def main():
    """
    Creates a sha256 hexdigest of the pure stack backtrace functions+offsets without any noise
    """
    panic, backtrace = pure_trace(sys.argv[1])
    return_val = list()
    return_val.append(panic)
    return_val.append((hashlib.sha256(backtrace.encode()).hexdigest()))
    write_sum(return_val)


if __name__ == "__main__":
    sys.exit(main())
