
#!/bin/bash
THE_PROGRAM="main.py"

# The program won't terminated by using ctrl+c, need to kill it manually.
ps aux | grep $THE_PROGRAM | grep -v grep | awk '{ print $2 }' | xargs kill
