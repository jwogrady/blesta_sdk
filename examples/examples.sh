#!/bin/bash

# Ensure the script is executable
# chmod +x run_blesta_commands.sh

# Function to run a blesta-cli command and display the last request
run_blesta_command() {
    echo "Running: $1"
    eval "$1"
    if [ $? -eq 0 ]; then
        echo "Command executed successfully."
    else
        echo "Command failed."
    fi
    echo "----------------------------------------"
}

# Prompt the user for confirmation to continue or exit
confirm_continue() {
    while true; do
        read -p "Do you want to continue or exit? (continue/exit): " choice
        case "$choice" in
            continue|c|C) return 0 ;;  # Proceed with the next command
            exit|e|E) echo "Exiting..."; exit 0 ;;  # Exit the script
            *) echo "Invalid input. Please type 'continue' or 'exit'." ;;
        esac
    done
}

# List of blesta-cli commands to execute
commands=(
    "blesta-cli --model clients --method getList --params status=active --last-request"
    "blesta-cli --model clients --method get --params client_id=1 --last-request"
    "blesta-cli --model services --method getList --params status=active --last-request"
    "blesta-cli --model services --method getListCount --params client_id=1 status=active"
    "blesta-cli --model services --method getAllByClient --params client_id=1 status=active --last-request"
)

# Iterate over commands and execute them
for cmd in "${commands[@]}"; do
    run_blesta_command "$cmd"
    confirm_continue
done