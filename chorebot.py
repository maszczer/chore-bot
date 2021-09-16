from twilio.rest import Client
import os

def send(text,number):
    account_sid = os.environ['TWILIO_ACCOUNT_SID']
    auth_token = os.environ['TWILIO_AUTH_TOKEN']
    client = Client(account_sid,auth_token)
    client.messages.create(\
        body = text,
        from_ = "+17028196468",
        to = number)


if __name__ == 'main':

    file_chores = open("chores.csv")
    file_people = open("people.csv")
    file_log = open("log.csv")

    lines_chores = file_chores.readlines()
    lines_people = file_people.readlines()
    
