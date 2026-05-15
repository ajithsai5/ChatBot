"""Tool registry definitions and callable metadata for function-routing.

Main responsibility:
- Map tool names to OpenAI function-call schemas and their Python callables.
- Provide the single source of truth for all registered chatbot tools.

Not handled here:
- Tool dispatch logic or LLM invocation (see dispatcher.py).
- Tool implementation (see rally_service.py, ticket_service.py, handlers.py).
"""

from app.tools.rally_service import (
    get_allowed_teams,
    get_capabilites,
    get_current_iterations,
    get_current_releases,
    get_defects,
    get_features,
    get_features_states,
    get_rally_obj_info,
    get_rally_obj_info_no_id,
    get_release_defects,
    get_release_features,
    get_user_stories,
    get_user_story_states,
)
from app.tools.ticket_service import (
    get_crux_report,
    get_dynatrace_problems,
    get_latest_chg,
    get_latest_inc,
    get_latest_prb,
    get_performance_score,
    get_splunk_report,
)
from app.tools.constants import vbf_list
from app.link_validator.handlers import (
    get_web_link_validator_status,
    run_web_link_validator_now,
    get_web_link_validator_report,
    cancel_web_link_validator_run,
    email_web_link_validator_report,
)

tools = {
     "get_user_stories": {
        "type": "function",
        "description": "Call this when a user asks for user stories. This will return all data for user stories that are asked about that a team is working on. The user stories can also be filtered by date, iteration, release, or feature.",
        "parameters": {
            "type": "object",
            "properties": {
                "team": {
                    "type": "string",
                    "description": f"The team the user wants user stories for."
                },
                "iteration": {
                    "type": "string",
                    "description": "The iteration for a certain user story. Only use this field when the user states an iteration. Iterations look like this Sprint_Aug_12_2025. There are no spaces in iteration names. Do not make up iteration names. Keep the exact spelling used."
                },
                "release": {
                    "type": "string",
                    "description": "The release for a certain user story. Only use this field when the user states a release. Releases look like this UHCCP_2025_Aug_06 or 2025_Aug_06_GPP-MRPR-Dev. There are no spaces in release names. Do not make up release names."
                },
                "feature": {
                    "type": "string",
                    "description": "The feature for a certain user story. Only use this field when the user states a feature ID. The feature is formatted as F123456. Do not make up feature IDs."
                },
                "from_date": {
                    "type": "string",
                    "description": "The starting date for the query. Fill this field if the user specifies a start time range, and do one day before the mentioned day. Use the same format as 2025-08-01T05:00:00.000"
                },
                "to_date": {
                    "type": "string",
                    "description": "The end date for the query. Fill this field if the user specifies an end time range, and do one day after the mentioned day. Use the same format as 2025-08-01T05:00:00.000"
                },
                "ai": {
                    "type": "string",
                    "description": "Make this True if the user is asking about any AI use. Make this empty if the user is not asking about AI."
                },
                "milestone": {
                    "type": "string",
                    "description": "Make this True if the user is asking about any milestone information. Make this empty if the user is not asking about milestone info."
                },
                "ppm": {
                    "type": "string",
                    "description": "Make this True if the user is asking about PPM projects or PPM IDs. Make this empty if the user is not asking about PPM."
                }
            }
        },
        "doc_count": 2,
        "long_res": True,
        "function": get_user_stories
    },
    "get_features": {
        "type": "function",
        "description": "This will return all data for features that are asked about that a team is working on. The features can also be filtered by date, or release.",
        "parameters": {
            "type": "object",
            "properties": {
                "team": {
                    "type": "string",
                    "description": f"The team the user wants features for. The only teams that can be used are listed before."
                },
                "release": {
                    "type": "string",
                    "description": "The release for a certain feature. Only use this field when the user states a release. Releases look like this UHCCP_2025_Aug_06 or 2025_Aug_06_GPP-MRPR-Dev. There are no spaces in release names. Do not make up release names."
                },
                "from_date": {
                    "type": "string",
                    "description": "The starting date for the query. Fill this field if the user specifies a start time range, and do one day before the mentioned day. Use the same format as 2024-05-01T05:00:00.000"
                },
                "to_date": {
                    "type": "string",
                    "description": "The end date for the query. Fill this field if the user specifies an end time range, and do one day after the mentioned day. Use the same format as 2024-05-01T05:00:00.000"
                },
                "ai": {
                    "type": "string",
                    "description": "Make this True if the user is asking about any AI use. Make this empty if the user is not asking about AI."
                },
                "milestone": {
                    "type": "string",
                    "description": "Make this True if the user is asking about any milestone information. Make this empty if the user is not asking about milestone info."
                },
                "ppm": {
                    "type": "string",
                    "description": "Make this True if the user is asking about PPM projects or PPM IDs. Make this empty if the user is not asking about PPM."
                }
            }
        },
        "doc_count": 2,
        "long_res": True,
        "function": get_features
    },
    "get_current_iterations": {
        "type": "function",
        "description": "Use this when a user asks for current iteration or sprint. This will return the name and dates for the recent iterations for a team.",
        "parameters": {
            "type": "object",
            "properties": {
                "team": {
                    "type": "string",
                    "description": f"The team the user wants the current iteration for. The only teams that can be used are listed before."
                }
            }
        },
        "function": get_current_iterations
    },
    "get_current_releases": {
        "type": "function",
        "description": "Use this when a user asks for what is the current release. This will return the name and dates for the recent releases for a team.",
        "parameters": {
            "type": "object",
            "properties": {
                "team": {
                    "type": "string",
                    "description": f"The team the user wants the current release for. The only teams that can be used are listed before."
                }
            }
        },
        "function": get_current_releases
    },
    "get_rally_obj_info": {
        "type": "function",
        "description": "Get information for a rally object. The user must give an object ID. Determine if the object is a user story, feature, defect or capability.",
        "parameters": {
            "type": "object",
            "properties": {
                "FormattedID": {
                    "type": "string",
                    "description": f"The id given for the object. Examples: US123456, F123456, DE123456, C123456. Do not make up object IDs."
                }
            }
        },
        "doc_count": 2,
        "long_res": True,
        "function": get_rally_obj_info
    },
     "get_rally_obj_info_no_id": {
        "type": "function",
        "description": "Get information for a rally object. The user must be looking for features or user stories without providing an ID. Only call this when the user is describing a task",
        "parameters": {
            "type": "object",
            "properties": {}
        },
        "search": True,
        "function": get_rally_obj_info_no_id
    },
    # "get_release_milestone_info": {
    #     "type": "function",
    #     "description": "Use this to pull release milestone information. This should be used when the user is asking about release milestones. Release milestones include [Sprint 1, Soft Code Freeze (SCF), Push to Redwood Dev, Intergration Sanity in Dev, Push to Redwood QA, QA&E - Sprint Hardening/Regression in QA (Redwood), UAT (Content / Accessibility/ Analytics) Non QA&E in QA (Redwood), Push to Stage (Redwood) for Perf Testing Only, Performance Test Scripting & Execution Stage (Redwood), Hard Code Freeze (HCF), Green Deployment (Redwood), Green Deployment Validation (Redwood), Go/NoGo, Deployment (Redwood)]",
    #     "parameters": {
    #         "type": "object",
    #         "properties": {}
    #     },
    #     "doc_count": 2,
    #     "function": get_release_milestone_info
    # },
    "get_defects": {
        "type": "function",
        "description": "This will return all data for defects that are asked about that a team is working on. The defects can be filtered by date, iteration, or release.",
        "parameters": {
            "type": "object",
            "properties": {
                "team": {
                    "type": "string",
                    "description": f"The team the user wants user stories for."
                },
                "iteration": {
                    "type": "string",
                    "description": "The iteration for a certain user story. Only use this field when the user states an iteration. Iterations look like this Sprint_Aug_12_2025. There are no spaces in iteration names. Do not make up iteration names. Keep the exact spelling used."
                },
                "release": {
                    "type": "string",
                    "description": "The release for a certain user story. Only use this field when the user states a release. Releases look like this UHCCP_2025_Aug_06 or 2025_Aug_06_GPP-MRPR-Dev. There are no spaces in release names. Do not make up release names."
                },
                "from_date": {
                    "type": "string",
                    "description": "The starting date for the query. Fill this field if the user specifies a start time range, and do one day before the mentioned day. Use the same format as 2024-05-01T05:00:00.000"
                },
                "to_date": {
                    "type": "string",
                    "description": "The end date for the query. Fill this field if the user specifies an end time range, and do one day after the mentioned day. Use the same format as 2024-05-01T05:00:00.000"
                }
            }
        },
        "doc_count": 2,
        "long_res": True,
        "function": get_defects
    },
    "get_release_defects": {
        "type": "function",
        "description": "This will return all data for defects in the next release. Use this when the user is asking about defects without specifying a team.",
        "parameters": {},
        "doc_count": 2,
        "long_res": True,
        "function": get_release_defects
    },
    "get_release_features": {
        "type": "function",
        "description": "This will return all data for features in the next release. Use this when the user is asking about features without specifying a team.",
        "parameters": {
            "type": "object",
            "properties": {
            }
        },
        "doc_count": 2,
        "long_res": True,
        "function": get_release_features
    },
     "get_capabilites": {
        "type": "function",
        "description": "This will return all data for capabilites that are asked about that a team is working on. The capabilites can also be filtered by date, or release.",
        "parameters": {
            "type": "object",
            "properties": {
                "team": {
                    "type": "string",
                    "description": f"The team the user wants capabilites for. The only teams that can be used are listed before."
                },
                "release": {
                    "type": "string",
                    "description": "The release for a certain capability. Only use this field when the user states a release. Releases look like this UHCCP_2025_Aug_06 or 2025_Aug_06_GPP-MRPR-Dev. There are no spaces in release names. Do not make up release names."
                },
                "from_date": {
                    "type": "string",
                    "description": "The starting date for the query. Fill this field if the user specifies a start time range, and do one day before the mentioned day. Use the same format as 2024-05-01T05:00:00.000"
                },
                "to_date": {
                    "type": "string",
                    "description": "The end date for the query. Fill this field if the user specifies an end time range, and do one day after the mentioned day. Use the same format as 2024-05-01T05:00:00.000"
                }
            }
        },
        "doc_count": 2,
        "long_res": True,
        "function": get_capabilites
    },

    "get_allowed_teams": {
        "type": "function",
        "description": "This will return the teams that are allowed to be queried with this chatbot.",
        "parameters": {},
        "function": get_allowed_teams
    },
    # "get_features_plan_estimates": {
    #     "type": "function",
    #     "description": "This will return the plan estimates for features that are asked about. The features can also be filtered by date, or release.",
    #     "parameters": {
    #         "type": "object",
    #         "properties": {
    #             "team": {
    #                 "type": "string",
    #                 "description": f"The team the user wants the plan estimates of features for. The only teams that can be used are listed before."
    #             },
    #             "release": {
    #                 "type": "string",
    #                 "description": "The release for a certain feature. Only use this field when the user states a release. Releases look like this 2024_Jul_24_GPP-MRPR-Dev. There are no spaces in release names. Do not make up release names."
    #             },
    #             "from_date": {
    #                 "type": "string",
    #                 "description": "The starting date for the query. Fill this field if the user specifies a start time range, and do one day before the mentioned day. Use the same format as 2024-05-01T05:00:00.000"
    #             },
    #             "to_date": {
    #                 "type": "string",
    #                 "description": "The end date for the query. Fill this field if the user specifies an end time range, and do one day after the mentioned day. Use the same format as 2024-05-01T05:00:00.000"
    #             }
    #         }
    #     },
    #     "doc_count": 2,
    #     "long_res": True,
    #     "function": get_features_plan_estimates
    # },
    "get_features_states": {
        "type": "function",
        "description": "This will return the work progress state data for features that are asked about. The features can also be filtered by date, or release.",
        "parameters": {
            "type": "object",
            "properties": {
                "team": {
                    "type": "string",
                    "description": f"The team the user wants the work progress state of features for. The only teams that can be used are listed before."
                },
                "release": {
                    "type": "string",
                    "description": "The release for a certain feature. Only use this field when the user states a release. Releases look like this 2024_Jul_24_GPP-MRPR-Dev. There are no spaces in release names. Do not make up release names."
                },
                "from_date": {
                    "type": "string",
                    "description": "The starting date for the query. Fill this field if the user specifies a start time range, and do one day before the mentioned day. Use the same format as 2024-05-01T05:00:00.000"
                },
                "to_date": {
                    "type": "string",
                    "description": "The end date for the query. Fill this field if the user specifies an end time range, and do one day after the mentioned day. Use the same format as 2024-05-01T05:00:00.000"
                }
            }
        },
        "doc_count": 2,
        "long_res": True,
        "function": get_features_states
    },
    #  "get_user_story_acceptance_criteria": {
    #     "type": "function",
    #     "description": "This will return only the acceptance criteria for user stories that are asked about. The user stories can also be filtered by date, iteration, release, or feature.",
    #     "parameters": {
    #         "type": "object",
    #         "properties": {
    #             "team": {
    #                 "type": "string",
    #                 "description": f"The team the user wants user story acceptance criterias for."
    #             },
    #             "iteration": {
    #                 "type": "string",
    #                 "description": "The iteration for a certain user story. Only use this field when the user states an iteration. Iterations look like this 2024_Jul_24_GPP-MRPR-Dev-Sprint_1. There are no spaces in iteration names. Do not make up iteration names. Keep the exact spelling used."
    #             },
    #             "release": {
    #                 "type": "string",
    #                 "description": "The release for a certain user story. Only use this field when the user states a release. Releases look like this 2024_Jul_24_GPP-MRPR-Dev. There are no spaces in release names. Do not make up release names."
    #             },
    #             "feature": {
    #                 "type": "string",
    #                 "description": "The feature for a certain user story. Only use this field when the user states a feature ID. The feature is formatted as F123456. Do not make up feature IDs."
    #             },
    #             "from_date": {
    #                 "type": "string",
    #                 "description": "The starting date for the query. Fill this field if the user specifies a start time range, and do one day before the mentioned day. Use the same format as 2024-05-01T05:00:00.000"
    #             },
    #             "to_date": {
    #                 "type": "string",
    #                 "description": "The end date for the query. Fill this field if the user specifies an end time range, and do one day after the mentioned day. Use the same format as 2024-05-01T05:00:00.000"
    #             }
    #         }
    #     },
    #     "doc_count": 2,
    #     "long_res": True,
    #     "function": get_user_story_acceptance_criteria
    # },
    # "get_user_story_estimates": {
    #     "type": "function",
    #     "description": "This will return only the estimates for user stories that are asked about. The user stories can also be filtered by date, iteration, release, or feature.",
    #     "parameters": {
    #         "type": "object",
    #         "properties": {
    #             "team": {
    #                 "type": "string",
    #                 "description": f"The team the user wants user story estimates for."
    #             },
    #             "iteration": {
    #                 "type": "string",
    #                 "description": "The iteration for a certain user story. Only use this field when the user states an iteration. Iterations look like this 2024_Jul_24_GPP-MRPR-Dev-Sprint_1. There are no spaces in iteration names. Do not make up iteration names. Keep the exact spelling used."
    #             },
    #             "release": {
    #                 "type": "string",
    #                 "description": "The release for a certain user story. Only use this field when the user states a release. Releases look like this 2024_Jul_24_GPP-MRPR-Dev. There are no spaces in release names. Do not make up release names."
    #             },
    #             "feature": {
    #                 "type": "string",
    #                 "description": "The feature for a certain user story. Only use this field when the user states a feature ID. The feature is formatted as F123456. Do not make up feature IDs."
    #             },
    #             "from_date": {
    #                 "type": "string",
    #                 "description": "The starting date for the query. Fill this field if the user specifies a start time range, and do one day before the mentioned day. Use the same format as 2024-05-01T05:00:00.000"
    #             },
    #             "to_date": {
    #                 "type": "string",
    #                 "description": "The end date for the query. Fill this field if the user specifies an end time range, and do one day after the mentioned day. Use the same format as 2024-05-01T05:00:00.000"
    #             }
    #         }
    #     },
    #     "doc_count": 2,
    #     "long_res": True,
    #     "function": get_user_story_estimates
    # },
    # "get_user_story_descriptions": {
    #     "type": "function",
    #     "description": "This will return only the descriptions for user stories that are asked about. The user stories can also be filtered by date, iteration, release, or feature.",
    #     "parameters": {
    #         "type": "object",
    #         "properties": {
    #             "team": {
    #                 "type": "string",
    #                 "description": f"The team the user wants user story descriptions for."
    #             },
    #             "iteration": {
    #                 "type": "string",
    #                 "description": "The iteration for a certain user story. Only use this field when the user states an iteration. Iterations look like this 2024_Jul_24_GPP-MRPR-Dev-Sprint_1. There are no spaces in iteration names. Do not make up iteration names. Keep the exact spelling used."
    #             },
    #             "release": {
    #                 "type": "string",
    #                 "description": "The release for a certain user story. Only use this field when the user states a release. Releases look like this 2024_Jul_24_GPP-MRPR-Dev. There are no spaces in release names. Do not make up release names."
    #             },
    #             "feature": {
    #                 "type": "string",
    #                 "description": "The feature for a certain user story. Only use this field when the user states a feature ID. The feature is formatted as F123456. Do not make up feature IDs."
    #             },
    #             "from_date": {
    #                 "type": "string",
    #                 "description": "The starting date for the query. Fill this field if the user specifies a start time range, and do one day before the mentioned day. Use the same format as 2024-05-01T05:00:00.000"
    #             },
    #             "to_date": {
    #                 "type": "string",
    #                 "description": "The end date for the query. Fill this field if the user specifies an end time range, and do one day after the mentioned day. Use the same format as 2024-05-01T05:00:00.000"
    #             }
    #         }
    #     },
    #     "doc_count": 2,
    #     "long_res": True,
    #     "function": get_user_story_descriptions
    # },
    "get_user_story_states": {
        "type": "function",
        "description": "This will return only the work progress states for user stories that are asked about. The user stories can also be filtered by date, iteration, release, or feature.",
        "parameters": {
            "type": "object",
            "properties": {
                "team": {
                    "type": "string",
                    "description": f"The team the user wants user story states for."
                },
                "iteration": {
                    "type": "string",
                    "description": "The iteration for a certain user story. Only use this field when the user states an iteration. Iterations look like this 2024_Jul_24_GPP-MRPR-Dev-Sprint_1. There are no spaces in iteration names. Do not make up iteration names. Keep the exact spelling used."
                },
                "release": {
                    "type": "string",
                    "description": "The release for a certain user story. Only use this field when the user states a release. Releases look like this 2024_Jul_24_GPP-MRPR-Dev. There are no spaces in release names. Do not make up release names."
                },
                "feature": {
                    "type": "string",
                    "description": "The feature for a certain user story. Only use this field when the user states a feature ID. The feature is formatted as F123456. Do not make up feature IDs."
                },
                "from_date": {
                    "type": "string",
                    "description": "The starting date for the query. Fill this field if the user specifies a start time range, and do one day before the mentioned day. Use the same format as 2024-05-01T05:00:00.000"
                },
                "to_date": {
                    "type": "string",
                    "description": "The end date for the query. Fill this field if the user specifies an end time range, and do one day after the mentioned day. Use the same format as 2024-05-01T05:00:00.000"
                }
            }
        },
        "doc_count": 2,
        "long_res": True,
        "function": get_user_story_states
    },

    # "get_quick_links": {
    #     "type": "function",
    #     "description": "Use this to pull quick links. Call this function any time a user is asking about links or quick links.",
    #     "parameters": {
    #         "type": "object",
    #         "properties": {
    #             "category": {
    #                 "type": "string",
    #                 "description": f"If the user is asking for a specific category of links, you can provide that here. The only categories that are currently supported are Splunk,Dynatrace,Azure,Zabbix,Other."
    #             }
    #         }
    #     },
    #     "search": True,
    #     "long_res": True,
    #     "function": get_quick_links_info
    # },
    "get_ticket_details": {
        "type": "function",
        "description": "Use this to pull last week worth of incidents or tickets from Servicenow. Call this function without any parameters.",
        "parameters": {
            "type": "object",
            "properties": {}
        },
        "function": get_latest_inc
    },
    "get_latest_prb": {
        "type": "function",
        "description": "Use this to pull last 30 days worth of PRB tickets from Servicenow. Call this function without any parameters.",
        "parameters": {
            "type": "object",
            "properties": {}
        },
        "function": get_latest_prb
    },
    "get_latest_chg": {
        "type": "function",
        "description": "Use this to pull last 30 days worth of CHG tickets from Servicenow. Call this function without any parameters.",
        "parameters": {
            "type": "object",
            "properties": {}
        },
        "function": get_latest_chg
    },
    "get_traffic_error_report": {
        "type": "function",
        # "description": "This will return the 4xx traffic and 5xx traffic or the HTTP traffic by VBF in datetime range. This should be used when the user is asking about splunk or vbf reports on 4xx errors or 5xx errors or http errors or traffic by VBF or splunk VBf stats.",
        "description": "This will return the 4xx traffic and 5xx traffic or the HTTP traffic by VBF in datetime range. This should be used when the user is asking about splunk report, 4xx errors, 5xx errors, http errors, traffic by VBF or splunk VBF stats.",
        "parameters": {
            "type": "object",
            "properties": {
                "from_date": {
                    "type": "string",
                    "description": "The starting date for the query. Fill this field if the user specifies a start time range, and do one day before the mentioned day. Use the same format as 2025-05-01T09:37:01.754Z"
                },
                "to_date": {
                    "type": "string",
                    "description": "The end date for the query. Fill this field if the user specifies an end time range, and do one day after the mentioned day. Use the same format as 2025-05-01T09:37:01.754Z"
                },
            }
        },
        "function": get_splunk_report
    },
    "get_dynatrace_problems":{
        "type": "function",
        "description": "Use this to pull the active or open Dynatrace ( dtsaas ) problems.This should be used always when the user is asking about any open or active Dynatrace or Dtsaas or dynatrace problems , it will return list of problems detected by dynatrace .",
        "parameters": {},
        "search": True,
        "long_res": True,
        "function": get_dynatrace_problems          
    },
    "get_crux_report": {
        "type": "function",
        "description": "This will return the crux or seo metrics a specific vbf in datetime range . Types of VBF are ."+ str(vbf_list),
        # "description": "This will return the crux or SEO metrics in a datetime range. Use this when user asked for crux report, crux metrics report or crux metrics report for specific vbf or all vbfs",
        "parameters": {
            "type": "object",
            "properties": {
                "from_date": {
                    "type": "string",
                    "description": "The starting date for the query. Fill this field if the user specifies a start time range, and do one day before the mentioned day. Use the same format as 2025-05-01T09:37:01.754Z"
                },
                "to_date": {
                    "type": "string",
                    "description": "The end date for the query. Fill this field if the user specifies an end time range, and do one day after the mentioned day. Use the same format as 2025-05-01T09:37:01.754Z"
                },
                 "VBF": {
                    "type": "string",
                    "description": "The VBF key for the query. Fill this field with Uppercase if the user specifies the VBF from the following list: " + str(vbf_list) + ". If no VBF is specified, return results for all VBFs."
                }
            }
        },
        "function": get_crux_report
    },
    "get_performance_report": {
        "type": "function",
        "description": "This will return the page performance scores/report in a datetime range. Use this when the user asks for page performance score, performance metrics report, page load times report, slowest 10% page performance report, or median page performance report.",
        "parameters": {
            "type": "object",
            "properties": {
                "from_date": {
                    "type": "string",
                    "description": "The starting date for the query. Fill this field if the user specifies a start time range, and do one day before the mentioned day. Use the same format as 2025-05-01T09:37:01.754Z"
                },
                "to_date": {
                    "type": "string",
                    "description": "The end date for the query. Fill this field if the user specifies an end time range, and do one day after the mentioned day. Use the same format as 2025-05-01T09:37:01.754Z"
                },
            }
        },
        "function": get_performance_score
    },
    "get_web_link_validator_status": {
        "type": "function",
        "description": "Use this when a user asks about the web link validator status, broken links, link health, or the website health check. This returns the status of the last web link validation run and the next scheduled run.",
        "parameters": {
            "type": "object",
            "properties": {}
        },
        "function": get_web_link_validator_status
    },
    "run_web_link_validator_now": {
        "type": "function",
        "description": "Use this when a user asks to run the web link validator, start a link health check, or scan the website for broken links right now.",
        "parameters": {
            "type": "object",
            "properties": {}
        },
        "function": run_web_link_validator_now
    },
    "get_web_link_validator_report": {
        "type": "function",
        "description": "Use this when a user asks for the web link validator report, broken links report, or link health CSV. Returns the path to the CSV report file.",
        "parameters": {
            "type": "object",
            "properties": {
                "run_id": {
                    "type": "string",
                    "description": "Optional specific run ID to get the report for. Leave empty for the latest run."
                }
            }
        },
        "function": get_web_link_validator_report
    },
    "cancel_web_link_validator_run": {
        "type": "function",
        "description": "Use this when a user asks to cancel or stop the currently running web link validator.",
        "parameters": {
            "type": "object",
            "properties": {}
        },
        "function": cancel_web_link_validator_run
    },
    "email_web_link_validator_report": {
        "type": "function",
        "description": "Use this when a user asks to email or send the web link validator report. Sends the latest link health report via email with CSV attachments.",
        "parameters": {
            "type": "object",
            "properties": {
                "run_id": {
                    "type": "string",
                    "description": "Optional specific run ID to email the report for. Leave empty for the latest run."
                }
            }
        },
        "function": email_web_link_validator_report
    },
}
