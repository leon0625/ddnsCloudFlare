#!/usr/bin/env python3

import logging, sys, os, time
import configparser
import requests
import subprocess

RETRY_COUNT = 6
RETRY_DELAY = 60  # seconds


def read_config(path):
    try:
        cfg = configparser.ConfigParser()
        cfg.read(path)
        zoneId = cfg.get('global', 'zoneId')
        recordName = cfg.get('global', 'recordName')
        apiKey = cfg.get('global', 'apiKey')
        return zoneId, recordName, apiKey
    except Exception as e:
        logging.error(f'Error reading config: {e}')
        exit(1)


def request_with_retry(method, url, **kwargs):
    for attempt in range(RETRY_COUNT):
        try:
            response = requests.request(method, url, timeout=20, **kwargs)
            response.raise_for_status()
            return response
        except Exception as e:
            logging.warning(f'[{attempt+1}/{RETRY_COUNT}] {method} request failed: {e}')
            if attempt < RETRY_COUNT - 1:
                time.sleep(RETRY_DELAY)
            else:
                logging.error('Max retry limit reached. Giving up.')
                exit(1)


def getIpv4Address():
    response = request_with_retry('GET', 'https://api.ipify.org')
    return response.text.strip()


def getIpv6Address():
    #command = "ip a show dev br0 mngtmpaddr | awk '/240e/ {print $2}' | sed 's@/.*@@' | head -n 1"
    command = "ip a | awk '/240/ {print $2}' | sed 's@/.*@@' | head -n 1"
    for attempt in range(RETRY_COUNT):
        try:
            proc = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
            output = proc.stdout.strip()
            if output:
                return output
            raise RuntimeError("Empty IPv6 address")
        except Exception as e:
            logging.warning(f'[{attempt+1}/{RETRY_COUNT}] Failed to get IPv6 address: {e}')
            if attempt < RETRY_COUNT - 1:
                time.sleep(RETRY_DELAY)
            else:
                logging.error('Max retry limit reached. Giving up.')
                exit(1)


def listRecord(zoneId, recordName, apiKey, type='A'):
    url = f'https://api.cloudflare.com/client/v4/zones/{zoneId}/dns_records?name={recordName}'
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {apiKey}'}
    response = request_with_retry('GET', url, headers=headers)
    jrst = response.json()
    logging.debug(jrst)
    if not jrst['success']:
        logging.error("Cloudflare response: success == False")
        exit(1)
    for record in jrst['result']:
        if record['type'] == type:
            return record['id'], record['content']
    logging.info('No record found')
    return None, None


def updateRecord(zoneId, recordName, apiKey, resourceId, type, value):
    url = f'https://api.cloudflare.com/client/v4/zones/{zoneId}/dns_records/{resourceId}'
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {apiKey}'}
    payload = {'type': type, 'name': recordName, 'content': value, 'ttl': 600, 'proxied': False}
    response = request_with_retry('PUT', url, headers=headers, json=payload)
    jrst = response.json()
    logging.debug(jrst)
    return jrst['success']


def createRecord(zoneId, recordName, apiKey, type, value):
    url = f'https://api.cloudflare.com/client/v4/zones/{zoneId}/dns_records'
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {apiKey}'}
    payload = {'type': type, 'name': recordName, 'content': value, 'ttl': 600, 'proxied': False}
    response = request_with_retry('POST', url, headers=headers, json=payload)
    jrst = response.json()
    logging.debug(jrst)
    return jrst['result']['id']


def updateIp(ntype):
    cfg_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    logging.debug(f'config file path: {cfg_path}')
    zoneId, recordName, apiKey = read_config(cfg_path)

    extIpAddr = getIpv6Address() if ntype == 'AAAA' else getIpv4Address()

    if len(extIpAddr) == 0:
        logging.error('Error: Unable to get external IP address')
        exit(1)

    id, currentIp = listRecord(zoneId, recordName, apiKey, ntype)

    if currentIp == extIpAddr:
        logging.info('No change')
        exit(0)

    if id is None:
        createRecord(zoneId, recordName, apiKey, ntype, extIpAddr)
    else:
        updateRecord(zoneId, recordName, apiKey, id, ntype, extIpAddr)

    logging.info(f'IP address update success: {currentIp} ==> {extIpAddr}')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) == 1:
        logging.error(f'No argument provided\nipv6: {sys.argv[0]} AAAA\nipv4: {sys.argv[0]} A')
        exit(1)

    updateIp(sys.argv[1])

