import os, time, base64, json
import numpy as np
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.text import MIMEText

#############
## GLOBALS ##
#############

UTIME_LAST = 0              # Unix time of last chore assignment
UTIME_TARGET = 0            # Unix time of next chore assignment
ROTS = []                   # Group-indexed list of chore rotation state
LOGFILE = None              # Logfile file object
STATEFILE = None            # Statefile file object
EVENT_THRES = 1             # Threshold number of seconds before an event to consider the event as "now".
CHORES = []                 # List of chores
PEOPLE = []                 # List of people (no duplicate elements)
PEOPLE_GROUP = []           # List of lists containing people in each group
NUM_CHORES = 0              # Total number of chores
NUM_GROUPS = 0              # Number of groups
NUM_PEOPLE = 0              # Number of people
NUM_CHORES_GROUP = []       # Number of chores per group
NUM_PEOPLE_GROUP = []       # Number of people per group
ADMIN = None                # instance of class Person who is notified when fatal errors occur.
CREDS = None                # Google oauth credentials object
SELF_ADDRESS = None
DEBUG = True



#############
## CLASSES ##
#############

# Person class
class Person():
    def __init__(self,name,email,choreCommon=None,choreGroup=None,group=None):
        self.name = name
        self.email = email
        self.choreCommon = choreCommon
        self.choreGroup = choreGroup
        self.group = group

# Chore class
class Chore():
    def __init__(self,name,group):
        self.name = name
        self.group = group
        self.status = False



###########
## UTILS ##
###########

# Authenticate
def authenticate():
    global CREDS
    
    writeLog("authenticate() called.")
    
    scopes = ['https://mail.google.com/']
    creds = None

    try:
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', scopes)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', scopes)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        CREDS = creds

    except Exception as e:
        writeLog("Exception occurred in authenticate():{expt}".format(expt=str(e)),level=-1)  
    

# Send Message using Google email
def send(subject,body,people,dummy=True):
    if dummy:
        print("{s}: {b}".format(s=subject,b=body))
    else:

        authenticate()
        service = build('gmail', 'v1', credentials=CREDS)
        
        addresses = []
        for p in people:
            addresses.append(p.email)
        address_str = ", ".join(addresses)

        message = MIMEText(body)
        message['To'] = address_str
        message['From'] = SELF_ADDRESS
        message['Subject'] = subject
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        create_message = {'raw': encoded_message}
        
        service.users().messages().send(userId="me", body=create_message).execute()

# Rotate list
def rotate(list, k):
    return list[k:] + list[:k]

# Write text to log file
def writeLog(text,level=0):
    
    if level == 0:
        lst = "NOTE"
    elif level == 1:
        lst = "WARN"
    elif level == -1:
        lst = "FATAL"
    else:
        lst = "   "

    tstamp = datetime.strftime(datetime.now(),"%Y/%m/%d %H:%M:%S")

    LOGFILE.write(f"[{lst}] <{tstamp}> "+text+"\n")
    LOGFILE.flush()

    if level == -1:
        send("CHOREBOT: A fatal error occured. " + f"[{lst}] <{tstamp}> "+text,ADMIN,dummy=DEBUG)
        exit()

# Load chore rotation indices
def loadState():
    # Load rotation indicies of chores from a file
    #
    # state file is a .txt where ...
    # 1.    first line is the unix time of the last time chores were assigned
    # 2.    following lines are the rotation indices for each group, 
    #           where the group associeted with the index is the row of the state file minus one.
    #           if the rotation index exceeds the length of the chores in the group, 
    #           it will be set to the number of chores in the group.

    global UTIME_LAST, ROTS, STATEFILE

    STATEFILE.close()
    STATEFILE = open(STATEFILE.name,"r")

    lines = STATEFILE.readlines()
    UTIME_LAST = float(lines[0].strip())
    for l in lines[1:None]:
        ROTS.append(int(l.strip()))

    writeLog("Ran loadState().")

