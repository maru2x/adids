from elasticsearch import Elasticsearch

def es_client(url="http://127.0.0.1:9200"):
    return Elasticsearch(url, request_timeout=60)

def bucketize_conn_per_min(es, index="filebeat-*", q=None, interval="1m"):
    body = {
        "size": 0,
        "query": q or {"term": {"event.dataset": "zeek.conn"}},
        "aggs": {
            "per": {
                "date_histogram": {"field": "@timestamp", "calendar_interval": interval},
                "aggs": {
                    "bytes": {"sum": {"field": "network.bytes"}},
                    "flows": {"value_count": {"field": "_id"}},
                    "src_ips": {"cardinality": {"field": "source.ip"}},
                    "dst_ips": {"cardinality": {"field": "destination.ip"}}
                }
            }
        }
    }
    resp = es.search(index=index, body=body)
    return resp["aggregations"]["per"]["buckets"]
