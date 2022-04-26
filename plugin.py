"""
<plugin key="Espresense" name="Espresense" version="0.1-beta">
    <description>
        <h2>Espresense Plugin (v. 0.1-beta)</h2>
        <p>Plugin to add support for</p>
        <p><a href="https://espresense.com">espresense</a></p>
    </description>
    <params>
        <param field="Address" label="MQTT Server address" width="300px" required="true" default="127.0.0.1"/>
        <param field="Port" label="Port" width="300px" required="true" default="1883"/>
        <param field="Username" label="MQTT Username (optional)" width="300px" required="false" default=""/>
        <param field="Password" label="MQTT Password (optional)" width="300px" required="false" default="" password="true"/>
        <param field="Mode3" label="MQTT Client ID (optional)" width="300px" required="false" default=""/>
        <param field="Mode1" label="Espresense Topic" width="300px" required="true" default="espresense/devices"/>
        <param field="Mode2" label="Device investigation (space delimited)" width="300px"/>
        <param field="Mode4" label="Exclude list" width="300px"/>
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="Verbose" value="Verbose"/>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal" default="true" />
            </options>
        </param>
    </params>
</plugin>
"""
import DomoticzEx as Domoticz
import domoticz
import os
from mqtt import MqttClient
import time
import json
from collections import defaultdict

def find_device(self, dev_id):
	if dev_id not in Devices:
		mySwitchUnit = Domoticz.Unit(Name=dev_id, DeviceID=dev_id, Unit=1, Type=244, Subtype=73, Switchtype=0, Options={}, Used=1, Description="")
		mySwitchUnit.Create()
		myTextUnit = Domoticz.Unit(Name=dev_id, DeviceID=dev_id, Unit=2, TypeName="General", Subtype=19, Options={}, Used=1, Description="")
		myTextUnit.Create()
	else:
		mySwitchUnit = Devices[dev_id].Units[1]
		myTextUnit = Devices[dev_id].Units[2]
	return mySwitchUnit, myTextUnit
	
def find_room(self, dev_id):
	dist=10
	roomname=""
	for room in self.rooms:
		if dev_id in self.rooms[room]:
			if self.rooms[room][dev_id]['distance'] < dist:
				dist = self.rooms[room][dev_id]['distance']
				roomname=room
	return(roomname, dist)

def prune_table(self, now):
	num_rooms=len(self.rooms)
	for room in list(self.rooms):
		for dev in list(self.rooms[room]):
			if (now - self.rooms[room][dev]['timestamp']) > 10:
				domoticz.debug("Dev " + dev + " in room " + room +  " is older than 10 seconds so delete")
				del(self.rooms[room][dev])

