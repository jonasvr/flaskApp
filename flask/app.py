#!flask/bin/python
import os
from flask import Flask, jsonify, request, redirect, json,make_response,url_for,render_template
from stravalib.client import Client
from flaskext.mysql import MySQL
import hashlib, uuid
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
# authorize_url = client.authorization_url(client_id=clientId, redirect_uri='http://localhost:5000/authorized')

@app.route('/')
def index():
    cur = mysql.get_db().cursor()
    cur.execute("SELECT * FROM users")
    rv = myJsonfy(cur.fetchall())
    return str(rv)

@app.route('/authorized', methods=['GET'])
def authorized():
    #prep insert data
    code =  request.args['code']
    access_token = client.exchange_code_for_token(client_id=clientId, client_secret='49dc3ee13e6ec7b605a23839ac92e2d94253dcaf', code=code)
    client.access_token = access_token
    athlete = client.get_athlete()
    app_id = athlete.id

    user_id = int(request.cookies.get('user_id'))
    query = "UPDATE `centerparks`.`users` SET accesstoken = '{}', park_id = {}, app_id = {} WHERE id = {};"
    qr = query.format(access_token, 1, app_id, user_id)
    dbCall(qr)
    # creating user if not exist

    resp = make_response('linked')
    resp.set_cookie('user_id', str(user_id))
    resp.set_cookie('token', access_token)
    return resp


@app.route('/link', methods=['GET'])
def link():
    if 'token' in request.cookies:
        return "already logged in"
    else:
        # localhost
        # return redirect("https://www.strava.com/oauth/authorize?client_id="+str(clientId)+"&response_type=code&redirect_uri=http://localhost:5000/authorized&scope=write&state=mystate&approval_prompt=force")
        # cloud9
        return redirect("https://www.strava.com/oauth/authorize?client_id="+str(clientId)+"&response_type=code&redirect_uri=https://flask-app-jonasvr.c9users.io/authorized&scope=write&state=mystate&approval_prompt=force")

@app.route('/login', methods=['GET'])
def getLogin():
    return render_template("login.html")

@app.route('/login', methods=['POST'])
def postLogin():
    email = request.form['email']
    password = request.form['password']

    selectQuery = "Select salt,password,accesstoken,id FROM users where email = '{}'".format(email)
    data = dbCall(selectQuery)
    if (len(data) != 0):
        salt = data[0][0]
        logged_password = data[0][1]
        accesstoken = data[0][2]
        user_id = data[0][3]
        db_password = password + salt
        hashed_password = hashlib.md5(db_password.encode()).hexdigest()
    
        if hashed_password == logged_password:
            return jsonify(accesstoken=accesstoken,user_id = user_id,message="success")
        else:
            return jsonify(message="fail: email or password is incorrect")
    else:
        return jsonify(message="fail: email or password is incorrect")

    # return render_template("login.html")

@app.route('/register', methods=['GET'])
def getRegister():
    return render_template("register.html")

@app.route('/register', methods=['POST'])
def postRegister():
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']

    salt = uuid.uuid4().hex
    db_password = password + salt
    hashed_password = hashlib.md5(db_password.encode()).hexdigest()

    selectQuery = "Select id  FROM users where email = '{}'".format(email)
    data = dbCall(selectQuery)
    if (len(data) == 0):
        query = "INSERT INTO `centerparks`.`users` (name,email,password,salt) VALUES ('{}','{}','{}','{}');"
        qr = query.format(name, email, hashed_password,salt)
        dbCall(qr)
        data = dbCall(selectQuery)
        user_id = data[0][0]
        for count in range(1, 4):
            query = "INSERT INTO `centerparks`.`stats` (`user_id`,`segment_id`,`distance`,`time`,`updated`) VALUES ('{}','{}','{}','{}','{}');"
            qr = query.format(user_id, count, '0', '0', '0')
            data = dbCall(qr)
    else:
        user_id = data[0][0]

    resp = make_response(redirect(url_for("link")))
    resp.set_cookie('user_id', str(user_id))

    return resp


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

