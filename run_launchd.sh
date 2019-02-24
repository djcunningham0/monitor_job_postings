#!/bin/sh

# ** Make sure this script is executable! (chmod 744) **

# launchd script is in /Users/Daniel/Library/LaunchAgents

# wait 2 minutes in case you're just turning on the computer and it doesn't 
# establish an internet connection right away
sleep 120

# run the python job
cd /Users/Daniel/Documents/Projects/monitor_job_listings/
/Users/Daniel/anaconda3/bin/python ./monitor_job_listings.py
