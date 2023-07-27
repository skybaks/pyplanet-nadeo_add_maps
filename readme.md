# Nadeo Add Maps

This is a plugin for the PyPlanet dedicated server controller for the game Trackmania (2020). It adds the ability to
add maps from the Nadeo Services API using the maps UID.

The command this plugin adds mirrors the form and function of the built-in MX/TMX map adding capability. Use the
following command to add a single map:

```
//nadeo add y6lNDJEgg5BH1zuaexM8GhKdPw4
```

If you want to add multiple maps, you can separate the UIDs with a space like as follows:

```
//nadeo add y6lNDJEgg5BH1zuaexM8GhKdPw4 iOyuS01BnGY8lbgRJ4vx6ew8Gu1 qiWGK50uLPAQ33EGRLvZMy7hKT
```

> Keep in mind you are limited by the maximum length of a chat message so you may not be able to send a lot at once.

The plugin needs to have the login and password of a dedicated server account in order to access the API which looks up
the map information. It will first attempt to get this from the dedicated_cfg.txt file if it is located in the standard
location at `UserData/Config/dedicated_cfg.txt`.

If it cannot read the login information from there it will fall back on getting it from the PyPlanet settings files.
You will have to manually specify the following in your base.py or local.py (local.py is preferred):

```python
DEDICATED_USERNAME = "my_dedicated_username"
DEDICATED_PASSWORD = "my_dedicated_password"
```

Where you replace "my_dedicated_username" and "my_dedicated_password" with your actually dedicated server account
username and password.
