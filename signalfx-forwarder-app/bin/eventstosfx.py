import gzip
import json
import os
import sys
import string
from collections import OrderedDict
from io import BytesIO

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from splunklib.searchcommands import Configuration, EventingCommand, Option, dispatch, validators  # isort:skip

from sfx_utils import get_access_token  # isort:skip

try:
    import configparser
except ImportError:
    import ConfigParser as configparser


@Configuration()
class ToSFXCommand(EventingCommand):
    """
    ## Syntax

    <command> | tosfx

    ## Description

    One or more datapoints are generated for each input event's field(s) of the
    form `gauge_*`, `counter_*` or `cumulative_counter_*`.  The metric name in
    SignalFx will be the `*` part of the field name.  Any additional fields on
    the event will be attached as dimensions to the generated datapoints.

    """

    access_token = Option()
    debug = Option(validate=validators.Boolean(), default=False)
    dry_run = Option(validate=validators.Boolean(), default=False)
    signalfx_realm = Option()
    ingest_url = Option()
    dp_endpoint = Option(default="/v2/event")

    def ensure_default_config(self):
        configs = configparser.ConfigParser(allow_no_value=True)
        local_config = os.path.abspath(os.path.join(os.getcwd(), "..", "local", "sfx.conf"))

        configs.read(local_config)

        def read_conf_value(field):
            try:
                return configs.get("setupentity", field)
            except configparser.NoOptionError:
                return None

        if not self.signalfx_realm:
            self.signalfx_realm = read_conf_value("signalfx_realm")
        if not self.ingest_url:
            self.ingest_url = read_conf_value("ingest_url")

        self.logger.error("getting access token")
        if not self.access_token:
            self.access_token = get_access_token(self.service)

    def transform(self, records):
        self.ensure_default_config()

        out = []
        payload = []
        for event in records:
            add_event_to_payload(self,event=event, payload=payload)

            if self.debug:
                event["endpoint"] = self.ingest_url + self.dp_endpoint

            out.append(event)

        self.logger.error(out)
        
        self.logger.error(payload)

        if not self.dry_run:
            resp = send_payload(
                payload=payload,
                target_url=compose_ingest_url(self.signalfx_realm, self.ingest_url, self.dp_endpoint),
                token=self.access_token,
            )
            for event in out:
                event["status"] = resp.status_code
                if resp.status_code != 200:
                    event["response_error"] = resp.content
        
        for event in out:
            yield event


def compose_ingest_url(realm, ingest_base_url, dp_endpoint):
    if realm:
        ingest_base_url = "https://ingest.%s.signalfx.com" % (realm,)

    return ingest_base_url.rstrip("/") + dp_endpoint



def add_event_to_payload(self,event, payload):
    
    eventDict = dict()
    dimensions = dict()
    properties = dict()
    timestamp = None
    eventType = None
    
    
    for key, value in event.iteritems():
        self.logger.error("key is "+str(key) + " value is "+str(value))
        if value != "":
            if key.startswith("event_"):
                eventType = value
            elif key.startswith("property_"):
                if value[0] != "_" and len(value) < 256:
                    newKey = key.replace("property_","")
                    newKey = newKey.replace(".","_")
                    self.logger.error("ALEX KEY is "+str(newKey))
                    properties[newKey] = value
            elif key == "_time":
                timestamp = int(float(value) * 1000)
            elif not key.startswith("_") and key != "punct" and not key.startswith("date_"):
                if value[0] != "_" and len(value) < 256:
                    dimensions[key.replace(".", "_")] = value
                    
    eventDict = {
        'category': 'USER_DEFINED',
        'dimensions': dimensions,
        'properties': properties,
        'timestamp': timestamp,
        'eventType': eventType,
    }
    
    payload.append(eventDict)
    
    event_payload = json.dumps(eventDict)
    #self.logger.error(event_payload)
    
    
def send_payload(payload, target_url, token):
    body = BytesIO()
    with gzip.GzipFile(fileobj=body, mode="w") as fd:
        fd.write(json.dumps(payload))
    body.seek(0)

    resp = requests.post(
        target_url,
        headers={"X-SF-TOKEN": token, "Content-Encoding": "gzip", "Content-Type": "application/json"},
        data=body.read(),
    )
    return resp


dispatch(ToSFXCommand, sys.argv, sys.stdin, sys.stdout, __name__)

