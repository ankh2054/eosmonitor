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

[Service]
User=eosio
ExecStart=/bin/bash -c "/usr/local/bin/eosmonitor > /dev/null  2>&1"
Restart=always

[Install]
WantedBy=multi-user.target
```

- Create and start service
```
sudo systemctl enable eosmonitor.service
sudo service eosmonitor start
```

### 5) To test your service is running

Tail the parse_log_file as specified in your config.ini. 
The python process constiously logs to that file.