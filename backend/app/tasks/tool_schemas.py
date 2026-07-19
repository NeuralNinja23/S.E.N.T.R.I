# Ollama/OpenAI tool schemas for Sentri's local tools registry

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lists all files and subdirectories directly inside a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The directory path to list. Defaults to '.' (root directory)."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the text contents of a file in the workspace within a line range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The relative or absolute path of the file to read."
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "The starting line number to read (1-indexed). Defaults to 1."
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "The ending line number to read (inclusive). Defaults to 800."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_tree",
            "description": "Returns a flat JSON list of all file paths in the entire codebase workspace.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Searches the codebase for matches using Ripgrep. Can search file contents or file names.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The text pattern or string to look for."
                    },
                    "search_type": {
                        "type": "string",
                        "enum": ["content", "filename"],
                        "description": "Search by matching file contents ('content') or file names ('filename'). Defaults to 'content'."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_dependencies",
            "description": "Parses a code file and extracts all its imports and dependencies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path to the file to parse."
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explain_architecture",
            "description": "Generates a high-level JSON map showing components, services, and configuration files of the Sentri project.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explain_module",
            "description": "Locates a specific module (like 'websocket' or 'vision') and summarizes its primary code structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "module_name": {
                        "type": "string",
                        "description": "The name of the module or component to inspect."
                    }
                },
                "required": ["module_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_resource",
            "description": "Opens a system resource link or document path in read-only mode.",
            "parameters": {
                "type": "object",
                "properties": {
                    "resource_path": {
                        "type": "string",
                        "description": "The resource path to access."
                    }
                },
                "required": ["resource_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_externally",
            "description": "Instructs the system workspace to open a file externally in the user's OS native editor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The file path to open."
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_internally",
            "description": "Instructs the system workspace to open a file internally within the active workspace editor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The file path to open."
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Performs a web search to fetch online information or references.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look up on the web."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "Saves a verified, long-term fact about the user's preferences, background, or life in the persistent memory graph.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {
                        "type": "string",
                        "description": "The clean, factual sentence about the user to remember."
                    },
                    "category": {
                        "type": "string",
                        "description": "The memory category for this fact (e.g. 'Identity', 'Career', 'Preference', 'Goal', 'Lifestyle', 'Project')."
                    }
                },
                "required": ["fact", "category"]  # Bug #30: category was missing — caused TypeError on every tool call
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Queries the persistent memory graph database for facts about the user matching a search query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search terms or keyword."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "forget_fact",
            "description": "Deletes user facts or preferences matching query keywords from persistent memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The keyword or term describing what information to delete (e.g. 'Hospitality', 'Rohan', 'favorite color')."
                    }
                },
                "required": ["query"]
            }
        }
    }
]
