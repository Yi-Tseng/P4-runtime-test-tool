#!/usr/bin/env python2
import os
import sys
import json
import time
import argparse

import p4runtime_lib.bmv2
import p4runtime_lib.tofino
import p4runtime_lib.helper

# object hook for josn library, use str instead of unicode object
# https://stackoverflow.com/questions/956867/how-to-get-string-objects-instead-of-unicode-from-json
def json_load_byteified(file_handle):
    return _byteify(
        json.load(file_handle, object_hook=_byteify),
        ignore_dicts=True
    )

def json_loads_byteified(json_text):
    return _byteify(
        json.loads(json_text, object_hook=_byteify),
        ignore_dicts=True
    )

def _byteify(data, ignore_dicts = False):
    # if this is a unicode string, return its string representation
    if isinstance(data, unicode):
        return data.encode('utf-8')
    # if this is a list of values, return list of byteified values
    if isinstance(data, list):
        return [ _byteify(item, ignore_dicts=True) for item in data ]
    # if this is a dictionary, return dictionary of byteified keys and values
    # but only if we haven't already byteified it
    if isinstance(data, dict) and not ignore_dicts:
        return {
            _byteify(key, ignore_dicts=True): _byteify(value, ignore_dicts=True)
            for key, value in data.iteritems()
        }
    # if it's anything else, return it in its original form
    return data

def flowStr(flow):
    matches = [str(flow['match_fields'][match_name]) for match_name in flow['match_fields']]
    matches = ' '.join(matches)
    params = [str(flow['action_params'][param_name]) for param_name in flow['action_params']]
    params = ' '.join(params)
    return "%s %s %s => %s" % (flow['table_name'], flow['action_name'], matches, params)

def installFlow(sw, flow, p4info_helper):
    table_name = flow['table_name']
    match_fields = flow['match_fields']
    action_name = flow['action_name']
    action_params = flow['action_params']
    priority = flow.get('priority') # None if not exists

    table_entry = p4info_helper.buildTableEntry(
        table_name=table_name,
        match_fields=match_fields,
        action_name=action_name,
        action_params=action_params,
        priority=priority)

    sw.WriteTableEntry(table_entry)

def readTableRules(p4info_helper, sw):
    '''
    Reads the table entries from all tables on the switch.
    :param p4info_helper: the P4Info helper
    :param sw: the switch connection
    '''
    print '\n----- Reading tables rules for %s -----' % sw.name
    for response in sw.ReadTableEntries():
        for entity in response.entities:
            entry = entity.table_entry
            # TODO For extra credit, you can use the p4info_helper to translate
            #      the IDs the entry to names
            table_name = p4info_helper.get_tables_name(entry.table_id)
            print '%s: ' % table_name,
            for m in entry.match:
                print p4info_helper.get_match_field_name(table_name, m.field_id),
                print '%r' % (p4info_helper.get_match_field_value(m),),
            action = entry.action.action
            action_name = p4info_helper.get_actions_name(action.action_id)
            print '->', action_name,
            for p in action.params:
                print p4info_helper.get_action_param_name(action_name, p.param_id),
                print '%r' % p.value,
            print

