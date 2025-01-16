"""Client terminal application."""
from console.service import client

def main():
    print("Terminal client for the Nexus service.")
    print("Type 'help' for a list of commands.")
    
    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if not user_input:
            continue

        parts = user_input.split()
        command = parts[0].lower()

        if command in ("exit", "quit"):
            print("Exiting...")
            break

        elif command == "help":
            client.help_menu()

        elif command == "health":
            client.health()

        elif command == "get":
            client.get_acquisition_parameter()

        elif command == "set":
            # Example: set param1=10 param2="hello world"
            # We want to parse param1=10, param2="hello world"
            # into a dictionary: {"param1": "10", "param2": "hello world"}
            params = {}
            for assignment in parts[1:]:
                try:
                    key, value = assignment.split("=", 1)
                    # Remove any surrounding quotes from the value
                    value = value.strip('"').strip("'")
                    params[key] = value
                except ValueError:
                    print(f"Invalid syntax: {assignment}")
            if params:
                client.set_acquisition_parameter(params)
            else:
                print("No parameters given. Usage: set param1=val param2=val ...")

        elif command == "submit":
            # Example: submit sequence="my_test_sequence"
            # or      submit sequence=filename.seq
            # We'll build a JSON body with the parsed key-value pairs
            data = {}
            for assignment in parts[1:]:
                try:
                    key, value = assignment.split("=", 1)
                    # Remove any surrounding quotes from the value
                    value = value.strip('"').strip("'")
                    data[key] = value
                except ValueError:
                    print(f"Invalid syntax: {assignment}")
            if data:
                client.submit_sequence(data)
            else:
                print("No sequence data provided. Usage: submit sequence=val")

        elif command == "status":
            # Example: status JOB_ID
            if len(parts) < 2:
                print("Usage: status <job_id>")
            else:
                job_id = parts[1]
                client.get_job_status(job_id)

        else:
            print(f"Unknown command: {command}")
            print("Type 'help' for a list of available commands.")

if __name__ == "__main__":
    main()
