from twilio.rest import Client
import os, time
import numpy as np
from datetime import datetime, timedelta

#############
## GLOBALS ##
#############

UTIME_LAST = 0              # Unix time of last chore assignment
UTIME_TARGET = 0                  # Unix time of next chore assignment
ROTS = []                   # Group-indexed list of chore rotation state
LOGFILE = None              # Logfile file object
STATEFILE = None            # Statefile file object
S_MIN = 60                  # Seconds in a minute
S_HOUR = S_MIN*60           # Seconds in an hour
S_DAY = S_HOUR*24           # Seconds in a day
S_WEEK = S_DAY*7            # Seconds in a week
EVENT_PERIOD = S_WEEK       # Period of chore assignment event
EVENT_THRES = 5             # Threshold number of seconds before an event to consider the event as "now".
CHORES = []                 # List of chores
PEOPLE = []                 # List of people
ADMIN = None                # instance of class Person who is notified when fatal errors occur.
DEBUG = True



#############
## CLASSES ##
#############

# Person class
class Person():
    def __init__(self,name,number,choreCommon=None,choreGroup=None,group=None):
        self.name = name
        self.number = number
        self.choreCommon = choreCommon
        self.choreGroup = choreGroup
        #self.status = status
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

# Send SMS
def send(text,number,dummy=True):
    if dummy:
        print("SMS Output:",text)
    else:
        account_sid = os.environ['TWILIO_ACCOUNT_SID']
        auth_token = os.environ['TWILIO_AUTH_TOKEN']
        client = Client(account_sid,auth_token)
        client.messages.create(\
            body = text,
            from_ = "+17028196468",
            to = number)

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
        send("CHOREBOT: A fatal error occured. " + f"[{lst}] <{tstamp}> "+text,ADMIN.number,dummy=DEBUG)
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

    global UTIME_LAST, ROTS

    lines = STATEFILE.readlines()
    UTIME_LAST = float(lines[0].strip())
    for k,l in enumerate(lines[1:None]):
        ROTS.append(int(l.strip()))

    writeLog("Ran loadState().")

# Write state to state file. Inverse of loadState().
def writeState():

    global STATEFILE

    STATEFILE.close()
    STATEFILE = open("state.txt","w+")

    STATEFILE.write(f"{UTIME_LAST}\n")
    for k,r in enumerate(ROTS):
        STATEFILE.write(f"{r}")
        if k != len(ROTS)-1:
            STATEFILE.write("\n")

    STATEFILE.flush()
    writeLog("Ran writeState().")
    
# Assign chores
def assignChores():

    global UTIME_LAST
    
    # Wipe chore assignments from people
    for pp in range(len(PEOPLE)):
        PEOPLE[pp].choreCommon = Chore("None",0)
        PEOPLE[pp].choreGroup = Chore("None",0)

    # Pad chore groups
    chores_local = CHORES

    # Loop through chore groups
    for gi, gc in enumerate(chores_local):

        # Rotate chores in group
        chores_local[gi] = rotate(gc,ROTS[gi]%len(CHORES[gi]))

        # if common group
        if gi == 0:

            # Loop through people in group
            for pi in range(len(PEOPLE)):
                prev_task = PEOPLE[pi].choreGroup
                task = chores_local[gi][pi]
                PEOPLE[pi].choreCommon = task
                if prev_task.name is not "None":
                    writeLog(f"In assignChores(): {PEOPLE[pi].name} already had common chore {prev_task.name}. It was overwritten by {task.name}.",1)
                else:
                    writeLog(f"In assignChores(): {PEOPLE[pi].name} was assigned common chore {task.name}.")
        
        else:

            # Loop through people in group
            k = 0
            for pi in range(len(PEOPLE)):
                if PEOPLE[pi].group == gi:
                    prev_task = PEOPLE[pi].choreGroup
                    task = chores_local[gi][k]
                    k += 1
                    PEOPLE[pi].choreGroup = task
                    if prev_task.name is not "None":
                        writeLog(f"In assignChores(): {PEOPLE[pi].name} already had group chore {prev_task.name}. It was overwritten by {task.name}.",1)
                    else:
                        writeLog(f"In assignChores(): {PEOPLE[pi].name} was assigned group chore {task.name}.")

    # Loop through people to send SMS
    for pp in PEOPLE:
        sms = f"CHOREBOT: {pp.name}, your common chore for this week is: {pp.choreCommon.name}.\nYour floor group chore is: {pp.choreGroup.name}."
        send(sms,pp.number,dummy=DEBUG)
        writeLog(f"SMS sent with DEBUG {DEBUG}: "+sms)

    UTIME_LAST = time.time()

    writeLog("Ran assignChores().")