def bmv2_test(parser, p4info_file_path, bmv2_file_path, test_json_path, proto_dump_file=None):

    if not os.path.exists(p4info_file_path):
        parser.print_help()
        print "\np4info file not found: %s\nHave you run 'make'?" % p4info_file_path
        parser.exit(1)
    if not os.path.exists(bmv2_file_path):
        parser.print_help()
        print "\nBMv2 JSON file not found: %s\nHave you run 'make'?" % bmv2_file_path
        parser.exit(1)
    if not os.path.exists(test_json_path):
        parser.print_help()
        print "\nTest JSON file not found: %s" % test_json_path
        parser.exit(1)

    # Instantiate a P4 Runtime helper from the p4info file
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)

    switches_info = {}
    with open(test_json_path, 'r') as test_json:
        switches_info = json_load_byteified(test_json)

    print "Installing flows from %s" % (test_json_path)
    sws = {}

    for sw_name in switches_info:
        sw_info = switches_info[sw_name]
        sw_addr = sw_info['addr']

        sw = p4runtime_lib.bmv2.Bmv2SwitchConnection(sw_name, address=sw_addr, proto_dump_file=proto_dump_file)
        sws[sw_name] = sw
        sw.MasterArbitrationUpdate()
        sw.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print "Installed P4 Program using SetForwardingPipelineConfig on %s" % sw.name
        print "Installing flows to %s" % sw_name

        flows = sw_info['flows']
        for flow in flows:
            print "Installing flow %s" % flowStr(flow)
            installFlow(sw, flow, p4info_helper)
            print "Installed"

    try:
        print "Reading table entries every 5 seconds"
        while True:
            for sw_name in sws:
                sw = sws[sw_name]
                readTableRules(p4info_helper, sw)
            time.sleep(5)
    except KeyboardInterrupt:
        print " Shutting down."
        for sw_name in sws:
            sw = sws[sw_name]
            sw.shutdown()

def tofino_test(parser, p4info_file_path, tofino_bin_path, cxt_json_path, test_json_path, proto_dump_file=None):
    # Instantiate a P4 Runtime helper from the p4info file
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)

    switches_info = {}
    with open(test_json_path, 'r') as test_json:
        switches_info = json_load_byteified(test_json)

    print "Installing flows from %s" % (test_json_path)
    sws = {}

    for sw_name in switches_info:
        sw_info = switches_info[sw_name]
        sw_addr = sw_info['addr']

        sw = p4runtime_lib.tofino.TofinoSwitchConnection(sw_name, address=sw_addr, proto_dump_file=proto_dump_file)
        sws[sw_name] = sw
        sw.MasterArbitrationUpdate()
        sw.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       tofino_bin=tofino_bin_path,
                                       cxt_json=cxt_json_path)

        print "Installed P4 Program using SetForwardingPipelineConfig on %s" % sw.name
        print "Installing flows to %s" % sw_name

        flows = sw_info['flows']
        for flow in flows:
            try:
                print "Installing flow %s" % flowStr(flow)
                installFlow(sw, flow, p4info_helper)
                print "Installed"
            except Exception as e:
                print "Can't install the flow due to: %s" % e

    try:
        print "Reading table entries every 5 seconds"
        while True:
            for sw_name in sws:
                sw = sws[sw_name]
                readTableRules(p4info_helper, sw)
            time.sleep(5)
    except KeyboardInterrupt:
        print " Shutting down."
        for sw_name in sws:
            sw = sws[sw_name]
            sw.shutdown()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='P4Runtime Test Tool')
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
                        type=str, action="store", required=False,
                        default='./target_p4_config/fabric.p4info')
    parser.add_argument('--target', help='Test target',
                        type=str, action='store', required=False,
                        default='bmv2')
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
                        type=str, action="store", required=False,
                        default='./target_p4_config/fabric.json')
    parser.add_argument('--tofino-bin', help='Compiled Tofino binary',
                        type=str, action="store", required=False,
                        default='')
    parser.add_argument('--tofino-ctx-json', help='Compiled Tofino context json',
                        type=str, action="store", required=False,
                        default='')
    parser.add_argument('--test-json', help='Test flow entries',
                        type=str, action="store", required=False,
                        default='entries.json')
    parser.add_argument('--proto-dump-file', help='File where to dump P4Runtime entries',
                        type=str, action="store", required=False,
                        default='entries.txt')

    args = parser.parse_args()

    if args.proto_dump_file is not None:
        with open(args.proto_dump_file, 'w') as f:
            f.write("")

    if (args.target == 'bmv2'):
        bmv2_test(parser, args.p4info, args.bmv2_json, args.test_json, args.proto_dump_file)

    if (args.target == 'tofino'):
        tofino_test(parser, args.p4info, args.tofino_bin, args.tofino_ctx_json,
                    args.test_json, args.proto_dump_file)
