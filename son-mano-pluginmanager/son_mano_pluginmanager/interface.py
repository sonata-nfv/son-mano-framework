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
LOG.setLevel(logging.DEBUG)
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
