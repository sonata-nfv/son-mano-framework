"""
Adds a REST interface to the plugin manager to control plugins registered to the platfoem.
"""
import logging
import threading
from flask import Flask, request
import flask_restful as fr

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("son-mano-pluginmanger:interface")
LOG.setLevel(logging.DEBUG)
logging.getLogger("werkzeug").setLevel(logging.WARNING)


class PluginsEndpoint(fr.Resource):

    def get(self):
        LOG.warning("Not implemented: GET.")
        return "Not implemented.", 500


class PluginEndpoint(fr.Resource):

    def get(self, plugin_uuid=None):
        LOG.warning("Not implemented: GET. Arguments: plugin_uuid=%r" % plugin_uuid)
        return "Not implemented.", 500

    def delete(self, plugin_uuid=None):
        LOG.warning("Not implemented: DELETE. Arguments: plugin_uuid=%r" % plugin_uuid)
        return "Not implemented.", 500


class PluginLifecycleEndpoint(fr.Resource):

    def get(self, plugin_uuid=None):
        LOG.warning("Not implemented: GET. Arguments: plugin_uuid=%r" % plugin_uuid)
        return "Not implemented.", 500

    def put(self, plugin_uuid=None):
        LOG.warning("Not implemented: PUT. Arguments: plugin_uuid=%r" % plugin_uuid)
        return "Not implemented.", 500


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


def start(host="0.0.0.0", port=8001):
    thread = threading.Thread(target=_start_flask, args=(host, port))
    thread.daemon = True
    thread.start()
    LOG.info("Started management REST interface @ http://%s:%d" % (host, port))
