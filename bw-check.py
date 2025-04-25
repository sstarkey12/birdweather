#!/usr/bin/python3 bw-check.py
"""birdweather station check v1.2
This script checks the status of a birdweather station and sends the data to an MQTT broker
"""
import os
import sys
import json
from datetime import datetime, timedelta
from configparser import ConfigParser
import requests
from paho.mqtt import publish
from astral import LocationInfo
from astral.sun import sun
import pytz

CONFIG_FILENAME = 'bw-check.ini'
LOG_FILENAME = 'bw-check.log'

status_msg = 'OK'

class StationData:
    """ Class to get data from Birdweather API
    Args:
        url (str): URL of the Birdweather API
        station_id (str): ID of the Birdweather station
        period (float): Time period in hours to determine if the station is online
        (default is 1.5 hours)
        query (str): GraphQL query to get data from the Birdweather API
        json_name (str): Name of the JSON string to save data to
    """
    def __init__(self, url, station_id, **kwargs):
        self.url = url
        self.station_id = station_id
        self.period = kwargs.get("period", 1.5)
        self.query = kwargs.get("query", "")
        self.json_name = kwargs.get("json_name", "")
        self.name, self.last_detect, self.species = self.station_data()
        self.status_msg = 'OK'

    def station_data(self):
        """Get station data from the Birdweather API
        Returns:
            tuple: Station name, last detection time, and species data
        """
        debug_print('Parsing station data')
        data = json.loads(self.response().content)
        station_data = data['data']['station']
        name = station_data['name']
        last_detect = datetime.fromisoformat(station_data['latestDetectionAt'])
        raw_species_data = station_data['topSpecies']
        species = {}
        for species_data in raw_species_data:
            count = species_data["count"]
            species_common_name = species_data["species"]["commonName"]
            species[species_common_name] = count
        return name, last_detect, species

    def response(self):
        """Get response from the Birdweather API
        Returns:
            response: Response object from the Birdweather API
        """
        try:
            debug_print('Fetching data from Birdweather API')
            response_data = requests.post(self.url, json={'query': self.query},timeout=10)
        except requests.exceptions.RequestException as e:
            debug_print('ERROR FETCHING DATA: ' + str(e))
            self.status_msg = 'ERROR FETCHING DATA: ' + str(e)
            return None
        if response_data.status_code != 200:
            debug_print('BAD RESPONSE: ' + str(response_data.status_code))
            self.status_msg = 'BAD RESPONSE: ' + str(response_data.status_code)
            return None
        debug_print('Data fetched successfully')
        return response_data

    def online(self):
        """Check if the station is online based on the last detection time
        Returns:
            bool: True if the station is online, False otherwise
        """
        if self.period == '':
            self.period = 1.5
        time_current = datetime.now()
        time_current = time_current.replace(microsecond=0).astimezone()
        delta_time = time_current - self.last_detect
        delta_hours = delta_time.seconds/3600
        return bool(delta_hours <= self.period)

    @property
    def json(self):
        """Convert the species data to JSON format"""
        top_species_list = [{"name": bird_name, "count": bird_count} for bird_name,
                            bird_count in self.species.items()]
        return {self.json_name: top_species_list}

    @property
    def plain(self):
        """Convert the species data to plain text format"""
        return '\n'.join(f'{bird_name}: {bird_count}' for bird_name,
                         bird_count in self.species.items())


