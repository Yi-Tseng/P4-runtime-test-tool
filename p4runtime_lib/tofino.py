# Copyright 2017-present Open Networking Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import struct
from switch import SwitchConnection
from p4.tmp import p4config_pb2


def buildDeviceConfig(prog_name="sample", tofino_bin=None, cxt_json=None):
    "Builds the device config for Tofino based switch"
    device_config = p4config_pb2.P4DeviceConfig()
    device_config.reassign = True

    with open(tofino_bin) as tofino_bin_f:
        with open(cxt_json) as cxt_json_f:
            device_config.device_data = ""
            device_config.device_data += struct.pack("<i", len(prog_name))
            device_config.device_data += prog_name
            tofino_bin = tofino_bin_f.read()
            device_config.device_data += struct.pack("<i", len(tofino_bin))
            device_config.device_data += tofino_bin
            cxt_json = cxt_json_f.read()
            device_config.device_data += struct.pack("<i", len(cxt_json))
            device_config.device_data += cxt_json
    return device_config

class TofinoSwitchConnection(SwitchConnection):
    def buildDeviceConfig(self, **kwargs):
        return buildDeviceConfig(**kwargs)
