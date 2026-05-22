# Help, health, and version flags
if [[ "$1" == "--help" ]]; then
    echo "Usage: $0 [--help|--health|--version]"
    echo "  --help     Show this help message."
    echo "  --health   Print OK if the script is available."
    echo "  --version  Print script version."
    exit 0
elif [[ "$1" == "--health" ]]; then
    echo "OK"
    exit 0
elif [[ "$1" == "--version" ]]; then
    echo "find_apache2_containers.sh version 1.0 (2026-03-14)"
    exit 0
fi
# Health and version flags
if [[ "$1" == "--health" ]]; then
    echo "OK"
    exit 0
elif [[ "$1" == "--version" ]]; then
    echo "find_apache2_containers.sh version 1.0 (2026-03-14)"
    exit 0
fi


###############################################################################
#  find_apache2_containers.sh
#
#  List all apache2 processes and show which (if any) Docker container they
#  belong to.
#
#  For each apache2 process running on the host, this script checks its cgroup
#  to determine if it is running inside a Docker container, and if so, attempts
#  to resolve the container name. Useful for debugging web server deployments
#  and container isolation.
#
#  Usage:
#      ./find_apache2_containers.sh
#
#  Output:
#      Prints the PID and container name (if any) for each apache2 process.
#
#  Requirements:
#      - Docker must be installed and running.
#      - Script should be run on the Docker host.
#
#  Author:      homelab-user
#  Date:        2026-03-14
###############################################################################

# Get all apache2 PIDs
pids=$(pgrep apache2)


for pid in $pids; do
    # Get cgroup info
    cgroup=$(cat /proc/$pid/cgroup 2>/dev/null | grep -Eo '[0-9a-f]{64}')
    if [[ -n "$cgroup" ]]; then
        container_id=$cgroup
        container_name=$(docker ps --no-trunc --format '{{.ID}} {{.Names}}' | grep "^$container_id" | awk '{print $2}')
        if [[ -n "$container_name" ]]; then
            echo "PID $pid is in Docker container: $container_name ($container_id)"
        else
            echo "PID $pid is in Docker container: $container_id (name not found)"
        fi
    else
        echo "PID $pid is NOT in a Docker container."
    fi
done