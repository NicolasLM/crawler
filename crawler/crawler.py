from urllib.parse import urlparse
from collections import namedtuple
import socket

import requests
from requests.packages import urllib3
from bs4 import BeautifulSoup
import rethinkdb as r
from celery import Celery
from celery.utils.log import get_task_logger
import pyasn
import geoip2.database, geoip2.errors

import crawler.conf as conf

logger = get_task_logger(__name__)
app = Celery('crawler')
app.config_from_object(conf.CeleryConf)
asn_db = pyasn.pyasn(conf.ASN_FILE)
geoip2_db = geoip2.database.Reader(conf.GEOIP2_FILE)

DomainInfo = namedtuple(
    'DomainInfo',
    ['name', 'elapsed', 'headers', 'linked_domains', 'asn', 'country']
)


class UncrawlableDomain(Exception):
    pass


def get_page(domain):
    urls = ['http://' + domain, 'https://' + domain]
    for url in urls:
        try:
            return requests.get('http://' + domain,
                                timeout=conf.REQUESTS_TIMEOUT)
        except (requests.RequestException, urllib3.exceptions.HTTPError):
            continue
    raise UncrawlableDomain('Cannot crawl ' + domain)


def get_asn_from_ip(ip):
    try:
        return asn_db.lookup(ip)[0]
    except ValueError:
        return None


def get_country_from_ip(ip):
    try:
        return geoip2_db.country(ip).country.name
    except (ValueError, geoip2.errors.AddressNotFoundError):
        return None


def get_domain_info(domain):
    response = get_page(domain)
    if 'text/html' not in response.headers.get('Content-Type', ''):
        raise UncrawlableDomain('Cannot crawl ' + domain)
    
    domains = list()
    soup = BeautifulSoup(response.content, 'html.parser')
    for link in soup.find_all('a'):
        parsed_link = urlparse(link.get('href'))
        if parsed_link.netloc:
            domains.append(parsed_link.netloc.lower())

    try:
        ip = socket.gethostbyname(domain)
        asn = get_asn_from_ip(ip)
        country = get_country_from_ip(ip)
    except socket.gaierror:
        asn = None
        country = None

    return DomainInfo(
        name=domain,
        elapsed=round(response.elapsed.microseconds / 1000),
        headers=response.headers,
        linked_domains=set(domains),
        asn=asn,
        country=country
    )


def record_success(conn, domain_name, domain_info):
    r.table('domains').insert({
        'name': domain_name,
        'success': True,
        'headers': domain_info.headers,
        'elapsed': domain_info.elapsed,
        'asn': domain_info.asn,
        'country': domain_info.country,
        'date': r.now()
    }).run(conn)
    logger.info('Fetched domain {} in {}ms'.format(domain_name,
                                                   domain_info.elapsed))


def record_failure(conn, domain_name):
    r.table('domains').insert({
        'name': domain_name,
        'success': False,
        'date': r.now()
    }).run(conn)
    logger.info('Could not fetch domain {}'.format(domain_name))


@app.task(name='crawler.crawl_domain')
def crawl_domain(domain):

    # Connect to rethinkdb
    conn = r.connect(host=conf.RethinkDBConf.HOST,
                     db=conf.RethinkDBConf.DB)

    # Do not process already crawled domains
    if r.table('domains').filter({'name': domain}).count().run(conn):
        return

    try:
        domain_info = get_domain_info(domain)
    except UncrawlableDomain:
        record_failure(conn, domain)
        return 

    # Create a task for each domain not seen yet
    for linked_domain in domain_info.linked_domains:
        if r.table('domains').filter({'name': linked_domain}).count().run(conn):
            continue
        crawl_domain.delay(linked_domain)

    record_success(conn, domain, domain_info)
