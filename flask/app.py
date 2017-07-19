#!flask/bin/python
import os
from flask import Flask, jsonify, request, redirect, json,make_response,url_for
from stravalib.client import Client
from flaskext.mysql import MySQL
import time
# from flask_mysqldb import MySQL
import sys

mysql = MySQL()
# app = Flask(__name__)
# app.config['MYSQL_DATABASE_USER'] = 'root'
# app.config['MYSQL_DATABASE_PASSWORD'] = 'root'
# app.config['MYSQL_DATABASE_DB'] = 'centerparks'
# app.config['MYSQL_DATABASE_HOST'] = '127.0.0.1'
# mysql.init_app(app)

app = Flask(__name__)
app.config['MYSQL_DATABASE_USER'] = 'jonasvr'
app.config['MYSQL_DATABASE_PASSWORD'] = ''
app.config['MYSQL_DATABASE_DB'] = 'centerparks'
app.config['MYSQL_DATABASE_HOST'] = '127.0.0.1'
mysql.init_app(app)

clientId = 19003
client = Client()
authorize_url = client.authorization_url(client_id=clientId, redirect_uri='http://localhost:5000/authorized')

@app.route('/')
def index():
    cur = mysql.get_db().cursor()
    cur.execute("SELECT * FROM users")
    rv = myJsonfy(cur.fetchall())
    # user = request.cookies.get('user_id')
    return str(rv)

@app.route('/authorized', methods=['GET'])
def authorized():
    #prep insert data
    code =  request.args['code']
    access_token = client.exchange_code_for_token(client_id=clientId, client_secret='49dc3ee13e6ec7b605a23839ac92e2d94253dcaf', code=code)
    client.access_token = access_token
    athlete = client.get_athlete()
    user = athlete.firstname+ " " +athlete.lastname
    app_id = athlete.id

    #mysql -> searching user
    selectQuery = "Select id  FROM users where app_id = {}".format(app_id)
    data = dbCall(selectQuery)

    # print(data[0][0], file=sys.stderr)

    # creating user if not exist
    if(len(data) == 0):

        query = "INSERT INTO `centerparks`.`users` (`name`,`accesstoken`,`park_id`,`app_id`) VALUES ('{}','{}',{},{});"
        qr = query.format(user, access_token, 1, app_id)
        dbCall(qr)
        data = dbCall(selectQuery)
        user_id = data[0][0]
        for count in range(1, 4):
            # print(count, file=sys.stderr)
            query = "INSERT INTO `centerparks`.`stats` (`user_id`,`segment_id`,`distance`,`time`,`updated`) VALUES ('{}','{}','{}','{}','{}');"
            qr = query.format(user_id, count,'0','0','0')
            data = dbCall(qr)
            # print(data, file=sys.stderr)
    else:
        user_id = data[0][0]
    # print(user_id, file=sys.stderr)

    resp = make_response('logged in')
    resp.set_cookie('user_id', str(user_id))
    resp.set_cookie('token', access_token)
    return resp


@app.route('/login', methods=['GET'])
def login():
    if 'token' in request.cookies:
        return "already logged in"
    else:
        # return redirect("https://www.strava.com/oauth/authorize?client_id="+str(clientId)+"&response_type=code&redirect_uri=http://localhost:5000/authorized&scope=write&state=mystate&approval_prompt=force")
        return "https://www.strava.com/oauth/authorize?client_id="+str(clientId)+"&response_type=code&redirect_uri=http://localhost&scope=write&state=mystate&approval_prompt=force"
@app.route('/register')
def register():
    # return redirect("https://www.strava.com/oauth/authorize?client_id=" + str(clientId) + "&response_type=code&redirect_uri=http://localhost:5000/authorized&scope=write&state=mystate&approval_prompt=force")
    return "https://www.strava.com/oauth/authorize?client_id=" + str(clientId) + "&response_type=code&redirect_uri=http://localhost&scope=write&state=mystate&approval_prompt=force"
    # return "test"


@app.route('/logout')
def logout():
    resp = make_response('logged out')
    resp.set_cookie('user_id', expires=0)
    resp.set_cookie('token', expires=0)
    return resp


# ###################################################################
@app.route('/athlete')
# def athlete():
#     token = getToken()
#     client.access_token = token
#     athlete = client.get_athlete()
#     return athlete.lastname

