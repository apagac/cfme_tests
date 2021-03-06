#!/usr/bin/env python3
import re
import subprocess
import sys

from cfme.utils import conf


def main():
    commit = sys.argv[1]

    key_list = [key.replace(' ', '') for key in conf['gpg']['allowed_keys']]
    proc = subprocess.Popen(['git', 'verify-commit', commit], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    proc.wait()
    output = proc.stderr.read().decode('utf-8')
    if re.findall('^gpg: Good signature', output, re.M):
        gpg = re.findall('fingerprint: ([A-F0-9 ]+)', output)[0].replace(' ', '')
        if gpg in key_list:
            print("Good sig and match for {}".format(gpg))
            sys.exit(0)
    print("ERROR: Bad signature. Please sign your commits!")
    print("git output: {}".format(output))
    sys.exit(127)


if __name__ == "__main__":
    main()