@app.route('/sync', methods=['POST'])
def sync():
    user_id= request.form['user_id']
    token =  request.form['token']
    client.access_token = token

    selectQuery = "Select time, distance, updated FROM stats where user_id = {}".format(user_id)
    oldData = dbCall(selectQuery)

    Run = []
    distanceRan = 0
    Swim = []
    distanceSwam = 0
    newDate = 0
    after = oldData[0][2]
    if after == 0:
        activities = client.get_activities()
    else:
        activities = client.get_activities(after=after) #after
    counter = 0
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
        counter = counter + 1
    
    if counter:
        totalRunTime = calcTotalTime(Run) + int(oldData[0][0])
        distanceRan = float(distanceRan/1000 + float(oldData[0][1]))
    
        totalSwimTime = calcTotalTime(Swim) + int(oldData[1][0])
        distanceSwam = float(distanceSwam/1000 + float(oldData[1][1]))
    
        
        selectQuery = "UPDATE stats SET time = {},distance = {},updated = '{}' WHERE user_id = {} and segment_id = {};".format(totalRunTime, distanceRan, newDate, user_id,1)
        data = dbCall(selectQuery)
        selectQuery = "UPDATE stats SET time = {},distance = {},updated = '{}' WHERE user_id = {} and segment_id = {};".format(totalSwimTime,distanceSwam, newDate, user_id, 2)
        data = dbCall(selectQuery)
        return jsonify(data=data,message="success")
    else:
        return jsonify(data=0,message="nothing to sync")

@app.route('/mystats', methods=['POST'])
def mystats():
    user_id= request.form['user_id']
    token =  request.form['token']
    client.access_token = token

    selectQuery = "Select time, distance, updated FROM stats where user_id = {}".format(user_id)
    data = dbCall(selectQuery)
    view = {
       "run" : {
            "time" : secToTime(int(data[0][0])),
            "distance" : round(float(data[0][1]), 2)
        },
       "swim": {
            "time": secToTime(int(data[1][0])),
            "distance": round(float(data[1][1]), 2)
        }
    }
    # return str(view)
    return jsonify(data=view,message="success")

@app.route('/park' , methods=['POST'])
def getPark():
    user_id = request.form['user_id']
    selectQuery = "SELECT parks.name FROM centerparks.users join parks on users.park_id = parks.id where users.id = {}".format(user_id);
    data = dbCall(selectQuery)
    return jsonify(park=data[0][0], message="success")

@app.route('/park/stats' , methods=['POST'])
def getOwnParkStats():
    user_id = request.form['user_id']
    selectQuery = "SELECT `segments`.`name`, sum(stats.distance) as distance, sum(stats.time) as time FROM centerparks.users join parks on users.park_id = parks.id join stats on users.id = stats.user_id join segments on stats.segment_id = segments.id where users.id = {} group by stats.segment_id".format(user_id);
    data = dbCall(selectQuery)
    for x in data:
        x[2]=secToTime(x[2])
        x[1]=round(float(x[1]),2)
    return jsonify(stats=data, message="success")

@app.route('/parks/stats' , methods=['GET'])
def getAllParkStats():
    selectQuery = "SELECT `segments`.`name` ,  `parks`.`name` , sum(stats.distance) as distance, sum(stats.time) FROM centerparks.users JOIN parks ON users.park_id = parks.id JOIN stats ON users.id = stats.user_id JOIN segments ON stats.segment_id = segments.id GROUP BY parks.id, stats.segment_id";
    data = dbCall(selectQuery)
    for x in data:
        x[3]=secToTime(x[3])
        x[2]=round(float(x[2]),2)
    return jsonify(stats=data, message="success")

@app.route('/parks' , methods=['GET'])
def getParks():

    selectQuery = "Select * FROM parks"
    data = dbCall(selectQuery)
    return jsonify(parks=data, message="success")

@app.route('/parks' , methods=['POST'])
def postParks():
    park_id = request.form['park_id']
    user_id = request.form['user_id']
    selectQuery = "UPDATE users SET park_id = {} WHERE id = {}".format(park_id, user_id)
    data = dbCall(selectQuery)
    return jsonify(data=data,message="success")

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
    return "{}d {:02}h {:02}min {:02}sec".format(int(day), int(hr), int(min), int(sec))

def dbCall(query):
    connection = mysql.get_db()
    cur = connection.cursor()
    cur.execute(query)
    connection.commit()
    data = myJsonfy(cur.fetchall())
    return data


def test():
    return "test"

# app.run(host = os.getenv("IP",'0.0.0.0'),port=int(os.getenv("PORT",5000)))
if __name__ == '__main__':
    app.run(host = os.getenv("IP",'0.0.0.0'),port=int(os.getenv("PORT",5000)))
    # app.run(debug=True)
    # app.run(debug=True, host='0.0.0.0', port=8080)
   