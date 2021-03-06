from model import *
import requests
import time
from pprint import pprint
import threading
import random

N_EPOCHS = 5  # request N_EPOCHS time each time
N_BATCHES = 6
JOBS = []
USER_URLS = []
INTERVAL = 143
LOCK = threading.Lock()
GAP = 1
SAFETY_PARAM = 3
USER_AGENTS = open('user-agents.txt').read().split('\n')

CACHE_EVENT_URL = {}  # {#url_id: {
#       end_status_code : #end_status_code
#       end_timestamp : #end_timestamp
#       }
# }


class Checker(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.sess = requests.session()
        self.event = Event()
        self.datapoints = None
        self.url = Url()

    def get_one_job(self):
        global JOBS
        job = (None, None)
        LOCK.acquire()
        if JOBS:
            job = JOBS.pop(0)
        LOCK.release()
        return job

    def run(self):
        while 1:
            id, url = self.get_one_job()
            if id:
                datapoint_generator = self.datapoint_generator(id, url)
                self.event.insert(datapoint_generator)
                event_generator = self.event_generator(id)
                self.event.insert(event_generator)

            time.sleep(GAP)

    def datapoint_generator(self, url_id, url):
        self.datapoints = []
        for datapoint in self.request(url):
            self.datapoints.append(datapoint)
            for _url_id, _user_id in USER_URLS:
                if _url_id == url_id:
                    metadata = {
                        'user_id': _user_id,
                        'url_id': _url_id,
                        '_index': 'webassistant3',
                        '_type': 'datapoint'
                    }
                    metadata.update(datapoint)
                    yield metadata

    def calculate_event(self, url_id):
        global CACHE_EVENT_URL
        assert len(self.datapoints) > 0 and len(self.datapoints) <= N_EPOCHS

        last_datapoint = self.datapoints[len(self.datapoints)-1]
        timestamp = time.time()

        if url_id not in CACHE_EVENT_URL.keys():
            CACHE_EVENT_URL[url_id] = {
                'end_status_code': last_datapoint['status_code'],
                'end_timestamp': timestamp
            }
            metadata = {
                'start_status_code': last_datapoint['status_code'],
                'duration': None,
                'timestamp': timestamp,
                'screenshot': None,
                'type' : None
            }
            if metadata['start_status_code'] == 200:
                self.url.update_status(1, url_id)
            else:
                self.url.update_status(0, url_id)
            metadata['type'] = 'Start'
            return [metadata]

        else:
            if CACHE_EVENT_URL[url_id]['end_status_code'] != last_datapoint['status_code']:
                metadata = {
                    'end_status_code': CACHE_EVENT_URL[url_id]['end_status_code'],
                    'start_status_code': last_datapoint['status_code'],
                    'duration': timestamp - CACHE_EVENT_URL[url_id]['end_timestamp'],
                    'timestamp': timestamp,
                    'screenshot': None,
                    'type': None
                }
                CACHE_EVENT_URL[url_id] = {
                    'end_status_code': last_datapoint['status_code'],
                    'end_timestamp': timestamp
                }
                if metadata['start_status_code'] == 200:
                    self.url.update_status(1, url_id)
                else:
                    self.url.update_status(0, url_id)
                      
                if metadata['start_status_code'] < 400:
                    metadata['type'] = 'Up'
                else:
                    metadata['type'] = 'Down'
                return [metadata]
            return []

    def event_generator(self, url_id):
        for event in self.calculate_event(url_id):

            for _url_id, _user_id in USER_URLS:
                if event['duration'] == None:
                    if self.event.had_first_event(_user_id, _url_id):
                        continue
                if _url_id == url_id:
                    metadata = {
                        'user_id': _user_id,
                        'url_id': _url_id,
                        '_index': 'webassistant3',
                        '_type': 'event'
                    }
                    metadata.update(event)
                    print(metadata)
                    yield metadata

    def request(self, url):
        headers = {'User-agent': random.choice(USER_AGENTS)}
        for i in range(N_EPOCHS):
            try:
                r = self.sess.get(url, timeout=30, headers=headers)
            except:
                data = {
                    'time_response': None,
                    'status_code': 408,
                    'timestamp': time.time()
                }
            else:
                data = {
                    'time_response': r.elapsed.total_seconds(),
                    'status_code': r.status_code,
                    'timestamp': time.time()
                }
            finally:
                yield data
                if data['status_code'] == 200:
                    break
                time.sleep(0.1)


class WebChecker():

    def __init__(self):
        self.url = Url()

    def decon(self):
        new_threads = int(self.url.count() / N_BATCHES *
                          SAFETY_PARAM) - threading.active_count()
        if new_threads > 0:
            for i in range(new_threads):
                print('Start new thread', threading.active_count())
                thread = Checker()
                thread.daemon = True
                thread.start()

    def reschedule(self):
        global JOBS

        urls = self.url.get()  # return ((1, u'http://vnist.vn'), (2, u'https://beta.vntrip.vn'), (3, u'https://vinhphuc1000.vn'), (4, u'https://lab.vnist.vn'))
        len_urls = len(urls)

        start_at = time.time()
        for i in range(0, len_urls, N_BATCHES):

            LOCK.acquire()
            JOBS += urls[0:N_BATCHES]
            LOCK.release()
            urls = urls[N_BATCHES:]
            print('Number of jobs =', len(JOBS))
            # print '    continue in', INTERVAL / len_urls * N_BATCHES
            time.sleep(INTERVAL / len_urls * N_BATCHES)

        if len(urls):
            LOCK.acquire()
            JOBS += urls
            LOCK.release()

    def update_user_urls(self):
        global USER_URLS
        USER_URLS = self.url.get_user_url()

    def run(self):
        while 1:
            reload()
            self.update_user_urls()
            self.decon()
            self.reschedule()
            time.sleep(1)

if __name__ == '__main__':
    WebChecker().run()
