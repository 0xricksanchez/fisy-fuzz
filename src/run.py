import json
import logging
import subprocess
import sys

from config import fuzzing_config


def build_tmux_session():
    subprocess.Popen(
        "tmux new -d -s fsfuzzer", shell=True, start_new_session=True, stdout=subprocess.DEVNULL,
    )


def build_new_tmux_window():
    subprocess.call("tmux new-window -t fsfuzzer", shell=True)


def to_dict(input_ordered_dict):
    return json.loads(json.dumps(input_ordered_dict))


def kill_tmux():
    subprocess.call("tmux kill-session -t fsfuzzer", shell=True, stdout=subprocess.PIPE)


def main():
    build_tmux_session()

    for i in range(len(fuzzing_config.fuzzer)):
        build_new_tmux_window()
        cmd = "python3 Fuzzer/Fuzzer.py {} {} {} '{}' {} {} {} {} {}".format(
            fuzzing_config.fuzzer[i]["name"],
            fuzzing_config.fuzzer[i]["fs_creator_vm"],
            fuzzing_config.fuzzer[i]["fuzzing_vm"],
            fuzzing_config.fuzzer[i]["mutation_engine"],
            fuzzing_config.fuzzer[i]["target_fs"],
            fuzzing_config.fuzzer[i]["target_size"],
            fuzzing_config.fuzzer[i]["populate_with_files"],
            fuzzing_config.fuzzer[i]["max_file_size"],
            fuzzing_config.fuzzer[i]["enable_dyn_scaling"],
        )
        print(cmd)
        fuzz_task = subprocess.Popen('tmux send-keys -t fsfuzzer "{}" C-m'.format(cmd), shell=True, stdout=subprocess.PIPE)
        if fuzz_task.poll() is not None:
            logging.debug("Failed to spawn at least one subprocess. Aborting!")
            kill_tmux()
            sys.exit(1)
    print("\x1b[6;30;42m" + 'Attach to tmux session via "{}"!'.format("tmux attach-session -t fsfuzzer") + "\x1b[0m")
    print("\x1b[6;30;42m" + "Ctrl+C to kill tmux session!" + "\x1b[0m")


if __name__ == "__main__":
    sys.exit(main())
