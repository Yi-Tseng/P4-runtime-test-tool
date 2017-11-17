ps aux | grep fabric-test-main.py | grep -v grep | awk '{ print $2 }' | xargs kill
