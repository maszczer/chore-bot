from twilio.rest import Client
import os, time
import numpy as np
from datetime import datetime, timedelta


class Person():
    def __init__(self,name,number,chore0=None,choreGroup=None,status=False,group=None):
        self.name = name
        self.number = number
        self.chore0 = chore0
        self.choreGroup = choreGroup
        self.status = status
        self.group = group


class Chore():
    def __init__(self,name,group):
        self.name = name
        self.group = group


def rotate(list, k):
    return list[k:] + list[:k]


def send(text,number,dummy=False):
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


def assign_chores(chores,people,file_log,debug=True):
    for pp in people:
        pp.chore0 = Chore("None",0)
        pp.choreGroup = Chore("None",0)

    pcount = 0
    for c in chores:
        if int(c.group) == 0:
            people[pcount].chore0 = c
            pcount += 1
        if int(c.group) == 1:
            for pp in people:
                if int(pp.group) == 1 and pp.choreGroup.name == "None":
                    pp.choreGroup = c
                    break
        if int(c.group) == 2:
            for pp in people:
                if int(pp.group) == 2 and pp.choreGroup.name == "None":
                    pp.choreGroup = c
                    break

    for pp in people:
        sms = f"CHOREBOT: {pp.name}, your common chore for this week is: {pp.chore0.name}. Your floor group chore is: {pp.choreGroup.name}."
        send(sms,pp.number,dummy=debug)
        write_log(file_log,sms,person=pp)
        file_log.flush()

    return people


def write_log(file,note,person=Person("n/a",0),chore=Chore("None",0)):
    file.write(f"{time.time()},{person.name},{chore.name},{note}\n")


def getWeekStart():
    weekstart_hour = 8
    t_now = datetime.now()
    dt = timedelta(days=t_now.weekday(),hours=t_now.hour,minutes=t_now.minute,seconds=t_now.second,microseconds=t_now.microsecond)
    t_week_start = t_now - dt + timedelta(hours=weekstart_hour)
    t_week_start_unix = time.mktime(t_week_start.timetuple())
    t_now_unix = time.mktime(t_now.timetuple())

    return t_week_start_unix, t_now_unix


if __name__ == '__main__':

    Debug = True

    file_chores = open("chores.csv","r")
    file_people = open("people.csv","r")
    file_log = open("log.csv","a")
    file_last_issue = open("last.txt","r")

    lines_chores = file_chores.readlines()
    lines_people = file_people.readlines()

    # Load Chores
    chores = []
    for l in lines_chores:
        lsp = l.split(',')
        chores.append(Chore(lsp[0],lsp[1]))

    # Load People
    people = []
    for l in lines_people:
        lsp = l.split(',')
        people.append(Person(lsp[0],lsp[1],group=lsp[2]))

    # Get the unix time of last chore issue event from file
    t_last = int(file_last_issue.read())
    file_last_issue.close()

    # Main loop
    write_log(file_log,"Starting main loop")
    file_log.flush()
    while(True):

        # Measure current time and get start of week time (unix for both)
        t_weekStart, t_now = getWeekStart()

        # If the last chore issue event was before the start of the present week, 
        # issue chores and update most recent chore issue event
        if (t_last < t_weekStart):
            people = assign_chores(chores,people,file_log,debug=Debug)
            t_last = t_now
            file_last_issue = open("last.txt","w")
            file_last_issue.write(str(int(t_last)))
            file_last_issue.close()

            people = rotate(people,1)
        else:
            print("Chores already sent this week.")

        # Wait ten minutes
        time.sleep(60*10)
    
