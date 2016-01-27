class CeleryConf:

    CELERY_RESULT_BACKEND = 'redis://172.17.0.2:6379/1'
    BROKER_URL = 'redis://172.17.0.2:6379/0'
    BROKER_TRANSPORT_OPTIONS = {'visibility_timeout': 600}
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT=['json']
    CELERY_TIMEZONE = 'Europe/Paris'
    CELERY_ENABLE_UTC = True


class RethinkDBConf:

    HOST = '172.17.0.3'
    DB = 'crawler'
    DURABILITY = 'soft'


ASN_FILE = 'ipasn.dat'
GEOIP2_FILE = 'GeoLite2-Country.mmdb'
REQUESTS_TIMEOUT = (5, 15)
