## Setup

Please read source carefully, as the log file directories are hardcoded.


mkdir -p /usr/lib/systemd/system 
nano /usr/lib/systemd/system/eosmonitor.service


## eosmonitor.service

```
[Unit]
Description=eoskeeper

[Service]
User=eosio
ExecStart=/bin/bash -c "/usr/local/bin/eosmonitor > /dev/null  2>&1"
Restart=always

[Install]
WantedBy=multi-user.target
```

sudo systemctl enable eosmonitor.service
sudo service eosmonitor start

