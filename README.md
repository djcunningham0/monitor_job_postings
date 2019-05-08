# monitor_job_list_postings

Scrape job listings daily and send an email when jobs are added or deleted. Currently it is only implemented for 
STATS (https://www.stats.com/careers/).

## Contents

* `monitor_job_listings.py`: defines a general JobList class and a StatsLLC subclass that are used to scrape job 
  listings from the careers URL and email additions and deletions to me
* `utils.py`: defines some functions used in `monitor_job_listings.py`
* `run_launchd.sh`: shell script that runs the `monitor_job_listings.py` script (called from a launchd agent)
* `local.joblistings.plist`: plist file for running a launch agent -- I have it scheduled to run daily at 5 PM 
  (and I have a symbolic link to this file in my `~/Library/LaunchAgents` directory)
* `job_list_files/`: directory where job data is saved in CSV files

## Usage

To run ad hoc, just run the `monitor_job_listings.py` script. 

To do it more manually (or if you want to change the default options when running the scraper, call the 
`JobList.run()` method. For example:
```
stats = StatsLLC()
stats.run()
```

To schedule a recurring run, I have a launch agent set up to run `run_launchd.sh` at 5 PM daily.
```
launchctl load local.joblistings.plist
```
