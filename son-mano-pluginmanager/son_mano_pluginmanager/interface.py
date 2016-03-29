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


# setup Flask
app = Flask(__name__)
api = fr.Api(app)
# define endpoints
# TODO


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
