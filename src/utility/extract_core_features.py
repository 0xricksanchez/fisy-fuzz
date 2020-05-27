#!/usr/bin/env python3

import hashlib
import re
import sys


def get_panic_name(data):
    return (
        str(data)
        .split("panic:")[1]
        .split(":")[0]
        .split("(")[0]
        .split("bp")[0]
        .split("fip")[0]
        .split("\\")[0]
        .split(", addr:")[0]
        .strip()
        .replace(" ", "_")
        .split("_/")[0]
    )


def get_core_details(data):
    full_strace = (
        str(data)
        .split("KDB: stack backtrace:")[1]
        .split("--- syscall")[0]
        .split("Uptime")[0]
        .replace("\\", "\n")
        .replace("\nn", "\n")
        .strip()
    )
    clean_strace = ""
    for line in full_strace.split("\n"):
        if re.match(r"---\strap\s", line):
            continue
        if re.match(r"#[0-9]{1,3}\s0x[0-9a-f]{0,16}\sat\s", line):
            clean_strace += line.split(" at ")[1] + "\n"
        else:
            clean_strace += line.split("/frame")[0] + "\n"
    return clean_strace


def get_sha256_sum(sanitized_stack_trace):
    return hashlib.sha256(sanitized_stack_trace.encode()).hexdigest()


def main():
    with open(sys.argv[1], "rb") as f:
        data = f.read()

    clean_stack_trace = get_core_details(data)
    print(get_sha256_sum(clean_stack_trace))


if __name__ == "__main__":
    sys.exit(main())