# Write state to state file. Inverse of loadState().
def writeState():

    global STATEFILE, UTIME_LAST, ROTS

    STATEFILE.close()
    STATEFILE = open(STATEFILE.name,"w+")

    STATEFILE.write(f"{UTIME_LAST}\n")
    for k,r in enumerate(ROTS):
        STATEFILE.write(f"{r}")
        if k != len(ROTS)-1:
            STATEFILE.write("\n")

    STATEFILE.flush()
    writeLog("Ran writeState().")
    
# Assign chores
def assignChores():

    global UTIME_LAST, PEOPLE, PEOPLE_GROUP
    
    # Wipe chore assignments from people
    for pp in range(len(PEOPLE)):
        PEOPLE[pp].choreCommon = Chore("None",0)
        PEOPLE[pp].choreGroup = Chore("None",0)

    # Loop through chore groups
    chores_local = []
    for gi in range(len(CHORES)):

        # Rotate chores in group
        chores_local.append([])
        chores_local[gi] = rotate(CHORES[gi],ROTS[gi]%len(CHORES[gi]))

        # if common group
        if gi == 0:

            # Loop through people in group
            for pi in range(len(PEOPLE_GROUP[gi])):
                #prev_task = PEOPLE_GROUP[gi][pi].choreCommon
                task = chores_local[gi][pi]
                PEOPLE_GROUP[gi][pi].choreCommon = task
                #if prev_task.name is not "None":
                #    writeLog(f"In assignChores(): {PEOPLE[pi].name} already had common chore {prev_task.name}. It was overwritten by {task.name}.",1)
                #else:
                #    writeLog(f"In assignChores(): {PEOPLE[pi].name} was assigned common chore {task.name}.")
        
        else:

            # Loop through people in group
            for pi in range(len(PEOPLE_GROUP[gi])):
                #prev_task = PEOPLE[gi][pi].choreGroup
                task = chores_local[gi][pi]
                PEOPLE_GROUP[gi][pi].choreGroup = task
                #if prev_task.name is not "None":
                #    writeLog(f"In assignChores(): {PEOPLE[pi].name} already had group chore {prev_task.name}. It was overwritten by {task.name}.",1)
                #else:
                #    writeLog(f"In assignChores(): {PEOPLE[pi].name} was assigned group chore {task.name}.")

    # Collect assignments from PEOPLE_GROUP list
    chore_group_index = [0]*NUM_GROUPS
    for pi, pp in enumerate(PEOPLE):
        pp.choreCommon = chores_local[0][pi]
        pp.choreGroup = chores_local[pp.group][chore_group_index[pp.group]]
        chore_group_index[pp.group] += 1

    # Construct body text
    body_text = "Here are the weekly chore assignments.\n\n"
    for pp in PEOPLE:
        body_text += f'''{pp.name}
    Common chore: {pp.choreCommon.name}
    Group chore: {pp.choreGroup.name}\n\n'''
    
    # Construct subject line
    subject_text = "CHOREBOT: Weekly Assignments"

    send(subject=subject_text,body=body_text,people=PEOPLE,dummy=DEBUG)
    writeLog(f"Email sent with DEBUG {DEBUG}: "+body_text)
    

    UTIME_LAST = time.time()

    writeLog("Ran assignChores().")


def checkTime():

    global UTIME_TARGET

    this, next, now = getNextUtime()
    diff = UTIME_TARGET-now

    if diff <= 0:
        writeLog(f"In checkTime(): Checked for time {UTIME_TARGET} at time {now}. Diff = {diff}.",1)
        diff = next-now
        return({"event":True,"sleep":diff*0.9})
    
    if diff < EVENT_THRES:
        diff = next-now
        response = {"event":True,"sleep":diff*0.9}
    else:
        response = {"event":False,"sleep":diff*0.9}
    
    writeLog(f"In checkTime(): Checked for time {UTIME_TARGET} at time {now}. Diff = {diff}. Event = {response['event']}. Sleep = {response['sleep']}.")
    
    return response


