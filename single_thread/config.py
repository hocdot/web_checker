# Load connect to database

import pymysql
from elasticsearch import Elasticsearch


HOST = '192.168.1.65'

class Config:

    def __init__(self):
        self.reload()

    def reload(self):
        # MySQL
        self.mysql_conn = pymysql.connect(
            host=HOST, user='root', password='vnistadmin', db='webassistant3', charset='utf8mb4')
        self.mysql_cur = self.mysql_conn.cursor()

        # ElasticSearch
        self.es = Elasticsearch(['%s:9200' % HOST])

   

if __name__ == '__main__':
    c = Config()
    data = {'create' : {
        '_index' : 'webassistant',
        '_type' : 'type',
        'msg' : 'test'
    }}
    # helpers.bulk(c.es, data)
    c.es.bulk(data)