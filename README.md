P4 Runtime test tool
====

To use it, run:
```
$ ./main.py
```

Parameters:
```
usage: main.py [-h] [--p4info P4INFO] [--bmv2-json BMV2_JSON]
               [--test-json TEST_JSON]

P4Runtime Test Tool

optional arguments:
  -h, --help            show this help message and exit
  --p4info P4INFO       p4info proto in text format from p4c
  --bmv2-json BMV2_JSON
                        BMv2 JSON file from p4c
  --test-json TEST_JSON
                        Test flow entries
```

Test cases:
 - Fabric.p4
   - L2 unicast flows for single switch with two untagged hosts