def getNextUtime():

    weekstart_hour = 8
    t_now = datetime.now()
    dt = timedelta(days=t_now.weekday(),hours=t_now.hour,minutes=t_now.minute,seconds=t_now.second,microseconds=t_now.microsecond)

    if t_now.weekday() == 0 and t_now.hour < weekstart_hour:
        dt = dt + timedelta(days=7)
    else:
        dt = timedelta(days=t_now.weekday(),hours=t_now.hour,minutes=t_now.minute,seconds=t_now.second,microseconds=t_now.microsecond)
    
    t_thisweek_start = t_now - dt + timedelta(hours=weekstart_hour)
    t_nextweek_start = t_thisweek_start + timedelta(days=7)

    t_thisweek_start_unix = time.mktime(t_thisweek_start.timetuple())
    t_nextweek_start_unix = time.mktime(t_nextweek_start.timetuple())
    t_now_unix = time.mktime(t_now.timetuple())

    writeLog("Ran getNextUtime().")

    return t_thisweek_start_unix, t_nextweek_start_unix, t_now_unix


def setTarget():

    global UTIME_TARGET

    this, next, now = getNextUtime()

    # Case: Chores haven't been assigned this week
    if now > UTIME_LAST and this > UTIME_LAST:
        UTIME_TARGET = now

    # Case: Chores have been assigned this week
    elif now > UTIME_LAST and this <= UTIME_LAST:
        UTIME_TARGET = next

    # Error: either now is before last assignment or some unknown error.
    else:
        writeLog(f"In setTarget(): Error setting UTIME_TARGET. UTIME_TARGET = {UTIME_TARGET}. now = {now}. UTIME_LAST = {UTIME_LAST}. this = {this}. next = {next}.",-1)

    writeLog("Ran setTarget().")


##########
## MAIN ##
##########

def __main__(debug=True,fname_log=None):

    global LOGFILE, STATEFILE, DEBUG, ADMIN, UTIME_LAST, ROTS, \
    CHORES, PEOPLE, NUM_CHORES, NUM_PEOPLE, NUM_GROUPS, NUM_PEOPLE_GROUP, NUM_CHORES_GROUP, SELF_ADDRESS

    print("Beginning main")

    # Load config settings
    file = open("config.json")
    config = json.load(file)
    file.close()
    DEBUG = debug #config['debug']
    ADMIN = Person(config["admin"]["name"],config["admin"]["email"])
    SELF_ADDRESS = config["bot_email_address"]

    # Open logfile
    if not fname_log:
        fname_log = "{tstamp}.log".format(tstamp=datetime.strftime(datetime.now(),"%Y_%m_%d_%H_%M_%S"))
    LOGFILE = open(fname_log,"w")

    # Open statefile
    STATEFILE = open("state.txt","r+")

    # Open chores and people files for read-in
    file_chores = open("chores.csv","r")
    file_people = open("people.csv","r")
    lines_chores = file_chores.readlines()
    lines_people = file_people.readlines()

    # Load chores and count chores & people, sort chores - Assumes number of groups is equal to max group index + 1 (i.e. no gaps)
    max_group = 0
    chores_all = []
    NUM_CHORES = len(lines_chores)
    for l in lines_chores:
        lsp = l.split(',')
        chores_all.append(Chore(lsp[0],int(lsp[1])))
        if int(lsp[1]) > max_group:
            max_group = int(lsp[1])
    NUM_GROUPS = max_group+1
    for g in range(NUM_GROUPS):
        CHORES.append([])
        PEOPLE_GROUP.append([])
        NUM_CHORES_GROUP.append(0)
        NUM_PEOPLE_GROUP.append(0)
    for cc in chores_all:
        CHORES[cc.group].append(cc)
        NUM_CHORES_GROUP[cc.group] += 1

    # Sort people
    NUM_PEOPLE = len(lines_people)
    for l in lines_people:
        lsp = l.split(',')
        PEOPLE.append(Person(lsp[0],lsp[1],group=int(lsp[2])))
    for pp in PEOPLE:
        PEOPLE_GROUP[0].append(pp)
        PEOPLE_GROUP[pp.group].append(pp)
        NUM_PEOPLE_GROUP[pp.group] += 1

    # Pad chore lists
    for gi in range(NUM_GROUPS):
        if NUM_CHORES_GROUP[gi] < NUM_PEOPLE_GROUP[gi]:
            for pi in range(NUM_PEOPLE_GROUP[gi]):
                try:
                    CHORES[gi][pi] = CHORES[gi][pi]
                except:
                    CHORES[gi].append(Chore("None",0))
        else:
            pass

    # Send admin start message
    send(subject="chorebot start alert",body="CHOREBOT: Chorebot.py has started.",people=[ADMIN],dummy=DEBUG)

    # Load state from file
    loadState()

    # Set target
    setTarget()

    # Main loop
    while(True):
        response = checkTime()

        if response["event"]:
            assignChores()
            ROTS = [k+1 for k in ROTS]
            time.sleep(1.1*EVENT_THRES)
            setTarget()
            writeState()

        writeLog(f"Sleeping {response['sleep']}.")
        time.sleep(response["sleep"])



