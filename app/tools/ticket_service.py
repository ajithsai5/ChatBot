"""Ticketing integration helpers for incidents, problems, and change records.

Main responsibility:
- Query the ITSM data-mart (PostgreSQL) for incidents, problems, and changes.
- Fetch Dynatrace, Splunk, and CrUX performance data from monitoring APIs.
- Correlate user queries with similar tickets via embedding similarity.

Not handled here:
- Tool registry or LLM tool-call resolution (see registry.py, dispatcher.py).
"""

import datetime
import hashlib
import json
import logging
import os
import re

import psycopg2
import requests

from config import env
from app.chat.search import get_embeddings
from app.tools.constants import vbf_list


LOGGER = logging.getLogger(__name__)

conn_details: dict = {
    "host": "itsm_dm_prod.optum.com",
    "database": "itsm_dm",
    "user": os.getenv("DATA_MART_DB_USER"),
    "password": os.getenv("DATA_MART_DB_PASSWORD"),
    "port": "5432",
}


def get_latest_inc(args: dict) -> tuple:
    """Fetch recent incidents from the ITSM data-mart."""
    LOGGER.debug("Getting latest incidents: %s", args)
    last_X_days = 30
    
    def generate_sql(start_date, end_date,fields):
        field_str = ', '.join(fields)
        fields = '*'
        sql = f"select {field_str} from SM_DM.SM_INCIDENTS where \"assignment\" = 'COMMUNITY_PORTAL' and open_time between \'" + start_date + "\' and \'" + end_date + "\'"
        return sql
    
    fields = ['uh_assignee_full_name', 'brief_description', 'in_id', 'update_action', 'resolution', 'open_time', 'priority_code', 'sm_incidents.status']
    sql = generate_sql(
        (datetime.datetime.now() - datetime.timedelta(days=last_X_days)).strftime('%Y-%m-%d 00:00:00.000'),
        (datetime.datetime.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d 00:00:00.000'),
        fields
    )

    conn = psycopg2.connect(**conn_details)
    cur = conn.cursor()
    cur.execute(sql)
    results = cur.fetchall()
    

    for i,r in enumerate(results):
        r = list(r)
        r[fields.index('priority_code')] = "Priority Code: P" + r[fields.index('priority_code')]
        r[fields.index('sm_incidents.status')] = "INC State: " + r[fields.index('sm_incidents.status')]
        results[i] = r
    cur.close()
    LOGGER.debug("Incident results count: %s", len(results))
    return (f"Here are incidents from the last {last_X_days} days.",results if len(results) > 0 else f"No Incidents found in the last {last_X_days} days.")


def get_latest_prb(args: dict) -> tuple:
    """Fetch recent problems from the ITSM data-mart."""
    last_X_days = 30
    def generate_sql(start_date, end_date,fields):
        field_str = ', '.join(fields)
        sql = f"select {field_str} from SM_DM.sm_problems sp where \"assignment\" = 'COMMUNITY_PORTAL' and open_time between \'" + start_date + "\' and \'" + end_date + "\'"
        return sql
    fields = ['pr_id', '\"assignment\"', 'status', 'brief_description', 'description_details', '\"open\"', 'open_time', 'update_time', 'close_time', 'priority_code', 'incident_category', 'incident_count', 'closure_code', 'resolution', 'rootcausedate', 'rootcause', 'update_work_log', 'workaround', 'uh_solution_summary', 'uh_root_cause_summary', 'uh_assignee_full_name', 'uh_goal_resolution_planned', 'uh_type', 'uh_category_explanation', 'sn_created_to_support_inc', 'uh_total_days_open', 'uh_days_since_last_worked', 'uh_closed_at', 'sn_rca_review', 'failed_service_ci_id', 'sys_created_on']
    sql = generate_sql((datetime.datetime.now() - datetime.timedelta(days=last_X_days)).strftime('%Y-%m-%dT00:00:00.000Z'),(datetime.datetime.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%dT00:00:00.000Z'),fields)
    conn = psycopg2.connect(**conn_details)
    cur = conn.cursor()
    cur.execute(sql)
    results = cur.fetchall()

    for i,r in enumerate(results):
        r = list(r)
        r[fields.index('priority_code')] = "Priority Code: " + r[fields.index('priority_code')]
        r[fields.index('status')] = "PRB State: " + r[fields.index('status')]
        results[i] = r
    cur.close()
    return (f"Here are PRBs from the last {last_X_days} days.",results if len(results) > 0 else f"No PRBs found in the last {last_X_days} days.")

def get_latest_chg(args: dict) -> tuple:
    """Fetch recent change records from the ITSM data-mart."""
    last_X_days = 30
    def generate_sql(start_date, end_date,fields):
        field_str = ', '.join(fields)
        sql = f"select {field_str} from sm_dm.sm_changes sc  where sc.assign_dept = 'COMMUNITY_PORTAL - CHG' and sc.close_time >= '{start_date}' and sc.close_time <= '{end_date}'"
        return sql
    fields = ['ch_id', 'current_phase', 'ch_category', 'brief_description', 'status', 'risk_assessment', 'date_entered', 'subcategory', 'description', 'justification', 'backout_method', 'closing_comments', 'implementationcomments', 'uh_requester_name', 'uh_assigned_to_name', 'implementation_plan']
    sql = generate_sql((datetime.datetime.now() - datetime.timedelta(days=last_X_days)).strftime('%Y-%m-%dT00:00:00.000Z'),(datetime.datetime.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%dT00:00:00.000Z'),fields)
    conn = psycopg2.connect(**conn_details)
    cur = conn.cursor()
    cur.execute(sql)
    results = cur.fetchall()

    for i,r in enumerate(results):
        r = list(r)
        r[fields.index('status')] = "CHG State: " + r[fields.index('status')]
        results[i] = r
    cur.close()
    return (f"Here are CHGs from the last {last_X_days} days.",results if len(results) > 0 else f"No CHGs found in the last {last_X_days} days.")


def get_incidents(user_input: str, search: str, logger=None) -> tuple[str, str]:
    """Find similar incidents by ID or embedding similarity."""
    try:
        pattern = r"\bINC\d+\b"
        outdata = ""
        matches = re.findall(pattern, user_input, re.IGNORECASE)
        
        if matches:
            LOGGER.debug("Incident Found: %s", matches[0])

            hashed_input_inc = hashlib.sha256(matches[0].encode()).hexdigest()
            similar_inc_base_url = f'{env.get_tickets_endpoint()}/tickets/incidents/similar?id='
            similar_inc_url = similar_inc_base_url + hashed_input_inc
            
            response = requests.get(similar_inc_url,verify='./optum.pem')
            if response.status_code != 200 : 
                cont =  response.content
            if response.status_code == 200 :
                data = json.loads(response.content)
                cont = "<br><br><strong>Similar Incident Tickets: </strong><br>"
                for d in data:
                    cont = cont + " "+ d["ID"] + f' [{int(d["Similarity score"]*100)}% Similar]' + "<br>"
                    if logger:
                        logger.add_incident(d["ID"])
                inc_base_url = f'{env.get_tickets_endpoint()}/tickets/incidents/get?id='
                inc_url = inc_base_url + hashed_input_inc
                response = requests.get(inc_url,verify='./optum.pem')

                data = json.loads(response.content)
                search += data["description"] + ' '
        else :
            LOGGER.debug("INC pattern not found, using embedding similarity.")
            req_body = {
                "desc" : get_embeddings(user_input)
            }
            response = requests.post(f'{env.get_tickets_endpoint()}/tickets/incidents/similar/list',data=json.dumps(req_body),verify='./optum.pem')
            if (response.status_code == 200):
                data = json.loads(response.content)
                    
                cont = "<br><br><strong>Similar Incident Tickets: </strong><br>"
                for d in data[:5]:
                    LOGGER.debug("Incident similarity keys: %s", list(d.keys()))
                    short_desc = d['short_description'].replace('\n',' ')
                    short_desc = short_desc[:150] + '...' if len(short_desc) > 150 else short_desc
                    cont = cont + d['id'] + " " + short_desc + "<br>"
                    if logger:
                        logger.add_incident(d["id"])
                outdata = cont
        return outdata,search
    except Exception as exc:
        LOGGER.warning("Failed to get Incident Tickets: %s", exc)
        return '', ''


def get_problems(user_input: str, search: str, logger=None) -> tuple[str, str]:
    """Find similar problems by ID or embedding similarity."""
    try:
        pattern = r"\bPRB\d+\b"
        outdata = ""
        matches = re.findall(pattern, user_input, re.IGNORECASE)
        
        if matches:
            LOGGER.debug("Problem Found: %s", matches[0])
            hashed_input_prb = hashlib.sha256(matches[0].encode()).hexdigest()
            similar_prb_base_url = f'{env.get_tickets_endpoint()}/tickets/problems/similar?id='
            similar_prb_url = similar_prb_base_url + hashed_input_prb
            response = requests.get(similar_prb_url,verify='./optum.pem')

            if response.status_code != 200 : 
                cont =  response.content
            if response.status_code == 200 :
                data = json.loads(response.content)
                cont = "<br><br><strong>Similar Problem Tickets: </strong><br>"
                for d in data:
                    cont = cont + " "+ d["ID"] + f' [{int(d["Similarity score"]*100)}% Similar]' + "<br>"
                    if logger:
                        logger.add_problem(d["ID"])
                outdata =  cont + "You can find detailed information about each Similar Problem by using their ID :  https://hcccloud-uhgdlm-dtlapi-dev.uhc.com/lpm-gpd-tickets/."
                
                
                prb_base_url = f'{env.get_tickets_endpoint()}/tickets/problems/get?id='
                prb_url = prb_base_url + hashed_input_prb
                response = requests.get(prb_url,verify='./optum.pem')
                data = json.loads(response.content)
                search += data["description"] + ' '
       
        return outdata,search
    except Exception as exc:
        LOGGER.warning("Failed to get Problem Tickets: %s", exc)
        return '', ''


def get_us(search: str, vbf=None, logger=None) -> str:
    """Fetch similar user stories via embedding similarity."""
    try:
        url = f"{env.get_tickets_endpoint()}/tickets/rally/get"
        req_body = {
            "desc" : get_embeddings(search),
            "vbf": vbf
        }
        if vbf and logger:
            logger.set_vbf(vbf)
        LOGGER.debug("Fetching US from: %s", url)
        response = requests.post(url,data=json.dumps(req_body),verify='./optum.pem')
        
        if (response.status_code == 200):
            datas = json.loads(response.content)
            if len(datas) > 0:
                LOGGER.debug("First US result: %s", datas[0])
                outdata = " <br>" + "<strong>Recent User Stories</strong> :"
                for data in datas[:2]:
                    outdata += " <br>" + data['FormattedID'][0] + " ⦂ "+ data["FeatureName"][0] + " worked By <strong>"+ data["Project"][0] +"</strong>" 
                    outdata += "<br>"
                    if logger:
                        logger.add_story(data['FormattedID'][0])
                return outdata
    except Exception as exc:
        LOGGER.warning("Failed to get User Stories: %s", exc)
    return ''

def get_related_tickets(user_input: str, search: str, logger=None) -> str:
    """Find related incident and problem tickets."""
    inc_res, inc_search = get_incidents(user_input, search, logger=logger)
    prb_res, prb_search = get_problems(user_input, search, logger=logger)
    return inc_res + prb_res


def get_related_stories(search: str, args: dict, logger=None) -> str:
    """Find related user stories via embedding similarity."""
    return get_us(search, None, logger=logger)

def query_quick_links(category: str | None = None) -> list | str:
    """Fetch quick-links from the tickets service, optionally filtered by category."""
    try:
        url = f'{env.get_tickets_endpoint()}/tickets/quick_links{"" if category is None else "?category="+category}' 
        response = requests.get(url,verify='./optum.pem')
        if (response.status_code == 200):
            datas = json.loads(response.content)
            return datas
    except Exception as exc:
        LOGGER.warning("Failed to get Quick Links: %s", exc)
    return 'Failed to get Quick Links'


def get_splunk_report(args: dict):
    """Fetch Splunk status-code aggregation data for UHCCP."""
    try:
        url = "http://mr-portals-monitoring.optum.com/elasticsearch/splunk-status-codes*/_search"

        querystring = {"ignore_throttled":"false"}
        payload = {"aggs": {"0": {"terms": {"field": "VBF.keyword","size": 50},"aggs": {"4xx Count": {"sum": {"field": "4xx_count"}},"Total Traffic": {"sum": {"field": "count"}},"5xx Count": {"sum": {"field": "5xx_count"}},"4xx Percent": {"bucket_script": {"buckets_path": {"fourxx": "4xx Count","total": "Total Traffic"},"script": "params.fourxx / params.total * 100"}},"5xx Percent": {"bucket_script": {"buckets_path": {"fivexx": "5xx Count","total": "Total Traffic"},"script": "params.fivexx / params.total * 100"}}}}},"size": 0,"query": {"bool": {"must": [],"filter": [{"bool": {"must": [],"filter": [{"bool": {"minimum_should_match": 1,"should": [{"term": {"application.keyword": {"value": "UHCCP"}}}]}},{"match_phrase": {"env.keyword": "UHCCP - Prod"}},{"match_phrase": {"VBF.keyword": "UHCCP"}}],"should": [],"must_not": []}},{"range": {"startTime": {"format": "strict_date_optional_time","gte": args.get('from_date', "now-1d/d/d-8d/d") ,"lte": args.get('to_date', "now-1d/d")}}}],"should": [],"must_not": []}}}
        headers = {'Content-Type': 'application/json'}

        response = requests.request("POST", url, json=payload, headers=headers, params=querystring) 

        return response.json()["aggregations"]["0"]["buckets"]
    except Exception as exc:
        LOGGER.warning("Error in getting splunk report: %s", exc)
        return str(exc)


def get_dynatrace_problems(search: str, args: dict) -> str:
    """Fetch active Dynatrace problems for UHCCP production."""
    url = "https://dtsaas.uhc.com/e/4944fc42-016d-4462-8104-a110143a2322/api/v2/problems"

    querystring = {"from":"now-1d","pageSize":"500"}

    payload = ""
    headers = {
        'Authorization': os.getenv("DYNATRACE_API"),
        'Accept': "application/json"
    }

    response = requests.request("GET", url, data=payload, headers=headers, params=querystring,verify='./standard_trusts.pem')

    if response.status_code != 200:
        return f"Error: {response.status_code}, {response.text}"

    prblms =  response.json()
    active_prb = []

    for i in range(len(prblms['problems'])):
        # if prblms['problems'][i]["status"]== "OPEN":
        #     active_prb.append(prblms['problems'][i])
        if prblms['problems'][i]['impactedEntities'][0]['name'] in ["prd-uhccommunityplan.uhc.com","UHCCP"]:
            active_prb.append(prblms['problems'][i])

    LOGGER.debug("Filtered Active Problems: %s", len(active_prb))

    summary_out =""
    if len(active_prb) <1: 
        summary_out = "There are no Active problem in Dynatrace as of Now!"
        #return summary_out
    else :
        summary_out = "There are "+str(len(active_prb)) +" Active problems in Dynatrace. Few of them are : " 
        for p in active_prb:
            summary_out += (
                f" <br>- <a href='https://dtsaas.uhc.com/e/4944fc42-016d-4462-8104-a110143a2322/#problems/problemdetails;gtf=today;gf=all;pid={p['problemId']}' >"
                f"<Strong>{p['problemId']}</Strong></a> : {p['title']} {p['displayId']} in {p['impactedEntities'][0]['name']} - Status: {p['status']}"
            )        

    return summary_out


def get_crux_report(args: dict):
    """Fetch Chrome UX Report (CrUX) data for UHCCP production."""
    url = "http://mr-portals-monitoring.optum.com/elasticsearch/google_psi*/_search"

    querystring = {"ignore_throttled": "false"}
    vbf = None  # Set to None if not valid or not provided

    if args and args.get('VBF'):
        for vi in vbf_list:
            if vi.lower() == args['VBF'].lower():
                vbf = vi
                break

    payload = {
        "query": {
            "bool": {
                "must_not": [{"match_phrase": {"strategy.keyword": "desktop"}}],
                "filter": [
                    {
                        "range": {
                            "startTime": {
                                "time_zone": "America/Chicago",
                                "gte": args.get("from_date", "now-1d/d"),
                                "lte": args.get("to_date", "now/d"),
                                "format": "strict_date_optional_time",
                            }
                        }
                    },
                    {"match_phrase": {"Env.keyword": "Online - Prod"}},
                    {"match_phrase": {"Application.keyword": "UHCCP"}},
                ],
                "should": [],
            }
        },
        "aggs": {
            "dates": {
                "date_histogram": {
                    "field": "startTime",
                    "fixed_interval": "1d",
                    "time_zone": "US/Central",
                    "min_doc_count": 0,
                },
                "aggs": {
                    "crux_interaction_to_next_paint": {
                        "avg": {"field": "crux_interaction_to_next_paint"}
                    },
                    "crux_cumulative_layout_shift_score": {
                        "avg": {
                            "field": "crux_cumulative_layout_shift_score",
                            "script": {
                                "lang": "painless",
                                "source": "doc['crux_cumulative_layout_shift_score'].value /100.0",
                            },
                        }
                    },
                    "crux_experimental_time_to_first_byte": {
                        "avg": {
                            "field": "crux_experimental_time_to_first_byte",
                            "script": {
                                "lang": "painless",
                                "source": "doc['crux_experimental_time_to_first_byte'].value /1000.0",
                            },
                        }
                    },
                    "crux_first_contentful_paint_ms": {
                        "avg": {
                            "field": "crux_first_contentful_paint_ms",
                            "script": {
                                "lang": "painless",
                                "source": "doc['crux_first_contentful_paint_ms'].value /1000.0",
                            },
                        }
                    },
                    "crux_largest_contentful_paint_ms": {
                        "avg": {
                            "field": "crux_largest_contentful_paint_ms",
                            "script": {
                                "lang": "painless",
                                "source": "doc['crux_largest_contentful_paint_ms'].value /1000.0",
                            },
                        }
                    },
                    "crux_first_input_delay_ms": {
                        "avg": {"field": "crux_first_input_delay_ms"}
                    },
                },
            }
        },
    }

    # Add VBF filter if valid
    if vbf:
        vbf_filter = {"match_phrase": {"VBF.keyword": vbf}}
        payload["query"]["bool"]["filter"].append(vbf_filter)

    LOGGER.debug("CrUX Payload: %s", json.dumps(payload, indent=2))

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.request(
            "POST", url, json=payload, headers=headers, params=querystring
        )
        response.raise_for_status()  # Raise an error for HTTP issues
        return response.json()["aggregations"]["dates"]["buckets"]
    except Exception as exc:
        LOGGER.warning("Error in getting crux report: %s", exc)
        return str(exc)


def get_performance_score(args: dict):
    """Fetch browser performance scores from the monitoring Elasticsearch cluster."""
    try:
        url = "http://mr-portals-monitoring.optum.com/elasticsearch/user_actions*/_search"

        querystring = {"ignore_throttled":"false"}
        LOGGER.debug("Performance score args: %s", args)
        
        payload = { "size": 0,"query": {"bool": {"must": [],"filter": [{"range": {"startTime": {"format": "strict_date_optional_time","gte": args.get('from_date', "now-1d/d/d-8d/d") ,"lte": args.get('to_date', "now-1d/d")}}},{"bool": {"must": [],"filter": [{"bool": {"minimum_should_match": 1,"should": [{"match_phrase": {"application.keyword": "UHCCP"}}]}},{"match_phrase": {"supported_browser": True}}],"should": [],"must_not": []}}],"should": [],"must_not": []}},"aggs": {"0":{"terms": {"field": "vbf.keyword","size": 50,"shard_size": 25},"aggs": {"90th Percentile Performance": { "percentiles": {"field": "performanceMetric","percents": [90],"script": {"lang": "painless","source": "doc['performanceMetric'].value /1000.0"}}},"Median Performance": { "percentiles": {"field": "performanceMetric","percents": [50],"script": {"lang": "painless","source": "doc['performanceMetric'].value /1000.0"}}}}}}}
        headers = {'Content-Type': 'application/json'}

        response = requests.request("GET", url, json=payload, headers=headers, params=querystring) 

        return response.json()["aggregations"]["0"]["buckets"]
    except Exception as exc:
        LOGGER.warning("Error in getting performance report: %s", exc)
        return str(exc)

