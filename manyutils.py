# -*- encoding: utf-8 -*-
import os
import json
import datetime

from tldextract import TLDExtract
from termcolor import colored

INFOFILES = [ 'phantom.log', '_traceroutes', 'unique_id', 'used_media.json',
              '_verbotracelogs', 'domain.infos', 'country', 'information',
              'errors.dns', 
              'source_url_configured.json',
              'reverse.dns', 
              'reverse.status.json',
              'reverse.errors.json',
              'resolution.dns', 
              'resolution.status.json',
              'resolution.errors.json',
              'first.json', 'second.json', 'third.json',
              'phantom.results.json', 'trace.results.json' ]

PERMITTED_SECTIONS = [ 'global', 'national', 'local', 'blog', 'removed', 'special', 'all' ]


def get_unique_urls(source_urldir, urldumpsf):
    urls = {}
    with file(urldumpsf) as f:
        for url_request in f.readlines():
            if url_request.startswith('http://'):
                urls[ url_request[7:].split('/')[0] ] = True
            elif url_request.startswith('https://'):
                urls[ url_request[8:].split('/')[0] ] = True
            elif url_request.startswith('data:'):
                continue
            elif url_request.startswith('about:blank'):
                continue
            else:
                print colored("%% Unexpected URL schema '%s' from '%s'" % ( url_request, source_urldir ), 'red')
                continue

    shortened = []
    for unique_url in urls.keys():
        if len(unique_url) > 4096:
            shortened.append(unique_url[:4096])
        else:
            shortened.append(unique_url)
    return shortened


def sortify(outputdir):

    urldict = {}
    skipped = 0

    for urlinfo in os.walk(outputdir):

        filelist = urlinfo[2]

        if not '__urls' in filelist:
            continue

        urlfile = os.path.join(urlinfo[0], '__urls')

        if not os.access(urlfile, 0):
            continue

        related_urls = get_unique_urls(urlinfo[0], urlfile)

        TLDio = TLDExtract(cache_file='mozilla_tld_file.dat')
        for dirty_url in related_urls:
            # dirty_url because may contain ":"

            if dirty_url.split(':') != -1:
                url = dirty_url.split(':')[0]
            else:
                url = dirty_url

            if urldict.has_key(url):
                skipped +=1
                continue

            dnsplit= TLDio(url)
            urldict.update({url : {
                    'domain' : dnsplit.domain,
                    'tld' : dnsplit.suffix,
                    'subdomain' : dnsplit.subdomain }
                })

        # note:
        # https://raw.github.com/mozilla/gecko-dev/master/netwerk/dns/effective_tld_names.dat
        # tldextract is based on this file, and cloudfront.net is readed as TLD. but is fine
        # I've only to sum domain + TLD in order to identify the "included entity"
    return urldict


def url_cleaner(line):

    # cleanurl is used to create the dir, media to phantomjs
    if line.startswith('http://'):
        cleanurl = line[7:]
    elif line.startswith('https://'):
        cleanurl = line[8:]
        # print "https will be converted in http =>", line
    else:
        raise Exception("Invalid protocol in: %s" % line)

    while cleanurl[-1] == '/':
        cleanurl = cleanurl[:-1]

    dirtyoptions = cleanurl.find("?")
    if dirtyoptions != -1:
        cleanurl = cleanurl[:dirtyoptions]

    cleanurl = cleanurl.split('/')[0]
    return cleanurl


def load_global_file(GLOBAL_MEDIA_FILE):

    global_media_list = []
    counter = 0

    TLDio = TLDExtract(cache_file='mozilla_tld_file.dat')

    with file(GLOBAL_MEDIA_FILE, 'r') as f:
        for line in f.readlines():

            line = line[:-1]

            if len(line) > 1 and line[0] == '#':
                continue

            # everything after a 0x20 need to be cut off
            line = line.split(' ')[0]

            if len(line) < 3:
                continue

            entry_records = dict({
                'category': None,
                'url': None,
                'site': None,
            })

            entry_records['category'] = 'global'
            entry_records['url'] = line
            cleanurl = url_cleaner(line)

            domainsplit = TLDio(cleanurl)
            domain_plus_tld = "%s.%s" % (domainsplit.domain, domainsplit.suffix)
            entry_records['site'] = domain_plus_tld

            counter += 1
            global_media_list.append(entry_records)

    return global_media_list


GLOBAL_MEDIA_FILE = 'special_media/global'

def media_file_cleanings(linelist, globalfile=GLOBAL_MEDIA_FILE, permit_flexible_category=False):
    """
    From the format
    [global]
    http://site.com/with.html
    # comment
    [othersec]
    http://otherweb

    return [
        {
            'category': 'global',
            'url': http://site.come/with.html
            'site': site.com
        }, {
            'category': 'othersec',
            'url': http://site.come/with.html
            'site': site.com
        } ]
    """
    retlist = []
    current_section = None
    counter_section = 0

    domain_only = []
    TLDio = TLDExtract(cache_file='mozilla_tld_file.dat')

    for line in linelist:

        entry_records = dict({
            'category': None,
            'url': None,
            'site': None,
        })

        line = line[:-1]

        if len(line) > 1 and line[0] == '#':
            continue

        # everything after a 0x20 need to be cut off
        line = line.split(' ')[0]

        if len(line) < 3:
            continue

        if line.startswith('[') and line.find(']') != -1:
            candidate_section = line[1:-1]

            if permit_flexible_category:
                print colored("Importing URLs in category: %s" % candidate_section, 'green')
                current_section = candidate_section
                continue

            if not candidate_section in PERMITTED_SECTIONS:
                print "The section in", line, "is invalid: do not match with", PERMITTED_SECTIONS
                quit(-1)

            # if we had 'global' section: is special!
            if candidate_section == 'global':
                global_section = load_global_file(globalfile)
                retlist += global_section
                continue

            current_section = candidate_section
            continue

        entry_records['category'] = current_section
        entry_records['url'] = line
        cleanurl = url_cleaner(line)

        domainsplit = TLDio(cleanurl)
        domain_plus_tld = "%s.%s" % (domainsplit.domain, domainsplit.suffix)
        # to spot http://www.nytimes.com vs http://nytimes.com
        entry_records['site'] = domain_plus_tld

        if domain_plus_tld in domain_only and permit_flexible_category == False:
            print colored(u' → %s is part of an already seen domain: %s' % (line, domain_plus_tld), 'blue', 'on_white')
        else:
            domain_only.append(domain_plus_tld)

        retlist.append(entry_records)
        counter_section += 1

    return retlist