###########
## TESTS ##
###########

def _test_states():
    global STATEFILE, LOGFILE, UTIME_LAST, ROTS

    LOGFILE = open("_test_states.log","w+")
    STATEFILE = open("_test_states.txt","w+")

    # Test 0: All zeros
    writeLog("Running Test0")
    UTIME_LAST = 0
    ROTS = [0,0,0]
    print(f"[Test 0] Inputs: UTIME_LAST = {UTIME_LAST}, ROTS = [{ROTS[0]},{ROTS[1]},{ROTS[2]}]")
    writeState()
    loadState()
    print(f"[Test 0] Outputs: UTIME_LAST = {UTIME_LAST}, ROTS = [{ROTS[0]},{ROTS[1]},{ROTS[2]}]")

    # Test 1
    writeLog("Running Test1")
    UTIME_LAST = time.time()
    ROTS = [1,2,0]
    print(f"[Test 1] Inputs: UTIME_LAST = {UTIME_LAST}, ROTS = [{ROTS[0]},{ROTS[1]},{ROTS[2]}]")
    writeState()
    loadState()
    print(f"[Test 1] Outputs: UTIME_LAST = {UTIME_LAST}, ROTS = [{ROTS[0]},{ROTS[1]},{ROTS[2]}]")

    # Test 2
    writeLog("Running Test2")
    UTIME_LAST = -1
    ROTS = [-1,-1,-1]
    print(f"[Test 2] Inputs: UTIME_LAST = {UTIME_LAST}, ROTS = [{ROTS[0]},{ROTS[1]},{ROTS[2]}]")
    writeState()
    loadState()
    print(f"[Test 2] Outputs: UTIME_LAST = {UTIME_LAST}, ROTS = [{ROTS[0]},{ROTS[1]},{ROTS[2]}]")

    # Test 3
    writeLog("Running Test3")
    UTIME_LAST = time.time() - 1000
    ROTS = [10,20,100]
    print(f"[Test 3] Inputs: UTIME_LAST = {UTIME_LAST}, ROTS = [{ROTS[0]},{ROTS[1]},{ROTS[2]}]")
    writeState()
    loadState()
    print(f"[Test 3] Outputs: UTIME_LAST = {UTIME_LAST}, ROTS = [{ROTS[0]},{ROTS[1]},{ROTS[2]}]")

def _test_checkTime():
    global LOGFILE
    LOGFILE = open("test.log","w")
    timer = {'event':False,'sleep':1}
    while timer['event'] is not True:
        time.sleep(timer["sleep"])
        timer = checkTime()
        print(f"Checked time. Sleeping {timer['sleep']}")
    print(f"Reached target {UTIME_TARGET} at {time.time()}!")

def _test_getNextUtime():
    global LOGFILE
    LOGFILE = open("_test_getNextUtime.log","w")
    t_thisweek_start_unix, t_nextweek_start_unix, t_now_unix = getNextUtime()
    print("t_thisweek_start_unix:",t_thisweek_start_unix)
    print("t_nextweek_start_unix:",t_nextweek_start_unix)
    print("t_now_unix:",t_now_unix)



############
## SCRIPT ##
############

if __name__ == '__main__':

    pass