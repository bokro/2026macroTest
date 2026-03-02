# Entry point to run the app from project root

import sys
from script.moverecord import moveRecord

if __name__ == '__main__':
    sys.modules['__main__'] = moveRecord
    moveRecord.main()
