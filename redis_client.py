import redis


db = redis.Redis(socket_connect_timeout=1)
db.ping()
