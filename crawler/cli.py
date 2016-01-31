from collections import OrderedDict
from urllib.parse import urlparse

import click
import rethinkdb as r
import redis

import crawler.conf as conf

# cli does not need to be thread-safe
conn = r.connect(host=conf.RethinkDBConf.HOST,
                 db=conf.RethinkDBConf.DB)
domains = r.table('domains')


@click.group()
@click.version_option()
def cli():
    """Crawler command line tool."""


@cli.command('as', short_help='most popular AS')
@click.option('--count', default=15, help='number of AS to show')
def top_as(count):
    """Show which Autonomous Systems are the most popular."""
    data = domains.filter(r.row['success'] == True).\
               group(r.row['asn']).count().run(conn)
    top('Autonomous Systems', count, data)


@cli.command('countries', short_help='most popular countries')
@click.option('--count', default=15, help='number of countries to show')
def top_countries(count):
    """Show which countries are the most popular."""
    data = domains.filter(r.row['success'] == True).\
               group(r.row['country']).count().run(conn)
    top('countries', count, data)


def top(kind, count, data):
    top = OrderedDict(sorted(data.items(), key=lambda t: -t[1]))
    i = 1
    click.secho('Top {} {}'.format(count, kind), bold=True)
    for value, occurences in top.items():
        if not value:
            continue
        click.echo('{:>15}  {}'.format(value, occurences))
        i += 1
        if i > count:
            break


@cli.command('stats', short_help='statistics about domains')
def stats():
    """Show statistics about domains."""
    success = domains.filter(r.row['success'] == True).count().run(conn)
    failure = domains.filter(r.row['success'] == False).count().run(conn)
    redis_url = urlparse(conf.CeleryConf.BROKER_URL)
    redis_conn = redis.StrictRedis(redis_url.hostname,
                                   port=redis_url.port,
                                   db=redis_url.path[1:])
    pending = redis_conn.llen('celery')
    try:
        percent_failure = failure*100/success
    except ZeroDivisionError:
        percent_failure = 0.0

    click.secho('Domain statistics', bold=True)
    click.secho('Success: {}'.format(success), fg='green')
    click.secho('Pending: {}'.format(pending), fg='yellow')
    click.secho('Failed: {} ({:.2f}%)'.format(failure, percent_failure),
               fg='red')


@cli.command('domain', short_help='information about a domain')
@click.argument('name')
def domain(name):
    """Show information about a domain."""
    import pprint
    domain_name = name.lower()
    try:
        pprint.pprint(domains.filter({'name': domain_name}).run(conn).next())
    except r.net.DefaultCursorEmpty:
        click.echo('No information on {}'.format(domain_name))


@cli.command('insert', short_help='insert a domain in the list to crawl')
@click.argument('name')
def insert(name):
    """Insert a domain in the list of domains to crawl."""
    from .crawler import crawl_domain
    name = name.lower()
    crawl_domain.delay(name)
    click.secho('Domain {} added to Celery tasks'.format(name),
                fg='yellow')


@cli.command('rethinkdb', short_help='prepare RethinkDB')
def rethinkdb():
    """Prepare database and table in RethinkDB"""
    from rethinkdb.errors import ReqlOpFailedError, ReqlRuntimeError
    conn = r.connect(host=conf.RethinkDBConf.HOST)

    # Create database
    try:
        r.db_create(conf.RethinkDBConf.DB).run(conn)
        click.secho('Created database {}'.format(conf.RethinkDBConf.DB),
                    fg='yellow')
    except ReqlOpFailedError:
        click.secho('Database {} already exists'.format(conf.RethinkDBConf.DB),
                    fg='green')

    # Create table 'domains'
    conn = r.connect(host=conf.RethinkDBConf.HOST,
                     db=conf.RethinkDBConf.DB)
    try:
        r.table_create('domains', durability=conf.RethinkDBConf.DURABILITY).\
            run(conn)
        click.secho('Created table domains', fg='yellow')
    except ReqlOpFailedError:
        click.secho('Table domains already exists', fg='green')
    
    # Create index on domains.name
    try:
        r.table('domains').index_create('name').run(conn)
        click.secho('Created index domains.name', fg='yellow')
    except ReqlRuntimeError:
        click.secho('Index domains.name already exists', fg='green')


@cli.command('duplicate', short_help='remove duplicated tasks')
def duplicate():
    """Remove duplicated scheduled tasks"""
    import json
    import base64

    from .crawler import app

    redis_url = urlparse(conf.CeleryConf.BROKER_URL)
    redis_conn = redis.StrictRedis(redis_url.hostname,
                                   port=redis_url.port,
                                   db=redis_url.path[1:])
    num_tasks = redis_conn.llen('celery')
    if not num_tasks:
        return

    scheduled_tasks = set()
    task_position = 0
    for i in range(num_tasks):
        print(i, task_position)
        task = json.loads(redis_conn.lindex('celery', task_position).decode())
        task_body = json.loads(base64.b64decode(task['body']).decode())
        task_domain = task_body['args'][0]

        if not task_domain in scheduled_tasks:
            scheduled_tasks.add(task_domain)
            task_position += 1
        else:
            redis_conn.ltrim('celery', task_position, task_position)
            click.secho('Removed duplicated {}'.format(task_domain),
                        fg='yellow')
