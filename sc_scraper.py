#!/usr/bin/env python

import argparse
import multiprocessing
import os
import pickle
import requests
import sys



class ExtendedDataGrabber(multiprocessing.Process):

    def __init__(self, task_queue, result_queue):
        multiprocessing.Process.__init__(self)
        self.task_queue = task_queue
        self.result_queue = result_queue

    def run(self):
        proc_name = self.name
        while True:
            next_task = self.task_queue.get()
            if next_task is None:
                self.task_queue.task_done()
                break
            answer = next_task()
            self.task_queue.task_done()
            self.result_queue.put(answer)
        return


class Task(object):

    def __init__(self, handle, mode, proxies={}):
        self.handle = handle
        self.mode = mode
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
        print("Processing {}".format(self.handle))
        return (self.handle, r.json()["data"]["resultset"][0])


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
        arr = [int(v) for v in self._data["flight_time"].split(":")]
        return (3600 * arr[0] + 60 * arr[1] + arr[2]) / 3600.0

    @property
    def matches(self):
        return int(self._data["matches"])

    @property
    def score(self):
        return int(self._data["score"])

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
        data = self._data["ship"][0]
        return (data["name"], float(data["ratio"]))

    @property
    def favorite_input(self):
        data = self._data["favorite_input"][0]
        return (data["name"], float(data["ratio"]))


def query_boundaries(url, query, proxies={}):
    r = requests.post(url, proxies=proxies, params=query)
    data = r.json()["data"]

    return {
        "entries": int(data["totalrows"]),
        "pages": int(data["pagecount"])
    }


def scrape_leaderboard(pilots, mode, season=5, proxies={}):
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

    tasks = multiprocessing.JoinableQueue()
    results = multiprocessing.Queue()
    data_grabbers = [ExtendedDataGrabber(tasks, results) for _ in range(20)]
    for entry in data_grabbers:
        entry.start()

    for i in range(bounds["pages"]):
        query["page"] = i+1
        req = requests.post(leaderboard_url, proxies=proxies, params=query)

        for i, entry in enumerate(req.json()["data"]["resultset"]):
            handle = entry["nickname"]
            if handle not in pilots:
                print("New pilot     : {}".format(handle))
                pilots[handle] = Pilot(entry)
                tasks.put(Task(handle, mode, proxies))
            else:
                tmp = Pilot(entry)
                if tmp.flight_time > pilots[handle].flight_time:
                    print("Updating pilot: {}".format(handle))
                    tasks.put(Task(handle, mode, proxies))
                pilots[handle].update(entry)

    for entry in data_grabbers:
        tasks.put(None)

    print("Waiting for detailed data to be grabbed")
    tasks.join()
    while not results.empty():
        entry = results.get()
        pilots[entry[0]].update(entry[1])


def scrape_data(pilot_data, proxies):
    mode_list = {
        "Battle Royale": "BR",
        "Squadron Battle": "SB",
        "Vanduul Swarm Coop": "VC",
        "Capture the Core": "CC",
    }

    for mode in mode_list.values():
        print(">>> Processing mode: {}".format(mode))
        if mode not in pilot_data:
            pilot_data[mode] = {}
        scrape_leaderboard(pilot_data[mode], mode, proxies)


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Star Citizen Leaderboard Scraper")
    parser.add_argument("data_file", help="Data file which contains the data")
    args = parser.parse_args()

    # Proxy server configuration
    proxies = {
        "http": "http://web-cache.usyd.edu.au:8080",
        "https": "http://web-cache.usyd.edu.au:8080"
    }
    
    # Load data and scrape data
    pilot_data = {}
    if os.path.exists(args.data_file):
        pilot_data = pickle.load(open(args.data_file, "rb"))
    scrape_data(pilot_data, proxies=proxies)
    pickle.dump(pilot_data, open(args.data_file, "wb"))


    return 0


if __name__ == "__main__":
    sys.exit(main())
