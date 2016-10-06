import email
from imapclient import IMAPClient
import smtplib
import csv

HOST = 'cs-imap-x.stanford.edu' #MAIL Server hostname
USERNAME = 'stats60' #Mailbox username
PASSWORD = 'stats60!' #Mailbox password
HEAD_TA =  "aashna94@stanford.edu"#'ljanson@stanford.edu'
alias1 = 'robota@cs.stanford.edu'
alias2 = 'stats60ta@cs.stanford.edu'
ssl = False

HOST2 = 'cs.stanford.edu'
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart


server = IMAPClient(HOST, use_uid=True, ssl=ssl)
server2 = smtplib.SMTP(HOST2,587)
server2.starttls()
server.login(USERNAME, PASSWORD)
server2.login(USERNAME, PASSWORD)

select_info = server.select_folder('INBOX')
messages = server.search(['ALL'])

print
print 'Messages:[ %d ]'%select_info['EXISTS']
print
response = server.fetch(messages, ['RFC822'])

student_db = {}  ## key: student_email, val: unique id
f = open('statsClassEmails.txt')
i=0
for line in f:
    student_db[str(line.strip())]=i
    i+=1
#print student_db
with open('official_randomization.csv', mode='r') as infile:
    reader = csv.reader(infile)
    student_group = {rows[1]:rows[2] for rows in reader}
student_ta = {1:alias1,2:alias1,3:alias2,4:alias2}
#Loop through message ID, parse the messages and extract the required info
for messagegId,data in response.iteritems():
        messageString= data['RFC822']
        msgStringParsed = email.message_from_string(messageString)
        #print 'Date:%s\nFrom:%s\nSubject:%s\nTo:%s\n%s' % \
        (msgStringParsed['date'],msgStringParsed['From'],msgStringParsed['Subject'],msgStringParsed['To'],msgStringParsed.get_payload())
        
        sender =  msgStringParsed['From'].split('<')[1][:-1]
        ## if email received from student
        if sender != HEAD_TA:
            print 'Student'
            msg = MIMEMultipart()
            msg['From'] = str(student_db[sender])
            msg['To'] = HEAD_TA
            msg['Subject'] = str(student_db[sender])+'##'+ msgStringParsed['Subject']
            print msg.as_string()
            #server2.sendmail(sender, [HEAD_TA], msg.as_string())
            ### Send this email

        # if email received from HEAD-TA
        else:
            print 'TA'
            student_id = int(msgStringParsed['Subject'].split('##')[0])
            msg = MIMEMultipart()
            msg['From'] = student_ta[student_group[student_id]]  # from changed to robota or stats60ta corresponding to the email id that student sent to
            msg['Subject'] = msgStringParsed['Subject'].split('##')[1]
            msg['To'] = student_db.keys()[student_db.values().index(student_id)]
            print msg.as_string()
            #server2.sendmail(sender, [msg['To']], msg.as_string())
            ### Send this email

server.close_folder()
server.logout()