# Sync workers avoid concurrent use of the existing shared SPARQL clients.
bind = '0.0.0.0:8000'
worker_class = 'sync'
workers = 1
threads = 1
timeout = 180
graceful_timeout = 180
accesslog = '-'
errorlog = '-'
