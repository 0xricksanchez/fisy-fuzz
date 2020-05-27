# [fuzzing task specs]
# List of dictionaries specifying each fuzzing instance
fuzzer = [
    {
        "name": "fuzz1",  # Name for internal bookkeeping
        "fs_creator_vm": "genBox",  # Name as specified in libvirt for the VM handling the file system generation
        "fuzzing_vm": "fuzzBox",  # Name as specified in libvirt for the VM handling the file system generation
        "mutation_engine": "radamsa, 0",  # Mutation Engine that is to be used, and size of mutation
        "target_fs": "ufs2",  # Target file system
        "target_size": 15,  # Max file system size in Megabyte
        "populate_with_files": 10,  # Amount of file that will be generated
        "max_file_size": 1024,  # Maximum file size in bytes for each generated file
        "enable_dyn_scaling": False,  # Dynamic scaling will increase the filesystem size periodically
    },
]

# [credentials]
# Credentials for the root user for the VMs
# It is expected that these are the same across all instances
user = "root"
pw = "root"
