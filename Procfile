web: gunicorn subway:app
worker: celery worker -A subway.celery -l info 
beat: celery beat -A subway.celery