def checkTime():

    global UTIME_TARGET

    now = time.time()
    diff = UTIME_TARGET-now

    if diff < 0:
        writeLog(f"In checkTime(): Checked for time {UTIME_TARGET} at time {now}. Diff = {diff}",1)
        return({"event":True,"sleep":S_DAY})
    
    if diff < EVENT_THRES:
        response = {"event":True,"sleep":EVENT_PERIOD/2}
    else:
        response = {"event":False,"sleep":diff*0.9}
    
    writeLog(f"In checkTime(): Checked for time at {now}. Diff = {diff}. Event = {response['event']}. Sleep = {response['sleep']}.")
    
    return response


def getNextUtime():

    weekstart_hour = 8
    t_now = datetime.now()
    dt = timedelta(days=t_now.weekday(),hours=t_now.hour,minutes=t_now.minute,seconds=t_now.second,microseconds=t_now.microsecond)
    t_thisweek_start = t_now - dt + timedelta(hours=weekstart_hour)
    t_nextweek_start = t_thisweek_start + timedelta(days=7)
    t_thisweek_start_unix = time.mktime(t_thisweek_start.timetuple())
    t_nextweek_start_unix = time.mktime(t_nextweek_start.timetuple())
    t_now_unix = time.time() #time.mktime(t_now.timetuple())

    writeLog("Ran getNextUtime().")

    return t_thisweek_start_unix, t_nextweek_start_unix, t_now_unix


def setTarget():

    global UTIME_TARGET

    this, next, now = getNextUtime()

    # Case: Chores haven't been assigned this week
    if now > UTIME_LAST and this > UTIME_LAST:
        UTIME_TARGET = now

    # Case: Chores have been assigned this week
    elif now > UTIME_LAST and this < UTIME_LAST:
        UTIME_TARGET = next

    # Error: either now is before last assignment or some unknown error.
    else:
        writeLog(f"In setTarget(): Error setting UTIME_TARGET. UTIME_TARGET = {UTIME_TARGET}. now = {now}. UTIME_LAST = {UTIME_LAST}. this = {this}. next = {next}.",-1)

    writeLog("Ran setTarget().")


##########
## MAIN ##
##########

def __main__(debug=True,fname_log=None):

    global LOGFILE, STATEFILE, DEBUG, ADMIN, UTIME_LAST, ROTS, CHORES, PEOPLE

    print("Beginning main")
    DEBUG = debug

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

    # Load Chores
    max_group = 0
    chores_all = []
    for l in lines_chores:
        lsp = l.split(',')
        chores_all.append(Chore(lsp[0],int(lsp[1])))
        if int(lsp[1]) > max_group:
            max_group = int(lsp[1])
    for g in range(max_group+1):
        CHORES.append([])
    for cc in chores_all:
        CHORES[cc.group].append(cc)

    # Load People
    for l in lines_people:
        lsp = l.split(',')
        PEOPLE.append(Person(lsp[0],lsp[1],group=int(lsp[2])))

    # Pad chores
    for cli in range(len(CHORES)):
        for pi in range(len(PEOPLE)):
            try:
                CHORES[cli][pi] = CHORES[cli][pi]
            except:
                CHORES[cli].append(Chore("None",0))

    # Set admin
    ADMIN = Person("Matthew Szczerba", "+18109229593")
    send("CHOREBOT: Chorebot.py has started.",ADMIN.number,dummy=DEBUG)

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
            time.sleep(1)
            setTarget()
            writeState()

        time.sleep(response["sleep"])



###########
## TESTS ##
###########

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
    t_thisweek_start_unix, t_nextweek_start_unix, t_now_unix = getNextUtime()
    print("t_thisweek_start_unix:",t_thisweek_start_unix)
    print("t_nextweek_start_unix:",t_nextweek_start_unix)
    print("t_now_unix:",t_now_unix)



############
## SCRIPT ##
############

if __name__ == '__main__':
    UTIME_TARGET = 1634531400
    EVENT_THRES = 5
    _test_checkTime()