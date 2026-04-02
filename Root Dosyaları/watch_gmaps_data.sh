#!/bin/bash

# GMaps Real-time Data Viewer
# Shows the latest data being collected by the scraper

echo "🗺️  GMaps Real-time Data Viewer"
echo "==============================="

# Find the most recently modified CSV file
latest_file=$(ls -t /root/gmapsdata/*.csv 2>/dev/null | head -1)

if [ -z "$latest_file" ]; then
    echo "❌ No CSV files found in /root/gmapsdata/"
    exit 1
fi

echo "📁 Watching: $(basename "$latest_file")"
echo "📊 Size: $(numfmt --to=iec $(stat -c%s "$latest_file"))"
echo "🕐 Last Modified: $(stat -c%y "$latest_file")"
echo ""
echo "🔍 Live Data Feed (Ctrl+C to stop):"
echo "-----------------------------------"

# Monitor the file for changes and show new entries
while true; do
    # Get current line count
    current_lines=$(wc -l < "$latest_file")
    
    # Wait for new data
    sleep 2
    
    # Get new line count
    new_lines=$(wc -l < "$latest_file")
    
    # If file grew, show new entries
    if [ $new_lines -gt $current_lines ]; then
        echo "🆕 New entries detected:"
        tail -n $((new_lines - current_lines)) "$latest_file" | while IFS=',' read -r line; do
            # Extract name and category (fields 2 and 3)
            name=$(echo "$line" | cut -d',' -f2)
            category=$(echo "$line" | cut -d',' -f3)
            phone=$(echo "$line" | cut -d',' -f8)
            
            if [ -n "$name" ] && [ "$name" != "title" ]; then
                echo "  📍 $name"
                echo "     📂 $category"
                if [ -n "$phone" ] && [ "$phone" != "" ]; then
                    echo "     📞 $phone"
                fi
                echo ""
            fi
        done
    fi
done
