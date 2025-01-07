#!/usr/bin/env python3

import logging
import re
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
from sh import tail
from configparser import RawConfigParser

@dataclass
class Config:
    block_producer: str
    eosio_log_file: Path
    parse_log_file: Path
    http_port: str
    pushover_user_key: str
    pushover_app_key: str
    fork_msg: bool
    unlikblk: bool
    dropblk: bool
    produced_blocks_alert: bool

class EOSMonitor:
    # Regex patterns
    PATTERNS = {
        'unlinkable': r'.*net_plugin.cpp.* [\":.-].*unlinkable_block_exception (#\d+) .*',
        'produced': r'.*producer_plugin.cpp.*] Produced block .* (#\d+) @.*',
        'dropped': r'.*producer_plugin.cpp.*] dropped incoming block (#\d+) .*',
        'nodeos_pid': r'.* NAME\\nnodeos  (\d+) .*',
        'connections': r'.*net_plugin.cpp.* p2p client connections: [\/0-9]*',
        'handshake': r'.*net_plugin.cpp.* recv_handshake.*',
        'block_send': r'.*net_plugin.cpp.* blk_send_branch_impl.*',
        'block_enqueue': r'.*net_plugin.cpp.* enqueue_sync_block.*',
        'fork': r'.*controller.cpp.* switching forks .* (\d+)'
    }

    def __init__(self):
        self.config = self._load_config()
        self.hostname = socket.gethostname()
        self.produced_blocks = 0
        self.current_links = ""
        self.current_linknum = 0
        self.nodeos_pid = self._get_nodeos_pid()
        
        logging.basicConfig(filename=self.config.parse_log_file, level=logging.INFO)

    def _load_config(self) -> Config:
        parser = RawConfigParser()
        parser.read(['/etc/eosmonitor/config.ini', 'config.ini'])
        
        return Config(
            block_producer=parser.get("global", "block_producer").strip('"\''),
            eosio_log_file=Path(parser.get("global", "eosio_log_file").strip('"\''))
            # ... similar for other config values
        )

    def _get_nodeos_pid(self) -> int:
        try:
            output = subprocess.check_output(["lsof", f"-i:{self.config.http_port}"])
            if match := re.match(self.PATTERNS['nodeos_pid'], str(output)):
                return int(match.group(1))
            raise ValueError("Could not find nodeos PID")
        except subprocess.CalledProcessError:
            self.log_error(f"Failed to run lsof -i:{self.config.http_port}", True)
            raise SystemExit(1)

    def log_info(self, msg: str) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"INFO: {timestamp} {msg}")
        logging.info(f"{timestamp} {msg}")

    def log_error(self, msg: str, priority: bool) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"ERROR: {timestamp} {msg}")
        logging.error(f"{timestamp} {msg}")
        self._send_pushover(msg, priority)

    def _send_pushover(self, message: str, priority: bool) -> None:
        try:
            requests.post(
                "https://api.pushover.net/1/messages.json",
                data={
                    "token": self.config.pushover_app_key,
                    "user": self.config.pushover_user_key,
                    "message": message,
                    "priority": 1 if priority else 0
                },
                timeout=10
            )
        except requests.RequestException:
            self.log_info("Failed to send Pushover notification")

    def detect_faults(self, line: str) -> None:
        # Handle block production monitoring
        if match := re.match(self.PATTERNS['produced'], line):
            self.log_info(f"{self.config.block_producer} Produced block {match.group(1)}")
            self.produced_blocks += 1
            return

        # Skip routine messages
        if any(re.match(pattern, line) for pattern in [
            self.PATTERNS['connections'],
            self.PATTERNS['handshake'],
            self.PATTERNS['block_send'],
            self.PATTERNS['block_enqueue']
        ]):
            return

        # Check for low block production
        if 1 < self.produced_blocks < 12:
            if self.config.produced_blocks_alert:
                self.log_error(
                    f"{self.config.block_producer} Only produced {self.produced_blocks} blocks",
                    True
                )
            self.produced_blocks = 0

        # Handle other error conditions
        for pattern_name, alert_config in [
            ('fork', self.config.fork_msg),
            ('unlinkable', self.config.unlikblk),
            ('dropped', self.config.dropblk)
        ]:
            if match := re.match(self.PATTERNS[pattern_name], line):
                if alert_config:
                    self.log_error(
                        f"{self.hostname}: {pattern_name.title()} detected: {match.group(1)}",
                        False
                    )

    def monitor_connections(self) -> None:
        try:
            output = subprocess.getoutput(["lsof", "-nP", "-p", str(self.nodeos_pid)])
            hostname_pattern = re.escape(self.hostname)
            
            connections = [
                line for line in output.split("\n")
                if re.match(f".*TCP {hostname_pattern}.*", line)
            ]
            
            self.current_linknum = len(connections)
            self.current_links = "\n".join(
                re.split(r" +", conn)[len(re.split(r" +", conn)) - 2]
                for conn in connections
            )

            self.log_info(f"Current connections: {self.current_linknum}")
            
            if self.current_linknum < 3:
                self.log_error(
                    f"{self.hostname} has only {self.current_linknum} connections",
                    True
                )
        except Exception as e:
            self.log_error(f"Connection monitoring failed: {str(e)}", False)

    def run(self):
        self.log_info("EOS monitor starting")
        
        # Start log parsing thread
        threading.Thread(
            target=self._monitor_logs,
            daemon=True
        ).start()

        # Start connection monitoring thread
        threading.Thread(
            target=self._monitor_connections,
            daemon=True
        ).start()

        while True:
            time.sleep(60)

    def _monitor_logs(self):
        self.log_info("Starting log parser")
        while True:
            try:
                for line in tail("-n", 1, "-f", self.config.eosio_log_file, _iter=True):
                    self.detect_faults(line)
            except Exception as e:
                self.log_error(
                    f"Log parsing failed: {str(e)}",
                    False
                )
            time.sleep(10)

    def _monitor_connections(self):
        self.log_info("Starting connection monitor")
        while True:
            try:
                self.monitor_connections()
            except Exception as e:
                self.log_error(
                    f"Connection monitoring failed: {str(e)}",
                    False
                )
            time.sleep(300)

if __name__ == '__main__':
    monitor = EOSMonitor()
    monitor.run()
