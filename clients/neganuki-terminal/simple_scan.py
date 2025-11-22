#!/usr/bin/env python3
"""
Simple Scan Script
==================

Simplified script for quick scanning operations.
Ideal for automation or simple scanning tasks.
"""

import sys
from pathlib import Path
from scanner_client import ScannerClient


def quick_scan(host='localhost', port=50051):
    """
    Perform a quick scan with default settings.
    
    Usage:
        python simple_scan.py
        python simple_scan.py --host 192.168.1.100
    """
    print("=== Quick Film Scanner ===\n")
    
    client = ScannerClient(host=host, port=port)
    
    # Connect
    if not client.connect():
        print("ERROR: Could not connect to scanner")
        return False
    
    try:
        # Start scan
        print("Starting scan...")
        if not client.start_scan():
            return False
        
        # Wait for completion
        success = client.wait_for_completion()
        
        if success:
            status = client.get_status()
            if status:
                print(f"\n✓ Scan complete! Captured {status['frame_count']} frames")
        
        return success
    
    finally:
        client.disconnect()


def capture_test_frame(host='localhost', port=50051, raw=False):
    """
    Capture a single test frame.
    
    Usage:
        python simple_scan.py --test
        python simple_scan.py --test --raw
    """
    print("=== Test Frame Capture ===\n")
    
    client = ScannerClient(host=host, port=port)
    
    if not client.connect():
        print("ERROR: Could not connect to scanner")
        return False
    
    try:
        frame_type = "RAW" if raw else "RGB"
        print(f"Capturing {frame_type} frame...")
        
        path = client.capture_frame(raw=raw)
        
        if path:
            print(f"\n✓ Frame captured successfully!")
            print(f"  Path: {path}")
            return True
        else:
            print("\n✗ Frame capture failed")
            return False
    
    finally:
        client.disconnect()


def monitor_scan(host='localhost', port=50051):
    """
    Monitor an ongoing scan with real-time status updates.
    
    Usage:
        python simple_scan.py --monitor
    """
    print("=== Scan Monitor ===\n")
    print("Connecting to scanner...")
    
    client = ScannerClient(host=host, port=port)
    
    if not client.connect():
        print("ERROR: Could not connect to scanner")
        return False
    
    try:
        print("Monitoring scan progress (Ctrl+C to stop)...\n")
        client.stream_status()
        return True
    
    finally:
        client.disconnect()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple Film Scanner Client')
    parser.add_argument('--host', default='localhost', help='Scanner host')
    parser.add_argument('--port', type=int, default=50051, help='Scanner port')
    parser.add_argument('--test', action='store_true', help='Capture a test frame instead of scanning')
    parser.add_argument('--raw', action='store_true', help='Capture RAW frame (use with --test)')
    parser.add_argument('--monitor', action='store_true', help='Monitor an ongoing scan')
    
    args = parser.parse_args()
    
    try:
        if args.monitor:
            success = monitor_scan(host=args.host, port=args.port)
        elif args.test:
            success = capture_test_frame(host=args.host, port=args.port, raw=args.raw)
        else:
            success = quick_scan(host=args.host, port=args.port)
        
        sys.exit(0 if success else 1)
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
