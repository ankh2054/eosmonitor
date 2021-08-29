#!/usr/bin/env python3

import re
import time
import threading
import re
import sys
import logging
import subprocess
from sh import tail
import socket
import requests
import configparser


class SetConfigParser(configparser.RawConfigParser):
    def get(self, section, option):
        val = configparser.RawConfigParser.get(self, section, option)
        return val.strip('"').strip("'")

config = SetConfigParser()

try:
    config.read('/etc/eosmonitor/config.ini')
    config.read('config.ini')
except:
    pass

block_producer = config.get("core", "block_producer")
eosio_log_file = config.get("core", "eosio_log_file")
parse_log_file = config.get("core", "parse_log_file")
http_port = config.get("core", "http_port")
parse_log_file = config.get("core", "parse_log_file")
pushover_user_key = config.get("core", "pushover_user_key")
pushover_app_key = config.get("core", "pushover_app_key")


#url = "http://"+http_ip+":"+http_port+"/v1/chain/get_info"
produced_blocks = 0 
current_links = ""  # strings
current_linkn = 0  # link number
nodeos_pid = 0
localhostname = socket.gethostname()

# Regex
re1 = r'.*net_plugin.cpp.* [\":.-].*unlinkable_block_exception (#\d+) .*'
re2 = r'.*producer_plugin.cpp.*] Produced block .* (#\d+) @.*'
re3 = r'.*producer_plugin.cpp.*] dropped incoming block (#\d+) .*'
re4 = r'.* NAME\\nnodeos  (\d+) .*'
#info  2021-07-27T19:33:09.287 net-0     net_plugin.cpp:3158           connection_monitor   ] p2p client connections: 0/300, peer connections: 6/6
re5 = r'.*net_plugin.cpp.* p2p client connections: [\/0-9]*'
#info  2021-07-29T05:00:45.463 net-0     net_plugin.cpp:1704           recv_handshake       ] handshake from wax.dapplica.io:9876 - 4b504a4, lib 132181734, head 132182065, head id 42b557ae09c92bbf.. sync 4
re6  = r'.*net_plugin.cpp.* recv_handshake.*'
#info  2021-07-30T06:02:15.785 net-1     net_plugin.cpp:1057           blk_send_branch_impl ] enqueue 132362216 - 132362216 to wax.dapplica.io:9876 - 4b504a4
re7 = r'.*net_plugin.cpp.* blk_send_branch_impl.*'
#info  2021-07-30T06:02:15.785 net-1     net_plugin.cpp:1217           enqueue_sync_block   ] completing enqueue_sync_block 132362216 to wax.dapplica.io:9876 - 4b504a4
re8 = r'.*net_plugin.cpp.* enqueue_sync_block.*'
#info  2021-07-31T17:02:17.781 nodeos    controller.cpp:2100           maybe_switch_forks   ] switching forks from 07e77d4d89f0383dbcc0a0cf164715a9d13ef8de366bd7c95fc4b9d77b025cac (block number 132611405) to 
re9 = r'.*controller.cpp.* switching forks .* (\d+)' 
# Setup Log file
logging.basicConfig(filename=parse_log_file, level="INFO")


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

def log_info(msg):
    print("INFO: " + now() + "  " + msg)
    logging.info("  " + now() + "  " + msg)


def log_err_notify(msg,prioirty):
    print("ERROR: " + now() + "  " + msg)
    logging.error("  " + now() + "  " + msg)
    # After logging error send to pushover with message priority
    pushover(msg,prioirty)

def pushover(message,priority):
    if priority:
        priority = 1
    else:
        priority = 0
    try:
        r = requests.post("https://api.pushover.net/1/messages.json", data = {
        "token": pushover_app_key,
        "user": pushover_user_key,
        "message": message,
        "priority": priority
        })
    except:
        log_info("Pushover message could not be send")
    


