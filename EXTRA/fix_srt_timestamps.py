#!/usr/bin/env python3
"""
SRT Timestamp Sorter and Overlap Fixer

This script:
1. Parses an SRT file.
2. Sorts subtitles by start timestamp.
3. Adjusts end timestamps to avoid overlaps.
4. Writes a corrected SRT file.

Author: AI Assistant
Date: July 31, 2025
"""

# python3 fix_srt_timestamps.py -i input.srt -o output.srt

import re
from datetime import timedelta
import argparse

def parse_srt_time(time_str):
    """Convert SRT timestamp (HH:MM:SS,mmm) to timedelta."""
    match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', time_str.strip())
    if not match:
        raise ValueError(f"Invalid timestamp format: {time_str}")
    hours, minutes, seconds, milliseconds = map(int, match.groups())
    return timedelta(hours=hours, minutes=minutes, seconds=seconds, milliseconds=milliseconds)

def format_srt_time(td):
    """Convert timedelta to SRT timestamp format (HH:MM:SS,mmm)."""
    total_ms = int(td.total_seconds() * 1000)
    hours = total_ms // (3600 * 1000)
    minutes = (total_ms // (60 * 1000)) % 60
    seconds = (total_ms // 1000) % 60
    milliseconds = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def parse_srt_file(input_file):
    """Parse SRT file into a list of subtitle entries."""
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    entries = []
    blocks = re.split(r'\n\s*\n', content)
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        try:
            index = int(lines[0])
            time_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})', lines[1])
            if not time_match:
                continue
            start_time = parse_srt_time(time_match.group(1))
            end_time = parse_srt_time(time_match.group(2))
            text = '\n'.join(lines[2:])
            entries.append({
                'index': index,
                'start': start_time,
                'end': end_time,
                'text': text
            })
        except (ValueError, IndexError):
            continue
    return entries

def fix_srt_timestamps(entries):
    """Sort entries by start time and fix overlaps."""
    # Sort by start time
    entries.sort(key=lambda x: x['start'])
    
    # Fix overlaps
    for i in range(len(entries) - 1):
        current = entries[i]
        next_entry = entries[i + 1]
        # If current end time overlaps with next start time, adjust end time
        if current['end'] > next_entry['start']:
            current['end'] = next_entry['start']
        # Ensure end time is after start time
        if current['end'] <= current['start']:
            current['end'] = current['start'] + timedelta(milliseconds=500)  # Minimum duration
    
    # Reassign indices
    for i, entry in enumerate(entries, 1):
        entry['index'] = i
    
    return entries

def write_srt_file(entries, output_file):
    """Write corrected entries to a new SRT file."""
    with open(output_file, 'w', encoding='utf-8') as f:
        for entry in entries:
            f.write(f"{entry['index']}\n")
            f.write(f"{format_srt_time(entry['start'])} --> {format_srt_time(entry['end'])}\n")
            f.write(f"{entry['text']}\n\n")

def main():
    parser = argparse.ArgumentParser(description="Sort and fix SRT timestamps.")
    parser.add_argument('-i', '--input', type=str, required=True, help='Path to input SRT file')
    parser.add_argument('-o', '--output', type=str, default='output.srt', help='Path to output SRT file')
    args = parser.parse_args()

    try:
        # Parse input file
        entries = parse_srt_file(args.input)
        if not entries:
            print("No valid subtitle entries found.")
            return
        
        # Fix timestamps
        fixed_entries = fix_srt_timestamps(entries)
        
        # Write output file
        write_srt_file(fixed_entries, args.output)
        print(f"Corrected SRT file created: {args.output}")
        
        # Print summary
        print(f"Processed {len(entries)} subtitle entries.")
        
    except FileNotFoundError:
        print(f"Error: Input file {args.input} not found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
