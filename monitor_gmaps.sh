#!/bin/bash

# GMaps Scraper Live Monitor
# This script provides real-time monitoring of the google-maps-scraper process

echo "🗺️  GMaps Scraper Live Monitor Started"
echo "======================================"

# Check if process is running
if ! pgrep -f "google-maps-scraper" > /dev/null; then
    echo "❌ google-maps-scraper process not found!"
    exit 1
fi

PID=$(pgrep -f "google-maps-scraper")
echo "📍 Process PID: $PID"
echo "📂 Data Folder: /root/gmapsdata"
echo ""

# Monitor loop
while true; do
    clear
    echo "🗺️  GMaps Scraper Live Monitor - $(date)"
    echo "======================================"
    echo "📍 Process PID: $PID"
    echo "📂 Data Folder: /root/gmapsdata"
    echo ""
    
    # Show process status
    echo "📊 Process Status:"
    ps -p $PID -o pid,etime,pcpu,pmem,cmd --no-headers
    echo ""
    
    # Show latest files
    echo "📁 Latest CSV Files:"
    ls -lah /root/gmapsdata/*.csv 2>/dev/null | tail -5 | awk '{print $6 " " $7 " " $8 " " $9}'
    echo ""
    
    # Show file sizes and growth
    echo "📈 File Size Growth:"
    for file in /root/gmapsdata/*.csv; do
        if [ -f "$file" ]; then
            size=$(stat -c%s "$file" 2>/dev/null)
            name=$(basename "$file")
            printf "%-40s %s\n" "$name" "$(numfmt --to=iec $size)"
        fi
    done | sort -k2 -hr | head -5
    echo ""
    
    # Show latest entries in the most recent file
    latest_file=$(ls -t /root/gmapsdata/*.csv 2>/dev/null | head -1)
    if [ -f "$latest_file" ]; then
        echo "🔍 Latest Entries ($(basename "$latest_file")):"
        tail -3 "$latest_file" | cut -d',' -f1-3 | while IFS=',' read -r url name category; do
            echo "  📍 $name ($category)"
        done
        echo ""
    fi
    
    # Check if process is still running
    if ! kill -0 $PID 2>/dev/null; then
        echo "❌ Process $PID has stopped!"
        exit 1
    fi
    
    echo "⏰ Next update in 10 seconds... (Ctrl+C to stop)"
    sleep 10
done
