# birdweather-checker
First off, I need to thank the folks over at [Birdweather](https://www.birdweather.com) -- we discovered their hardware on Kickstarter and the product is honestly, great. We got our PUC, mounted it ouside under an eave, plugged in power and it runs nearly constantly. They also offer a couple different APIs to pull data out if you want, as well as a great mobile app and website. We love our PUC! (not a paid advertisement, we really do, and really like what they offer)

This script was written so I could get more learnt on python as well as have a way to display data from my wife's Birdweather PUC via Home Assistant. I couldn't really find anything premade so I also decided to learn a little about GraphiQL API at the same time. I'm absolutely positive that anyone out there could probably build this better. I'm absolutely positive that this is probably not the best way to do what I'm trying to achieve. 

I am not a programmer. You have been warned, proceed at your own risk. I offer no guarantee, express or implied, that running this on your computer won't cause an adverse reaction, like a global thermonuclear war.

So far, I've been lucky.

## What it does
I run the script via a cron job on a LXC on my home server. It runs every 10 mins. Yeah, I probably don't need the `cd`. Right now, I am logging the terminal output to a file, but you don't need to. It'll log it automatically as well as put a message to the terminal (that you can ignore if you want `>/dev/null 2>&1`)
```
*/10 * * * * cd /home/birdweather && /usr/bin/python3 /home/birdweather/bw-check.py >> /home/birdweather/bw-check.log 
```
Running the script, it will first determine if the time you are running it is between sunrise/sunset times, it will then query the Birdweather API for a particular station. It gets the top 10 most seen birds for the last hour as well as the top 40 birds for the last day. It will send that data to an MQTT server in formatted form as well as JSON, they go to separate topics. A status message is output to the terminal and to log. 

## Prerequisites
If you're here, you probably have python and pip installed someplace. You'll need to install the following modules as well:
```
pip install paho-mqtt
pip install astral
pip install pytz
```
You need the python script `bw-check.py` as well as the file where all the configuration options are stored, `bw-check.ini`. 

You can create your own `bw-check.ini` file if you wish, or it will create one for you...probably hang a bit and throw an MQTT error, because the defaults are not applicable to you. Unless you live in my house. Honestly, this is probably the safest way, to run it the first time, so you know the file is created correctly.

## First run
After installing the required python modules you can hop into the directory and run it for the first time.
```
python3 bw-check.py
```
This is what you may see on first run, if you haven't created a `.ini` file already:
```
2025-04-24 23:22:28.195942: Creating new config file bw-check.ini with section default
2025-04-24 23:22:28.196406: Creating new config file bw-check.ini with section location
2025-04-24 23:22:28.196757: Creating new config file bw-check.ini with section birdweather
2025-04-24 23:22:28.197017: Creating new config file bw-check.ini with section mqtt
2025-04-24 23:22:34.402617: ONLINE - MQTT ERROR
```
You'll need to edit the config file now.

## bw-check.ini
```
[default]
debug = False
limit_times = True
sunrise_offset = -1
sunset_offset = 1
```
`debug`: defaults to `False`, set this to `True` to get more info to the terminal. Does not add any entries to log file, currently.

`limit_times`: defaults to `True`; using the lat/long and sunrise/set offset data, it will decide if it's within that timeframe, and if so, run; if not, exit. I set up a cron job to run this script from 0300-2300 and the offset to account for longer/shorter days when the birds are actually active, so it only runs when you expect activity. Set to `False` if you don't want to check, however all the other values still need to be present, they just won't be used. I do this because I live at a far north lattitude--summer days are looong and winter days are short.

`sunrise_offset`: defaults to `-1`, set the offset in hours before sunrise that it will begin executing the code if run; can positive or negative and use decimal like `-2.5` for two and one half hours before sunrise or `1.75` for one hour, fourty-five minutes after sunrise (don't know why you'd set this for after though...).

`sunset_offset`: defaults to `1`, same rules apply as sunrise_offset

```
[location]
lat = 46.69
lon = -92.05
tz = America/Chicago
```
`lat`: set your lattitude, for sunrise/sunset calculations

`lon`: set your longitude, for sunrise/sunset calculations

`tz`: set your timezone, in the linux format, defaults to central time, `America/Chicago`

```
[birdweather]
station_id = 2265
url = https://app.birdweather.com/graphql
```
`station_id`: set to your station ID# (not the name!)

`url`: this is the url for the Birdweather GraphiQL API endpoint. Shouldn't have to change this unless they change the url

```
[mqtt]
host = 192.168.10.10
port = 1883
username = mqtt-user
password = mqtt-user
topic = birdweather
```
`host`: the host of your MQTT server, I use an ip address at my house but if you use local domain names it should work as well, i.e. `awesome.mqtt.local` or whatever.

`port`: defaults to the MQTT default, `1883`

`username`: put in the username required to send data to your MQTT instance.

`password`: put in the password required to send data to your MQTT instance

`topic`: defaults to `birdweather`, but you can make it whatever you wish. 

## MQTT output
This format works for me, so I use it. I use the JSON data for Node-RED and use the plain text to display in text boxes in Home Assistant.

Topic organization is as follows:
```
birdweather
    {station name} = ONLINE
        stats = {"stationID":"2265","lastDetect":"YYYY-MM-DDTHH:MM:SS-TZ:TZ","timeNow":"..."}
        TopHourlySpecies = {"bird name": count, ...}
            json = {"hourlytopspecies":[{"name":"bird name", "count": count}, ...]}
            plain = bird name: count, ...
        TopDailySpecies = {"bird name": count, ...}
            json = {"dailytopspecies":[{"name":"bird name", "count": count}, ...]}
            plain = bird name: count, ...
```
For now, only one station can be queried but I will probably add the ability to search for more in the future if that's a thing that I need to do. Also, the only thing you get are bird names and how many the sensor has heard. Again, this suits my needs for now, until I think of a new 'feature' to add in the future. As is, it's quite a bit of data displayed on my little 10" HA dashboard.

## Error messages
You should see `ONLINE - OK` as a normal message, but these are the potential error messages that are output to the terminal:
```
OFFLINE
MQTT-ERROR
CONFIG FILE ERROR
BAD RESPONSE
ERROR FETCHING DATA
```
In MQTT, you will only get one of two messages:
```
ONLINE
OFFLINE
```
If you get nothing in the terminal, and nothing on MQTT, it's probably because you are not within the sunrise/set times to run and have `limit_times` set as `True`.

I send all my terminal messages to a log file, but the script will save the final log message to a `bw-check.log` file for inspection.

## Home Assistant
I added these MQTT sensors into my `configuration.yaml`:
```
mqtt:
  sensor:
    - name: "Birdweather Hourly List"
      state_topic: "birdweather/PUC-2265/TopHourlySpecies/plain"
      unique_id: e0281557-ccd9-4b6a-9081-4411eb4782d2
      json_attributes_topic: "birdweather/PUC-2265/TopHourlySpecies/json"

    - name: "Birdweather Daily List"
      state_topic: "birdweather/PUC-2265"
      json_attributes_topic: "birdweather/PUC-2265/TopDailySpecies/json"
      unique_id: ecd737ad-6275-4ea9-bfde-502d3a1ccfb3

    - name: "Birdweather PUC-2265"
      state_topic: "birdweather/PUC-2265"
      payload_available: "online"
      payload_not_available: "offline"
      json_attributes_topic: "birdweather/PUC-2265/stats"
      unique_id: 267504e2-2694-4cc8-bfc9-3947283a28cd
```
I display the hourly list in a simple markdown card on my dashboard:
```
type: markdown
content: >-
  Birdweather

  ===========


  Last Detect: {{ as_timestamp(state_attr('sensor.puc_2265', 'lastDetect' ), '%I
  %M') | int | timestamp_custom('%I:%M %p') }}


  ---

  Top Hourly Species

  ------------------

  {{ (states.sensor.birdweather_hourly_list.state) }}
tap_action:
  action: navigate
  navigation_path: /wall-tablet/birdweather
  ```
  and the daily data on a separate dashboard with another markdown card:
  ```
  <table>
  {% set birds = state_attr('sensor.birdweather_daily_list','dailytopspecies')%}
<tr>
<td><h4>Name<h3></td>
<td><h4>Count</td>
</tr>
  {% for i in range(0, birds | count ) %}
  <tr>
  <td>
  {{ birds[i]['name'] }}</td>
  <td>{{ birds[i]['count'] }}</td>
</tr>
{% endfor %}
```
I use Node-RED with an MQTT input node to catch issues and notify me. 

## More info
Feel free to take this and modify it to suit your purpose. As I mentioned, I wanted to solve a problem: let us see the birds that my wife's PUC was hearing without opening the app or going onto a computer. I also wanted to expand my knowledge of Python a bit. This is a result of the paths crossing. 

These links were handy on figureing out how to build the query, perhaps they will interest you. 

https://app.birdweather.com/graphiql

https://app.birdweather.com/api/index.html#introduction


Sláinte.

