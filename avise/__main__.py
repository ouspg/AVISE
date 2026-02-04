"""
AVISE entrypoint.
"""
import sys
from avise import cli

def main():
    cli.main(sys.argv[1:])

if __name__=="__main__":
    main()
