#!/usr/bin/env python2
import argparse
import json
import os

import p4runtime_lib.bmv2
import p4runtime_lib.helper
import p4runtime_lib.tofino


# object hook for josn library, use str instead of unicode object
# https://stackoverflow.com/questions/956867/how-to-get-string-objects-instead-of-unicode-from-json
def json_load_byteified(file_handle):
    return _byteify(json.load(file_handle, object_hook=_byteify),
                    ignore_dicts=True)


def json_loads_byteified(json_text):
    return _byteify(json.loads(json_text, object_hook=_byteify),
                    ignore_dicts=True)


def _byteify(data, ignore_dicts=False):
    # if this is a unicode string, return its string representation
    if isinstance(data, unicode):
        return data.encode('utf-8')
    # if this is a list of values, return list of byteified values
    if isinstance(data, list):
        return [_byteify(item, ignore_dicts=True) for item in data]
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
    matches = [str(flow['match_fields'][match_name]) for match_name in
               flow['match_fields']]
    matches = ' '.join(matches)
    params = [str(flow['action_params'][param_name]) for param_name in
              flow['action_params']]
    params = ' '.join(params)
    return "%s %s %s => %s" % (
        flow['table_name'], flow['action_name'], matches, params)


def installFlow(sw, flow, p4info_helper):
    table_name = flow['table_name']
    match_fields = flow['match_fields']
    action_name = flow['action_name']
    action_params = flow['action_params']
    priority = flow.get('priority')  # None if not exists

    table_entry = p4info_helper.buildTableEntry(
        table_name=table_name,
        match_fields=match_fields,
        action_name=action_name,
        action_params=action_params,
        priority=priority)

    sw.WriteTableEntry(table_entry)


def readTableRules(p4info_helper, sw):
    """
    Reads the table entries from all tables on the switch.
    :param p4info_helper: the P4Info helper
    :param sw: the switch connection
    """
    print '\n----- Reading tables rules for %s -----' % sw.name
    for response in sw.ReadTableEntries():
        for entity in response.entities:
            entry = entity.table_entry
            table_name = p4info_helper.get_tables_name(entry.table_id)
            print '%s: ' % table_name,
            for m in entry.match:
                print p4info_helper.get_match_field_name(table_name,
                                                         m.field_id),
                print '%r' % (p4info_helper.get_match_field_value(m),),
            action = entry.action.action
            action_name = p4info_helper.get_actions_name(action.action_id)
            print '->', action_name,
            for p in action.params:
                print p4info_helper.get_action_param_name(action_name,
                                                          p.param_id),
                print '%r' % p.value,
            print


def do_sw_provision(sw, p4info_helper, flows):
    sw.MasterArbitrationUpdate()
    print "Pushing pipeline config to %s..." % sw.name
    if args.target == "bmv2":
        sw.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=args.bmv2_json)
    else:
        sw.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       tofino_bin=args.tofino_bin,
                                       cxt_json=args.tofino_ctx_json)

    print "Will install %d table entries on %s..." \
          % (len(flows), sw.name)
    for flow in flows:
        print flowStr(flow)
        installFlow(sw, flow, p4info_helper)

def do_provision(args):
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(args.p4info)

    with open(args.test_json, 'r') as test_json:
        switches_info = json_load_byteified(test_json)

    for sw_name in switches_info:
        sw_info = switches_info[sw_name]
        sw_addr = sw_info['addr']
        flows = sw_info['flows']

        print "\n----"
        print "Creating gRPC client for %s target %s (%s)..." \
              % (args.target, sw_name, sw_addr)
        if args.target == "bmv2":
            sw = p4runtime_lib.bmv2.Bmv2SwitchConnection(
                sw_name, address=sw_addr, proto_dump_file=args.proto_dump_file)
        else:
            sw = p4runtime_lib.tofino.TofinoSwitchConnection(
                sw_name, address=sw_addr, proto_dump_file=args.proto_dump_file)

        try:
            do_sw_provision(sw, p4info_helper, flows)
        finally:
            sw.shutdown()

    print "All set!"
    exit()


def check_args(args):
    files_to_check = [args.p4info, args.test_json]
    if args.target not in ("bmv2", "tofino"):
        parser.error("unknown target %s" % args.target)
    if args.target == 'bmv2':
        files_to_check.append(args.bmv2_json)
    if args.target == 'tofino':
        files_to_check.append(args.tofino_bin)
        files_to_check.append(args.tofino_ctx_json)
    for fpath in files_to_check:
        if fpath is None or len(fpath) == 0:
            parser.error("arg missing")
        if not os.path.exists(fpath):
            parser.error("not such file %s" % fpath)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='P4Runtime Test Tool')
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
                        type=str, action="store", required=True)
    parser.add_argument('--target', help='Test target',
                        type=str, action='store', required=False,
                        default='bmv2')
    parser.add_argument('--test-json', help='Test JSON file with table entries',
                        type=str, action="store", required=True)
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
                        type=str, action="store", required=False)
    parser.add_argument('--tofino-bin', help='Compiled Tofino binary',
                        type=str, action="store", required=False)
    parser.add_argument('--tofino-ctx-json',
                        help='Compiled Tofino context json',
                        type=str, action="store", required=False)

    args = parser.parse_args()

    check_args(args)

    args.proto_dump_file = args.test_json[0:-4] + "protobuf.txt"

    if args.proto_dump_file is not None:
        with open(args.proto_dump_file, 'w') as f:
            f.write("")

    do_provision(args)
