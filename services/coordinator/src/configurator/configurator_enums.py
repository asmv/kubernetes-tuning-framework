from .clients import ycsb_configurator
from .targets import cassandra_configurator, spilo_postgres_configurator, redis_configurator

import enum

class DBTarget(enum.Enum):
    cassandra = cassandra_configurator.CassandraConfigurator
    spilo_postgres = spilo_postgres_configurator.SpiloPostgresConfigurator
    redis = redis_configurator.RedisConfigurator

    def __repr__(self):
        return self.name

    @staticmethod
    def get(name):
        return DBTarget[name]

class DBClient(enum.Enum):
    ycsb = ycsb_configurator.YCSBConfigurator

    def __repr__(self):
        return self.name

    @staticmethod
    def get(name):
        return DBClient[name]