def init():
    global nodeos_pid
    ret = ""
    try:
        ret = subprocess.check_output(["lsof", "-i:"+http_port])
    except:
        log_info("ERROR! run lsof -i:"+http_port+"\nExit!")
        exit(1)
    retstr = str(ret)
    nodeos_pid_match = re.match(re4, retstr)
    nodeos_pid = nodeos_pid_match.group(1)



def detect_faults(line):
    # Create global variables
    global produced_blocks,block_producer
    unlikblk = re.match(re1, line) # check for unlickable blocks
    prodblk = re.match(re2, line) # check for produced block
    dropblk = re.match(re3, line) # check for dropped block
    connt = re.match(re5, line) # check for connection messages
    handshake = re.match(re6, line) # check for connection messages
    blksend = re.match(re7, line) # check for blk_send_branch_impl
    blkenq = re.match(re8, line) # check for  enqueue_sync_block
    fork = re.match(re9, line) # check for  enqueue_sync_block
    if prodblk:
        log_info(block_producer + "  ******* Produce block " + prodblk.group(1) + " ********")
        produced_blocks += 1
    # If during block production we get random messages just skip them
    elif connt or handshake or blksend or blkenq:
        pass
    # Check it total produced blocks are less than 12 and also check prodblk is false to ensurs its finished
    elif 1 < produced_blocks  < 12:
        err_mesg = block_producer + "  ******* Only produced " + str(produced_blocks) + " around block" + prodblk.group(1) + "blocks ********"
        log_err_notify(err_mesg,True)
        # After message also set produced_blocks = 0
        produced_blocks = 0
        pass
    # If not producing blocks set to 0 and pass
    elif not prodblk:
        produced_blocks = 0
        pass
    elif fork:
        err_mesg = localhostname + ": Fork detected: " + fork.group(1) + " ********"
        log_err_notify(err_mesg,False)
    elif unlikblk:
        err_mesg = localhostname + ": Unlinkable block detected: " + unlikblk.group(1) + " ********"
        log_err_notify(err_mesg,False)
    elif dropblk:
        err_mesg = localhostname + ": Dropped block detected: " + dropblk.group(1) + " ********"
        log_err_notify(err_mesg,False)

class ParseLog(threading.Thread):
    def run(self):
        log_info("Run thread LogParser")
        while True:
            try:
                for line in tail("-n", 1, "-f", eosio_log_file, _iter=True):
                    detect_faults(line)
            except:
                log_err_notify("eosio log file:" + eosio_log_file + " parse failed! on " + localhostname,False)
            time.sleep(10)

# -- LsofParser --
def lsof_parser():
    global current_links, current_linkn, localhostname
    count = 0
    links = ""
    ret = subprocess.getoutput(["lsof", "-nP", "-p", str(nodeos_pid) ])
    lines = ret.split("\n")
    for line in lines:
        # Search for TCP connections matching your hostname
        if re.match(r'.*TCP block-producer.*', line):
            count += 1
            cols = re.split(r" +", line)
            links += cols[len(cols) - 2] + "\n"
    current_linkn = count
    current_links = links
    # log_info("\nlink_num: " + str(current_linkn) + "\nlink_str:\n" + current_links)
    log_info("\nlink_num: " + str(current_linkn) + "\n")
    if current_linkn < 3:
        err_mesg = localhostname + ' has less than ' + str(current_linkn) + ' connections'
        log_err_notify(err_mesg,True)


class ParseLsof(threading.Thread):
    def run(self):
        log_info("Run LsofParser as thread")
        while True:
            try:
                lsof_parser()
            except:
                log_err_notify("lsof parser failed on " + localhostname,False )
            time.sleep(300)


if __name__ == '__main__':
    log_info("EOS monitor starting: " + now())
    init()

    log_parser_t = ParseLog()
    log_parser_t.setDaemon(True)
    log_parser_t.start()

    lsof_parser_t = ParseLsof()
    lsof_parser_t.setDaemon(True)
    lsof_parser_t.start()

    while True:
        time.sleep(60)