class BasePlugin:
	mqttClient = None

	def onStart(self):
		self.debugging = Parameters["Mode6"]
	
		if self.debugging == "Verbose":
			Domoticz.Debugging(2+4+8+16+64)
		if self.debugging == "Debug":
			Domoticz.Debugging(2)

		self.base_topic = Parameters["Mode1"].strip()
		mqtt_server_address = Parameters["Address"].strip()
		mqtt_server_port = Parameters["Port"].strip()
		mqtt_client_id = Parameters["Mode3"].strip()
		self.mqttClient = MqttClient(mqtt_server_address, mqtt_server_port, mqtt_client_id, self.onMQTTConnected, self.onMQTTDisconnected, self.onMQTTPublish, self.onMQTTSubscribed)
		self.rooms = {}
		self.prequal = Parameters["Mode2"].split(" ")
		self.prequal = [q.strip() for q in self.prequal]
		self.ignore = Parameters["Mode4"]
		self.unique_apples = []
		self.last_unique_apples=""
		self.hbc=0

	def onStop(self):
		domoticz.debug("onStop called")

	def onCommand(self, device_id, unit, command, Level, Color):
		domoticz.debug("onCommand called")

	def onConnect(self, Connection, Status, Description):
		domoticz.debug("onConnect called")
		self.mqttClient.onConnect(Connection, Status, Description)

	def onDisconnect(self, Connection):
		self.mqttClient.onDisconnect(Connection)

	def onMessage(self, Connection, Data):
		self.mqttClient.onMessage(Connection, Data)

	def onHeartbeat(self):
		self.mqttClient.onHeartbeat()
		num_dev=len(Devices)
		found=False
		apstr = ""
		self.hbc += 1

		for dev in Devices:
			domoticz.debug("Iterating through " + str(dev))
			num_rooms=len(self.rooms)
			for room in self.rooms:
				domoticz.debug("Check room " + room)
				domoticz.debug("Check room " + str(self.rooms[room]))
				if dev in self.rooms[room]:
					domoticz.debug("Found dev " + dev + " in room " + room)
					found=True
			if not found:
				domoticz.debug("Switching device " + str(dev) + "off as it's gone")
				switchdev, textdev = find_device(self, dev)
				switchdev.nValue=0
				switchdev.Update(Log=True)
				textdev.sValue="Gone"
				textdev.Update(Log=True)
			found=False

		if self.hbc == 6:
			for apple in self.unique_apples:
				apstr += apple
				apstr += " "

			if apstr != self.last_unique_apples:
				self.last_unique_apples = apstr
				for room in self.rooms:
					domoticz.debug("pushing the query string for dev "+room+" with "+apstr)
					pubtop="espresense/rooms/"+room+"/query/set"
					payload=apstr
					self.mqttClient.publish(pubtop, payload)
					pubtop="espresense/rooms/"+room+"/restart/set"
					payload=" "
					self.mqttClient.publish(pubtop, payload)
				else:
					domoticz.debug("Query string for dev "+room+" did not change")
			self.hbc = 0
		if time.localtime().tm_hour == 1:
			self.last_unique_apples = ""


	def onMQTTConnected(self):
		self.mqttClient.subscribe([self.base_topic + '/#'])

	def onMQTTDisconnected(self):
		domoticz.debug('Disconnected from MQTT server')

	def onMQTTSubscribed(self):
		domoticz.debug('Subscribed to "' + self.base_topic + '/#" topic')

	def onMQTTPublish(self, topic, msg):
		domoticz.debug("MQTT message: " + topic + " " + str(msg))
		now = int(time.time())
		topic = topic.split('/')
		room=topic[3]
		domoticz.debug("room is " + room)
		rstr=""

		device=msg
		domoticz.debug("device is " + str(device))
		if room not in self.rooms:
			self.rooms[room]={}
			pubtop="espresense/rooms/"+room+"/exclude/set"
			payload=self.ignore
			self.mqttClient.publish(pubtop, payload)
			domoticz.debug("adding room " + room+" and sending payload "+payload+" to topic "+pubtop)
			pubtop="espresense/rooms/"+room+"/restart/set"
			payload=" "
			self.mqttClient.publish(pubtop, payload)
		dev_id=device['id']
		for qual in self.prequal:
			if (qual in dev_id):
				dist=device['distance']
				if dev_id in self.rooms[room]:
					self.rooms[room][dev_id]['distance']=dist
					self.rooms[room][dev_id]['timestamp']=now
				else:
					self.rooms[room][dev_id]={'id': dev_id, 'distance': dist, 'timestamp': now }
				prune_table(self, now)
				roomname,dist=find_room(self, dev_id)
				switchdev, textdev = find_device(self, dev_id)
#				domoticz.debug("Found switchdev " + switchdev.Name + " with value " + str(switchdev.nValue))
#				domoticz.debug("Found textdev " + textdev.Name + " with value " + textdev.sValue)
				if switchdev.nValue != 1:
					switchdev.nValue=1
					switchdev.Update(Log=True)

				if dist < 2.5:
					domoticz.debug("device " + dev_id + " is closest to room " + roomname +  " with distance " +  str(dist))
					rstr="In " + roomname
				else:
					domoticz.debug("device " + dev_id + " is in room " + roomname +  " with distance " +  str(dist))
					rstr="Near " + roomname

				if rstr != textdev.sValue:
					textdev.sValue=rstr
					textdev.Update(Log=True)
			else:
				if ("apple:100" in dev_id) and (dev_id not in self.unique_apples):
					self.unique_apples.append(dev_id)
					domoticz.debug("Unique appples now contains " + str(self.unique_apples))

global _plugin
_plugin = BasePlugin()

def onStart():
	global _plugin
	_plugin.onStart()

def onStop():
	global _plugin
	_plugin.onStop()
	
def onConnect(Connection, Status, Description):
	global _plugin
	_plugin.onConnect(Connection, Status, Description)

def onDeviceModified(DeviceId, Unit):
	global _plugin
	_plugin.onDeviceModified(DeviceId, Unit)

def onDeviceRemoved(DeviceId, Unit):
	configuration.remove_device(DeviceId, Unit)

def onDisconnect(Connection):
	global _plugin
	_plugin.onDisconnect(Connection)

def onMessage(Connection, Data):
	global _plugin
	_plugin.onMessage(Connection, Data)

def onCommand(DeviceId, Unit, Command, Level, Color):
	global _plugin
	_plugin.onCommand(DeviceId, Unit, Command, Level, Color)

def onHeartbeat():
	global _plugin
	_plugin.onHeartbeat()
