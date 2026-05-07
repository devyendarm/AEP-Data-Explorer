import os
import json
from datetime import datetime

# Store application state in user's AppData directory
app_data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'AEP_DataExplorer')
os.makedirs(app_data_dir, exist_ok=True)
PERSISTENCE_FILE = os.path.join(app_data_dir, "state.json")

def save_state(key, data):
    """
    Saves data for a specific key to the persistence file.
    data should be a dict, e.g., {"last_run": "...", "data_path": "..."}
    """
    state = {}
    if os.path.exists(PERSISTENCE_FILE):
        try:
            with open(PERSISTENCE_FILE, 'r') as f:
                state = json.load(f)
        except:
            state = {}
            
    state[key] = data
    
    with open(PERSISTENCE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

def load_state(key):
    """
    Loads data for a specific key. Returns None if not found.
    """
    if not os.path.exists(PERSISTENCE_FILE):
        return None
        
    try:
        with open(PERSISTENCE_FILE, 'r') as f:
            state = json.load(f)
            return state.get(key)
    except:
        return None

def get_current_time_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def save_feeds(feeds):
    """
    Saves the list of feed configurations.
    feeds: list of dicts
    """
    save_state("datafeeds", feeds)

def load_feeds():
    """
    Loads the list of feed configurations. Returns empty list if none.
    """
    feeds = load_state("datafeeds")
    if feeds is None:
        return []
    return feeds

def save_ingestion_tasks(tasks):
    """
    Saves the list of ingestion task configurations.
    tasks: list of dicts
    """
    save_state("ingestion_tasks", tasks)

def load_ingestion_tasks():
    """
    Loads the list of ingestion task configurations. Returns empty list if none.
    """
    tasks = load_state("ingestion_tasks")
    if tasks is None:
        return []
    return tasks

def save_local_queries(queries):
    """
    Saves the list of local query configurations.
    queries: list of dicts
    """
    save_state("local_queries", queries)

def load_local_queries():
    """
    Loads the list of local query configurations. Returns empty list if none.
    """
    queries = load_state("local_queries")
    if queries is None:
        return []
    return queries

def save_profile_tasks(tasks):
    """
    Saves the list of profile lookup configurations.
    tasks: list of dicts
    """
    save_state("profile_tasks", tasks)

def load_profile_tasks():
    """
    Loads the list of profile lookup configurations. Returns empty list if none.
    """
    tasks = load_state("profile_tasks")
    if tasks is None:
        return []
    return tasks

def save_segment_feeds(feeds):
    """
    Saves the list of segment feed configurations.
    feeds: list of dicts
    """
    save_state("segment_feeds", feeds)

def load_segment_feeds():
    """
    Loads the list of segment feed configurations. Returns empty list if none.
    """
    feeds = load_state("segment_feeds")
    if feeds is None:
        return []
    return feeds

def save_workflows(workflows):
    """
    Saves the list of workflow configurations.
    workflows: list of dicts
    """
    save_state("workflows", workflows)

def load_workflows():
    """
    Loads the list of workflow configurations. Returns empty list if none.
    """
    workflows = load_state("workflows")
    if workflows is None:
        return []
    return workflows
