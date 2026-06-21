#!/bin/bash

# Check if a filename argument was provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <filename>"
    exit 1
fi

# Store the filename parameter
FILE="$1"

# Check if the file actually exists
if [ ! -f "$FILE" ]; then
    echo "Error: File '$FILE' not found."
    exit 1
fi

# Extract and display the checkboxes
grep -E '\[[ xX]\]' "$FILE"