@app.route('/sync')
def sync():
    user_id= int(request.cookies.get('user_id'))
    token =  request.cookies.get('token')
    client.access_token = token

    selectQuery = "Select time, distance, updated FROM stats where user_id = {}".format(user_id)
    oldData = dbCall(selectQuery)
    print("user_id = {}".format(user_id))

    Run = []
    distanceRan = 0
    Swim = []
    distanceSwam = 0
    newDate = 0
    if oldData[0][2] == 0:
        activities = client.get_activities()
    else:
        activities = client.get_activities(after="2017-02-09 19:04:15+00:00")

    for activity in activities:
        if "{0.type}".format(activity) == "Run":
            Run.append("{0.moving_time}".format(activity))
            distance = float(("{0.distance}".format(activity)).split(' ')[0])
            distanceRan = distanceRan + distance
        elif "{0.type}".format(activity) == "Swim":
            Swim.append("{0.moving_time}".format(activity))
            distance = float(("{0.distance}".format(activity)).split(' ')[0])
            distanceSwam = distanceSwam + distance
        newDate = "{0.start_date}".format(activity)

    totalRunTime = calcTotalTime(Run) + int(oldData[0][0])
    distanceRan = (distanceRan + float(oldData[0][1]))/1000

    totalSwimTime = calcTotalTime(Swim) + int(oldData[1][0])
    distanceSwam = distanceSwam + float(oldData[1][1])/1000

    print("date = {}".format(newDate))

    selectQuery = "UPDATE stats SET time = {},distance = {},updated = '{}' WHERE user_id = {} and segment_id = {};".format(totalRunTime, distanceRan, newDate, user_id,1)
    data = dbCall(selectQuery)
    selectQuery = "UPDATE stats SET time = {},distance = {},updated = '{}' WHERE user_id = {} and segment_id = {};".format(totalSwimTime,distanceSwam, newDate, user_id, 2)
    data = dbCall(selectQuery)

    return redirect(url_for('mystats'))


@app.route('/mystats')
def mystats():
    # print(request.cookies.get('user_id'), file=sys.stderr)
    user_id = int(request.cookies.get('user_id'))
    token = request.cookies.get('token')
    client.access_token = token

    selectQuery = "Select time, distance, updated FROM stats where user_id = {}".format(user_id)
    data = dbCall(selectQuery)

    view = {
       "run" : {
            "time" : secToTime(int(data[0][0])),
            "distance" : data[0][1]
        },
       "swim": {
            "time": secToTime(int(data[0][0])),
            "distance": data[0][1]
        }
    }
    return str(view)

@app.route('/parks' , methods=['GET'])
def getParks():

    selectQuery = "Select * FROM parks"
    data = dbCall(selectQuery)
    return str(data)

@app.route('/parks' , methods=['POST'])
def postParks():
    # user_id = int(request.cookies.get('user_id'))
    user_id = 54
    # token = request.cookies.get('token')
    # client.access_token = token

    park_id = request.form['park_id']
    selectQuery = "UPDATE users SET park_id = {} WHERE id = {}".format(park_id, user_id)
    data = dbCall(selectQuery)
    return str(data)

###########################################################################################################

def myJsonfy(data):
    fetchedData = json.dumps(data)
    d = json.JSONDecoder()
    data = d.decode(fetchedData)
    return data

def calcTotalTime(timeList):
    totalSecs = 0
    for tm in timeList:
        timeParts = [int(s) for s in tm.split(':')]
        totalSecs += (timeParts[0] * 60 + timeParts[1]) * 60 + timeParts[2]
    return totalSecs

def secToTime(secs):
    # secs word het aantal min, sec is de rest
    secs, sec = divmod(secs, 60)
    # hr word het aantal uur, min is de rest
    hr, min = divmod(secs, 60)
    day, hr = divmod(hr, 24)
    return "{}d {:02}h {:02}min {:02}sec".format(day, hr, min, sec)

def dbCall(query):
    connection = mysql.get_db()
    cur = connection.cursor()
    cur.execute(query)
    connection.commit()
    data = myJsonfy(cur.fetchall())
    return data

# app.run(host = os.getenv("IP",'0.0.0.0'),port=int(os.getenv("PORT",5000)))
if __name__ == '__main__':
    # app.run(host = os.getenv("IP",'0.0.0.0'),port=int(os.getenv("PORT",5000)))
    # app.run(debug=True)
    app.run(debug=True, host='0.0.0.0', port=8080)
   