from setuptools import setup

setup(
    name='crawler',
    version='0.1.0',
    include_package_data=True,
    install_requires=[
        'celery[redis]==3.1.19',
        'redis==2.10.5',
        'rethinkdb==2.2.0.post1',
        'requests==2.9.1',
        'beautifulsoup4==4.4.1',
        'click==6.2',
        'geoip2==2.2.0',
        'pyasn==1.5.0b6',
        'threadpool==1.3.2'
    ],
    entry_points='''
        [console_scripts]
        crawler=crawler.cli:cli
    ''',
)
