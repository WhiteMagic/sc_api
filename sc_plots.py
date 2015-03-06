import argparse
import matplotlib.pyplot as plt
import pickle
import sys

from sc_scraper import Pilot


def filter_duration(data, threshold):
    new_data = []
    for pilot in data:
        if pilot.flight_time >= threshold:
            new_data.append(pilot)
    return new_data

def filter_matches(data, threshold):
    new_data = []
    for pilot in data:
        if pilot.matches >= threshold:
            new_data.append(pilot)
    return new_data

def filter_device(data, threshold):
    new_data = []
    for pilot in data:
        try:
            fav_input = pilot.favorite_input
            if fav_input[1] >= threshold:
                new_data.append(pilot)
        except KeyError:
            pass
    return new_data


def flight_time_histogram(data, modes):
    for i, mode in enumerate(modes):
        y = [e.flight_time for e in data[mode].values()]
        plt.subplot(len(modes), 1, i+1)
        plt.xlabel("Flight Time (Hours)")
        plt.ylabel("Player Count")
        plt.hist(y, bins=50, range=(0, 25), label=mode)
        plt.legend()
    #plt.show()
    plt.savefig("/tmp/flight_time_histogram.png", papertype="a4", dpi=300)


def match_count_histogram(data, modes):
    for i, mode in enumerate(modes):
        y = [e.matches for e in data[mode].values()]
        plt.subplot(len(modes), 1, i+1)
        plt.xlabel("Match Count")
        plt.ylabel("Player Count")
        plt.hist(y, bins=25, range=(0, 25), label=mode)
        plt.legend()
    #plt.show()
    plt.savefig("/tmp/match_count_histogram.png", papertype="a4", dpi=300)


def match_duration_histogram(data, modes):
    for i, mode in enumerate(modes):
        y = [e.flight_time / e.matches * 60 for e in data[mode].values()]
        weights = [e.matches for e in data[mode].values()]
        plt.subplot(len(modes), 1, i+1)
        plt.xlabel("Match Duration (Minutes)")
        plt.ylabel("Player Count")
        plt.hist(y, bins=100, weights=weights, range=(0, 60), label=mode)
        plt.legend()
    #plt.show()
    plt.savefig("/tmp/match_time_histogram.png", papertype="a4", dpi=300)


def score_per_minute_histogram(data, modes):
    for i, mode in enumerate(modes):
        filtered_data = filter_duration(data[mode].values(), 1.0)
        filtered_data = filter_matches(filtered_data, 4)
        filtered_data = filter_device(filtered_data, 0.9)
        
        plt.figure(i)
        for j, dev in enumerate(["Mouse", "Joystick", "Gamepad"]):
            plt.subplot(3, 1, j+1)

            #y = [e.score_minute for e in filtered_data if e.favorite_input[0] == dev]
            #plt.hist(y, bins=100, label=dev, range=(0, 1200), normed=True)
            #plt.ylim(0, 0.004)
            #plt.yticks([])

            y = [e.kill_death_ratio for e in filtered_data if e.favorite_input[0] == dev]
            plt.hist(y, bins=100, label=dev, range=(0, 2.5), normed=True)
            plt.ylim(0, 3.0)
            plt.yticks([])
            plt.legend()
        
        #plt.suptitle("SPM in {} - {:d} Players".format(mode, len(filtered_data)))
        #plt.savefig("/tmp/spm_hist_{}.png".format(mode), papertype="a4", dpi=300)

        plt.suptitle("KDR in {} - {:d} Players".format(mode, len(filtered_data)))
        plt.savefig("/tmp/kdr_hist_{}.png".format(mode), papertype="a4", dpi=300)


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Star Citizen Leaderboard Plotting")
    parser.add_argument("data_file", help="Data file which contains the data")
    args = parser.parse_args()
    
    pilot_data = pickle.load(open(args.data_file, "rb"))

    #flight_time_histogram(pilot_data, ["BR", "SB", "CC", "VC"])
    #match_count_histogram(pilot_data, ["BR", "SB", "VC"])
    #match_duration_histogram(pilot_data, ["BR", "SB", "VC"])
    score_per_minute_histogram(pilot_data, ["BR", "SB", "VC"])



    return 0


if __name__ == "__main__":
    sys.exit(main())
