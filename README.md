## Requirements

- Python3
- https://pushover.net account


## Setup instructions

### 1) Install python packages

pip3 install -r requirements.txt


### 2) Create folder and files

- mkdir /etc/eosmonitor 
- copy config.ini --> /etc/eoskeeper/config.ini
- copy eosmonitor.py --> /usr/local/bin/eosmonitor
- chmod +x /usr/local/bin/eosmonitor

### 3) Update config.ini

The config file requires the following parameters:

- **block_producer:** Account name of your block producer to monitor for in the log files. 
- **eosio_log_file:** Location of your eosio logfile.
- **parse_log_file:** Location of the eosmonitor logfile.
- **http_port:** Port of nodeos HTTP port
- **pushover_app_key:** Pushover APP key
- **pushover_user_key:** Pushover user key


### 4) Create and register as service. 

- mkdir -p /usr/lib/systemd/system 
- Add the contents below to file --> /usr/lib/systemd/system/eosmonitor.service

```
[Unit]
Description=eosmonitor
StartLimitIntervalSec=400
StartLimitBurst=3


[Service]
User=charles
ExecStart=/bin/bash -c "/usr/local/bin/eosmonitor > /dev/null  2>&1"
Restart=always
RestartSec=90

[Install]
WantedBy=multi-user.target
```

- Create and start service
```
sudo systemctl enable eosmonitor.service
sudo systemctl start eosmonitor 
```

### 5) To test your service is running

Tail the parse_log_file as specified in your config.ini. 
The python process constiously logs to that file.


## Additional config to think about


### 1) Configuring high-priority alerts 

- The pushover app allows you to overide the **Do Not Disturb mode** on your phone. 
- Within the python script you can set which alerts are considered high-priority. 
- By default any missed blocks are set to high-priority
- This ensures that even when you slumper and have **Do Not Disturb mode** enabled you wil be alerted when your proucer misss blocks.

![IMG_62E0230DB425-1](https://user-images.githubusercontent.com/6784287/131241185-5a82e583-6ae0-4b47-a41a-d6feaf799062.jpeg)
