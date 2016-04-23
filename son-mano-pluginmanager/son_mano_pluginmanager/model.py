import logging
import os
from datetime import datetime
from mongoengine import Document, connect, StringField, DateTimeField, BooleanField, signals

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("son-mano-pluginmanger:model")
LOG.setLevel(logging.INFO)


class Plugin(Document):
    """
    This model represents a plugin that is registered to the plugin manager.
    We use mongoengine as ORM to interact with MongoDB.
    """
    uuid = StringField(unique=True, primary_key=True, required=True)
    name = StringField(required=True)
    version = StringField(required=True)
    description = StringField(required=False)
    state = StringField(required=True, max_length=16)
    registered_at = DateTimeField(default=datetime.now())
    last_heartbeat_at = DateTimeField()
    #deregistered = BooleanField(default=False)

    def __repr__(self):
        return "Plugin(uuid=%r, name=%r, version=%r)" % (self.uuid, self.name, self.version)

    def __str__(self):
        return self.__repr__()

    def save(self, **kwargs):
        super().save(**kwargs)
        LOG.debug("Saved: %s" % self)

    def to_dict(self):
        """
        Convert to dict.
        (Yes, doing it manually isn't nice but its ok with a limited number of fields and gives us more control)
        :return:
        """
        res = dict()
        res["uuid"] = self.uuid
        res["name"] = self.name
        res["version"] = self.version
        res["description"] = self.description
        res["state"] = self.state
        res["registered_at"] = str(self.registered_at)
        res["last_heartbeat_at"] = str(self.last_heartbeat_at)
        return res


def initialize(db="sonata-plugin-manager",
               host=os.environ.get("mongo_host", "127.0.0.1"),
               port=int(os.environ.get("mongo_port", 27017)),
               clear_db=True):
    db_conn = connect(db, host=host, port=port)
    LOG.info("Connected to MongoDB %r@%s:%d" % (db, host, port))
    if clear_db:
        # remove all old data from DB
        db_conn.drop_database(db)
        LOG.info("Cleared DB %r" % db)
