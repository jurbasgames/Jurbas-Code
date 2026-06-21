import sys
from dotenv import load_dotenv
from jurbas.agent import run_agent_loop

def main():
    load_dotenv()
    try:
        run_agent_loop()
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
