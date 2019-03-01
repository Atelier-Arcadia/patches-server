'''Client functions used to fetch information about vulnerabilities
from version 1 of the Clair API.

See https://coreos.com/clair/docs/latest/api_v1.html for more information.
'''

from dataclasses import dataclass
from typing import Optional

import requests

from vulnerability import Vulnerability, Severity, Package


_DEFAULT_BASE_ADDR = 'http://127.0.0.1:6060'


@dataclass
class Client:
    '''An interface for fetching vulnerabilities from the Clair API.
    '''

    platform: str
    _base_addr: str = _DEFAULT_BASE_ADDR
    _fetch_limit: int = 128
    _next_page: Optional[str] = ''

    def has_vulns(self):
        '''Determine if the client has any more vulnerabilities to retrieve.
        '''

        return self._next_page is not None


    def retrieve_vulns(self):
        '''Retrieve vulnerabilities, returning a generator that will yield
        each one as it's fetched from the Clair API.
        '''

        np = self._next_page
        next_page = np if np not in ['', None] else None

        pform = self.platform
        baddr = self._base_addr
        limit = self._fetch_limit
            
        summaries = _summaries(pform, baddr, limit, next_page)

        self._next_page = summaries.get('NextPage', None)

        def generator():
            for summary in summaries:
                name = summary.get('Name', None)

                if name is None:
                    continue

                description = _description(pform, name, baddr)

                yield _to_vulnerability(pform, description)

        return generator


def new(platform, config):
    '''Construct a new Client to retrieve vulnerabilities affecting a particular
    platform with optional configuration values.
    '''

    base_addr = config.get('baseAddress', _DEFAULT_BASE_ADDR)

    fetch_limit = config.get('fetchLimit', 128)

    return Client(platform, base_addr, fetch_limit)


def _summaries_url(
    platform,
    base=_DEFAULT_BASE_ADDR,
    num_to_fetch=128,
    next_page=None):
    '''Construct the URL that GET requests can be made to to fetch summaries
    of vulnerabilities available for a particular platform.
    '''

    p = next_page
    pf = platform
    fetch = num_to_fetch

    if next_page is None:
        return f'{base}/v1/namespaces/{pf}/vulnerabilities?limit={fetch}'

    return f'{base}/v1/namespaces/{pf}/vulnerabilities?limit={fetch}&page={p}'


def _description_url(platform, vuln_name, base=_DEFAULT_BASE_ADDR):
    '''Construct the URL that GET requests can be made to to fetch a
    detailed description of one vulnerability affecting a particular
    platform.
    '''

    vuln = vuln_name

    return f'{base}/v1/namespaces/{platform}/vulnerabilities/{vuln}?fixedIn'
  

def _summaries(
    platform,
    num_to_fetch=128,
    base=_DEFAULT_BASE_ADDR,
    next_page=None):
    '''Make a GET request to fetch some number of vulnerability summaries
    affecting a particular platform.
    '''

    req_url = _summaries_url(platform, base, num_to_fetch, next_page)

    return requests.get(req_url).json()


def _description(
    platform,
    vuln_name,
    base=_DEFAULT_BASE_ADDR):
    '''Make a GET request to fetch a description of a vulnerability affecting
    a particular platform.
    '''

    req_url = _description_url(platform, vuln_name, base)
    vuln_json = requests.get(req_url).json()

    return _to_vulnerability(platform, vuln_json)


def _to_vulnerability(platform, description_json):
    '''Convert a JSON description of a vulnerability served by Clair into a
    patches.Vulnerability.
    '''

    is_vuln = all([
        key in description_json
        for key in [ 'Name', 'Link', 'Severity', 'FixedIn' ]
    ])

    if not is_vuln:
        return None

    return Vulnerability(
        description_json['Name'],
        platform,
        description_json['Link'],
        _to_severity(description_json['Severity']),
        [ _to_package(fix) for fix in description_json['FixedIn'] ],
    )


def _to_severity(sev_name):
    '''Convert the name of a vulnerability severity served by Clair into a
    patches.Severity.
    '''

    mapping = {
        'Unknown': Severity.UNKNOWN,
        'Negligible': Severity.NEGLIGIBLE,
        'Low': Severity.LOW,
        'Medium': Severity.MEDIUM,
        'High': Severity.HIGH,
        'Urgent': Severity.URGENT,
        'Defcon': Severity.CRITICAL,
    }

    return mapping.get(sev_name, Severity.UNKNOWN)


def _to_package(package_json):
    '''Convert a description of a package served by Clair into a
    patches.Package.
    '''

    is_package = 'Name' in package_json and 'Version' in package_json

    if not is_package:
        return None

    return Package(package_json['Name'], package_json['Version'])