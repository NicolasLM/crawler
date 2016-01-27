Crawl the web for fun
=====================

Have you ever heard statistics like "half of the websites in the world run
Apache" or "the number one hosting company in the US is xxx"? Have you ever
wondered how these figures were calculated? Well I do and I was a bit
skeptical, so I've decided to write my own crawler in Python to check this by
myself.

Fortunately Python makes this super easy. Basically the whole program is:

* fetch the homepage of a domain with requests
* search for all the links to external domains with Beautiful Soup
* schedule a Celery job for these domains
* repeat

The crawler only checks the homepage of each domain. Why that? Because hitting
once every website in the world sounds possible, however hitting once every
page of every website must be quite costly. The downside is that it will
probably miss a few domains.

Getting information about networks
----------------------------------

In order to display useful information this program needs to fetch data about
the network hosting a website. This is usually done with the Maxmind GeoIP
database. However it is not freely available, so instead it uses two different
databases:

* GeoLite2 Country from Maxmind
* An ASN database generated from routeviews.org (more on that later)

Installation
------------

This program is written in Python 3. Start by cloning the repository:

    git clone https://github.com/NicolasLM/crawler.git
    cd crawler

Create a new virtualenv:

    pyvenv venv
    source venv/bin/activate

Install the package and its requirements:

    pip install --editable .

Run Redis which is used by Celery as broker and result backend:

    docker run -d redis

Run RethinkDB, a document store to save data about domains:

    docker run -d rethinkdb rethinkdb --bind all

Download GeoLite2 Country from http://dev.maxmind.com/geoip/geoip2/geolite2/

Download and format the ASN db used by pyasn:

    pyasn_util_download.py --latest
    pyasn_util_convert.py --single rib.2016[...].bz2 ipasn.dat

You might want to tweak `crawler/conf.py` before initializing RethinkDB:

    crawler rethinkdb

Usage
-----

Put a single domain in the Celery task list:

    crawler insert www.python.org

Run 10 Celery workers in parallel:

    celery worker -A crawler.crawler.app -c 10 -P threads -Ofair --loglevel INFO

Explore the command line and get statistics:

    $ crawler countries --count 5
    Top 5 countries
             France  711
      United States  698
              Japan  367
        Netherlands  175
            Germany  73


License
-------

MIT
