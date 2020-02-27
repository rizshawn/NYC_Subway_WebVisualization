import os

API_KEY = os.environ.get('API_KEY') or 'dbc89e494ed6952440e02af5038d2806'

MONGO_URI = os.environ.get('MONGO_URI') or 'mongodb+srv://hunter:C8RKnWrxIgvxoXSD@cluster0-h8le0.mongodb.net/test?retryWrites=true&w=majority'

BROKER_URL=os.environ['REDIS_URL']

CELERY_RESULT_BACKEND=os.environ['REDIS_URL']