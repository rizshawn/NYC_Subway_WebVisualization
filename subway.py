import requests
import pandas as pd
import json
from bson import ObjectId

import time
from datetime import date, datetime
import pytz

import pymongo
from flask_pymongo import PyMongo
from flask import Flask, render_template, request, jsonify
from celery import Celery
import celeryconfig

from google.transit import gtfs_realtime_pb2
from protobuf_to_dict import protobuf_to_dict

from config import API_KEY, MONGO_URI, BROKER_URL, CELERY_RESULT_BACKEND

app = Flask(__name__)
app.config["MONGO_URI"] = MONGO_URI

def make_celery(app):
    celery = Celery(app.import_name, broker=BROKER_URL)
    celery.config_from_object(celeryconfig)
    celery.conf.update(app.config)
    TaskBase = celery.Task
    class ContextTask(TaskBase):
        abstract = True
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery

celery = make_celery(app)

mongo = PyMongo(app)
db = mongo.db

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)

# Creating dictionary to map stop ids to the station name
df = pd.read_csv('stops.csv')[['stop_id', 'stop_name', 'stop_lat', 'stop_lon', 'location_type', 'parent_station']]
stop_pairs = zip(df['stop_id'], df['stop_name'])
stops = dict(stop_pairs)

# Dict mapping subway lines to the proper url suffix
lines = {'1': '1', '2': '1', '3': '1', '4': '1', '5': '1', '6': '1', 
        'N': '16', 'Q': '16', 'R': '16', 'W': '16', 
        'B': '21', 'D': '21', 'F': '21', 'M': '21', 
        'A': '26', 'C': '26', 'E': '26',
        'L': '2', 'G': '31', 'J': '36', 'Z': '36', '7': '51'}

# Function to convert unix timestamp into something more readable
def read_time(stamp):
    dt_stamp = datetime.utcfromtimestamp(int(stamp))
    gdt = pytz.timezone('GMT').localize(dt_stamp)
    edt = gdt.astimezone(pytz.timezone('US/Eastern'))
    return edt.strftime('%Y-%m-%d %I:%M:%S %p')

# Function to replace aspects of the MTA feed with their more user-friendly alternatives i.e. '125th St' instead of 'A15'
# This function isn't currently being used in the app, but was in a previous version
def trip_prettify(trips):
    for trip in trips:
        if 'trip_update' in trip.keys():
            t = trip['trip_update']
            if 'stop_time_update' in t.keys():
                ss = t['stop_time_update']
                for s in ss:
                    s['arrival']['time'] = read_time(s['arrival']['time'])
                    s['departure']['time'] = read_time(s['departure']['time'])
                    try:
                        s['stop_id'] = stops[s['stop_id']]
                    except:
                        pass
        elif 'vehicle' in trip.keys():
            v = trip['vehicle']
            if 'timestamp' in v.keys():
                v['timestamp'] = read_time(v['timestamp'])
            if 'stop_id' in v.keys():
                try:
                    v['stop_id'] = stops[v['stop_id']]
                except:
                    pass
    return trips

# Function to pare down the list of trips returned to just ones that haven't started yet
# This function isn't currently being used in the app, but was in a previous version
def see_assigned(feed):
    fs = []
    for f in feed:
        if 'trip_update' in f.keys():
            t = f['trip_update']['trip']['start_date'] + ' ' + f['trip_update']['trip']['start_time']
            if datetime.strptime(t, '%Y%m%d %H:%M:%S') > datetime.now():
                fs.append(f)
        elif 'vehicle' in f.keys():
            t = f['vehicle']['trip']['start_date'] + ' ' + f['vehicle']['trip']['start_time']
            if datetime.strptime(t, '%Y%m%d %H:%M:%S') > datetime.now():
                fs.append(f)
    return fs

# Function for retrieving fresh data from the MTA
def refresh(line_num):
    feed = gtfs_realtime_pb2.FeedMessage()
    response = requests.get(f'http://datamine.mta.info/mta_esi.php?key={API_KEY}&feed_id={str(line_num)}')
    feed.ParseFromString(response.content)

    # Taking the transit data from its specific format into a dictionary
    subway_feed = protobuf_to_dict(feed)
    return subway_feed['entity']

# Function to comb through trip parts and combine those that share ids
def combine(trips):
    for i, trip in enumerate(trips):
        for trip in trips[i:]:
            if trips[i]['id'] == trip['id']:
                trips[i].update(trip)
    trips = [trip for trip in trips if 'pred_stops' in trip.keys()]
    return trips

def collect(feed):
    db.trips.drop() # Dropping the Mongo collection if one exists
    trips = []
    for t in feed:
        if 'trip_update' in t.keys() and 'stop_time_update' in t['trip_update'].keys():
            # Assigning necessary information to variables
            trip_id = t['trip_update']['trip']['trip_id']
            route_id = t['trip_update']['trip']['route_id']
            stops = t['trip_update']['stop_time_update']
            try:
                trips.append({
                    'id': trip_id,
                    'line': route_id, 
                    'pred_stops': [{'stop': stop['stop_id'], 'arrival': stop['arrival']['time']} for stop in stops]
                    })
            except KeyError: # Not every trip in the MTA feed will have arrival and departure predictions
                pass
        elif 'vehicle' in t.keys() and 'timestamp' in t['vehicle'].keys():
            tri = {'id': t['vehicle']['trip']['trip_id'], 'timestamp': t['vehicle']['timestamp']}
            try:
                tri['cs'] = t['vehicle']['stop_id']
            except:
                pass
            trips.append(tri)
    # Combine the two elements of each trip
    trips = combine(trips)
    # Dumping the collected the data into a MongoDB collection
    db.trips.insert_many(trips)
    return list(db.trips.find())

