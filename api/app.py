from flask import Flask, request, jsonify, render_template, json
from flask_expects_json import expects_json
import sqlite3
from datetime import datetime

app = Flask(__name__)

journey_schema = {
    'type': 'object',
    'properties': {
        'id': {'type': 'number',
                'minimum': 0},
        'people': {'type': 'number',
                    'minimum': 0,
                    'maximum':6}
    },
    'required': ['id', 'people']
}

cars_schema = {
    'type': 'array',
    "items": {
    'type': 'object',
    'properties': {
        'id': {'type': 'number',
                'minimum': 0},
        'seats': {'type': 'number',
                    'minimum': 4,
                    'maximun':6}
    },
    'required': ['id', 'seats']
  }
}

@app.route('/status', methods=['GET'])
def status():
    return "", 200
    

@app.route('/journey', methods=['POST'])
@expects_json(journey_schema)
def add_journey():
    if request.headers['Content-Type'] != 'application/json':
        return "", 400

    journey_json = json.dumps(request.json)
    journey = json.loads(journey_json)
    try:
        sqliteConnection = sqlite3.connect('carpooling.db')
        print("Successfully Connected to SQLite")
        cursor = sqliteConnection.cursor()

        """ CHECKS IF THERE ARE CARS """
        sqlite_check_car_table_query = '''SELECT name FROM sqlite_master 
                                        WHERE type='table' AND name='car';'''
        cursor.execute(sqlite_check_car_table_query)
        #if the count is 1, then table exists if not return with message
        num_occurs = cursor.fetchall()
        if  len(num_occurs)==0 :
            return no_cars_registered()

        """ CREATE JOURNEY TABLE IF NOT EXISTS """
        sqlite_create_journey_table_query = '''CREATE TABLE IF NOT EXISTS journey (
                                    id INTEGER PRIMARY KEY,
                                    people INTEGER NOT NULL,
                                    registration_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                                    assigned_car INTEGER);'''

        cursor.execute(sqlite_create_journey_table_query)
        sqliteConnection.commit()
        print("SQLite journey table created")

        ''' FIND A CAR WITH ENOUGH EMPTY SEATS FOR THE GROUP '''
        str_people = str(journey["people"])
        available_car_id = None
        sqlite_find_available_car_query = ''' SELECT * FROM car WHERE 
                                            empty_seats >=''' + str_people
        cursor.execute(sqlite_find_available_car_query)
        available_car = cursor.fetchone()
        if available_car is not None:
            available_car_id = available_car[0]
            str_available_car_id = str(available_car_id)
            ''' update empty seats '''
            sqlite_update_available_car_query = ''' UPDATE car SET empty_seats = 
                                                empty_seats - '''+str_people + '''
                                                WHERE id = ''' + str_available_car_id
            cursor.execute(sqlite_update_available_car_query)
            sqliteConnection.commit()

        ''' ADD JOURNNEY TO DB '''
        sql_add_journey = "INSERT INTO journey VALUES (?,?,?,?)"
        dateTimeObj = datetime.now()
        journey_tuple = (journey["id"],journey["people"],dateTimeObj,available_car_id)
        cursor.execute(sql_add_journey,journey_tuple)
        sqliteConnection.commit()
        print("SQLite journey created")

        cursor.close()

    except sqlite3.Error as error:
        print("Error while creating a sqlite table", error)
    finally:
        if (sqliteConnection):
            sqliteConnection.close()
            print("sqlite connection is closed")

    return "",200


@app.route('/cars', methods=['PUT'])
@expects_json(cars_schema)
def add_cars():
    if request.headers['Content-Type'] != 'application/json':
        return "",400

    cars_json = json.dumps(request.json)

    try:
        sqliteConnection = sqlite3.connect('carpooling.db')
        """ DELETE ALL PREVIOUS DATA (JOURNEYS AND CARS """
        sqlite_delete_car_table_query = "DROP TABLE IF EXISTS car"
        sqlite_delete_journey_table_query = "DROP TABLE IF EXISTS journey"
        cursor = sqliteConnection.cursor()
        cursor.execute(sqlite_delete_car_table_query)
        print("SQLite car table deleted")
        cursor.execute(sqlite_delete_journey_table_query)
        print("SQLite journey table deleted")

        sqlite_create_car_table_query = '''CREATE TABLE IF NOT EXISTS car (
                                    id INTEGER PRIMARY KEY,
                                    seats INTEGER NOT NULL,
                                    empty_seats INTEGER NOT NULL);'''

        
        print("Successfully Connected to SQLite")
        cursor.execute(sqlite_create_car_table_query)
        sqliteConnection.commit()
        print("SQLite car table created")

        ''' ADD CARS TO DB '''
        sql_add_car = "INSERT INTO car VALUES (?,?,?)"
        cars = json.loads(cars_json)
        for car in cars:
            ''' on creation the number of seats empty are equal to the maximun '''
            car_tuple = (car["id"],car["seats"],car["seats"])
            cursor.execute(sql_add_car,car_tuple)
            sqliteConnection.commit()
            print("SQLite car created")
    
        cursor.close()

    except sqlite3.Error as error:
        print("Error while creating a sqlite table", error)
    finally:
        if (sqliteConnection):
            sqliteConnection.close()
            print("sqlite connection is closed")

    return "",200


