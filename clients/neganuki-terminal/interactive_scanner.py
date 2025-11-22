"""
Interactive Scanner CLI
=======================

Terminal-based interactive interface for the film scanner.
Provides a menu-driven interface for easy control.
"""

import sys
from pathlib import Path
from scanner_client import ScannerClient

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text):
    """Print a styled header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")


def print_menu():
    """Print the main menu."""
    print(f"\n{Colors.OKCYAN}{Colors.BOLD}Scanner Control Menu:{Colors.ENDC}")
    print(f"  {Colors.OKBLUE}1.{Colors.ENDC} Start Full Scan")
    print(f"  {Colors.OKBLUE}2.{Colors.ENDC} Get Status")
    print(f"  {Colors.OKBLUE}3.{Colors.ENDC} Pause Scan")
    print(f"  {Colors.OKBLUE}4.{Colors.ENDC} Resume Scan")
    print(f"  {Colors.OKBLUE}5.{Colors.ENDC} Capture Single Frame (RGB)")
    print(f"  {Colors.OKBLUE}6.{Colors.ENDC} Capture Single Frame (RAW)")
    print(f"  {Colors.OKBLUE}7.{Colors.ENDC} Stream Status Updates")
    print(f"  {Colors.OKBLUE}8.{Colors.ENDC} Shutdown Scanner")
    print(f"  {Colors.OKBLUE}9.{Colors.ENDC} Reconnect")
    print(f"  {Colors.FAIL}0.{Colors.ENDC} Exit")
    print()


def display_status(status):
    """Display status information in a formatted way."""
    if not status:
        print(f"{Colors.FAIL}✗ Could not retrieve status{Colors.ENDC}")
        return
    
    state = status['state']
    frame_count = status['frame_count']
    message = status.get('message', '')
    
    # Color code based on state
    if state == 'finished':
        state_color = Colors.OKGREEN
    elif state in ['error', 'camera_error', 'motor_error']:
        state_color = Colors.FAIL
    elif state == 'paused':
        state_color = Colors.WARNING
    else:
        state_color = Colors.OKBLUE
    
    print(f"\n{Colors.BOLD}Current Status:{Colors.ENDC}")
    print(f"  State: {state_color}{state}{Colors.ENDC}")
    print(f"  Frames Captured: {Colors.OKGREEN}{frame_count}{Colors.ENDC}")
    if message:
        print(f"  Message: {message}")


def status_callback(state, message, frame_count):
    """Callback for streaming status updates."""
    # Color code based on state
    if state == 'finished':
        state_color = Colors.OKGREEN
    elif state in ['error', 'camera_error', 'motor_error']:
        state_color = Colors.FAIL
    elif state == 'paused':
        state_color = Colors.WARNING
    else:
        state_color = Colors.OKBLUE
    
    status_line = f"[{state_color}{state:20}{Colors.ENDC}] Frames: {Colors.OKGREEN}{frame_count:3}{Colors.ENDC}"
    if message:
        status_line += f" | {message}"
    
    print(status_line)


def main():
    """Main interactive loop."""
    print_header("Film Scanner - Interactive Control")
    
    # Get connection details
    host = input(f"Enter scanner host [{Colors.OKCYAN}localhost{Colors.ENDC}]: ").strip() or 'localhost'
    port_input = input(f"Enter scanner port [{Colors.OKCYAN}50051{Colors.ENDC}]: ").strip()
    port = int(port_input) if port_input else 50051
    
    client = ScannerClient(host=host, port=port)
    
    if not client.connect():
        print(f"\n{Colors.FAIL}Failed to connect. Please ensure the scanner server is running.{Colors.ENDC}")
        sys.exit(1)
    
    try:
        while True:
            print_menu()
            choice = input(f"{Colors.BOLD}Enter your choice: {Colors.ENDC}").strip()
            
            if choice == '1':
                # Start full scan
                print_header("Starting Full Scan")
                if client.start_scan():
                    print(f"\n{Colors.OKGREEN}Scan started successfully!{Colors.ENDC}")
                    
                    wait = input("\nWait for completion? [Y/n]: ").strip().lower()
                    if wait != 'n':
                        client.wait_for_completion()
            
            elif choice == '2':
                # Get status
                print_header("Scanner Status")
                status = client.get_status()
                display_status(status)
            
            elif choice == '3':
                # Pause scan
                print_header("Pausing Scan")
                client.pause_scan()
            
            elif choice == '4':
                # Resume scan
                print_header("Resuming Scan")
                client.resume_scan()
            
            elif choice == '5':
                # Capture RGB frame
                print_header("Capturing RGB Frame")
                path = client.capture_frame(raw=False)
                if path:
                    print(f"\n{Colors.OKGREEN}Frame saved to: {path}{Colors.ENDC}")
            
            elif choice == '6':
                # Capture RAW frame
                print_header("Capturing RAW Frame")
                path = client.capture_frame(raw=True)
                if path:
                    print(f"\n{Colors.OKGREEN}RAW frame saved to: {path}{Colors.ENDC}")
            
            elif choice == '7':
                # Stream status
                print_header("Streaming Status Updates")
                print(f"{Colors.WARNING}Press Ctrl+C to stop streaming{Colors.ENDC}\n")
                client.stream_status(callback=status_callback)
            
            elif choice == '8':
                # Shutdown scanner
                print_header("Shutting Down Scanner")
                confirm = input(f"{Colors.WARNING}Are you sure? [y/N]: {Colors.ENDC}").strip().lower()
                if confirm == 'y':
                    client.shutdown()
            
            elif choice == '9':
                # Reconnect
                print_header("Reconnecting to Scanner")
                client.disconnect()
                if client.connect():
                    print(f"\n{Colors.OKGREEN}Reconnected successfully!{Colors.ENDC}")
            
            elif choice == '0':
                # Exit
                print_header("Exiting")
                break
            
            else:
                print(f"\n{Colors.FAIL}Invalid choice. Please try again.{Colors.ENDC}")
            
            # Pause before showing menu again
            input(f"\n{Colors.BOLD}Press Enter to continue...{Colors.ENDC}")
    
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Interrupted by user{Colors.ENDC}")
    
    finally:
        client.disconnect()
        print(f"\n{Colors.OKGREEN}Goodbye!{Colors.ENDC}\n")


if __name__ == '__main__':
    main()
