"""
Copyright (c) 2015 SONATA-NFV
ALL RIGHTS RESERVED.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Neither the name of the SONATA-NFV [, ANY ADDITIONAL AFFILIATION]
nor the names of its contributors may be used to endorse or promote
products derived from this software without specific prior written
permission.

This work has been performed in the framework of the SONATA project,
funded by the European Commission under Grant number 671517 through
the Horizon 2020 and 5G-PPP programmes. The authors would like to
acknowledge the contributions of their colleagues of the SONATA
partner consortium (www.sonata-nfv.eu).
"""

"""
Adds a REST interface to the plugin manager to control plugins registered to the platfoem.
"""
import logging
import threading
import json
from flask import Flask, request
import flask_restful as fr
from mongoengine import DoesNotExist
from son_mano_pluginmanager import model

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("son-mano-pluginmanger:interface")
LOG.setLevel(logging.INFO)
logging.getLogger("werkzeug").setLevel(logging.WARNING)


class PluginsEndpoint(fr.Resource):

    def get(self):
        LOG.debug("GET plugin list")
        return [p.uuid for p in model.Plugin.objects], 200


class PluginEndpoint(fr.Resource):

    def get(self, plugin_uuid=None):
        LOG.debug("GET plugin info for: %r" % plugin_uuid)
        try:
            p = model.Plugin.objects.get(uuid=plugin_uuid)
            return p.to_dict(), 200
        except DoesNotExist as e:
            LOG.error("Lookup error: %r" % plugin_uuid)
            return {}, 404

    def delete(self, plugin_uuid=None):
        LOG.debug("DELETE plugin: %r" % plugin_uuid)
        try:
            p = model.Plugin.objects.get(uuid=plugin_uuid)
            # send lifecycle stop event to plugin
            PM.send_stop_notification(p)
            # TODO ensure that record is deleted even if plugin does not deregister itself (use a timeout?)
            return {}, 200
        except DoesNotExist as e:
            LOG.error("Lookup error: %r" % plugin_uuid)
            return {}, 404


class PluginLifecycleEndpoint(fr.Resource):

    def put(self, plugin_uuid=None):
        LOG.debug("PUT plugin lifecycle: %r" % plugin_uuid)
        try:
            p = model.Plugin.objects.get(uuid=plugin_uuid)
            # get target state from request body
            ts = json.loads(request.json).get("target_state")
            if ts is None:
                LOG.error("Malformed request: %r" % request.json)
                return {"message": "malformed request"}, 500
            if ts == "start":
                 PM.send_start_notification(p)
            elif ts == "pause":
                PM.send_pause_notification(p)
            elif ts == "stop":
                PM.send_stop_notification(p)
            else:
                return {"message": "Malformed request"}, 500
            return {}, 200
        except DoesNotExist as e:
            LOG.error("Lookup error: %r" % plugin_uuid)
            return {}, 404

# reference to plugin manager
PM = None
# setup Flask
app = Flask(__name__)
api = fr.Api(app)
# register endpoints
api.add_resource(PluginsEndpoint, "/api/plugins")
api.add_resource(PluginEndpoint, "/api/plugins/<string:plugin_uuid>")
api.add_resource(PluginLifecycleEndpoint, "/api/plugins/<string:plugin_uuid>/lifecycle")


def _start_flask(host, port):
    # start the Flask server (not the best performance but ok for our use case)
    app.run(host=host,
            port=port,
            debug=True,
            use_reloader=False  # this is needed to run Flask in a non-main thread
            )


def start(pm, host="0.0.0.0", port=8001):
    global PM
    PM = pm
    thread = threading.Thread(target=_start_flask, args=(host, port))
    thread.daemon = True
    thread.start()
    LOG.info("Started management REST interface @ http://%s:%d" % (host, port))
