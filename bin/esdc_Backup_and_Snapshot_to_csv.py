#Copyright (c) 2024, Paolo Marcheschi paolo.marcheschi@gmail.com
import subprocess
import argparse
#python3 escd_backup_snapshot_to_csv.py backup_data.csv snapshot_data.csv
#-------Change these values based on your environment-----------------------------------
es_cmd = "/home/paolo/DANUBECLOUD/es"
options = "-full 1 -extended 2 --csv"
#---------------------------------------------------------------------------------------
header_b_written = False
header_s_written = False
def get_node_backup_data(node_name, backup_file):
    global header_b_written  # Dichiarazione di header_b_written come globale
    command = f"{es_cmd} get /node/{node_name}/define/backup {options}"
    try:
        result = subprocess.run(command.split(), capture_output=True, check=True)
        data_lines = result.stdout.decode("utf-8").splitlines()
        if not header_b_written:
            with open(backup_file, "w", encoding="utf-8") as f:
                f.write("hostname;vm_uuid;dc;name;disk_id;type;node_name;zpool;desc;bwlimit;active;schedule;retention;compression;fsfreeze;backups\n")
            header_b_written = True
        with open(backup_file, "a", encoding="utf-8") as f:
            for line in data_lines[1:]:
                f.write(line + "\n")
        print(f"Backup data retrieved successfully for node {node_name}")
    except subprocess.CalledProcessError as e:
        print(f"Error during execution for node {node_name}: {e}")

def get_node_snapshot_data(node_name, backup_file):
    global header_s_written  # Dichiarazione di header_written come globale
    command = f"{es_cmd} get /node/{node_name}/storage/zones/snapshot {options}"
    try:
        result = subprocess.run(command.split(), capture_output=True, check=True)
        data_lines = result.stdout.decode("utf-8").splitlines()
        if not header_s_written:
            with open(backup_file, "w", encoding="utf-8") as f:
                f.write("node_name;hostname;vm_uuid;define;name;disk_id;note;type;created;status;size;id\n")
            header_s_written = True
        with open(backup_file, "a", encoding="utf-8") as f:
            for line in data_lines[1:]:
                f.write(f"{node_name};{line}\n")
        print(f"Snapshot data retrieved successfully for node {node_name}")
    except subprocess.CalledProcessError as e:
        print(f"Error during execution for node {node_name}: {e}")

def main(backup_file, snapshot_file):
    try:
        node_list_output = subprocess.run([es_cmd, "get", "/node/", "--csv"], capture_output=True, check=True)
        nodes = node_list_output.stdout.decode("utf-8").splitlines()
    except subprocess.CalledProcessError as e:
        print(f"Error retrieving list of nodes: {e}")
        exit(1)
    for node in nodes:
        node_name = node.strip()
        get_node_backup_data(node_name, backup_file)
        get_node_snapshot_data(node_name, snapshot_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieve backup and snapshot data for nodes.")
    parser.add_argument("backup_file", help="File to store backup data")
    parser.add_argument("snapshot_file", help="File to store snapshot data")
    args = parser.parse_args()

    main(args.backup_file, args.snapshot_file)
