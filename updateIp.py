#!/usr/bin/env python3

import logging,sys
import configparser
import requests
import subprocess


def read_config(path):
    try:
        cfg = configparser.ConfigParser()
        cfg.read(path)
        zoneId = cfg.get('global', 'zoneId')
        recordName = cfg.get('global', 'recordName')
        apiKey = cfg.get('global', 'apiKey')
        return zoneId, recordName, apiKey
    except Exception as e:
        print(f'Error: {e}')
        exit(1)


def getIpv4Address():
    response = requests.get('https://api.ipify.org')
    return response.text

def getIpv6Address():
    proc = subprocess.run(['curl', '-s', '-6', 'https://ifconfig.co/ip'], stdout=subprocess.PIPE, text=True)
    return proc.stdout.strip()

def listRecord(zoneId, recordName, apiKey, type='A'):
    result = requests.get(f'https://api.cloudflare.com/client/v4/zones/{zoneId}/dns_records?name={recordName}', 
                          headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {apiKey}'})
    jrst = result.json()
    logging.debug(jrst)
    if jrst['success'] == False:
        logging.error("success status isn't True")
        exit()

    for record in jrst['result']:
        if record['type'] == type:
            return record['id'], record['content']
    
    logging.info('No record found')
    return None,None


def updateRecord(zoneId, recordName, apiKey, resourceId, type, value):
    result = requests.put(f'https://api.cloudflare.com/client/v4/zones/{zoneId}/dns_records/{resourceId}', 
                          headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {apiKey}'},
                          json={'type': type, 'name': recordName, 'content': value, 'ttl': 600, 'proxied': False})
    jrst = result.json()
    logging.debug(jrst)
    return jrst['success']


def createRecord(zoneId, recordName, apiKey, type, value):
    result = requests.post(f'https://api.cloudflare.com/client/v4/zones/{zoneId}/dns_records', 
                           headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {apiKey}'},
                           json={'type': type, 'name': recordName, 'content': value, 'ttl': 600, 'proxied': False})
    jrst = result.json()
    logging.debug(jrst)
    return jrst['result']['id']

def updateIp(ntype):
    zoneId,recordName,apiKey = read_config('config.ini')
    if ntype == 'AAAA':
        extIpAddr = getIpv6Address()
    else:
        extIpAddr = getIpv4Address()

    if len(extIpAddr) == 0:
        logging.error('Error: Unable to get external IP address')
        exit(1)

    id,currentIp = listRecord(zoneId, recordName, apiKey, ntype)

    if currentIp == extIpAddr:
        logging.info('No change')
        exit(0)

    if id is None:
        createRecord(zoneId, recordName, apiKey, ntype, extIpAddr)
    else:
        updateRecord(zoneId, recordName, apiKey, id, ntype, extIpAddr)
    logging.info(f'IP address update success: {currentIp} ==> {extIpAddr}')


if __name__ == '__main__':
    logging.basicConfig(level = logging.INFO)

    if len(sys.argv) == 1:
        logging.error(f'No argument provided\nipv6: {sys.argv[0]} AAAA\nipv4: {sys.argv[0]} A')
        exit(1)

    updateIp(sys.argv[1])