# Function to find trips that haven't started and record the first arrival time predictions in the prediction database
def record_predictions(trips):
    for t in trips:
        if db.predictions.find({'id': t['id']}).count() > 0:
            try:
                if len(t['pred_stops']) < 2:
                    db.predictions.delete_one({'id': t['id']})
            except:
                pass
        else:
            db.predictions.insert_one(t)
    return list(db.predictions.find())

# Function to find trains heading to a specific stop and sort them by arrival time
def find(tl, stop):
    trains = []
    for t in tl:
        if 'pred_stops' in t.keys():
            for s in t['pred_stops']:
                if s['stop'] == stop and s['arrival'] > time.time():
                    # Converting the timestamps and stop codes into readable versions
                    s['arrival'] = read_time(s['arrival'])
                    s['stop'] = stops[s['stop']]
                    s['id'] = t['id']
                    s['line'] = t['line']
                    trains.append(s)
    trains = sorted(trains, key=lambda i: i['arrival'])
    return trains

# Function to wipe and reset the delay database; runs every day at midnight
def reset_delays():
    db.trips.drop()
    db.predictions.drop()
    db.delays.drop()
    line_list = ['1', '2', '3', '4', '5', '6', '7', 'A', 'B', 'C',
     'D', 'E', 'F', 'G', 'H', 'J', 'L', 'M', 'N', 'Q', 'R', 'Z']

    colors = ['#EE352E', '#EE352E', '#EE352E', '#00933C', '#00933C',
     '#00933C', '#B933AD', '#2850AD', '#FF6319', '#2850AD', '#FF6319', 
     '#2850AD', '#FF6319', '#6CBE45', '#2850AD', '#996633', '#A7A9AC', 
     '#FF6319', '#FCCC0A', '#FCCC0A', '#FCCC0A', '#996633']

    delay_cache = [{'line': line_list[i], 'count': 0, 'color': colors[i]} for i in range(len(colors))]
    db.delays.insert_many(delay_cache)

# Function to match current trips with their initial predictions and add the difference in times to the delay database
def reckoning(trips):
    trips = [trip for trip in trips if 'timestamp' in trip.keys() and 'cs' in trip.keys()]
    for trip in trips:
        preds = list(db.predictions.find({'id': trip['id']}).limit(1))
        try:
            preds = preds[0]['pred_stops']
        except:
            continue
        for pred in preds:
            if pred['stop'] == trip['cs'] or pred['stop'][:-1] == trip['cs'] or pred['stop'] == trip['cs'][:-1]:
                db.delays.update_one(
                    {'line': str(trip['id'][7])},
                    {'$inc': {'count': int((trip['timestamp'] - pred['arrival']))}})
    return list(db.delays.find())

@app.route('/')
def index():
    return render_template('index.html', lines=lines, stops=stops)

@app.route('/display')
def display():
    try:
        line = request.args.get('line', type=str)
        stop = request.args.get('stop', type=str)
        station = stops[stop]
        trips = collect(refresh(lines[line]))
        trains = find(trips, stop)
        return jsonify({'data': render_template('trainfeed.html', trains=trains, stop=stop, station=station)})
    except Exception as e:
        return str(e)

@app.route('/api/feed')
def feed():
    codes = ['1', '16', '21', '26', '2', '31', '36', '51']
    feed = []
    for code in codes:
        try:
            feed += collect(refresh(code))
        except:
            pass
    return JSONEncoder().encode(feed)

@app.route('/api/predictions')
def predictions():
    codes = ['1', '16', '21', '26', '2', '31', '36', '51']
    feed = []
    for code in codes:
        try:
            feed += record_predictions(collect(refresh(code)))
        except:
            pass
    return JSONEncoder().encode(list(db.predictions.find()))

@app.route('/api/delays')
def reckon():
    codes = ['1', '16', '21', '26', '2', '31', '36', '51']
    feed = []
    for code in codes:
        try:
            feed += collect(refresh(code))
        except:
            pass
    reckoning(feed)
    return JSONEncoder().encode(list(db.delays.find()))

@app.route('/api/delays/reset')
def reset():
    reset_delays()
    return JSONEncoder().encode(list(db.delays.find()))

@celery.task
def freshen():
    codes = ['1', '16', '21', '26', '2', '31', '36', '51']
    feed = []
    for code in codes:
        try:
            feed += collect(refresh(code))
        except:
            pass
    return JSONEncoder().encode(feed)

@celery.task
def rec_pred():
    codes = ['1', '16', '21', '26', '2', '31', '36', '51']
    feed = []
    for code in codes:
        try:
            feed += record_predictions(collect(refresh(code)))
        except:
            pass
    return JSONEncoder().encode(list(db.predictions.find()))

@celery.task
def clean():
    reset_delays()
    return JSONEncoder().encode(list(db.delays.find()))

if __name__ == "__main__":
    app.run(debug=True)