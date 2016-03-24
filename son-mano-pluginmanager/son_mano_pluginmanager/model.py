import logging
from datetime import datetime
from mongoengine import Document, connect, StringField, DateTimeField, BooleanField, signals

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("son-mano-pluginmanger:model")
LOG.setLevel(logging.DEBUG)


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



def initialize(db="sonata-plugin-manager", host="127.0.0.1", port=27017, clear_db=True):
    db_conn = connect(db, host=host, port=port)
    LOG.info("Connected to MongoDB %r@%s:%d" % (db, host, port))
    if clear_db:
        # remove all old data from DB
        db_conn.drop_database(db)
        LOG.info("Cleared DB %r" % db)
