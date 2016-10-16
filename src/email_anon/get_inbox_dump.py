from util import *
import csv

dump = open('email_dump.csv', 'wb')
wr = csv.writer(dump, quoting=csv.QUOTE_ALL)
wr.writerow(['From','To','Date','Subject','Body'])
server,_=  setup_servers()

def get_inbox():
    #f = open('email_dump.txt')
    select_info = server.select('INBOX',readonly=True)
    status, response = server.search(None, 'All')
    msg_nums = response[0].split()
    da = []
    for e_id in msg_nums:
        _, response = server.fetch(e_id,'(RFC822)')
        da.append(response[0][1])
    return da

def parse_emails(response):
    for data in response:
                msgStringParsed = email.message_from_string(data)
                frm =  msgStringParsed['From'].split('<')[1][:-1]
                to =  msgStringParsed['To'].split(' ')[0]
                subject = msgStringParsed['Subject']
                body = get_body(msgStringParsed)
                date= msgStringParsed['Date']
                wr.writerow([frm,to,date,subject,body])

data = get_inbox()
parse_emails(data)
