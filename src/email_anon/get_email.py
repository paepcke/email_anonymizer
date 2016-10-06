import email
from imapclient import IMAPClient
import smtplib

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
student_group = {82:0} ## key: student unique id, val: 0 (for alias1), 1 (for alias2)
student_ta = {0:alias1,1:alias2}
#Loop through message ID, parse the messages and extract the required info
for messagegId,data in response.iteritems():
        messageString= data['RFC822']
        msgStringParsed = email.message_from_string(messageString)
        #print 'Date:%s\nFrom:%s\nSubject:%s\nTo:%s\n%s' % \
        (msgStringParsed['date'],msgStringParsed['From'],msgStringParsed['Subject'],msgStringParsed['To'],msgStringParsed.get_payload())
        
        sender =  msgStringParsed['From'].split('<')[1][:-1]
        ## if email received from student
        print sender
        if sender != HEAD_TA:
            print 'Student'
            msg = MIMEMultipart()
            msg['From'] = str(student_db[sender])
            msg['To'] = HEAD_TA
            msg['Subject'] = str(student_db[sender])+'##'+ msgStringParsed['Subject']
            text = msg.as_string()
            #server2.sendmail(sender, [HEAD_TA], text)
            ### Send this email

        # if email received from HEAD-TA
        else:
            print 'TA'
            student_id = int(msgStringParsed['Subject'].split('##')[0])
            msg = MIMEMultipart()
            msg['From'] = student_ta[student_group[student_id]]  # from changed to robota or stats60ta corresponding to the email id that student sent to
            msg['Subject'] = msgStringParsed['Subject'].split('##')[1]
            msg['To'] = student_db.keys()[student_db.values().index(student_id)]
            #server2.sendmail(sender, [msg['To']], msg.as_string())
            ### Send this email

server.close_folder()
server.logout()