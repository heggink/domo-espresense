# domo-espresense
Domoticz espresense plugin

You can set 2 parameters in the esp devices through the plugin:
1) the exclude list of devices in the filter section
2) the "query device id's in the scanning section

The plugin then creates 2 domoticz devices per found device: an on/off to indicate if the device is picked up by any of the esp's and a text device indicating which room the device is in (smalles distance to the esp: if below 2.5 meters then "In" otherwise "Near").