class Configuration:
    """Class to handle configuration file
    Args:
        filename (str): Filename of the config file to read/create.
        vars (dict): Dictionary of variables to add
        section (str): Header section or title of the config within the file
        create (bool): If True, create the config file if it doesn't exist. Default is True.
    """
    def __init__(self, filename, config_values, section, create=True):
        self.filename = filename
        self.section = section
        self.config_vars = config_values
        self.create = create
        self.config = self.import_config()
        for key in self.config:
            if not hasattr(self, key):
                setattr(self, key, self.config[key])

    def new_config(self):
        """Create new config file

        Args:
            file (str): Filename of the config file to create.
            section (str): Header section or title of the config within the file
            config_vars (dict): Dictionary of variables to add
        """
        time_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        print(f'{time_stamp}: Creating new config file {self.filename} with section {self.section}')
        config = ConfigParser()
        config[self.section] = self.config_vars
        # configfile_path = os.getcwd() + self.filename
        configfile_path = self.filename
        with open(configfile_path, 'a', encoding='utf-8') as f:
            config.write(f)
            f.close()

    def import_config(self):
        """Import configuration file variables
        If the file exists, but the section does not, it will create the section
        as long as create_if_absent is True.

        Args:
            file: Filename of the config file to read.
            section: Header section or title of the config to read in the file
            create_if_absent: If the file doesn't exist, create it. Default is True.
            config_vars: Dictionary of variables to add
        Returns:
            updated_vars: Dictionary of variables with the values from the config file
        """
        if not os.path.exists(self.filename):
            if self.create:
                self.new_config()
            else:
                return None
        imported_config = ConfigParser()
        imported_config.read(self.filename)
        try:
            imported_config_data = imported_config[self.section]
        except KeyError:
            if self.create:
                self.new_config()
                imported_config.read(self.filename)
                imported_config_data = imported_config[self.section]
            else:
                return None
        except IOError as e:
            print(f'CONFIG FILE ERROR: {e}')
            sys.exit()
        except ValueError as e:
            print(f'CONFIG FILE VALUE ERROR: {e}')
            sys.exit()
        config = {}
        #take the config file vars and put them in the new vars
        for key in self.config_vars:
            #take each of the vars in the given vars
            config_file_var = imported_config_data[key]
            config[key] = config_file_var
        return config


class MqttSender:
    """Class to send MQTT messages
    Args:
        host (str): Hostname or IP address of the MQTT broker
        port (int): Port number of the MQTT broker
        username (str): Username for the MQTT broker
        password (str): Password for the MQTT broker
    """
    def __init__(self, host, port, username, password):
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password

    def send(self, msgs):
        """Send multiple MQTT messages
        Args:
            msgs (list): List of tuples containing topic, payload, qos, and retain
        Returns:
            str: Status message
        """
        debug_print('Sending MQTT messages')
        try:
            publish.multiple(msgs, hostname=self.host, port=self.port,
                             auth={'username':self.username,'password':self.password})
            debug_print('MQTT messages sent')
            return 'OK'
        except Exception as e:
            debug_print(f"MQTT ERROR: {e}")
            return "MQTT ERROR"



def debug_print(msg):
    """Print debug message if debug is enabled (True)
    Args:
        msg (str): Message to print
    Returns:
        str: Message with timestamp
    """
    time_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    msg_out = f'{time_stamp}: {msg}'
    if debug:
        print(msg_out)
    return msg_out


def between_sunrise_sunset(latitude, longitude, timezone="America/Chicago",
                           rise_offset=-1, set_offset=1):
    """Check if the current time is between sunrise and sunset
    This function uses the Astral library to calculate the sunrise and sunset
    times for a given location and checks if the current time is between
    those times. It takes the latitude and longitude of the location,
    as well as the timezone and offsets for sunrise and sunset. The offsets
    are in hours and can be positive or negative. The function returns True
    if the current time is between sunrise and sunset, and False otherwise.

    Args:
        latitude (float): The latitude of the location
        longitude (float): The longitude of the location
        timezone (str): The timezone of the location. Defaults to "America/Chicago".
        rise_offset (int): The offset for sunrise time in hours. Defaults to -1.
        set_offset (int): The offset for sunset time in hours. Defaults to 1.
    Returns:
        bool: True if the current time is between sunrise and sunset, False otherwise
    """
    debug_print('Checking sunrise and sunset times')
    city = LocationInfo("custom", "custom", timezone, float(latitude), float(longitude))
    now_time = datetime.now(tz=pytz.timezone(timezone))
    s = sun(city.observer, now_time, tzinfo="America/Chicago")
    sunrise_offset_time = s["sunrise"] + timedelta(hours=float(rise_offset))
    sunset_offset_time = s["sunset"] + timedelta(hours=float(set_offset))
    return bool(sunrise_offset_time < now_time < sunset_offset_time)


