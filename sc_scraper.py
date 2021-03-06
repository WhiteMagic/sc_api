#!/usr/bin/env python

import argparse
from collections import deque
import datetime
import logging
import threading
import os
import pickle
import requests
import sys
import time



class TaskManager(object):

    """Ensures that a certain number of task threads are active at any given time."""

    def __init__(self, thread_count):
        self.thread_count = thread_count
        self.queue = deque()
        self._current_count = 0
        self._counter_lock = threading.Lock()
        self._queue_lock = threading.Lock()

    def create(self, storage, handle, mode, proxies):
        thread = threading.Thread(target=Task(storage, handle, mode, self.done, proxies))
        with self._queue_lock:
            self.queue.append(thread)

    def done(self):
        with self._counter_lock:
            self._current_count -= 1
            assert(self._current_count >= 0)
        self.start_next()

    def start_next(self):
        with self._queue_lock:
            with self._counter_lock:
                while self._current_count < self.thread_count and len(self.queue) > 0:
                    thread = self.queue.popleft()
                    thread.start()
                    self._current_count += 1



class Task(object):

    def __init__(self, storage, handle, mode, callback, proxies={}):
        self.storage = storage
        self.handle = handle
        self.mode = mode
        self.callback = callback
        self.proxies = proxies

    def __call__(self):
        payload = {
                "map": "MAP-ANY",
                "mode": self.mode,
                "handle": self.handle,
                "type": "Account"
        }
        r = requests.post(
            "https://robertsspaceindustries.com/api/arena-commander/getAdditionalStats",
            params=payload,
            proxies=self.proxies
        )
        try:
            self.storage.get_pilot(self.handle).update(r.json()["data"]["resultset"][0])
        except TypeError:
            logging.error("ERROR: invalid data for user {}".format(self.handle))
        self.callback()


class Pilot(object):

    def __init__(self, data):
        self._data = data

    def update(self, data):
        for key, value in data.items():
            self._data[key] = value

    @property
    def handle(self):
        return self._data["nickname"]

    @property
    def flight_time(self):
        data = self._data["flight_time"]
        if data == -1:
            return 0
        else:
            try:
                arr = [int(v) for v in data.split(":")]
                return (3600 * arr[0] + 60 * arr[1] + arr[2]) / 3600.0
            except AttributeError:
                print(data, self._data["nickname"])

    @property
    def matches(self):
        return int(self._data["matches"])

    @property
    def score(self):
        return int(self._data["score"])

    @property
    def deaths(self):
        return int(self._data["deaths"])

    @property
    def kills(self):
        return int(self._data["kills"])

    @property
    def rank(self):
        return int(self._data["rank"])

    @property
    def rank_score(self):
        return float(self._data["rank_score"])

    @property
    def score_minute(self):
        return float(self._data["score_minute"])

    @property
    def damage_dealt(self):
        return int(self._data["damage_dealt"])

    @property
    def damage_taken(self):
        return int(self._data["damage_taken"])

    @property
    def damage_ratio(self):
        return float(self._data["damage_ratio"])

    @property
    def kill_death_ratio(self):
        return float(self._data["kill_death_ratio"])

    @property
    def favorite_ship(self):
        if len(self._data["ship"]) > 0:
            data = self._data["ship"][0]
            return (data["name"], float(data["ratio"]))
        else:
            return None

    @property
    def favorite_input(self):
        if len(self._data["favorite_input"]) > 0:
            data = self._data["favorite_input"][0]
            return (data["name"], float(data["ratio"]))
        else:
            return None


class DeltaEntry(object):

    def __init__(self, pilot, data):
        self.date = datetime.datetime.utcnow().date()
        tmp = Pilot(data)
        self.deaths = tmp.deaths - pilot.deaths
        self.flight_time = tmp.flight_time - pilot.flight_time
        self.kills = tmp.kills - pilot.kills
        self.matches = tmp.matches - pilot.matches
        self.score = tmp.score - pilot.score