@app.route('/dropoff', methods=['POST'])
def drop_off():
    if request.headers['Content-Type'] != 'application/x-www-form-urlencoded':
        return "",400
    journey_id = request.form.get('ID')
    
    f= open("output.txt","a+")
    f.write("\n** Dropoff **\n")

    if journey_id is None:
        return "",400
    
    #find journey
    journey_db = find_journey(journey_id)
    if journey_db is None:
        return "",404

    f.write("\njourney dropoff id =" +journey_id)
    f.write("\n journey: "+str(journey_db))
    f.close()


    #unregister journey
    unregister_journey(journey_db) 
    
    return '', 200


"""
    Unregister a group: removes a journey and release the seats 
    from the asigned car making it available for other groups givin priority
    to those which are waiting
"""
def unregister_journey(journey_db):

    f= open("output.txt","a+")
    f.write("\n** Unregister **\n")

    try:
        sqliteConnection = sqlite3.connect('carpooling.db')
        cursor = sqliteConnection.cursor()
        id_journey_str = str(journey_db[0])
        id_assigned_car = str(journey_db[3])
        sqlite_remove_journey_query = ''' DELETE FROM journey WHERE id = ''' + id_journey_str
        cursor.execute(sqlite_remove_journey_query)
        sqliteConnection.commit()
        f.write("\nremoved journey: " + id_journey_str)
        ''' updates the available number of seats if the trip was assigned to a car'''
        if id_assigned_car is not None:

            f.write("\n assigned car: " + id_assigned_car)

            ''' if there is a group waiting for a car and it fits into the car 
            we assign this group to the car '''
            # fetch the info of the car
            sqlite_find_car_query = ''' SELECT * from car WHERE id = ''' + id_assigned_car
            cursor.execute(sqlite_find_car_query)
            car = cursor.fetchone()
            car_empty_seats = car[2]
            people_leaving = journey_db[1]
            total_seats_available = car_empty_seats + people_leaving

            # fetch next group of waiting people that fits in the car
            sqlite_find_next_waiting_groups_query = ''' SELECT * FROM journey WHERE assigned_car IS NULL'''\
                + ''' AND people <= ''' + str(total_seats_available) + ''' ORDER BY registration_time ASC limit 1'''
            
            cursor.execute(sqlite_find_next_waiting_groups_query)
            waiting_group = cursor.fetchone()
            
            f.write("\n waiting group: " + str(waiting_group))
            
            # check if the result is not empty
            if waiting_group is not None: # first in queue waiting group found
                #update journey adding assigned car
                sqlite_update_journey_query = ''' UPDATE journey SET assigned_car = ''' + str(id_assigned_car) + ''' WHERE id = ''' + str(waiting_group[0])
                cursor.execute(sqlite_update_journey_query)
                sqliteConnection.commit()
                total_seats_available = total_seats_available - waiting_group[1]
            
            #update empty seats in the car
            sqlite_update_car_query = ''' UPDATE car SET empty_seats = ''' + str(total_seats_available) + ''' WHERE id = ''' + str(id_assigned_car)
            cursor.execute(sqlite_update_car_query)
            sqliteConnection.commit()

    except sqlite3.Error as error:
            print("Error while accessing journey table", error)
        
    finally:
        if (sqliteConnection):
            sqliteConnection.close()
            print("sqlite connection is closed")
        f.close()


@app.route('/locate', methods=['POST'])
def locate():
    if request.headers['Content-Type'] != 'application/x-www-form-urlencoded':
        return "",400
    
    journey_id = request.form.get('ID')
    
    if journey_id is None:
        return "",400
    
    f= open("output.txt","a+")
    f.write("\n** Locate **\n")
    f.write("\njourney_id = "+journey_id +"\n")

    #find journey
    journey_db = find_journey(journey_id)
    if journey_db is None:
        return "",404

    f.write("\n Journey: " + str(journey_db))
    f.close() 

    # if the group is waiting to be assigned
    if journey_db[3] is None:
        return no_content()

    id = journey_db[3]
    
    message = {
        'id': id
    }
    resp = jsonify(message)
    resp.status_code = 200

    return resp


""" Finds a journey from its id"""
def find_journey(journey_id):
    result = None
    try:
        sqliteConnection = sqlite3.connect('carpooling.db')
        sqlite_find_journey_query = ''' SELECT * FROM journey WHERE id = ''' + str(journey_id)
        cursor = sqliteConnection.cursor()
        cursor.execute(sqlite_find_journey_query)
        result = cursor.fetchone()
    except sqlite3.Error as error:
        print("Error while accessing journey table", error)
    
    finally:
        if (sqliteConnection):
            sqliteConnection.close()
            print("sqlite connection is closed")
    
    return result

@app.errorhandler(404)
def not_found(error=None):
    message = {
            'status': 404,
            'message': 'Not Found',
    }
    resp = jsonify(message)
    resp.status_code = 404

    return resp


@app.errorhandler(400)
def bad_request(error=None):
    message = {
            'status': 400,
            'message': 'Bad request',
    }
    resp = jsonify(message)
    resp.status_code = 400

    return resp


def no_content():
    message = {
            'status': 204,
            'message': 'No content',
    }
    resp = jsonify(message)
    resp.status_code = 204

    return resp


"""
    Response when a journey is being sent but there are no
    cars registered in the system, thus no need to store journey
    because every time cars are put into the system the db is erased
"""
def no_cars_registered(error=None):
    message = {
            'status': 409,
            'message': 'No cars registered in the system',
    }
    resp = jsonify(message)
    resp.status_code = 409

    return resp


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port = 9091) 