# set up the default config variables and load the configs in
mqtt_vars = {'host': '192.168.1.1',
                'port': '1883',
                'username': 'mqtt-user',
                'password': 'mqtt-password',
                'topic': 'birdweather'}
birdweather_vars = {'station_id': '2265',
                'url': 'https://app.birdweather.com/graphql'}
location_vars = {'lat': '46.69',
                'lon': '-92.05',
                'tz': 'America/Chicago'}
config_vars = {'debug': 'False',
               'limit_times' : 'True',
               'sunrise_offset': '-1',
               'sunset_offset': '1',}
run = Configuration(CONFIG_FILENAME, config_vars, "default")
location = Configuration(CONFIG_FILENAME, location_vars, "location")
birdweather = Configuration(CONFIG_FILENAME, birdweather_vars, "birdweather")
mqtt = Configuration(CONFIG_FILENAME, mqtt_vars, "mqtt")
debug = bool(run.debug == 'True')
# print the config info if we are in debug mode
if debug:
    debug_print('Debug mode is ON')
    debug_print(f'Config file: {CONFIG_FILENAME}')
    debug_print(f'Location: {location.config}')
    debug_print(f'Birdweather: {birdweather.config}')
    debug_print(f'MQTT: {mqtt.config}')
# check if we should run the script based on sunrise and sunset times
if run.limit_times == 'True':
    if between_sunrise_sunset(location.lat, location.lon, location.tz,
                              run.sunrise_offset, run.sunset_offset):
        pass
    else:
        sys.exit()
# create hourly and daily StationData objects from the queries
hourly_query = '{station(id: ' + birdweather.config["station_id"] + '), {coords{lat, lon}, id, latestDetectionAt, name, topSpecies(limit: 10, period: {count: 1, unit: "hour"}) {count, species {commonName}, speciesId}}}'
daily_query = '{station(id: ' + birdweather.config["station_id"] + '), {coords{lat, lon}, id, latestDetectionAt, name, topSpecies(limit: 40, period: {count: 1, unit: "day"}) {count, species {commonName}, speciesId}}}'
hour = StationData(
    birdweather.url,
    birdweather.station_id,
    period=12,
    query=hourly_query,
    json_name='hourlytopspecies')
status_msg = hour.status_msg
day = StationData(
    birdweather.url,
    birdweather.station_id,
    period=12,
    query=daily_query,
    json_name='dailytopspecies')
status_msg = day.status_msg
# check if the station is online
if hour.online():
    online_status_msg = "ONLINE"
else:
    online_status_msg = "OFFLINE"
# build and send the MQTT messages
debug_print('Sending MQTT messages')
time_now = datetime.now()
time_now_iso = time_now.replace(microsecond=0).astimezone()
mqtt_topic_base = mqtt.topic + '/' + hour.name
mqtt_topic_mods = ['/stats', '/TopHourlySpecies', '/TopDailySpecies', '/TopHourlySpecies/json',
                   '/TopDailySpecies/json', '/TopHourlySpecies/plain', '/TopDailySpecies/plain','']
mqtt_payloads = ['{ "stationID":"' + hour.station_id
                 + '", "lastDetect":"' + str(hour.last_detect)
                 + '", "timeNow":"' + str(time_now_iso) + '" }',
                        json.dumps(hour.species),
                        json.dumps(day.species),
                        json.dumps(hour.json),
                        json.dumps(day.json),
                        hour.plain,
                        day.plain,
                        online_status_msg]
mqtt_msgs = []
for i in range(len(mqtt_topic_mods)):
    build_tuple = (mqtt_topic_base + mqtt_topic_mods[i], mqtt_payloads[i], 0, False)
    mqtt_msgs.append(build_tuple)
server = MqttSender(mqtt.host, mqtt.port, mqtt.username, mqtt.password)
status_msg = server.send(mqtt_msgs)
# record log message
debug_print('Writing to log file')
last_status = debug_print(f'{online_status_msg} - {status_msg}')
with open(LOG_FILENAME, 'a', encoding='utf-8') as log_file:
    log_file.write(last_status + '\n')
log_file.close()
if not debug:
    print(last_status)