class Storage(object):

    def __init__(self):
        self._storage = {0: {}}

    def date_keys(self):
        keys = list(self._storage.keys())
        del keys[0]
        return keys

    def pilot_exists(self, handle):
        return handle in self._storage[0]

    def get_data(self, date=0):
        return self._storage[date]

    def get_pilot(self, handle, date=0):
        return self._storage[date][handle]

    def update_pilot(self, handle, data):
        if handle not in self._storage[0]:
            self._storage[0][handle] = Pilot(data)
        else:
            self._create_delta_entry(handle, data)
            self._storage[0][handle].update(data)

    def _create_delta_entry(self, handle, data):
        delta = DeltaEntry(self._storage[0][handle], data)
        if delta.date not in self._storage:
            self._storage[delta.date] = {}
        self._storage[delta.date][handle] = delta


def query_boundaries(url, query, proxies={}):
    r = requests.post(url, proxies=proxies, params=query)
    data = r.json()["data"]

    return {
        "entries": int(data["totalrows"]),
        "pages": int(data["pagecount"])
    }


def scrape_leaderboard(storage, mode, season=9, proxies={}):
    leaderboard_url = "https://robertsspaceindustries.com/api/arena-commander/getLeaderboard"
    query = {
        "map": "MAP-ANY",
        "mode": mode,
        "page": 1,
        "pagesize": 1000,
        "season": season,
        "type": "Account"
    }

    bounds = query_boundaries(leaderboard_url, query, proxies)
    manager = TaskManager(50)

    for i in range(bounds["pages"]):
        query["page"] = i+1
        req = requests.post(leaderboard_url, proxies=proxies, params=query)

        for i, entry in enumerate(req.json()["data"]["resultset"]):
            handle = entry["nickname"]
            if not storage.pilot_exists(handle):
                logging.debug("New pilot     : {}".format(handle))
                storage.update_pilot(handle, entry)
                manager.create(storage, handle, mode, proxies)
            else:
                tmp = Pilot(entry)
                if tmp.flight_time > storage.get_pilot(tmp.handle).flight_time:
                    logging.debug("Updating pilot: {}".format(handle))
                    manager.create(storage, handle, mode, proxies)
                    storage.update_pilot(tmp.handle, entry)
        manager.start_next()

    logging.debug("Waiting for all tasks to finish")
    manager.start_next()
    while(len(manager.queue) > 0):
        logging.debug("Tasks remaining: {:d}".format(len(manager.queue)))
        time.sleep(1)


def scrape_data(data, proxies):
    mode_list = {
        "Battle Royale": "BR",
        "Squadron Battle": "SB",
        "Vanduul Swarm Coop": "VC",
        "Capture the Core": "CC",
    }

    for mode in mode_list.values():
        logging.debug(">>> Processing mode: {}".format(mode))
        if mode not in data:
            data[mode] = Storage()
        scrape_leaderboard(data[mode], mode, 9, proxies)


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Star Citizen Leaderboard Scraper")
    parser.add_argument("data_file", help="Data file which contains the data")
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
            filename="/home/lott/sc_scraper_debug.log",
            format="%(asctime)s %(levelname)10s %(message)s",
            datefmt="%Y-%m-%d %H:%M",
            level=logging.DEBUG
    )
    #logging.getLogger("requests").setLevel(logging.WARNING)
    #logging.getLogger('urllib3').setLevel(logging.WARNING)

    # Proxy server configuration
    proxies = {
        "http": "http://web-cache.usyd.edu.au:8080",
        "https": "http://web-cache.usyd.edu.au:8080"
    }
    #proxies = {}
    
    # Load data and scrape data
    data = {}
    if os.path.exists(args.data_file):
        data = pickle.load(open(args.data_file, "rb"))
    scrape_data(data, proxies=proxies)
    pickle.dump(data, open(args.data_file, "wb"))


    return 0


if __name__ == "__main__":
    sys.exit(main())
