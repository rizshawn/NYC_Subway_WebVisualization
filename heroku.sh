#!/bin/bash
celery worker -A subway.celery --beat -loglevel info &
gunicorn subway:app