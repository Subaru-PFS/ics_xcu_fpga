from __future__ import print_function
import argparse
import sys

import testing.scopeProcedures

rig = None

def main():
    global rig
    
    parser = argparse.ArgumentParser(description="Run the BEE-to-dummy CCD preship test")
    
    parser.add_argument('--cam', type=str, help="name of cryostat to test. REQUIRED",
                        required=True)
    args = parser.parse_args()
    
    if args.cam is None:
        parser.print_help()
        sys.exit(0)
        
    rig = testing.scopeProcedures.BenchRig(sequence='preship', cam=args.cam)
    print(rig)

if __name__ == "__main__":
    main()

