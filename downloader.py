#!/usr/bin/env python

import json
import os
import requests
import smtplib
import time
import urllib
from email import message
from bs4 import BeautifulSoup
from multiprocessing.dummy import Pool as ThreadPool

test_run = True

def load_config():
    config = ""
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
    return config

def parse_episodes_for_season(season_url, row_identifier):
    episodes = []
    headers = { 'User-Agent': config['user_agent'] }
    response = requests.get(season_url, headers=headers)
    soup = BeautifulSoup(response.text, "lxml")
    table = soup.find('tbody')
    rows = table.findAll('tr')
    for tr in rows:
        if row_identifier in tr.text:
            for col in tr.findAll('td'):
                for c in col.findAll('a', href=True):
                    episodes.append(c.text)

    return episodes

def parse_seasons_for_series(season_list):
    seasons = []
    row_identifier = 's'
    headers = { 'User-Agent': config['user_agent'] }
    response = requests.get(season_list, headers=headers)
    soup = BeautifulSoup(response.text, "lxml")
    table = soup.find('tbody')
    rows = table.findAll('tr')
    for tr in rows:
        if row_identifier in tr.text:
            for col in tr.findAll('td'):
                for c in col.findAll('a', href=True):
                    seasons.append(c.text)
    return seasons

def get_episodes_for_series(config, series):
    episodes = []
    title = series['title']
    row_identifier = series['row_identifier']
    quality_folder = series['quality_folder']
    base_url = config['base_url']
    base_fs_path = config['base_fs_path']
    season_list_url = base_url + title + "/"

    seasons = parse_seasons_for_series(season_list_url)
    for season in seasons:
        season_url = season_list_url + season + quality_folder

        season_episodes = parse_episodes_for_season(season_url, row_identifier)
        for season_episode in season_episodes:
            episode = {}
            path = title + "/" + season + quality_folder + season_episode
            episode['series'] = title
            episode['season'] = season.replace("/", "").upper()
            episode['filename'] = season_episode
            episode['url'] = base_url + path
            episode['path'] = base_fs_path + path
            episodes.append(episode)

    return episodes

def send_notification(episode):
    m = message.Message()

    gmail_config = config['gmail_config']
    m.add_header('from', gmail_config['from_addr'])
    m.add_header('to', gmail_config['to_addr'])
    m.add_header('subject', "New " + episode['series']  + " episode downloaded!")

    body = episode['series'] + " (" + episode['season'] + ")\n"
    body = body + "\t" + episode['path'] + "\n"
    body = body + "\t" + episode['url'] + "\n"
    m.set_payload(body + '\n')

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(gmail_config['username'], gmail_config['password'])
    server.sendmail(gmail_config['from_addr'], gmail_config['to_addr'], m.as_string())
    server.quit()

def download_episode(episode):
    url = episode['url']
    path = episode['path']

    print "Downloading:  " + episode['filename']
    print "    " + url
    print "    " + path
    print

    exists = os.path.exists(path)
    if not exists:
        if not test_run:
            urllib.urlretrieve(url, path)
            exists = os.path.exists(path)
            if exists:
                send_notification(episode)
        else:
            time.sleep(2)
    queue.remove(episode)

config = load_config()

queue = []
while True:
    config = load_config()


    if not test_run:
        dl_threads = config['concurrent_dl']
    else:
        dl_threads = 1
    pool = ThreadPool(dl_threads)

    series_configs = config['series']
    for series in series_configs:
        print "Enumerating:  " + series['title']
        print
        series_episodes = get_episodes_for_series(config, series)
        for series_episode in series_episodes:
            exists = os.path.exists(series_episode['path'])
            if not exists and series_episode not in queue:
                print "   Queueing:  " + series_episode['filename']
                queue.append(series_episode)
        print

    if queue:
        pool.map(download_episode, queue)

    pool.close()
    pool.join()

    time.sleep(3600)
